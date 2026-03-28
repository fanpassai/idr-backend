"""
IDR Scanner Engine
Accessibility audit across 5 categories using Playwright + DOM analysis.
"""

import re
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional
from playwright.sync_api import sync_playwright, Page


# ─────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────

@dataclass
class Issue:
    category: str
    severity: str          # critical | serious | moderate | minor
    rule: str
    description: str
    element: str           # CSS selector or descriptive tag
    impact: str            # plain-English impact statement
    wcag: str              # WCAG criterion e.g. "1.1.1"
    count: int = 1


@dataclass
class CategoryResult:
    name: str
    slug: str
    passed: int = 0
    failed: int = 0
    issues: list = field(default_factory=list)

    @property
    def score(self) -> int:
        total = self.passed + self.failed
        return round((self.passed / total) * 100) if total > 0 else 100

    @property
    def status(self) -> str:
        if self.score >= 90:   return "pass"
        if self.score >= 60:   return "warning"
        return "fail"


@dataclass
class ScanResult:
    url: str
    domain: str
    scan_duration_ms: int
    categories: list = field(default_factory=list)
    page_title: str = ""
    error: Optional[str] = None

    @property
    def total_issues(self) -> int:
        return sum(c.failed for c in self.categories)

    @property
    def critical_count(self) -> int:
        count = 0
        for c in self.categories:
            for issue in c.issues:
                if issue.severity == "critical":
                    count += issue.count
        return count

    @property
    def overall_score(self) -> int:
        if not self.categories:
            return 0
        return round(sum(c.score for c in self.categories) / len(self.categories))

    @property
    def overall_status(self) -> str:
        if self.critical_count > 0:
            return "fail"
        if self.overall_score >= 85:
            return "pass"
        if self.overall_score >= 60:
            return "warning"
        return "fail"


# ─────────────────────────────────────────────
# Category 1 — Alt Text
# ─────────────────────────────────────────────

def audit_alt_text(page: Page) -> CategoryResult:
    result = CategoryResult(name="Image Alt Text", slug="alt_text")

    data = page.evaluate("""() => {
        const imgs = Array.from(document.querySelectorAll('img'));
        return imgs.map(img => ({
            src: img.getAttribute('src') || '',
            alt: img.getAttribute('alt'),
            role: img.getAttribute('role'),
            ariaLabel: img.getAttribute('aria-label'),
            ariaHidden: img.getAttribute('aria-hidden'),
            isDecorative: img.getAttribute('role') === 'presentation',
            inLink: !!img.closest('a'),
            linkText: img.closest('a') ? (img.closest('a').textContent || '').trim() : '',
            outerHTML: img.outerHTML.substring(0, 120)
        }));
    }""")

    missing = []
    empty_meaningful = []

    for img in data:
        # Skip aria-hidden decorative images
        if img.get('ariaHidden') == 'true' or img.get('isDecorative'):
            result.passed += 1
            continue

        alt = img.get('alt')
        aria = img.get('ariaLabel', '') or ''

        if alt is None and not aria:
            # No alt attribute at all
            missing.append(img)
        elif alt == '' and not aria:
            # Empty alt — acceptable only if decorative
            if img.get('inLink') and not img.get('linkText'):
                empty_meaningful.append(img)
            else:
                result.passed += 1
        else:
            # Has alt text — check for lazy/bad values
            lazy_patterns = ['image', 'photo', 'picture', 'img', 'graphic', 'icon', '.jpg', '.png', '.webp']
            alt_lower = (alt or '').lower()
            if any(p in alt_lower for p in lazy_patterns) and len(alt or '') < 20:
                result.failed += 1
                result.issues.append(Issue(
                    category="alt_text",
                    severity="moderate",
                    rule="no-redundant-alt",
                    description=f'Image alt text is non-descriptive: "{alt}"',
                    element="img",
                    impact="Screen reader users get no useful information about this image.",
                    wcag="1.1.1",
                    count=1
                ))
            else:
                result.passed += 1

    if missing:
        result.failed += len(missing)
        result.issues.append(Issue(
            category="alt_text",
            severity="critical",
            rule="image-alt",
            description="Images are missing alt attributes entirely.",
            element="img",
            impact="Screen reader users cannot understand the purpose of these images.",
            wcag="1.1.1",
            count=len(missing)
        ))

    if empty_meaningful:
        result.failed += len(empty_meaningful)
        result.issues.append(Issue(
            category="alt_text",
            severity="serious",
            rule="image-link-alt",
            description="Linked images with empty alt text and no surrounding link text.",
            element="a > img",
            impact="Screen reader users cannot determine where these links navigate.",
            wcag="1.1.1",
            count=len(empty_meaningful)
        ))

    return result


