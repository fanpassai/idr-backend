# ICC Email Queue System
# Generates personalized outreach emails for every prospect,
# stores them for review, sends approved ones via SendGrid.
# Contact: hans-peter@instituteofdigitalremediation.org
import os, json
from datetime import datetime, timezone

SENDGRID_KEY  = os.environ.get('SENDGRID_API_KEY', '')
FROM_EMAIL      = 'hello@idrshield.com'
FROM_NAME       = 'IDR Shield'
FROM_EMAIL_INST = 'hans-peter@instituteofdigitalremediation.org'
FROM_NAME_INST  = 'Institute of Digital Remediation'
DEADLINE      = datetime(2026, 5, 11, tzinfo=timezone.utc)

# ── HTML EMAIL TEMPLATE ───────────────────────────────────────────────────────
_TEMPLATE_SENTINEL = True  # ensures no adjacent string concatenation
HTML_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<title>{subject}</title>
<style>
body{{margin:0;padding:0;font-family:Georgia,'Times New Roman',serif;}}
table{{border-collapse:collapse;mso-table-lspace:0;mso-table-rspace:0;}}
a{{text-decoration:none;}}
p{{margin:0 0 20px;}}
</style>
</head>
<body bgcolor="#F0EDE6" style="margin:0;padding:0;background-color:#F0EDE6;">

<table width="100%" cellpadding="0" cellspacing="0" border="0"
  bgcolor="#F0EDE6" style="background-color:#F0EDE6;padding:40px 0;">
