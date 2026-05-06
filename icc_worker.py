"""
ICC — icc_worker.py
Background worker: harvests prospects, scans websites,
generates messages, sends daily briefing.
Runs inside the existing cron scheduler every hour.
"""

import os
import json
import time
import urllib.request
import urllib.parse
import ssl
from datetime import datetime, timezone

BACKEND_URL  = os.environ.get('RAILWAY_PUBLIC_DOMAIN',
               'https://idr-backend-production.up.railway.app')
SENDGRID_KEY = os.environ.get('SENDGRID_API_KEY', '')
BRIEFING_TO  = os.environ.get('ICC_BRIEFING_EMAIL', 'idrshieldhq@gmail.com')
ANTHROPIC_KEY= os.environ.get('ANTHROPIC_API_KEY', '')

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120',
    'Accept': 'application/json',
}


# ── PROSPECT HARVESTER ────────────────────────────────────────────────────────

def harvest_fqhc(state: str = None, limit: int = 100) -> int:
    """Pull FQHCs from HRSA. Returns count added."""
    from icc_database import upsert_prospect, log_activity
    added = 0
    try:
        page, page_size = 1, 50
        while added < limit:
            url = (f'https://findahealthcenter.hrsa.gov/api/health-centers'
                   f'?pageNumber={page}&pageSize={page_size}&sortBy=name')
            if state:
                url += f'&state={state}'
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=12, context=_ctx) as r:
                data = json.loads(r.read())
            items = (data.get('items') or data.get('data') or
                     data.get('results') or [])
            if not items:
                break
            for item in items:
                if added >= limit:
                    break
                pid = f"FQHC-{item.get('id') or item.get('bhcmisnum') or str(added)}"
                upsert_prospect({
                    'id':       pid,
                    'name':     (item.get('name') or item.get('site_name') or 'Unknown'),
                    'org_type': 'fqhc',
                    'address':  item.get('address') or item.get('street_address',''),
                    'city':     item.get('city',''),
                    'state':    item.get('state') or state or '',
                    'zip':      item.get('zip') or item.get('postal_code',''),
                    'phone':    item.get('phone') or item.get('telephone',''),
                    'website':  item.get('website') or item.get('web_address',''),
                    'source':   'hrsa',
                })
                added += 1
            if len(items) < page_size:
                break
            page += 1
        if added:
            log_activity('prospect_harvested',
                         f'HRSA: {added} FQHCs loaded'
                         + (f' for {state}' if state else ''), added)
    except Exception as e:
        print(f'[ICC_WORKER] HRSA harvest error: {e}')
    return added


def harvest_nursing_homes(state: str = None, limit: int = 100) -> int:
    """Pull nursing homes from CMS."""
    from icc_database import upsert_prospect, log_activity
    added = 0
    try:
        url = (f'https://data.cms.gov/provider-data/api/1/datastore/query'
               f'/4pq5-n9py/0?limit={min(limit,500)}&offset=0')
        if state:
            url += f'&conditions[0][property]=state&conditions[0][value]={state}'
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=15, context=_ctx) as r:
            data = json.loads(r.read())
        for item in (data.get('results') or [])[:limit]:
            pid = f"NH-{item.get('provnum') or item.get('federal_provider_number','UNK')}"
            upsert_prospect({
                'id':       pid,
                'name':     item.get('provname') or item.get('provider_name','Unknown'),
                'org_type': 'nh',
                'address':  item.get('address') or item.get('provider_address',''),
                'city':     item.get('city') or item.get('provider_city',''),
                'state':    item.get('state','') or state or '',
                'zip':      item.get('zip') or item.get('provider_zip_code',''),
                'phone':    item.get('phone') or item.get('provider_phone_number',''),
                'website':  '',
                'source':   'cms_nh',
            })
            added += 1
        if added:
            log_activity('prospect_harvested',
                         f'CMS: {added} nursing homes loaded', added)
    except Exception as e:
        print(f'[ICC_WORKER] CMS NH harvest error: {e}')
    return added