# ─────────────────────────────────────────────
# Category 2 — Form Labels
# ─────────────────────────────────────────────

def audit_form_labels(page: Page) -> CategoryResult:
    result = CategoryResult(name="Form Labels", slug="form_labels")

    data = page.evaluate("""() => {
        const inputs = Array.from(document.querySelectorAll(
            'input:not([type="hidden"]):not([type="submit"]):not([type="reset"]):not([type="button"]), textarea, select'
        ));
        return inputs.map(el => {
            const id = el.getAttribute('id');
            const name = el.getAttribute('name');
            const type = el.getAttribute('type') || el.tagName.toLowerCase();
            const ariaLabel = el.getAttribute('aria-label');
            const ariaLabelledBy = el.getAttribute('aria-labelledby');
            const placeholder = el.getAttribute('placeholder');
            const title = el.getAttribute('title');
            const hasLabel = id ? !!document.querySelector('label[for="' + id + '"]') : false;
            const isWrapped = !!el.closest('label');
            return { id, name, type, ariaLabel, ariaLabelledBy, placeholder, title, hasLabel, isWrapped };
        });
    }""")

    for el in data:
        has_proper_label = (
            el.get('hasLabel') or
            el.get('isWrapped') or
            el.get('ariaLabel') or
            el.get('ariaLabelledBy')
        )

        if has_proper_label:
            result.passed += 1
        elif el.get('placeholder') or el.get('title'):
            # Placeholder/title as label — technically accessible but not ideal
            result.failed += 1
            result.issues.append(Issue(
                category="form_labels",
                severity="moderate",
                rule="label-title-only",
                description=f'Form field relies on placeholder/title as its only label (type: {el.get("type", "input")}).',
                element="input, textarea, select",
                impact="Placeholders disappear when typing. Screen readers may not consistently announce them.",
                wcag="1.3.1",
                count=1
            ))
        else:
            result.failed += 1
            result.issues.append(Issue(
                category="form_labels",
                severity="critical",
                rule="label",
                description=f'Form field has no accessible label (type: {el.get("type", "input")}, name: {el.get("name", "unknown")}).',
                element="input, textarea, select",
                impact="Screen reader users cannot identify the purpose of this field.",
                wcag="1.3.1",
                count=1
            ))

    # Deduplicate by rule + severity
    result.issues = _deduplicate_issues(result.issues)
    return result


# ─────────────────────────────────────────────
# Category 3 — Keyboard Navigation
# ─────────────────────────────────────────────

