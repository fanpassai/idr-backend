"""
IDR Shield — hhs_emailer.py
HHS Healthcare Email Sequence

Sender structure:
  Official records / audit delivery  -> Institute of Digital Remediation <hello@idrshield.com>
  Activation confirmation            -> Institute of Digital Remediation <hello@idrshield.com>
  Weekly monitoring reports          -> IDR Compliance Team <hello@idrshield.com>
  Payment notification (internal)    -> IDR Shield <hello@idrshield.com>

TERMINOLOGY SWEEP APPLIED:
  - "audit" -> "Good Faith Effort Record" in all client-facing copy
  - "audit record" -> "compliance record"
  - "audit date" -> "record date"
  - "auditor" -> "accessibility reviewer"
  - Verification Certificate introduced as next step in Day 2 email
"""

import os
import base64
import threading
from datetime import datetime, timezone, timedelta
from receipt.hhs_pdf_generator import generate_hhs_pdf

SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
FROM_EMAIL       = 'hello@idrshield.com'

FROM_INSTITUTION = 'Institute of Digital Remediation'
FROM_COMPLIANCE  = 'IDR Compliance Team'
FROM_SUPPORT     = 'IDR Support'
FROM_ALERTS      = 'IDR Shield'

STRIPE_CONT_LINK = os.environ.get('STRIPE_CONT_LINK', 'https://buy.stripe.com/fZu7sK3MTeMI7YJ5hG2sM00')
VERIFY_BASE      = 'https://idrshield.com/hhs-verify'
DELIVERY_CONSOLE = 'https://idrshield.com/hhs-audit-delivery'

DELIVERY_DELAY_HOURS = 8


def _send(to_email, subject, html, text='', attachments=None, from_name=None):
    sender_name = from_name or FROM_INSTITUTION
    if not SENDGRID_API_KEY:
        print('[HHS_EMAIL] No SENDGRID_API_KEY — skipping: ' + subject)
        return False
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
        message = Mail(
            from_email=(FROM_EMAIL, sender_name),
            to_emails=to_email,
            subject=subject,
            html_content=html,
            plain_text_content=text or _strip_html(html)
        )
        if attachments:
            for att in attachments:
                a = Attachment()
                a.file_content = FileContent(att['content'])
                a.file_name    = FileName(att['filename'])
                a.file_type    = FileType(att['type'])
                a.disposition  = Disposition(att.get('disposition', 'attachment'))
                message.add_attachment(a)
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        r  = sg.client.mail.send.post(request_body=message.get())
        print('[HHS_EMAIL] Sent "' + subject + '" to ' + to_email + ' via ' + sender_name + ' — ' + str(r.status_code))
        return True
    except Exception as e:
        print('[HHS_EMAIL] SendGrid error: ' + str(e))
        return False


def _strip_html(html):
    import re
    return re.sub(r'<[^>]+>', '', html).strip()


def _hdr(eyebrow_line=''):
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '</head>'
        '<body style="margin:0;padding:0;background-color:#F2EFE9;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#F2EFE9;">'
        '<tr><td align="center" style="padding:32px 16px 0;">'
        '<table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;">'
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;height:4px;font-size:0;">&nbsp;</td></tr>'
        '<tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:28px 40px 22px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td style="vertical-align:middle;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:rgba(201,168,76,0.6);">Institute of Digital Remediation</div>'
        '<div style="font-family:Georgia,serif;font-size:10px;font-style:italic;color:rgba(201,168,76,0.35);margin-top:2px;">HHS Compliance Registry &middot; 2026</div>'
        '</td>'
        '<td align="right" style="vertical-align:middle;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;color:rgba(201,168,76,0.35);letter-spacing:0.1em;text-transform:uppercase;">'
        + eyebrow_line +
        '</div></td>'
        '</tr></table></td></tr>'
        '<tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:0 40px;">'
        '<div style="height:1px;background:rgba(201,168,76,0.15);"></div>'
        '</td></tr>'
    )


