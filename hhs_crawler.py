"""
IDR Shield — hhs_crawler.py
Multi-page WCAG 2.1 AA crawler for HHS paid audits.
Crawls up to MAX_PAGES internal pages, runs 5-category checks on each,
aggregates findings, returns enriched scan data with page inventory.
"""

import time
import re
from urllib.parse import urlparse, urljoin, urldefrag
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

MAX_PAGES       = 15
CRAWL_TIMEOUT   = 45          # seconds total crawl budget
PAGE_TIMEOUT    = 8           # seconds per page fetch
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (compatible; IDR-HHS-Crawler/1.0; '
        '+https://idrshield.com/hhs-compliance)'
    )
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalise(url):
    """Strip fragment, trailing slash, lowercase scheme+host."""
    url, _ = urldefrag(url)
    parsed  = urlparse(url)
    norm    = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=parsed.path.rstrip('/') or '/'
    )
    return norm.geturl()


def _same_domain(base_domain, url):
    """Return True if url belongs to base_domain (www. agnostic)."""
    try:
        host = urlparse(url).netloc.lower().lstrip('www.')
        base = base_domain.lower().lstrip('www.')
        return host == base or host.endswith('.' + base)
    except Exception:
        return False


def _skip_url(url):
    """Return True for non-HTML resources we should not crawl."""
    skip_exts = (
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.zip', '.tar', '.gz', '.jpg', '.jpeg', '.png', '.gif',
        '.svg', '.webp', '.ico', '.mp4', '.mp3', '.wav', '.avi',
        '.css', '.js', '.json', '.xml', '.rss', '.atom',
    )
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in skip_exts)


# ── Per-page WCAG checks ──────────────────────────────────────────────────────

