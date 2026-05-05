"""
ICC Email Queue System
Generates personalized outreach emails for every prospect,
stores them for review, sends approved ones via SendGrid.
Hans-Peter reviews in ICC → clicks Approve → email sends from hello@idrshield.com
"""

import os, json
from datetime import datetime, timezone

SENDGRID_KEY  = os.environ.get('SENDGRID_API_KEY', '')
FROM_EMAIL    = 'hello@idrshield.com'
FROM_NAME     = 'Hans-Peter Nkansah — Institute of Digital Remediation'
DEADLINE      = datetime(2026, 5, 11, tzinfo=timezone.utc)


# ── DATABASE SETUP ────────────────────────────────────────────────────────────

def init_email_queue_table():
    from database import get_conn
    conn = get_conn()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS icc_email_queue (
                    id            SERIAL PRIMARY KEY,
                    prospect_id   TEXT,
                    prospect_name TEXT,
                    prospect_type TEXT,
                    prospect_city TEXT,
                    prospect_state TEXT,
                    prospect_email TEXT,
                    subject       TEXT NOT NULL,
                    body_text     TEXT NOT NULL,
                    idr_score     INTEGER,
                    criticals     INTEGER,
                    status        TEXT DEFAULT 'pending',
                    created_at    TIMESTAMPTZ DEFAULT NOW(),
                    approved_at   TIMESTAMPTZ,
                    sent_at       TIMESTAMPTZ,
                    error_msg     TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS icc_association_queue (
                    id            SERIAL PRIMARY KEY,
                    assoc_id      TEXT,
                    assoc_name    TEXT,
                    contact_email TEXT,
                    subject       TEXT NOT NULL,
                    body_text     TEXT NOT NULL,
                    status        TEXT DEFAULT 'pending',
                    created_at    TIMESTAMPTZ DEFAULT NOW(),
                    approved_at   TIMESTAMPTZ,
                    sent_at       TIMESTAMPTZ
                )
            """)
        print('[ICC_QUEUE] Email queue tables ready')
        return True
    except Exception as e:
        print(f'[ICC_QUEUE] Init error: {e}')
        return False
    finally:
        conn.close()


# ── EMAIL GENERATORS ──────────────────────────────────────────────────────────

def _days_left():
    return max(0, (DEADLINE - datetime.now(timezone.utc)).days)


def generate_prospect_email(prospect: dict) -> dict:
    """Generate a personalized outreach email for a prospect."""
    name    = prospect.get('name', 'Healthcare Organization')
    city    = prospect.get('city', '')
    state   = prospect.get('state', '')
    score   = prospect.get('idr_score')
    crits   = prospect.get('criticals', 0) or 0
    otype   = prospect.get('org_type', 'fqhc')
    days    = _days_left()

    type_map = {
        'fqhc': ('health center', 'FQHCs are explicitly named in HHS 89 FR 40066 as covered entities. Your federal funding relationship means HHS OCR has direct jurisdiction over your digital presence.'),
        'nh':   ('nursing facility', 'The Section 504 digital requirement covers your website, online admissions forms, and family portal. Enforcement is complaint-driven — identical in mechanism to CMS/QAPI.'),
        'hha':  ('home health agency', 'Home health agencies receiving Medicare or Medicaid funding are covered entities under the May 11 WCAG 2.1 AA digital accessibility requirement.'),
    }
    org_label, type_context = type_map.get(otype, ('healthcare organization', 'Your organization receives federal health funding and is a covered entity under HHS 89 FR 40066.'))

    location = f"{city}, {state}" if city and state else (state or 'Florida')

    if score is not None and score < 60:
        subject = f"HHS Accessibility Scan — {name} — {crits} Critical Violations Found"
        body = f"""Hi,

I wanted to make sure your compliance team was aware of something time-sensitive before May 11.

I ran an external HHS accessibility scan of {name}'s website ahead of the Section 504 deadline.

Score: {score}/100
Critical violations: {crits}
Status: FAIL
Deadline: May 11, 2026 — {days} days away

{type_context}

The {crits} critical violation{"s" if crits != 1 else ""} found would be cited in an OCR investigation as direct barriers to patient access. Organizations without a documented audit record have nothing on file when a complaint is filed.

We publish independent third-party HHS accessibility audit records — a timestamped, cryptographically sealed document that goes on a public compliance registry. Initial audit is $497, delivered within 48 hours.

You can see the full scan results and activate at: idrshield.com/healthcare

Free to review — no obligation.

Hans-Peter Nkansah
Institute of Digital Remediation
hello@idrshield.com
idrshield.com"""

    else:
        subject = f"May 11 HHS Deadline — {name} — 48-Hour Audit Available"
        body = f"""Hi,

I work in HHS healthcare accessibility compliance and wanted to make sure {name} had a documented WCAG 2.1 AA audit record before the May 11 deadline.

{type_context}

HHS 89 FR 40066 — published July 8, 2024 — requires documented WCAG 2.1 AA conformance for your website, patient portal, and any digital intake tools by May 11, 2026. That is {days} days from today.

The risk isn't just having violations. It's having no documentation when a patient complaint triggers an OCR investigation. Organizations with a dated, independently verified audit record — even one showing violations and a remediation plan — are in a fundamentally stronger position than those with nothing on file.

We publish third-party HHS audit records for {org_label}s across {location} and nationally. Initial audit is $497, delivered within 48 hours. Free readiness scan at idrshield.com/healthcare.

Happy to answer any questions about the rule — no obligation.

Hans-Peter Nkansah
Institute of Digital Remediation
hello@idrshield.com
idrshield.com"""

    return {
        'prospect_id':    prospect.get('id', ''),
        'prospect_name':  name,
        'prospect_type':  otype,
        'prospect_city':  city,
        'prospect_state': state,
        'subject':        subject,
        'body_text':      body,
        'idr_score':      score,
        'criticals':      crits,
    }


def generate_association_emails() -> list:
    """Generate pitch emails for all 10 associations."""
    days = _days_left()
    assocs = [
        {
            'id': 'nachc',
            'name': 'NACHC — National Association of Community Health Centers',
            'email': 'advocacy@nachc.org',
            'subject': f'May 11 HHS Section 504 Deadline — Member Alert Opportunity',
            'body': f"""Hi,

I'm reaching out because the May 11, 2026 HHS Section 504 digital accessibility deadline is {days} days away and health centers are among the most directly exposed organizations in the country.

FQHCs are explicitly named in HHS 89 FR 40066 as covered entities. Every health center's website, patient portal, and digital intake tool must meet WCAG 2.1 AA by May 11. Most health center administrators know the deadline is coming — far fewer have a documented audit record on file. That gap is the risk.

I'd like to offer NACHC a member compliance alert, written and ready to send within 24 hours at no cost. The piece would explain exactly what the rule requires, what health centers need documented before enforcement opens, and where to get an independent audit record.

I run the Institute of Digital Remediation. We publish independent third-party HHS accessibility audit records for health centers nationally. I'm not asking for a promotional placement — I'm offering factual compliance content your members need right now.

Would a member alert be useful for your next communication?

Hans-Peter Nkansah
Institute of Digital Remediation
hello@idrshield.com
idrshield.com/healthcare"""
        },
        {
            'id': 'nhsa',
            'name': 'NHSA — National Head Start Association',
            'email': 'info@nhsa.org',
            'subject': f'May 11 HHS Digital Deadline — Head Start Programs Are Covered',
            'body': f"""Hi,

Head Start programs receive direct HHS funding and are explicitly covered by the May 11 Section 504 digital accessibility deadline. Every program website, enrollment portal, and digital family resource must meet WCAG 2.1 AA by May 11, 2026 — {days} days away.

Most program directors I've spoken with assume this rule applies to hospitals and clinics, not Head Start. It does. And programs without a documented audit record are exposed the moment a parent files an accessibility complaint.

I'd like to offer NHSA a member alert explaining exactly what's required and what programs should have documented before the deadline. I run the Institute of Digital Remediation and we publish independent HHS audit records. I can have the article written and delivered within 24 hours of your go-ahead.

Would that be useful for your next member communication?

Hans-Peter Nkansah
Institute of Digital Remediation
hello@idrshield.com
idrshield.com/healthcare"""
        },
        {
            'id': 'ahca',
            'name': 'AHCA — American Health Care Association',
            'email': 'info@ahca.org',
            'subject': f'May 11 HHS Website Accessibility Deadline — Long-Term Care Members',
            'body': f"""Hi,

The May 11, 2026 HHS Section 504 digital accessibility deadline is {days} days away and nursing homes and post-acute care facilities are covered entities under HHS 89 FR 40066.

Your members' websites, online admissions forms, and family portals are all subject to WCAG 2.1 AA compliance. The enforcement mechanism is complaint-driven — the same structure your members understand from CMS oversight — but without the documentation, there's nothing on file when OCR comes looking.

I'd like to offer AHCA a member compliance alert, written and ready within 24 hours at no cost. I run the Institute of Digital Remediation and we publish independent third-party HHS audit records for long-term care facilities.

Would a member alert be useful for your next communication?

Hans-Peter Nkansah
Institute of Digital Remediation
hello@idrshield.com
idrshield.com/healthcare"""
        },
        {
            'id': 'mgma',
            'name': 'MGMA — Medical Group Management Association',
            'email': 'advocacy@mgma.org',
            'subject': f'May 11 HHS Deadline — Physician Practice Websites Are Covered',
            'body': f"""Hi,

Physician practices that accept Medicaid or participate in any HHS-funded program are covered by the May 11, 2026 Section 504 digital accessibility deadline — {days} days away.

This covers their websites, patient portals, and online scheduling systems. MGMA members include hundreds of thousands of practice administrators who may not be aware their digital presence is subject to this rule.

I'd like to offer MGMA a member compliance alert on the deadline — written and ready within 24 hours at no cost. I run the Institute of Digital Remediation and we publish independent HHS accessibility audit records.

Would that be useful for your members right now?

Hans-Peter Nkansah
Institute of Digital Remediation
hello@idrshield.com
idrshield.com/healthcare"""
        },
        {
            'id': 'nahc',
            'name': 'NAHC — National Association for Home Care & Hospice',
            'email': 'info@nahc.org',
            'subject': f'May 11 HHS Digital Deadline — Home Health Agencies Are Covered',
            'body': f"""Hi,

Home health agencies and hospices receiving Medicare or Medicaid funding are covered entities under the May 11 HHS Section 504 digital accessibility deadline — {days} days from today.

Every agency website, online intake form, and patient-facing digital tool must meet WCAG 2.1 AA. Without a documented audit record, a single patient complaint opens an OCR investigation with nothing on file.

I'd like to offer NAHC a member compliance alert — written, ready within 24 hours, no cost. I run the Institute of Digital Remediation and we publish independent HHS audit records for home health agencies nationally.

Would this be useful for your next member communication?

Hans-Peter Nkansah
Institute of Digital Remediation
hello@idrshield.com
idrshield.com/healthcare"""
        },
        {
            'id': 'leadingage',
            'name': 'LeadingAge',
            'email': 'info@leadingage.org',
            'subject': f'May 11 HHS Section 504 Deadline — Non-Profit Aging Services Members',
            'body': f"""Hi,

LeadingAge members — nursing homes, assisted living, hospice, and home health — are covered entities under the May 11 HHS Section 504 digital accessibility deadline. {days} days remain.

The rule requires WCAG 2.1 AA compliance for all digital content, including websites, family portals, and online admissions. Many non-profit aging services organizations have the mission commitment but lack the technical documentation OCR looks for.

I'd like to offer LeadingAge a member compliance alert — written and ready within 24 hours at no cost. I run the Institute of Digital Remediation and we publish independent HHS audit records.

Would that be useful for your members?

Hans-Peter Nkansah
Institute of Digital Remediation
hello@idrshield.com
idrshield.com/healthcare"""
        },
        {
            'id': 'ahla',
            'name': 'AHLA — American Health Law Association',
            'email': 'info@americanhealthlaw.org',
            'subject': f'May 11 HHS Section 504 Digital Compliance — Guest Article for AHLA',
            'body': f"""Hi,

I'd like to offer AHLA a guest article on the May 11 HHS Section 504 digital accessibility deadline — framed specifically for healthcare counsel.

The piece would cover: what HHS 89 FR 40066 actually requires technically, which entities are covered, what "good faith compliance posture" means in an OCR investigation, and what documentation counsel should ensure clients have on file before enforcement opens.

AHLA members are advising covered organizations right now. A well-timed article in Health Law Daily or The Health Lawyer reaches exactly the attorneys whose clients need this information in the next {days} days.

I run the Institute of Digital Remediation. I can have a 600-word draft ready within 24 hours.

Hans-Peter Nkansah
Institute of Digital Remediation
hello@idrshield.com
idrshield.com/healthcare"""
        },
        {
            'id': 'ada_dental',
            'name': 'ADA — American Dental Association',
            'email': 'memberservice@ada.org',
            'subject': f'May 11 HHS Deadline — Dental Practices Accepting Medicaid Are Covered',
            'body': f"""Hi,

Dental practices that accept Medicaid are covered by the May 11, 2026 HHS Section 504 digital accessibility deadline — {days} days away. This is one of the most commonly missed applications of the rule.

Every practice website, online scheduling tool, and patient intake form must meet WCAG 2.1 AA. ADA members include hundreds of thousands of practices that may not realize their digital presence falls under this requirement.

I'd like to offer ADA a member practice alert — written, ready within 24 hours, no cost. I run the Institute of Digital Remediation and we publish independent HHS audit records for dental practices.

Would this be useful for ADA Practice Success resources?

Hans-Peter Nkansah
Institute of Digital Remediation
hello@idrshield.com
idrshield.com/healthcare"""
        },
        {
            'id': 'ahip',
            'name': 'AHIP — America\'s Health Insurance Plans',
            'email': 'info@ahip.org',
            'subject': f'May 11 HHS Section 504 Digital Deadline — Health Plan Members',
            'body': f"""Hi,

Health insurers and managed care organizations are covered entities under the May 11 HHS Section 504 digital accessibility deadline — {days} days away.

Member portals, plan comparison tools, provider directories, and digital enrollment systems all fall under WCAG 2.1 AA requirements. For health plans, the digital surface area is large and the patient population includes the very people the rule was designed to protect.

I'd like to offer AHIP a member compliance alert — written and ready within 24 hours at no cost. I run the Institute of Digital Remediation and we publish independent HHS audit records.

Hans-Peter Nkansah
Institute of Digital Remediation
hello@idrshield.com
idrshield.com/healthcare"""
        },
        {
            'id': 'jdsupra',
            'name': 'JD Supra — Healthcare Legal Publications',
            'email': 'editorial@jdsupra.com',
            'subject': f'Guest Article: HHS Section 504 Digital Deadline — Healthcare Compliance Alert',
            'body': f"""Hi,

I'd like to submit a guest article for JD Supra's healthcare practice area on the May 11, 2026 HHS Section 504 digital accessibility deadline.

The piece: "The May 11 HHS Digital Accessibility Deadline: What Healthcare Organizations Need Documented Before Enforcement Opens" — 600-800 words covering the regulatory basis, covered entities, what OCR looks for in investigations, and what constitutes a defensible compliance record.

JD Supra reaches 250,000+ legal and compliance professionals. Given the {days}-day window, timing is critical. I can have the full article submitted within 24 hours.

I run the Institute of Digital Remediation, which publishes independent third-party HHS accessibility audit records for healthcare organizations.

Hans-Peter Nkansah
Institute of Digital Remediation
hello@idrshield.com
idrshield.com/healthcare"""
        },
    ]
    return assocs


# ── QUEUE MANAGEMENT ──────────────────────────────────────────────────────────

def queue_prospect_email(email_data: dict) -> bool:
    """Store a generated email in the queue for approval."""
    from database import get_conn
    conn = get_conn()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            # Don't duplicate — check if prospect already queued today
            cur.execute("""
                SELECT id FROM icc_email_queue
                WHERE prospect_id = %s AND status IN ('pending','approved')
                AND created_at > NOW() - INTERVAL '24 hours'
                LIMIT 1
            """, (email_data.get('prospect_id',''),))
            if cur.fetchone():
                return False  # Already queued

            cur.execute("""
                INSERT INTO icc_email_queue
                    (prospect_id, prospect_name, prospect_type, prospect_city,
                     prospect_state, subject, body_text, idr_score, criticals)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                email_data.get('prospect_id',''),
                email_data.get('prospect_name',''),
                email_data.get('prospect_type',''),
                email_data.get('prospect_city',''),
                email_data.get('prospect_state',''),
                email_data['subject'],
                email_data['body_text'],
                email_data.get('idr_score'),
                email_data.get('criticals',0),
            ))
        return True
    except Exception as e:
        print(f'[ICC_QUEUE] Queue error: {e}')
        return False
    finally:
        conn.close()