def _ftr(domain='', registry_id=''):
    verify_url = (VERIFY_BASE + '/' + domain) if domain else 'https://idrshield.com/healthcare'
    rid_line = ('<div style="margin-top:7px;font-family:Courier New,Courier,monospace;font-size:9px;color:#BBBBBB;">REGISTRY ID &middot; ' + registry_id + '</div>') if registry_id else ''
    return (
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:22px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#AAAAAA;margin-bottom:7px;">Your Public Verification Record</div>'
        '<a href="' + verify_url + '" style="font-family:Courier New,Courier,monospace;font-size:11px;color:#8A6F2E;text-decoration:none;">' + verify_url + '</a>'
        + rid_line +
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:18px 40px;border-top:1px solid #E8E4DC;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;color:#CCCCCC;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:5px;">Institute of Digital Remediation &nbsp;&middot;&nbsp; idrshield.com &nbsp;&middot;&nbsp; IDR-BRAND-2026-01</div>'
        '<div style="font-family:Georgia,serif;font-size:10.5px;font-style:italic;color:#CCCCCC;line-height:1.7;">Not a law firm. This is a compliance documentation system.</div>'
        '<div style="margin-top:9px;font-family:Arial,sans-serif;font-size:8px;color:#DDDDDD;">'
        '<a href="https://idrshield.com/privacy" style="color:#CCCCCC;text-decoration:none;">Privacy Policy</a>'
        ' &nbsp;&middot;&nbsp; <a href="https://idrshield.com/terms" style="color:#CCCCCC;text-decoration:none;">Terms of Service</a>'
        ' &nbsp;&middot;&nbsp; <a href="mailto:hello@idrshield.com" style="color:#CCCCCC;text-decoration:none;">hello@idrshield.com</a>'
        '</div></td></tr>'
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;height:4px;font-size:0;">&nbsp;</td></tr>'
        '</table></td></tr></table></body></html>'
    )


def _section_divider():
    return '<tr><td bgcolor="#F2EFE9" height="2" style="background-color:#F2EFE9;height:2px;font-size:0;">&nbsp;</td></tr>'


def _feature_row(title, body):
    return (
        '<tr><td style="padding:12px 0;border-bottom:1px solid #F0EDE8;vertical-align:top;">'
        '<table cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td width="22" style="vertical-align:top;padding-top:2px;">'
        '<div style="width:14px;height:14px;border:1px solid #C9A84C;border-radius:50%;">'
        '<span style="font-family:Arial,sans-serif;font-size:8px;color:#C9A84C;">&#x2713;</span>'
        '</div></td>'
        '<td style="padding-left:10px;vertical-align:top;">'
        '<div style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;color:#333333;margin-bottom:3px;">' + title + '</div>'
        '<div style="font-family:Georgia,serif;font-size:12.5px;color:#888888;font-style:italic;line-height:1.6;">' + body + '</div>'
        '</td></tr></table>'
        '</td></tr>'
    )


def _tl_row(when, what, active=False):
    dot_color  = '#C9A84C' if active else '#DDDDDD'
    when_color = '#C9A84C' if active else '#AAAAAA'
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:12px;"><tr>'
        '<td width="20" style="vertical-align:top;padding-top:3px;">'
        '<div style="width:8px;height:8px;border-radius:50%;background:' + dot_color + ';"></div>'
        '</td>'
        '<td style="padding-left:10px;vertical-align:top;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:' + when_color + ';margin-bottom:3px;">' + when + '</div>'
        '<div style="font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.55;">' + what + '</div>'
        '</td></tr></table>'
    )


def _receipt_row(key, val):
    return (
        '<tr>'
        '<td bgcolor="#FDFCF9" style="background-color:#FDFCF9;padding:10px 16px;border-bottom:1px solid #F0EDE8;">'
        '<span style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#AAAAAA;">' + key + '</span>'
        '</td>'
        '<td bgcolor="#FDFCF9" style="background-color:#FDFCF9;padding:10px 16px;border-bottom:1px solid #F0EDE8;text-align:right;">'
        '<span style="font-family:Courier New,Courier,monospace;font-size:11px;color:#555555;">' + val + '</span>'
        '</td></tr>'
    )


def _receipt_row_dark(key, val):
    return (
        '<tr><td style="padding:10px 0;border-bottom:1px solid rgba(240,232,216,0.06);">'
        '<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.14em;text-transform:uppercase;color:rgba(240,232,216,0.3);">' + key + '</span>'
        '<span style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.14em;color:#C9A84C;float:right;">' + val + '</span>'
        '</td></tr>'
    )


# ── EMAIL 1 — ACTIVATION CONFIRMATION ────────────────────────────────────────

