"""
IDR Shield — hhs_emailer.py
HHS Healthcare Email Sequence
Four-email sequence matching emailer.py style.
Same SendGrid setup. Same solid-hex email-safe HTML.

EMAIL 1  — Activation confirmation   (fires immediately on $497 payment)
EMAIL 2  — Day 2 monitoring upsell   (fires if no $49/mo — tag: hhs_activated)
EMAIL 3  — Day 5 record snapshot     (fires if still no monitoring)
EMAIL 4  — Day 9 final window        (fires if still no monitoring — then silence)

TAGS:
  hhs_activated   — paid $497, no monitoring yet → runs sequence
  hhs_monitoring  — added $49/mo → sequence stops; monitoring welcome sent instead
"""

import os
from datetime import datetime, timezone, timedelta

SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
FROM_EMAIL       = 'hello@idrshield.com'
FROM_NAME        = 'Hans-Peter Nkansah — Institute of Digital Remediation'
STRIPE_CONT_LINK = os.environ.get('STRIPE_CONT_LINK', 'https://buy.stripe.com/REPLACE_CONTINUITY_LINK')
VERIFY_BASE      = 'https://idrshield.com/hhs-verify'


def _send(to_email, subject, html, text=''):
    if not SENDGRID_API_KEY:
        print(f'[HHS_EMAIL] No SENDGRID_API_KEY — skipping: {subject}')
        return False
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        message = Mail(
            from_email=(FROM_EMAIL, FROM_NAME),
            to_emails=to_email,
            subject=subject,
            html_content=html,
            plain_text_content=text or _strip_html(html)
        )
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
    """Shared email header — navy top bar, IDR seal, sender identity."""
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
        # Gold top rule
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;height:4px;font-size:0;">&nbsp;</td></tr>'
        # Header
        '<tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:28px 40px 22px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        # Seal + wordmark
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
        # Right — eyebrow
        '<td align="right" style="vertical-align:middle;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;color:rgba(201,168,76,0.35);letter-spacing:0.1em;text-transform:uppercase;">'
        + eyebrow_line +
        '</div></td>'
        '</tr></table></td></tr>'
        # Nav divider
        '<tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:0 40px;">'
        '<div style="height:1px;background:rgba(201,168,76,0.15);"></div>'
        '</td></tr>'
    )


def _ftr(domain='', registry_id=''):
    """Shared email footer."""
    verify_url = f'{VERIFY_BASE}/{domain}' if domain else 'https://idrshield.com/healthcare'
    return (
        # Registry line
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:22px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#AAAAAA;margin-bottom:7px;">Your Public Verification Record</div>'
        '<a href="' + verify_url + '" style="font-family:\'Courier New\',Courier,monospace;font-size:11px;color:#8A6F2E;text-decoration:none;">' + verify_url + '</a>'
        + (f'<div style="margin-top:7px;font-family:\'Courier New\',Courier,monospace;font-size:9px;color:#BBBBBB;">REGISTRY ID · {registry_id}</div>' if registry_id else '') +
        '</td></tr>'
        # Legal footer
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
        # Gold bottom rule
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;height:4px;font-size:0;">&nbsp;</td></tr>'
        '</table></td></tr></table></body></html>'
    )


def _section_divider():
    return '<tr><td bgcolor="#F2EFE9" height="2" style="background-color:#F2EFE9;height:2px;font-size:0;">&nbsp;</td></tr>'


# ── EMAIL 1 — ACTIVATION CONFIRMATION ────────────────────────────────────────

