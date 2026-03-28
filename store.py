"""
IDR Database Layer
PostgreSQL-backed immutable receipt store with full audit log.
Replaces the in-memory RECEIPT_STORE in app.py.
"""

import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from typing import Optional


# ─────────────────────────────────────────────
# Connection
# ─────────────────────────────────────────────

def get_conn():
    """Get a database connection from environment variables."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', 5432)),
        dbname=os.environ.get('DB_NAME', 'idr_scanner'),
        user=os.environ.get('DB_USER', 'idr'),
        password=os.environ.get('DB_PASSWORD', ''),
        cursor_factory=psycopg2.extras.RealDictCursor
    )


# ─────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────

SCHEMA_SQL = """
-- Immutable scan receipts log
-- Rows are NEVER updated or deleted — append only
CREATE TABLE IF NOT EXISTS scan_receipts (
    id              BIGSERIAL PRIMARY KEY,
    receipt_id      UUID        NOT NULL UNIQUE,
    registry_id     TEXT        NOT NULL,
    domain          TEXT        NOT NULL,
    url             TEXT        NOT NULL,
    page_title      TEXT,
    timestamp_utc   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    operator        TEXT        NOT NULL DEFAULT 'IDR_SCANNER_v1',

    -- Scan summary (denormalized for fast registry lookups)
    overall_score   SMALLINT    NOT NULL,
    overall_status  TEXT        NOT NULL CHECK (overall_status IN ('pass','warning','fail')),
    total_issues    SMALLINT    NOT NULL DEFAULT 0,
    critical_count  SMALLINT    NOT NULL DEFAULT 0,
    scan_duration_ms INT,

    -- Category scores (denormalized)
    score_alt_text          SMALLINT,
    score_form_labels       SMALLINT,
    score_keyboard_nav      SMALLINT,
    score_heading_structure SMALLINT,
    score_aria_links        SMALLINT,

    -- Full receipt JSON (canonical, immutable)
    receipt_json    JSONB       NOT NULL,

    -- SHA-256 hash for tamper detection
    hash_value      CHAR(64)    NOT NULL UNIQUE,

    -- Registry status computed at insert time
    registry_status TEXT        NOT NULL DEFAULT 'monitoring'
                    CHECK (registry_status IN ('active','monitoring','expired')),

    -- Prevent any updates to this table
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast domain lookups (registry page)
CREATE INDEX IF NOT EXISTS idx_receipts_domain
    ON scan_receipts (domain, timestamp_utc DESC);

-- Index for receipt ID lookups
CREATE INDEX IF NOT EXISTS idx_receipts_receipt_id
    ON scan_receipts (receipt_id);

-- Index for registry status filtering
CREATE INDEX IF NOT EXISTS idx_receipts_status
    ON scan_receipts (registry_status, domain);

-- Prevent UPDATE and DELETE at the database level
-- (Run as superuser once after creating the table)
-- REVOKE UPDATE, DELETE ON scan_receipts FROM idr;

-- Enrolled stores registry
CREATE TABLE IF NOT EXISTS enrolled_stores (
    id              BIGSERIAL PRIMARY KEY,
    domain          TEXT        NOT NULL UNIQUE,
    store_name      TEXT,
    registry_id     TEXT        NOT NULL UNIQUE,
    enrolled_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    plan            TEXT        NOT NULL DEFAULT 'standard',
    theme_variant   TEXT        NOT NULL DEFAULT 'dark'
                    CHECK (theme_variant IN ('dark','outline')),
    contact_email   TEXT,
    last_scan_at    TIMESTAMPTZ,
    registry_status TEXT        NOT NULL DEFAULT 'monitoring'
                    CHECK (registry_status IN ('active','monitoring','expired')),
    active          BOOLEAN     NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_stores_domain ON enrolled_stores (domain);
CREATE INDEX IF NOT EXISTS idx_stores_registry_id ON enrolled_stores (registry_id);

-- Scan queue for scheduled rescans
CREATE TABLE IF NOT EXISTS scan_queue (
    id              BIGSERIAL PRIMARY KEY,
    domain          TEXT        NOT NULL,
    url             TEXT        NOT NULL,
    scheduled_for   TIMESTAMPTZ NOT NULL,
    priority        SMALLINT    NOT NULL DEFAULT 5,
    status          TEXT        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','running','done','failed')),
    attempts        SMALLINT    NOT NULL DEFAULT 0,
    last_error      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_queue_scheduled
    ON scan_queue (scheduled_for, status, priority DESC)
    WHERE status = 'pending';
"""


def init_db():
    """Create all tables if they don't exist."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.commit()
    print("IDR Database initialized.")


# ─────────────────────────────────────────────
# Receipt Operations
# ─────────────────────────────────────────────

def save_receipt(receipt: dict) -> bool:
    """
    Persist a receipt to the immutable log.
    Returns True on success, False if already exists.
    """
    scan = receipt.get('scan', {})
    cats = {c['slug']: c['score'] for c in scan.get('categories', [])}

    sql = """
    INSERT INTO scan_receipts (
        receipt_id, registry_id, domain, url, page_title,
        timestamp_utc, operator,
        overall_score, overall_status, total_issues, critical_count, scan_duration_ms,
        score_alt_text, score_form_labels, score_keyboard_nav,
        score_heading_structure, score_aria_links,
        receipt_json, hash_value, registry_status
    ) VALUES (
        %(receipt_id)s, %(registry_id)s, %(domain)s, %(url)s, %(page_title)s,
        %(timestamp_utc)s, %(operator)s,
        %(overall_score)s, %(overall_status)s, %(total_issues)s, %(critical_count)s,
        %(scan_duration_ms)s,
        %(score_alt_text)s, %(score_form_labels)s, %(score_keyboard_nav)s,
        %(score_heading_structure)s, %(score_aria_links)s,
        %(receipt_json)s, %(hash_value)s, %(registry_status)s
    )
    ON CONFLICT (receipt_id) DO NOTHING
    RETURNING id;
    """

    params = {
        'receipt_id': receipt['receipt_id'],
        'registry_id': receipt['registry_id'],
        'domain': scan.get('domain', ''),
        'url': scan.get('url', ''),
        'page_title': scan.get('page_title', ''),
        'timestamp_utc': receipt['timestamp_utc'],
        'operator': receipt.get('operator', 'IDR_SCANNER_v1'),
        'overall_score': scan.get('overall_score', 0),
        'overall_status': scan.get('overall_status', 'fail'),
        'total_issues': scan.get('total_issues', 0),
        'critical_count': scan.get('critical_count', 0),
        'scan_duration_ms': scan.get('scan_duration_ms'),
        'score_alt_text': cats.get('alt_text'),
        'score_form_labels': cats.get('form_labels'),
        'score_keyboard_nav': cats.get('keyboard_nav'),
        'score_heading_structure': cats.get('heading_structure'),
        'score_aria_links': cats.get('aria_links_contrast'),
        'receipt_json': json.dumps(receipt),
        'hash_value': receipt['hash']['value'],
        'registry_status': _compute_registry_status(scan)
    }

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            conn.commit()
        return row is not None
    except Exception as e:
        print(f"[DB] save_receipt error: {e}")
        return False


def get_receipt(receipt_id: str) -> Optional[dict]:
    """Fetch a receipt by UUID."""
    sql = "SELECT receipt_json FROM scan_receipts WHERE receipt_id = %s LIMIT 1;"
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (receipt_id,))
                row = cur.fetchone()
        if row:
            return json.loads(row['receipt_json'])
        return None
    except Exception as e:
        print(f"[DB] get_receipt error: {e}")
        return None


def get_latest_receipt_for_domain(domain: str) -> Optional[dict]:
    """Get the most recent receipt for a domain."""
    sql = """
    SELECT receipt_json
    FROM scan_receipts
    WHERE domain = %s OR domain = %s
    ORDER BY timestamp_utc DESC
    LIMIT 1;
    """
    clean = domain.replace('www.', '')
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (domain, clean))
                row = cur.fetchone()
        if row:
            return json.loads(row['receipt_json'])
        return None
    except Exception as e:
        print(f"[DB] get_latest error: {e}")
        return None


def get_domain_history(domain: str, limit: int = 10) -> list:
    """Get scan history for a domain (summaries, not full receipts)."""
    sql = """
    SELECT
        receipt_id, registry_id, timestamp_utc,
        overall_score, overall_status, total_issues, critical_count,
        registry_status, scan_duration_ms
    FROM scan_receipts
    WHERE domain = %s OR domain = %s
    ORDER BY timestamp_utc DESC
    LIMIT %s;
    """
    clean = domain.replace('www.', '')
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (domain, clean, limit))
                rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] get_history error: {e}")
        return []


