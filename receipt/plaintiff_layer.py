"""
IDR Plaintiff Simulation Layer
Risk scoring, settlement range estimation, and comparable case analysis.
Reframes the receipt from compliance tool to intelligence platform.
"""

from typing import Optional


# ── Comparable ADA Case Database ─────────────────────────────────────────────

COMPARABLE_CASES = [
    {
        "case": "Robles v. Domino's Pizza LLC",
        "citation": "913 F.3d 898 (9th Cir. 2019)",
        "violation_types": ["img-alt-missing", "form-label-missing", "link-empty"],
        "wcag_standards": ["1.1.1", "1.3.1", "2.4.4"],
        "outcome": "Plaintiff prevailed. Site required to conform to WCAG 2.0. "
                   "Established that ADA applies to websites of brick-and-mortar businesses.",
        "relevance_tags": ["image_alt", "form_labels", "e-commerce"],
    },
    {
        "case": "Gil v. Winn-Dixie Stores, Inc.",
        "citation": "242 F. Supp. 3d 1315 (S.D. Fla. 2017)",
        "violation_types": ["landmark-main-missing", "skip-link-missing", "heading-h1-missing"],
        "wcag_standards": ["2.4.1", "2.4.6", "1.3.1"],
        "outcome": "Judgment for plaintiff. Winn-Dixie required to bring website into "
                   "WCAG 2.0 AA compliance within 3 years. First federal trial win on web accessibility.",
        "relevance_tags": ["navigation", "keyboard", "structure"],
    },
    {
        "case": "Murphy v. Eyebobs LLC",
        "citation": "No. 19-cv-2207 (D. Minn. 2019)",
        "violation_types": ["img-alt-missing", "button-empty", "link-text-generic"],
        "wcag_standards": ["1.1.1", "4.1.2", "2.4.4"],
        "outcome": "Settled. E-commerce retailer agreed to remediate site and pay "
                   "plaintiff's attorney fees. Pattern: serial plaintiff, demand letter to settlement.",
        "relevance_tags": ["image_alt", "buttons", "e-commerce"],
    },
    {
        "case": "Jahoda v. Camp Bow Wow Franchising",
        "citation": "No. 19-cv-00896 (D. Colo. 2019)",
        "violation_types": ["form-label-missing", "form-label-placeholder-only"],
        "wcag_standards": ["1.3.1", "2.4.6"],
        "outcome": "Settled confidentially. Franchise operator required to remediate "
                   "all franchise websites. Form accessibility a primary violation.",
        "relevance_tags": ["form_labels", "checkout"],
    },
    {
        "case": "Mendez v. Apple Inc.",
        "citation": "No. 18-cv-07550 (N.D. Cal. 2019)",
        "violation_types": ["duplicate-id", "aria-role-invalid", "button-empty"],
        "wcag_standards": ["4.1.1", "4.1.2"],
        "outcome": "Dismissed on standing grounds. Technical ARIA violations alone "
                   "insufficient — plaintiff must demonstrate actual barrier to access.",
        "relevance_tags": ["aria", "technical"],
    },
    {
        "case": "Laufer v. Naranda Hotels LLC",
        "citation": "No. 20-cv-2093 (D. Md. 2021)",
        "violation_types": ["img-alt-missing", "link-empty", "skip-link-missing"],
        "wcag_standards": ["1.1.1", "2.4.1", "2.4.4"],
        "outcome": "Pattern: serial ADA plaintiff filed 600+ complaints. "
                   "E-commerce and hospitality sites primary targets. "
                   "Demonstrates high-volume automated scanning for targets.",
        "relevance_tags": ["serial_plaintiff", "e-commerce", "image_alt"],
    },
]

# ── Risk Matrix ───────────────────────────────────────────────────────────────