<tr><td align="center">
<table width="580" cellpadding="0" cellspacing="0" border="0"
  style="max-width:580px;width:100%;">

  <!-- GOLD TOP RULE -->
  <tr>
    <td bgcolor="#C9A84C" height="5"
      style="background-color:#C9A84C;height:5px;
             font-size:0;line-height:0;border-radius:4px 4px 0 0;">&nbsp;</td>
  </tr>

  <!-- HEADER — white so iOS dark mode inverts it to dark naturally -->
  <tr>
    <td bgcolor="#FFFFFF"
      style="background-color:#FFFFFF;padding:28px 40px 24px;
             border-left:1px solid #E8DCC8;border-right:1px solid #E8DCC8;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td valign="middle">
            <p style="margin:0 0 4px;font-family:Georgia,serif;font-size:9px;
              letter-spacing:0.22em;color:#C9A84C;text-transform:uppercase;
              font-weight:700;">
              Institute of Digital Remediation
            </p>
            <p style="margin:0;font-family:Georgia,serif;font-size:26px;
              font-weight:700;color:#0F1E2E;letter-spacing:0.01em;line-height:1.1;">
              IDR Shield
            </p>
          </td>
          <td align="right" valign="middle">
            <table cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td bgcolor="#0F1E2E"
                  style="background-color:#0F1E2E;color:#C9A84C;
                         font-family:Georgia,serif;font-size:9px;font-weight:700;
                         letter-spacing:0.15em;text-transform:uppercase;
                         padding:6px 14px;border-radius:2px;">
                  HHS COMPLIANCE
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- DEADLINE STRIP -->
  <tr>
    <td bgcolor="#0F1E2E"
      style="background-color:#0F1E2E;padding:11px 40px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="font-family:Georgia,serif;font-size:10px;color:#94A3B8;
            letter-spacing:0.14em;text-transform:uppercase;">
            Federal Enforcement Deadline
          </td>
          <td align="right"
            style="font-family:Georgia,serif;font-size:12px;
              color:#C9A84C;font-weight:700;letter-spacing:0.03em;">
            May 11, 2026 &nbsp;|&nbsp; {days_left} days remaining
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- BODY -->
  <tr>
    <td bgcolor="#FFFFFF"
      style="background-color:#FFFFFF;padding:40px 40px 4px;
             border-left:1px solid #E8DCC8;border-right:1px solid #E8DCC8;">
      <p style="font-family:Georgia,serif;font-size:16px;color:#0F1E2E;
        line-height:1.5;font-weight:600;margin:0 0 28px;">
        Dear {salutation},
      </p>
      {body_html}
    </td>
  </tr>

  <!-- SIGNATURE DIVIDER + SIG -->
  <tr>
    <td bgcolor="#FFFFFF"
      style="background-color:#FFFFFF;padding:0 40px 36px;
             border-left:1px solid #E8DCC8;border-right:1px solid #E8DCC8;">
      <!-- Gold rule -->
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
        style="border-top:1px solid #C9A84C;padding-top:24px;margin-top:8px;">
        <tr>
          <td valign="top" style="padding-right:20px;">
            <p style="margin:0 0 2px;font-family:Georgia,serif;font-size:15px;
              font-weight:700;color:#0F1E2E;">
              Hans-Peter Nkansah
            </p>
            <p style="margin:0 0 10px;font-family:Georgia,serif;font-size:11px;
              color:#64748B;letter-spacing:0.04em;">
              Founder &amp; Director, Institute of Digital Remediation
            </p>
            <p style="margin:0 0 2px;font-family:Georgia,serif;font-size:11px;
              color:#64748B;">
              <a href="mailto:{sig_email}"
                style="color:#C9A84C;text-decoration:none;">{sig_email}</a>
            </p>
            <p style="margin:0 0 2px;font-family:Georgia,serif;font-size:11px;
              color:#64748B;">
              <a href="https://idrshield.com"
                style="color:#C9A84C;text-decoration:none;">idrshield.com</a>
            </p>
            <p style="margin:8px 0 0;font-family:Georgia,serif;font-size:10px;
              color:#94A3B8;letter-spacing:0.02em;">
              14 E Washington St, Orlando, FL 32801
            </p>
          </td>
          <td align="right" valign="top" width="120">
            <table cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td bgcolor="#F7F4EE"
                  style="background-color:#F7F4EE;border-radius:3px;
                         padding:10px 14px;font-family:Georgia,serif;font-size:9px;
                         color:#94A3B8;letter-spacing:0.1em;text-transform:uppercase;
                         text-align:center;line-height:1.7;border:1px solid #E8DCC8;">
                  Independent<br>HHS Audit<br>Records
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- FOOTER -->
  <tr>
    <td bgcolor="#2A2A2A"
      style="background-color:#2A2A2A;padding:18px 40px;
             border-radius:0 0 4px 4px;">
      <p style="margin:0;font-family:Georgia,serif;font-size:10px;
        color:#888888;line-height:1.8;text-align:center;">
        Institute of Digital Remediation &nbsp;|&nbsp; Orlando, FL 32801<br>
        <a href="mailto:{sig_email}"
          style="color:#C9A84C;text-decoration:none;">{sig_email}</a>
        &nbsp;|&nbsp;
        <a href="https://idrshield.com"
          style="color:#C9A84C;text-decoration:none;">idrshield.com</a>
      </p>
    </td>
  </tr>

  <!-- BOTTOM GOLD RULE -->
  <tr>
    <td bgcolor="#C9A84C" height="3"
      style="background-color:#C9A84C;height:3px;font-size:0;line-height:0;
             border-radius:0 0 3px 3px;">&nbsp;</td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""



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

def _days_past_deadline():
    """Returns how many days have passed since May 11 2026."""
    from datetime import date
    today = date.today()
    deadline = date(2026, 5, 11)
    return max(0, (today - deadline).days)


def save_to_queue(email_data: dict, auto_send: bool = False) -> bool:
    """Save generated email to queue. Auto-sends if score < 50 and contact email known."""
    if auto_send and email_data.get('idr_score', 100) < 50:
        to_email = email_data.get('contact_email', '')
        if to_email:
            return _send_via_sendgrid(
                to_email=to_email,
                subject=email_data['subject'],
                body_text=email_data['body_text'],
                prospect_id=email_data.get('prospect_id', ''),
                institutional=True,
            )
    return queue_prospect_email(email_data)


