"""
IDR Database Layer
PostgreSQL persistent store for receipts, registry, and evidence log.
Falls back to in-memory if DATABASE_URL not set (local dev).
"""

import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

_RAW_URL = os.environ.get('DATABASE_URL', '')

def _build_url():
    """Railway provides postgres:// — psycopg2 requires postgresql://"""
    url = _RAW_URL
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    return url

DATABASE_URL = _build_url()

# ── Connection ────────────────────────────────────────────────────────────────

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


# ── Schema Setup ─────────────────────────────────────────────────────────────

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

CREATE TABLE IF NOT EXISTS fix_requests (
    id                      SERIAL PRIMARY KEY,
    domain                  TEXT NOT NULL,
    receipt_id              TEXT NOT NULL,
    reported_by             TEXT NOT NULL,
    issue_category          TEXT NOT NULL,
    issue_count             INTEGER DEFAULT 0,
    status                  TEXT NOT NULL DEFAULT 'pending',
    confirmation_receipt_id TEXT,
    confirmed_at            TIMESTAMPTZ,
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fix_requests_domain
    ON fix_requests(domain);
CREATE INDEX IF NOT EXISTS idx_fix_requests_status
    ON fix_requests(status);
"""

def init_db():
    conn = get_conn()
    if not conn:
        print("No DATABASE_URL — running in-memory mode")
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        print("Database schema initialized")
        return True
    except Exception as e:
        print(f"DB init error: {e}")
        return False
    finally:
        conn.close()


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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        return True
    except Exception as e:
        print(f"save_receipt error: {e}")
        return False
    finally:
        conn.close()


def get_receipt(receipt_id: str) -> dict:
    conn = get_conn()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT receipt_json FROM receipts WHERE receipt_id = %s",
                (receipt_id.upper(),)
            )
            row = cur.fetchone()
            return row['receipt_json'] if row else None
    except Exception as e:
        print(f"get_receipt error: {e}")
        return None
    finally:
        conn.close()


def get_receipts_by_domain(domain: str) -> list:
    conn = get_conn()
    if not conn:
        return []
    try:
        clean = domain.replace('www.', '')
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT receipt_json FROM receipts 
                WHERE REPLACE(domain, 'www.', '') = %s
                ORDER BY timestamp_utc DESC
            """, (clean,))
            return [row['receipt_json'] for row in cur.fetchall()]
    except Exception as e:
        print(f"get_receipts_by_domain error: {e}")
        return []
    finally:
        conn.close()


# ── Registry Operations ───────────────────────────────────────────────────────

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
                     latest_score, critical_count, scan_count,
                     activated_by, updated_at)
                VALUES (%s, %s, %s, NOW(), %s, %s, 1, %s, NOW())
                ON CONFLICT (domain) DO UPDATE SET
                    status       = EXCLUDED.status,
                    last_scanned = NOW(),
                    latest_score = EXCLUDED.latest_score,
                    critical_count = EXCLUDED.critical_count,
                    scan_count   = registry.scan_count + 1,
                    updated_at   = NOW()
            """, (
                clean,
                receipt['registry_id'],
                status,
                score,
                critical,
                email
            ))
        return True
    except Exception as e:
        print(f"upsert_registry error: {e}")
        return False
    finally:
        conn.close()


def get_registry(domain: str) -> dict:
    conn = get_conn()
    if not conn:
        return None
    try:
        clean = domain.replace('www.', '')
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM registry WHERE domain = %s",
                (clean,)
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"get_registry error: {e}")
        return None
    finally:
        conn.close()


# ── Evidence Log ─────────────────────────────────────────────────────────────

def log_evidence(domain: str, receipt_id: str, event_type: str, detail: str = None) -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        clean = domain.replace('www.', '')
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO evidence_log 
                    (domain, receipt_id, event_type, event_detail)
                VALUES (%s, %s, %s, %s)
            """, (clean, receipt_id, event_type, detail))
        return True
    except Exception as e:
        print(f"log_evidence error: {e}")
        return False
    finally:
        conn.close()


def get_evidence_log(domain: str) -> list:
    conn = get_conn()
    if not conn:
        return []
    try:
        clean = domain.replace('www.', '')
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM evidence_log 
                WHERE domain = %s 
                ORDER BY timestamp_utc ASC
            """, (clean,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"get_evidence_log error: {e}")
        return []
    finally:
        conn.close()


# ── Scan Alert Log ────────────────────────────────────────────────────────────

# ── Fix Request Operations ────────────────────────────────────────────────────

def create_fix_request(domain: str, receipt_id: str, reported_by: str,
                       issue_category: str, issue_count: int = 0,
                       notes: str = None) -> int:
    """Insert one fix_request row. Returns new row ID or None on failure."""
    conn = get_conn()
    if not conn:
        return None
    try:
        clean = domain.replace('www.', '')
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO fix_requests
                    (domain, receipt_id, reported_by, issue_category, issue_count, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (clean, receipt_id, reported_by, issue_category, issue_count, notes))
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        print(f"create_fix_request error: {e}")
        return None
    finally:
        conn.close()


def get_fix_requests_by_domain(domain: str, status: str = None) -> list:
    """Return fix_requests for a domain. Pass status='pending' to filter."""
    conn = get_conn()
    if not conn:
        return []
    try:
        clean = domain.replace('www.', '')
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if status:
                cur.execute("""
                    SELECT * FROM fix_requests
                    WHERE domain = %s AND status = %s
                    ORDER BY created_at DESC
                """, (clean, status))
            else:
                cur.execute("""
                    SELECT * FROM fix_requests
                    WHERE domain = %s
                    ORDER BY created_at DESC
                """, (clean,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"get_fix_requests_by_domain error: {e}")
        return []
    finally:
        conn.close()


def update_fix_request(request_id: int, status: str,
                       confirmation_receipt_id: str = None) -> bool:
    """Update a fix_request after a confirmation scan. status: confirmed|partial|failed"""
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE fix_requests
                SET status                  = %s,
                    confirmation_receipt_id = %s,
                    confirmed_at            = NOW()
                WHERE id = %s
            """, (status, confirmation_receipt_id, request_id))
        return True
    except Exception as e:
        print(f"update_fix_request error: {e}")
        return False
    finally:
        conn.close()


