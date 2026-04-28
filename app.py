"""
IDR Scanner API - Phase 2A
Production build with PostgreSQL, email delivery, and evidence logging.
"""

import os
import traceback
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import io

# ── Sentry error alerting ─────────────────────────────────────────────────────
import sentry_sdk
_SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if _SENTRY_DSN:
    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
    print('[STARTUP] Sentry error alerting active')

from scanner.engine import scan_url
from receipt.generator import generate_receipt, verify_receipt, format_receipt_summary
from receipt.pdf_generator import generate_pdf
import hashlib
import secrets
import psycopg2.extras
from datetime import timedelta
from database import (
    queue_sequence, cancel_all_sequences, init_email_queue,
    init_db, save_receipt, get_receipt, get_receipts_by_domain,
    upsert_registry, get_registry, log_evidence, get_evidence_log,
    log_scan_alert,
    create_fix_request, get_fix_requests_by_domain,
    update_fix_request, get_all_pending_fix_domains,
    get_conn,
    init_auth_schema,
    create_magic_token, consume_magic_token,
    create_session_token, validate_session_token, revoke_session_token,
    get_member_dashboard, get_member_evidence,
    get_member_fixes, get_latest_receipt_id,
)
from emailer import send_activation_receipt, send_scan_alert, send_fix_confirmation_email, send_free_summary_email
from confirmation import run_confirmation_scan
from webhook import parse_gumroad_payload, verify_gumroad_seller, is_valid_sale
from kit_integration import on_purchase
from cron import start_cron_scheduler

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.config['JSON_SORT_KEYS'] = False

# ── Rate limiter (in-memory) ──────────────────────────────────────────────────
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

# In-memory fallback when no DB
RECEIPT_STORE = {}

# Initialize database on startup
db_available = init_db()
init_email_queue()
init_auth_schema()
start_cron_scheduler()


def _error(message, code):
    return jsonify({"error": message, "status": code}), code


def _save(receipt, email=None):
    """Save to DB if available, fallback to memory."""
    RECEIPT_STORE[receipt['receipt_id']] = receipt
    if db_available:
        domain = receipt.get('scan', {}).get('domain', '')
        save_receipt(receipt, email)
        upsert_registry(domain, receipt, email)
        log_evidence(domain, receipt['receipt_id'], 'SCAN_COMPLETED',
                     f"Score: {receipt.get('scan',{}).get('overall_score')}/100")


def _get(receipt_id):
    """Get from DB if available, fallback to memory."""
    if db_available:
        return get_receipt(receipt_id)
    return RECEIPT_STORE.get(receipt_id.upper())


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "service": "IDR Scanner API",
        "version": "2.0.0",
        "status": "operational",
        "db": "connected" if db_available else "in-memory"
    })


@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        "service": "IDR Scanner API",
        "version": "2.0.0",
        "protocol": "IDR-BRAND-2026-01",
        "status": "operational",
        "db": "connected" if db_available else "in-memory",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.route('/api/scan', methods=['POST'])
@limiter.limit("10 per minute")
def scan():
    try:
        body = request.get_json(silent=True)
        if not body or 'url' not in body:
            return _error("Request body must include a 'url' field.", 400)
        url = body['url'].strip()
        if not url.startswith(('http://', 'https://')):
            return _error("URL must begin with http:// or https://", 400)

        domain = url.replace('https://','').replace('http://','').split('/')[0]
        scanner_ip = request.remote_addr
        if db_available:
            log_scan_alert(domain, scanner_ip, 'public_scan')

        result = scan_url(url)
        if result.error:
            return _error(f"Scan failed: {result.error}", 502)

        receipt = generate_receipt(result)
        _save(receipt)

        email = body.get('email', '').strip()
        if email and '@' in email and db_available:
            from cron import FREE_SCANNER_STEPS
            def _queue_async():
                try:
                    queue_sequence(
                        email    = email,
                        domain   = domain,
                        sequence = 'free_scanner',
                        receipt  = receipt,
                        steps    = FREE_SCANNER_STEPS
                    )
                    print(f"[SCAN] Nurture sequence queued for {email}")
                except Exception as eq:
                    print(f"[SCAN] Queue error: {eq}")
            threading.Thread(target=_queue_async, daemon=True).start()

        return jsonify(receipt), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(f"Internal error: {str(e)}", 500)


@app.route('/api/activate', methods=['POST', 'OPTIONS'])
def activate():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body = request.get_json(silent=True)
        if not body:
            return _error("Request body required.", 400)

        email = body.get('email', '').strip()
        store_url = body.get('store_url', '').strip()

        if not email or '@' not in email:
            return _error("Valid email required.", 400)
        if not store_url.startswith(('http://', 'https://')):
            return _error("Valid store URL required.", 400)

        result = scan_url(store_url)
        if result.error:
            return _error(f"Could not reach that URL: {result.error}", 502)

        receipt = generate_receipt(result)
        receipt['activated_by'] = email
        _save(receipt, email)

        if db_available:
            log_evidence(
                result.domain, receipt['receipt_id'],
                'ACTIVATION',
                f"Store activated by {email}"
            )

        threading.Thread(
            target=send_activation_receipt,
            args=(email, receipt),
            daemon=True
        ).start()

        return jsonify({
            "success": True,
            "receipt_id": receipt['receipt_id'],
            "registry_id": receipt['registry_id'],
            "registry_url": receipt['registry_url'],
            "score": receipt['scan']['overall_score'],
            "status": receipt['scan']['overall_status'],
            "critical_count": receipt['scan']['critical_count'],
            "total_issues": receipt['scan']['total_issues'],
            "email": email,
            "db_saved": db_available
        }), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(f"Server error: {str(e)}", 500)


@app.route('/api/receipt/<receipt_id>', methods=['GET'])
def get_receipt_route(receipt_id):
    try:
        receipt = _get(receipt_id)
        if not receipt:
            return _error(f"Receipt {receipt_id} not found.", 404)
        return jsonify(receipt), 200
    except Exception as e:
        return _error(str(e), 500)


