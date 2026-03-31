"""
IDR Scanner Engine — Lightweight build (no Playwright)
Accessibility audit across 5 categories using requests + BeautifulSoup.
Violations are aggregated by rule at source — one row per violation type.
"""

import re
import time
from dataclasses import dataclass, field
from typing import Optional, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


@dataclass
class Issue:
    category: str
    severity: str
    rule: str
    description: str
    element: str
    impact: str
    wcag: str
    count: int = 1


@dataclass
class CategoryResult:
    name: str
    status: str
    score: int
    issues: List[Issue] = field(default_factory=list)
    critical_count: int = 0
    serious_count: int = 0


@dataclass
class ScanResult:
    url: str
    domain: str
    title: str
    categories: List[CategoryResult] = field(default_factory=list)
    overall_score: int = 0
    overall_status: str = "fail"
    critical_count: int = 0
    serious_count: int = 0
    total_issues: int = 0
    scan_duration_ms: int = 0
    error: Optional[str] = None


def _score(issues, total_checks):
    if total_checks == 0:
        return 100, "pass"
    critical = sum(i.count for i in issues if i.severity == "critical")
    serious = sum(i.count for i in issues if i.severity == "serious")
    moderate = sum(i.count for i in issues if i.severity == "moderate")
    deductions = (critical * 20) + (serious * 10) + (moderate * 3)
    score = max(0, 100 - deductions)
    if critical > 0:
        status = "fail"
    elif score >= 80:
        status = "pass"
    else:
        status = "warning"
    return score, status


def _make_cat(name, issues, checks):
    score, status = _score(issues, checks)
    cat = CategoryResult(name=name, status=status, score=score, issues=issues)
    cat.critical_count = sum(i.count for i in issues if i.severity == "critical")
    cat.serious_count = sum(i.count for i in issues if i.severity == "serious")
    return cat


def audit_images(soup) -> CategoryResult:
    images = soup.find_all("img")
    checks = len(images)
    missing_alts, empty_linked, non_descriptive = [], [], []

    for img in images:
        src = img.get("src", "")[:80]
        alt = img.get("alt")
        if alt is None:
            missing_alts.append(src)
        elif alt.strip() == "" and img.parent and img.parent.name == "a":
            empty_linked.append(src)
        elif alt and re.match(r'^(image|img|photo|picture|graphic|icon|logo|\.jpg|\.png|\.gif|\.svg)', alt.strip().lower()):
            non_descriptive.append((alt.strip(), src))

    issues = []
    if missing_alts:
        issues.append(Issue("Image Alt Text", "critical", "img-alt-missing",
            f"{len(missing_alts)} image(s) missing alt attribute",
            f'<img src="{missing_alts[0]}">',
            "Screen readers cannot describe these images to blind users.", "1.1.1", len(missing_alts)))
    if empty_linked:
        issues.append(Issue("Image Alt Text", "serious", "img-alt-empty-linked",
            f"{len(empty_linked)} linked image(s) have empty alt text — link purpose unclear",
            f'<a><img src="{empty_linked[0]}" alt=""></a>',
            "Screen reader users cannot determine where these links lead.", "1.1.1", len(empty_linked)))
    if non_descriptive:
        issues.append(Issue("Image Alt Text", "moderate", "img-alt-non-descriptive",
            f"{len(non_descriptive)} image(s) have non-descriptive alt text",
            f'<img alt="{non_descriptive[0][0]}" src="{non_descriptive[0][1]}">',
            "Alt text does not convey the image's meaning or purpose.", "1.1.1", len(non_descriptive)))

    return _make_cat("Image Alt Text", issues, checks)


