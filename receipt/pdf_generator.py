"""
IDR PDF Receipt Generator — Phase 2B
ReportLab engine. 10 sections. IDR institutional letterhead.
All scan data HTML-escaped before passing to Paragraph.
Violations deduplicated by rule as safety net for legacy receipts.
"""

import io
from html import escape as he
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.platypus.flowables import Flowable

from receipt.plaintiff_layer import calculate_plaintiff_risk
from receipt.remediation import get_remediations_for_receipt

# ── Brand Colors ──────────────────────────────────────────────────────────────
C_VOID       = HexColor("#080d1a")
C_GOLD       = HexColor("#C4A052")
C_CREAM      = HexColor("#F0E8D8")
C_FAIL       = HexColor("#C0392B")
C_WARNING    = HexColor("#E67E22")
C_PASS       = HexColor("#27AE60")
C_MODERATE   = HexColor("#D4AC0D")
C_LIGHT_GRAY = HexColor("#F5F5F5")
C_MID_GRAY   = HexColor("#CCCCCC")
C_DARK_GRAY  = HexColor("#555555")
C_RULE       = HexColor("#E0D4B8")
C_ROW_ALT    = HexColor("#F0EDE6")

SEV_COLOR = {
    "critical": HexColor("#C0392B"),
    "serious":  HexColor("#E67E22"),
    "moderate": HexColor("#D4AC0D"),
    "minor":    HexColor("#27AE60"),
}
RISK_COLOR = {
    "CRITICAL": HexColor("#C0392B"),
    "HIGH":     HexColor("#E67E22"),
    "MODERATE": HexColor("#D4AC0D"),
    "LOW":      HexColor("#27AE60"),
}
EFFORT_COLOR = {
    "LOW":      HexColor("#27AE60"),
    "MODERATE": HexColor("#E67E22"),
    "HIGH":     HexColor("#C0392B"),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def e(s):
    """Escape and truncate scan data for safe Paragraph use."""
    return he(str(s or ""))

def et(s, n=100):
    """Escape and truncate to n chars."""
    return he(str(s or ""))[:n]


def dedup_issues(issues):
    """Collapse issues with the same rule into one row, summing counts."""
    seen = {}
    for issue in issues:
        rule = issue.get("rule") or issue.get("description", "unknown")
        if rule not in seen:
            seen[rule] = dict(issue)
            seen[rule]["_total"] = issue.get("count", 1)
        else:
            seen[rule]["_total"] += issue.get("count", 1)
    return list(seen.values())


def dedup_flags(flags):
    """Collapse litigation flags with the same rule, summing instance counts."""
    seen = {}
    for flag in flags:
        rule = flag.get("rule", "unknown")
        if rule not in seen:
            seen[rule] = dict(flag)
            seen[rule]["_total"] = flag.get("count", 1)
        else:
            seen[rule]["_total"] += flag.get("count", 1)
    return list(seen.values())


# ── Custom Flowables ──────────────────────────────────────────────────────────

class DarkHeader(Flowable):
    def __init__(self, receipt_id, registry_id, timestamp, domain, width):
        Flowable.__init__(self)
        self.receipt_id = receipt_id
        self.registry_id = registry_id
        self.timestamp = timestamp
        self.domain = domain
        self.width = width
        self.height = 1.55 * inch

    def draw(self):
        c = self.canv
        c.setFillColor(C_VOID)
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        c.setFillColor(C_GOLD)
        c.rect(0, 0, self.width, 3, fill=1, stroke=0)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(HexColor("#6A5A30"))
        c.drawString(0.35*inch, self.height - 0.32*inch,
                     "INSTITUTE OF DIGITAL REMEDIATION  ·  IDR-PROTOCOL-2026")
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(C_CREAM)
        c.drawString(0.35*inch, self.height - 0.65*inch, "IDR SCAN RECEIPT")
        date_str = self.timestamp[:10] if self.timestamp else ""
        c.setFont("Helvetica", 8.5)
        c.setFillColor(HexColor("#8A7A5A"))
        c.drawString(0.35*inch, self.height - 0.88*inch,
                     f"Official Compliance Record  ·  {date_str}  ·  {self.domain}")
        rx = self.width - 0.35*inch
        c.setFont("Helvetica", 6.5)
        c.setFillColor(HexColor("#7A6A40"))
        c.drawRightString(rx, self.height - 0.35*inch, "RECEIPT ID")
        c.setFont("Courier-Bold", 7.5)
        c.setFillColor(C_CREAM)
        c.drawRightString(rx, self.height - 0.50*inch, str(self.receipt_id)[:36])
        c.setFont("Helvetica", 6.5)
        c.setFillColor(HexColor("#7A6A40"))
        c.drawRightString(rx, self.height - 0.68*inch, "REGISTRY ID")
        c.setFont("Courier-Bold", 7.5)
        c.setFillColor(C_GOLD)
        c.drawRightString(rx, self.height - 0.83*inch, str(self.registry_id))


class SectionHeader(Flowable):
    def __init__(self, number, title, width):
        Flowable.__init__(self)
        self.number = number
        self.title = title
        self.width = width
        self.height = 0.36*inch

    def draw(self):
        c = self.canv
        c.setFillColor(HexColor("#0d1526"))
        c.rect(0, 0, self.width, self.height, fill=1, stroke=0)
        c.setFillColor(C_GOLD)
        c.rect(0, 0, 4, self.height, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(C_GOLD)
        c.drawString(0.18*inch, 0.12*inch, f"§{self.number:02d}")
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(C_CREAM)
        c.drawString(0.5*inch, 0.12*inch, self.title.upper())


class ScoreBadge(Flowable):
    def __init__(self, score, status, width):
        Flowable.__init__(self)
        self.score = score
        self.status = status
        self.width = width
        self.height = 1.8*inch

    def draw(self):
        c = self.canv
        sc = {"pass": C_PASS, "warning": C_WARNING, "fail": C_FAIL}.get(self.status, C_FAIL)

        # Draw order bottom → top to guarantee no overlap

        # /100  — bottom
        c.setFont("Helvetica", 12)
        c.setFillColor(C_DARK_GRAY)
        c.drawCentredString(self.width/2, 0.15*inch, "/ 100")

        # Score number — 38pt cap-height ~0.38", top ≈ 0.53+0.38 = 0.91"
        c.setFont("Helvetica-Bold", 38)
        c.setFillColor(C_VOID)
        c.drawCentredString(self.width/2, 0.53*inch, str(self.score))

        # Status badge — bottom at 1.10", well above score top of 0.91"
        bw, bh = 1.1*inch, 0.28*inch
        bx = (self.width - bw) / 2
        by = 1.10*inch
        c.setFillColor(sc)
        c.roundRect(bx, by, bw, bh, 4, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 8.5)
        c.setFillColor(white)
        c.drawCentredString(self.width/2, by + 0.09*inch, self.status.upper())


# ── Styles ────────────────────────────────────────────────────────────────────

def S():
    base = getSampleStyleSheet()
    return {
        "body": ParagraphStyle("body", parent=base["Normal"],
            fontName="Helvetica", fontSize=9, leading=14,
            textColor=HexColor("#333333"), spaceAfter=3),
        "sm": ParagraphStyle("sm", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, leading=12,
            textColor=HexColor("#444444")),
        "xs": ParagraphStyle("xs", parent=base["Normal"],
            fontName="Helvetica", fontSize=7.5, leading=11,
            textColor=HexColor("#555555")),
        "label": ParagraphStyle("label", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=6.5, leading=10,
            textColor=HexColor("#888888"), spaceBefore=3),
        "val": ParagraphStyle("val", parent=base["Normal"],
            fontName="Helvetica", fontSize=8.5, leading=12,
            textColor=HexColor("#111111")),
        "mono": ParagraphStyle("mono", parent=base["Normal"],
            fontName="Courier", fontSize=7.5, leading=11,
            textColor=HexColor("#222222"), backColor=HexColor("#F0EDE6"),
            leftIndent=6, borderPad=4),
        "mono_green": ParagraphStyle("mono_green", parent=base["Normal"],
            fontName="Courier", fontSize=7.5, leading=11,
            textColor=HexColor("#C8E6C9"), backColor=HexColor("#0d1a0d"),
            leftIndent=6, borderPad=4),
        "gold_head": ParagraphStyle("gold_head", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=10, leading=15,
            textColor=C_GOLD, spaceBefore=10, spaceAfter=5),
        "legal": ParagraphStyle("legal", parent=base["Normal"],
            fontName="Helvetica", fontSize=8.5, leading=13.5,
            textColor=HexColor("#333333"), spaceAfter=6),
        "legal_bold": ParagraphStyle("legal_bold", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=8.5, leading=13,
            textColor=HexColor("#111111")),
        "center_white": ParagraphStyle("cw", parent=base["Normal"],
            fontName="Helvetica-Bold", fontSize=8, leading=12,
            textColor=white, alignment=TA_CENTER),
        "center_sm": ParagraphStyle("csm", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, leading=12,
            textColor=HexColor("#333333"), alignment=TA_CENTER),
    }


# ── Main Generator ────────────────────────────────────────────────────────────

def generate_pdf(receipt: dict) -> bytes:
    buf = io.BytesIO()
    PAGE_W, PAGE_H = letter
    M = 0.65*inch
    CW = PAGE_W - 2*M

    doc = SimpleDocTemplate(buf, pagesize=letter,
        leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=0.75*inch)

    ST = S()
    story = []

    scan       = receipt.get("scan", {})
    cats       = scan.get("categories", [])
    plaintiff  = calculate_plaintiff_risk(scan)
    rems       = get_remediations_for_receipt(cats)

    ts         = receipt.get("timestamp_utc", "")
    rid        = receipt.get("receipt_id", "")
    reg_id     = receipt.get("registry_id", "")
    domain     = scan.get("domain", "")
    score      = scan.get("overall_score", 0)
    status     = scan.get("overall_status", "fail")
    crit_ct    = scan.get("critical_count", 0)
    total_iss  = scan.get("total_issues", 0)
    hash_val   = receipt.get("hash", {}).get("value", "")
    reg_url    = receipt.get("registry_url", "")

    def sp(n=0.12): return Spacer(1, n*inch)
    def hr(): return HRFlowable(width=CW, thickness=0.5, color=C_RULE, spaceAfter=8, spaceBefore=8)

    # ── §01 LETTERHEAD ────────────────────────────────────────────────────────
    story.append(DarkHeader(rid, reg_id, ts, domain, CW))
    story.append(sp(0.18))

    # ── §02 STORE IDENTITY ────────────────────────────────────────────────────
    story.append(SectionHeader(2, "Store Identity", CW))
    story.append(sp(0.1))

    id_rows = [
        [Paragraph('<font size="6.5" color="#888888"><b>DOMAIN</b></font>', ST["label"]),
         Paragraph(e(domain), ST["val"]),
         Paragraph('<font size="6.5" color="#888888"><b>URL</b></font>', ST["label"]),
         Paragraph(e(scan.get("url", "")), ST["val"])],
        [Paragraph('<font size="6.5" color="#888888"><b>PAGE TITLE</b></font>', ST["label"]),
         Paragraph(et(scan.get("page_title", ""), 70), ST["val"]),
         Paragraph('<font size="6.5" color="#888888"><b>SCAN DURATION</b></font>', ST["label"]),
         Paragraph(f'{scan.get("scan_duration_ms", 0)}ms', ST["val"])],
        [Paragraph('<font size="6.5" color="#888888"><b>TIMESTAMP (UTC)</b></font>', ST["label"]),
         Paragraph(ts[:19].replace("T", "  "), ST["val"]),
         Paragraph('<font size="6.5" color="#888888"><b>OPERATOR</b></font>', ST["label"]),
         Paragraph(e(receipt.get("operator", "IDR_SCANNER_v1")), ST["val"])],
    ]
    id_table = Table(id_rows, colWidths=[1.0*inch, 2.8*inch, 1.0*inch, 2.8*inch])
    id_table.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0),(-1,-1), [C_LIGHT_GRAY, white]),
        ("BOX", (0,0),(-1,-1), 0.5, C_MID_GRAY),
        ("INNERGRID", (0,0),(-1,-1), 0.25, C_MID_GRAY),
        ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING", (0,0),(-1,-1), 8),
    ]))
    story.append(id_table)
    story.append(sp(0.18))

    # ── §03 EXECUTIVE SUMMARY ─────────────────────────────────────────────────
    story.append(SectionHeader(3, "Executive Summary", CW))
    story.append(sp(0.12))

    risk_key   = plaintiff["risk_level"]
    risk_color = RISK_COLOR.get(risk_key, C_FAIL)
    settle     = plaintiff["settlement_range"]
    checkout   = bool(plaintiff.get("checkout_barrier", False))
    checkout_label = "BARRIER FOUND" if checkout else "CHECKOUT CLEAR"
    checkout_color = "#C0392B" if checkout else "#27AE60"

    # Right column — risk + settlement
    right_items = [
        Paragraph('<font size="6.5" color="#888888"><b>PLAINTIFF RISK LEVEL</b></font>', ST["label"]),
        sp(0.04),
        Table([[Paragraph(f'<font size="13"><b>{risk_key}</b></font>', ST["center_white"])]],
              colWidths=[CW - 2.6*inch],
              style=TableStyle([
                  ("BACKGROUND", (0,0),(0,0), risk_color),
                  ("TOPPADDING", (0,0),(0,0), 7), ("BOTTOMPADDING", (0,0),(0,0), 7),
              ])),
        sp(0.08),
        Paragraph('<font size="6.5" color="#888888"><b>OBSERVED RANGE — COMPARABLE CASES</b></font>', ST["label"]),
        Paragraph(f'<font size="15" color="#C0392B"><b>{settle["formatted_low"]} – {settle["formatted_high"]}</b></font>',
                  ParagraphStyle("dr", fontName="Helvetica-Bold", fontSize=15, textColor=HexColor("#C0392B"))),
        sp(0.04),
        Paragraph('<font size="7" color="#aaaaaa"><i>Typical ranges observed in similar accessibility claims. '
                  'Not a prediction of any specific legal action.</i></font>',
                  ParagraphStyle("disc", fontName="Helvetica-Oblique", fontSize=7,
                                 textColor=HexColor("#aaaaaa"), leading=10)),
        sp(0.05),
        Paragraph('<font size="6.5" color="#888888"><b>DEMAND PROBABILITY</b></font>', ST["label"]),
        Paragraph(e(plaintiff["demand_probability"]), ST["val"]),
    ]

    exec_table = Table(
        [[ScoreBadge(score, status, 2.4*inch), right_items]],
        colWidths=[2.6*inch, CW - 2.6*inch])
    exec_table.setStyle(TableStyle([("VALIGN", (0,0),(-1,-1), "TOP")]))
    story.append(exec_table)
    story.append(sp(0.1))

    # Stats bar
    stats_data = [[
        Paragraph(f'<b><font size="18">{crit_ct}</font></b><br/>'
                  f'<font size="6.5" color="#888888">CRITICAL ISSUES</font>', ST["body"]),
        Paragraph(f'<b><font size="18">{total_iss}</font></b><br/>'
                  f'<font size="6.5" color="#888888">TOTAL ISSUES</font>', ST["body"]),
        Paragraph(f'<b><font size="18">{len(cats)}</font></b><br/>'
                  f'<font size="6.5" color="#888888">CATEGORIES SCANNED</font>', ST["body"]),
        Paragraph(f'<b><font size="11" color="{checkout_color}">{checkout_label}</font></b><br/>'
                  f'<font size="6.5" color="#888888">CHECKOUT ACCESS</font>', ST["body"]),
    ]]
    stats_table = Table(stats_data, colWidths=[CW/4]*4)
    stats_table.setStyle(TableStyle([
        ("ALIGN", (0,0),(-1,-1), "CENTER"),
        ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
        ("BOX", (0,0),(-1,-1), 0.5, C_MID_GRAY),
        ("INNERGRID", (0,0),(-1,-1), 0.25, C_MID_GRAY),
        ("TOPPADDING", (0,0),(-1,-1), 9), ("BOTTOMPADDING", (0,0),(-1,-1), 9),
        ("BACKGROUND", (0,0),(-1,-1), C_LIGHT_GRAY),
    ]))
    story.append(stats_table)
    story.append(sp(0.08))
    story.append(Paragraph(e(plaintiff["description"]), ST["legal"]))
    if status == "fail":
        story.append(Paragraph(
            '<font color="#888888"><i>Note: A FAIL score indicates the presence of unresolved '
            'accessibility barriers — not total non-compliance. Documented remediation effort '
            'is recognized as a mitigating factor in ADA demand letter negotiations.</i></font>',
            ParagraphStyle("fn", fontName="Helvetica-Oblique", fontSize=7.5,
                           textColor=HexColor("#888888"), leading=11, spaceBefore=4)))
    story.append(Paragraph(
        '<font color="#C0392B"><b>Stores without active monitoring lose their defense record '
        'continuity.</b></font> Each lapsed scan creates a gap in your documented compliance '
        'posture — the exact gap plaintiff firms look for.',
        ParagraphStyle("urg", fontName="Helvetica", fontSize=8,
                       textColor=HexColor("#444444"), leading=12,
                       spaceBefore=6, borderPad=6,
                       backColor=HexColor("#FFF8F5"), leftIndent=8, rightIndent=8)))
    story.append(sp(0.18))

    # ── §04 CATEGORY BREAKDOWN ────────────────────────────────────────────────
    story.append(SectionHeader(4, "Category Breakdown", CW))
    story.append(sp(0.1))

    for cat in cats:
        cat_status = cat.get("status", "fail")
        cat_score  = cat.get("score", 0)
        cat_color  = {"pass": C_PASS, "warning": C_WARNING, "fail": C_FAIL}.get(cat_status, C_FAIL)

        cat_hdr = Table(
            [[Paragraph(f'<b>{e(cat["name"])}</b>', ST["sm"]),
              Paragraph(f'<font size="9" color="white"><b>  {cat_score}/100  {cat_status.upper()}  </b></font>',
                        ParagraphStyle("ch", fontName="Helvetica-Bold", fontSize=9,
                                       textColor=white, alignment=TA_RIGHT))]],
            colWidths=[CW*0.68, CW*0.32])
        cat_hdr.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(0,0), HexColor("#EEEAE0")),
            ("BACKGROUND", (1,0),(1,0), cat_color),
            ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ("LEFTPADDING", (0,0),(-1,-1), 8), ("RIGHTPADDING", (0,0),(-1,-1), 8),
        ]))
        story.append(cat_hdr)

        raw_issues = cat.get("issues", [])
        # Deduplicate — safety net for legacy receipts stored before engine fix
        deduped = dedup_issues(raw_issues)

        if deduped:
            rows = [["SEV", "DESCRIPTION & ELEMENT", "WCAG", "COUNT"]]
            for iss in deduped:
                sev = iss.get("severity", "minor")
                sc  = SEV_COLOR.get(sev, C_DARK_GRAY)
                cnt = iss.get("_total", iss.get("count", 1))
                rows.append([
                    Paragraph(f'<font size="6.5" color="white"><b>{sev[:4].upper()}</b></font>',
                              ParagraphStyle("sv", fontName="Helvetica-Bold", fontSize=6.5,
                                             textColor=white, backColor=sc, alignment=TA_CENTER)),
                    [Paragraph(et(iss.get("description",""), 110), ST["sm"]),
                     Paragraph(f'<font size="7" color="#777777" fontName="Courier">{et(iss.get("element",""), 90)}</font>', ST["xs"]),
                     Paragraph(f'<font size="7" color="#555555"><i>{et(iss.get("impact",""), 100)}</i></font>', ST["xs"])],
                    Paragraph(f'WCAG {e(iss.get("wcag",""))}', ST["xs"]),
                    Paragraph(f'<b>{cnt}</b>', ST["center_sm"]),
                ])

            iss_table = Table(rows, colWidths=[0.65*inch, CW-2.05*inch, 0.85*inch, 0.55*inch])
            iss_table.setStyle(TableStyle([
                ("BACKGROUND", (0,0),(-1,0), C_VOID),
                ("TEXTCOLOR", (0,0),(-1,0), C_GOLD),
                ("FONTNAME", (0,0),(-1,0), "Helvetica-Bold"),
                ("FONTSIZE", (0,0),(-1,0), 6.5),
                ("ROWBACKGROUNDS", (0,1),(-1,-1), [white, C_ROW_ALT]),
                ("BOX", (0,0),(-1,-1), 0.5, C_MID_GRAY),
                ("INNERGRID", (0,0),(-1,-1), 0.25, C_MID_GRAY),
                ("TOPPADDING", (0,0),(-1,-1), 4), ("BOTTOMPADDING", (0,0),(-1,-1), 4),
                ("LEFTPADDING", (0,0),(-1,-1), 5),
                ("VALIGN", (0,0),(-1,-1), "TOP"),
                ("ALIGN", (0,0),(-1,0), "CENTER"),
                ("ALIGN", (2,1),(2,-1), "CENTER"),
                ("ALIGN", (3,1),(3,-1), "CENTER"),
                ("VALIGN", (3,1),(3,-1), "MIDDLE"),
            ]))
            story.append(iss_table)
        else:
            story.append(Paragraph(
                "✓  No issues detected in this category.",
                ParagraphStyle("ok", fontName="Helvetica", fontSize=8.5,
                               textColor=C_PASS, backColor=HexColor("#F0FFF4"),
                               leftIndent=8, borderPad=5)))
        story.append(sp(0.1))

    # ── §05 PLAINTIFF SIMULATION REPORT ───────────────────────────────────────
    story.append(PageBreak())
    story.append(SectionHeader(5, "Plaintiff Simulation Report", CW))
    story.append(sp(0.1))
    story.append(Paragraph(
        "The following analysis simulates how a plaintiff attorney or automated scanning service "
        "would evaluate this site as a litigation target. IDR uses the same scanning methodology "
        "employed by plaintiff firms — the difference is who runs it first.",
        ST["legal"]))
    story.append(Paragraph(
        "This simulation reflects common patterns observed in accessibility-related claims "
        "and does not represent a specific legal action or prediction of litigation.",
        ParagraphStyle("sim_disc", fontName="Helvetica-Oblique", fontSize=7.5,
                       textColor=HexColor("#888888"), leading=11, spaceBefore=2)))
    story.append(sp(0.1))

    # Litigation flags — deduplicated
    flags = dedup_flags(plaintiff.get("litigation_flags", []))
    if flags:
        story.append(Paragraph("HIGH-VALUE VIOLATION FLAGS", ST["gold_head"]))
        flag_rows = [["VIOLATION TYPE", "LITIGATION\nVALUE", "WCAG", "INSTANCES", "LEGAL CONTEXT"]]
        for fl in flags:
            lv = fl.get("litigation_value", "MODERATE")
            lv_color = RISK_COLOR.get(lv, C_MODERATE)
            cnt = fl.get("_total", fl.get("count", 1))
            flag_rows.append([
                Paragraph(fl.get("rule","").replace("-"," ").title(), ST["sm"]),
                Paragraph(f'<font size="7" color="white"><b>{lv}</b></font>',
                          ParagraphStyle("lv", fontName="Helvetica-Bold", fontSize=7,
                                         textColor=white, backColor=lv_color, alignment=TA_CENTER)),
                Paragraph(f'WCAG\n{e(fl.get("wcag",""))}', ST["xs"]),
                Paragraph(f'<b>{cnt}</b>', ST["center_sm"]),
                Paragraph(e(fl.get("legal_note","")), ST["xs"]),
            ])

        flag_table = Table(flag_rows,
            colWidths=[1.2*inch, 0.8*inch, 0.6*inch, 0.6*inch, CW-3.2*inch])
        flag_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(-1,0), C_VOID),
            ("TEXTCOLOR", (0,0),(-1,0), C_GOLD),
            ("FONTNAME", (0,0),(-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0),(-1,0), 7),
            ("ROWBACKGROUNDS", (0,1),(-1,-1), [white, C_ROW_ALT]),
            ("BOX", (0,0),(-1,-1), 0.5, C_MID_GRAY),
            ("INNERGRID", (0,0),(-1,-1), 0.25, C_MID_GRAY),
            ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ("LEFTPADDING", (0,0),(-1,-1), 5),
            ("VALIGN", (0,0),(-1,-1), "TOP"),
            ("ALIGN", (1,1),(1,-1), "CENTER"),
            ("ALIGN", (2,1),(2,-1), "CENTER"),
            ("ALIGN", (3,1),(3,-1), "CENTER"),
            ("VALIGN", (3,0),(3,-1), "MIDDLE"),
        ]))
        story.append(flag_table)
        story.append(sp(0.15))

    # Comparable cases
    comparable = plaintiff.get("comparable_cases", [])
    if comparable:
        story.append(Paragraph("COMPARABLE CASE LAW", ST["gold_head"]))
        for case in comparable:
            ct = Table([
                [Paragraph(f'<b>{e(case["case"])}</b>  '
                           f'<font size="7.5" color="#888888">{e(case["citation"])}</font>',
                           ST["legal_bold"])],
                [Paragraph(e(case["outcome"]), ST["legal"])],
            ], colWidths=[CW])
            ct.setStyle(TableStyle([
                ("BACKGROUND", (0,0),(-1,-1), HexColor("#FAFAF5")),
                ("BOX", (0,0),(-1,-1), 0.5, C_GOLD),
                ("LEFTPADDING", (0,0),(-1,-1), 10), ("RIGHTPADDING", (0,0),(-1,-1), 10),
                ("TOPPADDING", (0,0),(-1,-1), 6), ("BOTTOMPADDING", (0,0),(-1,-1), 6),
            ]))
            story.append(ct)
            story.append(sp(0.07))

    story.append(sp(0.15))

    # ── §06 REMEDIATION GUIDANCE ──────────────────────────────────────────────
    story.append(SectionHeader(6, "Remediation Guidance", CW))
    story.append(sp(0.1))
    story.append(Paragraph(
        "The following before/after code corrections address each unique violation type found in "
        "this scan, ordered by severity. Applying these fixes and running a confirmation scan "
        "generates an updated Scan Receipt documenting your remediation effort.",
        ST["legal"]))
    story.append(sp(0.1))

    for rem in rems[:10]:
        sev     = rem.get("severity", "minor")
        sc      = SEV_COLOR.get(sev, C_DARK_GRAY)
        effort  = rem.get("effort", "LOW")
        ec      = EFFORT_COLOR.get(effort, C_MODERATE)

        rem_hdr = Table(
            [[Paragraph(f'<b>{e(rem.get("title",""))}</b>', ST["legal_bold"]),
              Paragraph(f'<font size="7" color="white"> {sev.upper()} </font>',
                        ParagraphStyle("rh", fontName="Helvetica-Bold", fontSize=7,
                                       textColor=white, alignment=TA_RIGHT)),
              Paragraph(f'<font size="7" color="white"> EFFORT: {effort} </font>',
                        ParagraphStyle("ef", fontName="Helvetica-Bold", fontSize=7,
                                       textColor=white, alignment=TA_RIGHT))]],
            colWidths=[CW-1.9*inch, 0.85*inch, 1.05*inch])
        rem_hdr.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(0,0), HexColor("#F0EDE6")),
            ("BACKGROUND", (1,0),(1,0), sc),
            ("BACKGROUND", (2,0),(2,0), ec),
            ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ("LEFTPADDING", (0,0),(-1,-1), 8),
        ]))
        story.append(rem_hdr)

        before_raw = he(rem.get("before","")).replace("\n","<br/>").replace(" ","&nbsp;")
        after_raw  = he(rem.get("after","")).replace("\n","<br/>").replace(" ","&nbsp;")

        code_tbl = Table(
            [[Paragraph('<font size="6.5" color="#888888"><b>BEFORE — VIOLATION</b></font>', ST["label"]),
              Paragraph('<font size="6.5" color="#27AE60"><b>AFTER — CORRECTED</b></font>', ST["label"])],
             [Paragraph(before_raw, ST["mono"]),
              Paragraph(after_raw,  ST["mono_green"])]],
            colWidths=[CW/2 - 0.04*inch, CW/2 - 0.04*inch])
        code_tbl.setStyle(TableStyle([
            ("VALIGN", (0,0),(-1,-1), "TOP"),
            ("TOPPADDING", (0,0),(-1,-1), 4), ("BOTTOMPADDING", (0,0),(-1,-1), 4),
            ("LEFTPADDING", (0,0),(-1,-1), 0), ("RIGHTPADDING", (0,0),(-1,-1), 0),
        ]))
        story.append(code_tbl)
        story.append(Paragraph(f'<i>{he(rem.get("note",""))}</i>', ST["xs"]))
        story.append(hr())

    story.append(sp(0.1))

    # ── §07 EVIDENCE LOG CHAIN ────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(SectionHeader(7, "Evidence Log Chain", CW))
    story.append(sp(0.1))
    story.append(Paragraph(
        "Chronological audit trail for this scan session. Each entry is linked to this "
        "receipt via its unique identifier and establishes the chain of custody for legal purposes.",
        ST["legal"]))
    story.append(sp(0.1))

    ts_short = ts[:19].replace("T"," ") + " UTC"
    log_rows = [["TIMESTAMP (UTC)", "EVENT TYPE", "DETAIL"]]
    log_data = [
        (ts_short, "SCAN_INITIATED", f"Automated accessibility scan initiated for {domain}"),
        (ts_short, "SCAN_COMPLETED",
         f"Scan completed in {scan.get('scan_duration_ms',0)}ms. Score: {score}/100. "
         f"Critical: {crit_ct}. Total issues: {total_iss}."),
        (ts_short, "RECEIPT_GENERATED", f"Scan Receipt generated. ID: {rid}"),
        (ts_short, "HASH_COMPUTED", f"SHA-256 hash computed: {hash_val[:32]}..."),
        (ts_short, "REGISTRY_UPDATED", f"Registry record updated at {reg_url}"),
    ]
    for ts_v, evt, detail in log_data:
        log_rows.append([
            Paragraph(e(ts_v), ST["xs"]),
            Paragraph(f'<font size="7" color="#C4A052"><b>{e(evt)}</b></font>', ST["xs"]),
            Paragraph(e(detail), ST["xs"]),
        ])

    log_tbl = Table(log_rows, colWidths=[1.6*inch, 1.25*inch, CW-2.85*inch])
    log_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,0), C_VOID),
        ("TEXTCOLOR", (0,0),(-1,0), C_GOLD),
        ("FONTNAME", (0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0),(-1,0), 7),
        ("ROWBACKGROUNDS", (0,1),(-1,-1), [white, C_ROW_ALT]),
        ("BOX", (0,0),(-1,-1), 0.5, C_MID_GRAY),
        ("INNERGRID", (0,0),(-1,-1), 0.25, C_MID_GRAY),
        ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING", (0,0),(-1,-1), 6),
        ("VALIGN", (0,0),(-1,-1), "TOP"),
    ]))
    story.append(log_tbl)
    story.append(sp(0.18))

    # ── §08 SHA-256 VERIFICATION BLOCK ────────────────────────────────────────
    story.append(SectionHeader(8, "SHA-256 Verification Block", CW))
    story.append(sp(0.1))

    hash_meta = receipt.get("hash", {})
    ver_tbl = Table([
        [Paragraph('<font size="6.5" color="#888888"><b>ALGORITHM</b></font>', ST["label"]),
         Paragraph(e(hash_meta.get("algorithm","SHA-256")), ST["val"]),
         Paragraph('<font size="6.5" color="#888888"><b>INPUT SIZE</b></font>', ST["label"]),
         Paragraph(f'{hash_meta.get("input_bytes",0):,} bytes', ST["val"])],
        [Paragraph('<font size="6.5" color="#888888"><b>OPERATOR</b></font>', ST["label"]),
         Paragraph(e(receipt.get("operator","IDR_SCANNER_v1")), ST["val"]),
         Paragraph('<font size="6.5" color="#888888"><b>PROTOCOL</b></font>', ST["label"]),
         Paragraph(e(receipt.get("idr_protocol","IDR-BRAND-2026-01")), ST["val"])],
    ], colWidths=[1.0*inch, 2.8*inch, 1.0*inch, 2.8*inch])
    ver_tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0),(-1,-1), [C_LIGHT_GRAY, white]),
        ("BOX", (0,0),(-1,-1), 0.5, C_MID_GRAY),
        ("INNERGRID", (0,0),(-1,-1), 0.25, C_MID_GRAY),
        ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING", (0,0),(-1,-1), 8),
    ]))
    story.append(ver_tbl)
    story.append(sp(0.08))

    hash_box = Table([[Paragraph(
        f'<font size="6.5" color="#888888"><b>SHA-256 HASH</b></font><br/>'
        f'<font size="8.5" fontName="Courier">{e(hash_val)}</font>',
        ParagraphStyle("hv", fontName="Courier", fontSize=8.5,
                       textColor=HexColor("#1A1A1A"), backColor=HexColor("#F5F0E8"),
                       borderPad=8, leading=16)
    )]], colWidths=[CW])
    hash_box.setStyle(TableStyle([
        ("BOX", (0,0),(-1,-1), 1.5, C_GOLD),
        ("TOPPADDING", (0,0),(-1,-1), 10), ("BOTTOMPADDING", (0,0),(-1,-1), 10),
        ("LEFTPADDING", (0,0),(-1,-1), 12),
    ]))
    story.append(hash_box)
    story.append(sp(0.08))
    story.append(Paragraph(
        "This hash was computed at receipt generation over the canonical payload "
        "(receipt_id, registry_id, timestamp_utc, operator, scan data) using SHA-256. "
        "Any modification — including timestamp, score, or issue data — produces a different hash. "
        "The original hash is immutably stored in the IDR Registry. Tamper-evident by design.",
        ST["legal"]))
    story.append(sp(0.18))

    # ── §09 REGISTRY RECORD ───────────────────────────────────────────────────
    story.append(SectionHeader(9, "Registry Record", CW))
    story.append(sp(0.1))

    reg_status = "active" if (status == "pass" and crit_ct == 0) else "monitoring"
    reg_color  = C_PASS if reg_status == "active" else C_WARNING

    reg_tbl = Table([
        [Paragraph('<font size="6.5" color="#888888"><b>REGISTRY URL</b></font>', ST["label"]),
         Paragraph(e(reg_url), ParagraphStyle("ru", fontName="Helvetica", fontSize=8.5,
                                               textColor=HexColor("#0645AD")))],
        [Paragraph('<font size="6.5" color="#888888"><b>REGISTRY STATUS</b></font>', ST["label"]),
         Paragraph(f'<font color="white"><b>  {reg_status.upper()}  </b></font>',
                   ParagraphStyle("rs", fontName="Helvetica-Bold", fontSize=8.5,
                                  textColor=white, backColor=reg_color))],
        [Paragraph('<font size="6.5" color="#888888"><b>LAST SCANNED</b></font>', ST["label"]),
         Paragraph(ts[:10], ST["val"])],
        [Paragraph('<font size="6.5" color="#888888"><b>SCAN COUNT</b></font>', ST["label"]),
         Paragraph("1", ST["val"])],
    ], colWidths=[1.4*inch, CW-1.4*inch])
    reg_tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0,0),(-1,-1), [white, C_LIGHT_GRAY]),
        ("BOX", (0,0),(-1,-1), 0.5, C_MID_GRAY),
        ("INNERGRID", (0,0),(-1,-1), 0.25, C_MID_GRAY),
        ("TOPPADDING", (0,0),(-1,-1), 6), ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING", (0,0),(-1,-1), 8),
        ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(reg_tbl)
    story.append(sp(0.1))

    # Badge embed — pre-escaped, no HTML tag parsing issues
    badge_lines = [
        "&lt;!-- IDR Verified Badge --&gt;",
        f'&lt;script src="https://idrshield.com/badge.js"',
        f'&nbsp;&nbsp;data-store="{e(domain)}"',
        f'&nbsp;&nbsp;data-registry="{e(reg_id)}"&gt;',
        "&lt;/script&gt;",
    ]
    story.append(Paragraph('<font size="6.5" color="#888888"><b>BADGE EMBED CODE</b></font>', ST["label"]))
    story.append(sp(0.04))
    story.append(Paragraph("<br/>".join(badge_lines), ST["mono"]))
    story.append(sp(0.18))

    # ── §10 LEGAL POSITIONING STATEMENT ───────────────────────────────────────
    story.append(SectionHeader(10, "Legal Positioning Statement", CW))
    story.append(sp(0.1))

    sections = [
        ("DEFENSE RECORD STATEMENT",
         "This Scan Receipt constitutes a timestamped, third-party accessibility audit record created "
         "by the Institute of Digital Remediation (IDR). The receipt documents the accessibility state "
         "of the above-referenced domain at the time of scanning. The SHA-256 hash provides "
         "cryptographic proof of the receipt's integrity — any post-generation modification "
         "is mathematically detectable."),
        ("ADA COMPLIANCE CONTEXT",
         "Title III of the Americans with Disabilities Act (ADA) has been interpreted by multiple "
         "federal courts to apply to commercial websites. WCAG 2.1 Level AA is the broadly accepted "
         "technical standard for ADA compliance in e-commerce. Stores with documented remediation "
         "efforts and compliance records have historically achieved more favorable outcomes in "
         "ADA demand letter negotiations and litigation."),
        ("PROACTIVE DEFENSE POSTURE",
         "The same automated systems used by plaintiff law firms to identify targets are the systems "
         "IDR uses to build your defense record. By running this scan first, generating an immutable "
         "receipt, and pursuing remediation, you establish: (1) awareness of the issue, "
         "(2) good-faith remediation effort, and (3) a timestamped baseline that precedes any "
         "potential demand letter. This posture has been used to negotiate reduced settlements "
         "and dismissals."),
        ("DISCLAIMER",
         "The Institute of Digital Remediation is not a law firm and does not provide legal advice. "
         "This receipt is a compliance documentation and monitoring system. Settlement range estimates "
         "are based on publicly available case data and are for informational purposes only. "
         "Consult qualified legal counsel for advice specific to your situation. IDR-PROTOCOL-2026."),
    ]
    for title, text in sections:
        story.append(Paragraph(title, ST["gold_head"]))
        story.append(Paragraph(text, ST["legal"]))
        story.append(sp(0.05))

    # Footer
    story.append(sp(0.15))
    footer = Table([[Paragraph(
        f'<font size="7" color="white">Institute of Digital Remediation  ·  idrshield.com  ·  '
        f'hello@idrshield.com  ·  {e(rid)}</font>',
        ParagraphStyle("ft", fontName="Helvetica", fontSize=7,
                       textColor=white, alignment=TA_CENTER)
    )]], colWidths=[CW])
    footer.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), C_VOID),
        ("TOPPADDING", (0,0),(-1,-1), 8), ("BOTTOMPADDING", (0,0),(-1,-1), 8),
    ]))
    story.append(footer)

    doc.build(story)
    return buf.getvalue()
