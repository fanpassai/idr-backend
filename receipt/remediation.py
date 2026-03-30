"""
IDR Remediation Guidance
Per-violation before/after code fixes with implementation notes.
"""


REMEDIATION_MAP = {
    "img-alt-missing": {
        "title": "Add Descriptive Alt Text to Images",
        "wcag": "1.1.1",
        "effort": "LOW",
        "before": '<img src="/products/item.jpg">',
        "after": '<img src="/products/item.jpg" alt="Blue leather wallet, front view">',
        "note": (
            "Every <img> element must have an alt attribute. "
            "For product images, describe the item clearly. "
            "For decorative images, use alt=\"\" (empty string) to indicate they can be skipped. "
            "Never omit the alt attribute entirely."
        ),
    },
    "img-alt-empty-linked": {
        "title": "Add Alt Text to Linked Images",
        "wcag": "1.1.1",
        "effort": "LOW",
        "before": '<a href="/products">\n  <img src="/shop-icon.jpg" alt="">\n</a>',
        "after": '<a href="/products">\n  <img src="/shop-icon.jpg" alt="Browse all products">\n</a>',
        "note": (
            "When an image is the only content inside a link, the alt text becomes "
            "the link's accessible name. Describe the destination, not the image appearance."
        ),
    },
    "img-alt-non-descriptive": {
        "title": "Replace Non-Descriptive Alt Text",
        "wcag": "1.1.1",
        "effort": "LOW",
        "before": '<img src="/banner.jpg" alt="image">',
        "after": '<img src="/banner.jpg" alt="Summer sale — 30% off all footwear through August">',
        "note": (
            "Alt text must convey meaning, not just describe the file type. "
            "Avoid: 'image', 'photo', 'graphic', 'icon', 'logo', or filename extensions. "
            "Ask: what would a sighted user learn from seeing this image?"
        ),
    },
    "form-label-missing": {
        "title": "Associate Labels with Form Inputs",
        "wcag": "1.3.1",
        "effort": "LOW",
        "before": '<input type="email" id="user-email">',
        "after": (
            '<label for="user-email">Email address</label>\n'
            '<input type="email" id="user-email" autocomplete="email">'
        ),
        "note": (
            "Every form input needs a <label> element with a 'for' attribute matching "
            "the input's 'id'. Alternatively, use aria-label or aria-labelledby. "
            "Placeholder text alone does NOT constitute a label — "
            "it disappears when the user starts typing."
        ),
    },
    "form-label-placeholder-only": {
        "title": "Add Persistent Labels to Placeholder-Only Inputs",
        "wcag": "1.3.1",
        "effort": "LOW",
        "before": '<input type="text" placeholder="Full name">',
        "after": (
            '<label for="full-name">Full name</label>\n'
            '<input type="text" id="full-name" placeholder="e.g. Jane Smith" '
            'autocomplete="name">'
        ),
        "note": (
            "Placeholders are not a substitute for labels. They disappear on input, "
            "leaving users with cognitive disabilities without context. "
            "Keep the placeholder as a hint, but add a visible <label> element above the field."
        ),
    },
    "skip-link-missing": {
        "title": "Add Skip Navigation Link",
        "wcag": "2.4.1",
        "effort": "LOW",
        "before": "<!-- No skip link -->\n<header>\n  <nav>...</nav>\n</header>",
        "after": (
            '<a class="skip-link" href="#main-content">\n'
            '  Skip to main content\n'
            '</a>\n'
            '<header>\n'
            '  <nav>...</nav>\n'
            '</header>\n'
            '<main id="main-content">\n'
            '  ...\n'
            '</main>\n\n'
            '/* CSS */\n'
            '.skip-link {\n'
            '  position: absolute;\n'
            '  top: -40px;\n'
            '  left: 0;\n'
            '  background: #000;\n'
            '  color: #fff;\n'
            '  padding: 8px;\n'
            '  z-index: 100;\n'
            '}\n'
            '.skip-link:focus {\n'
            '  top: 0;\n'
            '}'
        ),
        "note": (
            "A skip link must be the first focusable element on the page. "
            "It can be visually hidden until focused — but must become visible on focus. "
            "The target (main-content) must exist as an id on the <main> element."
        ),
    },
    "landmark-main-missing": {
        "title": "Add Main Landmark Element",
        "wcag": "2.4.1",
        "effort": "LOW",
        "before": '<div id="content">\n  <!-- page content -->\n</div>',
        "after": '<main id="main-content">\n  <!-- page content -->\n</main>',
        "note": (
            "The <main> element or role=\"main\" is required so screen reader users "
            "can jump directly to the page's primary content. "
            "There should be exactly one <main> per page. "
            "Add id=\"main-content\" to pair it with your skip link."
        ),
    },
    "tabindex-negative-interactive": {
        "title": "Remove Negative Tabindex from Interactive Elements",
        "wcag": "2.1.1",
        "effort": "LOW",
        "before": '<button tabindex="-1">Add to cart</button>',
        "after": '<button>Add to cart</button>',
        "note": (
            "tabindex=\"-1\" removes an element from the tab order entirely. "
            "Never apply this to links, buttons, inputs, or other interactive controls "
            "that users need to reach by keyboard. "
            "It is only appropriate for elements that are programmatically focused via JavaScript."
        ),
    },
    "heading-h1-missing": {
        "title": "Add an H1 Heading to the Page",
        "wcag": "2.4.6",
        "effort": "LOW",
        "before": "<h2>Featured Products</h2>",
        "after": "<h1>Store Name — Featured Products</h1>\n<h2>Featured Products</h2>",
        "note": (
            "Every page must have exactly one H1 that identifies the page's primary purpose. "
            "Screen reader users use headings to navigate — the H1 is the entry point. "
            "On an e-commerce homepage, the H1 should be the store name or the primary section."
        ),
    },
    "heading-h1-multiple": {
        "title": "Consolidate to a Single H1 Heading",
        "wcag": "2.4.6",
        "effort": "LOW",
        "before": "<h1>Store Name</h1>\n...\n<h1>Featured Products</h1>",
        "after": "<h1>Store Name</h1>\n...\n<h2>Featured Products</h2>",
        "note": (
            "Only one H1 per page. The H1 defines the primary topic. "
            "All subsequent sections should use H2, H3, etc. in proper hierarchy. "
            "Multiple H1s create ambiguity for both screen readers and search engines."
        ),
    },
    "heading-empty": {
        "title": "Remove or Fill Empty Heading Elements",
        "wcag": "2.4.6",
        "effort": "LOW",
        "before": "<h2></h2>",
        "after": "<!-- Option A: Remove the empty heading element -->\n"
                 "<!-- Option B: Add meaningful text -->\n"
                 "<h2>Section Title</h2>",
        "note": (
            "Empty heading tags are announced by screen readers as 'heading, level 2' "
            "with no content — confusing and disorienting. "
            "Either add meaningful text content or remove the element entirely. "
            "Never use headings for visual styling — use CSS classes instead."
        ),
    },
    "heading-level-skipped": {
        "title": "Fix Skipped Heading Levels",
        "wcag": "1.3.1",
        "effort": "LOW",
        "before": "<h2>Category</h2>\n<h4>Product Name</h4>",
        "after": "<h2>Category</h2>\n<h3>Product Name</h3>",
        "note": (
            "Heading levels must not skip — H1 → H2 → H3, never H2 → H4. "
            "Screen reader users navigate by heading level; skipped levels indicate "
            "missing content and break the document outline. "
            "If you need smaller visual heading text, use CSS rather than a lower heading level."
        ),
    },
    "link-empty": {
        "title": "Add Accessible Names to Empty Links",
        "wcag": "2.4.4",
        "effort": "LOW",
        "before": '<a href="/cart"></a>',
        "after": (
            '<!-- Option A: aria-label -->\n'
            '<a href="/cart" aria-label="View shopping cart"></a>\n\n'
            '<!-- Option B: visually hidden text -->\n'
            '<a href="/cart">\n'
            '  <span aria-hidden="true">🛒</span>\n'
            '  <span class="sr-only">View shopping cart</span>\n'
            '</a>\n\n'
            '/* CSS for sr-only */\n'
            '.sr-only {\n'
            '  position: absolute;\n'
            '  width: 1px; height: 1px;\n'
            '  padding: 0; margin: -1px;\n'
            '  overflow: hidden;\n'
            '  clip: rect(0,0,0,0);\n'
            '  border: 0;\n'
            '}'
        ),
        "note": (
            "Every link must have an accessible name — either text content, "
            "an aria-label, or an aria-labelledby reference. "
            "Icon-only links are common in e-commerce and are a frequent ADA citation."
        ),
    },
    "link-text-generic": {
        "title": "Replace Generic Link Text with Descriptive Text",
        "wcag": "2.4.4",
        "effort": "LOW",
        "before": '<a href="/products/blue-shoe">Click here</a>',
        "after": '<a href="/products/blue-shoe">View Blue Running Shoe details</a>',
        "note": (
            "Links must make sense out of context. Screen reader users often navigate "
            "by listing all links on a page — 'click here' × 30 is meaningless. "
            "Describe the destination or action. Avoid: click here, here, read more, "
            "learn more, more, this."
        ),
    },
    "button-empty": {
        "title": "Add Accessible Names to Unlabeled Buttons",
        "wcag": "4.1.2",
        "effort": "LOW",
        "before": '<button></button>',
        "after": (
            '<!-- Option A: aria-label -->\n'
            '<button aria-label="Close dialog">×</button>\n\n'
            '<!-- Option B: visually hidden text -->\n'
            '<button>\n'
            '  <span aria-hidden="true">×</span>\n'
            '  <span class="sr-only">Close dialog</span>\n'
            '</button>'
        ),
        "note": (
            "Buttons without accessible names are announced as 'button' with no "
            "indication of purpose. Icon buttons (×, ≡, ♥) are the most common offender "
            "in e-commerce. Use aria-label to describe the action, not the icon."
        ),
    },
    "duplicate-id": {
        "title": "Resolve Duplicate ID Attributes",
        "wcag": "4.1.1",
        "effort": "MODERATE",
        "before": (
            '<div id="product-section">First section</div>\n'
            '...\n'
            '<div id="product-section">Second section</div>'
        ),
        "after": (
            '<div id="featured-products">First section</div>\n'
            '...\n'
            '<div id="sale-products">Second section</div>'
        ),
        "note": (
            "ID attributes must be unique within a page. Duplicate IDs break "
            "ARIA label associations (aria-labelledby, aria-describedby) and "
            "cause unpredictable behavior in assistive technologies. "
            "Audit your template system — duplicate IDs often come from component reuse."
        ),
    },
    "aria-role-invalid": {
        "title": "Replace Invalid ARIA Roles",
        "wcag": "4.1.1",
        "effort": "MODERATE",
        "before": '<div role="popup">...</div>',
        "after": '<div role="dialog" aria-modal="true" aria-label="Shopping cart">...</div>',
        "note": (
            "Only WAI-ARIA specification roles are valid. Invalid roles are ignored "
            "by assistive technologies. Common mistakes: role='popup' (use 'dialog'), "
            "role='tooltip-container' (use 'tooltip'), role='dropdown' (use 'listbox'). "
            "Reference: https://www.w3.org/TR/wai-aria-1.1/#role_definitions"
        ),
    },
}