def queue_association_emails():
    """Pre-populate all 10 association emails in the queue."""
    from database import get_conn
    conn = get_conn()
    if not conn: return 0
    added = 0
    try:
        for a in generate_association_emails():
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM icc_association_queue
                    WHERE assoc_id = %s AND status IN ('pending','approved','sent')
                    LIMIT 1
                """, (a['id'],))
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO icc_association_queue
                            (assoc_id, assoc_name, contact_email, subject, body_text)
                        VALUES (%s,%s,%s,%s,%s)
                    """, (a['id'], a['name'], a['email'], a['subject'], a['body']))
                    added += 1
        print(f'[ICC_QUEUE] {added} association emails queued')
    except Exception as e:
        print(f'[ICC_QUEUE] Assoc queue error: {e}')
    finally:
        conn.close()
    return added


def get_pending_emails(limit=50) -> list:
    from database import get_conn
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, prospect_name, prospect_type, prospect_city, prospect_state,
                       subject, body_text, idr_score, criticals, status, created_at
                FROM icc_email_queue
                WHERE status = 'pending'
                ORDER BY
                    CASE WHEN idr_score IS NOT NULL AND idr_score < 60 THEN 0 ELSE 1 END,
                    criticals DESC NULLS LAST,
                    created_at DESC
                LIMIT %s
            """, (limit,))
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return rows
    except Exception as e:
        print(f'[ICC_QUEUE] Fetch error: {e}')
        return []
    finally:
        conn.close()


def get_pending_association_emails() -> list:
    from database import get_conn
    conn = get_conn()
    if not conn: return []
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, assoc_id, assoc_name, contact_email,
                       subject, body_text, status, created_at
                FROM icc_association_queue
                WHERE status = 'pending'
                ORDER BY id ASC
            """)
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception as e:
        return []
    finally:
        conn.close()