@app.route('/api/verify', methods=['POST'])
def verify():
    try:
        receipt = request.get_json(silent=True)
        if not receipt:
            return _error("Request body required.", 400)
        result = verify_receipt(receipt)
        return jsonify({
            **result,
            "receipt_id": receipt.get("receipt_id"),
            "domain": receipt.get("scan", {}).get("domain"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200 if result['valid'] else 409
    except Exception as e:
        return _error(str(e), 500)


@app.route('/api/registry/<domain>', methods=['GET'])
def registry_lookup(domain):
    try:
        if db_available:
            reg = get_registry(domain)
            if not reg:
                return _error(f"No registry record for {domain}", 404)
            return jsonify({
                "domain": reg['domain'],
                "registry_id": reg['registry_id'],
                "status": reg['status'],
                "last_scanned": reg['last_scanned'].isoformat() if reg['last_scanned'] else None,
                "latest_score": reg['latest_score'],
                "critical_count": reg['critical_count'],
                "scan_count": reg['scan_count'],
                "registry_url": f"https://idrshield.com/verify/{reg['domain']}",
                "badge_active": reg['badge_active']
            }), 200

        matches = [
            r for r in RECEIPT_STORE.values()
            if r.get('scan', {}).get('domain', '').replace('www.', '') == domain.replace('www.', '')
        ]
        if not matches:
            return _error(f"No records found for domain: {domain}", 404)
        latest = sorted(matches, key=lambda r: r.get('timestamp_utc', ''), reverse=True)[0]
        scan = latest.get('scan', {})
        return jsonify({
            "domain": domain,
            "registry_id": latest.get('registry_id'),
            "last_scanned": latest.get('timestamp_utc'),
            "overall_score": scan.get('overall_score'),
            "overall_status": scan.get('overall_status'),
            "registry_url": latest.get('registry_url'),
        }), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(str(e), 500)


@app.route('/api/evidence/<domain>', methods=['GET'])
def evidence_log_route(domain):
    try:
        if not db_available:
            return _error("Evidence log requires database.", 503)
        log = get_evidence_log(domain)
        return jsonify({
            "domain": domain,
            "entries": log,
            "count": len(log)
        }), 200
    except Exception as e:
        return _error(str(e), 500)


@app.route('/api/badge/<domain>', methods=['GET'])
def badge_status(domain):
    """Live badge status endpoint — called by badge.js on every page load."""
    try:
        if db_available:
            reg = get_registry(domain)
            if not reg:
                return jsonify({"domain": domain, "status": "expired", "verified": False}), 200
            return jsonify({
                "domain": reg['domain'],
                "status": reg['status'],
                "last_scanned": reg['last_scanned'].isoformat() if reg['last_scanned'] else None,
                "score": reg['latest_score'],
                "verified": True,
                "registry_url": f"https://idrshield.com/verify/{reg['domain']}"
            }), 200
        return jsonify({"domain": domain, "status": "monitoring", "verified": False}), 200
    except Exception as e:
        return _error(str(e), 500)


@app.route('/api/badge-image/<domain>', methods=['GET'])
def badge_image(domain):
    """SVG badge image for Wix/Webflow — no JS required."""
    try:
        theme = request.args.get('theme', 'dark')
        size  = max(52, min(int(request.args.get('size', 104)), 160))

        status = 'unverified'
        if db_available:
            reg = get_registry(domain)
            if reg:
                status = reg.get('status', 'monitoring')

        if status == 'active':
            rc, lc, label, op = '#C9A84C', '#E2C97E', 'ACTIVE', '0.95'
        elif status == 'monitoring':
            rc, lc, label, op = '#C8C8D8', '#C8C8D8', 'MONITORING', '0.72'
        else:
            rc, lc, label, op = '#555555', '#555555', 'UNVERIFIED', '0.45'

        cx    = size / 2
        ro    = cx - 0.5
        ri    = ro * 0.685
        sw    = max(1.5, size * 0.025)
        fi    = round(size * 0.27, 1)
        fl    = round(size * 0.075, 1)
        fa    = round(size * 0.058, 1)
        fb    = round(size * 0.052, 1)
        ly    = cx + ri * 0.18
        lx1   = cx - ri * 0.52
        lx2   = cx + ri * 0.52
        ty    = cx + ri * 0.52
        iy    = cx - ri * 0.06
        arc_r = ro - 2
        ax1   = round(cx - arc_r, 2)
        ax2   = round(cx + arc_r, 2)
        fill  = 'none' if theme == 'outline' else '#0A0E1A'
        bg    = '<circle cx="{cx}" cy="{cx}" r="{ro}" fill="{fill}"/>'.format(
                cx=cx, ro=ro, fill=fill) if fill != 'none' else ''

        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg"'
            ' viewBox="0 0 {sz} {sz}" width="{sz}" height="{sz}">'
            '<defs>'
            '<path id="bT{sz}" d="M {ax1},{cx} A {ar},{ar} 0 0,1 {ax2},{cx}"/>'
            '<path id="bB{sz}" d="M {ax1},{cx} A {ar},{ar} 0 0,0 {ax2},{cx}"/>'
            '</defs>'
            '{bg}'
            '<circle cx="{cx}" cy="{cx}" r="{ro}" fill="none"'
            ' stroke="{rc}" stroke-width="{sw}" opacity="{op}"/>'
            '<circle cx="{cx}" cy="{cx}" r="{ri}" fill="none"'
            ' stroke="{rc}" stroke-width="{isw}" opacity="0.28"/>'
            '<text font-family="Arial,sans-serif" font-size="{fa}"'
            ' font-weight="700" letter-spacing="1.2" fill="{rc}" opacity="0.88">'
            '<textPath href="#bT{sz}" startOffset="50%"'
            ' text-anchor="middle" dy="-4">INSTITUTE OF DIGITAL REMEDIATION</textPath>'
            '</text>'
            '<text font-family="Arial,sans-serif" font-size="{fb}"'
            ' font-weight="600" letter-spacing="1.8" fill="{rc}" opacity="0.50">'
            '<textPath href="#bB{sz}" startOffset="50%"'
            ' text-anchor="middle" dy="7">FOUNDING MEMBER</textPath>'
            '</text>'
            '<text x="{cx}" y="{iy}" font-family="Georgia,serif"'
            ' font-size="{fi}" font-weight="700" fill="{rc}"'
            ' text-anchor="middle" dominant-baseline="middle">IDR</text>'
            '<line x1="{lx1}" y1="{ly}" x2="{lx2}" y2="{ly}"'
            ' stroke="#8A6F2E" stroke-width="0.9" opacity="0.65"/>'
            '<text x="{cx}" y="{ty}" font-family="Arial,sans-serif"'
            ' font-size="{fl}" font-weight="600" fill="{lc}"'
            ' text-anchor="middle" letter-spacing="1.5"'
            ' opacity="0.9">{label}</text>'
            '</svg>'
        ).format(
            sz=size, cx=cx, ro=ro, ri=ri, sw=sw,
            isw=max(0.6, size * 0.008),
            fi=fi, fl=fl, fa=fa, fb=fb,
            ly=ly, lx1=lx1, lx2=lx2,
            ty=ty, iy=iy, rc=rc, lc=lc, op=op,
            label=label, bg=bg,
            ax1=ax1, ax2=ax2, ar=arc_r
        )

        return svg, 200, {
            'Content-Type': 'image/svg+xml',
            'Cache-Control': 'public, max-age=300',
            'Access-Control-Allow-Origin': '*'
        }

    except Exception as e:
        fallback = ('<svg xmlns="http://www.w3.org/2000/svg"'
                    ' viewBox="0 0 104 104" width="104" height="104">'
                    '<circle cx="52" cy="52" r="51" fill="#0A0E1A"/>'
                    '<circle cx="52" cy="52" r="51" fill="none"'
                    ' stroke="#555" stroke-width="1.5" opacity="0.45"/>'
                    '<text x="52" y="52" font-family="Georgia,serif"'
                    ' font-size="26" font-weight="700" fill="#555"'
                    ' text-anchor="middle" dominant-baseline="middle">IDR</text>'
                    '</svg>')
        return fallback, 200, {
            'Content-Type': 'image/svg+xml',
            'Access-Control-Allow-Origin': '*'
        }


VALID_CATEGORIES = [
    'alt_text', 'form_labels', 'keyboard_nav',
    'heading_structure', 'contrast', 'aria_links'
]


@app.route('/api/fix-report', methods=['POST', 'OPTIONS'])
def fix_report():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body = request.get_json(silent=True)
        if not body:
            return _error("Request body required.", 400)

        email      = body.get('email', '').strip()
        domain     = body.get('domain', '').strip().replace('https://', '').replace('http://', '').split('/')[0]
        receipt_id = body.get('receipt_id', '').strip()
        categories = body.get('categories', [])
        notes      = body.get('notes', '').strip() or None

        if not email or '@' not in email:
            return _error("Valid email required.", 400)
        if not domain:
            return _error("Domain required.", 400)
        if not receipt_id:
            return _error("Original receipt_id required.", 400)
        if not categories or not isinstance(categories, list):
            return _error("categories must be a non-empty list.", 400)

        invalid = [c for c in categories if c not in VALID_CATEGORIES]
        if invalid:
            return _error(f"Invalid categories: {invalid}. Valid: {VALID_CATEGORIES}", 400)

        if not db_available:
            return _error("Database required for fix reports.", 503)

        original = _get(receipt_id)
        original_counts = {}
        if original:
            from confirmation import API_SLUG_TO_RECEIPT_SLUG
            receipt_slug_counts = {}
            for cat_obj in original.get('scan', {}).get('categories', []):
                slug  = cat_obj.get('slug', '')
                count = int(cat_obj.get('failed', cat_obj.get('issues_count', cat_obj.get('count', 0))))
                if slug:
                    receipt_slug_counts[slug] = count
            for cat in categories:
                receipt_slug = API_SLUG_TO_RECEIPT_SLUG.get(cat)
                original_counts[cat] = receipt_slug_counts.get(receipt_slug, 0) if receipt_slug else 0

        created_ids = []
        for cat in categories:
            fid = create_fix_request(
                domain         = domain,
                receipt_id     = receipt_id,
                reported_by    = email,
                issue_category = cat,
                issue_count    = original_counts.get(cat, 0),
                notes          = notes
            )
            if fid:
                created_ids.append(fid)
                log_evidence(domain, receipt_id, 'FIX_REPORTED',
                             f"{email} marked {cat} as fixed "
                             f"(was {original_counts.get(cat, 0)} issues)")

        if not created_ids:
            return _error("Failed to save fix requests.", 500)

        confirm_result = run_confirmation_scan(domain, triggered_by=email)

        reg = get_registry(domain)
        merchant_email = email
        if not confirm_result.get('error') and not confirm_result.get('no_pending'):
            send_fix_confirmation_email(
                email  = merchant_email,
                domain = domain,
                result = confirm_result
            )

        return jsonify({
            "success":         True,
            "domain":          domain,
            "fix_request_ids": created_ids,
            "categories":      categories,
            "confirmation":    confirm_result
        }), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(f"Server error: {str(e)}", 500)


@app.route('/api/confirm-scan/<domain>', methods=['POST', 'OPTIONS'])
def trigger_confirmation_scan(domain):
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body = request.get_json(silent=True) or {}
        triggered_by = body.get('triggered_by', 'admin')

        if not db_available:
            return _error("Database required for confirmation scans.", 503)

        result = run_confirmation_scan(domain, triggered_by=triggered_by)

        if result.get('error'):
            return jsonify({"success": False, **result}), 502

        if result.get('no_pending'):
            return jsonify({
                "success": True,
                "message": f"No pending fix requests for {domain}",
                **result
            }), 200

        return jsonify({"success": True, **result}), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(f"Server error: {str(e)}", 500)


@app.route('/api/fix-status/<domain>', methods=['GET'])
def fix_status(domain):
    try:
        if not db_available:
            return _error("Database required.", 503)

        clean = domain.replace('www.', '')
        requests = get_fix_requests_by_domain(clean)

        summary = {
            "pending":   [],
            "confirmed": [],
            "partial":   [],
            "failed":    [],
        }
        for r in requests:
            status = r.get('status', 'pending')
            entry = {
                "id":                      r['id'],
                "category":                r['issue_category'],
                "original_count":          r['issue_count'],
                "reported_by":             r['reported_by'],
                "reported_at":             r['created_at'].isoformat() if r.get('created_at') else None,
                "confirmed_at":            r['confirmed_at'].isoformat() if r.get('confirmed_at') else None,
                "confirmation_receipt_id": r.get('confirmation_receipt_id'),
                "notes":                   r.get('notes'),
            }
            if status in summary:
                summary[status].append(entry)

        return jsonify({
            "domain":  clean,
            "total":   len(requests),
            "summary": summary
        }), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(str(e), 500)


@app.route('/api/receipt/<receipt_id>/pdf', methods=['GET'])
def download_pdf(receipt_id):
    try:
        receipt = _get(receipt_id)
        if not receipt:
            return _error(f"Receipt {receipt_id} not found.", 404)

        pdf_bytes = generate_pdf(receipt)
        domain = receipt.get('scan', {}).get('domain', 'idr')
        filename = f"IDR-Receipt-{domain}-{receipt_id[:8]}.pdf"

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(traceback.format_exc())
        return _error(f"PDF generation failed: {str(e)}", 500)


@app.route('/api/scan/summary-email', methods=['POST', 'OPTIONS'])
def summary_email():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body = request.get_json(silent=True)
        if not body:
            return _error('Request body required.', 400)
        email   = body.get('email', '').strip()
        receipt = body.get('receipt', {})
        if not email or '@' not in email:
            return _error('Valid email required.', 400)
        if not receipt:
            return _error('Receipt data required.', 400)
        send_free_summary_email(email, receipt)
        return jsonify({'success': True, 'email': email}), 200
    except Exception as e:
        print(traceback.format_exc())
        return _error(f'Email error: {str(e)}', 500)


@app.route('/api/webhook/gumroad', methods=['POST'])
def gumroad_webhook():
    try:
        form_data = request.form.to_dict()
        parsed = parse_gumroad_payload(form_data)

        print(f"[WEBHOOK] Sale: {parsed['sale_id']} | "
              f"{parsed['email']} | plan={parsed['plan']} | "
              f"test={parsed['test']} | refunded={parsed['refunded']}")

        if not verify_gumroad_seller(parsed.get('seller_id', '')):
            print(f"[WEBHOOK] seller_id failed from {request.remote_addr}")
            return _error("Unauthorized", 401)

        if db_available and parsed.get('email'):
            domain_raw = parsed.get('store_url', 'unknown')
            domain_log = domain_raw.replace('https://','').replace('http://','').split('/')[0]
            log_evidence(domain_log, parsed.get('sale_id', 'ping'),
                         'GUMROAD_PING',
                         f"Sale {parsed['sale_id']} | {parsed['email']} | "
                         f"refunded={parsed['refunded']}")

        valid, reason = is_valid_sale(parsed)
        if not valid:
            print(f"[WEBHOOK] Invalid: {reason}")
            return jsonify({"received": True, "activated": False,
                            "reason": reason}), 200

        email     = parsed['email']
        store_url = parsed['store_url']
        plan      = parsed['plan']
        domain    = store_url.replace('https://','').replace('http://','').split('/')[0].replace('www.','')

        result = scan_url(store_url)
        if result.error:
            print(f"[WEBHOOK] Scan failed for {store_url}: {result.error}")
            return jsonify({"received": True, "activated": False,
                            "reason": f"Scan failed: {result.error}"}), 200

        receipt = generate_receipt(result)
        receipt['activated_by']    = email
        receipt['gumroad_sale_id'] = parsed['sale_id']
        receipt['plan']            = plan
        _save(receipt, email)

        if db_available:
            log_evidence(domain, receipt['receipt_id'],
                         'GUMROAD_ACTIVATION',
                         f"Sale {parsed['sale_id']} | plan={plan}")

        send_activation_receipt(email, receipt)

        if db_available:
            cancel_all_sequences(email)
            from cron import FOUNDER_STEPS
            queue_sequence(
                email    = email,
                domain   = domain,
                sequence = 'founder',
                receipt  = receipt,
                steps    = FOUNDER_STEPS
            )
            print(f"[WEBHOOK] Founder sequence queued for {email}")

        print(f"[WEBHOOK] Activated: {domain} | {email} | {receipt['receipt_id']}")

        return jsonify({
            "received":    True,
            "activated":   True,
            "domain":      result.domain,
            "receipt_id":  receipt['receipt_id'],
            "registry_id": receipt['registry_id'],
            "score":       result.overall_score,
            "plan":        plan
        }), 200

    except Exception as e:
        print(f"[WEBHOOK] Error: {traceback.format_exc()}")
        return jsonify({"received": True, "activated": False,
                        "reason": "Internal error"}), 200


ADMIN_KEY = os.environ.get('ADMIN_KEY', 'IDR-ADMIN-2026')


@app.route('/api/admin/members', methods=['GET'])
def admin_members():
    if request.args.get('key', '') != ADMIN_KEY:
        return _error('Unauthorized', 401)

    if not db_available:
        return _error('Database required for admin endpoint.', 503)

    conn = get_conn()
    if not conn:
        return _error('Database connection failed.', 503)

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    r.domain,
                    r.registry_id,
                    r.status,
                    r.latest_score,
                    r.critical_count,
                    r.scan_count,
                    r.last_scanned,
                    r.badge_active,
                    r.activated_by AS email,
                    rec.receipt_id
                FROM registry r
                LEFT JOIN LATERAL (
                    SELECT receipt_id
                    FROM receipts
                    WHERE domain = r.domain
                    ORDER BY timestamp_utc DESC
                    LIMIT 1
                ) rec ON true
                ORDER BY r.last_scanned DESC NULLS LAST
            """)
            members_raw = cur.fetchall()
            members = []
            for m in members_raw:
                members.append({
                    'domain':         m['domain'],
                    'email':          m['email'] or '',
                    'registry_id':    m['registry_id'],
                    'status':         m['status'],
                    'latest_score':   m['latest_score'],
                    'critical_count': m['critical_count'],
                    'scan_count':     m['scan_count'],
                    'last_scanned':   m['last_scanned'].isoformat() if m['last_scanned'] else None,
                    'badge_active':   m['badge_active'],
                    'receipt_id':     m['receipt_id'] or '',
                })

            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'active')     AS active,
                    COUNT(*) FILTER (WHERE status = 'monitoring') AS monitoring,
                    COUNT(*) FILTER (WHERE status = 'expired')    AS expired,
                    COUNT(*)                                       AS total
                FROM registry
            """)
            counts = dict(cur.fetchone())

            cur.execute("""
                SELECT DISTINCT ON (email)
                    email,
                    domain,
                    step       AS sequence_step,
                    send_after AS next_email_at,
                    created_at AS scanned_at
                FROM email_queue
                WHERE sequence = 'free_scanner'
                  AND cancelled = FALSE
                ORDER BY email, created_at DESC
            """)
            free_raw = cur.fetchall()
            free_scanners = []
            for f in free_raw:
                free_scanners.append({
                    'email':         f['email'],
                    'domain':        f['domain'],
                    'sequence_step': f['sequence_step'],
                    'next_email_at': f['next_email_at'].isoformat() if f['next_email_at'] else None,
                    'scanned_at':    f['scanned_at'].isoformat() if f['scanned_at'] else None,
                })

            cur.execute("""
                SELECT COUNT(*) AS queued
                FROM email_queue
                WHERE sent = FALSE AND cancelled = FALSE
            """)
            queued_count = cur.fetchone()['queued']

            cur.execute("""
                SELECT email, domain, sequence, step, send_after
                FROM email_queue
                WHERE sent = FALSE AND cancelled = FALSE
                ORDER BY send_after ASC
                LIMIT 20
            """)
            next_emails = []
            for e in cur.fetchall():
                next_emails.append({
                    'email':      e['email'],
                    'domain':     e['domain'],
                    'sequence':   e['sequence'],
                    'step':       e['step'],
                    'send_after': e['send_after'].isoformat() if e['send_after'] else None,
                })

        return jsonify({
            'members':       members,
            'free_scanners': free_scanners,
            'next_emails':   next_emails,
            'stats': {
                'total_members':       counts['total'],
                'active':              counts['active'],
                'monitoring':          counts['monitoring'],
                'expired':             counts['expired'],
                'total_free_scanners': len(free_scanners),
                'emails_queued':       queued_count,
            }
        }), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(f'Admin query failed: {str(e)}', 500)
    finally:
        conn.close()


MAGIC_LINK_EXPIRY_MINUTES = 15
SESSION_EXPIRY_DAYS       = 30
PORTAL_BASE_URL           = os.environ.get('PORTAL_BASE_URL', 'https://idrshield.com')


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _get_session_email(req):
    auth = req.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    raw_token = auth[7:].strip()
    if not raw_token:
        return None
    return validate_session_token(_hash_token(raw_token))


def _auth_required(req):
    email = _get_session_email(req)
    if not email:
        return None, _error('Unauthorized — invalid or expired session.', 401)
    return email, None


@app.route('/api/auth/request', methods=['POST', 'OPTIONS'])
def auth_request():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body  = request.get_json(silent=True) or {}
        email = body.get('email', '').strip().lower()

        if not email or '@' not in email:
            return _error('Valid email required.', 400)
        if not db_available:
            return _error('Service unavailable.', 503)

        conn_check  = get_conn()
        email_known = False
        if conn_check:
            try:
                with conn_check.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM registry WHERE activated_by = %s LIMIT 1",
                        (email,)
                    )
                    email_known = cur.fetchone() is not None
            finally:
                conn_check.close()

        if email_known:
            raw_token  = secrets.token_hex(32)
            token_hash = _hash_token(raw_token)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRY_MINUTES)
            ip         = request.remote_addr
            ok = create_magic_token(email, token_hash, expires_at, ip)
            if ok:
                magic_url = f"{PORTAL_BASE_URL}/idrshield_portal.html?token={raw_token}"
                _send_magic_link_email(email, magic_url)
                print(f"[AUTH] Magic link sent to {email}")

        return jsonify({
            'success': True,
            'message': 'If that email is registered, a login link has been sent.'
        }), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(f'Auth error: {str(e)}', 500)


