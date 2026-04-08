"""
IDR Scanner API - Phase 2A
Production build with PostgreSQL, email delivery, and evidence logging.
"""

import os
import traceback
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io

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
def scan():
    try:
        body = request.get_json(silent=True)
        if not body or 'url' not in body:
            return _error("Request body must include a 'url' field.", 400)
        url = body['url'].strip()
        if not url.startswith(('http://', 'https://')):
            return _error("URL must begin with http:// or https://", 400)

        # Log as external scan alert
        domain = url.replace('https://','').replace('http://','').split('/')[0]
        scanner_ip = request.remote_addr
        if db_available:
            log_scan_alert(domain, scanner_ip, 'public_scan')

        result = scan_url(url)
        if result.error:
            return _error(f"Scan failed: {result.error}", 502)

        receipt = generate_receipt(result)
        _save(receipt)

        # Queue free scanner nurture sequence if email provided
        email = body.get('email', '').strip()
        if email and '@' in email and db_available:
            from cron import FREE_SCANNER_STEPS
            queue_sequence(
                email    = email,
                domain   = domain,
                sequence = 'free_scanner',
                receipt  = receipt,
                steps    = FREE_SCANNER_STEPS
            )
            print(f"[SCAN] Nurture sequence queued for {email}")

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

        # Send receipt email
        send_activation_receipt(email, receipt)

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

        # Fallback to memory
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
        size  = max(28, min(int(request.args.get('size', 52)), 160))

        status = 'unverified'
        if db_available:
            reg = get_registry(domain)
            if reg:
                status = reg.get('status', 'monitoring')

        if status == 'active':
            rc, lc, label, op = '#C9A84C', '#E2C97E', 'ACTIVE', '0.95'
        elif status == 'monitoring':
            rc, lc, label, op = '#C8C8D8', '#C8C8D8', 'MONITORING', '0.75'
        else:
            rc, lc, label, op = '#555555', '#555555', 'UNVERIFIED', '0.45'

        cx     = size / 2
        ro     = cx - 0.5
        ri     = ro * 0.5
        sw     = max(1.5, size * 0.03)
        fi     = size * 0.26
        fl     = size * 0.07
        ly     = cx + ri * 0.22
        lx1    = cx - ri * 0.55
        lx2    = cx + ri * 0.55
        ty     = cx + ri * 0.55
        iy     = cx - ri * 0.07
        fill   = 'none' if theme == 'outline' else '#0A0E1A'
        bg     = ('<circle cx="{cx}" cy="{cx}" r="{ro}" fill="{fill}"/>'.format(
                    cx=cx, ro=ro, fill=fill)) if fill != 'none' else ''

        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg"'
            ' viewBox="0 0 {sz} {sz}" width="{sz}" height="{sz}">'
            '{bg}'
            '<circle cx="{cx}" cy="{cx}" r="{ro}" fill="none"'
            ' stroke="{rc}" stroke-width="{sw}" opacity="{op}"/>'
            '<circle cx="{cx}" cy="{cx}" r="{ri}" fill="none"'
            ' stroke="{rc}" stroke-width="0.7" opacity="0.28"/>'
            '<text x="{cx}" y="{iy}" font-family="Georgia,serif"'
            ' font-size="{fi}" font-weight="700" fill="{rc}"'
            ' text-anchor="middle" dominant-baseline="middle">IDR</text>'
            '<line x1="{lx1}" y1="{ly}" x2="{lx2}" y2="{ly}"'
            ' stroke="#8A6F2E" stroke-width="0.9" opacity="0.65"/>'
            '<text x="{cx}" y="{ty}" font-family="Arial,sans-serif"'
            ' font-size="{fl}" font-weight="600" fill="{lc}"'
            ' text-anchor="middle" letter-spacing="1.2"'
            ' opacity="0.9">{label}</text>'
            '</svg>'
        ).format(
            sz=size, cx=cx, ro=ro, ri=ri, sw=sw,
            fi=fi, fl=fl, ly=ly, lx1=lx1, lx2=lx2,
            ty=ty, iy=iy, rc=rc, lc=lc, op=op,
            label=label, bg=bg
        )

        return svg, 200, {
            'Content-Type': 'image/svg+xml',
            'Cache-Control': 'public, max-age=300',
            'Access-Control-Allow-Origin': '*'
        }

    except Exception as e:
        fallback = ('<svg xmlns="http://www.w3.org/2000/svg"'
                    ' viewBox="0 0 52 52" width="52" height="52">'
                    '<circle cx="26" cy="26" r="25" fill="#0A0E1A"/>'
                    '<circle cx="26" cy="26" r="25" fill="none"'
                    ' stroke="#555" stroke-width="1.5" opacity="0.45"/>'
                    '<text x="26" y="26" font-family="Georgia,serif"'
                    ' font-size="13" font-weight="700" fill="#555"'
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
    """
    Merchant calls this to say 'I fixed these issues.'
    Body: { email, domain, receipt_id, categories: ['alt_text', 'contrast'], notes? }
    Creates a fix_request per category, then queues a confirmation scan.
    """
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

        # ── Look up original scan to capture issue counts ──────────────────
        original = _get(receipt_id)
        original_counts = {}
        if original:
            # categories is a LIST of objects: [{"slug": "image_alt_text", "failed": 3}, ...]
            # Build a receipt_slug → count lookup first, then translate via API_SLUG_TO_RECEIPT_SLUG
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

        # ── Create one fix_request per category ───────────────────────────
        created_ids = []
        for cat in categories:
            fid = create_fix_request(
                domain     = domain,
                receipt_id = receipt_id,
                reported_by= email,
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

        # ── Trigger confirmation scan immediately ──────────────────────────
        confirm_result = run_confirmation_scan(domain, triggered_by=email)

        # Send result email
        reg = get_registry(domain)
        merchant_email = email
        if not confirm_result.get('error') and not confirm_result.get('no_pending'):
            send_fix_confirmation_email(
                email    = merchant_email,
                domain   = domain,
                result   = confirm_result
            )

        return jsonify({
            "success":        True,
            "domain":         domain,
            "fix_request_ids": created_ids,
            "categories":     categories,
            "confirmation":   confirm_result
        }), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(f"Server error: {str(e)}", 500)


@app.route('/api/confirm-scan/<domain>', methods=['POST', 'OPTIONS'])
def trigger_confirmation_scan(domain):
    """
    Manually trigger a confirmation scan for a domain.
    Useful for cron jobs or admin re-runs.
    Body (optional): { triggered_by: 'cron' | 'admin' | email }
    """
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
    """
    Returns all fix requests for a domain and their current status.
    Frontend uses this to show the merchant what's pending/confirmed/failed.
    """
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
                "id":                     r['id'],
                "category":               r['issue_category'],
                "original_count":         r['issue_count'],
                "reported_by":            r['reported_by'],
                "reported_at":            r['created_at'].isoformat() if r.get('created_at') else None,
                "confirmed_at":           r['confirmed_at'].isoformat() if r.get('confirmed_at') else None,
                "confirmation_receipt_id": r.get('confirmation_receipt_id'),
                "notes":                  r.get('notes'),
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
    """Generate and stream the full 10-section Defense Package PDF."""
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



# ── Free Visitor Summary Email ────────────────────────────────────────────────

@app.route('/api/scan/summary-email', methods=['POST', 'OPTIONS'])
def summary_email():
    """
    Sends a free scan summary email to a visitor.
    Called automatically after every free scan on the scanner page.
    Also callable manually via the "Email me my summary" button.
    Body: { email: str, receipt: dict }
    """
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body    = request.get_json(silent=True)
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


# ── Gumroad Webhook ───────────────────────────────────────────────────────────

@app.route('/api/webhook/gumroad', methods=['POST'])
def gumroad_webhook():
    """
    Gumroad Ping endpoint.
    Verifies seller_id → validates sale → scans store →
    saves receipt → emails welcome + PDF → tags in Kit.
    """
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
        receipt['activated_by'] = email
        receipt['gumroad_sale_id'] = parsed['sale_id']
        receipt['plan'] = plan
        _save(receipt, email)

        if db_available:
            log_evidence(domain, receipt['receipt_id'],
                         'GUMROAD_ACTIVATION',
                         f"Sale {parsed['sale_id']} | plan={plan}")

        send_activation_receipt(email, receipt)

        # Cancel any free scanner nurture emails still pending
        if db_available:
            cancel_all_sequences(email)
            # Queue founder onboarding sequence
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
            "received":   True,
            "activated":  True,
            "domain":     result.domain,
            "receipt_id": receipt['receipt_id'],
            "registry_id":receipt['registry_id'],
            "score":      result.overall_score,
            "plan":       plan
        }), 200

    except Exception as e:
        print(f"[WEBHOOK] Error: {traceback.format_exc()}")
        return jsonify({"received": True, "activated": False,
                        "reason": "Internal error"}), 200


