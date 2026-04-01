"""
IDR Scanner API - Phase 2B Launch
PDF gated behind payment. Free scan returns summary only.
Gumroad webhook triggers full activation + Kit tagging.
"""

import os
import traceback
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import io

from scanner.engine import scan_url
from receipt.generator import generate_receipt, verify_receipt
from receipt.pdf_generator import generate_pdf
from database import (
    init_db, save_receipt, get_receipt, get_receipts_by_domain,
    upsert_registry, get_registry, log_evidence, get_evidence_log,
    log_scan_alert, add_paid_customer, is_paid_customer
)
from emailer import send_activation_receipt, send_scan_alert
from webhook import parse_gumroad_payload, verify_gumroad_seller, is_valid_sale
from cron import start_cron_scheduler
from kit_integration import on_purchase, on_free_scan

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.config['JSON_SORT_KEYS'] = False

RECEIPT_STORE = {}
db_available = init_db()
start_cron_scheduler()


def _error(message, code):
    return jsonify({"error": message, "status": code}), code


def _save(receipt, email=None):
    RECEIPT_STORE[receipt['receipt_id']] = receipt
    if db_available:
        domain = receipt.get('scan', {}).get('domain', '')
        save_receipt(receipt, email)
        upsert_registry(domain, receipt, email)
        log_evidence(domain, receipt['receipt_id'], 'SCAN_COMPLETED',
                     f"Score: {receipt.get('scan',{}).get('overall_score')}/100")


def _get(receipt_id):
    if db_available:
        return get_receipt(receipt_id)
    return RECEIPT_STORE.get(receipt_id.upper())


def _summary_only(receipt: dict) -> dict:
    """
    Strip receipt to summary only — no categories, no remediation data.
    Used for free scan responses.
    """
    scan = receipt.get('scan', {})
    return {
        "receipt_id": receipt.get('receipt_id'),
        "registry_id": receipt.get('registry_id'),
        "timestamp_utc": receipt.get('timestamp_utc'),
        "scan": {
            "domain": scan.get('domain'),
            "url": scan.get('url'),
            "page_title": scan.get('page_title'),
            "overall_score": scan.get('overall_score'),
            "overall_status": scan.get('overall_status'),
            "critical_count": scan.get('critical_count'),
            "total_issues": scan.get('total_issues'),
            "scan_duration_ms": scan.get('scan_duration_ms'),
            # categories intentionally omitted
        },
        "hash": receipt.get('hash'),
        "registry_url": receipt.get('registry_url'),
        "idr_protocol": receipt.get('idr_protocol'),
        "verified_by": receipt.get('verified_by'),
        "gated": True,
        "upgrade_url": "https://idrshield.com/#activate",
        "message": (
            "Full Defense Package — remediation code, plaintiff simulation, "
            "comparable case law, and SHA-256 Scan Receipt — unlocks with "
            "IDR Shield Founding Membership."
        )
    }


# ── Core Routes ───────────────────────────────────────────────────────────────

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "service": "IDR Scanner API",
        "version": "3.0.0",
        "status": "operational",
        "db": "connected" if db_available else "in-memory"
    })


@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        "service": "IDR Scanner API",
        "version": "3.0.0",
        "protocol": "IDR-BRAND-2026-01",
        "status": "operational",
        "db": "connected" if db_available else "in-memory",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# ── Free Scan (summary only) ──────────────────────────────────────────────────

@app.route('/api/scan', methods=['POST'])
def scan():
    """
    Free public scan. Returns summary only — no categories, no PDF.
    Optionally captures email for Kit prospect nurture.
    """
    try:
        body = request.get_json(silent=True)
        if not body or 'url' not in body:
            return _error("Request body must include a 'url' field.", 400)

        url = body['url'].strip()
        email = body.get('email', '').strip()

        if not url.startswith(('http://', 'https://')):
            return _error("URL must begin with http:// or https://", 400)

        domain = url.replace('https://','').replace('http://','').split('/')[0]
        if db_available:
            log_scan_alert(domain, request.remote_addr, 'public_scan')

        result = scan_url(url)
        if result.error:
            return _error(f"Scan failed: {result.error}", 502)

        receipt = generate_receipt(result)
        _save(receipt)  # Save full receipt internally

        # Tag in Kit + send Email 1 if email provided
        if email and '@' in email:
            try:
                on_free_scan(email, domain)
                from emailer import send_free_scan_summary
                send_free_scan_summary(email, receipt)
            except Exception:
                pass  # Never block scan on email/Kit failure

        # Return summary only — gate the details
        return jsonify(_summary_only(receipt)), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(f"Internal error: {str(e)}", 500)


# ── Paid Activation ───────────────────────────────────────────────────────────

