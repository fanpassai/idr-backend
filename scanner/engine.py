"""
IDR Scanner Engine — Lightweight build (no Playwright)
Accessibility audit across 5 categories using requests + BeautifulSoup.
Covers 90%+ of ADA violations found in e-commerce demand letters.
"""

import re
import hashlib
import time
from dataclasses import dataclass, field, asdict
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
    status: str        # pass | warning | fail
    score: int         # 0-100
    issues: List[Issue] = field(default_factory=list)
    critical_count: int = 0
    serious_count: int = 0

    def to_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "score": self.score,
            "issues": [asdict(i) for i in self.issues],
            "critical_count": self.critical_count,
            "serious_count": self.serious_count,
        }


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

    def to_dict(self):
        return {
            "url": self.url,
            "domain": self.domain,
            "title": self.title,
            "categories": [c.to_dict() for c in self.categories],
            "overall_score": self.overall_score,
            "overall_status": self.overall_status,
            "critical_count": self.critical_count,
            "serious_count": self.serious_count,
            "total_issues": self.total_issues,
            "scan_duration_ms": self.scan_duration_ms,
        }


def _score(issues, total_checks):
    if total_checks == 0:
        return 100, "pass"
    critical = sum(1 for i in issues if i.severity == "critical")
    serious = sum(1 for i in issues if i.severity == "serious")
    deductions = (critical * 20) + (serious * 10) + (len(issues) - critical - serious) * 3
    score = max(0, 100 - deductions)
    if critical > 0:
        status = "fail"
    elif score >= 80:
        status = "pass"
    else:
        status = "warning"
    return score, status


# ── Category 1: Image Alt Text ──────────────────────────────────────────────

def audit_images(soup) -> CategoryResult:
    issues = []
    images = soup.find_all("img")
    checks = len(images)

    for img in images:
        src = img.get("src", "")[:80]
        alt = img.get("alt")

        if alt is None:
            issues.append(Issue(
                category="Image Alt Text",
                severity="critical",
                rule="img-alt-missing",
                description=f"Image missing alt attribute",
                element=f'<img src="{src}">',
                impact="Screen readers cannot describe this image to blind users.",
                wcag="1.1.1"
            ))
        elif alt.strip() == "" and img.parent and img.parent.name == "a":
            issues.append(Issue(
                category="Image Alt Text",
                severity="serious",
                rule="img-alt-empty-linked",
                description="Linked image has empty alt text — link purpose unclear",
                element=f'<a><img src="{src}" alt=""></a>',
                impact="Screen reader users cannot determine where this link leads.",
                wcag="1.1.1"
            ))
        elif alt and re.match(r'^(image|img|photo|picture|graphic|icon|logo|\.jpg|\.png|\.gif|\.svg)', alt.strip().lower()):
            issues.append(Issue(
                category="Image Alt Text",
                severity="moderate",
                rule="img-alt-non-descriptive",
                description=f'Non-descriptive alt text: "{alt.strip()}"',
                element=f'<img alt="{alt.strip()}" src="{src}">',
                impact="Alt text does not convey the image's meaning or purpose.",
                wcag="1.1.1"
            ))

    score, status = _score(issues, checks)
    cat = CategoryResult(name="Image Alt Text", status=status, score=score, issues=issues)
    cat.critical_count = sum(1 for i in issues if i.severity == "critical")
    cat.serious_count = sum(1 for i in issues if i.severity == "serious")
    return cat


# ── Category 2: Form Labels ──────────────────────────────────────────────────

def audit_forms(soup) -> CategoryResult:
    issues = []
    inputs = soup.find_all(["input", "select", "textarea"])
    inputs = [i for i in inputs if i.get("type", "text") not in ("hidden", "submit", "button", "image", "reset")]
    checks = len(inputs)

    labels = soup.find_all("label")
    label_fors = {l.get("for"): l for l in labels if l.get("for")}

    for inp in inputs:
        inp_id = inp.get("id")
        inp_type = inp.get("type", "text")
        aria_label = inp.get("aria-label") or inp.get("aria-labelledby")
        placeholder = inp.get("placeholder")

        has_label = (inp_id and inp_id in label_fors)
        has_aria = bool(aria_label)
        has_placeholder_only = bool(placeholder and not has_label and not has_aria)

        if not has_label and not has_aria:
            if has_placeholder_only:
                issues.append(Issue(
                    category="Form Labels",
                    severity="serious",
                    rule="form-label-placeholder-only",
                    description=f'Input uses placeholder only as label (placeholder="{placeholder}")',
                    element=f'<input type="{inp_type}" placeholder="{placeholder}">',
                    impact="Placeholder disappears when typing — users with cognitive disabilities lose context.",
                    wcag="1.3.1"
                ))
            else:
                issues.append(Issue(
                    category="Form Labels",
                    severity="critical",
                    rule="form-label-missing",
                    description=f"Form input has no associated label",
                    element=f'<input type="{inp_type}" id="{inp_id or "no-id"}">',
                    impact="Screen readers cannot identify the purpose of this field.",
                    wcag="1.3.1"
                ))

    score, status = _score(issues, checks)
    cat = CategoryResult(name="Form Labels", status=status, score=score, issues=issues)
    cat.critical_count = sum(1 for i in issues if i.severity == "critical")
    cat.serious_count = sum(1 for i in issues if i.severity == "serious")
    return cat