def audit_keyboard_nav(page: Page) -> CategoryResult:
    result = CategoryResult(name="Keyboard Navigation", slug="keyboard_nav")

    data = page.evaluate("""() => {
        const interactive = Array.from(document.querySelectorAll(
            'a, button, input, select, textarea, [tabindex], [onclick], [role="button"], [role="link"], [role="menuitem"]'
        ));

        const trapped = [];
        const missingFocus = [];
        const negativeTabs = [];
        const skipLinks = document.querySelectorAll('a[href^="#"]');
        const hasSkipNav = Array.from(skipLinks).some(a =>
            (a.textContent || '').toLowerCase().includes('skip') ||
            (a.textContent || '').toLowerCase().includes('main')
        );

        interactive.forEach(el => {
            const tabindex = el.getAttribute('tabindex');
            const tag = el.tagName.toLowerCase();

            if (tabindex === '-1' && (tag === 'a' || tag === 'button')) {
                negativeTabs.push({ tag, text: (el.textContent || '').trim().substring(0, 40) });
            }
        });

        // Check if there are modals/dialogs that might trap focus
        const dialogs = document.querySelectorAll('[role="dialog"], [aria-modal="true"], .modal, #modal');

        return {
            interactiveCount: interactive.length,
            negativeTabs,
            hasSkipNav,
            dialogCount: dialogs.length,
            hasMainLandmark: !!document.querySelector('main, [role="main"]'),
            hasNavLandmark: !!document.querySelector('nav, [role="navigation"]'),
        };
    }""")

    # Skip navigation
    if not data.get('hasSkipNav') and data.get('interactiveCount', 0) > 5:
        result.failed += 1
        result.issues.append(Issue(
            category="keyboard_nav",
            severity="serious",
            rule="skip-link",
            description='No skip navigation link detected.',
            element="body",
            impact="Keyboard users must tab through all navigation on every page before reaching main content.",
            wcag="2.4.1"
        ))
    else:
        result.passed += 1

    # Landmarks
    if data.get('hasMainLandmark'):
        result.passed += 1
    else:
        result.failed += 1
        result.issues.append(Issue(
            category="keyboard_nav",
            severity="serious",
            rule="landmark-main",
            description='No <main> landmark element found.',
            element="body",
            impact="Screen reader and keyboard users cannot jump directly to main content.",
            wcag="1.3.6"
        ))

    if data.get('hasNavLandmark'):
        result.passed += 1
    else:
        result.failed += 1
        result.issues.append(Issue(
            category="keyboard_nav",
            severity="moderate",
            rule="landmark-nav",
            description='No <nav> landmark element found.',
            element="body",
            impact="Screen reader users cannot navigate to the site's navigation region.",
            wcag="1.3.6"
        ))

    # Negative tabindex on interactive elements
    neg = data.get('negativeTabs', [])
    if neg:
        result.failed += len(neg)
        result.issues.append(Issue(
            category="keyboard_nav",
            severity="serious",
            rule="tabindex-negative",
            description=f'{len(neg)} interactive element(s) have tabindex="-1", removing them from keyboard flow.',
            element="a, button",
            impact="These controls are unreachable by keyboard-only users.",
            wcag="2.1.1",
            count=len(neg)
        ))
    else:
        result.passed += 1

    return result


# ─────────────────────────────────────────────
# Category 4 — Heading Structure
# ─────────────────────────────────────────────

def audit_heading_structure(page: Page) -> CategoryResult:
    result = CategoryResult(name="Heading Structure", slug="heading_structure")

    data = page.evaluate("""() => {
        const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'));
        return headings.map(h => ({
            level: parseInt(h.tagName[1]),
            text: (h.textContent || '').trim().substring(0, 80),
            empty: !(h.textContent || '').trim()
        }));
    }""")

    if not data:
        result.failed += 1
        result.issues.append(Issue(
            category="heading_structure",
            severity="serious",
            rule="page-has-heading",
            description='No headings found on the page.',
            element="body",
            impact="Screen reader users cannot navigate or understand the page structure.",
            wcag="2.4.6"
        ))
        return result

    # H1 check
    h1s = [h for h in data if h['level'] == 1]
    if len(h1s) == 0:
        result.failed += 1
        result.issues.append(Issue(
            category="heading_structure",
            severity="serious",
            rule="page-has-h1",
            description='No H1 heading found. Every page should have exactly one H1.',
            element="body",
            impact="Screen reader users and search engines cannot identify the page's primary topic.",
            wcag="2.4.6"
        ))
    elif len(h1s) > 1:
        result.failed += 1
        result.issues.append(Issue(
            category="heading_structure",
            severity="moderate",
            rule="h1-single",
            description=f'Multiple H1 headings found ({len(h1s)}). Only one H1 is recommended per page.',
            element="h1",
            impact="Creates ambiguity about the primary topic of the page.",
            wcag="2.4.6",
            count=len(h1s)
        ))
    else:
        result.passed += 1

    # Heading hierarchy — detect skipped levels
    skipped = []
    prev_level = 0
    for h in data:
        if prev_level > 0 and h['level'] > prev_level + 1:
            skipped.append(f"H{prev_level} → H{h['level']} (skipped H{prev_level+1})")
        prev_level = h['level']

    if skipped:
        result.failed += len(skipped)
        result.issues.append(Issue(
            category="heading_structure",
            severity="moderate",
            rule="heading-order",
            description=f'Heading levels are skipped in {len(skipped)} place(s): {"; ".join(skipped[:3])}',
            element="h1-h6",
            impact="Screen reader users navigating by heading encounter a disjointed, confusing outline.",
            wcag="1.3.1",
            count=len(skipped)
        ))
    else:
        result.passed += 1

    # Empty headings
    empty = [h for h in data if h['empty']]
    if empty:
        result.failed += len(empty)
        result.issues.append(Issue(
            category="heading_structure",
            severity="serious",
            rule="empty-heading",
            description=f'{len(empty)} empty heading element(s) found.',
            element="h1-h6",
            impact="Screen readers announce empty headings, creating confusion and noise.",
            wcag="2.4.6",
            count=len(empty)
        ))
    else:
        result.passed += 1

    return result