def generate_followup_email(outreach_record: dict) -> dict:
    """48-hour follow-up — enforcement is now open."""
    name      = outreach_record.get('prospect_name', 'Healthcare Organization')
    score     = outreach_record.get('idr_score', 0)
    domain    = (outreach_record.get('website') or '').replace('https://','').replace('http://','').rstrip('/')
    days_past = _days_past_deadline()
    subject   = f"Following up: {name} — Enforcement Window Now Open"
    body = f"""Hi,

I wanted to follow up on the accessibility scan results I sent earlier.

The HHS Section 504 enforcement deadline passed on May 11, 2026 — {days_past} days ago. Organizations without a documented compliance record before that date are now in a more difficult position than those that acted proactively.

What this means for {name}: the window to establish a pre-enforcement record has closed. What remains is the ability to demonstrate good faith remediation — which requires documentation, not just intent.

Domain: {domain or name}
Score: {score}/100 — Registry Status: ABSENT

Every day without a documented record is another day of exposure in an active enforcement environment. We can still establish your compliance record. $497. 48-hour delivery.

Hans-Peter Nkansah
Institute of Digital Remediation
hans-peter@instituteofdigitalremediation.org"""
    return {
        'prospect_id': outreach_record.get('prospect_id', ''),
        'prospect_name': name,
        'subject': subject,
        'body_text': body,
        'idr_score': score,
        'criticals': 0,
        'is_followup': True,
    }


def generate_prospect_email(prospect: dict) -> dict:
    """
    Generate personalized outreach — FAIL / WARNING / PASS / NO SCORE.
    Post-deadline enforcement language. No countdown.
    """
    name      = prospect.get('name', 'Healthcare Organization')
    city      = prospect.get('city', '')
    state     = prospect.get('state', '')
    score     = prospect.get('idr_score')
    crits     = prospect.get('critical_count', 0) or prospect.get('criticals', 0) or 0
    otype     = prospect.get('org_type', 'fqhc')
    olane     = prospect.get('org_lane', 'healthcare')
    domain    = (prospect.get('website') or '').replace('https://','').replace('http://','').rstrip('/')
    days_past = _days_past_deadline()

    type_map = {
        'fqhc':   'health center',
        'nh':     'nursing facility',
        'hha':    'home health agency',
        'city':   'city government',
        'county': 'county government',
    }
    org_label = type_map.get(otype, 'healthcare organization')
    location  = f"{city}, {state}" if city and state else (state or '')

    # FAIL: score < 60
    if score is not None and score < 60:
        subject = f"HHS Accessibility Scan: {name} — Score {score}/100 — Registry Status: ABSENT"
        body = f"""Hi,

The HHS Section 504 enforcement deadline passed on May 11, 2026 — {days_past} days ago.

I ran an independent accessibility scan of {name}'s website.

Domain: {domain or name}
Score: {score}/100
Critical violations: {crits}
Registry Status: ABSENT

A score of {score}/100 places {name} in the highest-exposure category. The {crits} critical violation{"s" if crits != 1 else ""} on your site match the violation profile that plaintiff firm automation and HHS OCR investigations target first.

The enforcement window is now open. Every covered entity without a documented audit record is currently exposed. The distinction between organizations that faced OCR action and those that did not often comes down to one thing: whether they had a documented record of awareness and action before a complaint was filed.

We publish independent third-party HHS audit records — SHA-256 timestamped, cryptographically sealed, publicly verifiable. When your Registry status moves from ABSENT to ACTIVE, you have documented proof that your organization was aware and acted.

$497. Delivered within 48 hours.

Search {domain or name} on the IDR Registry at idrshield.com/healthscan. If it says ABSENT, your exposure is documented and public.

Hans-Peter Nkansah
Institute of Digital Remediation
hans-peter@instituteofdigitalremediation.org"""

    # WARNING: score 60-79
    elif score is not None and score < 80:
        subject = f"HHS Compliance Record Missing: {name} — Score {score}/100, Registry ABSENT"
        body = f"""Hi,

I want to make sure you have the complete picture on {name}'s current compliance posture.

Domain: {domain or name}
Score: {score}/100 — WARNING
Registry Status: ABSENT
Enforcement status: Active since May 11, 2026

A score of {score}/100 means your organization has documented accessibility violations with no remediation record on file. The HHS Section 504 enforcement window opened {days_past} days ago.

Here is the legal distinction that matters: under 45 CFR Part 84, willful neglect is defined by the absence of documented remediation effort, not by the presence of violations. An organization with a WARNING score and no Registry record is in the most legally precarious position — visible to enforcement systems, invisible on the compliance registry.

A documented record moves you from exposure to defensibility. The record is what HHS OCR asks for when a complaint is filed. Not the score. The record.

We publish independent third-party HHS audit records. $497. Delivered within 48 hours.

Hans-Peter Nkansah
Institute of Digital Remediation
hans-peter@instituteofdigitalremediation.org"""

    # PASS: score 80+
    elif score is not None and score >= 80:
        subject = f"Registry Alert: {name} Scored {score}/100 — But Registry Status Is ABSENT"
        body = f"""Hi,

{name}'s website scored {score}/100 on our independent HHS accessibility scan. That is a strong technical result.

It does not protect you.

Domain: {domain or name}
Score: {score}/100
Registry Status: ABSENT

Here is the compliance gap that most organizations do not discover until it is too late: HHS OCR does not ask for your scan score when a complaint is filed. They ask for your documented compliance record. A scan score with no audit trail, no SHA-256 timestamp, and no formal remediation documentation provides no legal defense.

The enforcement window opened {days_past} days ago. An organization with an 80/100 score and no Registry ID has the same legal defense position as one with a 40/100 score and no Registry ID: none.

The IDR Public Registry converts your existing compliance posture into a dated, cryptographically sealed, publicly verifiable record. That record is the Good Faith Evidence HHS OCR requires.

$497. Delivered within 48 hours.

Hans-Peter Nkansah
Institute of Digital Remediation
hans-peter@instituteofdigitalremediation.org"""

    # NO SCORE
    else:
        subject = f"HHS Registry Alert: {name} — Registry Status ABSENT"
        body = f"""Hi,

The HHS Section 504 digital accessibility enforcement window opened on May 11, 2026.

Registry Status for {name}: ABSENT

An ABSENT registry status means that if a patient or constituent complaint triggers an HHS OCR investigation, your organization has no documented compliance record on file. No audit trail. No Good Faith Evidence. No defense.

The enforcement window is now active. The organizations that will face the least exposure are not those with perfect websites — they are those with documented records of awareness and action.

We publish independent third-party HHS audit records for {org_label}s nationally. SHA-256 timestamped. Cryptographically sealed. Publicly verifiable.

$497. Delivered within 48 hours.

Run a free scan at idrshield.com/healthscan to see your current violation profile.

Hans-Peter Nkansah
Institute of Digital Remediation
hans-peter@instituteofdigitalremediation.org"""

    return {
        'prospect_id':    prospect.get('id', ''),
        'prospect_name':  name,
        'prospect_type':  otype,
        'prospect_city':  city,
        'prospect_state': state,
        'subject':        subject,
        'body_text':      body,
        'idr_score':      score,
        'critical_count': crits,
        'contact_email':  prospect.get('contact_email', ''),
    }