def audit_forms(soup) -> CategoryResult:
    inputs = soup.find_all(["input", "select", "textarea"])
    inputs = [i for i in inputs if i.get("type", "text") not in ("hidden", "submit", "button", "image", "reset")]
    checks = len(inputs)
    labels = soup.find_all("label")
    label_fors = {l.get("for"): l for l in labels if l.get("for")}
    missing_label, placeholder_only = [], []

    for inp in inputs:
        inp_id = inp.get("id")
        inp_type = inp.get("type", "text")
        aria_label = inp.get("aria-label") or inp.get("aria-labelledby")
        placeholder = inp.get("placeholder")
        has_label = (inp_id and inp_id in label_fors)
        has_aria = bool(aria_label)
        if not has_label and not has_aria:
            if placeholder:
                placeholder_only.append((inp_type, placeholder))
            else:
                missing_label.append((inp_type, inp_id or "no-id"))

    issues = []
    if missing_label:
        issues.append(Issue("Form Labels", "critical", "form-label-missing",
            f"{len(missing_label)} form input(s) have no associated label",
            f'<input type="{missing_label[0][0]}" id="{missing_label[0][1]}">',
            "Screen readers cannot identify the purpose of these fields.", "1.3.1", len(missing_label)))
    if placeholder_only:
        issues.append(Issue("Form Labels", "serious", "form-label-placeholder-only",
            f"{len(placeholder_only)} input(s) use placeholder as only label",
            f'<input type="{placeholder_only[0][0]}" placeholder="{placeholder_only[0][1]}">',
            "Placeholder disappears on input — users with cognitive disabilities lose context.", "1.3.1", len(placeholder_only)))

    return _make_cat("Form Labels", issues, checks)


def audit_keyboard(soup) -> CategoryResult:
    checks = 3
    issues = []
    first_links = soup.find_all("a", limit=5)
    has_skip = any("skip" in (a.get_text().lower() + a.get("href", "").lower()) for a in first_links)
    if not has_skip:
        issues.append(Issue("Keyboard Navigation", "serious", "skip-link-missing",
            "No skip navigation link found", "<body> — no skip link in first 5 links",
            "Keyboard users must tab through entire navigation on every page load.", "2.4.1", 1))

    has_main = bool(soup.find("main") or soup.find(attrs={"role": "main"}))
    if not has_main:
        issues.append(Issue("Keyboard Navigation", "serious", "landmark-main-missing",
            "No <main> landmark element found", "<body>",
            "Screen reader users cannot jump directly to main content.", "2.4.1", 1))

    bad_tabindex = soup.find_all(["a", "button", "input", "select"], tabindex="-1")
    if bad_tabindex:
        issues.append(Issue("Keyboard Navigation", "critical", "tabindex-negative-interactive",
            f"{len(bad_tabindex)} interactive element(s) have tabindex=-1",
            str(bad_tabindex[0])[:80],
            "These elements are unreachable by keyboard navigation.", "2.1.1", len(bad_tabindex)))

    return _make_cat("Keyboard Navigation", issues, checks)


def audit_headings(soup) -> CategoryResult:
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    checks = max(len(headings), 1)
    issues = []

    h1s = [h for h in headings if h.name == "h1"]
    if not h1s:
        issues.append(Issue("Heading Structure", "serious", "heading-h1-missing",
            "Page has no H1 heading", "<body>",
            "Screen readers and search engines cannot identify the page's primary topic.", "2.4.6", 1))
    elif len(h1s) > 1:
        issues.append(Issue("Heading Structure", "moderate", "heading-h1-multiple",
            f"Page has {len(h1s)} H1 headings (should have exactly one)",
            str(h1s[1])[:80],
            "Document structure is ambiguous for screen reader users.", "2.4.6", len(h1s)))

    empty = [h for h in headings if not h.get_text(strip=True)]
    if empty:
        issues.append(Issue("Heading Structure", "serious", "heading-empty",
            f"{len(empty)} empty heading(s) found", str(empty[0])[:80],
            "Screen readers announce empty headings, confusing navigation.", "2.4.6", len(empty)))

    levels = [int(h.name[1]) for h in headings]
    for i in range(1, len(levels)):
        if levels[i] > levels[i - 1] + 1:
            issues.append(Issue("Heading Structure", "moderate", "heading-level-skipped",
                f"Heading level skipped: H{levels[i-1]} to H{levels[i]}",
                str(headings[i])[:80],
                "Heading hierarchy is broken, making document navigation unreliable.", "1.3.1", 1))
            break

    return _make_cat("Heading Structure", issues, checks)


