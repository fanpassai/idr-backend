"""
IDR PDF Receipt Generator
ReportLab engine producing the full 10-section Defense Package PDF.
IDR institutional letterhead. Formatted as professional legal document.
"""

import io
from html import escape
from datetime import datetime, timezone

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib import colors

from receipt.plaintiff_layer import calculate_plaintiff_risk
from receipt.remediation import get_remediations_for_receipt


# ── Brand Colors ──────────────────────────────────────────────────────────────

C_VOID        = HexColor("#080d1a")   # Near-black background
C_GOLD        = HexColor("#C4A052")   # IDR gold accent
C_CREAM       = HexColor("#F0E8D8")   # Light text on dark
C_GOLD_FAINT  = HexColor("#2a2215")   # Faint gold tint for alternating rows
C_FAIL        = HexColor("#C0392B")   # Red
C_WARNING     = HexColor("#E67E22")   # Orange
C_PASS        = HexColor("#27AE60")   # Green
C_MODERATE    = HexColor("#D4AC0D")   # Yellow
C_LIGHT_GRAY  = HexColor("#F5F5F5")
C_MID_GRAY    = HexColor("#CCCCCC")
C_DARK_GRAY   = HexColor("#555555")
C_RULE        = HexColor("#E0D4B8")   # Divider lines

SEVERITY_COLORS = {
    "critical": HexColor("#C0392B"),
    "serious":  HexColor("#E67E22"),
    "moderate": HexColor("#D4AC0D"),
    "minor":    HexColor("#27AE60"),
}

RISK_COLORS = {
    "CRITICAL": HexColor("#C0392B"),
    "HIGH":     HexColor("#E67E22"),
    "MODERATE": HexColor("#D4AC0D"),
    "LOW":      HexColor("#27AE60"),
}

EFFORT_COLORS = {
    "LOW":      HexColor("#27AE60"),
    "MODERATE": HexColor("#E67E22"),
    "HIGH":     HexColor("#C0392B"),
}


# ── Custom Flowables ──────────────────────────────────────────────────────────

class DarkHeader(Flowable):
    """Full-width dark letterhead header block."""

    def __init__(self, receipt_id, registry_id, timestamp, domain, width):
        Flowable.__init__(self)
        self.receipt_id = receipt_id
        self.registry_id = registry_id
        self.timestamp = timestamp
        self.domain = domain
        self.width = width
        self.height = 1.6 * inch

    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(C_VOID)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        # Gold bottom border
        c.setFillColor(C_GOLD)
        c.rect(0, 0, self.width, 3, fill=1, stroke=0)

        # Institution label
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor("#7A6A40"))
        c.drawString(0.35 * inch, self.height - 0.35 * inch,
                     "INSTITUTE OF DIGITAL REMEDIATION  ·  IDR-PROTOCOL-2026")

        # Title
        c.setFont("Helvetica-Bold", 22)
        c.setFillColor(C_CREAM)
        c.drawString(0.35 * inch, self.height - 0.72 * inch, "IDR SCAN RECEIPT")

        # Subtitle
        c.setFont("Helvetica", 9)
        c.setFillColor(HexColor("#8A7A5A"))
        date_str = self.timestamp[:10] if self.timestamp else ""
        c.drawString(0.35 * inch, self.height - 0.95 * inch,
                     f"Official Compliance Record  ·  {date_str}  ·  {self.domain}")

        # Right side IDs
        right_x = self.width - 0.35 * inch
        c.setFont("Helvetica", 7)
        c.setFillColor(HexColor("#7A6A40"))
        c.drawRightString(right_x, self.height - 0.38 * inch, "RECEIPT ID")
        c.setFont("Courier-Bold", 8)
        c.setFillColor(C_CREAM)
        c.drawRightString(right_x, self.height - 0.52 * inch, self.receipt_id[:36])
        c.setFont("Helvetica", 7)
        c.setFillColor(HexColor("#7A6A40"))
        c.drawRightString(right_x, self.height - 0.70 * inch, "REGISTRY ID")
        c.setFont("Courier-Bold", 8)
        c.setFillColor(C_GOLD)
        c.drawRightString(right_x, self.height - 0.84 * inch, self.registry_id)