def send_hhs_activation_confirmation(email, domain, score=None, crits=None, total=None, receipt_id=None, registry_id=None, timestamp_utc=''):
    try:
        dt = datetime.strptime(timestamp_utc[:19], '%Y-%m-%dT%H:%M:%S') if timestamp_utc else datetime.now(timezone.utc)
        display_date = dt.strftime('%B %d, %Y at %H:%M UTC')
    except Exception:
        display_date = datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')

    verify_url    = VERIFY_BASE + '/' + domain
    cont_link     = STRIPE_CONT_LINK + '?client_reference_id=' + domain
    rid_display   = registry_id or ('IDR-HHS-' + domain.upper().replace('.', '-'))
    receipt_short = ((receipt_id[:24] + '&hellip;') if receipt_id and len(receipt_id) > 24 else receipt_id) if receipt_id else 'Pending — delivered within 48 hrs'

    subject = 'Your HHS Good Faith Effort Record is being prepared — ' + domain

    html = (
        _hdr('HHS Good Faith Effort Record') +
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 28px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Record Initiation Confirmed</div>'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:700;color:#0A0E1A;margin-bottom:6px;line-height:1.25;">Your compliance record is now being prepared.</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;font-style:italic;color:#AAAAAA;line-height:1.7;margin-bottom:0;">'
        'Your HHS Accessibility Good Faith Effort Record for <strong style="color:#333333;">' + domain + '</strong> has been initiated. '
        'A CPACC-certified accessibility reviewer will complete your compliance record within 48 hours. '
        'This email confirms what has been established and what arrives next.'
        '</div>'
        '</td></tr>'
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#AAAAAA;margin-bottom:16px;">What Your Record Includes</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        + _feature_row('SHA-256 Timestamped Scan Receipt', 'A cryptographically sealed, tamper-proof record of your accessibility posture at the time of engagement. Immutable by design.')
        + _feature_row('IDR Registry Entry — Manual Verified', 'Your organization is now enrolled in the IDR HHS Compliance Registry. Public verification record: ' + verify_url)
        + _feature_row('CPACC Human Validation', 'A Certified Professional in Accessibility Core Competencies will complete all five manual checks: keyboard navigation, screen reader pass, form completion, PDF accessibility, and visual stress testing.')
        + _feature_row('Defense Positioning Summary', 'A formal statement confirming your organization has initiated active accessibility monitoring and remediation — ready for legal use under Section 504 and Section 1557.')
        + _feature_row('Remediation Roadmap', 'Prioritized fix guidance with developer-ready code examples for every documented violation.')
        + '</table>'
        '</td></tr>'
        '<tr><td bgcolor="#FAFAF8" style="background-color:#FAFAF8;padding:28px 40px;border-top:1px solid #F0EDE8;border-bottom:1px solid #F0EDE8;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#AAAAAA;margin-bottom:18px;">What Happens Next</div>'
        + _tl_row('Now', 'This email is your record of initiation. Save it.', True)
        + _tl_row('Within 5 minutes', 'Your registry record is initialized. Status: Pending Verification.', False)
        + _tl_row('Within 24 hours', 'CPACC human validation completed. Findings documented and annotated.', False)
        + _tl_row('Within 48 hours', 'Your complete Good Faith Effort Record delivered to this email. Registry status updates to Manual Verified.', False)
        + _tl_row('Day 30', 'IDR runs your Verification Re-Scan. Closed violations receive a Verification Certificate.', False)
        + '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#AAAAAA;margin-bottom:14px;">Your Record Details</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;">'
        + _receipt_row('Domain', domain)
        + _receipt_row('Registry ID', rid_display)
        + _receipt_row('Receipt ID', receipt_short)
        + _receipt_row('Record Initiated', display_date)
        + _receipt_row('Protocol Standard', 'WCAG 2.1 AA &middot; Section 504 / 1557')
        + _receipt_row('Status', 'Pending CPACC Validation &rarr; Manual Verified within 48 hrs')
        + _receipt_row('Public Verify URL', verify_url)
        + '</table></td></tr>'
        + _section_divider() +
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px 36px;border-top:1px solid #F0EDE8;">'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#555555;line-height:1.8;">'
        'Your record is now in motion. We will have it complete and in your hands within 48 hours.<br><br>'
        'If you have any questions before then, reply directly to this email.<br><br>'
        'Institute of Digital Remediation<br>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">idrshield.com &nbsp;&middot;&nbsp; hello@idrshield.com</span>'
        '</div>'
        '</td></tr>'
        + _ftr(domain, rid_display)
    )

    return _send(email, subject, html, from_name=FROM_INSTITUTION)


# ── EMAIL 2 — DAY 2 — Record verified + verification certificate intro ─────────