def generate_association_emails() -> list:
    """Generate pitch emails for all 10 associations, named contacts, HTML-ready."""
    days_past = _days_past_deadline()

    def _body(org, serves, named_person, role, specific_angle):
        return f"""The May 11, 2026 HHS Section 504 digital accessibility deadline is {days_past} days since the May 11 deadline past the May 11 enforcement deadline. {specific_angle}

HHS 89 FR 40066, published July 8, 2024, requires WCAG 2.1 AA compliance for every covered entity website, patient portal, and digital intake tool. For {org} members, this is not a future obligation. It is an active enforcement window opening in {days_past} days since the May 11 deadline.

The risk most organizations do not anticipate is not the violations themselves. It is the absence of documentation. An organization that has a dated, independently verified audit record on file is in a fundamentally stronger position when OCR opens an investigation than one with nothing documented at all.

I would like to offer {org} a member compliance alert, written and delivered within 24 hours at no cost. The piece would explain what the rule requires, which member categories are covered, and what documentation should exist before May 11.

I run the Institute of Digital Remediation. We publish independent third-party HHS accessibility audit records for healthcare organizations nationally. I am not asking for a promotional placement. I am offering factual compliance content that your members need this week.

Would a member alert be useful for your next communication?"""

    return [
        {
            'id': 'nachc',
            'name': 'NACHC, National Association of Community Health Centers',
            'email': 'advocacy@nachc.org',
            'named_email': 'krhee@nachc.org',
            'named_contact': 'Dr. Kyu Rhee',
            'named_title': 'President & CEO, NACHC',
            'subject': 'May 11 HHS Section 504 Deadline, Member Alert Opportunity for Health Centers',
            'salutation': 'NACHC Policy & Advocacy Team',
            'body': _body('NACHC', 'FQHCs', 'Amanda Pears Kelly', 'CEO',
                'FQHCs are explicitly named in HHS 89 FR 40066 as covered entities. Every health center website, patient portal, and digital intake tool is subject to this requirement. Your members are among the most directly exposed organizations in the country, and among those with the most to lose if a complaint triggers OCR with nothing documented.')
        },
        {
            'id': 'nhsa',
            'name': 'NHSA, National Head Start Association',
            'email': 'info@nhsa.org',
            'named_email': 'yvinci@nhsa.org',
            'named_contact': 'Yasmina Vinci',
            'named_title': 'CEO, NHSA',
            'subject': 'May 11 HHS Digital Deadline, Head Start Programs Are Covered',
            'salutation': 'NHSA Communications Team',
            'body': _body('NHSA', 'Head Start programs', 'Yasmina Vinci', 'CEO',
                'Head Start programs receive direct HHS funding and are explicitly covered by the May 11 Section 504 digital accessibility deadline. Most program directors assume this rule applies to hospitals and clinics. It applies equally to every program website, enrollment portal, and digital family resource.')
        },
        {
            'id': 'ahca',
            'name': 'AHCA, American Health Care Association',
            'email': 'info@ahca.org',
            'named_email': 'cporter@ahcancal.org',
            'named_contact': 'Clifton J. Porter II',
            'named_title': 'President & CEO, AHCA/NCAL',
            'subject': 'May 11 HHS Website Accessibility Deadline, Long-Term Care Members',
            'salutation': 'AHCA/NCAL Leadership Team',
            'body': _body('AHCA', 'nursing homes and post-acute facilities', 'Mark Parkinson', 'President & CEO',
                'Nursing homes and post-acute care facilities are covered entities under HHS 89 FR 40066. The enforcement mechanism is complaint-driven, structurally identical to what your members know from CMS oversight. Every member website, online admissions form, and family portal is subject to WCAG 2.1 AA by May 11.')
        },
        {
            'id': 'mgma',
            'name': 'MGMA, Medical Group Management Association',
            'email': 'government.affairs@mgma.com',
            'named_email': 'agilberg@mgma.com',
            'named_contact': 'Anders Gilberg',
            'named_title': 'Senior VP, Government Affairs, MGMA',
            'subject': 'May 11 HHS Deadline, Physician Practice Websites Are Covered',
            'salutation': 'MGMA Government Affairs Team',
            'body': _body('MGMA', 'physician practice administrators', 'Anders Gilberg', 'SVP Government Affairs',
                'Physician practices that accept Medicaid or participate in any HHS-funded program are covered entities under the May 11 HHS Section 504 deadline. This covers their websites, patient portals, and online scheduling systems. MGMA members are the administrators who handle this, and most have not yet been informed their digital presence falls under this requirement.')
        },
        {
            'id': 'nahc',
            'name': 'NAHC, National Association for Home Care & Hospice',
            'email': 'info@nahc.org',
            'named_email': 'wdombi@nahc.org',
            'named_contact': 'William Dombi',
            'named_title': 'President, NAHC',
            'subject': 'May 11 HHS Digital Deadline, Home Health Agencies Are Covered',
            'salutation': 'NAHC Communications Team',
            'body': _body('NAHC', 'home health agencies and hospices', 'William Dombi', 'President',
                'Home health agencies and hospices receiving Medicare or Medicaid funding are covered entities under the May 11 HHS Section 504 deadline. Every agency website, online intake form, and patient-facing digital tool must meet WCAG 2.1 AA. The agencies most at risk are those with no documented audit record when a patient complaint triggers OCR.')
        },
        {
            'id': 'leadingage',
            'name': 'LeadingAge',
            'email': 'info@leadingage.org',
            'named_email': 'ksloan@leadingage.org',
            'named_contact': 'Katie Smith Sloan',
            'named_title': 'President & CEO, LeadingAge',
            'subject': 'May 11 HHS Section 504 Deadline, Non-Profit Aging Services Members',
            'salutation': 'LeadingAge Policy Team',
            'body': _body('LeadingAge', 'non-profit aging services providers', 'Katie Smith Sloan', 'President & CEO',
                'LeadingAge members, nursing homes, assisted living, hospice, and home health, are covered entities under the May 11 HHS Section 504 digital accessibility deadline. Many non-profit aging services organizations have the mission commitment but lack the technical documentation OCR looks for when a complaint is filed.')
        },
        {
            'id': 'ahla',
            'name': 'AHLA, American Health Law Association',
            'email': 'publications@americanhealthlaw.org',
            'named_email': 'publications@americanhealthlaw.org',
            'named_contact': 'Publications Team',
            'named_title': 'American Health Law Association',
            'subject': 'Guest Article: HHS Section 504 Digital Compliance, Healthcare Counsel Alert',
            'salutation': 'AHLA Publications Team',
            'body': f"""The May 11, 2026 HHS Section 504 digital accessibility deadline is {days_past} days since the May 11 deadline past the May 11 enforcement deadline. I would like to submit a guest article for Health Law Daily or The Health Lawyer, framed specifically for healthcare counsel.

The piece is titled "The May 11 HHS Digital Accessibility Deadline: What Covered Entities Need Documented Before Enforcement Opens." It runs approximately 700 words and covers the regulatory basis in HHS 89 FR 40066, the covered entity categories, what constitutes a defensible compliance record in an OCR investigation, and why absence of documentation is more damaging than imperfect compliance.

AHLA members are advising covered organizations right now. The attorneys reading Health Law Daily this week are the same attorneys whose clients will face corrective action plans after May 11 without this guidance.

I run the Institute of Digital Remediation. I can have the full article submitted within 24 hours.

Would this be appropriate for an upcoming issue?"""
        },
        {
            'id': 'ada_dental',
            'name': 'ADA, American Dental Association',
            'email': 'memberservice@ada.org',
            'named_email': 'jada@ada.org',
            'named_contact': 'JADA Editorial Office',
            'named_title': 'Journal of the American Dental Association',
            'subject': 'May 11 HHS Deadline, Dental Practices Accepting Medicaid Are Covered',
            'salutation': 'ADA Practice Resources Team',
            'body': _body('ADA', 'dental practices', 'ADA Practice Resources', 'Team',
                'Dental practices that accept Medicaid are covered entities under the May 11, 2026 HHS Section 504 digital accessibility deadline. This is one of the most consistently overlooked applications of the rule. Every practice website, online scheduling tool, and patient intake form must meet WCAG 2.1 AA. ADA members include hundreds of thousands of practices that have not been informed their digital presence falls under this requirement.')
        },
        {
            'id': 'ahip',
            'name': "AHIP, America's Health Insurance Plans",
            'email': 'media@ahip.org',
            'named_email': 'media@ahip.org',
            'named_contact': 'Communications Team',
            'named_title': "America's Health Insurance Plans",
            'subject': 'May 11 HHS Section 504 Digital Deadline, Health Plan Members',
            'salutation': 'AHIP Communications Team',
            'body': _body('AHIP', 'health insurers and managed care organizations', 'AHIP Team', 'Communications',
                'Health insurers and managed care organizations are covered entities under the May 11 HHS Section 504 digital accessibility deadline. Member portals, plan comparison tools, provider directories, and digital enrollment systems all fall under WCAG 2.1 AA requirements. For health plans, the digital surface area is large and the patient population includes the very individuals the rule was designed to protect.')
        },
        {
            'id': 'jdsupra',
            'name': 'JD Supra, Healthcare Legal Publications',
            'email': 'editorial@jdsupra.com',
            'named_email': 'editorial@jdsupra.com',
            'named_contact': 'Editorial Team',
            'named_title': 'JD Supra',
            'subject': 'Guest Submission: HHS Section 504 Digital Deadline, Healthcare Compliance Alert',
            'salutation': 'JD Supra Editorial Team',
            'body': f"""I would like to submit a guest article for JD Supra's healthcare practice area on the May 11, 2026 HHS Section 504 digital accessibility deadline.

The article is titled "The May 11 HHS Digital Accessibility Deadline: What Healthcare Organizations Need Documented Before Enforcement Opens." It runs approximately 700 words and covers the regulatory basis, which entities are covered, what OCR looks for during an investigation, and what documentation puts an organization in a defensible position.

JD Supra reaches 250,000 legal and compliance professionals. With {days_past} days since the May 11 deadline until enforcement opens, this is directly actionable for your readers today.

I run the Institute of Digital Remediation. We publish independent third-party HHS accessibility audit records for healthcare organizations. I can submit the full article within 24 hours.

Would this be appropriate for your healthcare compliance section?"""
        },
    ]