def send_hhs_activation_confirmation(email, domain, score, crits, total, receipt_id, registry_id, timestamp_utc=''):
    """
    Fires immediately on $497 payment.
    Elite club tone. You are now on record. Here is what was created.
    Soft close on monitoring — planted, not pushed.
    """
    try:
        dt = datetime.strptime(timestamp_utc[:19], '%Y-%m-%dT%H:%M:%S') if timestamp_utc else datetime.now(timezone.utc)
        display_date = dt.strftime('%B %d, %Y at %H:%M UTC')
    except Exception:
        display_date = datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')

    score_color = '#27AE60' if score >= 80 else '#E9A030' if score >= 60 else '#E05252'
    crits_word  = 'violation' if crits == 1 else 'violations'
    receipt_short = (receipt_id[:24] + '&hellip;') if len(receipt_id) > 24 else receipt_id
    verify_url = f'{VERIFY_BASE}/{domain}'
    cont_link  = f'{STRIPE_CONT_LINK}?client_reference_id={domain}'

    subject = f'Your HHS Readiness Record is being created — {domain}'

    html = (
        _hdr('HHS Readiness Audit') +

        # Opening — gold bar
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 28px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Activation Confirmed</div>'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:700;color:#0A0E1A;margin-bottom:6px;line-height:1.25;">Your record is now being created.</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;font-style:italic;color:#AAAAAA;line-height:1.7;margin-bottom:0;">'
        f'Your HHS Readiness Audit for <strong style="color:#333333;">{domain}</strong> has been activated. '
        f'A human auditor will complete your compliance record within 48 hours. '
        f'This email confirms what has been established — and what arrives next.'
        '</div>'
        '</td></tr>'

        # Score panel
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td align="center" style="padding-right:24px;border-right:1px solid #E8E4DC;width:130px;vertical-align:middle;">'
        f'<div style="font-family:Georgia,serif;font-size:60px;font-weight:700;color:{score_color};line-height:1;">{score}</div>'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.2em;color:#AAAAAA;text-transform:uppercase;margin-top:4px;">Baseline Score</div>'
        '</td>'
        '<td style="padding-left:28px;vertical-align:middle;">'
        f'<div style="font-family:Georgia,serif;font-size:36px;font-weight:700;color:#E05252;line-height:1;">{crits}</div>'
        f'<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.18em;color:#AAAAAA;text-transform:uppercase;margin-top:4px;margin-bottom:14px;">Critical {crits_word}</div>'
        f'<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#888888;line-height:1.6;">'
        f'{total} total issues flagged. These findings are now formally documented and timestamped.'
        '</div>'
        '</td></tr></table>'
        '</td></tr>'

        # What you activated
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:32px 40px 0;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#C9A84C;padding-bottom:14px;border-bottom:1px solid #E8E4DC;margin-bottom:20px;">What You Have Activated</div>'
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:0 40px 32px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'

        # Feature rows
        + _feature_row('SHA-256 Timestamped Scan Receipt', 'A cryptographically sealed, tamper-proof record of your accessibility posture at the time of audit. Immutable by design.')
        + _feature_row('IDR Registry Entry — Manual Verified', f'Your organization is now enrolled in the IDR HHS Compliance Registry. Status upon delivery: Manual Verified. Public verification record: {verify_url}')
        + _feature_row('Human Validation Audit', 'A human auditor will complete all five manual checks within 24 hours: keyboard navigation, screen reader pass, form completion, PDF accessibility, and visual stress testing.')
        + _feature_row('Defense Positioning Summary', 'A formal statement confirming your organization has initiated active accessibility monitoring and remediation — ready for legal use under Section 504 and Section 1557 if compliance is ever challenged.')
        + _feature_row('Screenshot Evidence Package', 'Annotated screenshots of all identified failure points with plain-language explanation of user impact for each critical finding.')

        + '</table></td></tr>'

        # Timeline
        '<tr><td bgcolor="#FAFAF8" style="background-color:#FAFAF8;padding:28px 40px;border-top:1px solid #F0EDE8;border-bottom:1px solid #F0EDE8;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#AAAAAA;margin-bottom:18px;">What Happens Next</div>'
        + _tl_row('Now', 'This confirmation email is your record of activation. Save it.', True)
        + _tl_row('Within 5 minutes', 'Your registry record is initialized. Status: Pending Verification.', False)
        + _tl_row('Within 24 hours', 'Human validation audit completed. Findings documented and annotated.', False)
        + _tl_row('Within 48 hours', 'Complete HHS Readiness Record delivered to this email. Registry status updates to Manual Verified.', False)
        + '</td></tr>'

        # Receipt data
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#AAAAAA;margin-bottom:14px;">Your Activation Record</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;">'
        + _receipt_row('Domain', domain)
        + _receipt_row('Registry ID', registry_id)
        + _receipt_row('Receipt ID', receipt_short)
        + _receipt_row('Activation Timestamp', display_date)
        + _receipt_row('Protocol Standard', 'WCAG 2.1 AA · Section 504 / 1557')
        + _receipt_row('Status', 'Pending Human Verification → Manual Verified within 48 hrs')
        + '</table></td></tr>'

        + _section_divider() +

        # Monitoring soft close
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

        # Signature
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px 36px;border-top:1px solid #F0EDE8;">'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#555555;line-height:1.75;">'
        'Your record is now in motion. We will have it complete and in your hands within 48 hours.<br><br>'
        'If you have any questions before then, reply directly to this email.<br><br>'
        'Hans-Peter Nkansah<br>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">Founder, Institute of Digital Remediation</span><br>'
        '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">idrshield.com &nbsp;·&nbsp; hello@idrshield.com</span>'
        '</div>'
        '</td></tr>'

        + _ftr(domain, registry_id)
    )

    return _send(email, subject, html)


