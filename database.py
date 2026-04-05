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


# ── Member Auth ───────────────────────────────────────────────────────────────

AUTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS member_sessions (
    id              SERIAL PRIMARY KEY,
    email           TEXT NOT NULL,
    token_hash      TEXT NOT NULL UNIQUE,
    token_type      TEXT NOT NULL DEFAULT 'magic_link',
    expires_at      TIMESTAMPTZ NOT NULL,
    used            BOOLEAN NOT NULL DEFAULT FALSE,
    used_at         TIMESTAMPTZ,
    created_ip      TEXT,
    used_ip         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_token_hash
    ON member_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_email
    ON member_sessions(email);
CREATE INDEX IF NOT EXISTS idx_sessions_expires
    ON member_sessions(expires_at)
    WHERE used = FALSE;
"""


def init_auth_schema():
    """Create member_sessions table if it doesn't exist."""
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(AUTH_SCHEMA)
        print("Auth schema initialized")
        return True
    except Exception as e:
        print(f"Auth schema init error: {e}")
        return False
    finally:
        conn.close()


def create_magic_token(email: str, token_hash: str, expires_at, ip: str = None) -> bool:
    """Store a new magic link token (hashed)."""
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            # Invalidate any existing unused magic links for this email
            cur.execute("""
                UPDATE member_sessions
                SET used = TRUE
                WHERE email = %s
                  AND token_type = 'magic_link'
                  AND used = FALSE
            """, (email,))
            # Insert new token
            cur.execute("""
                INSERT INTO member_sessions
                    (email, token_hash, token_type, expires_at, created_ip)
                VALUES (%s, %s, 'magic_link', %s, %s)
            """, (email, token_hash, expires_at, ip))
        return True
    except Exception as e:
        print(f"create_magic_token error: {e}")
        return False
    finally:
        conn.close()


def consume_magic_token(token_hash: str, ip: str = None):
    """
    Validate and consume a magic link token.
    Returns email string if valid, None if not found/expired/used.
    """
    conn = get_conn()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, email, expires_at, used
                FROM member_sessions
                WHERE token_hash = %s
                  AND token_type = 'magic_link'
            """, (token_hash,))
            row = cur.fetchone()
            if not row:
                return None
            if row['used']:
                return None
            if row['expires_at'] < datetime.now(timezone.utc):
                return None
            # Mark as used
            cur.execute("""
                UPDATE member_sessions
                SET used = TRUE, used_at = NOW(), used_ip = %s
                WHERE id = %s
            """, (ip, row['id']))
        return row['email']
    except Exception as e:
        print(f"consume_magic_token error: {e}")
        return None
    finally:
        conn.close()


def create_session_token(email: str, token_hash: str, expires_at, ip: str = None) -> bool:
    """Store a 30-day session token (hashed)."""
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO member_sessions
                    (email, token_hash, token_type, expires_at, created_ip)
                VALUES (%s, %s, 'session', %s, %s)
            """, (email, token_hash, expires_at, ip))
        return True
    except Exception as e:
        print(f"create_session_token error: {e}")
        return False
    finally:
        conn.close()


def validate_session_token(token_hash: str) -> str:
    """
    Validate a session token.
    Returns email if valid and not expired, None otherwise.
    """
    conn = get_conn()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT email, expires_at, used
                FROM member_sessions
                WHERE token_hash = %s
                  AND token_type = 'session'
            """, (token_hash,))
            row = cur.fetchone()
            if not row:
                return None
            if row['used']:
                return None
            if row['expires_at'] < datetime.now(timezone.utc):
                return None
            return row['email']
    except Exception as e:
        print(f"validate_session_token error: {e}")
        return None
    finally:
        conn.close()


def revoke_session_token(token_hash: str) -> bool:
    """Mark a session token as used (logout)."""
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE member_sessions
                SET used = TRUE, used_at = NOW()
                WHERE token_hash = %s AND token_type = 'session'
            """, (token_hash,))
        return True
    except Exception as e:
        print(f"revoke_session_token error: {e}")
        return False
    finally:
        conn.close()