# ── QUEUE MANAGEMENT ──────────────────────────────────────────────────────────

def queue_prospect_email(email_data: dict) -> bool:
    """Store a generated email in the queue for approval."""
    from database import get_conn
    conn = get_conn()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            # Don't duplicate, check if prospect already queued today
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
    """Pre-populate all 10 association emails, primary + named contact versions."""
    from database import get_conn
    conn = get_conn()
    if not conn: return 0
    added = 0

    # Ensure salutation column exists
    try:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE icc_association_queue
                ADD COLUMN IF NOT EXISTS salutation TEXT DEFAULT 'Team',
                ADD COLUMN IF NOT EXISTS named_contact TEXT,
                ADD COLUMN IF NOT EXISTS named_email TEXT
            """)
    except Exception:
        pass

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
                            (assoc_id, assoc_name, contact_email, subject, body_text,
                             salutation, named_contact, named_email)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (a['id'], a['name'], a['email'], a['subject'], a['body'],
                          a.get('salutation','Team'),
                          a.get('named_contact',''),
                          a.get('named_email','')))
                    added += 1
        print(f'[ICC_QUEUE] {added} association emails queued')
    except Exception as e:
        print(f'[ICC_QUEUE] Assoc queue error: {e}')
    finally:
        conn.close()
    return added






def send_test_email(to_email: str = 'idrshieldhq@gmail.com') -> dict:
    """Send a test HTML email so Hans-Peter can preview the design."""
    subject = "IDR Shield — Email Design Preview"
    body = """This is a preview of how your outreach emails will appear to association directors and healthcare compliance officers.