def approve_and_send(queue_id: int, to_email: str, edited_body: str = None) -> dict:
    """Approve and send a prospect email via SendGrid."""
    from database import get_conn
    conn = get_conn()
    if not conn: return {'success': False, 'error': 'DB unavailable'}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT prospect_name, subject, body_text, prospect_email
                FROM icc_email_queue WHERE id = %s AND status = 'pending'
            """, (queue_id,))
            row = cur.fetchone()
        if not row:
            return {'success': False, 'error': 'Email not found or already sent'}

        name, subject, body, stored_email = row
        body = edited_body or body
        recipient = to_email or stored_email

        if not recipient:
            # Mark as approved but no email address — needs manual send
            with conn.cursor() as cur:
                cur.execute("UPDATE icc_email_queue SET status='approved', approved_at=NOW() WHERE id=%s", (queue_id,))
            return {'success': True, 'sent': False, 'message': 'Approved — add recipient email to send'}

        _send_via_sendgrid(recipient, subject, body)

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_email_queue
                SET status='sent', approved_at=NOW(), sent_at=NOW()
                WHERE id=%s
            """, (queue_id,))
        return {'success': True, 'sent': True, 'to': recipient}

    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def approve_and_send_association(queue_id: int, edited_body: str = None) -> dict:
    """Approve and send an association email via SendGrid."""
    from database import get_conn
    conn = get_conn()
    if not conn: return {'success': False, 'error': 'DB unavailable'}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT assoc_name, contact_email, subject, body_text
                FROM icc_association_queue WHERE id = %s AND status = 'pending'
            """, (queue_id,))
            row = cur.fetchone()
        if not row:
            return {'success': False, 'error': 'Not found or already sent'}

        name, email, subject, body = row
        body = edited_body or body

        _send_via_sendgrid(email, subject, body)

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_association_queue
                SET status='sent', approved_at=NOW(), sent_at=NOW()
                WHERE id=%s
            """, (queue_id,))
        return {'success': True, 'sent': True, 'to': email, 'name': name}

    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()


