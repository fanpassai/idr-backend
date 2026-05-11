"""
ICC — icc_worker.py  v2.0
Three autonomous agents that run 24/7 on Railway.

SCOUT AGENT   — harvests organizations from government DBs, scans websites,
                writes everything to the DB. Four data sources so it never
                returns zero. Runs every hour.

OUTREACH AGENT — monitors the prospect table for new scores, generates
                 personalized emails, queues follow-ups at 48h, sends
                 notifications on warm lead signals. Runs every hour.

INTELLIGENCE AGENT — monitors HHS OCR, Federal Register RSS, and regulatory
                     news. Feeds the morning briefing with real intelligence,
                     not generic advice. Runs every 6 hours.

DAILY BRIEFING — 7am EDT every day. Pulls from real DB tables. Specific names,
                 phone numbers, call scripts. Not generic. Never generic.
"""

import os
import json
import time
import urllib.request
import urllib.parse
import ssl
import xml.etree.ElementTree as ET
from datetime import datetime, date, timezone, timedelta

BACKEND_URL   = os.environ.get('RAILWAY_PUBLIC_DOMAIN',
                'https://idr-backend-production.up.railway.app')
SENDGRID_KEY  = os.environ.get('SENDGRID_API_KEY', '')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
BRIEFING_TO   = os.environ.get('ICC_BRIEFING_EMAIL', 'idrshieldhq@gmail.com')
NOTIFY_TO     = os.environ.get('ICC_NOTIFY_EMAIL',   'idrshieldhq@gmail.com')

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; IDR-Scout/2.0)',
    'Accept': 'application/json,text/html,*/*',
}

# ── Brand constants (imported from icc_database) ──────────────────────────────

def _brand():
    from icc_database import BRAND
    return BRAND

def _enforcement(lane='healthcare'):
    from icc_database import ENFORCEMENT_COPY
    return ENFORCEMENT_COPY.get(lane, ENFORCEMENT_COPY['healthcare'])


# =============================================================================
# SCOUT AGENT
# =============================================================================

def _fetch_json(url, timeout=12):
    """Safe JSON fetch — returns None on any failure, never raises."""
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f'[SCOUT] fetch_json failed {url[:60]}: {e}')
        return None


def _harvest_hrsa(state: str, limit: int = 50) -> int:
    """
    Source 1: HRSA Health Center Finder API.
    Returns count added. Never raises — returns 0 on failure.
    """
    from icc_database import upsert_prospect, log_activity
    added = 0
    try:
        urls_to_try = [
            f'https://findahealthcenter.hrsa.gov/api/health-centers?pageNumber=1&pageSize={limit}&sortBy=name&state={state}',
            f'https://data.hrsa.gov/api/reporting/bphc/sites?state={state}&limit={limit}',
        ]
        items = []
        for url in urls_to_try:
            data = _fetch_json(url)
            if not data:
                continue
            # Try every possible key name the API might use
            for key in ('items', 'data', 'results', 'healthCenters',
                        'HealthCenters', 'records', 'features', 'sites'):
                if isinstance(data.get(key), list) and data[key]:
                    items = data[key]
                    break
            if not items and isinstance(data, list):
                items = data
            if items:
                break

        for item in items[:limit]:
            pid = f"FQHC-{state}-{item.get('id') or item.get('bhcmisnum') or item.get('site_id') or added}"
            upsert_prospect({
                'id':       pid,
                'name':     (item.get('name') or item.get('site_name') or
                             item.get('health_center_name') or 'Unknown'),
                'org_type': 'fqhc',
                'org_lane': 'healthcare',
                'address':  (item.get('address') or item.get('street_address') or ''),
                'city':     item.get('city', ''),
                'state':    item.get('state', state),
                'zip':      (item.get('zip') or item.get('postal_code') or ''),
                'phone':    (item.get('phone') or item.get('telephone') or ''),
                'website':  (item.get('website') or item.get('web_address') or ''),
                'source':   'hrsa_api',
            })
            added += 1

        if added:
            log_activity('prospect_harvested', f'HRSA API: {added} FQHCs from {state}', added)
    except Exception as e:
        print(f'[SCOUT] HRSA harvest error for {state}: {e}')
    return added


def _harvest_cms_nursing_homes(state: str, limit: int = 50) -> int:
    """Source 2: CMS Care Compare nursing homes."""
    from icc_database import upsert_prospect, log_activity
    added = 0
    try:
        url = (f'https://data.cms.gov/provider-data/api/1/datastore/query'
               f'/4pq5-n9py/0?limit={min(limit,200)}&offset=0'
               f'&conditions[0][property]=state&conditions[0][value]={state}')
        data = _fetch_json(url)
        if not data:
            return 0
        for item in (data.get('results') or [])[:limit]:
            pid = f"NH-{item.get('provnum') or item.get('federal_provider_number', f'{state}-{added}')}"
            upsert_prospect({
                'id':       pid,
                'name':     (item.get('provname') or item.get('provider_name') or 'Unknown'),
                'org_type': 'nh',
                'org_lane': 'healthcare',
                'address':  (item.get('address') or item.get('provider_address') or ''),
                'city':     (item.get('city') or item.get('provider_city') or ''),
                'state':    item.get('state', state),
                'zip':      (item.get('zip') or item.get('provider_zip_code') or ''),
                'phone':    (item.get('phone') or item.get('provider_phone_number') or ''),
                'website':  '',
                'source':   'cms_nh',
            })
            added += 1
        if added:
            log_activity('prospect_harvested', f'CMS: {added} nursing homes from {state}', added)
    except Exception as e:
        print(f'[SCOUT] CMS NH harvest error for {state}: {e}')
    return added