The design you are seeing was built to communicate authority and professionalism. The dark navy header carries the IDR Shield brand. The gold accent line signals premium positioning. The Georgia serif typeface reads as institutional rather than promotional.

Every association email you approve from the ICC Email Queue will be delivered in this format, sent from hello@idrshield.com via SendGrid.

Here is what a typical paragraph of outreach copy looks like. The May 11, 2026 HHS Section 504 digital accessibility deadline requires WCAG 2.1 AA compliance for every covered entity website, patient portal, and digital intake tool. Organizations without a documented audit record have nothing on file when OCR opens an investigation.

We publish independent third-party HHS accessibility audit records for healthcare organizations nationally.

Activate your audit at idrshield.com/healthcare"""

    try:
        _send_via_sendgrid(
            to_email,
            subject,
            body,
            salutation='Hans-Peter',
            institutional=True
        )
        return {'success': True, 'to': to_email}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def reset_and_reseed_associations():
    """Clear all pending association emails and reseed with latest copy."""
    from database import get_conn
    conn = get_conn()
    if not conn: return 0
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM icc_association_queue WHERE status = 'pending'")
            print('[ICC_QUEUE] Cleared pending association emails')
    except Exception as e:
        print(f'[ICC_QUEUE] Clear error: {e}')
    finally:
        conn.close()
    return queue_association_emails()

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
            # Mark as approved but no email address, needs manual send
            with conn.cursor() as cur:
                cur.execute("UPDATE icc_email_queue SET status='approved', approved_at=NOW() WHERE id=%s", (queue_id,))
            return {'success': True, 'sent': False, 'message': 'Approved, add recipient email to send'}

        _send_via_sendgrid(recipient, subject, body)

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_email_queue
                SET status='sent', approved_at=NOW(), sent_at=NOW()
                WHERE id=%s
            """, (queue_id,))
        _send_confirmation_notification(name, recipient, 'Prospect Outreach')
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
                SELECT assoc_name, contact_email, subject, body_text,
                       COALESCE(salutation,'Team') as salutation
                FROM icc_association_queue WHERE id = %s AND status = 'pending'
            """, (queue_id,))
            row = cur.fetchone()
        if not row:
            return {'success': False, 'error': 'Not found or already sent'}

        name, email, subject, body, salutation = row
        body = edited_body or body

        _send_via_sendgrid(email, subject, body, salutation=salutation, institutional=True)

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_association_queue
                SET status='sent', approved_at=NOW(), sent_at=NOW()
                WHERE id=%s
            """, (queue_id,))
        _send_confirmation_notification(name, email, 'Association Pitch')
        return {'success': True, 'sent': True, 'to': email, 'name': name}

    except Exception as e:
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()





