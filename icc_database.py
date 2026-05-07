"""
ICC — icc_database.py
Database layer for IDR Command Center.
Creates and manages ICC-specific tables in the existing PostgreSQL database.
"""

import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

def get_conn():
    from database import get_conn as _get
    return _get()


# ── Schema ────────────────────────────────────────────────────────────────────

ICC_SCHEMA = """

-- Prospect database: every healthcare org we know about
CREATE TABLE IF NOT EXISTS icc_prospects (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    org_type        TEXT NOT NULL,  -- fqhc, nh, hha, clinic, dental
    address         TEXT,
    city            TEXT,
    state           TEXT,
    zip             TEXT,
    phone           TEXT,
    website         TEXT,
    idr_score       INTEGER,
    critical_count  INTEGER,
    scanned         BOOLEAN DEFAULT FALSE,
    scanned_at      TIMESTAMPTZ,
    priority        BOOLEAN DEFAULT FALSE,
    outreach_msg    TEXT,
    source          TEXT,           -- hrsa, cms_nh, cms_hha, manual
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_icc_prospects_state   ON icc_prospects(state);
CREATE INDEX IF NOT EXISTS idx_icc_prospects_type    ON icc_prospects(org_type);
CREATE INDEX IF NOT EXISTS idx_icc_prospects_priority ON icc_prospects(priority);
CREATE INDEX IF NOT EXISTS idx_icc_prospects_score   ON icc_prospects(idr_score);

-- Outreach tracker: every contact attempt
CREATE TABLE IF NOT EXISTS icc_outreach (
    id              SERIAL PRIMARY KEY,
    prospect_id     TEXT REFERENCES icc_prospects(id),
    prospect_name   TEXT,
    contact_name    TEXT,
    contact_title   TEXT,
    message_type    TEXT,  -- connection, scan_personal, followup, fqhc, nh, close
    status          TEXT DEFAULT 'sent',  -- sent, connected, replied, interested, converted, no_response
    notes           TEXT,
    revenue         INTEGER DEFAULT 0,
    sent_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_icc_outreach_status   ON icc_outreach(status);
CREATE INDEX IF NOT EXISTS idx_icc_outreach_prospect ON icc_outreach(prospect_id);

-- Activity log: everything ICC does gets logged here
CREATE TABLE IF NOT EXISTS icc_activity (
    id              SERIAL PRIMARY KEY,
    event_type      TEXT NOT NULL,  -- prospect_loaded, scan_complete, outreach_sent, association_contacted, briefing_sent
    detail          TEXT,
    count           INTEGER DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_icc_activity_type ON icc_activity(event_type);
CREATE INDEX IF NOT EXISTS idx_icc_activity_time ON icc_activity(created_at DESC);

-- Association tracker: every mouthpiece channel
CREATE TABLE IF NOT EXISTS icc_associations (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    serves          TEXT,           -- who they represent
    member_count    TEXT,
    website         TEXT,
    contact_name    TEXT,
    contact_title   TEXT,
    contact_email   TEXT,
    status          TEXT DEFAULT 'not_contacted',  -- not_contacted, contacted, in_conversation, published, declined
    pitch_sent_at   TIMESTAMPTZ,
    notes           TEXT,
    priority_order  INTEGER DEFAULT 99,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ICC settings
CREATE TABLE IF NOT EXISTS icc_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
"""

def init_icc_db():
    conn = get_conn()
    if not conn:
        print('[ICC_DB] No database connection')
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(ICC_SCHEMA)
        print('[ICC_DB] Schema initialized')
        _seed_associations()
        return True
    except Exception as e:
        print(f'[ICC_DB] Schema error: {e}')
        return False
    finally:
        conn.close()


# ── Associations seed data ────────────────────────────────────────────────────