def run_harvest_cycle(states=None, limit_per_state=50):
    """
    Runs every hour. Harvests new prospects from government databases.
    Focuses on states that have fewer than 20 prospects loaded.
    """
    from icc_database import get_icc_stats
    stats = get_icc_stats()
    if stats.get('total', 0) >= 2000:
        print('[ICC_WORKER] Prospect database full (2000+) — skipping harvest')
        return

    target_states = states or [
        'FL','TX','CA','NY','GA','IL','OH','NC','PA','MI',
        'NJ','VA','WA','AZ','MA','TN','IN','MO','MD','WI',
    ]

    total = 0
    for state in target_states[:5]:  # 5 states per cycle to avoid rate limiting
        added = harvest_fqhc(state, limit=limit_per_state)
        total += added
        time.sleep(2)
        added2 = harvest_nursing_homes(state, limit=limit_per_state)
        total += added2
        time.sleep(2)

    print(f'[ICC_WORKER] Harvest cycle complete — {total} prospects added/updated')


# ── WEBSITE SCANNER ───────────────────────────────────────────────────────────

def _build_outreach_msg(name: str, org_type: str, state: str,
                         score: int, criticals: int) -> str:
    """Build a personalized outreach message using real scan data."""
    from datetime import datetime, timezone
    deadline = datetime(2026, 5, 11, tzinfo=timezone.utc)
    days = max(0, (deadline - datetime.now(timezone.utc)).days)

    type_context = {
        'fqhc': ('FQHCs are explicitly named in HHS 89 FR 40066 as covered entities. '
                 'Your federal funding relationship means HHS OCR has direct jurisdiction.'),
        'nh':   ('The Section 504 digital requirement is separate from your CMS/QAPI '
                 'obligations but enforcement is complaint-driven and identical in mechanism.'),
        'hha':  ('Home health agencies receiving Medicare/Medicaid are covered entities '
                 'under the May 11 WCAG 2.1 AA digital accessibility requirement.'),
    }.get(org_type, 'Your organization receives federal health funding and is a covered entity.')

    if score < 60:
        return (
            f'Hi [Name] — I ran an HHS accessibility scan of {name}\'s website '
            f'ahead of the May 11 deadline.\n\n'
            f'Score: {score}/100\nCritical violations: {criticals}\nStatus: FAIL\n\n'
            f'{type_context}\n\n'
            f'The {criticals} critical violation{"s" if criticals!=1 else ""} would be '
            f'cited in an OCR investigation as direct patient access barriers. '
            f'You have {days} days before enforcement opens.\n\n'
            f'We publish third-party HHS audit records — $497, delivered within 48 hours. '
            f'Free full scan at idrshield.com/healthcare.\n\n'
            f'Direct link to activate: https://buy.stripe.com/14A00i4QX9so6UF11q2sM01'
        )
    else:
        return (
            f'Hi [Name] — I work in HHS accessibility compliance. '
            f'The May 11 Section 504 digital deadline applies to {name}. '
            f'{type_context}\n\n'
            f'HHS 89 FR 40066 requires documented WCAG 2.1 AA conformance for your '
            f'website, patient portal, and digital intake tools by May 11. '
            f'Organizations without a documented audit record are exposed '
            f'if a patient complaint triggers an OCR investigation.\n\n'
            f'We publish third-party HHS audit records — $497, 48-hour delivery. '
            f'Free scan at idrshield.com/healthcare. Happy to answer questions — '
            f'no obligation.'
        )