# ── Admin Dashboard Endpoint ──────────────────────────────────────────────────

ADMIN_KEY = os.environ.get('ADMIN_KEY', 'IDR-ADMIN-2026')


@app.route('/api/admin/members', methods=['GET'])
def admin_members():
    """
    Single aggregated call for the admin dashboard.
    Protected by ?key= query param.
    Returns: members, free_scanners, next_emails, stats.
    """
    if request.args.get('key', '') != ADMIN_KEY:
        return _error('Unauthorized', 401)

    if not db_available:
        return _error('Database required for admin endpoint.', 503)

    conn = get_conn()
    if not conn:
        return _error('Database connection failed.', 503)

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # Members: join registry → receipts (latest) to get email + receipt_id
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
                    r.activated_by   AS email,
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

            # Status counts
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE status = 'active')     AS active,
                    COUNT(*) FILTER (WHERE status = 'monitoring') AS monitoring,
                    COUNT(*) FILTER (WHERE status = 'expired')    AS expired,
                    COUNT(*)                                       AS total
                FROM registry
            """)
            counts = dict(cur.fetchone())

            # Free scanners: latest step per email in free_scanner sequence (not cancelled)
            cur.execute("""
                SELECT DISTINCT ON (email)
                    email,
                    domain,
                    step        AS sequence_step,
                    send_after  AS next_email_at,
                    created_at  AS scanned_at
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

            # Total pending emails
            cur.execute("""
                SELECT COUNT(*) AS queued
                FROM email_queue
                WHERE sent = FALSE AND cancelled = FALSE
            """)
            queued_count = cur.fetchone()['queued']

            # Next 20 emails due (queue panel)
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