@app.route('/api/auth/verify', methods=['POST', 'OPTIONS'])
def auth_verify():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body  = request.get_json(silent=True) or {}
        token = body.get('token', '').strip()
        if not token:
            return _error('Token required.', 400)
        if not db_available:
            return _error('Service unavailable.', 503)

        ip           = request.remote_addr
        token_hash   = _hash_token(token)
        email        = consume_magic_token(token_hash, ip)

        if not email:
            return _error('This link is invalid, expired, or has already been used.', 401)

        session_raw  = secrets.token_hex(32)
        session_hash = _hash_token(session_raw)
        expires_at   = datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)

        ok = create_session_token(email, session_hash, expires_at, ip)
        if not ok:
            return _error('Could not create session.', 500)

        print(f"[AUTH] Session issued for {email}")
        return jsonify({
            'success':       True,
            'session_token': session_raw,
            'email':         email,
            'expires_at':    expires_at.isoformat(),
        }), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(f'Auth error: {str(e)}', 500)


@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    email, err = _auth_required(request)
    if err:
        return err
    return jsonify({'authenticated': True, 'email': email}), 200


@app.route('/api/auth/logout', methods=['POST', 'OPTIONS'])
def auth_logout():
    if request.method == 'OPTIONS':
        return '', 200
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        raw_token = auth[7:].strip()
        if raw_token:
            revoke_session_token(_hash_token(raw_token))
    return jsonify({'success': True}), 200