@app.route('/api/activate', methods=['POST', 'OPTIONS'])
def activate():
    """
    Direct paid activation. Used by the activation page.
    Checks payment record before running full scan.
    In production: only Gumroad webhook should trigger this flow.
    For testing: accepts email + store_url directly.
    """
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

        # Payment gate — check DB for verified payment
        # In dev/test mode, BYPASS_PAYMENT_GATE=true skips this
        bypass = os.environ.get('BYPASS_PAYMENT_GATE', 'false').lower() == 'true'
        if not bypass and db_available:
            domain_check = store_url.replace('https://','').replace('http://','').split('/')[0]
            if not is_paid_customer(email=email, domain=domain_check):
                return _error(
                    "Payment verification required. Purchase IDR Shield at "
                    "idrshield.com to activate your store.",
                    402
                )

        result = scan_url(store_url)
        if result.error:
            return _error(f"Could not reach that URL: {result.error}", 502)

        receipt = generate_receipt(result)
        receipt['activated_by'] = email
        _save(receipt, email)

        if db_available:
            log_evidence(result.domain, receipt['receipt_id'],
                         'ACTIVATION', f"Store activated by {email}")

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


# ── Gumroad Webhook ───────────────────────────────────────────────────────────

@app.route('/api/webhook/gumroad', methods=['POST'])
def gumroad_webhook():
    """
    Gumroad Ping endpoint.
    Verifies seller_id → validates sale → scans store →
    saves payment record → emails receipt → tags in Kit.
    """
    try:
        form_data = request.form.to_dict()

        # Log full payload for debugging
        print(f"[WEBHOOK] Raw payload keys: {list(form_data.keys())}")
        print(f"[WEBHOOK] email={form_data.get('email')} "
              f"sale_id={form_data.get('sale_id')} "
              f"seller_id={form_data.get('seller_id','')[:12]}... "
              f"test={form_data.get('test')}")
        # Log any custom field keys
        cf_keys = [k for k in form_data.keys() if 'custom' in k.lower() or 'store' in k.lower()]
        if cf_keys:
            print(f"[WEBHOOK] Custom field keys: {cf_keys}")
            for k in cf_keys:
                print(f"[WEBHOOK]   {k} = {form_data.get(k)}")

        parsed = parse_gumroad_payload(form_data)

        print(f"[WEBHOOK] Sale: {parsed['sale_id']} | "
              f"{parsed['email']} | plan={parsed['plan']} | "
              f"test={parsed['test']} | refunded={parsed['refunded']}")

        # Verify seller
        if not verify_gumroad_seller(parsed.get('seller_id', '')):
            print(f"[WEBHOOK] seller_id failed from {request.remote_addr}")
            return _error("Unauthorized", 401)

        # Log raw ping
        if db_available and parsed.get('email'):
            domain_raw = parsed.get('store_url', 'unknown')
            domain_log = domain_raw.replace('https://','').replace('http://','').split('/')[0]
            log_evidence(domain_log, parsed.get('sale_id', 'ping'),
                         'GUMROAD_PING',
                         f"Sale {parsed['sale_id']} | {parsed['email']} | "
                         f"refunded={parsed['refunded']}")

        # Validate
        valid, reason = is_valid_sale(parsed)
        if not valid:
            print(f"[WEBHOOK] Invalid: {reason}")
            return jsonify({"received": True, "activated": False,
                            "reason": reason}), 200

        email = parsed['email']
        store_url = parsed['store_url']
        plan = parsed['plan']
        monthly_rate = 29  # Founding rate

        domain = store_url.replace('https://','').replace('http://','').split('/')[0].replace('www.','')

        # Scan store
        result = scan_url(store_url)
        if result.error:
            print(f"[WEBHOOK] Scan failed for {store_url}: {result.error}")
            return jsonify({"received": True, "activated": False,
                            "reason": f"Scan failed: {result.error}"}), 200

        # Generate and save receipt
        receipt = generate_receipt(result)
        receipt['activated_by'] = email
        receipt['gumroad_sale_id'] = parsed['sale_id']
        receipt['plan'] = plan
        _save(receipt, email)

        # Record payment
        if db_available:
            add_paid_customer(
                email=email,
                domain=domain,
                sale_id=parsed['sale_id'],
                plan=plan,
                monthly_rate=monthly_rate
            )
            log_evidence(domain, receipt['receipt_id'],
                         'GUMROAD_ACTIVATION',
                         f"Sale {parsed['sale_id']} | plan={plan} | "
                         f"monthly=${monthly_rate}")

        # Send receipt email with PDF
        send_activation_receipt(email, receipt)

        # Tag in Kit
        try:
            on_purchase(
                email=email,
                domain=domain,
                plan=plan,
                full_name=parsed.get('full_name', '')
            )
        except Exception as ke:
            print(f"[WEBHOOK] Kit tagging failed (non-fatal): {ke}")

        print(f"[WEBHOOK] ✓ Activated: {domain} | "
              f"{result.overall_score}/100 | {email}")

        return jsonify({
            "received": True,
            "activated": True,
            "domain": result.domain,
            "receipt_id": receipt['receipt_id'],
            "registry_id": receipt['registry_id'],
            "score": result.overall_score,
            "plan": plan
        }), 200

    except Exception as e:
        print(f"[WEBHOOK] Error: {traceback.format_exc()}")
        return jsonify({"received": True, "activated": False,
                        "reason": "Internal error"}), 200