# ── Auth helpers ──────────────────────────────────────────────────────────────

MAGIC_LINK_EXPIRY_MINUTES = 15
SESSION_EXPIRY_DAYS       = 30
PORTAL_BASE_URL           = os.environ.get('PORTAL_BASE_URL', 'https://idrshield.com')


def _hash_token(token):
    """SHA-256 hash a token before storing. Never store raw tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def _get_session_email(req):
    """
    Extract and validate session token from Authorization header.
    Returns email string if valid, None if missing/invalid/expired.
    Header: Authorization: Bearer <token>
    """
    auth = req.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    raw_token = auth[7:].strip()
    if not raw_token:
        return None
    return validate_session_token(_hash_token(raw_token))


def _auth_required(req):
    """
    Call at top of any protected endpoint.
    Returns (email, None) on success or (None, error_response) on failure.
    """
    email = _get_session_email(req)
    if not email:
        return None, _error('Unauthorized — invalid or expired session.', 401)
    return email, None


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.route('/api/auth/request', methods=['POST', 'OPTIONS'])
def auth_request():
    """
    Step 1 of magic link flow.
    Body: { email: str }
    Always returns 200 to avoid leaking whether email is registered.
    """
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body  = request.get_json(silent=True) or {}
        email = body.get('email', '').strip().lower()

        if not email or '@' not in email:
            return _error('Valid email required.', 400)
        if not db_available:
            return _error('Service unavailable.', 503)

        conn_check = get_conn()
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
    """
    Step 2 of magic link flow.
    Body: { token: str }
    Consumes magic link token, issues 30-day session token.
    """
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body  = request.get_json(silent=True) or {}
        token = body.get('token', '').strip()
        if not token:
            return _error('Token required.', 400)
        if not db_available:
            return _error('Service unavailable.', 503)

        ip         = request.remote_addr
        token_hash = _hash_token(token)
        email      = consume_magic_token(token_hash, ip)

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
    """Validate session and return member identity. Called by portal on every load."""
    email, err = _auth_required(request)
    if err:
        return err
    return jsonify({'authenticated': True, 'email': email}), 200


@app.route('/api/auth/logout', methods=['POST', 'OPTIONS'])
def auth_logout():
    """Revoke the current session token."""
    if request.method == 'OPTIONS':
        return '', 200
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        raw_token = auth[7:].strip()
        if raw_token:
            revoke_session_token(_hash_token(raw_token))
    return jsonify({'success': True}), 200


# ── Member portal endpoints ───────────────────────────────────────────────────

@app.route('/api/member/dashboard', methods=['GET'])
def member_dashboard():
    """All domains + scan history for the authenticated member."""
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
    """Compliance evidence log — ownership verified by session."""
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
    """Fix request history — ownership verified by session."""
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
    """Download the most recent Defense Package PDF for a domain."""
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
    """Return personalised badge and chip embed code for a domain."""
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


# ── Magic link email sender ───────────────────────────────────────────────────

def _send_magic_link_email(email, magic_url):
    from emailer import _send
    subject = 'Your IDR Shield login link'
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



# ── Entry point ───────────────────────────────────────────────────────────────
# NOTE: In production, Railway uses gunicorn (see Dockerfile).
# This block only runs when you execute `python app.py` locally.

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
# ── Support Escalation Endpoint ───────────────────────────────────────────────

@app.route('/api/support/escalate', methods=['POST', 'OPTIONS'])
def support_escalate():
    """
    Receives a legal escalation from Reid and emails support@idrshield.com.
    Body: { name, email, domain, phone, description, conversation_summary }
    """
    if request.method == 'OPTIONS':
        return '', 200
    try:
        body = request.get_json(silent=True) or {}
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



# ── Reid Chat Proxy ───────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')


@app.route('/api/support/chat', methods=['POST', 'OPTIONS'])
def support_chat():
    """
    Proxies Reid's conversation to Claude via the Anthropic API.
    Keeps the API key server-side, never exposed to the browser.
    Body: { system: str, messages: list, context: str }
    """
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

        # Validate messages are safe (role must be user or assistant)
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