RISK_LEVELS = {
    "CRITICAL": {
        "label": "CRITICAL",
        "color_hex": "#C0392B",
        "settlement_low": 25000,
        "settlement_high": 95000,
        "description": (
            "This store presents a high-value target for plaintiff firms using automated "
            "scanning tools. The combination of critical violations — particularly in form "
            "labels and image alt text — mirrors the violation profiles in the majority of "
            "successful ADA demand letters. Serial plaintiff firms file these cases at scale; "
            "automated scanners identify targets like this site daily."
        ),
        "demand_probability": "HIGH",
    },
    "HIGH": {
        "label": "HIGH",
        "color_hex": "#E67E22",
        "settlement_low": 12500,
        "settlement_high": 35000,
        "description": (
            "Significant accessibility barriers exist that have been the basis for ADA "
            "demand letters in comparable cases. Critical violations in interactive elements "
            "— forms, buttons, and navigation — constitute the core violation pattern "
            "plaintiff attorneys target in e-commerce litigation."
        ),
        "demand_probability": "MODERATE-HIGH",
    },
    "MODERATE": {
        "label": "MODERATE",
        "color_hex": "#D4AC0D",
        "settlement_low": 5000,
        "settlement_high": 15000,
        "description": (
            "Serious accessibility issues present that, while not all critical, represent "
            "documented barriers to disabled users. Plaintiff firms targeting lower-volume "
            "demand letters frequently cite violations at this severity level. "
            "Remediation is advisable before a scan by an opposing party occurs."
        ),
        "demand_probability": "MODERATE",
    },
    "LOW": {
        "label": "LOW",
        "color_hex": "#27AE60",
        "settlement_low": 2500,
        "settlement_high": 8000,
        "description": (
            "Minor accessibility issues detected. No critical violations found. "
            "While no site is entirely risk-free, the violation profile here is "
            "significantly below the threshold typically targeted by plaintiff firms. "
            "Remediation of remaining issues is recommended to achieve full compliance."
        ),
        "demand_probability": "LOW",
    },
}


# ── Risk Scoring Logic ────────────────────────────────────────────────────────

def calculate_plaintiff_risk(scan: dict) -> dict:
    """
    Compute plaintiff risk level from scan data.
    Returns full risk assessment dict for inclusion in receipt.
    """
    critical_count = scan.get("critical_count", 0)
    total_issues = scan.get("total_issues", 0)
    categories = scan.get("categories", [])

    # Extract all rule names from issues
    all_rules = []
    for cat in categories:
        for issue in cat.get("issues", []):
            all_rules.append(issue.get("rule", ""))

    serious_count = sum(
        1 for cat in categories
        for issue in cat.get("issues", [])
        if issue.get("severity") == "serious"
    )

    # Check for high-value violation patterns
    has_form_critical = any(
        "form-label-missing" in r for r in all_rules
    )
    has_checkout_barrier = has_form_critical  # Form labels block checkout for screen reader users
    has_image_critical = any("img-alt-missing" in r for r in all_rules)
    has_nav_issues = any(r in ("skip-link-missing", "landmark-main-missing") for r in all_rules)

    # Determine risk level
    if critical_count >= 5 or (critical_count >= 2 and has_checkout_barrier):
        risk_key = "CRITICAL"
    elif critical_count >= 2 or (critical_count >= 1 and serious_count >= 5):
        risk_key = "HIGH"
    elif critical_count >= 1 or serious_count >= 5:
        risk_key = "MODERATE"
    else:
        risk_key = "LOW"

    risk = RISK_LEVELS[risk_key]

    # Find matching comparable cases
    matched_cases = _match_comparable_cases(all_rules, risk_key)

    # Build violation-to-litigation mapping
    litigation_flags = _build_litigation_flags(categories)

    return {
        "risk_level": risk_key,
        "risk_label": risk["label"],
        "risk_color": risk["color_hex"],
        "demand_probability": risk["demand_probability"],
        "settlement_range": {
            "low": risk["settlement_low"],
            "high": risk["settlement_high"],
            "formatted_low": f"${risk['settlement_low']:,}",
            "formatted_high": f"${risk['settlement_high']:,}",
        },
        "description": risk["description"],
        "comparable_cases": matched_cases,
        "litigation_flags": litigation_flags,
        "critical_count": critical_count,
        "serious_count": serious_count,
        "checkout_barrier": has_checkout_barrier,
        "has_image_violations": has_image_critical,
        "has_navigation_violations": has_nav_issues,
    }