def _send_via_sendgrid(to_email: str, subject: str, body_text: str):
    """Send plain text email via SendGrid from hello@idrshield.com."""
    if not SENDGRID_KEY:
        raise Exception('SendGrid key not configured')
    import sendgrid as sg_module
    from sendgrid.helpers.mail import Mail, Email, To, Content
    message = Mail(
        from_email=Email(FROM_EMAIL, FROM_NAME),
        to_emails=To(to_email),
        subject=subject,
    )
    message.content = [Content('text/plain', body_text)]
    client = sg_module.SendGridAPIClient(api_key=SENDGRID_KEY)
    response = client.client.mail.send.post(request_body=message.get())
    if response.status_code not in (200, 202):
        raise Exception(f'SendGrid error: {response.status_code}')


def get_queue_stats() -> dict:
    from database import get_conn
    conn = get_conn()
    if not conn: return {}
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE status='pending') as pending,
                    COUNT(*) FILTER (WHERE status='sent') as sent,
                    COUNT(*) FILTER (WHERE status='approved') as approved
                FROM icc_email_queue
            """)
            r = cur.fetchone()
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE status='pending') as assoc_pending,
                    COUNT(*) FILTER (WHERE status='sent') as assoc_sent
                FROM icc_association_queue
            """)
            r2 = cur.fetchone()
        return {
            'prospect_pending': r[0] or 0,
            'prospect_sent': r[1] or 0,
            'prospect_approved': r[2] or 0,
            'assoc_pending': r2[0] or 0,
            'assoc_sent': r2[1] or 0,
        }
    except:
        return {}
    finally:
        conn.close()


def generate_and_queue_from_prospects(limit=100):
    """
    Pull scanned prospects from DB, generate emails, add to queue.
    Runs hourly in background.
    """
    from database import get_conn
    from icc_database import get_prospects
    conn = get_conn()
    if not conn: return 0

    try:
        prospects = get_prospects(limit=limit, scanned_only=False)
    except:
        return 0
    finally:
        conn.close()

    queued = 0
    for p in prospects:
        email_data = generate_prospect_email(p)
        if queue_prospect_email(email_data):
            queued += 1
    if queued:
        print(f'[ICC_QUEUE] {queued} prospect emails queued')
    return queued