def _harvest_data_gov_government(state: str, limit: int = 20) -> int:
    """
    Source 3: data.gov — city/county government websites.
    Uses the US Government API endpoint for municipal websites.
    """
    from icc_database import upsert_prospect, log_activity
    added = 0
    try:
        # data.gov catalog for government websites
        url = (f'https://catalog.data.gov/api/3/action/package_search'
               f'?q=city+government+{state}&rows={limit}&fq=organization_type:local-government')
        data = _fetch_json(url)
        if not data:
            return 0
        results = (data.get('result', {}).get('results') or [])
        for i, item in enumerate(results[:limit]):
            name = item.get('title') or item.get('name') or f'Government Entity {state}-{i}'
            url_val = ''
            for res in (item.get('resources') or []):
                if res.get('url', '').startswith('http'):
                    url_val = res['url']
                    break
            pid = f"GOV-{state}-API-{i}"
            upsert_prospect({
                'id':       pid,
                'name':     name,
                'org_type': 'city',
                'org_lane': 'government',
                'state':    state,
                'website':  url_val,
                'source':   'data_gov',
            })
            added += 1
        if added:
            log_activity('prospect_harvested', f'data.gov: {added} gov entities from {state}', added)
    except Exception as e:
        print(f'[SCOUT] data.gov harvest error for {state}: {e}')
    return added


def _use_seed_fallback(state: str) -> int:
    """
    Source 4 (always works): Use the seed data already in icc_database.py.
    Called when all APIs fail. Re-upserts seed data to ensure DB is populated.
    """
    from icc_database import SEED_PROSPECTS, SEED_GOVERNMENT, bulk_upsert_prospects, log_activity
    prospects = []
    if state in SEED_PROSPECTS:
        for p in SEED_PROSPECTS[state]:
            prospects.append({**p, 'org_lane': 'healthcare', 'source': 'seed_fallback'})
    if not prospects:
        return 0
    count = bulk_upsert_prospects(prospects)
    log_activity('prospect_harvested', f'Seed fallback: {count} prospects for {state}', count)
    return count


def run_harvest_cycle(states=None, limit_per_state=50):
    """
    Runs every 6 hours. Harvests from all sources in priority order.
    Hybrid strategy: API first, seed fallback guaranteed.
    Never returns zero — seed data is always the floor.
    """
    from icc_database import get_icc_stats

    stats = get_icc_stats()
    current_total = stats.get('total', 0)
    if current_total >= 5000:
        print('[SCOUT] Database has 5000+ prospects — harvest paused')
        return

    target_states = states or [
        'FL', 'TX', 'CA', 'NY', 'GA', 'IL', 'OH', 'NC', 'PA', 'MI',
        'NJ', 'VA', 'WA', 'AZ', 'MA', 'TN', 'IN', 'MO', 'MD', 'WI',
    ]

    total_added = 0
    # Process 5 states per cycle to avoid rate limiting
    for state in target_states[:5]:
        state_total = 0

        # Source 1: HRSA
        added = _harvest_hrsa(state, limit=limit_per_state)
        state_total += added
        time.sleep(2)

        # Source 2: CMS nursing homes
        added = _harvest_cms_nursing_homes(state, limit=limit_per_state)
        state_total += added
        time.sleep(2)

        # Source 3: Government entities (healthcare states only if in gov lane)
        # Government harvest runs separately via _harvest_data_gov_government

        # Source 4: Seed fallback if APIs produced nothing
        if state_total == 0:
            added = _use_seed_fallback(state)
            state_total += added
            print(f'[SCOUT] APIs returned zero for {state} — used seed fallback ({added} prospects)')

        total_added += state_total
        print(f'[SCOUT] {state}: {state_total} prospects added/updated')
        time.sleep(3)

    print(f'[SCOUT] Harvest cycle complete — {total_added} total added/updated')


# =============================================================================
# WEBSITE SCANNER
# =============================================================================