def send_hhs_day2_monitoring(email, domain, score=None, registry_id=None):
    verify_url  = VERIFY_BASE + '/' + domain
    cont_link   = STRIPE_CONT_LINK + '?client_reference_id=' + domain
    registry_id = registry_id or ('IDR-HHS-' + domain.upper().replace('.', '-'))
    subject     = domain + ' — your Good Faith Effort Record is verified. Here is what comes next.'

    html = (
        _hdr('HHS Compliance Record') +
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 24px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Your Record — Day Two</div>'
        '<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#0A0E1A;margin-bottom:8px;line-height:1.3;">'
        'Your Good Faith Effort Record for ' + domain + ' is complete.<br>'
        '<span style="color:#C9A84C;font-style:italic;">Status: Manual Verified.</span>'
        '</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#888888;font-style:italic;line-height:1.7;">'
        'You now have the first documented proof your organization has taken action under HHS accessibility requirements. '
        'That is significant. Here is exactly what happens next — and what this record cannot do alone.'
        '</div>'
        '</td></tr>'
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;border-top:1px solid #F0EDE8;border-bottom:1px solid #F0EDE8;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#AAAAAA;margin-bottom:18px;">Your Compliance Path — Three Steps</div>'
        + _tl_row('Step 1 — Complete', 'Good Faith Effort Record issued. Baseline established. Registry entry: Manual Verified.', True)
        + _tl_row('Step 2 — Day 30', 'IDR runs your Verification Re-Scan. Every documented violation independently re-tested. Closed violations receive a Remediation Verification Certificate — a second formal document proving your organization not only identified its issues but corrected them. $297.', False)
        + _tl_row('Step 3 — Ongoing', 'Active Compliance Monitoring keeps your record current — weekly rescans, real-time registry updates, a continuously dated evidence log. $49/month.', False)
        + '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#AAAAAA;line-height:1.6;border-left:2px solid #E8E4DC;padding-left:14px;margin-bottom:16px;">'
        '&ldquo;A static record documents a single date. A verified remediation record proves action was taken. A continuously dated record is far harder to dispute.&rdquo;'
        '</div>'
        '<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:16px;"><tr>'
        '<td bgcolor="#C9A84C" style="background-color:#C9A84C;">'
        '<a href="' + cont_link + '" style="display:block;padding:15px 36px;font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#0A0E1A;text-decoration:none;">Add Ongoing Monitoring — $49/month</a>'
        '</td></tr></table>'
        '<div style="font-family:Arial,sans-serif;font-size:10px;color:#CCCCCC;">Your public record: <a href="' + verify_url + '" style="color:#8A6F2E;">' + verify_url + '</a></div>'
        '</td></tr>'
        + _ftr(domain, registry_id)
    )

    return _send(email, subject, html, from_name=FROM_COMPLIANCE)


# ── EMAIL 3 — DAY 5 RECORD SNAPSHOT ──────────────────────────────────────────

def send_hhs_day5_snapshot(email, domain, score=None, crits=None, registry_id=None):
    verify_url  = VERIFY_BASE + '/' + domain
    cont_link   = STRIPE_CONT_LINK + '?client_reference_id=' + domain
    registry_id = registry_id or ('IDR-HHS-' + domain.upper().replace('.', '-'))
    subject     = domain + ' — your compliance record, 5 days in'

    html = (
        _hdr('HHS Compliance Record') +
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 24px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Five Days In</div>'
        '<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#0A0E1A;margin-bottom:8px;line-height:1.3;">'
        'Here is what your public compliance record currently shows.'
        '</div>'
        '</td></tr>'
        '<tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:rgba(201,168,76,0.5);margin-bottom:16px;">IDR HHS Registry — Current Status</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        + _receipt_row_dark('Domain', domain)
        + _receipt_row_dark('Registry Status', 'MANUAL VERIFIED')
        + _receipt_row_dark('Remediation Verified', 'NOT YET — Verification Re-Scan Pending')
        + _receipt_row_dark('Monitoring Status', 'NOT ACTIVE')
        + _receipt_row_dark('Next Rescan Scheduled', 'NONE — Monitoring Not Active')
        + '</table>'
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#555555;line-height:1.75;margin-bottom:18px;">'
        'Your Good Faith Effort Record is verified and on file. The fields above are visible to anyone who checks your verification page — including enforcement auditors and legal teams. '
        'The Remediation Verified and Monitoring Active fields are blank. Those are the next two steps.'
        '</div>'
        '<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:12px;"><tr>'
        '<td bgcolor="#C9A84C" style="background-color:#C9A84C;">'
        '<a href="' + cont_link + '" style="display:block;padding:15px 36px;font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#0A0E1A;text-decoration:none;">Add Ongoing Monitoring — $49/month</a>'
        '</td></tr></table>'
        '</td></tr>'
        + _ftr(domain, registry_id)
    )

    return _send(email, subject, html, from_name=FROM_COMPLIANCE)


# ── EMAIL 4 — DAY 9 FINAL WINDOW ─────────────────────────────────────────────

