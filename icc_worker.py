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
    """Sends a real intelligence briefing — pulls from actual DB tables."""
    if not SENDGRID_KEY:
        print('[ICC_WORKER] No SendGrid key — skipping briefing')
        return

    from icc_database import (get_icc_stats, get_scanned_prospects,
                               get_warm_leads, get_associations, log_activity)
    from datetime import date as _date
    _today = _date.today()
    _dl    = _date(2026, 5, 11)
    days   = max(0, (_dl - _today).days)
    stats  = get_icc_stats()
    if not stats:
        print('[ICC_WORKER] No stats — skipping briefing')
        return

    scanned    = get_scanned_prospects(limit=100)
    warm_leads = get_warm_leads()
    assocs     = get_associations()
    associations_warm    = [a for a in assocs if a.get('status') in ('opened','replied','in_conversation')]
    associations_not_yet = [a for a in assocs if a.get('status') == 'not_contacted']
    fail_scores  = [p for p in scanned if (p.get('idr_score') or 101) < 60]
    warn_scores  = [p for p in scanned if 60 <= (p.get('idr_score') or 101) < 80]
    pass_scores  = [p for p in scanned if (p.get('idr_score') or 0) >= 80]

    def sc(s):
        if s is None: return '#64748B'
        if s < 60: return '#DC2626'
        if s < 80: return '#D97706'
        return '#059669'

    # Build sections as strings
    warm_section = ''
    if warm_leads:
        rows = ''
        for lead in warm_leads[:5]:
            s = lead.get('idr_score')
            ph = ('<div style="font-size:11px;color:#374151;">&#128222; ' +
                  lead.get('phone','') + '</div>') if lead.get('phone') else ''
            rows += ('<div style="border-left:3px solid #C9A84C;padding:10px 14px;'
                     'margin-bottom:8px;background:#FFFBEB;">'
                     '<div style="font-size:14px;font-weight:700;color:#0F1E2E;">' +
                     lead.get('name','') + '</div>'
                     '<div style="font-size:11px;color:#64748B;">Score: <b style="color:' +
                     sc(s) + '">' + str(s) + '/100</b> &nbsp;|&nbsp; ' +
                     lead.get('status','').upper() + '</div>' + ph +
                     '<div style="font-size:11px;color:#C9A84C;">&#8594; Follow up immediately</div>'
                     '</div>')
        warm_section = ('<p style="font-size:10px;letter-spacing:0.12em;color:#C9A84C;'
                        'text-transform:uppercase;margin:20px 0 8px;">WARM LEADS — ACT TODAY</p>' + rows)

    fail_section = ''
    if fail_scores:
        rows = ''
        for p in fail_scores[:8]:
            s = p.get('idr_score', 0)
            ph = ('<div style="font-size:11px;color:#374151;">&#128222; ' +
                  p.get('phone','') + '</div>') if p.get('phone') else ''
            rows += ('<div style="border-left:3px solid #DC2626;padding:8px 14px;'
                     'margin-bottom:6px;background:#FEF2F2;">'
                     '<div style="font-size:13px;font-weight:700;color:#0F1E2E;">' +
                     p.get('name','') + '</div>'
                     '<div style="font-size:11px;color:#64748B;">' +
                     p.get('city','') + ', ' + p.get('state','') +
                     ' &nbsp;|&nbsp; Score: <b style="color:#DC2626">' +
                     str(s) + '/100</b> &nbsp;|&nbsp; ' +
                     str(p.get('critical_count',0)) + ' critical</div>' + ph + '</div>')
        fail_section = ('<p style="font-size:10px;letter-spacing:0.12em;color:#DC2626;'
                        'text-transform:uppercase;margin:20px 0 8px;">PRIORITY — SCORE BELOW 60</p>' + rows)

    scan_section = ''
    if scanned:
        scan_section = ('<p style="font-size:10px;letter-spacing:0.12em;color:#C9A84C;'
                        'text-transform:uppercase;margin:20px 0 8px;">' +
                        str(len(scanned)) + ' ORGANIZATIONS SCANNED</p>'
                        '<table width="100%" cellpadding="0" cellspacing="8" style="margin-bottom:16px;"><tr>'
                        '<td align="center" style="background:#FEF2F2;padding:10px;border-radius:4px;">'
                        '<div style="font-size:28px;font-weight:700;color:#DC2626;">' + str(len(fail_scores)) + '</div>'
                        '<div style="font-size:9px;color:#DC2626;text-transform:uppercase;">FAIL</div></td>'
                        '<td align="center" style="background:#FFFBEB;padding:10px;border-radius:4px;">'
                        '<div style="font-size:28px;font-weight:700;color:#D97706;">' + str(len(warn_scores)) + '</div>'
                        '<div style="font-size:9px;color:#D97706;text-transform:uppercase;">WARNING</div></td>'
                        '<td align="center" style="background:#F0FDF4;padding:10px;border-radius:4px;">'
                        '<div style="font-size:28px;font-weight:700;color:#059669;">' + str(len(pass_scores)) + '</div>'
                        '<div style="font-size:9px;color:#059669;text-transform:uppercase;">PASS</div></td>'
                        '</tr></table>')

    assoc_section = ''
    if associations_warm:
        rows = ''
        for a in associations_warm:
            rows += ('<div style="padding:8px 14px;border-left:3px solid #C9A84C;'
                     'margin-bottom:6px;background:#FFFBEB;font-size:12px;color:#0F1E2E;">'
                     '<b>' + a.get('name','') + '</b> — ' + a.get('status','').upper() +
                     '<br><span style="color:#64748B;">' + a.get('member_count','') + ' members</span></div>')
        assoc_section += ('<p style="font-size:10px;letter-spacing:0.12em;color:#C9A84C;'
                          'text-transform:uppercase;margin:16px 0 8px;">ASSOCIATIONS — HOT</p>' + rows)
    if associations_not_yet:
        rows = ''
        for a in associations_not_yet[:5]:
            rows += ('<div style="padding:6px 14px;font-size:11px;color:#64748B;'
                     'border-bottom:1px solid #F3F4F6;">' +
                     a.get('name','') + ' — ' + a.get('member_count','') + ' members</div>')
        assoc_section += ('<p style="font-size:10px;letter-spacing:0.12em;color:#94A3B8;'
                          'text-transform:uppercase;margin:16px 0 8px;">NOT YET CONTACTED</p>' + rows)

    # Specific todos based on real data
    todos = []
    if warm_leads:
        top = warm_leads[0]
        todos.append('<b>CALL NOW:</b> ' + top.get('name','') +
                     ' is a warm lead. Phone: ' + top.get('phone','find on website') +
                     '. Opening: "I saw you reviewed our HHS scan — wanted to connect before May 11."')
    if fail_scores:
        top = fail_scores[0]
        todos.append('<b>HIGH PRIORITY:</b> ' + top.get('name','') + ' scored ' +
                     str(top.get('idr_score','')) + '/100. Email auto-queued. Call: ' +
                     top.get('phone','find contact on their website'))
    if len(scanned) < 30:
        todos.append('<b>SCAN MORE:</b> Only ' + str(len(scanned)) + ' prospects scanned. '
                     'Open ICC Prospects tab and scan 15 more today. Every FAIL score = sales call.')
    if associations_not_yet:
        todos.append('<b>ASSOCIATIONS:</b> ' + str(len(associations_not_yet)) +
                     ' not yet contacted. Follow up on sent emails via Namecheap inbox.')
    if not todos:
        todos.append('<b>APPROVE EMAILS:</b> Open ICC Email Queue and approve all pending outreach.')
        todos.append('<b>LINKEDIN:</b> Post today\'s Observatory data from scan results above.')

    todos_html = ''.join(
        '<div style="padding:10px 14px;border-left:3px solid #C9A84C;margin-bottom:8px;'
        'font-size:12px;color:#1E293B;background:#FAFAF8;">' + t + '</div>'
        for t in todos)

    deadline_color = '#DC2626' if days <= 2 else ('#D97706' if days <= 5 else '#C9A84C')
    if days == 0:
        days_label = 'DEADLINE PASSED — ENFORCEMENT IS OPEN'
    else:
        days_label = str(days) + ' DAYS TO MAY 11 DEADLINE'

    rev = stats.get('revenue', 0)
    subject = ('ICC Briefing — ' + _today.strftime('%a %b %d') + ' — ' +
               days_label + ' — ' + str(len(fail_scores)) + ' FAIL · ' +
               str(len(warn_scores)) + ' WARNING · $' + str(rev) + ' revenue')

    html = ('<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
            '<body style="margin:0;padding:0;font-family:Georgia,serif;background:#F0EDE6;">'
            '<table width="100%" cellpadding="0" cellspacing="0" style="background:#F0EDE6;padding:32px 0;">'
            '<tr><td align="center">'
            '<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">'
            '<tr><td style="background:#0F1E2E;padding:24px 32px;">'
            '<p style="margin:0 0 2px;font-size:9px;letter-spacing:0.2em;color:#C9A84C;text-transform:uppercase;">ICC &middot; IDR Command Center</p>'
            '<p style="margin:0;font-size:22px;font-weight:700;color:#F0E8D8;">Morning Briefing &middot; ' + _today.strftime('%A, %B %d') + '</p>'
            '</td></tr>'
            '<tr><td style="background:' + deadline_color + ';padding:12px 32px;text-align:center;">'
            '<p style="margin:0;font-size:12px;font-weight:700;color:#FFFFFF;letter-spacing:0.15em;text-transform:uppercase;">' + days_label + '</p>'
            '</td></tr>'
            '<tr><td style="background:#FFFFFF;padding:24px 32px;">'
            '<table width="100%" cellpadding="0" cellspacing="0"><tr>'
            '<td align="center" style="padding:8px;">'
            '<div style="font-size:32px;font-weight:700;color:#C9A84C;">' + str(stats.get('total',0)) + '</div>'
            '<div style="font-size:9px;letter-spacing:0.1em;color:#94A3B8;text-transform:uppercase;">Prospects</div></td>'
            '<td align="center" style="padding:8px;">'
            '<div style="font-size:32px;font-weight:700;color:#DC2626;">' + str(stats.get('priority',0)) + '</div>'
            '<div style="font-size:9px;letter-spacing:0.1em;color:#94A3B8;text-transform:uppercase;">Priority</div></td>'
            '<td align="center" style="padding:8px;">'
            '<div style="font-size:32px;font-weight:700;color:#374151;">' + str(stats.get('contacted',0)) + '</div>'
            '<div style="font-size:9px;letter-spacing:0.1em;color:#94A3B8;text-transform:uppercase;">Contacted</div></td>'
            '<td align="center" style="padding:8px;">'
            '<div style="font-size:32px;font-weight:700;color:#059669;">' + str(stats.get('warm',0)) + '</div>'
            '<div style="font-size:9px;letter-spacing:0.1em;color:#94A3B8;text-transform:uppercase;">Warm</div></td>'
            '<td align="center" style="padding:8px;">'
            '<div style="font-size:32px;font-weight:700;color:#059669;">$' + str(rev) + '</div>'
            '<div style="font-size:9px;letter-spacing:0.1em;color:#94A3B8;text-transform:uppercase;">Revenue</div></td>'
            '</tr></table></td></tr>'
            '<tr><td style="background:#FFFFFF;padding:0 32px 24px;">'
            '<p style="font-size:10px;letter-spacing:0.12em;color:#C9A84C;text-transform:uppercase;margin:16px 0 8px;">YOUR ACTIONS TODAY</p>'
            + todos_html + warm_section + fail_section + scan_section + assoc_section +
            '<div style="text-align:center;margin:24px 0 8px;">'
            '<a href="https://idrshield.com/icc.html" '
            'style="background:#C9A84C;color:#0F1E2E;font-size:11px;font-weight:700;'
            'letter-spacing:0.12em;text-transform:uppercase;padding:12px 32px;text-decoration:none;display:inline-block;">'
            'OPEN ICC COMMAND CENTER &#8594;</a></div>'
            '</td></tr>'
            '<tr><td style="background:#1a2435;padding:16px 32px;text-align:center;">'
            '<p style="margin:0;font-size:10px;color:#64748B;">ICC &middot; IDR Command Center &middot; idrshield.com</p>'
            '</td></tr>'
            '</table></td></tr></table></body></html>')

    try:
        import sendgrid as sg_mod
        from sendgrid.helpers.mail import Mail, Email, To, Content
        msg = Mail(
            from_email=Email('hello@idrshield.com', 'ICC — IDR Command Center'),
            to_emails=To(BRIEFING_TO),
            subject=subject,
        )
        msg.content = [Content('text/html', html)]
        client = sg_mod.SendGridAPIClient(api_key=SENDGRID_KEY)
        r = client.client.mail.send.post(request_body=msg.get())
        print(f'[ICC_WORKER] Briefing sent — {r.status_code}')
        log_activity('briefing_sent',
                     f'Briefing — {days} days left — {len(fail_scores)} FAIL — {len(warm_leads)} warm')
    except Exception as e:
        print(f'[ICC_WORKER] Briefing send error: {e}')



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