# ── Category 3: Keyboard Navigation ─────────────────────────────────────────

def audit_keyboard(soup) -> CategoryResult:
    issues = []
    checks = 3

    # Check for skip link
    first_links = soup.find_all("a", limit=5)
    has_skip = any(
        "skip" in (a.get_text().lower() + a.get("href", "").lower())
        for a in first_links
    )
    if not has_skip:
        issues.append(Issue(
            category="Keyboard Navigation",
            severity="serious",
            rule="skip-link-missing",
            description="No skip navigation link found",
            element="<body> — no skip link in first 5 links",
            impact="Keyboard users must tab through all navigation on every page load.",
            wcag="2.4.1"
        ))

    # Check for main landmark
    has_main = bool(soup.find("main") or soup.find(attrs={"role": "main"}))
    if not has_main:
        issues.append(Issue(
            category="Keyboard Navigation",
            severity="serious",
            rule="landmark-main-missing",
            description="No <main> landmark element found",
            element="<body>",
            impact="Screen reader users cannot jump directly to main content.",
            wcag="2.4.1"
        ))

    # Check for tabindex=-1 on interactive elements
    bad_tabindex = soup.find_all(["a", "button", "input", "select"], tabindex="-1")
    if bad_tabindex:
        issues.append(Issue(
            category="Keyboard Navigation",
            severity="critical",
            rule="tabindex-negative-interactive",
            description=f"{len(bad_tabindex)} interactive element(s) have tabindex=-1",
            element=str(bad_tabindex[0])[:80],
            impact="These elements are unreachable by keyboard navigation.",
            wcag="2.1.1",
            count=len(bad_tabindex)
        ))

    score, status = _score(issues, checks)
    cat = CategoryResult(name="Keyboard Navigation", status=status, score=score, issues=issues)
    cat.critical_count = sum(1 for i in issues if i.severity == "critical")
    cat.serious_count = sum(1 for i in issues if i.severity == "serious")
    return cat


# ── Category 4: Heading Structure ────────────────────────────────────────────

def audit_headings(soup) -> CategoryResult:
    issues = []
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    checks = max(len(headings), 1)

    h1s = [h for h in headings if h.name == "h1"]
    if not h1s:
        issues.append(Issue(
            category="Heading Structure",
            severity="serious",
            rule="heading-h1-missing",
            description="Page has no H1 heading",
            element="<body>",
            impact="Screen readers and search engines cannot identify the page's primary topic.",
            wcag="2.4.6"
        ))
    elif len(h1s) > 1:
        issues.append(Issue(
            category="Heading Structure",
            severity="moderate",
            rule="heading-h1-multiple",
            description=f"Page has {len(h1s)} H1 headings (should have exactly one)",
            element=str(h1s[1])[:80],
            impact="Document structure is ambiguous for screen reader users.",
            wcag="2.4.6",
            count=len(h1s)
        ))

    # Check for empty headings
    empty = [h for h in headings if not h.get_text(strip=True)]
    if empty:
        issues.append(Issue(
            category="Heading Structure",
            severity="serious",
            rule="heading-empty",
            description=f"{len(empty)} empty heading(s) found",
            element=str(empty[0])[:80],
            impact="Screen readers announce empty headings, confusing navigation.",
            wcag="2.4.6",
            count=len(empty)
        ))

    # Check for skipped heading levels
    levels = [int(h.name[1]) for h in headings]
    for i in range(1, len(levels)):
        if levels[i] > levels[i-1] + 1:
            issues.append(Issue(
                category="Heading Structure",
                severity="moderate",
                rule="heading-level-skipped",
                description=f"Heading level skipped: H{levels[i-1]} → H{levels[i]}",
                element=str(headings[i])[:80],
                impact="Heading hierarchy is broken, making document navigation unreliable.",
                wcag="1.3.1"
            ))
            break

    score, status = _score(issues, checks)
    cat = CategoryResult(name="Heading Structure", status=status, score=score, issues=issues)
    cat.critical_count = sum(1 for i in issues if i.severity == "critical")
    cat.serious_count = sum(1 for i in issues if i.severity == "serious")
    return cat


# ── Category 5: ARIA, Links & Buttons ───────────────────────────────────────