def _check_page(soup, url):
    """
    Run 5-category WCAG 2.1 AA checks on a parsed page.
    Returns dict: {slug: {score, issues: [{severity, description, wcag, count}]}}
    """
    results = {}

    # ── 1. Image Alt Text (WCAG 1.1.1) ───────────────────────────────────────
    imgs          = soup.find_all('img')
    missing_alt   = [i for i in imgs if i.get('alt') is None]
    empty_meaningful = [
        i for i in imgs
        if i.get('alt') == '' and not i.get('role') == 'presentation'
        and not i.get('aria-hidden') == 'true'
    ]
    alt_issues = []
    if missing_alt:
        alt_issues.append({
            'severity': 'critical',
            'description': f'{len(missing_alt)} image(s) missing alt attribute.',
            'wcag': '1.1.1', 'count': len(missing_alt),
        })
    if empty_meaningful:
        alt_issues.append({
            'severity': 'serious',
            'description': f'{len(empty_meaningful)} image(s) with empty alt on potentially meaningful content.',
            'wcag': '1.1.1', 'count': len(empty_meaningful),
        })
    alt_score = max(0, 100 - len(missing_alt) * 12 - len(empty_meaningful) * 6)
    results['alt_text'] = {'score': min(100, alt_score), 'issues': alt_issues}

    # ── 2. Form Labels (WCAG 1.3.1, 3.3.2) ──────────────────────────────────
    inputs = soup.find_all(['input', 'select', 'textarea'])
    inputs = [i for i in inputs
              if i.get('type') not in ('hidden', 'submit', 'button', 'image', 'reset')
              and i.get('type') != None or i.name in ('select', 'textarea')]
    unlabeled   = []
    placeholder_only = []
    for inp in inputs:
        inp_id = inp.get('id')
        has_label = (
            (inp_id and soup.find('label', attrs={'for': inp_id})) or
            inp.get('aria-label') or
            inp.get('aria-labelledby') or
            inp.find_parent('label')
        )
        if not has_label:
            if inp.get('placeholder'):
                placeholder_only.append(inp)
            else:
                unlabeled.append(inp)
    form_issues = []
    if unlabeled:
        form_issues.append({
            'severity': 'critical',
            'description': f'{len(unlabeled)} form input(s) have no label at all.',
            'wcag': '1.3.1', 'count': len(unlabeled),
        })
    if placeholder_only:
        form_issues.append({
            'severity': 'serious',
            'description': f'{len(placeholder_only)} input(s) use placeholder as only label.',
            'wcag': '3.3.2', 'count': len(placeholder_only),
        })
    form_score = max(0, 100 - len(unlabeled) * 15 - len(placeholder_only) * 7)
    results['form_labels'] = {'score': min(100, form_score), 'issues': form_issues}

    # ── 3. Keyboard Navigation (WCAG 2.1.1, 2.4.1, 2.4.7) ───────────────────
    kbd_issues = []
    # tabindex=-1 on interactive elements
    neg_tab = soup.find_all(
        ['a', 'button', 'input', 'select', 'textarea'],
        attrs={'tabindex': '-1'}
    )
    if neg_tab:
        kbd_issues.append({
            'severity': 'critical',
            'description': f'{len(neg_tab)} interactive element(s) removed from tab order via tabindex="-1".',
            'wcag': '2.1.1', 'count': len(neg_tab),
        })
    # No skip link
    skip_links = soup.find_all('a', href=re.compile(r'^#'))
    has_skip   = any(
        'skip' in (s.get_text() or '').lower() or
        'main' in (s.get('href') or '').lower()
        for s in skip_links
    )
    if not has_skip:
        kbd_issues.append({
            'severity': 'serious',
            'description': 'No skip navigation link detected.',
            'wcag': '2.4.1', 'count': 1,
        })
    # focus:none in inline styles
    focus_none = soup.find_all(style=re.compile(r'outline\s*:\s*none|outline\s*:\s*0'))
    if focus_none:
        kbd_issues.append({
            'severity': 'serious',
            'description': f'{len(focus_none)} element(s) suppress focus indicator via inline style.',
            'wcag': '2.4.7', 'count': len(focus_none),
        })
    kbd_score = max(0, 100 - len(neg_tab) * 18 - (15 if not has_skip else 0) - len(focus_none) * 8)
    results['keyboard_nav'] = {'score': min(100, kbd_score), 'issues': kbd_issues}

    # ── 4. Heading Structure (WCAG 1.3.1, 2.4.6) ─────────────────────────────
    headings = soup.find_all(['h1','h2','h3','h4','h5','h6'])
    hdg_issues = []
    h1s = [h for h in headings if h.name == 'h1']
    if not h1s:
        hdg_issues.append({
            'severity': 'serious',
            'description': 'Page has no H1 heading.',
            'wcag': '1.3.1', 'count': 1,
        })
    elif len(h1s) > 1:
        hdg_issues.append({
            'severity': 'moderate',
            'description': f'Page has {len(h1s)} H1 headings — should have exactly one.',
            'wcag': '1.3.1', 'count': len(h1s),
        })
    # Check for skipped levels
    levels = [int(h.name[1]) for h in headings]
    skips  = sum(1 for i in range(1, len(levels)) if levels[i] - levels[i-1] > 1)
    if skips:
        hdg_issues.append({
            'severity': 'moderate',
            'description': f'Heading level skipped {skips} time(s) — e.g. H1 to H3 with no H2.',
            'wcag': '2.4.6', 'count': skips,
        })
    h1_penalty = 20 if not h1s else (5 * (len(h1s) - 1))
    hdg_score  = max(0, 100 - h1_penalty - skips * 8)
    results['heading_structure'] = {'score': min(100, hdg_score), 'issues': hdg_issues}

    # ── 5. ARIA & Links (WCAG 4.1.2, 2.4.4, 4.1.1) ──────────────────────────
    aria_issues = []
    # Buttons with no accessible name
    buttons = soup.find_all('button')
    unnamed_btns = [
        b for b in buttons
        if not b.get_text(strip=True)
        and not b.get('aria-label')
        and not b.get('aria-labelledby')
        and not b.find('img', alt=True)
    ]
    if unnamed_btns:
        aria_issues.append({
            'severity': 'critical',
            'description': f'{len(unnamed_btns)} button(s) have no accessible name.',
            'wcag': '4.1.2', 'count': len(unnamed_btns),
        })
    # Generic link text
    links = soup.find_all('a', href=True)
    generic_text = ['click here', 'read more', 'learn more', 'more', 'here', 'link']
    generic_links = [
        l for l in links
        if l.get_text(strip=True).lower() in generic_text
        and not l.get('aria-label')
    ]
    if generic_links:
        aria_issues.append({
            'severity': 'serious',
            'description': f'{len(generic_links)} link(s) use non-descriptive text (e.g. "click here", "read more").',
            'wcag': '2.4.4', 'count': len(generic_links),
        })
    # Duplicate IDs
    ids = [t.get('id') for t in soup.find_all(id=True)]
    dup_ids = len(ids) - len(set(ids))
    if dup_ids:
        aria_issues.append({
            'severity': 'serious',
            'description': f'{dup_ids} duplicate ID(s) found — ARIA relationships may break.',
            'wcag': '4.1.1', 'count': dup_ids,
        })
    aria_score = max(0, 100 - len(unnamed_btns) * 14 - len(generic_links) * 5 - dup_ids * 3)
    results['aria_links_contrast'] = {'score': min(100, aria_score), 'issues': aria_issues}

    return results


