"""
IDR Shield — hhs_certificate.py
HHS Accessibility Remediation Verification Certificate
Two-page, court-ready. Generated when all critical violations confirmed closed.
"""

import io, hashlib
from datetime import datetime, timezone
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle,
    PageBreak,
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
import qrcode, qrcode.constants
from reportlab.lib.utils import ImageReader

NAVY      = colors.HexColor('#0A0E1A')
GOLD      = colors.HexColor('#C9A84C')
GOLD_DARK = colors.HexColor('#8A6F2E')
CREAM     = colors.HexColor('#FAF8F4')
CREAM_MID = colors.HexColor('#F2EFE9')
CREAM_DRK = colors.HexColor('#E2DDD5')
CHARCOAL  = colors.HexColor('#1A1A2E')
GRAY_MID  = colors.HexColor('#7A7A8A')
GRAY_LT   = colors.HexColor('#B0B0C0')
GREEN     = colors.HexColor('#1A7A3C')
GREEN_LT  = colors.HexColor('#EEF8F2')
RED_CRIT  = colors.HexColor('#B8280A')
AMBER     = colors.HexColor('#C47F00')
WHITE     = colors.white

PAGE_W, PAGE_H = letter
M = 0.75 * inch
HEADER_H = 0.36 * inch
FOOTER_H = 0.28 * inch
BODY_Y   = M + FOOTER_H + 0.06*inch
BODY_H   = PAGE_H - M - HEADER_H - 0.12*inch - BODY_Y

class _St:
    registry_id = ''; cert_hash = ''; total_pages = 2
_state = _St()

def _qr(url):
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=7, border=2)
    q.add_data(url); q.make(fit=True)
    img = q.make_image(fill_color='#0A0E1A', back_color='#FAF8F4')
    buf = io.BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
    return ImageReader(buf)

def _seal(c, cx, cy, r=32):
    c.setFillColor(NAVY); c.circle(cx, cy, r, fill=1, stroke=0)
    c.setStrokeColor(GOLD); c.setLineWidth(1.2); c.circle(cx, cy, r-1.5, fill=0, stroke=1)
    c.setFillColor(GOLD); c.setFont('Times-Bold', r*0.38)
    c.drawCentredString(cx, cy-r*0.12, 'IDR')
    c.saveState(); c.setStrokeColor(GOLD_DARK); c.setLineWidth(0.5); c.setStrokeAlpha(0.4)
    hw = r*0.52; c.line(cx-hw, cy-r*0.28, cx+hw, cy-r*0.28); c.restoreState()

def _watermark(c):
    c.saveState(); c.setFillColor(NAVY); c.setFillAlpha(0.025); c.setFont('Times-Bold', 44)
    c.translate(PAGE_W/2, PAGE_H/2); c.rotate(42)
    c.drawCentredString(0, 40, 'INSTITUTE OF DIGITAL REMEDIATION')
    c.drawCentredString(0,-40, 'INSTITUTE OF DIGITAL REMEDIATION')
    c.setFillAlpha(1.0); c.restoreState()

def _header(c):
    c.setFillColor(GOLD); c.rect(0, PAGE_H-5, PAGE_W, 5, fill=1, stroke=0)
    c.setFillColor(NAVY); c.rect(0, PAGE_H-5-HEADER_H, PAGE_W, HEADER_H, fill=1, stroke=0)
    y = PAGE_H-5-HEADER_H/2-3
    c.setFillColor(GOLD); c.setFillAlpha(0.60)
    c.setFont('Helvetica-Bold', 6); c.drawString(M, y, 'IDR HHS REMEDIATION VERIFICATION CERTIFICATE')
    c.setFont('Courier', 6); c.drawRightString(PAGE_W-M, y, _state.registry_id)
    c.setFillAlpha(1.0)

def _footer(c, pg):
    c.setStrokeColor(CREAM_DRK); c.setLineWidth(0.4)
    yf = BODY_Y - 5; c.line(M, yf, PAGE_W-M, yf)
    h = _state.cert_hash[:44]+'…' if len(_state.cert_hash)>44 else _state.cert_hash
    c.setFillColor(GRAY_LT); c.setFont('Courier', 5)
    c.drawString(M, yf-10, f'SHA-256: {h}')
    c.setFont('Helvetica', 6); c.setFillColor(GRAY_MID)
    c.drawRightString(PAGE_W-M, yf-10, f'Page {pg} of {_state.total_pages}')
    c.setFillColor(GOLD); c.rect(0, 0, PAGE_W, 4, fill=1, stroke=0)