@app.route('/api/member/dashboard', methods=['GET'])
def member_dashboard():
    email, err = _auth_required(request)
    if err:
        return err
    try:
        data = get_member_dashboard(email)
        if data is None:
            return _error('No registry record found for this account.', 404)
        return jsonify({'email': email, 'domains': data}), 200
    except Exception as e:
        print(traceback.format_exc())
        return _error(str(e), 500)


@app.route('/api/member/evidence/<domain>', methods=['GET'])
def member_evidence(domain):
    email, err = _auth_required(request)
    if err:
        return err
    try:
        log = get_member_evidence(email, domain)
        if log is None:
            return _error('Domain not found or not owned by this account.', 403)
        return jsonify({'domain': domain, 'entries': log, 'count': len(log)}), 200
    except Exception as e:
        return _error(str(e), 500)


@app.route('/api/member/fixes/<domain>', methods=['GET'])
def member_fixes(domain):
    email, err = _auth_required(request)
    if err:
        return err
    try:
        fixes = get_member_fixes(email, domain)
        if fixes is None:
            return _error('Domain not found or not owned by this account.', 403)
        return jsonify({'domain': domain, 'fixes': fixes}), 200
    except Exception as e:
        return _error(str(e), 500)


@app.route('/api/member/receipt/<domain>/latest/pdf', methods=['GET'])
def member_latest_pdf(domain):
    email, err = _auth_required(request)
    if err:
        return err
    try:
        receipt_id = get_latest_receipt_id(email, domain)
        if not receipt_id:
            return _error('No receipt found for this domain.', 404)
        receipt = get_receipt(receipt_id)
        if not receipt:
            return _error('Receipt data not found.', 404)
        pdf_bytes = generate_pdf(receipt)
        filename  = f"IDR-DefensePackage-{domain}-{receipt_id[:8]}.pdf"
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(traceback.format_exc())
        return _error(f'PDF error: {str(e)}', 500)