def send_hhs_day9_final(email, domain, score=None, registry_id=None):
    verify_url  = VERIFY_BASE + '/' + domain
    cont_link   = STRIPE_CONT_LINK + '?client_reference_id=' + domain
    registry_id = registry_id or ('IDR-HHS-' + domain.upper().replace('.', '-'))
    subject     = 'Final notice — ' + domain + ' · HHS enforcement window closes May 11'

    html = (
        _hdr('HHS Enforcement Window') +
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 24px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#E63946;margin-bottom:10px;">Enforcement Window Closing</div>'
        '<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#0A0E1A;margin-bottom:8px;line-height:1.3;">'
        'May 11 is the deadline. Your Good Faith Effort Record exists. Your remediation record does not.'
        '</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#888888;font-style:italic;line-height:1.7;">'
        'Your verified compliance record for ' + domain + ' is on file. After May 11, organizations with continuous monitoring records and verified remediation will be in a fundamentally different regulatory position.'
        '</div>'
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:32px 40px;">'
        '<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:12px;"><tr>'
        '<td bgcolor="#C9A84C" style="background-color:#C9A84C;">'
        '<a href="' + cont_link + '" style="display:block;padding:17px 40px;font-family:Arial,sans-serif;font-size:10.5px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#0A0E1A;text-decoration:none;">Activate Monitoring — $49/month</a>'
        '</td></tr></table>'
        '<div style="font-family:Arial,sans-serif;font-size:10px;color:#CCCCCC;margin-bottom:20px;">Weekly rescans &middot; Monitoring Active status &middot; Living evidence log</div>'
        '</td></tr>'
        + _ftr(domain, registry_id)
    )

    return _send(email, subject, html, from_name=FROM_COMPLIANCE)


# ── MONITORING WELCOME ────────────────────────────────────────────────────────

def send_hhs_monitoring_welcome(email, domain, registry_id=None):
    verify_url  = VERIFY_BASE + '/' + domain
    registry_id = registry_id or ('IDR-HHS-' + domain.upper().replace('.', '-'))
    subject     = domain + ' — Monitoring Active. Your compliance record is now live.'

    html = (
        _hdr('Monitoring Active') +
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#52B788;margin-bottom:10px;">Monitoring Active</div>'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:700;color:#0A0E1A;margin-bottom:8px;line-height:1.25;">Your compliance record is now a living document.</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#888888;font-style:italic;line-height:1.7;margin-bottom:24px;">'
        + domain + ' has been upgraded to Monitoring Active status in the IDR HHS Compliance Registry. '
        'Weekly automated rescans are now scheduled. Your evidence log is building — every week that passes adds another timestamped entry to your compliance record.'
        '</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;">'
        + _receipt_row('Domain', domain)
        + _receipt_row('Registry Status', 'MONITORING ACTIVE')
        + _receipt_row('Registry ID', registry_id)
        + _receipt_row('Scan Frequency', 'Weekly — Automated WCAG 2.1 AA Protocol')
        + _receipt_row('Evidence Log', 'Building — every rescan adds a timestamped entry')
        + _receipt_row('Public Record', verify_url)
        + '</table>'
        '</td></tr>'
        + _ftr(domain, registry_id)
    )

    return _send(email, subject, html, from_name=FROM_COMPLIANCE)


# ── ACCESS CODE EMAIL ─────────────────────────────────────────────────────────

def _send_access_code_email(email, domain, password, registry_id):
    subject = 'Your IDR Document Access Code — ' + domain

    html = (
        _hdr('Document Access Code') +
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 28px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">HHS Good Faith Effort Record</div>'
        '<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#0A0E1A;margin-bottom:8px;line-height:1.25;">Your compliance record will arrive within 48 hours.</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;font-style:italic;color:#AAAAAA;line-height:1.7;margin-bottom:24px;">'
        'When your HHS Accessibility Good Faith Effort Record for <strong style="color:#333333;">' + domain + '</strong> arrives, '
        'it will be secured with the access code below. Keep this email for your records.'
        '</div>'
        '</td></tr>'
        '<tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:32px 40px;text-align:center;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.32em;text-transform:uppercase;color:rgba(201,168,76,0.55);margin-bottom:14px;">Document Access Code</div>'
        '<div style="font-family:Courier New,Courier,monospace;font-size:32px;font-weight:700;color:#C9A84C;letter-spacing:0.18em;">' + password + '</div>'
        '<div style="font-family:Arial,sans-serif;font-size:9px;color:rgba(201,168,76,0.35);margin-top:10px;letter-spacing:0.08em;">'
        'Enter this code when prompted to open your compliance record PDF'
        '</div>'
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:24px 40px 32px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#AAAAAA;margin-bottom:10px;">What This Code Is</div>'
        '<div style="font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.75;">'
        'Your access code is cryptographically derived from your compliance record. '
        'It is unique to your organization and mathematically linked to the document contents. '
        'If the document is altered in any way, this code will no longer work — '
        'an additional layer of tamper-evidence built into your official record.'
        '</div>'
        '</td></tr>'
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:18px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;color:#AAAAAA;line-height:1.6;">'
        '<strong>Registry ID:</strong> ' + registry_id + '<br>'
        '<strong>Domain:</strong> ' + domain + '<br>'
        '<strong>Keep this email.</strong> If you lose your access code, contact hello@idrshield.com.'
        '</div>'
        '</td></tr>'
        + _ftr(domain, registry_id)
    )

    return _send(email, subject, html, from_name=FROM_INSTITUTION)


