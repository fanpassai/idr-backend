"""
IDR Database Layer - Phase 2B
PostgreSQL persistent store. Falls back to in-memory if unavailable.
"""

import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

_RAW_URL = os.environ.get('DATABASE_URL', '')

def _build_url():
    url = _RAW_URL
    if not url:
        return None
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

CREATE INDEX IF NOT EXISTS idx_receipts_domain
    ON receipts(domain);
CREATE INDEX IF NOT EXISTS idx_receipts_registry_id
    ON receipts(registry_id);
CREATE INDEX IF NOT EXISTS idx_receipts_activated_by
    ON receipts(activated_by);

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

CREATE INDEX IF NOT EXISTS idx_evidence_domain
    ON evidence_log(domain);

CREATE TABLE IF NOT EXISTS scan_alerts (
    id              SERIAL PRIMARY KEY,
    domain          TEXT NOT NULL,
    scanner_ip      TEXT,
    scan_type       TEXT DEFAULT 'external',
    notified        BOOLEAN DEFAULT FALSE,
    timestamp_utc   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paid_customers (
    id              SERIAL PRIMARY KEY,
    email           TEXT NOT NULL,
    domain          TEXT NOT NULL,
    sale_id         TEXT UNIQUE,
    plan            TEXT NOT NULL DEFAULT 'founding',
    monthly_rate    INTEGER NOT NULL DEFAULT 29,
    activated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(email, domain)
);

CREATE INDEX IF NOT EXISTS idx_paid_email
    ON paid_customers(email);
CREATE INDEX IF NOT EXISTS idx_paid_domain
    ON paid_customers(domain);
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


# ── Payment Verification ──────────────────────────────────────────────────────

def add_paid_customer(email: str, domain: str, sale_id: str,
                      plan: str = 'founding', monthly_rate: int = 29) -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        clean = domain.replace('www.', '')
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO paid_customers
                    (email, domain, sale_id, plan, monthly_rate)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (email, domain) DO UPDATE SET
                    sale_id=EXCLUDED.sale_id,
                    plan=EXCLUDED.plan,
                    monthly_rate=EXCLUDED.monthly_rate,
                    active=TRUE
            """, (email.lower().strip(), clean, sale_id, plan, monthly_rate))
        conn.close()
        return True
    except Exception as e:
        print(f"add_paid_customer error: {e}")
        return False


def is_paid_customer(email: str = None, domain: str = None) -> bool:
    """
    Check if email OR domain has a verified payment record.
    Used to gate PDF downloads and full scan results.
    """
    conn = get_conn()
    if not conn:
        return False
    try:
        clean = domain.replace('www.', '') if domain else None
        with conn.cursor() as cur:
            if email and domain:
                cur.execute("""
                    SELECT 1 FROM paid_customers
                    WHERE active = TRUE
                      AND (email = %s OR domain = %s)
                    LIMIT 1
                """, (email.lower().strip(), clean))
            elif email:
                cur.execute("""
                    SELECT 1 FROM paid_customers
                    WHERE active = TRUE AND email = %s LIMIT 1
                """, (email.lower().strip(),))
            elif domain:
                cur.execute("""
                    SELECT 1 FROM paid_customers
                    WHERE active = TRUE AND domain = %s LIMIT 1
                """, (clean,))
            else:
                return False
            result = cur.fetchone()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"is_paid_customer error: {e}")
        return False


def get_customer_plan(email: str = None, domain: str = None) -> dict:
    """Get plan details for a paid customer."""
    conn = get_conn()
    if not conn:
        return {}
    try:
        clean = domain.replace('www.', '') if domain else None
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if email:
                cur.execute("""
                    SELECT * FROM paid_customers
                    WHERE active = TRUE AND email = %s LIMIT 1
                """, (email.lower().strip(),))
            else:
                cur.execute("""
                    SELECT * FROM paid_customers
                    WHERE active = TRUE AND domain = %s LIMIT 1
                """, (clean,))
            row = cur.fetchone()
        conn.close()
        return dict(row) if row else {}
    except Exception as e:
        print(f"get_customer_plan error: {e}")
        return {}


# ── Receipt Operations ────────────────────────────────────────────────────────

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
                receipt.get('timestamp_utc',
                            datetime.now(timezone.utc).isoformat()),
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
        with conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT receipt_json FROM receipts WHERE receipt_id = %s",
                (receipt_id.upper(),))
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
        with conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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


def upsert_registry(domain: str, receipt: dict,
                    email: str = None) -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        scan = receipt.get('scan', {})
        score = scan.get('overall_score', 0)
        critical = scan.get('critical_count', 0)
        status = ('active' if (score >= 80 and critical == 0)
                  else 'monitoring')
        clean = domain.replace('www.', '')
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO registry
                    (domain, registry_id, status, last_scanned,
                     latest_score, critical_count, scan_count,
                     activated_by, updated_at)
                VALUES (%s,%s,%s,NOW(),%s,%s,1,%s,NOW())
                ON CONFLICT (domain) DO UPDATE SET
                    status=EXCLUDED.status,
                    last_scanned=NOW(),
                    latest_score=EXCLUDED.latest_score,
                    critical_count=EXCLUDED.critical_count,
                    scan_count=registry.scan_count+1,
                    updated_at=NOW()
            """, (clean, receipt['registry_id'], status,
                  score, critical, email))
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
        with conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM registry WHERE domain = %s", (clean,))
            row = cur.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        print(f"get_registry error: {e}")
        return None


def log_evidence(domain: str, receipt_id: str,
                 event_type: str, detail: str = None) -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        clean = domain.replace('www.', '')
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO evidence_log
                    (domain, receipt_id, event_type, event_detail)
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
        with conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, domain, receipt_id, event_type,
                       event_detail,
                       timestamp_utc::text as timestamp_utc
                FROM evidence_log
                WHERE domain=%s
                ORDER BY timestamp_utc ASC
            """, (clean,))
            rows = [dict(row) for row in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"get_evidence_log error: {e}")
        return []


def log_scan_alert(domain: str, scanner_ip: str = None,
                   scan_type: str = 'external') -> bool:
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