# ── EMAIL 2 — DAY 2 MONITORING UPSELL ────────────────────────────────────────

def send_hhs_day2_monitoring(email, domain, score, registry_id):
    """
    Day 2. Only if no $49/mo purchased (tag: hhs_activated, not hhs_monitoring).
    The snapshot is real. Here is what monitoring adds.
    """
    verify_url = f'{VERIFY_BASE}/{domain}'
    cont_link  = f'{STRIPE_CONT_LINK}?client_reference_id={domain}'

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
        'it is whether your organization continued to act. A single snapshot answers one question. '
        'An ongoing, continuously dated record answers a much harder one.'
        '</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;border-left:3px solid #C9A84C;margin-bottom:24px;">'
        '<tr><td bgcolor="#FDFCF9" style="background-color:#FDFCF9;padding:20px 24px;">'
        '<div style="font-family:Georgia,serif;font-size:14px;font-style:italic;color:#555555;line-height:1.75;">'
        '&ldquo;A static audit can be challenged. A continuously dated record is far harder to dispute.&rdquo;'
        '</div>'
        '</td></tr></table>'
        '</td></tr>'

        # Comparison
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#AAAAAA;margin-bottom:16px;">Manual Verified vs. Monitoring Active</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr>'
        '<td width="50%" style="padding-right:16px;vertical-align:top;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#C9A84C;margin-bottom:10px;">Manual Verified (Your Current Status)</div>'
        + _compare_row('Defensible record — point in time')
        + _compare_row('SHA-256 sealed audit')
        + _compare_row('Public registry entry')
        + _compare_row('Timestamp of action — one date')
        + '</td>'
        '<td width="50%" style="padding-left:16px;vertical-align:top;border-left:1px solid #E8E4DC;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#52B788;margin-bottom:10px;">Monitoring Active ($49/mo)</div>'
        + _compare_row('Everything above, plus:')
        + _compare_row('Weekly automated rescans')
        + _compare_row('Continuous evidence log — every scan sealed')
        + _compare_row('Real-time alerts on score changes')
        + _compare_row('Living record — strongest possible defense')
        + '</td></tr></table>'
        '</td></tr>'

        # CTA
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:32px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:8px;">Activate Ongoing Monitoring</div>'
        '<div style="font-family:Georgia,serif;font-size:16px;font-weight:700;color:#0A0E1A;margin-bottom:6px;">Convert your snapshot into a living record.</div>'
        '<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#AAAAAA;margin-bottom:22px;">$49/month. Cancel anytime. Upgrades your registry status to Monitoring Active immediately.</div>'
        '<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:16px;"><tr>'
        '<td bgcolor="#C9A84C" style="background-color:#C9A84C;">'
        '<a href="' + cont_link + '" style="display:block;padding:15px 36px;font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#0A0E1A;text-decoration:none;">Activate Monitoring — $49/month</a>'
        '</td></tr></table>'
        '<div style="font-family:Arial,sans-serif;font-size:10px;color:#CCCCCC;">Your public record: <a href="' + verify_url + '" style="color:#8A6F2E;">' + verify_url + '</a></div>'
        '</td></tr>'

        # Sign off
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