@app.route('/api/member/badge-code/<domain>', methods=['GET'])
def member_badge_code(domain):
    email, err = _auth_required(request)
    if err:
        return err
    try:
        reg = get_registry(domain)
        if not reg or reg.get('activated_by') != email:
            return _error('Domain not found or not owned by this account.', 403)
        clean       = domain.replace('www.', '')
        registry_id = reg['registry_id']
        badge_code  = (
            f'<script src="https://idrshield.com/badge.js"\n'
            f'        data-store="{clean}"\n'
            f'        data-id="{registry_id}"\n'
            f'        data-theme="dark"\n'
            f'        data-size="52"\n'
            f'        data-tier="founding">\n'
            f'</script>'
        )
        chip_code = (
            f'<script src="https://idrshield.com/chip.js"\n'
            f'        data-store="{clean}"\n'
            f'        data-id="{registry_id}"\n'
            f'        data-format="pill"\n'
            f'        data-theme="dark"\n'
            f'        data-tier="founding">\n'
            f'</script>'
        )
        return jsonify({
            'domain':       clean,
            'registry_id':  registry_id,
            'badge_code':   badge_code,
            'chip_code':    chip_code,
            'status':       reg['status'],
            'badge_active': reg['badge_active'],
        }), 200
    except Exception as e:
        return _error(str(e), 500)


def _send_magic_link_email(email, magic_url):
    from emailer import _send
    subject    = 'Your IDR Shield login link'
    expiry_str = (datetime.now(timezone.utc) + timedelta(minutes=MAGIC_LINK_EXPIRY_MINUTES)).strftime('%B %d, %Y at %H:%M UTC')
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f5f5f5;margin:0;padding:40px 20px;">
<div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">
  <div style="background:#0A0E1A;padding:28px 36px;border-bottom:3px solid #C9A84C;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:rgba(201,168,76,0.6);margin:0 0 6px;">Institute of Digital Remediation</p>
    <h1 style="font-size:20px;font-weight:normal;color:#FAF7F2;margin:0;">Member Portal Access</h1>
  </div>
  <div style="padding:32px 36px;">
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#333;line-height:1.7;margin:0 0 24px;">
      Click the button below to access your IDR Shield member portal.
      This link expires in <strong>15 minutes</strong> and can only be used once.
    </p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{magic_url}" style="display:inline-block;background:#C9A84C;color:#0A0E1A;font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;padding:15px 36px;text-decoration:none;">
        Access My Portal &rarr;
      </a>
    </div>
    <p style="font-family:Arial,sans-serif;font-size:11px;color:#999;line-height:1.6;margin:0;">
      If you didn't request this, ignore this email — your account is safe.<br>
      Link expires: {expiry_str}
    </p>
  </div>
  <div style="padding:18px 36px;background:#0A0E1A;">
    <p style="font-family:Arial,sans-serif;font-size:10px;color:rgba(250,247,242,0.3);margin:0;">
      Institute of Digital Remediation &middot; idrshield.com &middot; hello@idrshield.com
    </p>
  </div>