def get_remediation(rule: str) -> dict:
    """
    Return remediation guidance for a given rule ID.
    Returns a default if rule not found.
    """
    default = {
        "title": f"Remediate: {rule.replace('-', ' ').title()}",
        "wcag": "—",
        "effort": "MODERATE",
        "before": "<!-- See issue details above -->",
        "after": "<!-- Apply WCAG 2.1 AA guideline for this violation type -->",
        "note": (
            "Consult WCAG 2.1 Success Criterion documentation for this violation. "
            "Reference: https://www.w3.org/TR/WCAG21/"
        ),
    }
    return REMEDIATION_MAP.get(rule, default)


def get_remediations_for_receipt(categories: list) -> list:
    """
    Build ordered remediation list from all issues in a receipt.
    Deduplicates by rule, highest severity first.
    """
    seen_rules = set()
    remediations = []

    severity_order = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}

    all_issues = []
    for cat in categories:
        for issue in cat.get("issues", []):
            all_issues.append(issue)

    all_issues.sort(key=lambda i: severity_order.get(i.get("severity", "minor"), 4))

    for issue in all_issues:
        rule = issue.get("rule", "")
        if rule and rule not in seen_rules:
            seen_rules.add(rule)
            remediation = get_remediation(rule)
            remediations.append({
                "rule": rule,
                "category": issue.get("category"),
                "severity": issue.get("severity"),
                "wcag": issue.get("wcag"),
                "element_found": issue.get("element", ""),
                **remediation,
            })

    return remediations
