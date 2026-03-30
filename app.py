"""
IDR Scanner API - Phase 2A"""
IDR Database Layer - Phase 2A
PostgreSQL persistent store. Falls back to in-memory if unavailable.
"""

import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

_RAW_URL = os.environ.get('DATABASE_URL', '')

def _build_url():
    """Normalize the database URL for psycopg2."""
    url = _RAW_URL
    if not url:
        return None
    # psycopg2 requires postgresql:// not postgres://
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    return url

DATABASE_URL = _build_url()


def get_conn():
    if not DATABASE_URL:
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        conn.autocommit = True
        return conn
    except Exception:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            conn.autocommit = True
            return conn
        except Exception as e:
            print(f"DB connection error: {e}")
            return None


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id      TEXT PRIMARY KEY,
    registry_id     TEXT NOT NULL,
    domain          TEXT NOT NULL,
    activated_by    TEXT,
    timestamp_utc   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    overall_score   INTEGER,
    overall_status  TEXT,
    critical_count  INTEGER DEFAULT 0,
    total_issues    INTEGER DEFAULT 0,
    hash_value      TEXT,
    receipt_json    JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_receipts_domain ON receipts(domain);
CREATE INDEX IF NOT EXISTS idx_receipts_registry_id ON receipts(registry_id);

CREATE TABLE IF NOT EXISTS registry (
    domain          TEXT PRIMARY KEY,
    registry_id     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'monitoring',
    last_scanned    TIMESTAMPTZ,
    latest_score    INTEGER,
    critical_count  INTEGER DEFAULT 0,
    scan_count      INTEGER DEFAULT 0,
    activated_by    TEXT,
    badge_active    BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence_log (
    id              SERIAL PRIMARY KEY,
    domain          TEXT NOT NULL,
    receipt_id      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    event_detail    TEXT,
    timestamp_utc   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evidence_domain ON evidence_log(domain);

CREATE TABLE IF NOT EXISTS scan_alerts (
    id              SERIAL PRIMARY KEY,
    domain          TEXT NOT NULL,
    scanner_ip      TEXT,
    scan_type       TEXT DEFAULT 'external',
    notified        BOOLEAN DEFAULT FALSE,
    timestamp_utc   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

def init_db():
    print(f"DB URL present: {bool(DATABASE_URL)}")
    conn = get_conn()
    if not conn:
        print("No DB connection — running in-memory mode")
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        print("Database schema initialized successfully")
        conn.close()
        return True
    except Exception as e:
        print(f"DB init error: {e}")
        return False


def save_receipt(receipt: dict, email: str = None) -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        scan = receipt.get('scan', {})
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO receipts 
                    (receipt_id, registry_id, domain, activated_by,
                     timestamp_utc, overall_score, overall_status,
                     critical_count, total_issues, hash_value, receipt_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (receipt_id) DO NOTHING
            """, (
                receipt['receipt_id'],
                receipt['registry_id'],
                scan.get('domain', ''),
                email,
                receipt.get('timestamp_utc', datetime.now(timezone.utc).isoformat()),
                scan.get('overall_score'),
                scan.get('overall_status'),
                scan.get('critical_count', 0),
                scan.get('total_issues', 0),
                receipt.get('hash', {}).get('value'),
                json.dumps(receipt)
            ))
        conn.close()
        return True
    except Exception as e:
        print(f"save_receipt error: {e}")
        return False


def get_receipt(receipt_id: str) -> dict:
    conn = get_conn()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT receipt_json FROM receipts WHERE receipt_id = %s", (receipt_id.upper(),))
            row = cur.fetchone()
            conn.close()
            return row['receipt_json'] if row else None
    except Exception as e:
        print(f"get_receipt error: {e}")
        return None


def get_receipts_by_domain(domain: str) -> list:
    conn = get_conn()
    if not conn:
        return []
    try:
        clean = domain.replace('www.', '')
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT receipt_json FROM receipts 
                WHERE REPLACE(domain,'www.','') = %s
                ORDER BY timestamp_utc DESC
            """, (clean,))
            rows = [row['receipt_json'] for row in cur.fetchall()]
            conn.close()
            return rows
    except Exception as e:
        print(f"get_receipts_by_domain error: {e}")
        return []


def upsert_registry(domain: str, receipt: dict, email: str = None) -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        scan = receipt.get('scan', {})
        score = scan.get('overall_score', 0)
        critical = scan.get('critical_count', 0)
        status = 'active' if (score >= 80 and critical == 0) else 'monitoring'
        clean = domain.replace('www.', '')
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO registry
                    (domain, registry_id, status, last_scanned,
                     latest_score, critical_count, scan_count, activated_by, updated_at)
                VALUES (%s,%s,%s,NOW(),%s,%s,1,%s,NOW())
                ON CONFLICT (domain) DO UPDATE SET
                    status=EXCLUDED.status,
                    last_scanned=NOW(),
                    latest_score=EXCLUDED.latest_score,
                    critical_count=EXCLUDED.critical_count,
                    scan_count=registry.scan_count+1,
                    updated_at=NOW()
            """, (clean, receipt['registry_id'], status, score, critical, email))
        conn.close()
        return True
    except Exception as e:
        print(f"upsert_registry error: {e}")
        return False


def get_registry(domain: str) -> dict:
    conn = get_conn()
    if not conn:
        return None
    try:
        clean = domain.replace('www.', '')
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM registry WHERE domain = %s", (clean,))
            row = cur.fetchone()
            conn.close()
            return dict(row) if row else None
    except Exception as e:
        print(f"get_registry error: {e}")
        return None


def log_evidence(domain: str, receipt_id: str, event_type: str, detail: str = None) -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        clean = domain.replace('www.', '')
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO evidence_log (domain, receipt_id, event_type, event_detail)
                VALUES (%s,%s,%s,%s)
            """, (clean, receipt_id, event_type, detail))
        conn.close()
        return True
    except Exception as e:
        print(f"log_evidence error: {e}")
        return False


def get_evidence_log(domain: str) -> list:
    conn = get_conn()
    if not conn:
        return []
    try:
        clean = domain.replace('www.', '')
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, domain, receipt_id, event_type, event_detail,
                       timestamp_utc::text as timestamp_utc
                FROM evidence_log WHERE domain=%s ORDER BY timestamp_utc ASC
            """, (clean,))
            rows = [dict(row) for row in cur.fetchall()]
            conn.close()
            return rows
    except Exception as e:
        print(f"get_evidence_log error: {e}")
        return []


def log_scan_alert(domain: str, scanner_ip: str = None, scan_type: str = 'external') -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        clean = domain.replace('www.', '')
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO scan_alerts (domain, scanner_ip, scan_type)
                VALUES (%s,%s,%s)
            """, (clean, scanner_ip, scan_type))
        conn.close()
        return True
    except Exception as e:
        print(f"log_scan_alert error: {e}")
        return False

Production build with PostgreSQL, email delivery, and evidence logging.
"""

import os
import traceback
from datetime import datetime, timezone
from flask import Flask, request, jsonify
from flask_cors import CORS

from scanner.engine import scan_url
from receipt.generator import generate_receipt, verify_receipt, format_receipt_summary
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