# ── AUDIT DELIVERY ────────────────────────────────────────────────────────────

def send_hhs_audit_delivery(email, domain, score, crits, total, receipt_id,
                             registry_id, timestamp_utc='', organization=None,
                             scan_data=None):
    """
    Generates the PDF immediately. Sends access code email immediately.
    Schedules PDF delivery email for DELIVERY_DELAY_HOURS later.
    Password = first 8 chars of SHA-256 doc hash, uppercased.
    """
    try:
        dt = datetime.strptime(timestamp_utc[:19], '%Y-%m-%dT%H:%M:%S') if timestamp_utc else datetime.now(timezone.utc)
        display_date = dt.strftime('%B %d, %Y at %H:%M UTC')
    except Exception:
        display_date = datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')

    verify_url    = VERIFY_BASE + '/' + domain
    cont_link     = STRIPE_CONT_LINK + '?client_reference_id=' + domain
    rid_display   = registry_id or ('IDR-HHS-' + domain.upper().replace('.', '-'))
    receipt_short = ((receipt_id[:24] + '&hellip;') if receipt_id and len(receipt_id) > 24 else receipt_id) if receipt_id else '—'
    score_color   = '#27AE60' if score >= 80 else '#E9A030' if score >= 60 else '#E05252'
    crits_word    = 'violation' if crits == 1 else 'violations'

    pdf_bytes    = None
    doc_password = None
    try:
        org = organization or {'name': domain}
        if scan_data:
            scan = scan_data
        else:
            scan = {
                'domain': domain, 'url': 'https://' + domain, 'title': '',
                'overall_score': score,
                'overall_status': 'pass' if score >= 80 else 'warning' if score >= 60 else 'fail',
                'critical_count': crits, 'serious_count': 0, 'total_issues': total,
                'scan_duration_ms': 0, 'categories': [],
            }

        receipt_data = {
            'receipt_id':    receipt_id or '',
            'registry_id':   rid_display,
            'timestamp_utc': timestamp_utc or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'hash':          '',
            'activated_by':  email,
            'organization':  org,
            'scan':          scan,
        }

        raw_pdf = generate_hhs_pdf(receipt_data)
        print('[HHS_EMAIL] PDF generated — ' + str(len(raw_pdf)) + ' bytes for ' + domain)

        import hashlib, json as _json
        payload_str = _json.dumps({
            'receipt_id':  receipt_id or '',
            'registry_id': rid_display,
            'domain':      domain,
        }, sort_keys=True)
        doc_hash     = hashlib.sha256(payload_str.encode()).hexdigest()
        doc_password = doc_hash[:8].upper()

        from pypdf import PdfReader as _PdfReader, PdfWriter as _PdfWriter
        import io as _io
        reader = _PdfReader(_io.BytesIO(raw_pdf))
        writer = _PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(user_password=doc_password, owner_password=doc_password)
        enc_buf = _io.BytesIO()
        writer.write(enc_buf)
        pdf_bytes = enc_buf.getvalue()
        print('[HHS_EMAIL] PDF encrypted — password: ' + doc_password)

    except Exception as e:
        print('[HHS_EMAIL] PDF generation/encryption failed: ' + str(e))

    if doc_password:
        _send_access_code_email(email, domain, doc_password, rid_display)

    def _deliver():
        _send_audit_delivery_email(
            email=email, domain=domain, score=score, crits=crits, total=total,
            receipt_id=receipt_id, registry_id=rid_display,
            display_date=display_date, verify_url=verify_url,
            cont_link=cont_link, receipt_short=receipt_short,
            score_color=score_color, crits_word=crits_word,
            pdf_bytes=pdf_bytes, timestamp_utc=timestamp_utc
        )

    delay_seconds = DELIVERY_DELAY_HOURS * 3600
    t = threading.Timer(delay_seconds, _deliver)
    t.daemon = True
    t.start()

    scheduled_time = (datetime.now(timezone.utc) + timedelta(hours=DELIVERY_DELAY_HOURS)).strftime('%B %d, %Y at %H:%M UTC')
    print('[HHS_EMAIL] Delivery to ' + email + ' scheduled for ' + str(DELIVERY_DELAY_HOURS) + ' hours — approx ' + scheduled_time)
    return True