def purge_expired_tokens() -> int:
    """
    Delete tokens expired more than 24h ago. Called by cron to keep table lean.
    Returns count of deleted rows.
    """
    conn = get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM member_sessions
                WHERE expires_at < NOW() - INTERVAL '24 hours'
            """)
            return cur.rowcount
    except Exception as e:
        print(f"purge_expired_tokens error: {e}")
        return 0
    finally:
        conn.close()


# ── Member portal queries ─────────────────────────────────────────────────────

def get_member_dashboard(email: str) -> dict:
    """
    Full dashboard data for a member identified by email.
    Returns registry record + scan history summary.
    """
    conn = get_conn()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Registry record
            cur.execute("""
                SELECT domain, registry_id, status, latest_score,
                       critical_count, scan_count, last_scanned,
                       badge_active, activated_by, created_at
                FROM registry
                WHERE activated_by = %s
                ORDER BY created_at ASC
            """, (email,))
            domains = [dict(r) for r in cur.fetchall()]

            if not domains:
                return None

            # Scan history for all their domains (last 20 scans each)
            result = []
            for d in domains:
                cur.execute("""
                    SELECT receipt_id, overall_score, overall_status,
                           critical_count, total_issues, timestamp_utc
                    FROM receipts
                    WHERE domain = %s
                    ORDER BY timestamp_utc DESC
                    LIMIT 20
                """, (d['domain'],))
                scans = []
                for row in cur.fetchall():
                    scans.append({
                        'receipt_id':    row['receipt_id'],
                        'score':         row['overall_score'],
                        'status':        row['overall_status'],
                        'critical_count': row['critical_count'],
                        'total_issues':  row['total_issues'],
                        'scanned_at':    row['timestamp_utc'].isoformat() if row['timestamp_utc'] else None,
                    })
                d_out = dict(d)
                d_out['last_scanned'] = d['last_scanned'].isoformat() if d.get('last_scanned') else None
                d_out['created_at']   = d['created_at'].isoformat()   if d.get('created_at')   else None
                d_out['scan_history'] = scans
                result.append(d_out)

            return result

    except Exception as e:
        print(f"get_member_dashboard error: {e}")
        return None
    finally:
        conn.close()


def get_member_evidence(email: str, domain: str) -> list:
    """Evidence log for a domain, verified to belong to this email."""
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Verify ownership
            cur.execute("""
                SELECT domain FROM registry
                WHERE domain = %s AND activated_by = %s
            """, (domain.replace('www.', ''), email))
            if not cur.fetchone():
                return None  # None = unauthorized vs [] = empty

            cur.execute("""
                SELECT event_type, event_detail, timestamp_utc, receipt_id
                FROM evidence_log
                WHERE domain = %s
                ORDER BY timestamp_utc ASC
            """, (domain.replace('www.', ''),))
            return [{
                'event_type':   r['event_type'],
                'detail':       r['event_detail'],
                'timestamp':    r['timestamp_utc'].isoformat() if r['timestamp_utc'] else None,
                'receipt_id':   r['receipt_id'],
            } for r in cur.fetchall()]
    except Exception as e:
        print(f"get_member_evidence error: {e}")
        return []
    finally:
        conn.close()


def get_member_fixes(email: str, domain: str) -> list:
    """Fix requests for a domain, verified to belong to this email."""
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT domain FROM registry
                WHERE domain = %s AND activated_by = %s
            """, (domain.replace('www.', ''), email))
            if not cur.fetchone():
                return None

            cur.execute("""
                SELECT id, issue_category, issue_count, status,
                       confirmation_receipt_id, confirmed_at,
                       notes, created_at
                FROM fix_requests
                WHERE domain = %s
                ORDER BY created_at DESC
            """, (domain.replace('www.', ''),))
            return [{
                'id':              r['id'],
                'category':        r['issue_category'],
                'original_count':  r['issue_count'],
                'status':          r['status'],
                'confirmation_id': r['confirmation_receipt_id'],
                'confirmed_at':    r['confirmed_at'].isoformat() if r.get('confirmed_at') else None,
                'notes':           r['notes'],
                'reported_at':     r['created_at'].isoformat() if r.get('created_at') else None,
            } for r in cur.fetchall()]
    except Exception as e:
        print(f"get_member_fixes error: {e}")
        return []
    finally:
        conn.close()


def get_latest_receipt_id(email: str, domain: str):
    """Get the most recent receipt_id for a domain owned by this email."""
    conn = get_conn()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.receipt_id
                FROM receipts r
                JOIN registry reg ON reg.domain = r.domain
                WHERE r.domain = %s AND reg.activated_by = %s
                ORDER BY r.timestamp_utc DESC
                LIMIT 1
            """, (domain.replace('www.', ''), email))
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        print(f"get_latest_receipt_id error: {e}")
        return None
    finally:
        conn.close()