def get_all_pending_fix_domains() -> list:
    """Distinct domains with at least one pending fix_request. Used by cron."""
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT domain FROM fix_requests
                WHERE status = 'pending'
                ORDER BY domain
            """)
            return [row[0] for row in cur.fetchall()]
    except Exception as e:
        print(f"get_all_pending_fix_domains error: {e}")
        return []
    finally:
        conn.close()


# ── Scan Alert Log ────────────────────────────────────────────────────────────

def log_scan_alert(domain: str, scanner_ip: str = None, scan_type: str = 'external') -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        clean = domain.replace('www.', '')
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO scan_alerts (domain, scanner_ip, scan_type)
                VALUES (%s, %s, %s)
            """, (clean, scanner_ip, scan_type))
        return True
    except Exception as e:
        print(f"log_scan_alert error: {e}")
        return False
    finally:
        conn.close()


# ── Email Queue ───────────────────────────────────────────────────────────────

EMAIL_QUEUE_SCHEMA = """
CREATE TABLE IF NOT EXISTS email_queue (
    id              SERIAL PRIMARY KEY,
    email           TEXT NOT NULL,
    domain          TEXT NOT NULL,
    sequence        TEXT NOT NULL,
    step            INTEGER NOT NULL,
    send_after      TIMESTAMPTZ NOT NULL,
    sent            BOOLEAN NOT NULL DEFAULT FALSE,
    sent_at         TIMESTAMPTZ,
    cancelled       BOOLEAN NOT NULL DEFAULT FALSE,
    receipt_json    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_queue_pending
    ON email_queue(send_after)
    WHERE sent = FALSE AND cancelled = FALSE;

CREATE INDEX IF NOT EXISTS idx_email_queue_email
    ON email_queue(email);

CREATE UNIQUE INDEX IF NOT EXISTS idx_email_queue_unique
    ON email_queue(email, sequence, step)
    WHERE sent = FALSE AND cancelled = FALSE;
"""


def init_email_queue():
    """Create email_queue table if it doesn't exist."""
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(EMAIL_QUEUE_SCHEMA)
        print("Email queue schema initialized")
        return True
    except Exception as e:
        print(f"Email queue init error: {e}")
        return False
    finally:
        conn.close()


def queue_sequence(email: str, domain: str, sequence: str,
                   receipt: dict = None, steps: list = None) -> bool:
    """
    Insert all steps of a sequence into the email queue.
    steps = list of (step_number, delay_hours) tuples.
    Uses INSERT ... ON CONFLICT DO NOTHING to prevent duplicates.
    """
    conn = get_conn()
    if not conn:
        return False
    try:
        import json
        receipt_json = json.dumps(receipt) if receipt else None
        now = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            for step_num, delay_hours in steps:
                send_after = now + timedelta(hours=delay_hours)
                cur.execute("""
                    INSERT INTO email_queue
                        (email, domain, sequence, step, send_after, receipt_json)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (email, sequence, step)
                    WHERE sent = FALSE AND cancelled = FALSE
                    DO NOTHING
                """, (email, domain, sequence, step_num, send_after, receipt_json))
        print(f"[QUEUE] Queued {len(steps)} steps of '{sequence}' for {email}")
        return True
    except Exception as e:
        print(f"queue_sequence error: {e}")
        return False
    finally:
        conn.close()


def get_due_emails() -> list:
    """
    Return all unsent, uncancelled emails whose send_after has passed.
    Called by cron every hour.
    """
    conn = get_conn()
    if not conn:
        return []
    try:
        import psycopg2.extras
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, email, domain, sequence, step, receipt_json
                FROM email_queue
                WHERE sent = FALSE
                  AND cancelled = FALSE
                  AND send_after <= NOW()
                ORDER BY send_after ASC
                LIMIT 100
            """)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f"get_due_emails error: {e}")
        return []
    finally:
        conn.close()


def mark_email_sent(queue_id: int) -> bool:
    """Mark a queued email as sent."""
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE email_queue
                SET sent = TRUE, sent_at = NOW()
                WHERE id = %s
            """, (queue_id,))
        return True
    except Exception as e:
        print(f"mark_email_sent error: {e}")
        return False
    finally:
        conn.close()


def cancel_sequence(email: str, sequence: str) -> bool:
    """
    Cancel all unsent emails in a sequence for an email address.
    Used when a free scanner purchases — cancels their nurture sequence.
    """
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE email_queue
                SET cancelled = TRUE
                WHERE email = %s
                  AND sequence = %s
                  AND sent = FALSE
            """, (email, sequence))
            cancelled = cur.rowcount
        print(f"[QUEUE] Cancelled {cancelled} pending '{sequence}' emails for {email}")
        return True
    except Exception as e:
        print(f"cancel_sequence error: {e}")
        return False
    finally:
        conn.close()


def cancel_all_sequences(email: str) -> bool:
    """Cancel ALL unsent emails for an email address. Used on purchase."""
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE email_queue
                SET cancelled = TRUE
                WHERE email = %s AND sent = FALSE
            """, (email,))
            cancelled = cur.rowcount
        print(f"[QUEUE] Cancelled {cancelled} pending emails for {email}")
        return True
    except Exception as e:
        print(f"cancel_all_sequences error: {e}")
        return False
    finally:
        conn.close()