ASSOCIATIONS = [
    {
        'id': 'nachc', 'name': 'NACHC — National Association of Community Health Centers',
        'serves': 'Every FQHC in America — 1,400+ health centers',
        'member_count': '1,400+', 'website': 'nachc.org',
        'contact_name': 'Policy & Advocacy Team', 'contact_title': 'Director of Policy',
        'contact_email': 'advocacy@nachc.org', 'priority_order': 1,
    },
    {
        'id': 'nhsa', 'name': 'NHSA — National Head Start Association',
        'serves': 'Every Head Start program director in America',
        'member_count': '2,700+', 'website': 'nhsa.org',
        'contact_name': 'Communications Team', 'contact_title': 'Director of Communications',
        'contact_email': 'info@nhsa.org', 'priority_order': 2,
    },
    {
        'id': 'ahca', 'name': 'AHCA — American Health Care Association',
        'serves': 'Nursing homes and post-acute care facilities',
        'member_count': '14,000+', 'website': 'ahcancal.org',
        'contact_name': 'Government Affairs Team', 'contact_title': 'VP of Government Affairs',
        'contact_email': 'info@ahca.org', 'priority_order': 3,
    },
    {
        'id': 'mgma', 'name': 'MGMA — Medical Group Management Association',
        'serves': 'Physician practice executives and administrators',
        'member_count': '350,000+', 'website': 'mgma.com',
        'contact_name': 'Advocacy Team', 'contact_title': 'Director of Government Affairs',
        'contact_email': 'advocacy@mgma.org', 'priority_order': 4,
    },
    {
        'id': 'nahc', 'name': 'NAHC — National Association for Home Care & Hospice',
        'serves': 'Home health agencies and hospices',
        'member_count': '6,000+', 'website': 'nahc.org',
        'contact_name': 'Communications Team', 'contact_title': 'Director of Communications',
        'contact_email': 'info@nahc.org', 'priority_order': 5,
    },
    {
        'id': 'leadingage', 'name': 'LeadingAge',
        'serves': 'Non-profit aging services — nursing homes, assisted living, hospice',
        'member_count': '5,000+', 'website': 'leadingage.org',
        'contact_name': 'Policy Team', 'contact_title': 'VP of Policy',
        'contact_email': 'info@leadingage.org', 'priority_order': 6,
    },
    {
        'id': 'ahla', 'name': 'AHLA — American Health Law Association',
        'serves': 'Healthcare attorneys — they advise every covered organization',
        'member_count': '13,000+', 'website': 'americanhealthlaw.org',
        'contact_name': 'Publications Team', 'contact_title': 'Director of Publications',
        'contact_email': 'info@americanhealthlaw.org', 'priority_order': 7,
    },
    {
        'id': 'ada_dental', 'name': 'ADA — American Dental Association',
        'serves': 'Dentists and dental practices across America',
        'member_count': '161,000+', 'website': 'ada.org',
        'contact_name': 'Practice Resources Team', 'contact_title': 'Director of Practice Success',
        'contact_email': 'memberservice@ada.org', 'priority_order': 8,
    },
    {
        'id': 'ahip', 'name': 'AHIP — America\'s Health Insurance Plans',
        'serves': 'Health insurers and managed care organizations',
        'member_count': '1,300+', 'website': 'ahip.org',
        'contact_name': 'Policy Team', 'contact_title': 'VP of Policy',
        'contact_email': 'info@ahip.org', 'priority_order': 9,
    },
    {
        'id': 'jdsupra', 'name': 'JD Supra — Healthcare Legal Publications',
        'serves': 'Healthcare attorneys and in-house counsel',
        'member_count': '250,000+ readers', 'website': 'jdsupra.com',
        'contact_name': 'Content Team', 'contact_title': 'Editor',
        'contact_email': 'editorial@jdsupra.com', 'priority_order': 10,
    },
]

def _seed_associations():
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as cur:
            for a in ASSOCIATIONS:
                cur.execute("""
                    INSERT INTO icc_associations
                        (id, name, serves, member_count, website,
                         contact_name, contact_title, contact_email, priority_order)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                """, (a['id'], a['name'], a['serves'], a['member_count'],
                      a['website'], a['contact_name'], a['contact_title'],
                      a['contact_email'], a['priority_order']))
        print(f'[ICC_DB] Seeded {len(ASSOCIATIONS)} associations')
    except Exception as e:
        print(f'[ICC_DB] Seed error: {e}')
    finally:
        conn.close()


