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
from database import (
    init_db, save_receipt, get_receipt, get_receipts_by_domain,
    upsert_registry, get_registry, log_evidence, get_evidence_log,
    log_scan_alert
)
from emailer import send_activation_receipt, send_scan_alert

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.config['JSON_SORT_KEYS'] = False

# In-memory fallback when no DB
RECEIPT_STORE = {}

# Initialize database on startup
db_available = init_db()


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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)


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