def audit_aria_links(soup) -> CategoryResult:
    all_links = soup.find_all("a")
    all_buttons = soup.find_all("button")
    checks = max(len(all_links) + len(all_buttons), 1)
    issues = []

    empty_links = [a for a in all_links
                   if not a.get_text(strip=True) and not a.find("img") and not a.get("aria-label")]
    if empty_links:
        issues.append(Issue("ARIA & Links", "critical", "link-empty",
            f"{len(empty_links)} link(s) have no text content",
            str(empty_links[0])[:80],
            "Screen readers cannot describe where these links lead.", "2.4.4", len(empty_links)))

    generic_texts = {"click here", "here", "read more", "more", "learn more", "click", "link", "this"}
    generic_links = [a for a in all_links if a.get_text(strip=True).lower() in generic_texts]
    if generic_links:
        issues.append(Issue("ARIA & Links", "serious", "link-text-generic",
            f"{len(generic_links)} link(s) use generic text ('click here', 'read more')",
            str(generic_links[0])[:80],
            "Out of context, these links convey no destination or purpose.", "2.4.4", len(generic_links)))

    empty_buttons = [b for b in all_buttons
                     if not b.get_text(strip=True) and not b.get("aria-label") and not b.find("img")]
    if empty_buttons:
        issues.append(Issue("ARIA & Links", "critical", "button-empty",
            f"{len(empty_buttons)} button(s) have no accessible name",
            str(empty_buttons[0])[:80],
            "Screen readers cannot describe what these buttons do.", "4.1.2", len(empty_buttons)))

    all_ids = [el.get("id") for el in soup.find_all(id=True)]
    seen, dupes = set(), set()
    for id_val in all_ids:
        if id_val in seen:
            dupes.add(id_val)
        seen.add(id_val)
    if dupes:
        sample = ", ".join(list(dupes)[:3])
        issues.append(Issue("ARIA & Links", "serious", "duplicate-id",
            f"{len(dupes)} duplicate ID(s) found: {sample}",
            f'id="{list(dupes)[0]}"',
            "Duplicate IDs break ARIA relationships and confuse assistive technology.", "4.1.1", len(dupes)))

    valid_roles = {
        "alert","alertdialog","application","article","banner","button","cell","checkbox",
        "columnheader","combobox","complementary","contentinfo","definition","dialog",
        "directory","document","feed","figure","form","grid","gridcell","group","heading",
        "img","link","list","listbox","listitem","log","main","marquee","math","menu",
        "menubar","menuitem","menuitemcheckbox","menuitemradio","navigation","none","note",
        "option","presentation","progressbar","radio","radiogroup","region","row","rowgroup",
        "rowheader","scrollbar","search","searchbox","separator","slider","spinbutton",
        "status","switch","tab","table","tablist","tabpanel","term","textbox","timer",
        "toolbar","tooltip","tree","treegrid","treeitem"
    }
    invalid_roles = [el for el in soup.find_all(role=True) if el.get("role") not in valid_roles]
    if invalid_roles:
        issues.append(Issue("ARIA & Links", "moderate", "aria-role-invalid",
            f"{len(invalid_roles)} element(s) have invalid ARIA roles",
            str(invalid_roles[0])[:80],
            "Invalid roles are ignored or misinterpreted by assistive technology.", "4.1.1", len(invalid_roles)))

    return _make_cat("ARIA & Links", issues, checks)


def scan_url(url: str) -> ScanResult:
    start = time.time()
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; IDR-Scanner/1.0; +https://idrshield.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return ScanResult(url=url, domain=domain, title="", error="Request timed out after 20 seconds.")
    except requests.exceptions.ConnectionError:
        return ScanResult(url=url, domain=domain, title="", error="Could not connect to the URL.")
    except requests.exceptions.HTTPError as e:
        return ScanResult(url=url, domain=domain, title="", error=f"HTTP error: {e}")
    except Exception as e:
        return ScanResult(url=url, domain=domain, title="", error=str(e))

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    categories = [
        audit_images(soup),
        audit_forms(soup),
        audit_keyboard(soup),
        audit_headings(soup),
        audit_aria_links(soup),
    ]

    critical = sum(c.critical_count for c in categories)
    serious = sum(c.serious_count for c in categories)
    total = sum(i.count for cat in categories for i in cat.issues)
    avg_score = sum(c.score for c in categories) // len(categories)
    overall_status = "fail" if critical > 0 else ("pass" if avg_score >= 80 else "warning")
    duration_ms = int((time.time() - start) * 1000)

    return ScanResult(
        url=url, domain=domain, title=title,
        categories=categories,
        overall_score=avg_score,
        overall_status=overall_status,
        critical_count=critical,
        serious_count=serious,
        total_issues=total,
        scan_duration_ms=duration_ms,
    )