def _send_audit_delivery_email(email, domain, score, crits, total, receipt_id,
                                registry_id, display_date, verify_url, cont_link,
                                receipt_short, score_color, crits_word,
                                pdf_bytes, timestamp_utc=''):
    subject = 'Your HHS Good Faith Effort Record — ' + domain + ' · Complete'

    html = (
        _hdr('HHS Good Faith Effort Record · Delivered') +
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 28px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Record Complete — Delivered</div>'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:700;color:#0A0E1A;margin-bottom:8px;line-height:1.25;">Your HHS Good Faith Effort Record is complete.</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;font-style:italic;color:#AAAAAA;line-height:1.7;">'
        'Your full compliance record is attached. Open it using the access code sent in your previous email.'
        '</div>'
        '</td></tr>'
        '<tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:18px 40px;">'
        '<table cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td width="28" style="vertical-align:middle;padding-right:12px;"><div style="font-size:20px;">&#128196;</div></td>'
        '<td style="vertical-align:middle;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:rgba(201,168,76,0.6);margin-bottom:3px;">Attached to this email</div>'
        '<div style="font-family:Courier New,Courier,monospace;font-size:11px;color:#C9A84C;">IDR-HHS-GoodFaithRecord-' + domain + '-' + (receipt_id or '')[:8] + '.pdf</div>'
        '<div style="font-family:Arial,sans-serif;font-size:9px;color:rgba(255,255,255,0.3);margin-top:2px;">Password-protected &middot; Use the access code from your previous email</div>'
        '</td></tr></table>'
        '</td></tr>'
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td align="center" style="padding-right:24px;border-right:1px solid #E8E4DC;width:130px;vertical-align:middle;">'
        '<div style="font-family:Georgia,serif;font-size:60px;font-weight:700;color:' + score_color + ';line-height:1;">' + str(score) + '</div>'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.2em;color:#AAAAAA;text-transform:uppercase;margin-top:4px;">Score / 100</div>'
        '</td>'
        '<td style="padding-left:28px;vertical-align:middle;">'
        '<div style="font-family:Georgia,serif;font-size:36px;font-weight:700;color:#E05252;line-height:1;">' + str(crits) + '</div>'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.18em;color:#AAAAAA;text-transform:uppercase;margin-top:4px;margin-bottom:14px;">Critical ' + crits_word + '</div>'
        '<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#888888;line-height:1.6;">'
        + str(total) + ' total issues documented in your sealed compliance record.'
        '</div>'
        '</td></tr></table>'
        '</td></tr>'
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#AAAAAA;margin-bottom:14px;">Your Sealed Compliance Record</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;">'
        + _receipt_row('Domain', domain)
        + _receipt_row('Registry ID', registry_id)
        + _receipt_row('Receipt ID', receipt_short)
        + _receipt_row('Record Date', display_date)
        + _receipt_row('Accessibility Score', str(score) + '/100')
        + _receipt_row('Critical Violations', str(crits))
        + _receipt_row('Total Issues Documented', str(total))
        + _receipt_row('Protocol Standard', 'WCAG 2.1 AA &middot; Section 504 / 1557')
        + _receipt_row('Verification Type', 'Manual Verified — CPACC Human Reviewed')
        + _receipt_row('Public Verify URL', verify_url)
        + '</table></td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;border-left:3px solid #C9A84C;"><tr>'
        '<td bgcolor="#FDFCF9" style="background-color:#FDFCF9;padding:22px 26px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Your Next Step — Day 30 Verification</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#555555;line-height:1.75;margin-bottom:14px;">'
        'At Day 30 from your record date, IDR will run an external Verification Re-Scan of every documented violation. '
        'Closed violations receive a Remediation Verification Certificate — a second formal document proving your organization acted on its findings. '
        'That certificate is what transforms a Good Faith Effort Record into a complete compliance defense.'
        '</div>'
        '<a href="' + cont_link + '" style="display:inline-block;padding:12px 26px;background-color:transparent;border:1px solid #C9A84C;font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#8A6F2E;text-decoration:none;">Add Monitoring — $49/month</a>'
        '</td></tr></table>'
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:24px 40px 36px;border-top:1px solid #F0EDE8;">'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#555555;line-height:1.8;">'
        'Your full compliance record is attached. If you have any questions about the findings, reply directly to this email.<br><br>'
        'Institute of Digital Remediation<br>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">idrshield.com &nbsp;&middot;&nbsp; hello@idrshield.com</span>'
        '</div>'
        '</td></tr>'
        + _ftr(domain, registry_id)
    )

    pdf_attachment = None
    if pdf_bytes:
        pdf_attachment = {
            'content':     base64.b64encode(pdf_bytes).decode(),
            'type':        'application/pdf',
            'filename':    'IDR-HHS-GoodFaithRecord-' + domain + '-' + (receipt_id or '')[:8] + '.pdf',
            'disposition': 'attachment',
        }

    attachments = [pdf_attachment] if pdf_attachment else None
    return _send(email, subject, html, attachments=attachments, from_name=FROM_INSTITUTION)