def _on_page(c, doc):
    _watermark(c); _header(c); _footer(c, doc.page)

class GoldRule(Flowable):
    def __init__(self, h=0.75, pt=4, pb=4):
        super().__init__(); self.h=h; self.pt=pt; self.pb=pb
    def wrap(self, aW, aH): self.W=aW; return aW, self.h+self.pt+self.pb
    def draw(self):
        self.canv.setStrokeColor(GOLD); self.canv.setLineWidth(self.h)
        self.canv.line(0, self.pb, self.W, self.pb)

class GreenStamp(Flowable):
    """REMEDIATION VERIFIED green stamp."""
    def wrap(self, aW, aH): self.W=aW; return aW, 48
    def draw(self):
        c = self.canv; W = self.W
        # Green border box
        c.setStrokeColor(GREEN); c.setLineWidth(2)
        c.roundRect(W/2-110, 4, 220, 40, 4, fill=0, stroke=1)
        # Text
        c.setFillColor(GREEN); c.setFont('Helvetica-Bold', 11); c.setFillAlpha(0.9)
        c.drawCentredString(W/2, 20, 'REMEDIATION VERIFIED')
        c.setFont('Helvetica', 7); c.setFillAlpha(0.6)
        c.drawCentredString(W/2, 11, 'IDR HHS Compliance Registry')
        c.setFillAlpha(1.0)

class SealFL(Flowable):
    def __init__(self, r=32): super().__init__(); self.r=r
    def wrap(self, aW, aH): self.W=aW; return aW, self.r*2+16
    def draw(self): _seal(self.canv, self.W/2, self.r+8, self.r)

class QRFL(Flowable):
    def __init__(self, url, sz=1.1*inch, cap=''):
        super().__init__(); self.url=url; self.sz=sz; self.cap=cap; self._ir=None
    def _img(self):
        if not self._ir: self._ir=_qr(self.url)
        return self._ir
    def wrap(self, aW, aH): self.W=aW; return self.sz, self.sz+14
    def draw(self):
        self.canv.drawImage(self._img(), 0, 14, self.sz, self.sz, preserveAspectRatio=True)
        if self.cap:
            self.canv.setFillColor(GRAY_MID); self.canv.setFont('Helvetica', 5.5)
            self.canv.drawCentredString(self.sz/2, 2, self.cap)

def _p(name, **kw):
    d = dict(fontName='Times-Roman', fontSize=10, textColor=CHARCOAL, leading=14, spaceAfter=4)
    d.update(kw); return ParagraphStyle(name, **d)

def _kv_tbl(rows, c1=1.8*inch, gold=True):
    Cw = PAGE_W - 2*M
    data = [[
        Paragraph(k, _p('kk', fontName='Helvetica-Bold', fontSize=6.5,
                         textColor=GRAY_MID, leading=10, letterSpacing=0.5)),
        Paragraph(str(v), _p('kv', fontName='Courier', fontSize=8,
                              textColor=CHARCOAL, leading=11)),
    ] for k,v in rows]
    t = Table(data, colWidths=[c1, Cw-c1])
    st = [('BACKGROUND',(0,0),(0,-1),CREAM_MID),('BACKGROUND',(1,0),(1,-1),CREAM),
          ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
          ('LEFTPADDING',(0,0),(-1,-1),10),('GRID',(0,0),(-1,-1),0.4,CREAM_DRK)]
    if gold:
        st += [('LINEABOVE',(0,0),(-1,0),1.5,GOLD),('LINEBELOW',(0,-1),(-1,-1),1.5,GOLD)]
    t.setStyle(TableStyle(st)); return t


def _dt(ts):
    try:
        d = datetime.strptime(ts[:10], '%Y-%m-%d')
        return d.strftime('%B %d, %Y')
    except:
        return datetime.now(timezone.utc).strftime('%B %d, %Y')


def _sc(s):
    return GREEN if s>=80 else AMBER if s>=60 else RED_CRIT


# ── Main generator ─────────────────────────────────────────────────────────────