def _body_to_html(text: str) -> str:
    """Convert plain text body to HTML paragraphs."""
    paragraphs = text.strip().split('\n\n')
    html = ''
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        # Bold key phrases
        p = p.replace('May 11, 2026', '<strong>May 11, 2026</strong>')
        p = p.replace('$497', '<strong style="color:#C9A84C;">$497</strong>')
        p = p.replace('WCAG 2.1 AA', '<strong>WCAG 2.1 AA</strong>')
        p = p.replace('HHS OCR', '<strong>HHS OCR</strong>')
        p = p.replace('idrshield.com/healthcare',
            '<a href="https://idrshield.com/healthcare" style="color:#C9A84C;font-weight:700;">idrshield.com/healthcare</a>')
        lines = p.split('\n')
        if len(lines) > 1:
            html += '<p style="margin:0 0 16px;font-family:Georgia,serif;font-size:14px;color:#374151;line-height:1.8;">'
            html += '<br>'.join(lines)
            html += '</p>'
        else:
            html += f'<p style="margin:0 0 16px;font-family:Georgia,serif;font-size:14px;color:#374151;line-height:1.8;">{p}</p>'
    return html


def _build_html_email(salutation: str, body_text: str, subject: str,
                       institutional: bool = False) -> str:
    """Wrap plain text body in the elite HTML template."""
    days_past = _days_past_deadline()
    body_html = _body_to_html(body_text)
    sig_email = FROM_EMAIL_INST if institutional else FROM_EMAIL
    return HTML_EMAIL_TEMPLATE.format(
        subject=subject,
        days_left=days,
        salutation=salutation,
        body_html=body_html,
        sig_email=sig_email,
    )