# ── Aggregation ───────────────────────────────────────────────────────────────

def _aggregate(page_results, base_url):
    """
    Merge per-page check results into site-wide category findings.
    Deduplicates identical descriptions across pages.
    Returns categories list matching the existing receipt schema.
    """
    CAT_NAMES = {
        'alt_text':           'Image Alt Text',
        'form_labels':        'Form Labels',
        'keyboard_nav':       'Keyboard Navigation',
        'heading_structure':  'Heading Structure',
        'aria_links_contrast':'ARIA & Links',
    }

    agg = defaultdict(lambda: {'scores': [], 'issues_by_desc': defaultdict(lambda: {
        'severity': 'minor', 'wcag': '', 'count': 0, 'pages': []
    })})

    for page_url, checks in page_results.items():
        for slug, data in checks.items():
            agg[slug]['scores'].append(data['score'])
            for issue in data['issues']:
                key = issue['description'][:80]
                existing = agg[slug]['issues_by_desc'][key]
                existing['severity'] = issue['severity']
                existing['wcag']     = issue.get('wcag', '')
                existing['count']   += issue.get('count', 1)
                existing['pages'].append(page_url)

    categories = []
    for slug in ['alt_text', 'form_labels', 'keyboard_nav', 'heading_structure', 'aria_links_contrast']:
        data   = agg[slug]
        scores = data['scores']
        score  = int(sum(scores) / len(scores)) if scores else 100
        status = 'pass' if score >= 80 else 'warning' if score >= 60 else 'fail'

        issues_raw = data['issues_by_desc']
        issues = []
        for desc_key, info in issues_raw.items():
            page_note = f' (found on {len(info["pages"])} page(s))' if len(info['pages']) > 1 else ''
            issues.append({
                'rule':        f'{slug}-{info["severity"]}',
                'severity':    info['severity'],
                'description': desc_key + page_note,
                'element':     '',
                'impact':      'Accessibility barrier identified during multi-page audit.',
                'url':         base_url,
                'wcag':        info['wcag'],
                'count':       info['count'],
            })
        # Sort: critical first
        sev_order = {'critical': 0, 'serious': 1, 'moderate': 2, 'minor': 3}
        issues.sort(key=lambda x: sev_order.get(x['severity'], 4))

        crits   = sum(1 for i in issues if i['severity'] == 'critical')
        serious = sum(1 for i in issues if i['severity'] == 'serious')

        categories.append({
            'name':           CAT_NAMES[slug],
            'slug':           slug,
            'status':         status,
            'score':          score,
            'critical_count': crits,
            'serious_count':  serious,
            'issues':         issues,
        })

    return categories