# ─────────────────────────────────────────────
# Category 5 — ARIA, Contrast & Link Labels
# ─────────────────────────────────────────────

def audit_aria_links_contrast(page: Page) -> CategoryResult:
    result = CategoryResult(name="ARIA, Links & Contrast", slug="aria_links_contrast")

    data = page.evaluate("""() => {
        // Links
        const links = Array.from(document.querySelectorAll('a[href]'));
        const emptyLinks = links.filter(a => {
            const text = (a.textContent || '').trim();
            const ariaLabel = a.getAttribute('aria-label');
            const ariaLabelledBy = a.getAttribute('aria-labelledby');
            const title = a.getAttribute('title');
            const hasImg = !!a.querySelector('img[alt]');
            return !text && !ariaLabel && !ariaLabelledBy && !title && !hasImg;
        });
        const genericLinks = links.filter(a => {
            const text = (a.textContent || '').trim().toLowerCase();
            return ['click here', 'read more', 'here', 'more', 'learn more', 'this link'].includes(text);
        });

        // ARIA
        const invalidRoles = [];
        const validRoles = ['button','link','navigation','main','banner','contentinfo','search',
            'complementary','region','article','section','heading','list','listitem',
            'checkbox','radio','textbox','combobox','menuitem','tab','tabpanel',
            'dialog','alert','alertdialog','status','log','timer','progressbar',
            'slider','spinbutton','grid','gridcell','row','rowgroup','columnheader',
            'rowheader','tree','treeitem','treegrid','menu','menubar','toolbar','tooltip',
            'application','document','presentation','none','img','figure','form','table',
            'cell','term','definition','note','group','radiogroup','listbox','option',
            'scrollbar','separator','switch','math','marquee'];

        document.querySelectorAll('[role]').forEach(el => {
            const role = (el.getAttribute('role') || '').toLowerCase().trim();
            if (role && !validRoles.includes(role)) {
                invalidRoles.push({ role, tag: el.tagName.toLowerCase() });
            }
        });

        const ariaOnNative = Array.from(document.querySelectorAll(
            'button[role], a[role], input[role], select[role], textarea[role]'
        )).filter(el => {
            const role = el.getAttribute('role');
            const tag = el.tagName.toLowerCase();
            const nativeRoles = { button: 'button', a: 'link', input: 'textbox' };
            return role && nativeRoles[tag] && role !== nativeRoles[tag];
        });

        // IDs — duplicate IDs are a common ARIA breakage point
        const allIds = Array.from(document.querySelectorAll('[id]')).map(el => el.id);
        const duplicateIds = allIds.filter((id, i) => allIds.indexOf(id) !== i);

        // Buttons without accessible names
        const emptyButtons = Array.from(document.querySelectorAll('button, [role="button"]')).filter(btn => {
            const text = (btn.textContent || '').trim();
            const ariaLabel = btn.getAttribute('aria-label');
            const ariaLabelledBy = btn.getAttribute('aria-labelledby');
            const title = btn.getAttribute('title');
            return !text && !ariaLabel && !ariaLabelledBy && !title;
        });

        return {
            emptyLinks: emptyLinks.length,
            genericLinks: genericLinks.map(a => (a.textContent || '').trim()),
            invalidRoles,
            ariaOnNativeCount: ariaOnNative.length,
            duplicateIds,
            emptyButtons: emptyButtons.length,
            totalLinks: links.length,
            totalButtons: document.querySelectorAll('button, [role="button"]').length
        };
    }""")

    # Empty links
    if data['emptyLinks'] > 0:
        result.failed += data['emptyLinks']
        result.issues.append(Issue(
            category="aria_links_contrast",
            severity="critical",
            rule="link-name",
            description=f'{data["emptyLinks"]} link(s) have no accessible name.',
            element="a[href]",
            impact="Screen reader users cannot determine the purpose of these links.",
            wcag="4.1.2",
            count=data['emptyLinks']
        ))
    else:
        result.passed += 1

    # Generic link text
    generic = data.get('genericLinks', [])
    unique_generic = list(set(generic))
    if unique_generic:
        result.failed += len(unique_generic)
        result.issues.append(Issue(
            category="aria_links_contrast",
            severity="serious",
            rule="link-generic-text",
            description='Generic link text found: ' + ", ".join(f'"{g}"' for g in unique_generic[:4]) + '.',
            element="a[href]",
            impact='When screen reader users scan links out of context, "click here" or "read more" conveys nothing.',
            wcag="2.4.4",
            count=len(generic)
        ))
    else:
        result.passed += 1

    # Invalid ARIA roles
    invalid = data.get('invalidRoles', [])
    if invalid:
        result.failed += len(invalid)
        result.issues.append(Issue(
            category="aria_links_contrast",
            severity="serious",
            rule="aria-roles",
            description=f'Invalid ARIA role(s) found: {", ".join(set(r["role"] for r in invalid[:3]))}.',
            element="[role]",
            impact="Assistive technologies cannot correctly interpret elements with invalid roles.",
            wcag="4.1.2",
            count=len(invalid)
        ))
    else:
        result.passed += 1

    # Duplicate IDs
    dups = data.get('duplicateIds', [])
    unique_dups = list(set(dups))
    if unique_dups:
        result.failed += len(unique_dups)
        result.issues.append(Issue(
            category="aria_links_contrast",
            severity="serious",
            rule="duplicate-id",
            description='Duplicate IDs found: ' + ', '.join('#' + d for d in unique_dups[:4]) + '.',
            element="[id]",
            impact="ARIA references using these IDs will target the wrong element or break entirely.",
            wcag="4.1.1",
            count=len(unique_dups)
        ))
    else:
        result.passed += 1

    # Empty buttons
    if data['emptyButtons'] > 0:
        result.failed += data['emptyButtons']
        result.issues.append(Issue(
            category="aria_links_contrast",
            severity="critical",
            rule="button-name",
            description=f'{data["emptyButtons"]} button(s) have no accessible name.',
            element="button",
            impact="Screen reader users cannot determine what these buttons do.",
            wcag="4.1.2",
            count=data['emptyButtons']
        ))
    else:
        result.passed += 1

    return result