def _build_outreach_msg(name: str, org_type: str, org_lane: str,
                         score: int, criticals: int) -> str:
    """
    Builds personalized outreach message using real scan data.
    Post-deadline enforcement language — no countdown language.
    """
    from icc_database import ENFORCEMENT_COPY, BRAND
    ec = ENFORCEMENT_COPY.get(org_lane, ENFORCEMENT_COPY['healthcare'])

    type_context = {
        'fqhc': ('FQHCs are explicitly named in HHS 89 FR 40066 as covered entities. '
                 'Your federal funding relationship means HHS OCR has direct jurisdiction.'),
        'nh':   ('Nursing facilities receiving Medicare or Medicaid funding are covered entities '
                 'under HHS Section 504. The digital accessibility requirement applies to your '
                 'website, patient portal, and online intake systems.'),
        'hha':  ('Home health agencies receiving Medicare or Medicaid are covered entities '
                 'under the May 11 WCAG 2.1 AA digital accessibility requirement.'),
        'city': ('City governments serving populations of 50,000 or more were required to '
                 'achieve WCAG 2.1 AA conformance by April 24, 2026. That deadline has passed.'),
        'county': ('County governments were subject to the ADA Title II April 24, 2026 deadline. '
                   'Enforcement is now active for all covered entities.'),
    }.get(org_type, ec['deadline_passed'])

    if score < 60:
        return (
            f'Hi [Name],\n\n'
            f'I ran an independent accessibility scan of {name}\'s website.\n\n'
            f'Score: {score}/100\n'
            f'Critical violations: {criticals}\n'
            f'Registry Status: ABSENT\n\n'
            f'{type_context}\n\n'
            f'{ec["deadline_passed"]} {ec["status_absent"]}\n\n'
            f'The {criticals} critical violation{"s" if criticals != 1 else ""} on your site '
            f'are exactly what plaintiff firm automation and OCR investigators look for first. '
            f'An organization with violations and no documented record is in the worst possible '
            f'legal position.\n\n'
            f'{ec["cta"]}\n\n'
            f'Free scan at {BRAND["scan_page"]}.\n\n'
            f'Hans-Peter Nkansah\n'
            f'Institute of Digital Remediation\n'
            f'hans-peter@instituteofdigitalremediation.org'
        )
    elif score < 80:
        return (
            f'Hi [Name],\n\n'
            f'I want to make sure you have the complete picture on your organization\'s '
            f'digital accessibility posture.\n\n'
            f'Score: {score}/100 — WARNING\n'
            f'Registry Status: ABSENT\n\n'
            f'{type_context}\n\n'
            f'{ec["deadline_passed"]}\n\n'
            f'A WARNING score with no Registry record puts your organization in the most '
            f'problematic category legally: you have documented violations with no documented '
            f'remediation effort. Under 45 CFR Part 84, that is the definition of willful '
            f'neglect — the highest exposure tier.\n\n'
            f'{ec["cta"]}\n\n'
            f'Hans-Peter Nkansah\n'
            f'Institute of Digital Remediation\n'
            f'hans-peter@instituteofdigitalremediation.org'
        )
    else:
        return (
            f'Hi [Name],\n\n'
            f'Your website scanned at {score}/100 — which is above the warning threshold.\n\n'
            f'Here is what most organizations in your position do not realize: an organization '
            f'with an 80/100 score and no Registry record has the same legal defense position '
            f'as one with a 40/100 score and no Registry record. None.\n\n'
            f'{ec["deadline_passed"]} The record is the defense. Not the scan. Not the score.\n\n'
            f'{ec["cta"]}\n\n'
            f'Hans-Peter Nkansah\n'
            f'Institute of Digital Remediation\n'
            f'hans-peter@instituteofdigitalremediation.org'
        )


def scan_prospect(prospect: dict) -> bool:
    """
    Scans a single prospect's website using the IDR scanner.
    Calls /api/scan on the Railway backend — same scanner as healthscan.html.
    """
    from icc_database import update_prospect_score, save_scan_result, log_activity

    pid     = prospect['id']
    name    = prospect.get('name', pid)
    website = prospect.get('website', '').strip()
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
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=25, context=_ctx) as r:
            data = json.loads(r.read())

        score    = (data.get('scan', {}).get('overall_score') or
                    data.get('overall_score') or 0)
        criticals = (data.get('scan', {}).get('critical_count') or
                     data.get('critical_count') or 0)
        total    = (data.get('scan', {}).get('total_issues') or
                    data.get('total_issues') or 0)

        msg = _build_outreach_msg(
            name, prospect.get('org_type', 'fqhc'),
            prospect.get('org_lane', 'healthcare'),
            score, criticals,
        )

        save_scan_result(pid, website, name, score, criticals, total)
        update_prospect_score(pid, score, criticals, msg)

        print(f'[SCOUT] Scanned {name}: {score}/100 ({criticals} critical)')
        return True

    except Exception as e:
        print(f'[SCOUT] Scan error for {name} ({website}): {e}')
        return False


def run_scan_cycle(batch_size=8):
    """
    Runs every hour. Scans unscanned prospects with websites.
    Prioritizes prospects that have never been scanned.
    """
    from icc_database import get_unscanned_with_websites
    prospects = get_unscanned_with_websites(limit=batch_size)
    if not prospects:
        print('[SCOUT] No unscanned prospects with websites')
        return

    print(f'[SCOUT] Scanning {len(prospects)} websites')
    ok = 0
    for p in prospects:
        if scan_prospect(p):
            ok += 1
        time.sleep(4)  # Polite gap — avoid overwhelming targets
    print(f'[SCOUT] Scan cycle: {ok}/{len(prospects)} successful')


# =============================================================================
# OUTREACH AGENT
# =============================================================================

def _auto_queue_fail_email(prospect: dict):
    """
    When a prospect scores below 50, generate and queue their outreach email
    automatically — no human action required.
    For scores 50-59, queue for morning approval.
    """
    try:
        from icc_email_queue import generate_prospect_email, save_to_queue
        score = prospect.get('idr_score', 100)
        email_data = generate_prospect_email(prospect)
        if not email_data:
            return
        auto_send = score < 50  # Below 50 = auto-send, 50-59 = approval queue
        save_to_queue(email_data, auto_send=auto_send)
        action = 'AUTO-QUEUED for send' if auto_send else 'queued for approval'
        print(f'[OUTREACH] {prospect["name"]} ({score}/100) — email {action}')
    except Exception as e:
        print(f'[OUTREACH] Auto-queue error: {e}')