def generate_verification_certificate(
    domain: str,
    org_name: str,
    registry_id: str,
    receipt_id: str,
    original_audit_date: str,
    verification_date: str,
    original_score: int,
    verified_score: int,
    violations_closed: list,
    violations_still_open: list,
    auditor_name: str = 'Hans-Peter Nkansah',
    organization: dict = None,
) -> bytes:
    """
    Generate the IDR HHS Remediation Verification Certificate.

    Args:
        violations_closed: list of {rule, category, severity, wcag,
                                    original_count, closed_date}
        violations_still_open: list of {rule, category, severity, wcag,
                                         original_count, days_open}
    Returns: bytes — PDF
    """
    verify_url   = f'https://idrshield.com/hhs-verify/{domain}'
    cert_date    = _dt(verification_date) if verification_date else datetime.now(timezone.utc).strftime('%B %d, %Y')
    audit_date   = _dt(original_audit_date) if original_audit_date else '—'
    org          = organization or {}
    all_critical_closed = all(
        v.get('severity','').lower() == 'critical'
        for v in violations_still_open
    ) == False or len(violations_still_open) == 0

    cert_status = 'FULL REMEDIATION VERIFIED' if len(violations_still_open) == 0 else 'PARTIAL REMEDIATION VERIFIED'

    # Hash
    import json as _j
    payload = _j.dumps({
        'domain': domain, 'registry_id': registry_id,
        'cert_date': cert_date, 'verified_score': verified_score,
        'closed': len(violations_closed), 'open': len(violations_still_open),
    }, sort_keys=True)
    cert_hash = hashlib.sha256(payload.encode()).hexdigest()

    _state.registry_id  = registry_id
    _state.cert_hash    = cert_hash
    _state.total_pages  = 2

    Cw = PAGE_W - 2*M
    buf = io.BytesIO()

    body_frame = Frame(M, BODY_Y, Cw, BODY_H,
                       id='bf', leftPadding=0, rightPadding=0,
                       topPadding=4, bottomPadding=0)
    doc = BaseDocTemplate(
        buf, pagesize=letter,
        leftMargin=M, rightMargin=M,
        topMargin=M+HEADER_H+0.12*inch,
        bottomMargin=M+FOOTER_H+0.08*inch,
        title=f'IDR HHS Verification Certificate — {domain}',
        author='Institute of Digital Remediation',
        subject=f'Remediation Verification · {domain} · {registry_id}',
    )
    doc.addPageTemplates([PageTemplate(id='Main', frames=[body_frame], onPage=_on_page)])

    S = []

    # ── PAGE 1 — Certificate ──────────────────────────────────────────────────
    S.append(Spacer(1, 0.10*inch))
    S.append(SealFL(r=36))
    S.append(Spacer(1, 0.12*inch))

    S.append(Paragraph('INSTITUTE OF DIGITAL REMEDIATION',
        _p('ci', fontName='Helvetica-Bold', fontSize=7, textColor=GOLD_DARK,
           leading=10, alignment=TA_CENTER, letterSpacing=2.5, spaceAfter=2)))
    S.append(Paragraph('HHS Compliance Division  ·  2026',
        _p('cs', fontName='Times-Italic', fontSize=9, textColor=GRAY_MID,
           leading=12, alignment=TA_CENTER, spaceAfter=0)))
    S.append(Spacer(1, 0.16*inch))
    S.append(GoldRule(h=1.0, pt=0, pb=0))
    S.append(Spacer(1, 0.14*inch))

    S.append(Paragraph('HHS ACCESSIBILITY REMEDIATION',
        _p('t1', fontName='Times-Bold', fontSize=22, textColor=NAVY,
           leading=26, alignment=TA_CENTER, spaceAfter=3)))
    S.append(Paragraph('VERIFICATION CERTIFICATE',
        _p('t2', fontName='Times-Bold', fontSize=22, textColor=NAVY,
           leading=26, alignment=TA_CENTER, spaceAfter=0)))
    S.append(Spacer(1, 0.08*inch))
    S.append(Paragraph(domain.upper(),
        _p('dom', fontName='Helvetica-Bold', fontSize=11, textColor=GOLD,
           leading=14, alignment=TA_CENTER, letterSpacing=1.5, spaceAfter=0)))
    S.append(Spacer(1, 0.14*inch))

    # Green verified stamp
    S.append(GreenStamp())
    S.append(Spacer(1, 0.14*inch))

    # Certificate details table
    org_display = org.get('name', org_name)
    S.append(_kv_tbl([
        ('ORGANIZATION',        org_display),
        ('DOMAIN',              domain),
        ('REGISTRY ID',         registry_id),
        ('ORIGINAL AUDIT DATE', audit_date),
        ('VERIFICATION DATE',   cert_date),
        ('ORIGINAL SCORE',      f'{original_score} / 100'),
        ('VERIFIED SCORE',      f'{verified_score} / 100'),
        ('VIOLATIONS VERIFIED CLOSED', str(len(violations_closed))),
        ('VIOLATIONS STILL OPEN',      str(len(violations_still_open))),
        ('CERTIFICATE STATUS',  cert_status),
        ('CERTIFICATE HASH',    cert_hash[:32]+'…'),
        ('STANDARD',            'WCAG 2.1 Level AA · Section 504 · Section 1557 ACA'),
    ]))
    S.append(Spacer(1, 0.14*inch))

    # Certification statement
    stmt = (
        f'This certificate confirms that IDR Engine v3 conducted an external verification '
        f're-scan of <b>{org_display}</b> ({domain}) on {cert_date}. '
        f'The re-scan confirmed that <b>{len(violations_closed)} violation(s)</b> identified '
        f'in the original audit dated {audit_date} are no longer present on the live site. '
        f'This constitutes independent, third-party verification that remediation was completed.'
    )
    S.append(Paragraph(stmt,
        _p('stmt', fontSize=10, alignment=TA_JUSTIFY, leading=16)))
    S.append(Spacer(1, 0.14*inch))

    # Signature
    S.append(GoldRule(h=0.75))
    S.append(Spacer(1, 0.10*inch))
    S.append(Paragraph(auditor_name,
        _p('sn', fontName='Times-BoldItalic', fontSize=24, textColor=NAVY, leading=28, spaceAfter=4)))
    S.append(Paragraph('Lead Accessibility Auditor',
        _p('sd', fontName='Helvetica', fontSize=8, textColor=GRAY_MID, leading=12, spaceAfter=2)))
    S.append(Paragraph('Institute of Digital Remediation',
        _p('sd2', fontName='Helvetica', fontSize=8, textColor=GRAY_MID, leading=12, spaceAfter=2)))
    S.append(Paragraph(f'Certified: {cert_date}',
        _p('sd3', fontName='Helvetica', fontSize=8, textColor=GRAY_MID, leading=12, spaceAfter=0)))

    S.append(PageBreak())

    # ── PAGE 2 — Violation Status Table ──────────────────────────────────────
    S.append(Paragraph('VIOLATION STATUS RECORD', _p('ey', fontName='Helvetica-Bold',
        fontSize=6.5, textColor=GOLD_DARK, leading=9, spaceAfter=3, letterSpacing=2.2)))
    S.append(GoldRule())
    S.append(Spacer(1, 0.08*inch))
    S.append(Paragraph('Violation Closure Record',
        _p('h1', fontName='Times-Bold', fontSize=18, textColor=NAVY, leading=22, spaceAfter=6)))
    S.append(Paragraph(
        f'The following table documents the status of all violations identified in the original '
        f'IDR HHS Accessibility Audit of {org_display} conducted on {audit_date}. '
        f'Status is determined by external re-scan conducted on {cert_date}.',
        _p('body', fontSize=9.5, alignment=TA_JUSTIFY, leading=15)))
    S.append(Spacer(1, 0.12*inch))

    # Re-scan score comparison
    score_rows = [[
        Paragraph('ORIGINAL SCORE',
            _p('sk', fontName='Helvetica-Bold', fontSize=6.5, textColor=GRAY_MID,
               leading=10, letterSpacing=0.5)),
        Paragraph(f'<b>{original_score}/100</b>',
            _p('sv', fontName='Courier-Bold', fontSize=10,
               textColor=_sc(original_score), leading=13, alignment=TA_RIGHT)),
    ],[
        Paragraph('VERIFIED SCORE',
            _p('sk2', fontName='Helvetica-Bold', fontSize=6.5, textColor=GRAY_MID,
               leading=10, letterSpacing=0.5)),
        Paragraph(f'<b>{verified_score}/100</b>',
            _p('sv2', fontName='Courier-Bold', fontSize=11,
               textColor=_sc(verified_score), leading=13, alignment=TA_RIGHT)),
    ]]
    sct = Table(score_rows, colWidths=[Cw-1.0*inch, 1.0*inch])
    sct.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),CREAM),
        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
        ('GRID',(0,0),(-1,-1),0.4,CREAM_DRK),
        ('LINEABOVE',(0,0),(-1,0),1.5,GOLD),('LINEBELOW',(0,-1),(-1,-1),1.5,GOLD),
    ]))
    S.append(sct)
    S.append(Spacer(1, 0.14*inch))

    # Violation table header
    hdr = Table([[
        Paragraph('RULE', _p('th', fontName='Helvetica-Bold', fontSize=6, textColor=GOLD, leading=8, letterSpacing=0.8)),
        Paragraph('CATEGORY', _p('th2', fontName='Helvetica-Bold', fontSize=6, textColor=GOLD, leading=8, letterSpacing=0.8)),
        Paragraph('SEVERITY', _p('th3', fontName='Helvetica-Bold', fontSize=6, textColor=GOLD, leading=8, letterSpacing=0.8, alignment=TA_CENTER)),
        Paragraph('WCAG', _p('th4', fontName='Helvetica-Bold', fontSize=6, textColor=GOLD, leading=8, letterSpacing=0.8, alignment=TA_CENTER)),
        Paragraph('STATUS', _p('th5', fontName='Helvetica-Bold', fontSize=6, textColor=GOLD, leading=8, letterSpacing=0.8, alignment=TA_CENTER)),
        Paragraph('CLOSED DATE', _p('th6', fontName='Helvetica-Bold', fontSize=6, textColor=GOLD, leading=8, letterSpacing=0.8, alignment=TA_CENTER)),
    ]], colWidths=[1.4*inch, 1.2*inch, 0.65*inch, 0.55*inch, 0.9*inch, Cw-4.7*inch])
    hdr.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),NAVY),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),8),
        ('LINEABOVE',(0,0),(-1,0),1.5,GOLD),
    ]))
    S.append(hdr)

    # Closed violations
    for i, v in enumerate(violations_closed):
        sev = v.get('severity','').lower()
        sc2 = RED_CRIT if sev=='critical' else AMBER if sev=='serious' else GRAY_MID
        bg  = GREEN_LT if i%2==0 else CREAM
        row = Table([[
            Paragraph(v.get('rule',''), _p('r1', fontName='Courier', fontSize=7, textColor=CHARCOAL, leading=10)),
            Paragraph(v.get('category',''), _p('r2', fontName='Times-Roman', fontSize=8, textColor=CHARCOAL, leading=11)),
            Paragraph(sev.upper(), _p('r3', fontName='Helvetica-Bold', fontSize=7, textColor=sc2, leading=10, alignment=TA_CENTER)),
            Paragraph(v.get('wcag',''), _p('r4', fontName='Courier', fontSize=7, textColor=GRAY_MID, leading=10, alignment=TA_CENTER)),
            Paragraph('<font color="#1A7A3C"><b>CLOSED</b></font>',
                      _p('r5', fontName='Helvetica-Bold', fontSize=7, textColor=GREEN, leading=10, alignment=TA_CENTER)),
            Paragraph(v.get('closed_date', cert_date),
                      _p('r6', fontName='Courier', fontSize=7, textColor=GRAY_MID, leading=10, alignment=TA_CENTER)),
        ]], colWidths=[1.4*inch, 1.2*inch, 0.65*inch, 0.55*inch, 0.9*inch, Cw-4.7*inch])
        row.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),bg),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
            ('LEFTPADDING',(0,0),(-1,-1),8),
            ('LINEBELOW',(0,0),(-1,-1),0.3,CREAM_DRK),
        ]))
        S.append(row)

    # Still open violations
    for i, v in enumerate(violations_still_open):
        sev = v.get('severity','').lower()
        sc2 = RED_CRIT if sev=='critical' else AMBER if sev=='serious' else GRAY_MID
        row = Table([[
            Paragraph(v.get('rule',''), _p('ro1', fontName='Courier', fontSize=7, textColor=CHARCOAL, leading=10)),
            Paragraph(v.get('category',''), _p('ro2', fontName='Times-Roman', fontSize=8, textColor=CHARCOAL, leading=11)),
            Paragraph(sev.upper(), _p('ro3', fontName='Helvetica-Bold', fontSize=7, textColor=sc2, leading=10, alignment=TA_CENTER)),
            Paragraph(v.get('wcag',''), _p('ro4', fontName='Courier', fontSize=7, textColor=GRAY_MID, leading=10, alignment=TA_CENTER)),
            Paragraph('<font color="#B8280A"><b>OPEN</b></font>',
                      _p('ro5', fontName='Helvetica-Bold', fontSize=7, textColor=RED_CRIT, leading=10, alignment=TA_CENTER)),
            Paragraph('—', _p('ro6', fontName='Courier', fontSize=7, textColor=GRAY_MID, leading=10, alignment=TA_CENTER)),
        ]], colWidths=[1.4*inch, 1.2*inch, 0.65*inch, 0.55*inch, 0.9*inch, Cw-4.7*inch])
        row.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#FDF4F4')),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
            ('LEFTPADDING',(0,0),(-1,-1),8),
            ('LINEBELOW',(0,0),(-1,-1),0.3,CREAM_DRK),
        ]))
        S.append(row)

    # Close gold rule
    S.append(Table([[Spacer(1,1)]], colWidths=[Cw],
                    style=TableStyle([('LINEABOVE',(0,0),(-1,-1),1.5,GOLD),
                                      ('TOPPADDING',(0,0),(-1,-1),0),
                                      ('BOTTOMPADDING',(0,0),(-1,-1),0)])))
    S.append(Spacer(1, 0.14*inch))

    # QR + verify block
    qr_f = QRFL(verify_url, sz=1.1*inch, cap=f'Scan to verify · {verify_url}')
    url_p = Paragraph(
        f'<font color="#8A6F2E"><b>Verify URL:</b></font><br/>'
        f'<font name="Courier" size="9" color="#1A1A2E">{verify_url}</font><br/><br/>'
        f'<font name="Helvetica" size="7.5" color="#7A7A8A">'
        f'This certificate is publicly verifiable. Registry status reflects '
        f'REMEDIATION VERIFIED as of {cert_date}.</font>',
        _p('vu', fontName='Helvetica', fontSize=10, textColor=CHARCOAL, leading=16))
    qt = Table([[qr_f, url_p]], colWidths=[1.4*inch, Cw-1.4*inch])
    qt.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(0,0),8),('LEFTPADDING',(1,0),(1,0),16),
        ('RIGHTPADDING',(0,0),(-1,-1),8),
        ('BACKGROUND',(0,0),(-1,-1),CREAM),
        ('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12),
        ('LINEABOVE',(0,0),(-1,0),1.0,GOLD),('LINEBELOW',(0,-1),(-1,-1),1.0,GOLD),
        ('BOX',(0,0),(-1,-1),0.4,CREAM_DRK),
    ]))
    S.append(qt)
    S.append(Spacer(1, 0.10*inch))
    S.append(Paragraph(
        'Institute of Digital Remediation  ·  idrshield.com  ·  hello@idrshield.com  ·  IDR-BRAND-2026-01',
        _p('ftr', fontName='Helvetica', fontSize=7, textColor=GRAY_LT, leading=9, alignment=TA_CENTER)))

    doc.build(S)
    return buf.getvalue()