def _send_via_sendgrid(to_email: str, subject: str, body_text: str,
                        salutation: str = 'Team', institutional: bool = False):
    """Send branded HTML email via SendGrid from hello@idrshield.com."""
    if not SENDGRID_KEY:
        raise Exception('SendGrid key not configured')
    import sendgrid as sg_module
    from sendgrid.helpers.mail import Mail, Email, To, Content
    html_body = _build_html_email(salutation, body_text, subject, institutional=institutional)
    sender_email = FROM_EMAIL_INST if institutional else FROM_EMAIL
    sender_name  = FROM_NAME_INST  if institutional else FROM_NAME
    message = Mail(
        from_email=Email(sender_email, sender_name),
        to_emails=To(to_email),
        subject=subject,
    )
    # Send both plain text and HTML
    message.content = [
        Content('text/plain', body_text),
        Content('text/html', html_body),
    ]
    client = sg_module.SendGridAPIClient(api_key=SENDGRID_KEY)
    response = client.client.mail.send.post(request_body=message.get())
    if response.status_code not in (200, 202):
        raise Exception(f'SendGrid error: {response.status_code}')


def _send_confirmation_notification(recipient_name: str, recipient_email: str,
                                     email_type: str = 'association') -> None:
    """Fire a quick confirmation to idrshieldhq@gmail.com when an email is sent."""
    try:
        from datetime import datetime
        now = datetime.now().strftime('%b %d, %I:%M %p')
        subject = f"✓ Sent: {recipient_name}"
        body = f"""Email delivered successfully.

To: {recipient_name}
Address: {recipient_email}
Type: {email_type}
Time: {now}

Check hans-peter@instituteofdigitalremediation.org for replies.
"""
        import sendgrid as sg_module
        from sendgrid.helpers.mail import Mail, Email, To, Content
        msg = Mail(
            from_email=Email(FROM_EMAIL_INST, 'ICC Notifications'),
            to_emails=To('idrshieldhq@gmail.com'),
            subject=subject,
        )
        msg.content = [Content('text/plain', body)]
        client = sg_module.SendGridAPIClient(api_key=SENDGRID_KEY)
        client.client.mail.send.post(request_body=msg.get())
    except Exception as e:
        print(f'[ICC_NOTIFY] Notification failed (non-critical): {e}')


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