</div>
</body></html>"""
    text = f"Your IDR Shield portal login link:\n\n{magic_url}\n\nExpires in 15 minutes. Single use only.\nLink expires: {expiry_str}"
    return _send(email, subject, html, text)


@app.route('/api/stats', methods=['GET'])
def public_stats():
    FOUNDING_TOTAL = 500
    try:
        if not db_available:
            return jsonify({'total_members': 0, 'spots_remaining': FOUNDING_TOTAL, 'founding_open': True}), 200
        conn = get_conn()
        if not conn:
            return jsonify({'total_members': 0, 'spots_remaining': FOUNDING_TOTAL, 'founding_open': True}), 200
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM registry")
                total = cur.fetchone()[0]
        finally:
            conn.close()
        remaining     = max(0, FOUNDING_TOTAL - total)
        founding_open = total < FOUNDING_TOTAL
        return jsonify({
            'total_members':   total,
            'spots_remaining': remaining,
            'founding_open':   founding_open,
        }), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({'total_members': 0, 'spots_remaining': FOUNDING_TOTAL, 'founding_open': True}), 200


@app.route('/api/support/escalate', methods=['POST', 'OPTIONS'])
def support_escalate():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body        = request.get_json(silent=True) or {}
        name        = body.get('name', '').strip()
        email       = body.get('email', '').strip()
        domain      = body.get('domain', '').strip()
        phone       = body.get('phone', '').strip()
        description = body.get('description', '').strip()
        convo       = body.get('conversation_summary', '').strip()

        if not name or not email or not description:
            return _error('name, email, and description required.', 400)

        from emailer import _send

        subject = f'[LEGAL ESCALATION] {domain or email} — Action Required'
        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">
  <div style="background:#0A0E1A;padding:24px 32px;border-bottom:3px solid #C9A84C;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:rgba(201,168,76,0.7);margin:0 0 6px;">IDR Shield — Legal Escalation</p>
    <h1 style="font-size:20px;font-weight:normal;color:#FAF7F2;margin:0;">Action Required</h1>
  </div>
  <div style="padding:28px 32px;border-bottom:1px solid #f0ede6;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;">
      <tr><td style="padding:6px 0;color:#999;width:120px;">Name</td><td style="padding:6px 0;color:#333;font-weight:600;">{name}</td></tr>
      <tr><td style="padding:6px 0;color:#999;">Email</td><td style="padding:6px 0;color:#333;">{email}</td></tr>
      <tr><td style="padding:6px 0;color:#999;">Domain</td><td style="padding:6px 0;color:#333;">{domain or '—'}</td></tr>
      <tr><td style="padding:6px 0;color:#999;">Phone</td><td style="padding:6px 0;color:#333;">{phone or '—'}</td></tr>
    </table>
  </div>
  <div style="padding:28px 32px;border-bottom:1px solid #f0ede6;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#C9A84C;margin:0 0 10px;">Situation Description</p>
    <p style="font-family:Georgia,serif;font-size:14px;color:#333;line-height:1.7;margin:0;">{description}</p>
  </div>
  {'<div style="padding:28px 32px;background:#fafafa;"><p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#999;margin:0 0 10px;">Conversation Summary</p><pre style="font-family:Georgia,serif;font-size:12px;color:#555;line-height:1.7;white-space:pre-wrap;margin:0;">' + convo + '</pre></div>' if convo else ''}
  <div style="padding:20px 32px;background:#0A0E1A;">
    <p style="font-family:Arial,sans-serif;font-size:10px;color:rgba(250,247,242,0.3);margin:0;">
      IDR Shield · Escalated via Reid Support Specialist · {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}
    </p>
  </div>
</div>
</body></html>"""

        text = f"""IDR LEGAL ESCALATION — ACTION REQUIRED

Name:   {name}
Email:  {email}
Domain: {domain or '—'}
Phone:  {phone or '—'}

Description:
{description}

{'Conversation Summary:' + chr(10) + convo if convo else ''}

Escalated via Reid — {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}
"""
        sent = _send('support@idrshield.com', subject, html, text)

        if db_available and domain:
            log_evidence(
                domain.replace('www.', ''),
                'SUPPORT-ESCALATION',
                'LEGAL_ESCALATION',
                f"Escalated by {name} ({email}) via Reid"
            )

        return jsonify({'success': True, 'sent': sent}), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(f'Escalation error: {str(e)}', 500)


ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')


@app.route('/api/support/chat', methods=['POST', 'OPTIONS'])
def support_chat():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        if not ANTHROPIC_API_KEY:
            return _error('AI service not configured.', 503)

        body     = request.get_json(silent=True) or {}
        system   = body.get('system', '')
        messages = body.get('messages', [])

        if not messages:
            return _error('messages required.', 400)

        clean_messages = []
        for m in messages:
            role    = m.get('role', '')
            content = m.get('content', '')
            if role in ('user', 'assistant') and isinstance(content, str) and content.strip():
                clean_messages.append({'role': role, 'content': content.strip()})

        if not clean_messages:
            return _error('No valid messages provided.', 400)

        import urllib.request as urlreq
        import json as _json

        payload = {
            'model':      'claude-sonnet-4-20250514',
            'max_tokens': 1024,
            'system':     system,
            'messages':   clean_messages,
        }

        req = urlreq.Request(
            'https://api.anthropic.com/v1/messages',
            data=_json.dumps(payload).encode('utf-8'),
            headers={
                'x-api-key':         ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'Content-Type':      'application/json',
            },
            method='POST'
        )

        with urlreq.urlopen(req, timeout=30) as resp:
            data  = _json.loads(resp.read().decode('utf-8'))
            reply = ''.join(
                b.get('text', '')
                for b in data.get('content', [])
                if b.get('type') == 'text'
            )

        return jsonify({'success': True, 'reply': reply}), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(f'Chat error: {str(e)}', 500)


# ── HHS Registry Endpoint ─────────────────────────────────────────────────────