# ── Main crawl entry point ────────────────────────────────────────────────────

def run_hhs_crawl(start_url: str, max_pages: int = MAX_PAGES) -> dict:
    """
    Crawl start_url and up to max_pages internal links.
    Returns enriched scan dict ready to merge into receipt_data['scan'].

    Keys added vs single-page scan:
        pages_scanned      int
        pages_crawled      list of {url, title, score, critical_count}
        crawl_duration_ms  int
        is_multi_page      True
    """
    crawl_start = time.time()

    parsed     = urlparse(start_url)
    base_domain = parsed.netloc.lower()

    visited    = set()
    queue      = [_normalise(start_url)]
    page_results = {}      # url -> checks dict
    page_inventory = []    # for PDF and receipt display

    session = requests.Session()
    session.headers.update(HEADERS)

    while queue and len(visited) < max_pages:
        if time.time() - crawl_start > CRAWL_TIMEOUT:
            print(f'[CRAWLER] Time budget exhausted after {len(visited)} pages')
            break

        url = queue.pop(0)
        if url in visited:
            continue
        if _skip_url(url):
            continue

        visited.add(url)

        try:
            resp = session.get(url, timeout=PAGE_TIMEOUT, allow_redirects=True)
            if resp.status_code != 200:
                print(f'[CRAWLER] {resp.status_code} — {url}')
                continue
            ct = resp.headers.get('Content-Type', '')
            if 'html' not in ct:
                continue

            soup  = BeautifulSoup(resp.text, 'html.parser')
            title = soup.title.string.strip() if soup.title and soup.title.string else url

            # Run checks on this page
            checks = _check_page(soup, url)
            page_results[url] = checks

            # Page-level score
            page_score = int(sum(c['score'] for c in checks.values()) / len(checks))
            page_crits = sum(
                sum(1 for i in c['issues'] if i['severity'] == 'critical')
                for c in checks.values()
            )
            page_inventory.append({
                'url':            url,
                'title':          title[:80],
                'score':          page_score,
                'critical_count': page_crits,
            })

            # Discover internal links
            for tag in soup.find_all('a', href=True):
                href = tag['href'].strip()
                if not href or href.startswith(('mailto:', 'tel:', 'javascript:')):
                    continue
                abs_url = _normalise(urljoin(url, href))
                if (
                    _same_domain(base_domain, abs_url)
                    and abs_url not in visited
                    and abs_url not in queue
                    and not _skip_url(abs_url)
                    and len(queue) < max_pages * 3
                ):
                    queue.append(abs_url)

        except requests.exceptions.Timeout:
            print(f'[CRAWLER] Timeout — {url}')
        except Exception as e:
            print(f'[CRAWLER] Error on {url}: {e}')

    crawl_ms = int((time.time() - crawl_start) * 1000)

    if not page_results:
        # Crawl completely failed — return minimal indicator
        return {
            'pages_scanned':    0,
            'pages_crawled':    [],
            'crawl_duration_ms': crawl_ms,
            'is_multi_page':    False,
            'crawl_error':      'No pages could be fetched.',
        }

    # Aggregate all pages into site-wide categories
    categories   = _aggregate(page_results, start_url)
    all_issues   = [i for cat in categories for i in cat['issues']]
    total_issues = len(all_issues)
    crits        = sum(1 for i in all_issues if i['severity'] == 'critical')
    serious      = sum(1 for i in all_issues if i['severity'] == 'serious')
    avg_score    = int(sum(c['score'] for c in categories) / len(categories))
    status       = 'pass' if avg_score >= 80 else 'warning' if avg_score >= 60 else 'fail'

    return {
        'overall_score':    avg_score,
        'overall_status':   status,
        'critical_count':   crits,
        'serious_count':    serious,
        'total_issues':     total_issues,
        'categories':       categories,
        'pages_scanned':    len(page_results),
        'pages_crawled':    page_inventory,
        'crawl_duration_ms': crawl_ms,
        'is_multi_page':    True,
    }