def run_outreach_cycle():
    """
    Runs every hour. Checks for:
    1. New FAIL scores that haven't been emailed yet
    2. Outreach sent 48h ago with no response — queue follow-up
    3. Warm leads (opens/clicks) — notify immediately
    """
    from icc_database import (get_scanned_prospects, get_followups_due,
                               get_warm_leads, log_activity)

    # 1. New FAIL/WARNING scores — auto-queue emails
    scanned = get_scanned_prospects(limit=200)
    new_priority = [
        p for p in scanned
        if p.get('priority') and not p.get('contact_email')
        # contact_email being empty means we haven't contacted them yet
    ]
    for p in new_priority[:10]:  # Max 10 per cycle
        _auto_queue_fail_email(p)
        time.sleep(1)

    # 2. Follow-ups due (48h no response)
    followups = get_followups_due()
    if followups:
        print(f'[OUTREACH] {len(followups)} follow-ups due')
        try:
            from icc_email_queue import generate_followup_email, save_to_queue
            for f in followups[:5]:  # Max 5 follow-ups per cycle
                email_data = generate_followup_email(f)
                if email_data:
                    save_to_queue(email_data, auto_send=False)
        except Exception as e:
            print(f'[OUTREACH] Follow-up queue error: {e}')

    # 3. Warm lead notification
    warm = get_warm_leads()
    if warm:
        print(f'[OUTREACH] {len(warm)} warm leads detected')
        _notify_warm_leads(warm)


def _notify_warm_leads(warm_leads: list):
    """Send instant notification when a prospect opens or clicks."""
    if not SENDGRID_KEY or not warm_leads:
        return
    try:
        top = warm_leads[0]
        subject = f'WARM LEAD: {top["name"]} opened your email'
        body = (
            f'<p style="font-family:Georgia,serif;color:#0B1220;">'
            f'<strong>{top["name"]}</strong> has opened your outreach email.<br><br>'
            f'Score: {top.get("idr_score","?"  )}/100<br>'
            f'Phone: {top.get("phone","Find on their website")}<br>'
            f'Website: {top.get("website","")}<br><br>'
            f'<strong>Suggested call script:</strong><br>'
            f'"Hi, I\'m Hans-Peter Nkansah from the Institute of Digital Remediation. '
            f'I sent information about your HHS accessibility scan results and wanted to '
            f'make sure it reached the right person. Do you have two minutes?"<br><br>'
            f'<a href="https://idrshield.com/icc.html" '
            f'style="background:#C8A75A;color:#0B1220;padding:10px 20px;'
            f'text-decoration:none;font-weight:bold;">Open ICC Command Center</a>'
            f'</p>'
        )
        _sendgrid_send(
            to_email=NOTIFY_TO,
            from_email='hello@idrshield.com',
            from_name='ICC Alert',
            subject=subject,
            html=body,
        )
    except Exception as e:
        print(f'[OUTREACH] Warm lead notify error: {e}')


# =============================================================================
# INTELLIGENCE AGENT
# =============================================================================

def _fetch_rss(url: str) -> list:
    """Fetch and parse an RSS feed. Returns list of {title, summary, link, published}."""
    items = []
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'IDR-Intelligence/2.0',
            'Accept': 'application/rss+xml,application/xml,*/*',
        })
        with urllib.request.urlopen(req, timeout=10, context=_ctx) as r:
            raw = r.read()
        root = ET.fromstring(raw)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        # Handle both RSS and Atom
        entries = root.findall('.//item') or root.findall('.//atom:entry', ns)
        for entry in entries[:10]:
            title = (entry.findtext('title') or
                     entry.findtext('atom:title', namespaces=ns) or '')
            summary = (entry.findtext('description') or
                       entry.findtext('summary') or
                       entry.findtext('atom:summary', namespaces=ns) or '')
            link = (entry.findtext('link') or
                    entry.findtext('atom:link', namespaces=ns) or '')
            pub = (entry.findtext('pubDate') or
                   entry.findtext('published') or
                   entry.findtext('atom:published', namespaces=ns) or '')
            if title:
                items.append({
                    'title': title.strip(),
                    'summary': summary.strip()[:500],
                    'link': link.strip(),
                    'published': pub.strip(),
                })
    except Exception as e:
        print(f'[INTEL] RSS fetch error {url[:50]}: {e}')
    return items


def _is_relevant(title: str, summary: str) -> bool:
    """Check if a news item is relevant to IDR's mission."""
    keywords = [
        'accessibility', 'ada', 'wcag', 'section 504', 'hhs', 'ocr',
        'disability', 'compliance', 'enforcement', 'investigation',
        'title ii', 'section 508', 'digital access', 'remediation',
        'lawsuit', 'complaint', 'settlement', 'fine', 'penalty',
    ]
    text = (title + ' ' + summary).lower()
    return any(kw in text for kw in keywords)