# ── Receipt Routes ────────────────────────────────────────────────────────────

@app.route('/api/receipt/<receipt_id>', methods=['GET'])
def get_receipt_route(receipt_id):
    try:
        receipt = _get(receipt_id)
        if not receipt:
            return _error(f"Receipt {receipt_id} not found.", 404)
        # Check if this is a paid receipt
        activated_by = receipt.get('activated_by')
        if not activated_by:
            return jsonify(_summary_only(receipt)), 200
        return jsonify(receipt), 200
    except Exception as e:
        return _error(str(e), 500)


@app.route('/api/receipt/<receipt_id>/pdf', methods=['GET'])
def download_pdf(receipt_id):
    """
    PDF download — gated behind payment verification.
    Checks activated_by on receipt AND paid_customers table.
    """
    try:
        receipt = _get(receipt_id)
        if not receipt:
            return _error(f"Receipt {receipt_id} not found.", 404)

        # Gate 1: Receipt must have been activated (not a free scan)
        activated_by = receipt.get('activated_by')
        if not activated_by:
            return _error(
                "Defense Package PDF requires IDR Shield activation. "
                "Purchase at idrshield.com to unlock your full report.",
                402
            )

        # Gate 2: Verify active payment record in DB
        bypass = os.environ.get('BYPASS_PAYMENT_GATE', 'false').lower() == 'true'
        if not bypass and db_available:
            domain = receipt.get('scan', {}).get('domain', '')
            if not is_paid_customer(email=activated_by, domain=domain):
                return _error(
                    "Payment verification failed. "
                    "Please contact hello@idrshield.com if you believe this "
                    "is an error.",
                    402
                )

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


@app.route('/api/verify', methods=['POST'])
def verify():
    try:
        receipt = request.get_json(silent=True)
        if not receipt:
            return _error("Request body required.", 400)
        from receipt.generator import verify_receipt
        result = verify_receipt(receipt)
        return jsonify({
            **result,
            "receipt_id": receipt.get("receipt_id"),
            "domain": receipt.get("scan", {}).get("domain"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200 if result['valid'] else 409
    except Exception as e:
        return _error(str(e), 500)


# ── Registry & Badge ──────────────────────────────────────────────────────────

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
                "last_scanned": reg['last_scanned'].isoformat()
                               if reg['last_scanned'] else None,
                "latest_score": reg['latest_score'],
                "critical_count": reg['critical_count'],
                "scan_count": reg['scan_count'],
                "registry_url": f"https://idrshield.com/verify/{reg['domain']}",
                "badge_active": reg['badge_active']
            }), 200

        matches = [
            r for r in RECEIPT_STORE.values()
            if r.get('scan', {}).get('domain', '').replace('www.', '')
            == domain.replace('www.', '')
        ]
        if not matches:
            return _error(f"No records found for domain: {domain}", 404)
        latest = sorted(matches,
                        key=lambda r: r.get('timestamp_utc', ''),
                        reverse=True)[0]
        scan = latest.get('scan', {})
        return jsonify({
            "domain": domain,
            "registry_id": latest.get('registry_id'),
            "last_scanned": latest.get('timestamp_utc'),
            "overall_score": scan.get('overall_score'),
            "registry_url": latest.get('registry_url'),
        }), 200

    except Exception as e:
        print(traceback.format_exc())
        return _error(str(e), 500)


@app.route('/api/badge/<domain>', methods=['GET'])
def badge_status(domain):
    try:
        if db_available:
            reg = get_registry(domain)
            if not reg:
                return jsonify({
                    "domain": domain, "status": "expired",
                    "verified": False
                }), 200
            return jsonify({
                "domain": reg['domain'],
                "status": reg['status'],
                "last_scanned": reg['last_scanned'].isoformat()
                               if reg['last_scanned'] else None,
                "score": reg['latest_score'],
                "verified": True,
                "registry_url": f"https://idrshield.com/verify/{reg['domain']}"
            }), 200
        return jsonify({"domain": domain, "status": "monitoring",
                        "verified": False}), 200
    except Exception as e:
        return _error(str(e), 500)


@app.route('/api/evidence/<domain>', methods=['GET'])
def evidence_log_route(domain):
    try:
        if not db_available:
            return _error("Evidence log requires database.", 503)
        log = get_evidence_log(domain)
        return jsonify({"domain": domain, "entries": log,
                        "count": len(log)}), 200
    except Exception as e:
        return _error(str(e), 500)


# ── Manual Cron Trigger ───────────────────────────────────────────────────────

@app.route('/api/cron/run', methods=['POST'])
def trigger_cron():
    auth = request.headers.get('X-Cron-Secret', '')
    if auth != os.environ.get('CRON_SECRET', ''):
        return _error("Unauthorized", 401)
    try:
        from cron import run_cron_cycle
        run_cron_cycle()
        return jsonify({"triggered": True}), 200
    except Exception as e:
        return _error(str(e), 500)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