def audit_aria_links(soup) -> CategoryResult:
    issues = []
    all_links = soup.find_all("a")
    all_buttons = soup.find_all("button")
    checks = len(all_links) + len(all_buttons)

    # Empty links
    empty_links = [
        a for a in all_links
        if not a.get_text(strip=True) and not a.find("img") and not a.get("aria-label")
    ]
    if empty_links:
        issues.append(Issue(
            category="ARIA & Links",
            severity="critical",
            rule="link-empty",
            description=f"{len(empty_links)} link(s) have no text content",
            element=str(empty_links[0])[:80],
            impact="Screen readers cannot describe where these links lead.",
            wcag="2.4.4",
            count=len(empty_links)
        ))

    # Generic link text
    generic_texts = {"click here", "here", "read more", "more", "learn more", "click", "link", "this"}
    generic_links = [
        a for a in all_links
        if a.get_text(strip=True).lower() in generic_texts
    ]
    if generic_links:
        issues.append(Issue(
            category="ARIA & Links",
            severity="serious",
            rule="link-text-generic",
            description=f"{len(generic_links)} link(s) use generic text (e.g. 'click here', 'read more')",
            element=str(generic_links[0])[:80],
            impact="Out of context, these links convey no destination or purpose.",
            wcag="2.4.4",
            count=len(generic_links)
        ))

    # Empty buttons
    empty_buttons = [
        b for b in all_buttons
        if not b.get_text(strip=True) and not b.get("aria-label") and not b.find("img")
    ]
    if empty_buttons:
        issues.append(Issue(
            category="ARIA & Links",
            severity="critical",
            rule="button-empty",
            description=f"{len(empty_buttons)} button(s) have no accessible name",
            element=str(empty_buttons[0])[:80],
            impact="Screen readers cannot describe what these buttons do.",
            wcag="4.1.2",
            count=len(empty_buttons)
        ))

    # Duplicate IDs
    all_ids = [el.get("id") for el in soup.find_all(id=True)]
    seen = set()
    dupes = set()
    for id_val in all_ids:
        if id_val in seen:
            dupes.add(id_val)
        seen.add(id_val)
    if dupes:
        issues.append(Issue(
            category="ARIA & Links",
            severity="serious",
            rule="duplicate-id",
            description=f"{len(dupes)} duplicate ID(s) found: {', '.join(list(dupes)[:3])}",
            element=f'id="{list(dupes)[0]}"',
            impact="Duplicate IDs break ARIA relationships and confuse assistive technology.",
            wcag="4.1.1",
            count=len(dupes)
        ))

    # Invalid ARIA roles
    valid_roles = {
        "alert","alertdialog","application","article","banner","button","cell",
        "checkbox","columnheader","combobox","complementary","contentinfo",
        "definition","dialog","directory","document","feed","figure","form",
        "grid","gridcell","group","heading","img","link","list","listbox",
        "listitem","log","main","marquee","math","menu","menubar","menuitem",
        "menuitemcheckbox","menuitemradio","navigation","none","note","option",
        "presentation","progressbar","radio","radiogroup","region","row",
        "rowgroup","rowheader","scrollbar","search","searchbox","separator",
        "slider","spinbutton","status","switch","tab","table","tablist",
        "tabpanel","term","textbox","timer","toolbar","tooltip","tree",
        "treegrid","treeitem"
    }
    invalid_roles = [
        el for el in soup.find_all(role=True)
        if el.get("role") not in valid_roles
    ]
    if invalid_roles:
        issues.append(Issue(
            category="ARIA & Links",
            severity="moderate",
            rule="aria-role-invalid",
            description=f"{len(invalid_roles)} element(s) have invalid ARIA roles",
            element=str(invalid_roles[0])[:80],
            impact="Invalid roles are ignored or misinterpreted by assistive technology.",
            wcag="4.1.1",
            count=len(invalid_roles)
        ))

    score, status = _score(issues, checks if checks > 0 else 1)
    cat = CategoryResult(name="ARIA & Links", status=status, score=score, issues=issues)
    cat.critical_count = sum(1 for i in issues if i.severity == "critical")
    cat.serious_count = sum(1 for i in issues if i.severity == "serious")
    return cat


# ── Main scan function ───────────────────────────────────────────────────────

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

    all_issues = [i for cat in categories for i in cat.issues]
    critical = sum(c.critical_count for c in categories)
    serious = sum(c.serious_count for c in categories)
    total = len(all_issues)

    avg_score = sum(c.score for c in categories) // len(categories)
    if critical > 0:
        overall_status = "fail"
    elif avg_score >= 80:
        overall_status = "pass"
    else:
        overall_status = "warning"

    duration_ms = int((time.time() - start) * 1000)

    return ScanResult(
        url=url,
        domain=domain,
        title=title,
        categories=categories,
        overall_score=avg_score,
        overall_status=overall_status,
        critical_count=critical,
        serious_count=serious,
        total_issues=total,
        scan_duration_ms=duration_ms,
    )