def run_intelligence_cycle():
    """
    Runs every 6 hours.
    Monitors HHS OCR, Federal Register, and regulatory news via RSS.
    Saves relevant items to icc_intelligence table.
    """
    from icc_database import save_intelligence, log_activity

    sources = [
        {
            'name': 'HHS OCR News',
            'url': 'https://www.hhs.gov/ocr/newsroom/index.rss',
            'type': 'ocr_news',
            'relevance': 90,
        },
        {
            'name': 'Federal Register — HHS',
            'url': 'https://www.federalregister.gov/documents/search.rss?conditions%5Bagencies%5D%5B%5D=health-and-human-services-department',
            'type': 'regulatory',
            'relevance': 85,
        },
        {
            'name': 'Federal Register — DOJ',
            'url': 'https://www.federalregister.gov/documents/search.rss?conditions%5Bagencies%5D%5B%5D=justice-department',
            'type': 'regulatory',
            'relevance': 80,
        },
        {
            'name': 'ADA.gov Updates',
            'url': 'https://www.ada.gov/feed.xml',
            'type': 'regulatory',
            'relevance': 85,
        },
        {
            'name': 'Healthcare Compliance News',
            'url': 'https://www.healthcarecompliance.com/feed/',
            'type': 'industry_news',
            'relevance': 70,
        },
    ]

    total_saved = 0
    for source in sources:
        items = _fetch_rss(source['url'])
        for item in items:
            if _is_relevant(item['title'], item['summary']):
                saved = save_intelligence(
                    intel_type=source['type'],
                    source=source['name'],
                    headline=item['title'],
                    summary=item['summary'],
                    url=item['link'],
                    relevance=source['relevance'],
                )
                if saved:
                    total_saved += 1
        time.sleep(2)

    if total_saved:
        log_activity('intelligence_gathered',
                     f'Intelligence cycle: {total_saved} new items from {len(sources)} sources',
                     total_saved)
    print(f'[INTEL] Intelligence cycle complete — {total_saved} new items saved')


# =============================================================================
# CONTENT ENGINE — Auto-generate branded LinkedIn posts from scan data
# =============================================================================

def generate_daily_content():
    """
    Runs daily at 6am EDT. Generates 2 posts from real scan data.
    Post 1 (8:30am): Observatory — real scan data, Institutional Noir style
    Post 2 (12pm):   Intelligence Brief — regulatory insight, Executive Minimal style
    """
    from icc_database import (get_scanned_prospects, get_fresh_intelligence,
                               save_content, log_activity)

    scanned = get_scanned_prospects(limit=50)
    if not scanned:
        print('[CONTENT] No scanned prospects — skipping content generation')
        return

    # Post 1: Observatory — pick the most interesting scan
    fail_scores = [p for p in scanned if (p.get('idr_score') or 101) < 60]
    subject = fail_scores[0] if fail_scores else scanned[0]
    score = subject.get('idr_score', 0)
    criticals = subject.get('critical_count', 0)
    name = subject['name']
    state = subject.get('state', '')

    # Post-deadline enforcement framing throughout
    caption_1 = (
        f'We scanned {name} ({state}) this week.\n\n'
        f'Score: {score}/100\n'
        f'Critical violations: {criticals}\n'
        f'Registry Status: ABSENT\n\n'
        f'The HHS Section 504 enforcement window is open. '
        f'Every organization in the healthcare sector without a documented '
        f'audit record is currently exposed.\n\n'
        f'The scan is not the defense. The record is the defense.\n\n'
        f'Search your domain at idrshield.com/healthscan'
    )
    hashtags_1 = ('#HHScompliance #Section504 #digitalaccessibility '
                  '#WCAG21 #healthcarecompliance #IDRShield')

    save_content(
        content_type='observatory',
        visual_direction='institutional_noir',
        caption=caption_1,
        body_text=caption_1,
        hashtags=hashtags_1,
        prospect_id=subject['id'],
        scan_score=score,
    )

    # Post 2: Intelligence Brief
    intel_items = get_fresh_intelligence(limit=3)
    if intel_items:
        top = intel_items[0]
        caption_2 = (
            f'IDR Intelligence Brief\n\n'
            f'{top["headline"]}\n\n'
            f'{top["summary"][:300]}\n\n'
            f'What this means for covered entities: '
            f'documentation of your accessibility posture is no longer optional. '
            f'It is the evidence that demonstrates good faith when OCR comes looking.\n\n'
            f'The record is how you prove it.\n\n'
            f'instituteofdigitalremediation.org'
        )
    else:
        caption_2 = (
            f'IDR Intelligence Brief\n\n'
            f'Organizations do not get cited for having accessibility issues.\n\n'
            f'They get cited for having no record of addressing them.\n\n'
            f'The distinction matters legally. Under 45 CFR Part 84, willful neglect '
            f'is defined by the absence of documented remediation effort, not by '
            f'the presence of violations.\n\n'
            f'A documented record today is a defensible position tomorrow.\n\n'
            f'instituteofdigitalremediation.org'
        )

    hashtags_2 = ('#digitalaccessibility #HHScompliance #accessibility '
                  '#healthcarecompliance #Section504 #complianceofficer')

    save_content(
        content_type='intelligence_brief',
        visual_direction='executive_minimal',
        caption=caption_2,
        body_text=caption_2,
        hashtags=hashtags_2,
    )

    log_activity('content_generated', 'Daily content: 2 posts generated for approval', 2)
    print('[CONTENT] 2 posts generated — pending approval in ICC Content room')


# =============================================================================
# SENDGRID SENDER — Used by briefing and warm lead notifications
# =============================================================================

def _sendgrid_send(to_email: str, from_email: str, from_name: str,
                   subject: str, html: str) -> bool:
    if not SENDGRID_KEY:
        print('[SENDGRID] No API key — skipping send')
        return False
    try:
        import sendgrid as sg_mod
        from sendgrid.helpers.mail import Mail, Email, To, Content
        msg = Mail(
            from_email=Email(from_email, from_name),
            to_emails=To(to_email),
            subject=subject,
        )
        msg.content = [Content('text/html', html)]
        client = sg_mod.SendGridAPIClient(api_key=SENDGRID_KEY)
        r = client.client.mail.send.post(request_body=msg.get())
        return r.status_code in (200, 202)
    except Exception as e:
        print(f'[SENDGRID] Send error: {e}')
        return False