# ── PAYMENT NOTIFICATION ──────────────────────────────────────────────────────

def send_payment_notification(domain, email, amount, product_type):
    NOTIFY_EMAIL  = 'idrshieldhq@gmail.com'
    verify_url    = VERIFY_BASE + '/' + domain
    product_label = '$497 HHS Good Faith Effort Record' if product_type == 'audit' else '$49/month Monitoring'
    console_url   = DELIVERY_CONSOLE + '?domain=' + domain + '&email=' + email
    subject       = '[NEW PAYMENT] ' + domain + ' — ' + product_label

    html = (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
        '<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:30px 16px;">'
        '<div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">'
        '<div style="background:#0A0E1A;padding:22px 28px;border-bottom:3px solid #C9A84C;">'
        '<p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:rgba(201,168,76,0.6);margin:0 0 4px;">IDR Shield — Payment Alert</p>'
        '<h1 style="font-size:18px;font-weight:normal;color:#FAF7F2;margin:0;">' + product_label + ' Received</h1>'
        '</div>'
        '<div style="padding:24px 28px;">'
        '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        '<tr><td style="padding:7px 0;color:#999;width:120px;">Domain</td><td style="padding:7px 0;color:#333;font-weight:700;">' + domain + '</td></tr>'
        '<tr><td style="padding:7px 0;color:#999;">Customer</td><td style="padding:7px 0;color:#333;">' + email + '</td></tr>'
        '<tr><td style="padding:7px 0;color:#999;">Product</td><td style="padding:7px 0;color:#C9A84C;font-weight:700;">' + product_label + '</td></tr>'
        '<tr><td style="padding:7px 0;color:#999;">Verify URL</td><td style="padding:7px 0;"><a href="' + verify_url + '" style="color:#8A6F2E;">' + verify_url + '</a></td></tr>'
        '</table>'
        '</div>'
        + (
            '<div style="background:#FDF8F0;border-top:1px solid #F0E8D8;border-bottom:1px solid #F0E8D8;padding:18px 28px;">'
            '<p style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;color:#C9A84C;margin:0 0 6px;letter-spacing:0.1em;text-transform:uppercase;">Action Required — 48 Hour Delivery Window</p>'
            '<p style="font-family:Georgia,serif;font-size:13px;color:#555;line-height:1.6;margin:0 0 14px;">'
            'Prepare the Good Faith Effort Record for <strong>' + domain + '</strong>.<br>'
            'Client email pre-filled: <strong>' + email + '</strong>'
            '</p>'
            '<a href="' + console_url + '" '
            'style="display:inline-block;padding:13px 26px;background:#C9A84C;'
            'font-family:Arial,sans-serif;font-size:10px;font-weight:700;'
            'letter-spacing:0.16em;text-transform:uppercase;color:#0A0E1A;text-decoration:none;">'
            'Open Delivery Console &rarr; ' + domain +
            '</a>'
            '<p style="font-family:Arial,sans-serif;font-size:9px;color:#AAAAAA;margin:12px 0 0;">'
            'Direct link: <a href="' + console_url + '" style="color:#8A6F2E;">' + console_url + '</a>'
            '</p>'
            '</div>'
            if product_type == 'audit' else
            '<div style="background:#F0FDF4;border-top:1px solid #D1FAE5;border-bottom:1px solid #D1FAE5;padding:18px 28px;">'
            '<p style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;color:#27AE60;margin:0 0 6px;letter-spacing:0.1em;text-transform:uppercase;">Monitoring Activated — No Action Required</p>'
            '<p style="font-family:Georgia,serif;font-size:13px;color:#555;line-height:1.6;margin:0;">Weekly rescans will begin automatically. Registry status upgraded to Monitoring Active.</p>'
            '</div>'
        ) +
        '<div style="padding:16px 28px;">'
        '<p style="font-family:Arial,sans-serif;font-size:10px;color:#CCCCCC;margin:0;">IDR Shield &middot; Automated payment alert</p>'
        '</div>'
        '</div>'
        '</body></html>'
    )

    return _send(NOTIFY_EMAIL, subject, html, from_name=FROM_ALERTS)