# ── Test ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    pdf = generate_verification_certificate(
        domain              = 'orlandohealth.com',
        org_name            = 'Orlando Health, Inc.',
        registry_id         = 'IDR-HHS-ORLANDOHEALTH-COM',
        receipt_id          = 'IDR-2026-A9F3C821',
        original_audit_date = '2026-04-26',
        verification_date   = '2026-05-26',
        original_score      = 62,
        verified_score      = 81,
        violations_closed   = [
            {'rule':'img-alt-missing','category':'Image Alt Text','severity':'critical','wcag':'1.1.1','closed_date':'2026-05-20'},
            {'rule':'label-missing','category':'Form Labels','severity':'critical','wcag':'1.3.1','closed_date':'2026-05-18'},
            {'rule':'focus-visible-missing','category':'Keyboard Navigation','severity':'serious','wcag':'2.4.7','closed_date':'2026-05-22'},
        ],
        violations_still_open = [
            {'rule':'heading-skipped','category':'Heading Structure','severity':'moderate','wcag':'1.3.1','days_open':30},
        ],
        organization = {'name': 'Orlando Health, Inc.', 'address': '1414 Kuhl Avenue, Orlando FL 32806'},
    )
    out = '/mnt/user-data/outputs/IDR-HHS-VerificationCertificate-SAMPLE.pdf'
    with open(out,'wb') as f: f.write(pdf)
    print(f'Done — {len(pdf):,} bytes → {out}')