class SectionHeader(Flowable):
    """Dark section divider with gold left border and section number."""

    def __init__(self, number, title, width):
        Flowable.__init__(self)
        self.number = number
        self.title = title
        self.width = width
        self.height = 0.4 * inch

    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(HexColor("#0d1526"))
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        # Gold left accent
        c.setFillColor(C_GOLD)
        c.rect(0, 0, 4, self.height, fill=1, stroke=0)
        # Section number
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(C_GOLD)
        c.drawString(0.2 * inch, 0.14 * inch, f"§{self.number:02d}")
        # Title
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(C_CREAM)
        c.drawString(0.55 * inch, 0.14 * inch, self.title.upper())


class ScoreBadge(Flowable):
    """Large score display with status badge."""

    def __init__(self, score, status, width):
        Flowable.__init__(self)
        self.score = score
        self.status = status
        self.width = width
        self.height = 1.1 * inch

    def draw(self):
        c = self.canv
        status_color = {
            "pass": C_PASS, "warning": C_WARNING, "fail": C_FAIL
        }.get(self.status, C_FAIL)

        # Score number
        c.setFont("Helvetica-Bold", 52)
        c.setFillColor(C_VOID)
        c.drawCentredString(self.width / 2, 0.42 * inch, str(self.score))

        # /100
        c.setFont("Helvetica", 14)
        c.setFillColor(C_DARK_GRAY)
        c.drawCentredString(self.width / 2, 0.24 * inch, "/ 100")

        # Status badge
        badge_w = 1.2 * inch
        badge_h = 0.28 * inch
        badge_x = (self.width - badge_w) / 2
        badge_y = self.height - 0.36 * inch
        c.setFillColor(status_color)
        c.roundRect(badge_x, badge_y, badge_w, badge_h, 4, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(white)
        c.drawCentredString(self.width / 2, badge_y + 0.08 * inch,
                            self.status.upper())


# ── Style Definitions ─────────────────────────────────────────────────────────

def _build_styles():
    base = getSampleStyleSheet()

    styles = {
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontName="Helvetica", fontSize=9,
            leading=14, textColor=HexColor("#333333"),
            spaceAfter=4,
        ),
        "body_small": ParagraphStyle(
            "body_small", parent=base["Normal"],
            fontName="Helvetica", fontSize=8,
            leading=12, textColor=HexColor("#555555"),
        ),
        "label": ParagraphStyle(
            "label", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=7,
            leading=10, textColor=HexColor("#888888"),
            spaceBefore=4,
        ),
        "value": ParagraphStyle(
            "value", parent=base["Normal"],
            fontName="Helvetica", fontSize=9,
            leading=13, textColor=HexColor("#111111"),
        ),
        "mono": ParagraphStyle(
            "mono", parent=base["Normal"],
            fontName="Courier", fontSize=8,
            leading=11, textColor=HexColor("#222222"),
            backColor=HexColor("#F0EDE6"),
            leftIndent=6, rightIndent=6,
            borderPad=4,
        ),
        "mono_dark": ParagraphStyle(
            "mono_dark", parent=base["Normal"],
            fontName="Courier", fontSize=8,
            leading=11, textColor=HexColor("#C8E6C9"),
            backColor=HexColor("#0d1a0d"),
            leftIndent=6, rightIndent=6,
            borderPad=4,
        ),
        "heading_gold": ParagraphStyle(
            "heading_gold", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=11,
            leading=16, textColor=C_GOLD,
            spaceBefore=8, spaceAfter=4,
        ),
        "legal": ParagraphStyle(
            "legal", parent=base["Normal"],
            fontName="Helvetica", fontSize=8,
            leading=13, textColor=HexColor("#444444"),
            spaceAfter=6,
        ),
        "legal_bold": ParagraphStyle(
            "legal_bold", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=8,
            leading=13, textColor=HexColor("#222222"),
        ),
        "risk_desc": ParagraphStyle(
            "risk_desc", parent=base["Normal"],
            fontName="Helvetica", fontSize=9,
            leading=14, textColor=HexColor("#333333"),
            spaceAfter=6,
        ),
    }
    return styles


# ── PDF Builder ───────────────────────────────────────────────────────────────