def _match_comparable_cases(rules: list, risk_key: str) -> list:
    """Match 2-3 most relevant comparable cases based on violation rules."""
    scored = []
    for case in COMPARABLE_CASES:
        score = sum(1 for r in rules if r in case["violation_types"])
        if score > 0:
            scored.append((score, case))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:3]]


def _build_litigation_flags(categories: list) -> list:
    """
    Map each critical/serious issue to its litigation relevance.
    Returns list of flagged violations with legal context.
    """
    HIGH_VALUE_RULES = {
        "img-alt-missing": {
            "litigation_value": "HIGH",
            "legal_note": "WCAG 1.1.1 failure. Primary violation in Robles v. Domino's and "
                          "hundreds of demand letters annually. Screen reader users cannot "
                          "perceive product images — direct barrier to purchase.",
        },
        "form-label-missing": {
            "litigation_value": "CRITICAL",
            "legal_note": "WCAG 1.3.1 failure. Checkout and contact forms without labels "
                          "constitute a complete barrier to commerce for blind users. "
                          "Courts have found this creates a cognizable ADA injury.",
        },
        "form-label-placeholder-only": {
            "litigation_value": "HIGH",
            "legal_note": "WCAG 1.3.1 failure. Placeholder-only labels disappear on input, "
                          "creating a barrier for users with cognitive disabilities and "
                          "those using screen readers.",
        },
        "skip-link-missing": {
            "litigation_value": "MODERATE",
            "legal_note": "WCAG 2.4.1 failure. Keyboard users must navigate through entire "
                          "header/navigation on every page. Cited in Gil v. Winn-Dixie. "
                          "Disproportionate burden on motor-impaired users.",
        },
        "landmark-main-missing": {
            "litigation_value": "MODERATE",
            "legal_note": "WCAG 2.4.1 failure. Screen reader users cannot navigate directly "
                          "to page content. Cited alongside skip-link violations in ADA complaints.",
        },
        "link-empty": {
            "litigation_value": "HIGH",
            "legal_note": "WCAG 2.4.4 failure. Empty links have no accessible name — "
                          "screen reader users hear 'link' with no destination. "
                          "Cited in multiple e-commerce ADA demand letters.",
        },
        "button-empty": {
            "litigation_value": "HIGH",
            "legal_note": "WCAG 4.1.2 failure. Unlabeled buttons — common in cart and "
                          "checkout flows — create a direct barrier to completing a purchase.",
        },
        "link-text-generic": {
            "litigation_value": "MODERATE",
            "legal_note": "WCAG 2.4.4 failure. 'Click here' and 'read more' links "
                          "convey no purpose out of context. Cited in lower-value demand letters.",
        },
        "duplicate-id": {
            "litigation_value": "MODERATE",
            "legal_note": "WCAG 4.1.1 failure. Duplicate IDs break ARIA relationships "
                          "and cause unpredictable screen reader behavior.",
        },
        "tabindex-negative-interactive": {
            "litigation_value": "CRITICAL",
            "legal_note": "WCAG 2.1.1 failure. Interactive elements removed from tab order "
                          "are completely inaccessible to keyboard-only users.",
        },
        "heading-h1-missing": {
            "litigation_value": "MODERATE",
            "legal_note": "WCAG 2.4.6 failure. Missing H1 prevents screen reader users "
                          "from identifying page context. Supporting violation in ADA complaints.",
        },
        "img-alt-empty-linked": {
            "litigation_value": "HIGH",
            "legal_note": "WCAG 1.1.1 failure. Linked images with empty alt text leave "
                          "screen reader users unable to determine link destinations.",
        },
    }

    flags = []
    for cat in categories:
        for issue in cat.get("issues", []):
            rule = issue.get("rule", "")
            if rule in HIGH_VALUE_RULES:
                flag_data = HIGH_VALUE_RULES[rule]
                flags.append({
                    "rule": rule,
                    "category": issue.get("category"),
                    "severity": issue.get("severity"),
                    "wcag": issue.get("wcag"),
                    "litigation_value": flag_data["litigation_value"],
                    "legal_note": flag_data["legal_note"],
                    "element": issue.get("element", ""),
                    "count": issue.get("count", 1),
                })

    return flags