def send_hhs_day5_snapshot(email, domain, score, crits, registry_id):
    """
    Day 5. Only if still no monitoring.
    Shows their verify page status. Makes the absence of monitoring visible.
    """
    verify_url = f'{VERIFY_BASE}/{domain}'
    cont_link  = f'{STRIPE_CONT_LINK}?client_reference_id={domain}'
    days_since = 5
    score_color = '#27AE60' if score >= 80 else '#E9A030' if score >= 60 else '#E05252'

    subject = f'{domain} — your compliance record, {days_since} days in'

    html = (
        _hdr('HHS Compliance Record') +

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px 24px;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Five Days In</div>'
        '<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#0A0E1A;margin-bottom:8px;line-height:1.3;">'
        f'Here is what your public record currently shows.'
        '</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#888888;font-style:italic;line-height:1.7;">'
        f'This is what HHS auditors, legal counsel, and compliance officers see when they check {verify_url}'
        '</div>'
        '</td></tr>'

        # Registry snapshot
        '<tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:28px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:rgba(201,168,76,0.5);margin-bottom:16px;">IDR HHS Registry — Current Status</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td style="padding:10px 0;border-bottom:1px solid rgba(240,232,216,0.06);">'
        '<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.14em;text-transform:uppercase;color:rgba(240,232,216,0.3);">Domain</span>'
        '<span style="font-family:\'Courier New\',Courier,monospace;font-size:12px;color:rgba(201,168,76,0.7);float:right;">' + domain + '</span>'
        '</td></tr>'
        '<tr><td style="padding:10px 0;border-bottom:1px solid rgba(240,232,216,0.06);">'
        '<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.14em;text-transform:uppercase;color:rgba(240,232,216,0.3);">Registry Status</span>'
        '<span style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.14em;color:#C9A84C;float:right;">MANUAL VERIFIED</span>'
        '</td></tr>'
        f'<tr><td style="padding:10px 0;border-bottom:1px solid rgba(240,232,216,0.06);">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.14em;text-transform:uppercase;color:rgba(240,232,216,0.3);">Current Score</span>'
        f'<span style="font-family:Georgia,serif;font-size:16px;font-weight:700;color:{score_color};float:right;">{score}/100</span>'
        f'</td></tr>'
        f'<tr><td style="padding:10px 0;border-bottom:1px solid rgba(240,232,216,0.06);">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.14em;text-transform:uppercase;color:rgba(240,232,216,0.3);">Monitoring Status</span>'
        f'<span style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.14em;color:#E63946;float:right;">NOT ACTIVE</span>'
        f'</td></tr>'
        '<tr><td style="padding:10px 0;">'
        '<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.14em;text-transform:uppercase;color:rgba(240,232,216,0.3);">Next Rescan Scheduled</span>'
        '<span style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.14em;color:rgba(240,232,216,0.25);float:right;">NONE — Monitoring Not Active</span>'
        '</td></tr>'
        '</table>'
        '</td></tr>'

        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#555555;line-height:1.75;margin-bottom:18px;">'
        'Your record is verified. That is real. But the field above — Monitoring Status: Not Active — '
        'is visible to anyone who checks your verification page, including enforcement auditors and legal teams. '
        'It signals that your organization documented a moment, not a practice.'
        '</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;font-style:italic;color:#888888;line-height:1.75;border-left:3px solid #E8E4DC;padding-left:16px;margin-bottom:24px;">'
        'The difference between a verified record and a monitored record is the difference between '
        'proving you started and proving you kept going. In an enforcement context, the second is worth significantly more.'
        '</div>'
        '<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:12px;"><tr>'
        '<td bgcolor="#C9A84C" style="background-color:#C9A84C;">'
        '<a href="' + cont_link + '" style="display:block;padding:15px 36px;font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#0A0E1A;text-decoration:none;">Activate Monitoring — $49/month</a>'
        '</td></tr></table>'
        '<div style="font-family:Georgia,serif;font-size:12px;font-style:italic;color:#CCCCCC;">Upgrades your public registry status to Monitoring Active immediately.</div>'
        '</td></tr>'

        # Sign off
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

def send_hhs_day9_final(email, domain, score, registry_id):
    """
    Day 9. Final email in sequence. Hard deadline. Then silence.
    Only if still no monitoring.
    """
    verify_url = f'{VERIFY_BASE}/{domain}'
    cont_link  = f'{STRIPE_CONT_LINK}?client_reference_id={domain}'

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
        f'After May 11, organizations with continuous monitoring records will be in a fundamentally different compliance position than those with a single audit.'
        '</div>'
        '</td></tr>'

        '<tr><td bgcolor="#FDF8F0" style="background-color:#FDF8F0;border-top:1px solid #F0E8D8;border-bottom:1px solid #F0E8D8;padding:24px 40px;border-left:4px solid #E63946;">'
        '<div style="font-family:Georgia,serif;font-size:17px;font-weight:700;color:#0A0E1A;line-height:1.45;margin-bottom:10px;">What changes after May 11</div>'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#666666;line-height:1.75;">'
        'Organizations with an active monitoring record will have demonstrated a pattern of compliance effort — '
        'multiple scans, continuous documentation, real-time remediation tracking. '
        'Organizations with a single audit will have demonstrated that they acted once. '
        'In an enforcement proceeding, those two positions are not equivalent.'
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
        '<div style="font-family:Arial,sans-serif;font-size:10px;color:#CCCCCC;margin-bottom:20px;">Weekly rescans · Monitoring Active status · Gold pulse badge · Living evidence log</div>'
        '<div style="font-family:Georgia,serif;font-size:12px;font-style:italic;color:#CCCCCC;">Your public record: <a href="' + verify_url + '" style="color:#8A6F2E;">' + verify_url + '</a></div>'
        '</td></tr>'

        # Final signature — more personal
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

def send_hhs_monitoring_welcome(email, domain, registry_id):
    """
    Fires when $49/mo is activated. Stops the sequence.
    Confirms status upgrade. Short and authoritative.
    """
    verify_url = f'{VERIFY_BASE}/{domain}'

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
    dot_color = '#C9A84C' if active else '#DDDDDD'
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