@app.route('/api/hhs/registry/<path:domain>', methods=['GET'])
def hhs_registry(domain):
    domain = domain.lower().strip().rstrip('/')
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("""
            SELECT status, registry_id, last_scanned, latest_score,
                   critical_count, scan_count
            FROM registry
            WHERE domain = %s
              AND hhs_enrolled = TRUE
        """, (domain,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return jsonify({'error': 'not enrolled', 'status': 'not_monitored'}), 404
        status = row[0]
        if status in ('active', 'monitoring'):
            display_status = 'active'
        elif status in ('manual_verified', 'verified'):
            display_status = 'on_record'
        else:
            return jsonify({'error': 'not enrolled', 'status': 'not_monitored'}), 404
        return jsonify({
            'status':         display_status,
            'domain':         domain,
            'registry_id':    row[1],
            'registry_url':   'https://idrshield.com/hhs-verify/' + domain,
            'last_scanned':   str(row[2]) if row[2] else None,
            'latest_score':   row[3],
            'critical_count': row[4],
            'scan_count':     row[5],
            'sector':         'hhs',
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Stripe HHS Webhook ────────────────────────────────────────────────────────

import stripe

STRIPE_WEBHOOK_SECRET_HHS = os.environ.get('STRIPE_WEBHOOK_SECRET_HHS', '')


@app.route('/api/webhook/stripe/hhs', methods=['POST'])
def stripe_hhs_webhook():
    payload = request.get_data()
    sig     = request.headers.get('Stripe-Signature', '')

    if not STRIPE_WEBHOOK_SECRET_HHS:
        return _error('Webhook secret not configured', 500)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig, STRIPE_WEBHOOK_SECRET_HHS
        )
    except stripe.error.SignatureVerificationError as e:
        print(f'[HHS WEBHOOK] Signature failed: {e}')
        return _error('Invalid signature', 400)
    except Exception as e:
        print(f'[HHS WEBHOOK] Parse error: {e}')
        return _error('Bad payload', 400)

    if event['type'] != 'checkout.session.completed':
        return jsonify({'received': True, 'action': 'ignored'}), 200

    import json as _json
    session = _json.loads(payload.decode('utf-8'))['data']['object']

    domain = session.get('client_reference_id') or None
    if not domain:
        try:
            custom_fields = session.get('custom_fields', []) or []
            for field in custom_fields:
                try:
                    label_obj = field.get('label', {}) or {}
                    label_str = str(label_obj.get('custom', '') or '').lower()
                    if 'website' in label_str or 'domain' in label_str:
                        text_obj = field.get('text', {}) or {}
                        domain = text_obj.get('value') or None
                        if domain:
                            break
                except Exception:
                    continue
        except Exception:
            pass

    if not domain:
        print('[HHS WEBHOOK] No domain found — skipping')
        return jsonify({'received': True, 'action': 'no_domain'}), 200

    domain = str(domain).strip().lower()
    domain = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]

    amount           = session.get('amount_total', 0)
    customer_details = session.get('customer_details', {}) or {}
    email            = customer_details.get('email', '') or ''
    is_audit         = (amount == 49700)
    is_monitoring    = (amount == 4900)

    print(f'[HHS WEBHOOK] domain={domain} email={email} amount={amount} audit={is_audit} monitoring={is_monitoring}')

    if not db_available:
        return jsonify({'received': True, 'action': 'db_unavailable'}), 200

    conn = get_conn()
    if not conn:
        return jsonify({'received': True, 'action': 'db_error'}), 200

    try:
        with conn.cursor() as cur:
            if is_audit:
                cur.execute("""
                    INSERT INTO registry
                        (domain, registry_id, status, hhs_enrolled, product_lane, activated_by, created_at, updated_at)
                    VALUES
                        (%s, %s, 'manual_verified', TRUE, 'hhs', %s, NOW(), NOW())
                    ON CONFLICT (domain) DO UPDATE SET
                        status       = 'manual_verified',
                        hhs_enrolled = TRUE,
                        product_lane = 'hhs',
                        activated_by = COALESCE(registry.activated_by, EXCLUDED.activated_by),
                        updated_at   = NOW()
                """, (domain, f'IDR-HHS-{domain.upper().replace(".", "-")}', email))
                conn.commit()
                log_evidence(domain, 'STRIPE-HHS-AUDIT', 'HHS_AUDIT_PAYMENT',
                             f'$497 audit payment from {email}')
                try:
                    from hhs_emailer import send_hhs_activation_confirmation, send_payment_notification
                    if email:
                        send_hhs_activation_confirmation(email, domain)
                    send_payment_notification(domain, email, 49700, 'audit')
                except Exception as ex:
                    print(f'[HHS WEBHOOK] Email error: {ex}')
                if email:
                    try:
                        from cron import HHS_UPSELL_STEPS
                        queue_sequence(
                            email    = email,
                            domain   = domain,
                            sequence = 'hhs_upsell',
                            receipt  = {'registry_id': f'IDR-HHS-{domain.upper().replace(".", "-")}'},
                            steps    = HHS_UPSELL_STEPS
                        )
                        print(f'[HHS WEBHOOK] HHS upsell sequence queued for {email}')
                    except Exception as eq:
                        print(f'[HHS WEBHOOK] Sequence queue error: {eq}')

                return jsonify({
                    'received': True,
                    'action':   'hhs_audit_activated',
                    'domain':   domain,
                    'status':   'manual_verified'
                }), 200

            elif is_monitoring:
                cur.execute("""
                    INSERT INTO registry
                        (domain, registry_id, status, hhs_enrolled, product_lane, activated_by, created_at, updated_at)
                    VALUES
                        (%s, %s, 'active', TRUE, 'hhs', %s, NOW(), NOW())
                    ON CONFLICT (domain) DO UPDATE SET
                        status       = 'active',
                        hhs_enrolled = TRUE,
                        product_lane = 'hhs',
                        updated_at   = NOW()
                """, (domain, f'IDR-HHS-{domain.upper().replace(".", "-")}', email))
                conn.commit()
                log_evidence(domain, 'STRIPE-HHS-MONITORING', 'HHS_MONITORING_PAYMENT',
                             f'$49/mo monitoring payment from {email}')
                try:
                    from hhs_emailer import send_hhs_monitoring_welcome, send_payment_notification
                    if email:
                        send_hhs_monitoring_welcome(email, domain)
                    send_payment_notification(domain, email, 4900, 'monitoring')
                except Exception as ex:
                    print(f'[HHS WEBHOOK] Email error: {ex}')
                if email:
                    try:
                        cancel_all_sequences(email)
                        print(f'[HHS WEBHOOK] HHS upsell sequence cancelled for {email} — converted to monitoring')
                    except Exception as eq:
                        print(f'[HHS WEBHOOK] Cancel sequence error: {eq}')

                return jsonify({
                    'received': True,
                    'action':   'hhs_monitoring_activated',
                    'domain':   domain,
                    'status':   'active'
                }), 200

            else:
                print(f'[HHS WEBHOOK] Unknown amount {amount} for {domain}')
                return jsonify({
                    'received': True,
                    'action':   'unknown_amount',
                    'amount':   amount
                }), 200

    except Exception as e:
        print(f'[HHS WEBHOOK] DB error: {traceback.format_exc()}')
        conn.rollback()
        return jsonify({'received': True, 'action': 'db_error'}), 200
    finally:
        conn.close()


# ── HHS Manual Audit Delivery ─────────────────────────────────────────────────

@app.route('/api/hhs/manual-deliver', methods=['POST', 'OPTIONS'])
def hhs_manual_deliver():
    """
    Hans-Peter's admin endpoint — receives completed manual audit form,
    generates the 30-page PDF, and delivers it to the client.
    Called from hhs_audit_delivery.html.
    """
    if request.method == 'OPTIONS':
        return '', 200

    try:
        body = request.get_json(silent=True)
        if not body:
            return _error('Request body required.', 400)

        if body.get('admin_key', '') != ADMIN_KEY:
            return _error('Unauthorized', 401)

        client_email  = body.get('client_email', '').strip()
        domain        = body.get('domain', '').strip().lower()
        receipt_id    = body.get('receipt_id', '').strip()
        registry_id   = body.get('registry_id', '').strip()
        timestamp_utc = body.get('timestamp_utc', '')
        organization  = body.get('organization', {})
        scan_data     = body.get('scan', {})
        manual_checks = body.get('manual_checks', {})

        if not client_email or '@' not in client_email:
            return _error('Valid client_email required.', 400)
        if not domain:
            return _error('domain required.', 400)
        if not receipt_id:
            return _error('receipt_id required.', 400)

        domain = domain.replace('https://','').replace('http://','').replace('www.','').split('/')[0]

        if not registry_id:
            registry_id = 'IDR-HHS-' + domain.upper().replace('.', '-')

        if not timestamp_utc:
            timestamp_utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        scan_data['manual_checks'] = manual_checks
        scan_data['domain']        = scan_data.get('domain', domain)

        import hashlib, json as _json
        payload_str = _json.dumps({
            'receipt_id':  receipt_id,
            'registry_id': registry_id,
            'timestamp':   timestamp_utc,
            'domain':      domain,
            'scan':        scan_data,
        }, sort_keys=True)
        doc_hash = hashlib.sha256(payload_str.encode()).hexdigest()

        receipt_data = {
            'receipt_id':    receipt_id,
            'registry_id':   registry_id,
            'timestamp_utc': timestamp_utc,
            'hash':          doc_hash,
            'activated_by':  client_email,
            'organization':  organization,
            'scan':          scan_data,
        }

        from receipt.hhs_pdf_generator import generate_hhs_pdf
        pdf_bytes = generate_hhs_pdf(receipt_data)
        print(f'[HHS_DELIVER] PDF generated — {len(pdf_bytes):,} bytes for {domain}')

        from hhs_emailer import send_hhs_audit_delivery
        score   = scan_data.get('overall_score', 0)
        crits   = scan_data.get('critical_count', 0)
        total   = scan_data.get('total_issues', 0)
        serious = scan_data.get('serious_count', 0)

        sent = send_hhs_audit_delivery(
            email         = client_email,
            domain        = domain,
            score         = score,
            crits         = crits,
            total         = total,
            receipt_id    = receipt_id,
            registry_id   = registry_id,
            timestamp_utc = timestamp_utc,
            organization  = organization,
            scan_data     = scan_data,
        )

        if db_available:
            log_evidence(
                domain, receipt_id,
                'HHS_AUDIT_DELIVERED',
                f'Manual audit delivered to {client_email} by Hans-Peter. '
                f'Score: {score}/100, Critical: {crits}, Total: {total}'
            )
            conn = get_conn()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE registry SET
                                status         = 'manual_verified',
                                latest_score   = %s,
                                critical_count = %s,
                                last_scanned   = NOW(),
                                updated_at     = NOW()
                            WHERE domain = %s
                        """, (score, crits, domain))
                finally:
                    conn.close()

        print(f'[HHS_DELIVER] Delivered to {client_email} | sent={sent}')

        return jsonify({
            'success':    True,
            'domain':     domain,
            'receipt_id': receipt_id,
            'email_sent': sent,
            'pdf_bytes':  len(pdf_bytes),
            'score':      score,
        }), 200

    except Exception as e:
        print(f'[HHS_DELIVER] Error: {traceback.format_exc()}')
        return _error(f'Delivery failed: {str(e)}', 500)


# ── HHS Org Data Capture ──────────────────────────────────────────────────────

@app.route('/api/hhs/capture', methods=['POST', 'OPTIONS'])
def hhs_capture():
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body        = request.get_json(silent=True) or {}
        domain      = body.get('domain', '').strip().lower()
        org_name    = body.get('org_name', '').strip()
        org_contact = body.get('org_contact', '').strip()
        org_title   = body.get('org_title', '').strip()
        org_phone   = body.get('org_phone', '').strip()
        org_address = body.get('org_address', '').strip()
        if not domain:
            return _error('domain required.', 400)
        if not org_name:
            return _error('org_name required.', 400)
        domain = domain.replace('https://','').replace('http://','').replace('www.','').split('/')[0]
        if db_available:
            conn = get_conn()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO registry
                                (domain, registry_id, org_name, org_contact, org_title, org_phone, org_address, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                            ON CONFLICT (domain) DO UPDATE SET
                                org_name    = EXCLUDED.org_name,
                                org_contact = EXCLUDED.org_contact,
                                org_title   = EXCLUDED.org_title,
                                org_phone   = EXCLUDED.org_phone,
                                org_address = EXCLUDED.org_address,
                                updated_at  = NOW()
                        """, (
                            domain,
                            'IDR-HHS-' + domain.upper().replace('.', '-'),
                            org_name, org_contact, org_title, org_phone, org_address
                        ))
                        conn.commit()
                finally:
                    conn.close()
        print('[HHS CAPTURE] Stored org data for ' + domain + ': ' + org_name)
        return jsonify({'success': True, 'domain': domain}), 200
    except Exception as e:
        print(traceback.format_exc())
        return _error('Capture error: ' + str(e), 500)


@app.route('/api/hhs/org-data/<path:domain>', methods=['GET'])
def hhs_org_data(domain):
    domain = domain.lower().strip().replace('https://','').replace('http://','').replace('www.','').split('/')[0]
    try:
        conn = get_conn()
        if not conn:
            return _error('DB unavailable', 503)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT org_name, org_contact, org_title, org_phone, org_address,
                       activated_by, registry_id, status, latest_score, critical_count
                FROM registry WHERE domain = %s
            """, (domain,))
            row = cur.fetchone()
        conn.close()
        if not row:
            return jsonify({'found': False, 'domain': domain}), 200
        return jsonify({
            'found':          True,
            'domain':         domain,
            'org_name':       row[0] or '',
            'org_contact':    row[1] or '',
            'org_title':      row[2] or '',
            'org_phone':      row[3] or '',
            'org_address':    row[4] or '',
            'email':          row[5] or '',
            'registry_id':    row[6] or '',
            'status':         row[7] or '',
            'score':          row[8] or 0,
            'critical_count': row[9] or 0,
        }), 200
    except Exception as e:
        print(traceback.format_exc())
        return _error(str(e), 500)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