# ── Prospect operations ───────────────────────────────────────────────────────

def upsert_prospect(p: dict) -> bool:
    """Upsert a prospect — preserves existing score if not provided."""
    conn = get_conn()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO icc_prospects
                    (id, name, org_type, address, city, state, zip,
                     phone, website, source, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name,
                    phone=COALESCE(EXCLUDED.phone, icc_prospects.phone),
                    website=COALESCE(EXCLUDED.website, icc_prospects.website),
                    updated_at=NOW()
            """, (p['id'], p['name'], p.get('org_type','fqhc'),
                  p.get('address',''), p.get('city',''), p.get('state',''),
                  p.get('zip',''), p.get('phone',''), p.get('website',''),
                  p.get('source','browser')))
        return True
    except Exception as e:
        print(f'[ICC_DB] upsert_prospect error: {e}')
        return False
    finally:
        conn.close()


def bulk_upsert_prospects(prospects: list) -> int:
    """Upsert a list of prospects in one transaction. Returns count saved."""
    if not prospects: return 0
    conn = get_conn()
    if not conn: return 0
    saved = 0
    try:
        with conn.cursor() as cur:
            for p in prospects:
                try:
                    cur.execute("""
                        INSERT INTO icc_prospects
                            (id, name, org_type, address, city, state, zip,
                             phone, website, source, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                        ON CONFLICT (id) DO UPDATE SET
                            name=EXCLUDED.name,
                            phone=COALESCE(EXCLUDED.phone, icc_prospects.phone),
                            website=COALESCE(EXCLUDED.website, icc_prospects.website),
                            updated_at=NOW()
                    """, (p['id'], p['name'], p.get('org_type','fqhc'),
                          p.get('address',''), p.get('city',''), p.get('state',''),
                          p.get('zip',''), p.get('phone',''), p.get('website',''),
                          p.get('source','browser')))
                    saved += 1
                except Exception:
                    pass
        print(f'[ICC_DB] bulk_upsert: {saved}/{len(prospects)} prospects saved')
        return saved
    except Exception as e:
        print(f'[ICC_DB] bulk_upsert error: {e}')
        return 0
    finally:
        conn.close()


def save_scan_result(prospect_id: str, website: str, name: str,
                     score: int, criticals: int, total_issues: int = 0) -> bool:
    """Save a scan result — upserts the prospect row first then sets score."""
    conn = get_conn()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            # Ensure the prospect row exists
            cur.execute("""
                INSERT INTO icc_prospects (id, name, org_type, website, source, updated_at)
                VALUES (%s, %s, 'fqhc', %s, 'browser', NOW())
                ON CONFLICT (id) DO UPDATE SET
                    website=COALESCE(EXCLUDED.website, icc_prospects.website),
                    updated_at=NOW()
            """, (prospect_id, name or prospect_id, website))
            # Now set the score
            cur.execute("""
                UPDATE icc_prospects SET
                    idr_score=%s, critical_count=%s,
                    scanned=TRUE, scanned_at=NOW(),
                    priority=(%s < 60),
                    updated_at=NOW()
                WHERE id=%s
            """, (score, criticals, score, prospect_id))
        log_activity('scan_complete',
                     f'{name}: {score}/100 ({criticals} critical)'
                     + (' — PRIORITY' if score < 60 else ''))
        return True
    except Exception as e:
        print(f'[ICC_DB] save_scan_result error: {e}')
        return False
    finally:
        conn.close()


def mark_association_contacted(assoc_id: str, email: str = '') -> bool:
    """Mark an association as contacted after email is sent."""
    conn = get_conn()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_associations SET
                    status='contacted',
                    pitch_sent_at=NOW(),
                    contact_email=COALESCE(%s, contact_email),
                    updated_at=NOW()
                WHERE id=%s AND status='not_contacted'
            """, (email or None, assoc_id))
        return True
    except Exception as e:
        print(f'[ICC_DB] mark_association_contacted error: {e}')
        return False
    finally:
        conn.close()


def get_scanned_prospects(limit=100) -> list:
    """Get all prospects that have been scanned with scores."""
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, org_type, city, state, phone, website,
                       idr_score, critical_count, scanned_at, priority
                FROM icc_prospects
                WHERE scanned=TRUE AND idr_score IS NOT NULL
                ORDER BY priority DESC, idr_score ASC
                LIMIT %s
            """, (limit,))
            cols = [d[0] for d in cur.description]
            rows = []
            for r in cur.fetchall():
                row = dict(zip(cols, r))
                if row.get('scanned_at'):
                    row['scanned_at'] = row['scanned_at'].isoformat()
                rows.append(row)
            return rows
    except Exception as e:
        print(f'[ICC_DB] get_scanned_prospects error: {e}')
        return []
    finally:
        conn.close()


def get_warm_leads() -> list:
    """Get prospects with email opens or clicks — warm leads."""
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.id, p.name, p.website, p.idr_score, p.phone,
                       o.status, o.sent_at, o.notes
                FROM icc_prospects p
                JOIN icc_outreach o ON o.prospect_id = p.id
                WHERE o.status IN ('opened', 'clicked', 'replied', 'interested')
                ORDER BY o.updated_at DESC
                LIMIT 20
            """)
            if cur.description:
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
            return []
    except Exception as e:
        print(f'[ICC_DB] get_warm_leads error: {e}')
        return []
    finally:
        conn.close()