def scan_prospect(prospect: dict) -> bool:
    """Scan a single prospect's website using the IDR scanner."""
    from icc_database import update_prospect_score, log_activity

    pid     = prospect['id']
    name    = prospect['name']
    website = prospect.get('website', '')
    if not website:
        return False
    if not website.startswith('http'):
        website = 'https://' + website

    try:
        payload = json.dumps({'url': website}).encode()
        req = urllib.request.Request(
            f'{BACKEND_URL}/api/scan',
            data=payload,
            headers={**_HEADERS, 'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=20, context=_ctx) as r:
            data = json.loads(r.read())

        score    = (data.get('scan', {}).get('overall_score') or
                    data.get('overall_score') or 0)
        criticals= (data.get('scan', {}).get('critical_count') or
                    data.get('critical_count') or 0)
        msg = _build_outreach_msg(
            name, prospect.get('org_type',''), prospect.get('state',''),
            score, criticals
        )
        update_prospect_score(pid, score, criticals, msg)
        log_activity('scan_complete',
                     f'{name}: {score}/100 ({criticals} critical)'
                     + (' — PRIORITY' if score < 60 else ''))
        print(f'[ICC_WORKER] Scanned {name}: {score}/100')
        return True
    except Exception as e:
        print(f'[ICC_WORKER] Scan error for {name}: {e}')
        return False


def run_scan_cycle(batch_size=8):
    """
    Runs every hour. Scans unscanned prospects with websites.
    Processes in small batches to avoid overwhelming the scanner.
    """
    from icc_database import get_unscanned_with_websites
    prospects = get_unscanned_with_websites(limit=batch_size)
    if not prospects:
        print('[ICC_WORKER] No unscanned prospects with websites')
        return

    print(f'[ICC_WORKER] Scanning {len(prospects)} websites')
    ok = 0
    for p in prospects:
        if scan_prospect(p):
            ok += 1
        time.sleep(3)  # polite gap between scans
    print(f'[ICC_WORKER] Scan cycle complete — {ok}/{len(prospects)} successful')


# ── DAILY BRIEFING ────────────────────────────────────────────────────────────

def send_daily_briefing():
    """Sends a 7am email briefing to Hans-Peter."""
    if not SENDGRID_KEY:
        print('[ICC_WORKER] No SendGrid key — skipping briefing')
        return

    from icc_database import get_icc_stats, get_followups_due, get_associations

    stats    = get_icc_stats()
    followups= get_followups_due()
    assocs   = get_associations()
    not_contacted = [a for a in assocs if a['status'] == 'not_contacted'][:3]

    deadline = datetime(2026, 5, 11, tzinfo=timezone.utc)
    days     = max(0, (deadline - datetime.now(timezone.utc)).days)
    date_str = datetime.now(timezone.utc).strftime('%A, %B %d')

    # Build to-do list with AI
    todos = _generate_daily_todos(stats, followups, not_contacted, days)

    subject = f'ICC Morning Briefing — {date_str} — {days} days to May 11'

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f8f6f2;margin:0;padding:24px 16px;">
<div style="max-width:580px;margin:0 auto;background:#fff;border:1px solid #e8e4dc;">

  <!-- Header -->
  <div style="background:#0A0E1A;padding:20px 28px;border-bottom:3px solid #C9A84C;">
    <div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;
         letter-spacing:.22em;text-transform:uppercase;color:rgba(201,168,76,.55);
         margin-bottom:4px;">ICC · IDR Command Center</div>
    <div style="font-family:Georgia,serif;font-size:18px;color:#FAF7F2;">
      Morning Briefing · {date_str}
    </div>
  </div>

  <!-- Days remaining banner -->
  <div style="background:{'#B8280A' if days<=3 else '#C47F00' if days<=7 else '#1A7A3C'};
       padding:12px 28px;text-align:center;">
    <span style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;
         letter-spacing:.14em;text-transform:uppercase;color:#fff;">
      {days} DAYS TO MAY 11 DEADLINE
    </span>
  </div>

  <!-- Stats row -->
  <div style="padding:20px 28px;border-bottom:1px solid #f0ede8;">
    <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td style="text-align:center;padding:0 8px;">
        <div style="font-family:Georgia,serif;font-size:28px;font-weight:700;
             color:#C9A84C;">{stats.get('total',0)}</div>
        <div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;
             letter-spacing:.14em;text-transform:uppercase;color:#AAAAAA;">Prospects</div>
      </td>
      <td style="text-align:center;padding:0 8px;">
        <div style="font-family:Georgia,serif;font-size:28px;font-weight:700;
             color:#E63946;">{stats.get('priority',0)}</div>
        <div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;
             letter-spacing:.14em;text-transform:uppercase;color:#AAAAAA;">Priority</div>
      </td>
      <td style="text-align:center;padding:0 8px;">
        <div style="font-family:Georgia,serif;font-size:28px;font-weight:700;
             color:#555;">{stats.get('contacted',0)}</div>
        <div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;
             letter-spacing:.14em;text-transform:uppercase;color:#AAAAAA;">Contacted</div>
      </td>
      <td style="text-align:center;padding:0 8px;">
        <div style="font-family:Georgia,serif;font-size:28px;font-weight:700;
             color:#1A7A3C;">{stats.get('converted',0)}</div>
        <div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;
             letter-spacing:.14em;text-transform:uppercase;color:#AAAAAA;">Converted</div>
      </td>
      <td style="text-align:center;padding:0 8px;">
        <div style="font-family:Georgia,serif;font-size:28px;font-weight:700;
             color:#1A7A3C;">${stats.get('revenue',0):,}</div>
        <div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;
             letter-spacing:.14em;text-transform:uppercase;color:#AAAAAA;">Revenue</div>
      </td>
    </tr>
    </table>
  </div>

  <!-- Today's to-do -->
  <div style="padding:20px 28px;border-bottom:1px solid #f0ede8;">
    <div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;
         letter-spacing:.2em;text-transform:uppercase;color:#C9A84C;margin-bottom:12px;">
      Your Tasks For Today
    </div>
    {todos}
  </div>

  <!-- Follow-ups due -->
  {'<div style="padding:20px 28px;border-bottom:1px solid #f0ede8;background:#FDF8F0;"><div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:#C47F00;margin-bottom:10px;">Follow-Ups Due (' + str(len(followups)) + ')</div>' + ''.join([f'<div style="font-size:12px;color:#555;padding:5px 0;border-bottom:1px solid #f0e8d8;">{f["prospect_name"]} — contacted {f["sent_at"].strftime("%b %d") if f.get("sent_at") else "recently"}</div>' for f in followups[:5]]) + '</div>' if followups else ''}

  <!-- Association opportunities -->
  {'<div style="padding:20px 28px;border-bottom:1px solid #f0ede8;"><div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Associations Not Yet Contacted</div>' + ''.join([f'<div style="font-size:12px;color:#555;padding:4px 0;">{a["name"].split("—")[0].strip()} — {a["member_count"]} members</div>' for a in not_contacted]) + '</div>' if not_contacted else ''}

  <!-- CTA -->
  <div style="padding:20px 28px;text-align:center;">
    <a href="https://idrshield.com/icc"
       style="display:inline-block;background:#C9A84C;color:#0A0E1A;
              font-family:Arial,sans-serif;font-size:9px;font-weight:700;
              letter-spacing:.16em;text-transform:uppercase;
              padding:13px 32px;text-decoration:none;">
      Open ICC Command Center →
    </a>
  </div>

  <div style="padding:14px 28px;background:#0A0E1A;">
    <div style="font-family:Arial,sans-serif;font-size:8px;color:rgba(250,247,242,.25);">
      ICC · IDR Command Center · idrshield.com · Automated morning briefing
    </div>
  </div>

</div>
</body></html>"""

    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        msg = Mail(
            from_email=('hello@idrshield.com',
                        'ICC — IDR Command Center'),
            to_emails=BRIEFING_TO,
            subject=subject,
            html_content=html,
        )
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_KEY)
        r  = sg.client.mail.send.post(request_body=msg.get())
        print(f'[ICC_WORKER] Daily briefing sent to {BRIEFING_TO} — {r.status_code}')
        from icc_database import log_activity
        log_activity('briefing_sent', f'Morning briefing — {days} days left')
    except Exception as e:
        print(f'[ICC_WORKER] Briefing error: {e}')


def _generate_daily_todos(stats, followups, not_contacted, days):
    """Generate today's to-do list using Claude AI."""
    if not ANTHROPIC_KEY:
        # Fallback static todos
        items = []
        if stats.get('priority', 0) > 0:
            items.append(f'Contact {min(stats["priority"],10)} priority prospects (score below 60) — messages are pre-written in ICC')
        if followups:
            items.append(f'Send follow-ups to {len(followups)} contacts who haven\'t responded in 3+ days')
        if not_contacted:
            items.append(f'Pitch {not_contacted[0]["name"].split("—")[0].strip()} — {not_contacted[0]["member_count"]} members waiting')
        items.append(f'Post LinkedIn content about the {days}-day deadline')
        items.append('Run ICC scanner on 20 more healthcare websites')
        return ''.join([f'<div style="font-size:13px;color:#333;padding:6px 0;border-bottom:1px solid #f0ede8;padding-left:16px;position:relative;"><span style="position:absolute;left:0;color:#C9A84C;">→</span>{item}</div>' for item in items])

    try:
        prompt = f"""You are the ICC AI advisor for IDR Shield, an HHS healthcare accessibility compliance company. 
Generate exactly 5 specific action items for today based on this campaign data:
- Days to May 11 deadline: {days}
- Total prospects in database: {stats.get('total',0)}
- Priority prospects (score<60): {stats.get('priority',0)}
- Contacted so far: {stats.get('contacted',0)}
- Converted to clients: {stats.get('converted',0)}
- Revenue: ${stats.get('revenue',0):,}
- Follow-ups due: {len(followups)}
- Associations not yet contacted: {len(not_contacted)}

Return ONLY a JSON array of 5 strings, each a specific action item. No other text."""

        payload = json.dumps({
            'model': 'claude-sonnet-4-6',
            'max_tokens': 400,
            'messages': [{'role': 'user', 'content': prompt}]
        }).encode()
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={
                'x-api-key': ANTHROPIC_KEY,
                'anthropic-version': '2023-06-01',
                'Content-Type': 'application/json',
            },
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
        text  = data['content'][0]['text'].strip()
        clean = text.replace('```json','').replace('```','').strip()
        items = json.loads(clean)
        return ''.join([
            f'<div style="font-size:13px;color:#333;padding:6px 0;'
            f'border-bottom:1px solid #f0ede8;padding-left:16px;position:relative;">'
            f'<span style="position:absolute;left:0;color:#C9A84C;">→</span>{item}</div>'
            for item in items
        ])
    except Exception as e:
        print(f'[ICC_WORKER] AI todo error: {e}')
        return '<div style="font-size:12px;color:#888;padding:8px 0;">Open ICC to see today\'s priorities.</div>'


# ── MAIN CYCLE ────────────────────────────────────────────────────────────────

def run_icc_cycle():
    """
    Main ICC worker cycle. Called every hour by the cron scheduler.
    1. Harvest new prospects from government databases
    2. Scan unscanned websites
    3. Send daily briefing at 7am
    """
    now = datetime.now(timezone.utc)
    print(f'[ICC_WORKER] Cycle starting at {now.isoformat()}')

    # Always scan - this is the most valuable hourly task
    run_scan_cycle(batch_size=8)

    # Harvest every 6 hours (not every hour - government APIs are rate sensitive)
    if now.hour % 6 == 0:
        run_harvest_cycle(limit_per_state=50)

    # Daily briefing at 11am UTC = 7am EDT (Orlando)
    if now.hour == 11 and now.minute < 60:
        send_daily_briefing()

    print('[ICC_WORKER] Cycle complete')