# ─────────────────────────────────────────────
# Registry Operations
# ─────────────────────────────────────────────

def get_registry_entry(domain: str) -> Optional[dict]:
    """
    Get the live registry record for a domain.
    Combines enrolled store data with latest scan.
    """
    sql = """
    SELECT
        s.domain, s.store_name, s.registry_id, s.enrolled_at,
        s.plan, s.theme_variant, s.registry_status,
        r.overall_score, r.overall_status, r.total_issues,
        r.critical_count, r.timestamp_utc as last_scanned,
        r.receipt_id, r.hash_value
    FROM enrolled_stores s
    LEFT JOIN LATERAL (
        SELECT * FROM scan_receipts
        WHERE domain = s.domain
        ORDER BY timestamp_utc DESC
        LIMIT 1
    ) r ON TRUE
    WHERE s.domain = %s OR s.domain = %s
    LIMIT 1;
    """
    clean = domain.replace('www.', '')
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (domain, clean))
                row = cur.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"[DB] get_registry error: {e}")
        return None


def update_store_registry_status(domain: str, status: str):
    """Update the registry status for an enrolled store."""
    sql = """
    UPDATE enrolled_stores
    SET registry_status = %s, last_scan_at = NOW()
    WHERE domain = %s OR domain = %s;
    """
    clean = domain.replace('www.', '')
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (status, domain, clean))
            conn.commit()
    except Exception as e:
        print(f"[DB] update_status error: {e}")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _compute_registry_status(scan: dict) -> str:
    if not scan:
        return 'expired'
    if scan.get('overall_status') == 'pass' and scan.get('critical_count', 1) == 0:
        return 'active'
    return 'monitoring'