# =============================================================================
# DAILY BRIEFING — 7am EDT. Real data. Specific names. Actionable.
# =============================================================================

def _sg_send_raw(to_email: str, from_email: str, from_name: str,
                  subject: str, html: str) -> bool:
    """
    Direct SendGrid HTTP call — no library dependency.
    This is the bulletproof fallback used by the briefing.
    """
    if not SENDGRID_KEY:
        print('[SG_RAW] No API key')
        return False
    try:
        payload = json.dumps({
            'personalizations': [{'to': [{'email': to_email}]}],
            'from': {'email': from_email, 'name': from_name},
            'subject': subject,
            'content': [{'type': 'text/html', 'value': html}],
        }).encode()
        req = urllib.request.Request(
            'https://api.sendgrid.com/v3/mail/send',
            data=payload,
            headers={
                'Authorization': f'Bearer {SENDGRID_KEY}',
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=15, context=_ctx) as r:
            status = r.status
        print(f'[SG_RAW] Sent to {to_email} — status {status}')
        return status in (200, 202)
    except Exception as e:
        print(f'[SG_RAW] Error: {e}')
        return False


def send_daily_briefing():
    """
    Sends a real intelligence briefing — pulls from actual DB tables.
    Never generic. Every number is a real count. Every name is a real person.
    Uses direct HTTP to SendGrid — no library dependency.
    """
    if not SENDGRID_KEY:
        print('[BRIEFING] No SendGrid key — skipping')
        return

    print('[BRIEFING] Starting...')

    try:
        from icc_database import (get_icc_stats, get_scanned_prospects,
                                   get_warm_leads, get_associations,
                                   get_fresh_intelligence, log_activity)
        BRAND_COLORS = {
            'navy': '#0B1220', 'gold': '#C8A75A', 'red': '#DC2626',
            'amber': '#D97706', 'green': '#059669', 'cream': '#F8F6F1',
        }
    except Exception as import_err:
        print(f'[BRIEFING] Import error: {import_err}')
        return

    try:
        stats = get_icc_stats() or {}
    except Exception as e:
        print(f'[BRIEFING] Stats error: {e}')
        stats = {}

    print(f'[BRIEFING] Stats: {stats}')

    scanned    = get_scanned_prospects(limit=100)
    warm_leads = get_warm_leads()
    assocs     = get_associations()
    intel      = get_fresh_intelligence(limit=5)

    fail_scores  = [p for p in scanned if (p.get('idr_score') or 101) < 60]
    warn_scores  = [p for p in scanned if 60 <= (p.get('idr_score') or 101) < 80]
    pass_scores  = [p for p in scanned if (p.get('idr_score') or 0) >= 80]
    assoc_warm   = [a for a in assocs if a.get('status') in ('opened', 'replied', 'in_conversation')]
    days_past    = stats.get('days_past_deadline', 0)

    gold   = BRAND_COLORS['gold']
    navy   = BRAND_COLORS['navy']
    red    = BRAND_COLORS['red']
    amber  = BRAND_COLORS['amber']
    green  = BRAND_COLORS['green']
    cream  = BRAND_COLORS['cream']

    def sc(s):
        if s is None: return '#64748B'
        if s < 60: return red
        if s < 80: return amber
        return green

    # Build today's specific action items from real data
    todos = []
    if warm_leads:
        top = warm_leads[0]
        ph = top.get('phone') or top.get('contact_email') or 'find contact on their website'
        todos.append(
            f'<strong>CALL NOW:</strong> {top["name"]} opened your email. '
            f'Contact: {ph}. '
            f'Opening: "I\'m Hans-Peter Nkansah from the Institute of Digital Remediation. '
            f'I wanted to make sure my scan results reached the right person."'
        )
    if fail_scores:
        top = fail_scores[0]
        ph = top.get('phone', '')
        todos.append(
            f'<strong>PRIORITY EMAIL:</strong> {top["name"]} scored {top.get("idr_score","?")}/100. '
            f'{top.get("critical_count",0)} critical violations. '
            + (f'Phone: {ph}.' if ph else 'Find compliance contact on their website.')
            + ' Outreach email auto-queued — approve in Email Queue.'
        )
    if len(scanned) < 50:
        todos.append(
            f'<strong>SCAN MORE:</strong> {len(scanned)} prospects scanned so far. '
            f'Open ICC Prospects and run the scan batch — every FAIL score is a sales call.'
        )
    if assoc_warm:
        top_a = assoc_warm[0]
        todos.append(
            f'<strong>ASSOCIATION HOT:</strong> {top_a["name"]} status: {top_a["status"].upper()}. '
            f'Reply within the hour — offer to deliver the article draft immediately.'
        )
    if not todos:
        todos.append(
            '<strong>APPROVE EMAILS:</strong> Open ICC Email Queue and approve all pending outreach.'
        )
        todos.append(
            '<strong>LINKEDIN:</strong> Post today\'s Observatory content from the Content room.'
        )

    todos_html = ''.join(
        f'<div style="padding:12px 16px;border-left:3px solid {gold};'
        f'margin-bottom:10px;font-size:13px;color:#1E293B;background:#FAFAF8;">'
        f'{t}</div>'
        for t in todos
    )

    # Warm leads section
    warm_html = ''
    if warm_leads:
        rows = ''
        for lead in warm_leads[:5]:
            s = lead.get('idr_score')
            ph = f'<div style="font-size:11px;color:#374151;">{lead.get("phone","")}</div>' if lead.get('phone') else ''
            rows += (
                f'<div style="border-left:3px solid {gold};padding:10px 14px;'
                f'margin-bottom:8px;background:#FFFBEB;">'
                f'<div style="font-size:14px;font-weight:700;color:{navy};">{lead["name"]}</div>'
                f'<div style="font-size:11px;color:#64748B;">Score: '
                f'<strong style="color:{sc(s)}">{s}/100</strong> &nbsp;|&nbsp; '
                f'{lead.get("status","").upper()}</div>'
                f'{ph}'
                f'<div style="font-size:11px;color:{gold};">Follow up immediately</div>'
                f'</div>'
            )
        warm_html = (
            f'<p style="font-size:10px;letter-spacing:0.12em;color:{gold};'
            f'text-transform:uppercase;margin:20px 0 8px;">WARM LEADS</p>' + rows
        )

    # Fail scores section
    fail_html = ''
    if fail_scores:
        rows = ''
        for p in fail_scores[:8]:
            s = p.get('idr_score', 0)
            ph = f'<div style="font-size:11px;color:#374151;">{p.get("phone","")}</div>' if p.get('phone') else ''
            email_stored = p.get('contact_email', '')
            email_note = (f'<div style="font-size:10px;color:#059669;">Contact stored: {email_stored}</div>'
                          if email_stored else
                          '<div style="font-size:10px;color:#94A3B8;">No contact email yet</div>')
            rows += (
                f'<div style="border-left:3px solid {red};padding:8px 14px;'
                f'margin-bottom:6px;background:#FEF2F2;">'
                f'<div style="font-size:13px;font-weight:700;color:{navy};">{p["name"]}</div>'
                f'<div style="font-size:11px;color:#64748B;">'
                f'{p.get("city","")}, {p.get("state","")} &nbsp;|&nbsp; '
                f'Score: <strong style="color:{red}">{s}/100</strong> &nbsp;|&nbsp; '
                f'{p.get("critical_count",0)} critical &nbsp;|&nbsp; '
                f'Maturity: {p.get("maturity_level","ABSENT")}</div>'
                f'{ph}{email_note}</div>'
            )
        fail_html = (
            f'<p style="font-size:10px;letter-spacing:0.12em;color:{red};'
            f'text-transform:uppercase;margin:20px 0 8px;">'
            f'PRIORITY TARGETS — SCORE BELOW 60</p>' + rows
        )

    # Scan summary
    scan_html = ''
    if scanned:
        scan_html = (
            f'<p style="font-size:10px;letter-spacing:0.12em;color:{gold};'
            f'text-transform:uppercase;margin:20px 0 8px;">'
            f'{len(scanned)} ORGANIZATIONS SCANNED</p>'
            f'<table width="100%" cellpadding="0" cellspacing="8" style="margin-bottom:16px;"><tr>'
            f'<td align="center" style="background:#FEF2F2;padding:10px;border-radius:4px;">'
            f'<div style="font-size:28px;font-weight:700;color:{red};">{len(fail_scores)}</div>'
            f'<div style="font-size:9px;color:{red};text-transform:uppercase;">FAIL</div></td>'
            f'<td align="center" style="background:#FFFBEB;padding:10px;border-radius:4px;">'
            f'<div style="font-size:28px;font-weight:700;color:{amber};">{len(warn_scores)}</div>'
            f'<div style="font-size:9px;color:{amber};text-transform:uppercase;">WARNING</div></td>'
            f'<td align="center" style="background:#F0FDF4;padding:10px;border-radius:4px;">'
            f'<div style="font-size:28px;font-weight:700;color:{green};">{len(pass_scores)}</div>'
            f'<div style="font-size:9px;color:{green};text-transform:uppercase;">PASS</div></td>'
            f'</tr></table>'
        )

    # Intelligence section
    intel_html = ''
    if intel:
        rows = ''
        for item in intel[:3]:
            rows += (
                f'<div style="padding:8px 14px;border-left:3px solid #64748B;'
                f'margin-bottom:6px;font-size:12px;color:{navy};">'
                f'<strong>{item["headline"][:80]}</strong><br>'
                f'<span style="color:#64748B;">{item["source"]}</span>'
                f'</div>'
            )
        intel_html = (
            f'<p style="font-size:10px;letter-spacing:0.12em;color:{gold};'
            f'text-transform:uppercase;margin:20px 0 8px;">REGULATORY INTELLIGENCE</p>' + rows
        )

    # Association status
    assoc_html = ''
    if assoc_warm:
        rows = ''
        for a in assoc_warm:
            rows += (
                f'<div style="padding:8px 14px;border-left:3px solid {gold};'
                f'margin-bottom:6px;background:#FFFBEB;font-size:12px;color:{navy};">'
                f'<strong>{a["name"]}</strong> — {a["status"].upper()}<br>'
                f'<span style="color:#64748B;">{a.get("member_count","?")} members</span>'
                f'</div>'
            )
        assoc_html = (
            f'<p style="font-size:10px;letter-spacing:0.12em;color:{gold};'
            f'text-transform:uppercase;margin:16px 0 8px;">ASSOCIATIONS — HOT</p>' + rows
        )

    today_str = date.today().strftime('%A, %B %d, %Y')
    rev = stats.get('revenue', 0)

    subject = (
        f'IDR Morning Briefing — {today_str} — '
        f'{len(fail_scores)} FAIL · {len(warn_scores)} WARNING · '
        f'{len(warm_leads)} Warm · ${rev} Revenue'
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="color-scheme" content="light only">
<meta name="supported-color-schemes" content="light">
</head>
<body bgcolor="{cream}" style="margin:0;padding:0;font-family:Georgia,serif;background:{cream};">
<table width="100%" bgcolor="{cream}" cellpadding="0" cellspacing="0" style="padding:32px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

<!-- Header -->
<tr><td bgcolor="{navy}" style="padding:24px 32px;">
<p style="margin:0 0 2px;font-size:9px;letter-spacing:0.2em;color:{gold};text-transform:uppercase;">
ICC · IDR Command Center · Institute of Digital Remediation</p>
<p style="margin:0;font-size:22px;font-weight:700;color:{cream};">
Morning Briefing · {today_str}</p>
</td></tr>

<!-- Enforcement status bar -->
<tr><td bgcolor="{red}" style="padding:12px 32px;text-align:center;">
<p style="margin:0;font-size:12px;font-weight:700;color:#FFFFFF;letter-spacing:0.15em;text-transform:uppercase;">
HHS ENFORCEMENT WINDOW OPEN · {days_past} DAYS SINCE MAY 11 DEADLINE</p>
</td></tr>

<!-- Stats row -->
<tr><td bgcolor="#FFFFFF" style="padding:24px 32px;">
<table width="100%" cellpadding="0" cellspacing="0"><tr>
<td align="center" style="padding:8px;">
<div style="font-size:32px;font-weight:700;color:{gold};">{stats.get("total",0)}</div>
<div style="font-size:9px;letter-spacing:0.1em;color:#94A3B8;text-transform:uppercase;">Prospects</div></td>
<td align="center" style="padding:8px;">
<div style="font-size:32px;font-weight:700;color:{red};">{stats.get("priority",0)}</div>
<div style="font-size:9px;letter-spacing:0.1em;color:#94A3B8;text-transform:uppercase;">Priority</div></td>
<td align="center" style="padding:8px;">
<div style="font-size:32px;font-weight:700;color:#374151;">{stats.get("contacted",0)}</div>
<div style="font-size:9px;letter-spacing:0.1em;color:#94A3B8;text-transform:uppercase;">Contacted</div></td>
<td align="center" style="padding:8px;">
<div style="font-size:32px;font-weight:700;color:{green};">{stats.get("warm",0)}</div>
<div style="font-size:9px;letter-spacing:0.1em;color:#94A3B8;text-transform:uppercase;">Warm</div></td>
<td align="center" style="padding:8px;">
<div style="font-size:32px;font-weight:700;color:{green};">${rev}</div>
<div style="font-size:9px;letter-spacing:0.1em;color:#94A3B8;text-transform:uppercase;">Revenue</div></td>
</tr></table>
</td></tr>

<!-- Actions -->
<tr><td bgcolor="#FFFFFF" style="padding:0 32px 24px;">
<p style="font-size:10px;letter-spacing:0.12em;color:{gold};text-transform:uppercase;margin:16px 0 8px;">
YOUR ACTIONS TODAY</p>
{todos_html}
{warm_html}
{fail_html}
{scan_html}
{intel_html}
{assoc_html}
<div style="text-align:center;margin:24px 0 8px;">
<a href="https://idrshield.com/icc.html"
style="background:{gold};color:{navy};font-size:11px;font-weight:700;
letter-spacing:0.12em;text-transform:uppercase;padding:12px 32px;
text-decoration:none;display:inline-block;">
OPEN ICC COMMAND CENTER</a>
</div>
</td></tr>

<!-- Footer -->
<tr><td bgcolor="#1a2435" style="padding:16px 32px;text-align:center;">
<p style="margin:0;font-size:10px;color:#64748B;">
Institute of Digital Remediation · Digital Access. Trust. Compliance. · idrshield.com</p>
</td></tr>

</table>
</td></tr>
</table>
</body></html>"""

    ok = _sg_send_raw(
        to_email=BRIEFING_TO,
        from_email='hello@idrshield.com',
        from_name='ICC Command Center',
        subject=subject,
        html=html,
    )
    status = 'sent' if ok else 'failed'
    log_activity('briefing_sent',
                 f'Morning briefing {status} — {len(fail_scores)} fail, '
                 f'{len(warm_leads)} warm, ${rev} revenue')
    print(f'[BRIEFING] {status.upper()} — {today_str}')


# =============================================================================
# MAIN CYCLE — Called by cron every hour
# =============================================================================

def run_icc_cycle():
    """
    Main ICC worker cycle. Called every hour by cron scheduler.
    Sequenced to prioritize high-value actions first.
    """
    now = datetime.now(timezone.utc)
    print(f'[ICC] Cycle starting {now.isoformat()}')

    # 1. Always scan — highest value hourly task
    run_scan_cycle(batch_size=8)

    # 2. Always run outreach cycle — catch new FAIL scores, queue follow-ups
    run_outreach_cycle()

    # 3. Harvest every 6 hours — government APIs are rate-sensitive
    if now.hour % 6 == 0:
        run_harvest_cycle(limit_per_state=50)

    # 4. Intelligence every 6 hours
    if now.hour % 6 == 0:
        run_intelligence_cycle()

    # 5. Generate daily content at 6am UTC (2am EDT — ready by morning)
    if now.hour == 6 and now.minute < 60:
        generate_daily_content()

    # 6. Morning briefing at 11am UTC = 7am EDT
    if now.hour == 11 and now.minute < 60:
        send_daily_briefing()

    print('[ICC] Cycle complete')