def update_prospect_score(prospect_id: str, score: int, criticals: int, msg: str) -> bool:
    conn = get_conn()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_prospects SET
                    idr_score=%s, critical_count=%s,
                    scanned=TRUE, scanned_at=NOW(),
                    priority=(%s < 60),
                    outreach_msg=%s, updated_at=NOW()
                WHERE id=%s
            """, (score, criticals, score, msg, prospect_id))
        return True
    except Exception as e:
        print(f'[ICC_DB] update_score error: {e}')
        return False
    finally:
        conn.close()


def get_prospects(state=None, org_type=None, priority_only=False,
                  unscanned_only=False, limit=200, offset=0) -> list:
    conn = get_conn()
    if not conn: return []
    try:
        conditions = []
        params = []
        if state:
            conditions.append('state = %s'); params.append(state)
        if org_type:
            conditions.append('org_type = %s'); params.append(org_type)
        if priority_only:
            conditions.append('priority = TRUE')
        if unscanned_only:
            conditions.append('scanned = FALSE')
            conditions.append("website != ''")
        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        params += [limit, offset]
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT * FROM icc_prospects
                {where}
                ORDER BY priority DESC, idr_score ASC NULLS LAST, name ASC
                LIMIT %s OFFSET %s
            """, params)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        print(f'[ICC_DB] get_prospects error: {e}')
        return []
    finally:
        conn.close()


def get_prospect_by_id(pid: str) -> dict:
    conn = get_conn()
    if not conn: return {}
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM icc_prospects WHERE id=%s', (pid,))
            row = cur.fetchone()
            return dict(row) if row else {}
    except Exception as e:
        return {}
    finally:
        conn.close()