# ─────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────

def _deduplicate_issues(issues: list) -> list:
    seen = {}
    for issue in issues:
        key = (issue.rule, issue.severity)
        if key in seen:
            seen[key].count += issue.count
            seen[key].failed = seen[key].count
        else:
            seen[key] = issue
    return list(seen.values())


# ─────────────────────────────────────────────
# Main Scanner Entry Point
# ─────────────────────────────────────────────

def scan_url(url: str, timeout_ms: int = 30000) -> ScanResult:
    """
    Run a full IDR accessibility scan on the given URL.
    Returns a ScanResult with all 5 categories populated.
    """
    start = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="IDRScanner/1.0 (accessibility-audit; +https://idrshield.com)"
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(1500)   # let JS render

            title = page.title()
            domain = _extract_domain(url)

            categories = [
                audit_alt_text(page),
                audit_form_labels(page),
                audit_keyboard_nav(page),
                audit_heading_structure(page),
                audit_aria_links_contrast(page),
            ]

            duration = round((time.time() - start) * 1000)

            return ScanResult(
                url=url,
                domain=domain,
                page_title=title,
                scan_duration_ms=duration,
                categories=categories
            )

        except Exception as e:
            duration = round((time.time() - start) * 1000)
            domain = _extract_domain(url)
            return ScanResult(
                url=url,
                domain=domain,
                scan_duration_ms=duration,
                error=str(e)
            )
        finally:
            browser.close()


def scan_html_file(file_path: str) -> ScanResult:
    """Scan a local HTML file — used for testing."""
    return scan_url(f"file://{file_path}")


def _extract_domain(url: str) -> str:
    match = re.search(r'https?://([^/]+)', url)
    if match:
        return match.group(1)
    if url.startswith('file://'):
        return 'local-test'
    return url
