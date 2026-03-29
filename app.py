"""
IDR Scanner API - Production build for Railway
"""

import os
import sys
import json
import traceback
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS

from scanner.engine import scan_url
from receipt.generator import generate_receipt, verify_receipt, format_receipt_summary

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.config['JSON_SORT_KEYS'] = False

RECEIPT_STORE = {}


def _error(message, code):
    return jsonify({"error": message, "status": code}), code


@app.route('/', methods=['GET'])
def root():
    return jsonify({"service": "IDR Scanner API", "version": "1.0.0", "status": "operational"})


@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        "service": "IDR Scanner API",
        "version": "1.0.0",
        "protocol": "IDR-BRAND-2026-01",
        "status": "operational",
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
        result = scan_url(url)
        if result.error:
            return _error(f"Scan failed: {result.error}", 502)
        receipt = generate_receipt(result)
        RECEIPT_STORE[receipt['receipt_id']] = receipt
        return jsonify(receipt), 200
    except Exception as e:
        return _error(f"Internal error: {str(e)}", 500)


@app.route('/api/activate', methods=['POST', 'OPTIONS'])
def activate():
    # Handle preflight CORS
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
            return _error("Valid store URL required (must start with https://).", 400)

        result = scan_url(store_url)

        if result.error:
            return _error(f"Could not reach that URL: {result.error}", 502)

        receipt = generate_receipt(result)
        receipt['activated_by'] = email
        RECEIPT_STORE[receipt['receipt_id']] = receipt

        return jsonify({
            "success": True,
            "receipt_id": receipt['receipt_id'],
            "registry_id": receipt['registry_id'],
            "registry_url": receipt['registry_url'],
            "score": receipt['scan']['overall_score'],
            "status": receipt['scan']['overall_status'],
            "email": email
        }), 200

    except Exception as e:
        tb = traceback.format_exc()
        print(f"ACTIVATE ERROR: {tb}")
        return _error(f"Server error: {str(e)}", 500)


@app.route('/api/receipt/<receipt_id>', methods=['GET'])
def get_receipt(receipt_id):
    try:
        receipt = RECEIPT_STORE.get(receipt_id.upper())
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
            return _error("Request body must be a receipt JSON object.", 400)
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
def registry(domain):
    try:
        matches = [
            r for r in RECEIPT_STORE.values()
            if r.get('scan', {}).get('domain', '').replace('www.', '') == domain.replace('www.', '')
        ]
        if not matches:
            return _error(f"No records found for domain: {domain}", 404)
        latest = sorted(matches, key=lambda r: r.get('timestamp_utc', ''), reverse=True)[0]
        scan = latest.get('scan', {})
        status_val = scan.get('overall_status', 'fail')
        reg_status = "active" if (status_val == 'pass' and scan.get('critical_count', 1) == 0) else "monitoring"
        return jsonify({
            "domain": domain,
            "registry_id": latest.get('registry_id'),
            "last_scanned": latest.get('timestamp_utc'),
            "overall_score": scan.get('overall_score'),
            "overall_status": scan.get('overall_status'),
            "critical_issues": scan.get('critical_count'),
            "total_issues": scan.get('total_issues'),
            "registry_status": reg_status,
            "receipt_id": latest.get('receipt_id'),
            "registry_url": latest.get('registry_url'),
            "verified_by": latest.get('verified_by')
        }), 200
    except Exception as e:
        return _error(str(e), 500)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