def get_unscanned_with_websites(limit=20) -> list:
    return get_prospects(unscanned_only=True, limit=limit)


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_icc_stats() -> dict:
    conn = get_conn()
    if not conn: return {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM icc_prospects")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM icc_prospects WHERE scanned=TRUE")
            scanned = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM icc_prospects WHERE priority=TRUE")
            priority = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM icc_outreach")
            contacted = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM icc_outreach WHERE status='converted'")
            converted = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(revenue),0) FROM icc_outreach WHERE status='converted'")
            revenue = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM icc_outreach WHERE status IN ('replied','interested')")
            warm = cur.fetchone()[0]
            cur.execute("""
                SELECT event_type, detail, created_at FROM icc_activity
                ORDER BY created_at DESC LIMIT 20
            """)
            activity = [{'type':r[0],'detail':r[1],
                         'time':r[2].strftime('%H:%M') if r[2] else ''} for r in cur.fetchall()]
        from datetime import date as _date
        _today = _date.today()
        _dl = _date(2026, 5, 11)
        days_left = max(0, (_dl - _today).days)
        # Association contacted count
        cur.execute("SELECT COUNT(*) FROM icc_associations WHERE status != 'not_contacted'")
        assoc_contacted = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM icc_associations WHERE status = 'not_contacted'")
        assoc_not_contacted = cur.fetchone()[0]

        return {
            'total': total, 'scanned': scanned, 'priority': priority,
            'contacted': contacted, 'converted': converted,
            'revenue': revenue, 'warm': warm,
            'days_left': days_left, 'activity': activity,
            'assoc_contacted': assoc_contacted,
            'assoc_not_contacted': assoc_not_contacted,
        }
    except Exception as e:
        print(f'[ICC_DB] stats error: {e}')
        return {}
    finally:
        conn.close()


# ── Outreach operations ───────────────────────────────────────────────────────

def log_outreach(prospect_id: str, prospect_name: str, contact_name: str,
                 contact_title: str, message_type: str, notes: str = '') -> int:
    conn = get_conn()
    if not conn: return 0
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO icc_outreach
                    (prospect_id, prospect_name, contact_name,
                     contact_title, message_type, notes)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
            """, (prospect_id, prospect_name, contact_name,
                  contact_title, message_type, notes))
            return cur.fetchone()[0]
    except Exception as e:
        print(f'[ICC_DB] log_outreach error: {e}')
        return 0
    finally:
        conn.close()


def update_outreach_status(outreach_id: int, status: str,
                            revenue: int = 0, notes: str = '') -> bool:
    conn = get_conn()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_outreach SET
                    status=%s, revenue=%s,
                    notes=COALESCE(NULLIF(%s,''), notes),
                    updated_at=NOW()
                WHERE id=%s
            """, (status, revenue, notes, outreach_id))
        return True
    except Exception as e:
        return False
    finally:
        conn.close()


def get_outreach_list(status=None, limit=100) -> list:
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if status:
                cur.execute("""
                    SELECT * FROM icc_outreach WHERE status=%s
                    ORDER BY sent_at DESC LIMIT %s
                """, (status, limit))
            else:
                cur.execute("""
                    SELECT * FROM icc_outreach
                    ORDER BY sent_at DESC LIMIT %s
                """, (limit,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        return []
    finally:
        conn.close()


def get_followups_due() -> list:
    """Contacts sent 3+ days ago with no response."""
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM icc_outreach
                WHERE status = 'sent'
                  AND sent_at < NOW() - INTERVAL '3 days'
                ORDER BY sent_at ASC
                LIMIT 50
            """)
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        return []
    finally:
        conn.close()


# ── Activity log ──────────────────────────────────────────────────────────────

def log_activity(event_type: str, detail: str, count: int = 1):
    conn = get_conn()
    if not conn: return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO icc_activity (event_type, detail, count)
                VALUES (%s,%s,%s)
            """, (event_type, detail, count))
    except Exception as e:
        pass
    finally:
        conn.close()


# ── Association operations ────────────────────────────────────────────────────

def get_associations() -> list:
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM icc_associations ORDER BY priority_order')
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        return []
    finally:
        conn.close()


def update_association_status(assoc_id: str, status: str, notes: str = '') -> bool:
    conn = get_conn()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_associations SET
                    status=%s,
                    notes=COALESCE(NULLIF(%s,''), notes),
                    pitch_sent_at=CASE WHEN %s='contacted' AND pitch_sent_at IS NULL
                                  THEN NOW() ELSE pitch_sent_at END,
                    updated_at=NOW()
                WHERE id=%s
            """, (status, notes, status, assoc_id))
        return True
    except Exception as e:
        return False
    finally:
        conn.close()
