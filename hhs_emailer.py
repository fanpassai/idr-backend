"""
IDR Shield — hhs_emailer.py
HHS Healthcare Email Sequence
"""

import os
import base64
from datetime import datetime, timezone, timedelta
from hhs_pdf_generator import generate_hhs_pdf

SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
FROM_EMAIL       = 'hello@idrshield.com'
FROM_NAME        = 'Hans-Peter Nkansah — Institute of Digital Remediation'
STRIPE_CONT_LINK = os.environ.get('STRIPE_CONT_LINK', 'https://buy.stripe.com/REPLACE_CONTINUITY_LINK')
VERIFY_BASE      = 'https://idrshield.com/hhs-verify'


def _send(to_email, subject, html, text='', attachments=None):
    if not SENDGRID_API_KEY:
        print(f'[HHS_EMAIL] No SENDGRID_API_KEY — skipping: {subject}')
        return False
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
        message = Mail(
            from_email=(FROM_EMAIL, FROM_NAME),
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
        print(f'[HHS_EMAIL] Sent "{subject}" to {to_email} — {r.status_code}')
        return True
    except Exception as e:
        print(f'[HHS_EMAIL] SendGrid error: {e}')
        return False


def _strip_html(html):
    import re
    return re.sub(r'<[^>]+>', '', html).strip()


def _hdr(eyebrow_line=''):
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="x-apple-disable-message-reformatting">'
        '</head>'
        '<body style="margin:0;padding:0;background-color:#F2EFE9;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#F2EFE9;">'
        '<tr><td align="center" style="padding:32px 16px 0;">'
        '<table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;">'
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;height:4px;font-size:0;">&nbsp;</td></tr>'
        '<tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:28px 40px 22px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td style="vertical-align:middle;">'
        '<table cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td style="vertical-align:middle;">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 36 36">'
        '<circle cx="18" cy="18" r="17" fill="#0A0E1A"/>'
        '<circle cx="18" cy="18" r="16.5" fill="none" stroke="#C9A84C" stroke-width="1.2" opacity="0.9"/>'
        '<circle cx="18" cy="18" r="12" fill="none" stroke="#C9A84C" stroke-width="0.5" opacity="0.3"/>'
        '<text x="18" y="22" font-family="Georgia,serif" font-size="9.5" font-weight="700" fill="#C9A84C" text-anchor="middle">IDR</text>'
        '</svg></td>'
        '<td width="10">&nbsp;</td>'
        '<td style="vertical-align:middle;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:rgba(201,168,76,0.6);">Institute of Digital Remediation</div>'
        '<div style="font-family:Georgia,serif;font-size:10px;font-style:italic;color:rgba(201,168,76,0.35);margin-top:2px;">HHS Compliance Registry · 2026</div>'
        '</td></tr></table></td>'
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
    verify_url = f'{VERIFY_BASE}/{domain}' if domain else 'https://idrshield.com/healthcare'
    return (
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:22px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#AAAAAA;margin-bottom:7px;">Your Public Verification Record</div>'
        '<a href="' + verify_url + '" style="font-family:\'Courier New\',Courier,monospace;font-size:11px;color:#8A6F2E;text-decoration:none;">' + verify_url + '</a>'
        + (f'<div style="margin-top:7px;font-family:\'Courier New\',Courier,monospace;font-size:9px;color:#BBBBBB;">REGISTRY ID · {registry_id}</div>' if registry_id else '') +
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:18px 40px;border-top:1px solid #E8E4DC;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td>'
        '<div style="font-family:Arial,sans-serif;font-size:8px;color:#CCCCCC;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:5px;">Institute of Digital Remediation &nbsp;·&nbsp; idrshield.com &nbsp;·&nbsp; IDR-BRAND-2026-01</div>'
        '<div style="font-family:Georgia,serif;font-size:10.5px;font-style:italic;color:#CCCCCC;line-height:1.7;">Not a law firm. This is a compliance documentation system. This record does not constitute legal advice.</div>'
        '<div style="margin-top:9px;font-family:Arial,sans-serif;font-size:8px;color:#DDDDDD;">'
        '<a href="https://idrshield.com/privacy" style="color:#CCCCCC;text-decoration:none;">Privacy Policy</a>'
        ' &nbsp;·&nbsp; <a href="https://idrshield.com/terms" style="color:#CCCCCC;text-decoration:none;">Terms of Service</a>'
        ' &nbsp;·&nbsp; <a href="mailto:hello@idrshield.com" style="color:#CCCCCC;text-decoration:none;">hello@idrshield.com</a>'
        '</div></td>'
        '<td width="40" align="right" style="vertical-align:middle;">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">'
        '<circle cx="14" cy="14" r="13" fill="none" stroke="#E8E4DC" stroke-width="1"/>'
        '<text x="14" y="18" font-family="Georgia,serif" font-size="7" font-weight="700" fill="#DDDDDD" text-anchor="middle">IDR</text>'
        '</svg></td></tr></table></td></tr>'
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;height:4px;font-size:0;">&nbsp;</td></tr>'
        '</table></td></tr></table></body></html>'
    )


def _section_divider():
    return '<tr><td bgcolor="#F2EFE9" height="2" style="background-color:#F2EFE9;height:2px;font-size:0;">&nbsp;</td></tr>'


# ── EMAIL 1 — ACTIVATION CONFIRMATION ────────────────────────────────────────

def send_hhs_activation_confirmation(email, domain, score=None, crits=None, total=None, receipt_id=None, registry_id=None, timestamp_utc=''):
    """
    Fires immediately on $497 payment.
    All scan-related args are optional — webhook fires this before a scan exists.
    """
    try:
        dt = datetime.strptime(timestamp_utc[:19], '%Y-%m-%dT%H:%M:%S') if timestamp_utc else datetime.now(timezone.utc)
        display_date = dt.strftime('%B %d, %Y at %H:%M UTC')
    except Exception:
        display_date = datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')

    verify_url    = f'{VERIFY_BASE}/{domain}'
    cont_link     = f'{STRIPE_CONT_LINK}?client_reference_id={domain}'
    rid_display   = registry_id or f'IDR-HHS-{domain.upper().replace(".", "-")}'
    receipt_short = ((receipt_id[:24] + '&hellip;') if receipt_id and len(receipt_id) > 24 else receipt_id) if receipt_id else 'Pending — delivered within 48 hrs'

    subject = f'Your HHS Readiness Record is being created — {domain}'

    html = (
        _hdr('HHS Readiness Audit') +

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 28px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Activation Confirmed</div>'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:700;color:#0A0E1A;margin-bottom:6px;line-height:1.25;">Your record is now being created.</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;font-style:italic;color:#AAAAAA;line-height:1.7;margin-bottom:0;">'
        f'Your HHS Readiness Audit for <strong style="color:#333333;">{domain}</strong> has been activated. '
        f'A human auditor will complete your compliance record within 48 hours. '
        f'This email confirms what has been established — and what arrives next.'
        '</div>'
        '</td></tr>'

        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#AAAAAA;margin-bottom:16px;">What You Have Activated</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        + _feature_row('SHA-256 Timestamped Scan Receipt', 'A cryptographically sealed, tamper-proof record of your accessibility posture at the time of audit. Immutable by design.')
        + _feature_row('IDR Registry Entry — Manual Verified', f'Your organization is now enrolled in the IDR HHS Compliance Registry. Public verification record: {verify_url}')
        + _feature_row('Human Validation Audit', 'A human auditor will complete all five manual checks within 24 hours: keyboard navigation, screen reader pass, form completion, PDF accessibility, and visual stress testing.')
        + _feature_row('Defense Positioning Summary', 'A formal statement confirming your organization has initiated active accessibility monitoring and remediation — ready for legal use under Section 504 and Section 1557.')
        + _feature_row('Screenshot Evidence Package', 'Annotated screenshots of all identified failure points with plain-language explanation of user impact for each critical finding.')
        + '</table>'
        '</td></tr>'

        '<tr><td bgcolor="#FAFAF8" style="background-color:#FAFAF8;padding:28px 40px;border-top:1px solid #F0EDE8;border-bottom:1px solid #F0EDE8;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#AAAAAA;margin-bottom:18px;">What Happens Next</div>'
        + _tl_row('Now', 'This confirmation email is your record of activation. Save it.', True)
        + _tl_row('Within 5 minutes', 'Your registry record is initialized. Status: Pending Verification.', False)
        + _tl_row('Within 24 hours', 'Human validation audit completed. Findings documented and annotated.', False)
        + _tl_row('Within 48 hours', 'Complete HHS Readiness Record delivered to this email. Registry status updates to Manual Verified.', False)
        + '</td></tr>'

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#AAAAAA;margin-bottom:14px;">Your Activation Record</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;">'
        + _receipt_row('Domain', domain)
        + _receipt_row('Registry ID', rid_display)
        + _receipt_row('Receipt ID', receipt_short)
        + _receipt_row('Activation Timestamp', display_date)
        + _receipt_row('Protocol Standard', 'WCAG 2.1 AA · Section 504 / 1557')
        + _receipt_row('Status', 'Pending Human Verification → Manual Verified within 48 hrs')
        + _receipt_row('Public Verify URL', verify_url)
        + '</table></td></tr>'

        + _section_divider() +

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;border-left:3px solid #C9A84C;"><tr>'
        '<td bgcolor="#FDFCF9" style="background-color:#FDFCF9;padding:20px 24px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#8A6F2E;margin-bottom:8px;">A Note on Your Record After Delivery</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#555555;line-height:1.75;margin-bottom:16px;">'
        'Your audit documents where you stood on the day it was conducted. HHS compliance is an ongoing obligation — not a one-time event. '
        'To maintain an active, continuously dated record, consider adding ongoing monitoring after your audit is delivered.'
        '</div>'
        '<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#AAAAAA;line-height:1.6;border-left:2px solid #E8E4DC;padding-left:14px;margin-bottom:16px;">'
        'A static audit can be challenged. A continuously dated record is far harder to dispute.'
        '</div>'
        '<a href="' + cont_link + '" style="display:inline-block;padding:11px 24px;background-color:transparent;border:1px solid #C9A84C;font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#8A6F2E;text-decoration:none;">Add Ongoing Monitoring — $49/month</a>'
        '</td></tr></table>'
        '</td></tr>'

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px 36px;border-top:1px solid #F0EDE8;">'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#555555;line-height:1.75;">'
        'Your record is now in motion. We will have it complete and in your hands within 48 hours.<br><br>'
        'If you have any questions before then, reply directly to this email.<br><br>'
        'Hans-Peter Nkansah<br>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">Founder, Institute of Digital Remediation</span><br>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">idrshield.com &nbsp;·&nbsp; hello@idrshield.com</span>'
        '</div>'
        '</td></tr>'

        + _ftr(domain, rid_display)
    )

    return _send(email, subject, html)


# ── EMAIL 2 — DAY 2 MONITORING UPSELL ────────────────────────────────────────

def send_hhs_day2_monitoring(email, domain, score=None, registry_id=None):
    verify_url = f'{VERIFY_BASE}/{domain}'
    cont_link  = f'{STRIPE_CONT_LINK}?client_reference_id={domain}'
    registry_id = registry_id or f'IDR-HHS-{domain.upper().replace(".", "-")}'

    subject = f'{domain} — your record is verified. Here is what it cannot do alone.'

    html = (
        _hdr('HHS Compliance Record') +

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 24px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Your Record — Day Two</div>'
        '<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#0A0E1A;margin-bottom:8px;line-height:1.3;">'
        f'Your audit for {domain} is complete.<br>'
        '<span style="color:#C9A84C;font-style:italic;">Your record is now Manual Verified.</span>'
        '</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#888888;font-style:italic;line-height:1.7;">'
        'What you have today is the first documented proof your organization has taken action under HHS accessibility requirements. '
        'That is significant. But there is something worth understanding about what it is — and what it is not.'
        '</div>'
        '</td></tr>'

        '<tr><td bgcolor="#FDF8F0" style="background-color:#FDF8F0;border-top:1px solid #F0E8D8;border-bottom:1px solid #F0E8D8;padding:24px 40px;border-left:4px solid #C9A84C;">'
        '<div style="font-family:Georgia,serif;font-size:17px;font-weight:700;color:#0A0E1A;line-height:1.45;margin-bottom:10px;">What your record documents today</div>'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#666666;line-height:1.75;">'
        f'Your scan score. Your critical violations at the time of audit. '
        f'The timestamp. The SHA-256 hash. The human verification. '
        f'All of it sealed, immutable, and publicly visible at <a href="{verify_url}" style="color:#8A6F2E;">{verify_url}</a>.'
        '</div>'
        '</td></tr>'

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Georgia,serif;font-size:17px;font-weight:700;color:#0A0E1A;margin-bottom:10px;">What it cannot do alone</div>'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#666666;line-height:1.75;margin-bottom:18px;">'
        'A verified record shows where you stood on one specific date. It does not show what happened after. '
        'In an enforcement proceeding, the question is rarely whether you ran an audit — '
        'it is whether your organization continued to act.'
        '</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;border-left:3px solid #C9A84C;margin-bottom:24px;">'
        '<tr><td bgcolor="#FDFCF9" style="background-color:#FDFCF9;padding:20px 24px;">'
        '<div style="font-family:Georgia,serif;font-size:14px;font-style:italic;color:#555555;line-height:1.75;">'
        '&ldquo;A static audit can be challenged. A continuously dated record is far harder to dispute.&rdquo;'
        '</div>'
        '</td></tr></table>'
        '<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:16px;"><tr>'
        '<td bgcolor="#C9A84C" style="background-color:#C9A84C;">'
        '<a href="' + cont_link + '" style="display:block;padding:15px 36px;font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#0A0E1A;text-decoration:none;">Activate Monitoring — $49/month</a>'
        '</td></tr></table>'
        '<div style="font-family:Arial,sans-serif;font-size:10px;color:#CCCCCC;">Your public record: <a href="' + verify_url + '" style="color:#8A6F2E;">' + verify_url + '</a></div>'
        '</td></tr>'

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:20px 40px 32px;border-top:1px solid #F0EDE8;">'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#777777;line-height:1.75;">'
        'Hans-Peter Nkansah<br>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">Founder, Institute of Digital Remediation</span>'
        '</div>'
        '</td></tr>'

        + _ftr(domain, registry_id)
    )

    return _send(email, subject, html)


# ── EMAIL 3 — DAY 5 RECORD SNAPSHOT ──────────────────────────────────────────

def send_hhs_day5_snapshot(email, domain, score=None, crits=None, registry_id=None):
    verify_url  = f'{VERIFY_BASE}/{domain}'
    cont_link   = f'{STRIPE_CONT_LINK}?client_reference_id={domain}'
    registry_id = registry_id or f'IDR-HHS-{domain.upper().replace(".", "-")}'

    subject = f'{domain} — your compliance record, 5 days in'

    html = (
        _hdr('HHS Compliance Record') +

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 24px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Five Days In</div>'
        '<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#0A0E1A;margin-bottom:8px;line-height:1.3;">'
        'Here is what your public record currently shows.'
        '</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#888888;font-style:italic;line-height:1.7;">'
        f'This is what HHS auditors, legal counsel, and compliance officers see when they check {verify_url}'
        '</div>'
        '</td></tr>'

        '<tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:rgba(201,168,76,0.5);margin-bottom:16px;">IDR HHS Registry — Current Status</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        + _receipt_row_dark('Domain', domain)
        + _receipt_row_dark('Registry Status', 'MANUAL VERIFIED')
        + _receipt_row_dark('Monitoring Status', 'NOT ACTIVE')
        + _receipt_row_dark('Next Rescan Scheduled', 'NONE — Monitoring Not Active')
        + '</table>'
        '</td></tr>'

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#555555;line-height:1.75;margin-bottom:18px;">'
        'Your record is verified. That is real. But the Monitoring Status: Not Active field '
        'is visible to anyone who checks your verification page, including enforcement auditors and legal teams.'
        '</div>'
        '<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:12px;"><tr>'
        '<td bgcolor="#C9A84C" style="background-color:#C9A84C;">'
        '<a href="' + cont_link + '" style="display:block;padding:15px 36px;font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#0A0E1A;text-decoration:none;">Activate Monitoring — $49/month</a>'
        '</td></tr></table>'
        '</td></tr>'

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:20px 40px 32px;border-top:1px solid #F0EDE8;">'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#777777;line-height:1.75;">'
        'Hans-Peter Nkansah<br>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">Founder, Institute of Digital Remediation</span>'
        '</div>'
        '</td></tr>'

        + _ftr(domain, registry_id)
    )

    return _send(email, subject, html)


# ── EMAIL 4 — DAY 9 FINAL WINDOW ─────────────────────────────────────────────

def send_hhs_day9_final(email, domain, score=None, registry_id=None):
    verify_url  = f'{VERIFY_BASE}/{domain}'
    cont_link   = f'{STRIPE_CONT_LINK}?client_reference_id={domain}'
    registry_id = registry_id or f'IDR-HHS-{domain.upper().replace(".", "-")}'

    subject = f'Final notice — {domain} · HHS enforcement window closes May 11'

    html = (
        _hdr('HHS Enforcement Window') +

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 24px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#E63946;margin-bottom:10px;">Enforcement Window Closing</div>'
        '<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#0A0E1A;margin-bottom:8px;line-height:1.3;">'
        'May 11 is the deadline. Your snapshot remains.'
        '</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#888888;font-style:italic;line-height:1.7;">'
        f'Your verified record for {domain} exists. What it documents is a single date in time. '
        f'After May 11, organizations with continuous monitoring records will be in a fundamentally different compliance position.'
        '</div>'
        '</td></tr>'

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:32px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:8px;">This Is the Final Notice</div>'
        '<div style="font-family:Georgia,serif;font-size:15px;color:#333333;line-height:1.75;margin-bottom:20px;">'
        'After this email, we will not follow up on monitoring. '
        'Your verified record remains active regardless. '
        'This is simply the last time we will make the case for what the next level means.'
        '</div>'
        '<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:12px;"><tr>'
        '<td bgcolor="#C9A84C" style="background-color:#C9A84C;">'
        '<a href="' + cont_link + '" style="display:block;padding:17px 40px;font-family:Arial,sans-serif;font-size:10.5px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#0A0E1A;text-decoration:none;">Activate Monitoring — $49/month</a>'
        '</td></tr></table>'
        '<div style="font-family:Arial,sans-serif;font-size:10px;color:#CCCCCC;margin-bottom:20px;">Weekly rescans · Monitoring Active status · Living evidence log</div>'
        '</td></tr>'

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:24px 40px 36px;border-top:1px solid #F0EDE8;">'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#555555;line-height:1.8;">'
        'I built IDR because the same systems that document compliance are the same ones being used to identify exposure. '
        'You have already done the hard part by creating a record. '
        'Keeping it active is the last step that separates a snapshot from a defense.<br><br>'
        'Hans-Peter Nkansah<br>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">Founder, Institute of Digital Remediation</span>'
        '</div>'
        '</td></tr>'

        + _ftr(domain, registry_id)
    )

    return _send(email, subject, html)


# ── MONITORING WELCOME ────────────────────────────────────────────────────────

def send_hhs_monitoring_welcome(email, domain, registry_id=None):
    verify_url  = f'{VERIFY_BASE}/{domain}'
    registry_id = registry_id or f'IDR-HHS-{domain.upper().replace(".", "-")}'

    subject = f'{domain} — Monitoring Active. Your record is now live.'

    html = (
        _hdr('Monitoring Active') +

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#52B788;margin-bottom:10px;">Monitoring Active</div>'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:700;color:#0A0E1A;margin-bottom:8px;line-height:1.25;">Your record is now a living document.</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#888888;font-style:italic;line-height:1.7;margin-bottom:24px;">'
        f'{domain} has been upgraded to Monitoring Active status in the IDR HHS Compliance Registry. '
        f'Weekly automated rescans are now scheduled. Your evidence log is building.'
        '</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;">'
        + _receipt_row('Domain', domain)
        + _receipt_row('Registry Status', 'MONITORING ACTIVE')
        + _receipt_row('Registry ID', registry_id)
        + _receipt_row('Scan Frequency', 'Weekly — Automated')
        + _receipt_row('Badge Status', 'HHS Accessibility Monitored — Active')
        + _receipt_row('Public Record', verify_url)
        + '</table>'
        '</td></tr>'

        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:24px 40px;">'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.75;">'
        'Your public verification page now reflects Monitoring Active status with a live badge. '
        'You will receive an email alert any time your score changes or new violations are detected. '
        'Every rescan is timestamped and sealed — your evidence log grows each week.'
        '</div>'
        '</td></tr>'

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:24px 40px 36px;border-top:1px solid #F0EDE8;">'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#777777;line-height:1.75;">'
        'Hans-Peter Nkansah<br>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">Founder, Institute of Digital Remediation</span>'
        '</div>'
        '</td></tr>'

        + _ftr(domain, registry_id)
    )

    return _send(email, subject, html)


# ── HELPER COMPONENTS ─────────────────────────────────────────────────────────

def _feature_row(title, body):
    return (
        '<tr><td style="padding:12px 0;border-bottom:1px solid #F0EDE8;vertical-align:top;">'
        '<table cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td width="22" style="vertical-align:top;padding-top:2px;">'
        '<div style="width:14px;height:14px;border:1px solid #C9A84C;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;">'
        '<span style="font-family:Arial,sans-serif;font-size:8px;color:#C9A84C;">&#x2713;</span>'
        '</div></td>'
        '<td style="padding-left:10px;vertical-align:top;">'
        '<div style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.04em;color:#333333;margin-bottom:3px;">' + title + '</div>'
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
        f'<div style="width:8px;height:8px;border-radius:50%;background:{dot_color};"></div>'
        '</td>'
        '<td style="padding-left:10px;vertical-align:top;">'
        f'<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:{when_color};margin-bottom:3px;">{when}</div>'
        f'<div style="font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.55;">{what}</div>'
        '</td></tr></table>'
    )


def _receipt_row(key, val):
    return (
        '<tr>'
        '<td bgcolor="#FDFCF9" style="background-color:#FDFCF9;padding:10px 16px;border-bottom:1px solid #F0EDE8;vertical-align:middle;">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#AAAAAA;">{key}</span>'
        '</td>'
        '<td bgcolor="#FDFCF9" style="background-color:#FDFCF9;padding:10px 16px;border-bottom:1px solid #F0EDE8;text-align:right;">'
        f'<span style="font-family:\'Courier New\',Courier,monospace;font-size:11px;color:#555555;">{val}</span>'
        '</td></tr>'
    )


def _receipt_row_dark(key, val):
    return (
        '<tr><td style="padding:10px 0;border-bottom:1px solid rgba(240,232,216,0.06);">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.14em;text-transform:uppercase;color:rgba(240,232,216,0.3);">{key}</span>'
        f'<span style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.14em;color:#C9A84C;float:right;">{val}</span>'
        '</td></tr>'
    )


def _compare_row(text):
    return (
        '<tr><td style="padding:5px 0;border-bottom:1px solid #F0EDE8;">'
        '<table cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td width="14" style="vertical-align:top;padding-top:3px;">'
        '<div style="width:4px;height:4px;border-radius:50%;background:#C9A84C;"></div>'
        '</td>'
        '<td style="padding-left:8px;">'
        '<span style="font-family:Georgia,serif;font-size:12.5px;color:#555555;line-height:1.5;">' + text + '</span>'
        '</td></tr></table>'
        '</td></tr>'
    )


# ── AUDIT DELIVERY — with PDF attachment ──────────────────────────────────────

def send_hhs_audit_delivery(email, domain, score, crits, total, receipt_id,
                             registry_id, timestamp_utc='', organization=None,
                             scan_data=None):
    """
    The actual product delivery. Sends the 30-page PDF audit report as an attachment.
    Hans-Peter triggers this manually within 48 hours of payment, or it fires
    automatically from the webhook when scan_data is available.

    New args vs original:
        organization : dict  — {name, address, contact_name, phone, email}
                               Falls back to domain if not provided.
        scan_data    : dict  — full scan dict to build the PDF. If None,
                               a minimal receipt is built from the flat args.
    """
    try:
        dt = datetime.strptime(timestamp_utc[:19], '%Y-%m-%dT%H:%M:%S') if timestamp_utc else datetime.now(timezone.utc)
        display_date = dt.strftime('%B %d, %Y at %H:%M UTC')
    except Exception:
        display_date = datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')

    score_color  = '#27AE60' if score >= 80 else '#E9A030' if score >= 60 else '#E05252'
    crits_word   = 'violation' if crits == 1 else 'violations'
    verify_url   = f'{VERIFY_BASE}/{domain}'
    cont_link    = f'{STRIPE_CONT_LINK}?client_reference_id={domain}'
    rid_display  = registry_id or f'IDR-HHS-{domain.upper().replace(".", "-")}'
    receipt_short = ((receipt_id[:24] + '&hellip;') if receipt_id and len(receipt_id) > 24 else receipt_id) if receipt_id else '—'

    # ── Build and attach the PDF ───────────────────────────────────────────────
    pdf_attachment = None
    try:
        # Build receipt_data for the PDF generator
        org = organization or {'name': domain}

        # Use provided scan_data or build a minimal scan from flat args
        if scan_data:
            scan = scan_data
        else:
            scan = {
                'domain':          domain,
                'url':             f'https://{domain}',
                'title':           '',
                'overall_score':   score,
                'overall_status':  'pass' if score >= 80 else 'warning' if score >= 60 else 'fail',
                'critical_count':  crits,
                'serious_count':   0,
                'total_issues':    total,
                'scan_duration_ms': 0,
                'categories':      [],
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

        pdf_bytes = generate_hhs_pdf(receipt_data)
        pdf_attachment = {
            'content':     base64.b64encode(pdf_bytes).decode(),
            'type':        'application/pdf',
            'filename':    f'IDR-HHS-AuditRecord-{domain}-{(receipt_id or "")[:8]}.pdf',
            'disposition': 'attachment',
        }
        print(f'[HHS_EMAIL] PDF generated — {len(pdf_bytes):,} bytes')
    except Exception as e:
        print(f'[HHS_EMAIL] PDF generation failed (email still sends): {e}')

    badge_embed = (
        f'&lt;!-- IDR HHS Compliance Badge — paste into your website footer --&gt;<br>'
        f'&lt;a href=&quot;{verify_url}&quot; target=&quot;_blank&quot; rel=&quot;noopener&quot;&gt;<br>'
        f'&nbsp;&nbsp;&lt;img src=&quot;https://idr-backend-production.up.railway.app/api/badge-image/{domain}&quot;<br>'
        f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;alt=&quot;IDR HHS Compliance Verified&quot; width=&quot;52&quot; height=&quot;52&quot;&gt;<br>'
        f'&lt;/a&gt;'
    )

    subject = f'Your HHS Readiness Record — {domain} · Audit Complete'

    html = (
        _hdr('HHS Readiness Record · Delivered') +

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 28px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Audit Complete — Record Delivered</div>'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:700;color:#0A0E1A;margin-bottom:8px;line-height:1.25;">Your HHS Readiness Record is complete.</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;font-style:italic;color:#AAAAAA;line-height:1.7;">'
        f'Everything below is your permanent compliance record for <strong style="color:#333333;">{domain}</strong>. '
        f'The full 30-page audit report is attached to this email as a PDF.'
        '</div>'
        '</td></tr>'

        # PDF attached notice
        '<tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:18px 40px;">'
        '<table cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td width="28" style="vertical-align:middle;padding-right:12px;">'
        '<div style="font-size:20px;">📄</div>'
        '</td>'
        '<td style="vertical-align:middle;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:rgba(201,168,76,0.6);margin-bottom:3px;">Attached to this email</div>'
        f'<div style="font-family:\'Courier New\',Courier,monospace;font-size:11px;color:#C9A84C;">IDR-HHS-AuditRecord-{domain}-{(receipt_id or "")[:8]}.pdf</div>'
        '<div style="font-family:Arial,sans-serif;font-size:9px;color:rgba(255,255,255,0.3);margin-top:2px;">30-page court-ready audit record · Cryptographically sealed</div>'
        '</td></tr></table>'
        '</td></tr>'

        # Score panel
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td align="center" style="padding-right:24px;border-right:1px solid #E8E4DC;width:130px;vertical-align:middle;">'
        f'<div style="font-family:Georgia,serif;font-size:60px;font-weight:700;color:{score_color};line-height:1;">{score}</div>'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.2em;color:#AAAAAA;text-transform:uppercase;margin-top:4px;">Accessibility Score</div>'
        '</td>'
        '<td style="padding-left:28px;vertical-align:middle;">'
        f'<div style="font-family:Georgia,serif;font-size:36px;font-weight:700;color:#E05252;line-height:1;">{crits}</div>'
        f'<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.18em;color:#AAAAAA;text-transform:uppercase;margin-top:4px;margin-bottom:14px;">Critical {crits_word}</div>'
        f'<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#888888;line-height:1.6;">'
        f'{total} total issues identified and documented in your sealed record.'
        '</div>'
        '</td></tr></table>'
        '</td></tr>'

        # Human validation
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:32px 40px 8px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#C9A84C;padding-bottom:14px;border-bottom:1px solid #E8E4DC;margin-bottom:20px;">Human Validation — Five-Point Audit</div>'
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:0 40px 32px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        + _feature_row('Keyboard Navigation Test', 'Full site navigation completed using keyboard only. Tab order, focus visibility, and interactive element reachability documented.')
        + _feature_row('Screen Reader Pass', 'Page content read using assistive technology. Heading structure, landmark navigation, and image descriptions verified.')
        + _feature_row('Form Completion Test', 'All forms tested for label association, error messaging, and accessible submission flow.')
        + _feature_row('PDF Accessibility Review', 'Any linked PDF documents reviewed for tagged structure, reading order, and alternative text.')
        + _feature_row('Visual Stress Testing', 'Page tested at 200% zoom, high contrast mode, and reduced motion settings for WCAG 2.1 AA conformance.')
        + '</table>'
        '</td></tr>'

        # Badge
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#AAAAAA;margin-bottom:16px;">Your IDR Badge — On Record Status</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td width="80" style="vertical-align:middle;padding-right:20px;">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 96 96">'
        '<circle cx="48" cy="48" r="47.5" fill="#0A0E1A"/>'
        '<circle cx="48" cy="48" r="45.6" fill="none" stroke="#C9A84C" stroke-width="1.5" opacity="0.80"/>'
        '<circle cx="48" cy="48" r="34.6" fill="none" stroke="#C9A84C" stroke-width="0.65" opacity="0.17"/>'
        '<text x="48" y="45.3" font-family="Georgia,serif" font-size="27" font-weight="700" fill="#C9A84C" opacity="0.86" text-anchor="middle" dominant-baseline="middle">IDR</text>'
        '<line x1="22.3" y1="55.3" x2="73.7" y2="55.3" stroke="#8A6F2E" stroke-width="0.75" opacity="0.58"/>'
        '<text x="48" y="66.8" font-family="Arial,sans-serif" font-size="7.3" font-weight="600" fill="#C9A84C" text-anchor="middle" letter-spacing="0.77" opacity="0.68">ON RECORD</text>'
        '</svg>'
        '</td>'
        '<td style="vertical-align:middle;">'
        '<div style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#C9A84C;margin-bottom:6px;">ON RECORD Badge — Active</div>'
        '<div style="font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.65;margin-bottom:10px;">'
        'This static gold badge is now live on your public verification page. It signals to any visitor — including auditors and legal counsel — that your organization has an established, documented compliance record.'
        '</div>'
        '<div style="font-family:Arial,sans-serif;font-size:10px;color:#AAAAAA;">Your verify page: <a href="' + verify_url + '" style="color:#8A6F2E;">' + verify_url + '</a></div>'
        '</td></tr></table>'
        '</td></tr>'

        # Badge embed
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#AAAAAA;margin-bottom:12px;">Embed Your Badge on Your Website</div>'
        '<div style="font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.65;margin-bottom:14px;">'
        'Paste this into your website footer or compliance page.'
        '</div>'
        '<div style="background:#0A0E1A;border:1px solid rgba(201,168,76,0.2);border-radius:3px;padding:16px 18px;font-family:\'Courier New\',Courier,monospace;font-size:10px;color:rgba(201,168,76,0.6);line-height:1.85;">'
        + badge_embed +
        '</div>'
        '</td></tr>'

        # Registry record
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#AAAAAA;margin-bottom:14px;">Your Sealed Registry Record</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;">'
        + _receipt_row('Domain', domain)
        + _receipt_row('Registry ID', rid_display)
        + _receipt_row('Receipt ID', receipt_short)
        + _receipt_row('Audit Timestamp', display_date)
        + _receipt_row('Accessibility Score', f'{score}/100')
        + _receipt_row('Critical Violations', str(crits))
        + _receipt_row('Total Issues Documented', str(total))
        + _receipt_row('Protocol Standard', 'WCAG 2.1 AA · Section 504 / 1557')
        + _receipt_row('Verification Type', 'Manual Verified — Human Audited')
        + _receipt_row('Public Verify URL', verify_url)
        + '</table></td></tr>'

        # Monitoring close
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;border-left:3px solid #C9A84C;"><tr>'
        '<td bgcolor="#FDFCF9" style="background-color:#FDFCF9;padding:22px 26px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">What Your Record Does — and What It Does Not</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#555555;line-height:1.75;margin-bottom:14px;">'
        'Your ON RECORD badge documents where your organization stood on the date of this audit. '
        'HHS enforcement looks for a pattern — not a moment.'
        '</div>'
        '<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#AAAAAA;line-height:1.6;border-left:2px solid #E8E4DC;padding-left:14px;margin-bottom:18px;">'
        '&ldquo;A static audit can be challenged. A continuously dated record is far harder to dispute.&rdquo;'
        '</div>'
        '<a href="' + cont_link + '" style="display:inline-block;padding:12px 26px;background-color:transparent;border:1px solid #C9A84C;font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#8A6F2E;text-decoration:none;">Upgrade to Monitoring Active — $49/month</a>'
        '</td></tr></table>'
        '</td></tr>'

        # Signature
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:24px 40px 36px;border-top:1px solid #F0EDE8;">'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#555555;line-height:1.8;">'
        'Your full audit report is attached. If you have any questions about the findings, reply directly to this email.<br><br>'
        'Hans-Peter Nkansah<br>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">Founder, Institute of Digital Remediation</span><br>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">idrshield.com &nbsp;·&nbsp; hello@idrshield.com</span>'
        '</div>'
        '</td></tr>'

        + _ftr(domain, rid_display)
    )

    attachments = [pdf_attachment] if pdf_attachment else None
    return _send(email, subject, html, attachments=attachments)


# ── PAYMENT NOTIFICATION TO HANS-PETER ───────────────────────────────────────

def send_payment_notification(domain, email, amount, product_type):
    """
    Fires internally to idrshieldhq@gmail.com every time a payment lands.
    """
    NOTIFY_EMAIL = 'idrshieldhq@gmail.com'
    verify_url   = f'{VERIFY_BASE}/{domain}'
    product_label = '$497 HHS Readiness Audit' if product_type == 'audit' else '$49/month Monitoring'

    subject = f'[NEW PAYMENT] {domain} — {product_label}'

    html = (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
        '<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:30px 16px;">'
        '<div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">'
        '<div style="background:#0A0E1A;padding:22px 28px;border-bottom:3px solid #C9A84C;">'
        '<p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:rgba(201,168,76,0.6);margin:0 0 4px;">IDR Shield — Payment Alert</p>'
        f'<h1 style="font-size:18px;font-weight:normal;color:#FAF7F2;margin:0;">{product_label} Received</h1>'
        '</div>'
        '<div style="padding:24px 28px;">'
        f'<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        f'<tr><td style="padding:7px 0;color:#999;width:120px;">Domain</td><td style="padding:7px 0;color:#333;font-weight:700;">{domain}</td></tr>'
        f'<tr><td style="padding:7px 0;color:#999;">Customer</td><td style="padding:7px 0;color:#333;">{email}</td></tr>'
        f'<tr><td style="padding:7px 0;color:#999;">Product</td><td style="padding:7px 0;color:#C9A84C;font-weight:700;">{product_label}</td></tr>'
        f'<tr><td style="padding:7px 0;color:#999;">Verify URL</td><td style="padding:7px 0;"><a href="{verify_url}" style="color:#8A6F2E;">{verify_url}</a></td></tr>'
        '</table>'
        '</div>'
        + (
            '<div style="background:#FDF8F0;border-top:1px solid #F0E8D8;border-bottom:1px solid #F0E8D8;padding:18px 28px;">'
            '<p style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;color:#C9A84C;margin:0 0 6px;letter-spacing:0.1em;text-transform:uppercase;">Action Required — 48 Hour Delivery</p>'
            '<p style="font-family:Georgia,serif;font-size:13px;color:#555;line-height:1.6;margin:0 0 14px;">'
            f'Audit the site, complete your manual checks, then deliver using the link below.'
            '</p>'
            f'<a href="https://idrshield.com/hhs-audit-delivery.html?domain={domain}&email={email}" '
            'style="display:inline-block;padding:11px 24px;background:#C9A84C;'
            'font-family:Arial,sans-serif;font-size:10px;font-weight:700;'
            'letter-spacing:0.16em;text-transform:uppercase;color:#0A0E1A;text-decoration:none;">'
            f'Open Delivery Console → {domain}'
            '</a>'
            '</div>'
            if product_type == 'audit' else
            '<div style="background:#F0FDF4;border-top:1px solid #D1FAE5;border-bottom:1px solid #D1FAE5;padding:18px 28px;">'
            '<p style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;color:#27AE60;margin:0 0 6px;letter-spacing:0.1em;text-transform:uppercase;">Monitoring Activated — No Action Required</p>'
            '<p style="font-family:Georgia,serif;font-size:13px;color:#555;line-height:1.6;margin:0;">Weekly rescans will begin automatically. Registry status upgraded to Monitoring Active.</p>'
            '</div>'
        ) +
        '<div style="padding:16px 28px;">'
        '<p style="font-family:Arial,sans-serif;font-size:10px;color:#CCCCCC;margin:0;">IDR Shield · Automated payment alert · Do not reply</p>'
        '</div>'
        '</div>'
        '</body></html>'
    )

    return _send(NOTIFY_EMAIL, subject, html)