def generate_pdf(receipt: dict) -> bytes:
    """
    Build the full 10-section IDR Defense Package PDF.
    Returns raw PDF bytes.
    """
    buf = io.BytesIO()

    PAGE_W, PAGE_H = letter
    MARGIN = 0.65 * inch
    CONTENT_W = PAGE_W - 2 * MARGIN

    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=0.75 * inch,
    )

    S = _build_styles()
    story = []

    scan = receipt.get("scan", {})
    categories = scan.get("categories", [])

    # Pre-compute layers
    plaintiff = calculate_plaintiff_risk(scan)
    remediations = get_remediations_for_receipt(categories)
    timestamp = receipt.get("timestamp_utc", "")
    receipt_id = receipt.get("receipt_id", "")
    registry_id = receipt.get("registry_id", "")
    domain = scan.get("domain", "")
    score = scan.get("overall_score", 0)
    status = scan.get("overall_status", "fail")
    critical_count = scan.get("critical_count", 0)
    total_issues = scan.get("total_issues", 0)
    hash_value = receipt.get("hash", {}).get("value", "")
    registry_url = receipt.get("registry_url", "")

    # ── §01 DOCUMENT HEADER ────────────────────────────────────────────────────
    story.append(DarkHeader(receipt_id, registry_id, timestamp, domain, CONTENT_W))
    story.append(Spacer(1, 0.2 * inch))

    # ── §02 STORE IDENTITY BLOCK ───────────────────────────────────────────────
    story.append(SectionHeader(2, "Store Identity", CONTENT_W))
    story.append(Spacer(1, 0.1 * inch))

    identity_data = [
        ["DOMAIN", domain, "URL", scan.get("url", "")],
        ["PAGE TITLE", scan.get("page_title", "—"), "SCAN DURATION",
         f"{scan.get('scan_duration_ms', 0)}ms"],
        ["TIMESTAMP", timestamp[:19].replace("T", "  ") + " UTC", "OPERATOR",
         receipt.get("operator", "IDR_SCANNER_v1")],
    ]

    identity_table = Table(
        [[Paragraph(f'<font size="7" color="#888888"><b>{r[0]}</b></font>', S["label"]),
          Paragraph(f'<font size="8">{r[1][:60]}</font>', S["value"]),
          Paragraph(f'<font size="7" color="#888888"><b>{r[2]}</b></font>', S["label"]),
          Paragraph(f'<font size="8">{r[3][:60]}</font>', S["value"])]
         for r in identity_data],
        colWidths=[1.1 * inch, 2.7 * inch, 1.1 * inch, 2.7 * inch],
    )
    identity_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT_GRAY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_LIGHT_GRAY, white]),
        ("BOX", (0, 0), (-1, -1), 0.5, C_MID_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_MID_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(identity_table)
    story.append(Spacer(1, 0.2 * inch))

    # ── §03 EXECUTIVE SUMMARY ──────────────────────────────────────────────────
    story.append(SectionHeader(3, "Executive Summary", CONTENT_W))
    story.append(Spacer(1, 0.15 * inch))

    risk_color = RISK_COLORS.get(plaintiff["risk_level"], C_FAIL)

    exec_left = [
        [ScoreBadge(score, status, 2.4 * inch)],
        [Paragraph(
            f'<font size="8" color="#888888"><b>OVERALL STATUS</b></font><br/>'
            f'<font size="10"><b>{status.upper()}</b></font>',
            S["body"]
        )],
    ]

    risk_badge_text = plaintiff["risk_level"]
    settlement = plaintiff["settlement_range"]

    exec_right = [
        Paragraph('<font size="7" color="#888888"><b>PLAINTIFF RISK LEVEL</b></font>', S["label"]),
        Spacer(1, 4),
        Table(
            [[Paragraph(
                f'<font size="14" color="white"><b>{risk_badge_text}</b></font>',
                ParagraphStyle("rb", fontName="Helvetica-Bold", fontSize=14,
                               textColor=white, alignment=TA_CENTER)
            )]],
            colWidths=[2.8 * inch],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), risk_color),
                ("TOPPADDING", (0, 0), (0, 0), 8),
                ("BOTTOMPADDING", (0, 0), (0, 0), 8),
            ])
        ),
        Spacer(1, 8),
        Paragraph(
            '<font size="7" color="#888888"><b>ESTIMATED DEMAND RANGE</b></font>',
            S["label"]
        ),
        Paragraph(
            f'<font size="16" color="#C0392B"><b>'
            f'{settlement["formatted_low"]} – {settlement["formatted_high"]}'
            f'</b></font>',
            ParagraphStyle("sr", fontName="Helvetica-Bold", fontSize=16,
                           textColor=HexColor("#C0392B"))
        ),
        Spacer(1, 4),
        Paragraph(
            f'<font size="7" color="#888888"><b>DEMAND PROBABILITY</b></font>',
            S["label"]
        ),
        Paragraph(plaintiff["demand_probability"], S["value"]),
    ]

    stats_data = [
        [Paragraph(f'<b><font size="16">{critical_count}</font></b><br/>'
                   f'<font size="7" color="#888888">CRITICAL ISSUES</font>', S["body"]),
         Paragraph(f'<b><font size="16">{total_issues}</font></b><br/>'
                   f'<font size="7" color="#888888">TOTAL ISSUES</font>', S["body"]),
         Paragraph(f'<b><font size="16">{len(categories)}</font></b><br/>'
                   f'<font size="7" color="#888888">CATEGORIES SCANNED</font>', S["body"]),
         Paragraph(f'<b><font size="16">{"YES" if plaintiff["checkout_barrier"] else "NO"}</font></b><br/>'
                   f'<font size="7" color="#888888">CHECKOUT BARRIER</font>', S["body"])],
    ]
    stats_table = Table(
        stats_data,
        colWidths=[CONTENT_W / 4] * 4,
    )
    stats_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, C_MID_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_MID_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT_GRAY),
    ]))

    exec_table = Table(
        [[ScoreBadge(score, status, 2.4 * inch), exec_right]],
        colWidths=[2.6 * inch, CONTENT_W - 2.6 * inch],
    )
    exec_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(exec_table)
    story.append(Spacer(1, 0.1 * inch))
    story.append(stats_table)
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(plaintiff["description"], S["risk_desc"]))
    story.append(Spacer(1, 0.2 * inch))

    # ── §04 PER-CATEGORY BREAKDOWN ─────────────────────────────────────────────
    story.append(SectionHeader(4, "Category Breakdown", CONTENT_W))
    story.append(Spacer(1, 0.12 * inch))

    for cat in categories:
        cat_status = cat.get("status", "fail")
        cat_score = cat.get("score", 0)
        cat_color = {"pass": C_PASS, "warning": C_WARNING, "fail": C_FAIL}.get(cat_status, C_FAIL)

        cat_header = Table(
            [[Paragraph(
                f'<font size="9"><b>{cat["name"]}</b></font>',
                S["body"]
              ),
              Paragraph(
                f'<font size="9" color="white"><b> {cat_score}/100 {cat_status.upper()} </b></font>',
                ParagraphStyle("ch", fontName="Helvetica-Bold", fontSize=9,
                               textColor=white, alignment=TA_RIGHT)
              )]],
            colWidths=[CONTENT_W * 0.7, CONTENT_W * 0.3],
        )
        cat_header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), HexColor("#EEEAE0")),
            ("BACKGROUND", (1, 0), (1, 0), cat_color),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(cat_header)

        issues = cat.get("issues", [])
        if issues:
            issue_rows = [["SEVERITY", "DESCRIPTION", "WCAG", "COUNT"]]
            for issue in issues:
                sev = issue.get("severity", "minor").upper()
                sev_color = SEVERITY_COLORS.get(issue.get("severity", "minor"), C_DARK_GRAY)
                issue_rows.append([
                    Paragraph(
                        f'<font size="7" color="white"><b>{sev}</b></font>',
                        ParagraphStyle("sv", fontName="Helvetica-Bold", fontSize=7,
                                       textColor=white, backColor=sev_color,
                                       alignment=TA_CENTER)
                    ),
                    [
                        Paragraph(escape(issue.get("description", ""))[:100], S["body_small"]),
                        Paragraph(
                            f'<font size="7" color="#888888">Element: </font>'
                            f'<font size="7" fontName="Courier">{escape(issue.get("element", ""))[:80]}</font>',
                            S["body_small"]
                        ),
                        Paragraph(
                            f'<font size="7" color="#555555">{escape(issue.get("impact", ""))[:90]}</font>',
                            S["body_small"]
                        ),
                    ],
                    Paragraph(f'WCAG {issue.get("wcag", "")}', S["body_small"]),
                    Paragraph(str(issue.get("count", 1)), S["body_small"]),
                ])

            issue_table = Table(
                issue_rows,
                colWidths=[0.75 * inch, CONTENT_W - 2.15 * inch, 0.85 * inch, 0.55 * inch],
            )
            issue_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), C_VOID),
                ("TEXTCOLOR", (0, 0), (-1, 0), C_GOLD),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 7),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, C_LIGHT_GRAY]),
                ("BOX", (0, 0), (-1, -1), 0.5, C_MID_GRAY),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, C_MID_GRAY),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("ALIGN", (2, 1), (2, -1), "CENTER"),
                ("ALIGN", (3, 1), (3, -1), "CENTER"),
            ]))
            story.append(issue_table)
        else:
            story.append(Paragraph(
                "✓  No issues detected in this category.",
                ParagraphStyle("ok", fontName="Helvetica", fontSize=9,
                               textColor=C_PASS, backColor=HexColor("#F0FFF4"),
                               leftIndent=8, borderPad=5)
            ))

        story.append(Spacer(1, 0.12 * inch))

    # ── §05 PLAINTIFF SIMULATION REPORT ───────────────────────────────────────
    story.append(PageBreak())
    story.append(SectionHeader(5, "Plaintiff Simulation Report", CONTENT_W))
    story.append(Spacer(1, 0.12 * inch))

    story.append(Paragraph(
        "The following analysis simulates how a plaintiff attorney or automated scanning "
        "service would evaluate this site as a litigation target. IDR uses the same scanning "
        "methodology employed by plaintiff firms — the difference is who runs it first.",
        S["legal"]
    ))
    story.append(Spacer(1, 0.1 * inch))

    # Litigation flags table
    flags = plaintiff.get("litigation_flags", [])
    if flags:
        story.append(Paragraph("HIGH-VALUE VIOLATION FLAGS", S["heading_gold"]))
        flag_rows = [["VIOLATION", "LITIGATION VALUE", "WCAG", "LEGAL NOTE"]]
        for flag in flags:
            lv = flag.get("litigation_value", "MODERATE")
            lv_color = {
                "CRITICAL": C_FAIL,
                "HIGH": C_WARNING,
                "MODERATE": C_MODERATE,
                "LOW": C_PASS
            }.get(lv, C_MODERATE)
            flag_rows.append([
                Paragraph(flag.get("rule", "").replace("-", " "), S["body_small"]),
                Paragraph(
                    f'<font size="7" color="white"><b>{lv}</b></font>',
                    ParagraphStyle("lv", fontName="Helvetica-Bold", fontSize=7,
                                   textColor=white, backColor=lv_color,
                                   alignment=TA_CENTER)
                ),
                Paragraph(f'WCAG {flag.get("wcag", "")}', S["body_small"]),
                Paragraph(escape(flag.get("legal_note", ""))[:160], S["body_small"]),
            ])

        flag_table = Table(
            flag_rows,
            colWidths=[1.2 * inch, 0.9 * inch, 0.75 * inch, CONTENT_W - 2.85 * inch],
        )
        flag_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_VOID),
            ("TEXTCOLOR", (0, 0), (-1, 0), C_GOLD),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, C_LIGHT_GRAY]),
            ("BOX", (0, 0), (-1, -1), 0.5, C_MID_GRAY),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, C_MID_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 1), (1, -1), "CENTER"),
            ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ]))
        story.append(flag_table)
        story.append(Spacer(1, 0.15 * inch))

    # Comparable cases
    comparable = plaintiff.get("comparable_cases", [])
    if comparable:
        story.append(Paragraph("COMPARABLE CASE LAW", S["heading_gold"]))
        for case in comparable:
            case_block = [
                [Paragraph(
                    f'<b>{case["case"]}</b>  '
                    f'<font size="8" color="#888888">{case["citation"]}</font>',
                    S["legal_bold"]
                )],
                [Paragraph(case["outcome"], S["legal"])],
            ]
            case_table = Table(case_block, colWidths=[CONTENT_W])
            case_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FAFAF5")),
                ("BOX", (0, 0), (-1, -1), 0.5, C_GOLD),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(case_table)
            story.append(Spacer(1, 0.08 * inch))

    story.append(Spacer(1, 0.15 * inch))

    # ── §06 REMEDIATION GUIDANCE ───────────────────────────────────────────────
    story.append(SectionHeader(6, "Remediation Guidance", CONTENT_W))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph(
        "The following before/after code corrections address each unique violation type "
        "found in this scan, ordered by severity. Applying these fixes and running a "
        "confirmation scan will generate an updated Scan Receipt.",
        S["legal"]
    ))
    story.append(Spacer(1, 0.12 * inch))

    for i, rem in enumerate(remediations[:12]):  # Cap at 12 unique remediation items
        sev = rem.get("severity", "minor")
        sev_color = SEVERITY_COLORS.get(sev, C_DARK_GRAY)
        effort = rem.get("effort", "LOW")
        effort_color = EFFORT_COLORS.get(effort, C_MODERATE)

        rem_header = Table(
            [[Paragraph(
                f'<b>{rem.get("title", "")}</b>',
                S["legal_bold"]
              ),
              Paragraph(
                f'<font size="7" color="white"> {sev.upper()} </font>',
                ParagraphStyle("rh", fontName="Helvetica-Bold", fontSize=7,
                               textColor=white, alignment=TA_RIGHT)
              ),
              Paragraph(
                f'<font size="7" color="white"> EFFORT: {effort} </font>',
                ParagraphStyle("ef", fontName="Helvetica-Bold", fontSize=7,
                               textColor=white, alignment=TA_RIGHT)
              )]],
            colWidths=[CONTENT_W - 2.0 * inch, 0.9 * inch, 1.1 * inch],
        )
        rem_header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), HexColor("#F0EDE6")),
            ("BACKGROUND", (1, 0), (1, 0), sev_color),
            ("BACKGROUND", (2, 0), (2, 0), effort_color),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(rem_header)

        # Before / After — escape HTML first, then apply display replacements
        before_text = escape(rem.get("before", "")).replace("\n", "<br/>").replace(" ", "&nbsp;")
        after_text = escape(rem.get("after", "")).replace("\n", "<br/>").replace(" ", "&nbsp;")

        code_table = Table(
            [[Paragraph('<font size="7" color="#888888"><b>BEFORE (VIOLATION)</b></font>', S["label"]),
              Paragraph('<font size="7" color="#27AE60"><b>AFTER (CORRECTED)</b></font>', S["label"])],
             [Paragraph(before_text, S["mono"]),
              Paragraph(after_text, S["mono_dark"])]],
            colWidths=[CONTENT_W / 2 - 0.05 * inch, CONTENT_W / 2 - 0.05 * inch],
        )
        code_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("COLPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(code_table)
        story.append(Paragraph(f'Note: {escape(rem.get("note", ""))}', S["body_small"]))
        story.append(HRFlowable(width=CONTENT_W, thickness=0.5, color=C_RULE,
                                spaceAfter=8, spaceBefore=8))

    story.append(Spacer(1, 0.1 * inch))

    # ── §07 EVIDENCE LOG CHAIN ─────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(SectionHeader(7, "Evidence Log Chain", CONTENT_W))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph(
        "This log records the chain of events for this scan session. "
        "Each entry is chronologically ordered and linked to this receipt via its unique identifier. "
        "This chain establishes the audit trail for legal purposes.",
        S["legal"]
    ))
    story.append(Spacer(1, 0.1 * inch))

    log_entries = [
        [timestamp[:19].replace("T", " ") + " UTC",
         "SCAN_INITIATED",
         f"Automated accessibility scan initiated for {domain}"],
        [timestamp[:19].replace("T", " ") + " UTC",
         "SCAN_COMPLETED",
         f"Scan completed in {scan.get('scan_duration_ms', 0)}ms. "
         f"Score: {score}/100. Critical issues: {critical_count}. "
         f"Total issues: {total_issues}."],
        [timestamp[:19].replace("T", " ") + " UTC",
         "RECEIPT_GENERATED",
         f"Scan Receipt generated. ID: {receipt_id}"],
        [timestamp[:19].replace("T", " ") + " UTC",
         "HASH_COMPUTED",
         f"SHA-256 hash computed: {hash_value[:32]}..."],
        [timestamp[:19].replace("T", " ") + " UTC",
         "REGISTRY_UPDATED",
         f"Registry record updated at {registry_url}"],
    ]

    log_rows = [["TIMESTAMP (UTC)", "EVENT TYPE", "DETAIL"]]
    for entry in log_entries:
        log_rows.append([
            Paragraph(entry[0], S["body_small"]),
            Paragraph(
                f'<font size="7" color="#C4A052"><b>{entry[1]}</b></font>',
                S["body_small"]
            ),
            Paragraph(entry[2], S["body_small"]),
        ])

    log_table = Table(
        log_rows,
        colWidths=[1.6 * inch, 1.3 * inch, CONTENT_W - 2.9 * inch],
    )
    log_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_VOID),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_GOLD),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, HexColor("#0d1526")]),
        ("TEXTCOLOR", (0, 1), (-1, -1), HexColor("#333333")),
        ("BOX", (0, 0), (-1, -1), 0.5, C_MID_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_MID_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(log_table)
    story.append(Spacer(1, 0.2 * inch))

    # ── §08 SHA-256 VERIFICATION BLOCK ────────────────────────────────────────
    story.append(SectionHeader(8, "SHA-256 Verification Block", CONTENT_W))
    story.append(Spacer(1, 0.12 * inch))

    hash_data = receipt.get("hash", {})
    verification_table = Table(
        [
            [Paragraph('<font size="7" color="#888888"><b>ALGORITHM</b></font>', S["label"]),
             Paragraph(hash_data.get("algorithm", "SHA-256"), S["value"]),
             Paragraph('<font size="7" color="#888888"><b>INPUT SIZE</b></font>', S["label"]),
             Paragraph(f'{hash_data.get("input_bytes", 0):,} bytes', S["value"])],
            [Paragraph('<font size="7" color="#888888"><b>OPERATOR</b></font>', S["label"]),
             Paragraph(receipt.get("operator", "IDR_SCANNER_v1"), S["value"]),
             Paragraph('<font size="7" color="#888888"><b>PROTOCOL</b></font>', S["label"]),
             Paragraph(receipt.get("idr_protocol", "IDR-BRAND-2026-01"), S["value"])],
        ],
        colWidths=[1.0 * inch, 2.8 * inch, 1.0 * inch, 2.8 * inch],
    )
    verification_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_LIGHT_GRAY),
        ("BOX", (0, 0), (-1, -1), 0.5, C_MID_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_MID_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(verification_table)
    story.append(Spacer(1, 0.08 * inch))

    hash_display = Table(
        [[Paragraph(
            f'<font size="8" color="#888888"><b>SHA-256 HASH</b></font><br/>'
            f'<font size="9" fontName="Courier">{hash_value}</font>',
            ParagraphStyle("hv", fontName="Courier", fontSize=9,
                           textColor=HexColor("#1A1A1A"),
                           backColor=HexColor("#F5F0E8"),
                           borderPad=8, leading=16)
        )]],
        colWidths=[CONTENT_W],
    )
    hash_display.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.5, C_GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(hash_display)
    story.append(Spacer(1, 0.08 * inch))
    story.append(Paragraph(
        "This hash was computed at the moment of receipt generation over the canonical "
        "payload (receipt_id, registry_id, timestamp_utc, operator, scan data) using "
        "SHA-256. Any modification to this receipt — including timestamp, score, or "
        "issue data — produces a different hash. The original hash is immutably stored "
        "in the IDR Registry. Tamper-evident by design.",
        S["legal"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    # ── §09 REGISTRY RECORD ────────────────────────────────────────────────────
    story.append(SectionHeader(9, "Registry Record", CONTENT_W))
    story.append(Spacer(1, 0.12 * inch))

    reg_status = "active" if (status == "pass" and critical_count == 0) else "monitoring"
    reg_color = C_PASS if reg_status == "active" else C_WARNING

    registry_table = Table(
        [
            [Paragraph('<font size="7" color="#888888"><b>REGISTRY URL</b></font>', S["label"]),
             Paragraph(registry_url, ParagraphStyle("ru", fontName="Helvetica", fontSize=9,
                                                     textColor=HexColor("#0645AD")))],
            [Paragraph('<font size="7" color="#888888"><b>REGISTRY STATUS</b></font>', S["label"]),
             Paragraph(
                 f'<font color="white"><b> {reg_status.upper()} </b></font>',
                 ParagraphStyle("rs", fontName="Helvetica-Bold", fontSize=9,
                                textColor=white, backColor=reg_color)
             )],
            [Paragraph('<font size="7" color="#888888"><b>LAST SCANNED</b></font>', S["label"]),
             Paragraph(timestamp[:10], S["value"])],
            [Paragraph('<font size="7" color="#888888"><b>SCAN COUNT</b></font>', S["label"]),
             Paragraph("1", S["value"])],
        ],
        colWidths=[1.4 * inch, CONTENT_W - 1.4 * inch],
    )
    registry_table.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [white, C_LIGHT_GRAY]),
        ("BOX", (0, 0), (-1, -1), 0.5, C_MID_GRAY),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_MID_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(registry_table)
    story.append(Spacer(1, 0.1 * inch))

    badge_embed = (
        f'<!-- IDR Verified Badge -->\n'
        f'<script src="https://idrshield.com/badge.js"\n'
        f'  data-store="{domain}"\n'
        f'  data-registry="{registry_id}">\n'
        f'</script>'
    )
    story.append(Paragraph(
        '<font size="7" color="#888888"><b>BADGE EMBED CODE</b></font>',
        S["label"]
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        badge_embed.replace("\n", "<br/>").replace(" ", "&nbsp;"),
        S["mono"]
    ))
    story.append(Spacer(1, 0.2 * inch))

    # ── §10 LEGAL POSITIONING STATEMENT ───────────────────────────────────────
    story.append(SectionHeader(10, "Legal Positioning Statement", CONTENT_W))
    story.append(Spacer(1, 0.12 * inch))

    legal_text = [
        (
            "DEFENSE RECORD STATEMENT",
            "This Scan Receipt constitutes a timestamped, third-party accessibility audit "
            "record created by the Institute of Digital Remediation (IDR). The receipt "
            "documents the accessibility state of the above-referenced domain at the time "
            "of scanning. The SHA-256 hash provides cryptographic proof of the receipt's "
            "integrity — any post-generation modification is mathematically detectable."
        ),
        (
            "ADA COMPLIANCE CONTEXT",
            "Title III of the Americans with Disabilities Act (ADA) has been interpreted "
            "by multiple federal courts to apply to commercial websites. WCAG 2.1 Level AA "
            "is the broadly accepted technical standard for ADA compliance in e-commerce. "
            "Stores with documented remediation efforts and compliance records have "
            "historically achieved more favorable outcomes in ADA demand letter negotiations "
            "and litigation."
        ),
        (
            "PROACTIVE DEFENSE POSTURE",
            "The same automated systems used by plaintiff law firms to identify targets are "
            "the systems IDR uses to build your defense record. By running this scan first, "
            "generating an immutable receipt, and pursuing remediation, you establish: "
            "(1) awareness of the issue, (2) good-faith remediation effort, and "
            "(3) a timestamped baseline that precedes any potential demand letter. "
            "This posture has been used to negotiate reduced settlements and dismissals."
        ),
        (
            "DISCLAIMER",
            "The Institute of Digital Remediation is not a law firm and does not provide "
            "legal advice. This receipt is a compliance documentation and monitoring system. "
            "The settlement range estimates are based on publicly available case data and "
            "are provided for informational purposes only. Consult qualified legal counsel "
            "for advice on your specific legal situation. IDR-PROTOCOL-2026."
        ),
    ]

    for title, text in legal_text:
        story.append(Paragraph(title, S["heading_gold"]))
        story.append(Paragraph(text, S["legal"]))
        story.append(Spacer(1, 0.08 * inch))

    # ── Footer row ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.2 * inch))
    footer_table = Table(
        [[Paragraph(
            f'<font size="7" color="white">Institute of Digital Remediation  ·  '
            f'idrshield.com  ·  hello@idrshield.com  ·  {receipt_id}</font>',
            ParagraphStyle("ft", fontName="Helvetica", fontSize=7,
                           textColor=white, alignment=TA_CENTER)
        )]],
        colWidths=[CONTENT_W],
    )
    footer_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_VOID),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(footer_table)

    doc.build(story)
    return buf.getvalue()
