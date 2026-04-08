"""
IDR Shield — emailer.py
All transactional email via SendGrid.
Email-safe HTML: solid hex bgcolor on every td, no border-radius on tables,
no rgba(), no linear-gradient. Tested against iOS Mail + Gmail.
"""

import os

SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
FROM_EMAIL       = 'hello@idrshield.com'
FROM_NAME        = 'Institute of Digital Remediation'
GUMROAD_URL      = os.environ.get('GUMROAD_URL', 'https://idrshield.gumroad.com/l/oadcfq')


def _send(to_email, subject, html):
    if not SENDGRID_API_KEY:
        print(f'[EMAIL] No SENDGRID_API_KEY — skipping: {subject}')
        return
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail
        message = Mail(
            from_email=(FROM_EMAIL, FROM_NAME),
            to_emails=to_email,
            subject=subject,
            html_content=html
        )
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        r  = sg.client.mail.send.post(request_body=message.get())
        print(f'[EMAIL] Sent "{subject}" to {to_email} — {r.status_code}')
    except Exception as e:
        print(f'[EMAIL] SendGrid error: {e}')



def send_free_summary_email(email, receipt):
    sc          = receipt.get('scan', {})
    domain      = sc.get('domain', 'your store')
    score       = int(sc.get('overall_score', 0))
    status      = sc.get('overall_status', 'warning')
    crits       = sc.get('critical_count', 0)
    total       = sc.get('total_issues', 0)
    cats        = sc.get('categories', [])
    receipt_id  = receipt.get('receipt_id', '')
    registry_id = receipt.get('registry_id', '')
    timestamp   = sc.get('timestamp', '')

    try:
        from datetime import datetime
        dt = datetime.strptime(timestamp[:19], '%Y-%m-%dT%H:%M:%S')
        display_date = dt.strftime('%b %-d, %Y · %H:%M UTC')
    except Exception:
        display_date = (timestamp[:16].replace('T', ' ') + ' UTC') if timestamp else ''

    if score >= 80:
        score_color  = '#27AE60'
        status_label = 'PASS'
        status_badge = 'Compliance Verified'
        badge_color  = '#27AE60'
    elif score >= 50:
        score_color  = '#E9A030'
        status_label = 'MONITORING'
        status_badge = 'Remediation Required'
        badge_color  = '#E9A030'
    else:
        score_color  = '#E05252'
        status_label = 'FAIL'
        status_badge = 'Remediation Required'
        badge_color  = '#E05252'

    subject = f'Your store scan results — {domain}'

    cat_map    = {c['category']: c for c in cats} if cats else {}
    cat_labels = {
        'alt_text':          'Image Alt Text',
        'form_labels':       'Form Labels',
        'keyboard_nav':      'Keyboard Navigation',
        'heading_structure': 'Heading Structure',
        'contrast':          'Color Contrast',
        'aria_links':        'ARIA & Links',
    }

    cat_rows_html = ''
    row_bg = ['#FFFFFF', '#FAFAF8']
    for i, (cat_key, cat_name) in enumerate(cat_labels.items()):
        bg       = row_bg[i % 2]
        cat_data = cat_map.get(cat_key, {})
        cat_crits = cat_data.get('critical', 0)
        cat_total = cat_data.get('total', 0)
        if cat_crits > 0:
            bar_color  = '#E05252'
            bar_width  = max(20, min(160, int(cat_crits * 20)))
            count_html = f'<span style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:#E05252;">{cat_crits} critical</span>'
        elif cat_total > 0:
            bar_color  = '#E9C46A'
            bar_width  = max(40, min(160, int(cat_total * 25)))
            count_html = f'<span style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:#E9A030;">{cat_total} issue{"s" if cat_total != 1 else ""}</span>'
        else:
            bar_color  = '#52B788'
            bar_width  = 160
            count_html = '<span style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:#52B788;">&#x2713; Clean</span>'
        is_last   = (i == len(cat_labels) - 1)
        border_st = '' if is_last else 'border-bottom:1px solid #F2EFE9;'
        cat_rows_html += (
            f'<tr><td bgcolor="{bg}" style="background-color:{bg};padding:0 40px;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="{border_st}"><tr>'
            f'<td style="padding:13px 0;vertical-align:middle;">'
            f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:9px;font-weight:700;'
            f'letter-spacing:0.1em;text-transform:uppercase;color:#333333;margin-bottom:7px;">{cat_name}</div>'
            f'<table cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td bgcolor="#F0ECE4" width="160" height="3" style="background-color:#F0ECE4;width:160px;height:3px;font-size:0;">'
            f'<table cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td bgcolor="{bar_color}" width="{bar_width}" height="3" style="background-color:{bar_color};width:{bar_width}px;height:3px;font-size:0;">&nbsp;</td>'
            f'</tr></table></td></tr></table></td>'
            f'<td align="right" style="vertical-align:middle;white-space:nowrap;">{count_html}</td>'
            f'</tr></table></td></tr>\n'
        )

    receipt_short = (receipt_id[:22] + '&hellip;') if len(receipt_id) > 22 else receipt_id
    crits_word    = 'violation' if crits == 1 else 'violations'

    html = (
        '<!DOCTYPE html><html lang="en"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="x-apple-disable-message-reformatting">'
        '<title>Your IDR Scan Results</title>'
        '</head><body style="margin:0;padding:0;background-color:#F2EFE9;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#F2EFE9;">'
        '<tr><td align="center" style="padding:0;">'
        '<table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;">'

        # Top gold rule
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;height:4px;font-size:0;line-height:0;">&nbsp;</td></tr>'

        # Header
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:24px 40px 20px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td style="vertical-align:middle;">'
        '<table cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td style="vertical-align:middle;">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 36 36">'
        '<circle cx="18" cy="18" r="17" fill="#0A0E1A"/>'
        '<circle cx="18" cy="18" r="16.5" fill="none" stroke="#C9A84C" stroke-width="1.2" opacity="0.9"/>'
        '<circle cx="18" cy="18" r="12" fill="none" stroke="#C9A84C" stroke-width="0.5" opacity="0.3"/>'
        '<text x="18" y="22" font-family="Georgia,serif" font-size="9.5" font-weight="700" fill="#C9A84C" text-anchor="middle">IDR</text>'
        '</svg></td><td width="10">&nbsp;</td>'
        '<td style="vertical-align:middle;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#C9A84C;line-height:1.2;">Institute of Digital Remediation</div>'
        '<div style="font-family:Georgia,serif;font-size:10px;font-style:italic;color:#8A6F2E;margin-top:2px;">IDR Protocol Series &middot; 2026 Edition</div>'
        '</td></tr></table></td>'
        f'<td align="right" style="vertical-align:middle;">'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;color:#AAAAAA;letter-spacing:0.1em;text-transform:uppercase;">Scan Receipt</div>'
        f'<div style="font-family:Georgia,serif;font-size:10px;color:#BBBBBB;margin-top:2px;font-style:italic;">{display_date}</div>'
        '</td></tr></table></td></tr>'

        # Header divider
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:0 40px;"><div style="height:1px;background:#E8E4DC;"></div></td></tr>'

        # Domain + status
        f'<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:20px 40px 0;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td style="vertical-align:bottom;">'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.3em;text-transform:uppercase;color:#BBBBBB;margin-bottom:6px;">Your Store Scan Results</div>'
        f'<div style="font-family:Georgia,serif;font-size:26px;font-weight:700;color:#0A0E1A;letter-spacing:-0.01em;line-height:1;">{domain}</div>'
        f'</td>'
        f'<td align="right" style="vertical-align:bottom;padding-bottom:2px;">'
        f'<div style="border:1.5px solid {badge_color};padding:5px 12px;display:inline-block;">'
        f'<span style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:{badge_color};">{status_badge}</span>'
        f'</div></td></tr></table></td></tr>'

        # Score block
        f'<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px 32px;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td width="130" align="center" style="vertical-align:top;">'
        f'<table width="110" height="110" cellpadding="0" cellspacing="0" border="0" style="border:2px solid {score_color};margin:0 auto;">'
        f'<tr><td align="center" style="vertical-align:middle;background-color:#FFFFFF;">'
        f'<div style="font-family:Georgia,serif;font-size:58px;font-weight:700;color:{score_color};line-height:1;">{score}</div>'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;font-weight:600;letter-spacing:0.2em;color:#CCCCCC;text-transform:uppercase;margin-top:3px;">/ 100</div>'
        f'</td></tr></table>'
        f'<div style="margin-top:10px;text-align:center;">'
        f'<span style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:{score_color};border:1px solid {score_color};padding:4px 14px;display:inline-block;">{status_label}</span>'
        f'</div></td>'
        f'<td width="20">&nbsp;</td>'
        f'<td style="vertical-align:top;">'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#CCCCCC;margin-bottom:14px;">Scan Summary</div>'
        f'<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:18px;"><tr>'
        f'<td style="padding-right:28px;border-right:1px solid #E8E4DC;">'
        f'<div style="font-family:Georgia,serif;font-size:40px;font-weight:700;color:#0A0E1A;line-height:1;">{crits}</div>'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#AAAAAA;margin-top:4px;">Critical</div>'
        f'</td><td style="padding-left:28px;">'
        f'<div style="font-family:Georgia,serif;font-size:40px;font-weight:700;color:#0A0E1A;line-height:1;">{total}</div>'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#AAAAAA;margin-top:4px;">Total Issues</div>'
        f'</td></tr></table>'
        f'<div style="border-left:2px solid #E8E4DC;padding-left:14px;">'
        f'<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#888888;line-height:1.65;">'
        f'{crits} critical {crits_word} detected &mdash; the exact issue profile plaintiff scanners flag when building demand letter queues.'
        f'</div></div></td></tr></table></td></tr>'

        # Urgency band
        '<tr><td bgcolor="#FDF8F0" style="background-color:#FDF8F0;border-top:1px solid #F0E8D8;border-bottom:1px solid #F0E8D8;padding:24px 40px;border-left:4px solid #C9A84C;">'
        '<div style="font-family:Georgia,serif;font-size:18px;font-weight:700;color:#0A0E1A;line-height:1.45;margin-bottom:10px;">Most store owners don&rsquo;t find out until they receive a legal notice &mdash; often without warning.</div>'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#666666;line-height:1.75;">At that point, the cost is no longer optional. Typical settlement ranges in comparable cases run <span style="color:#0A0E1A;font-weight:700;">$25,000&ndash;$95,000</span> &mdash; resolved quietly, quickly, and without trial. These scans run continuously across thousands of stores. The only question is whether you see the results first, or they do.</div>'
        '</td></tr>'

        '<tr><td bgcolor="#FFFFFF" height="8" style="background-color:#FFFFFF;height:8px;font-size:0;">&nbsp;</td></tr>'

        # Category breakdown header
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:0 40px;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#C9A84C;padding:20px 0 12px;border-bottom:1px solid #E8E4DC;">Category Breakdown</div>'
        '</td></tr>'
    )

    html += cat_rows_html

    html += (
        '<tr><td bgcolor="#F2EFE9" height="2" style="background-color:#F2EFE9;height:2px;font-size:0;">&nbsp;</td></tr>'

        # Locked items
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#C9A84C;margin-bottom:6px;">What You&rsquo;re Seeing Here Is Only the Surface</div>'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#888888;line-height:1.6;margin-bottom:20px;">This summary does not include:</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;border-left:3px solid #C9A84C;">'
        '<tr><td bgcolor="#FDFCF9" style="background-color:#FDFCF9;padding:20px 24px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td style="padding-bottom:10px;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F512;&nbsp;&nbsp;Full 10-section legal-grade Defense Package PDF</td></tr>'
        '<tr><td style="padding:10px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F512;&nbsp;&nbsp;Step-by-step remediation code for every flagged issue</td></tr>'
        '<tr><td style="padding:10px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F512;&nbsp;&nbsp;Plaintiff simulation &mdash; exactly how a law firm scores your store</td></tr>'
        '<tr><td style="padding:10px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F512;&nbsp;&nbsp;SHA-256 tamper-proof Scan Receipt &mdash; your immutable evidence record</td></tr>'
        '<tr><td style="padding-top:10px;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F512;&nbsp;&nbsp;IDR Verified badge + weekly automated rescans with real-time alerts</td></tr>'
        '</table></td></tr></table></td></tr>'

        # Bridge copy
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<div style="font-family:Georgia,serif;font-size:19px;font-weight:700;color:#0A0E1A;line-height:1.4;margin-bottom:8px;">Most stores wait until they&rsquo;re forced to respond.</div>'
        '<div style="font-family:Georgia,serif;font-size:19px;color:#C9A84C;font-style:italic;line-height:1.4;margin-bottom:14px;">Founding members act before that moment.</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#777777;line-height:1.8;">The Defense Package doesn&rsquo;t just show you the issues &mdash; it gives you the documentation, proof, and positioning to protect your store if it&rsquo;s ever challenged.</div>'
        '</td></tr>'

        # CTA section
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:8px;">Founding Member Access</div>'
        '<div style="font-family:Georgia,serif;font-size:26px;font-weight:700;color:#0A0E1A;margin-bottom:4px;line-height:1.15;">Activate Your IDR Shield</div>'
        '<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#AAAAAA;margin-bottom:28px;">Lock in founding access. First 500 stores only.</div>'

        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:28px;"><tr>'
        '<td width="50%" style="vertical-align:top;padding-right:16px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td style="padding:8px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.4;"><span style="color:#C9A84C;font-family:Arial,sans-serif;font-size:11px;">&#x2713;</span>&nbsp; The 2026 Accessibility Shield &mdash; full digital book</td></tr>'
        '<tr><td style="padding:8px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.4;"><span style="color:#C9A84C;font-family:Arial,sans-serif;font-size:11px;">&#x2713;</span>&nbsp; 10-section legal-grade Defense Package PDF</td></tr>'
        '<tr><td style="padding:8px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.4;"><span style="color:#C9A84C;font-family:Arial,sans-serif;font-size:11px;">&#x2713;</span>&nbsp; SHA-256 Scan Receipt &mdash; cryptographic proof</td></tr>'
        '<tr><td style="padding-top:8px;font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.4;"><span style="color:#C9A84C;font-family:Arial,sans-serif;font-size:11px;">&#x2713;</span>&nbsp; IDR Registry entry &mdash; publicly verifiable</td></tr>'
        '</table></td>'
        '<td width="50%" style="vertical-align:top;padding-left:16px;border-left:1px solid #F0EDE8;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td style="padding:8px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.4;"><span style="color:#C9A84C;font-family:Arial,sans-serif;font-size:11px;">&#x2713;</span>&nbsp; IDR Verified badge for your store footer</td></tr>'
        '<tr><td style="padding:8px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.4;"><span style="color:#C9A84C;font-family:Arial,sans-serif;font-size:11px;">&#x2713;</span>&nbsp; Weekly automated rescans + real-time alerts</td></tr>'
        '<tr><td style="padding-top:8px;font-family:Georgia,serif;font-size:13px;line-height:1.4;"><span style="color:#C9A84C;font-family:Arial,sans-serif;font-size:11px;">&#x2713;</span>&nbsp; <strong style="color:#0A0E1A;">$29/month &mdash; locked permanently</strong><br><span style="color:#AAAAAA;font-size:12px;">for founding members</span></td></tr>'
        '</table></td>'
        '</tr></table>'

        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#FDFCF9;border:1px solid #E8E4DC;margin-bottom:20px;"><tr>'
        '<td style="padding:18px 24px;vertical-align:middle;">'
        '<span style="font-family:Georgia,serif;font-size:44px;font-weight:700;color:#C9A84C;line-height:1;">$97</span>'
        '<span style="font-family:Arial,Helvetica,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#CCCCCC;margin-left:10px;white-space:nowrap;">Founding Access &middot; First 500 Stores</span>'
        '</td>'
        '<td align="right" style="padding:18px 24px;vertical-align:middle;">'
        '<div style="font-family:Georgia,serif;font-size:11px;font-style:italic;color:#AAAAAA;text-align:right;line-height:1.6;">Standard price $127<br>after founding window closes</div>'
        '</td></tr></table>'

        f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td bgcolor="#C9A84C" align="center" style="background-color:#C9A84C;">'
        f'<a href="{GUMROAD_URL}" style="display:block;padding:18px 40px;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#FFFFFF;text-decoration:none;text-align:center;">ACTIVATE FOUNDING MEMBERSHIP &mdash; $97</a>'
        f'</td></tr></table>'
        '<div style="text-align:center;margin-top:10px;font-family:Arial,Helvetica,sans-serif;font-size:9px;color:#CCCCCC;letter-spacing:0.1em;">Limited to the first 500 stores &nbsp;&middot;&nbsp; 30 days free &nbsp;&middot;&nbsp; $29/month locked permanently</div>'
        '</td></tr>'

        # Registry
        f'<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:22px 40px;">'
        f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#AAAAAA;margin-bottom:8px;">Your Public Registry Record</div>'
        f'<a href="https://idrshield.com/verify/{domain}" style="font-family:\'Courier New\',Courier,monospace;font-size:12px;color:#8A6F2E;text-decoration:none;">https://idrshield.com/verify/{domain}</a>'
        f'<div style="margin-top:8px;font-family:Georgia,serif;font-size:11px;font-style:italic;color:#BBBBBB;">Publicly verifiable. Anyone can confirm your compliance record.</div>'
        f'<div style="margin-top:14px;padding-top:12px;border-top:1px solid #E8E4DC;font-family:\'Courier New\',Courier,monospace;font-size:9px;color:#CCCCCC;line-height:1.8;">RECEIPT &middot; {receipt_short} &nbsp;&nbsp; REGISTRY &middot; {registry_id} &nbsp;&nbsp; OPERATOR &middot; IDR_SCANNER_v1</div>'
        '</td></tr>'

        # Footer
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:18px 40px;border-top:1px solid #E8E4DC;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td>'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;color:#CCCCCC;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:6px;">Institute of Digital Remediation &nbsp;&middot;&nbsp; idrshield.com &nbsp;&middot;&nbsp; IDR-BRAND-2026-01</div>'
        '<div style="font-family:Georgia,serif;font-size:10.5px;font-style:italic;color:#CCCCCC;line-height:1.7;">Not a law firm. This is a compliance documentation system. Settlement ranges cited reflect publicly available case data and are not a prediction of any specific legal action.</div>'
        '<div style="margin-top:10px;font-family:Arial,Helvetica,sans-serif;font-size:8px;color:#DDDDDD;letter-spacing:0.06em;">'
        '<a href="https://idrshield.com/privacy" style="color:#CCCCCC;text-decoration:none;">Privacy Policy</a>'
        ' &nbsp;&middot;&nbsp; <a href="https://idrshield.com/terms" style="color:#CCCCCC;text-decoration:none;">Terms of Service</a>'
        ' &nbsp;&middot;&nbsp; <a href="mailto:hello@idrshield.com" style="color:#CCCCCC;text-decoration:none;">hello@idrshield.com</a>'
        '</div>'
        '</td>'
        '<td width="50" align="right" style="vertical-align:middle;">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 30 30">'
        '<circle cx="15" cy="15" r="14" fill="none" stroke="#E8E4DC" stroke-width="1"/>'
        '<text x="15" y="19" font-family="Georgia,serif" font-size="8" font-weight="700" fill="#DDDDDD" text-anchor="middle">IDR</text>'
        '</svg>'
        '</td></tr></table></td></tr>'

        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;height:4px;font-size:0;line-height:0;">&nbsp;</td></tr>'
        '</table></td></tr></table>'
        '</body></html>'
    )

    _send(email, subject, html)


def send_activation_receipt(email, receipt):
    domain       = receipt.get('domain', 'your store')
    score        = receipt.get('score', 0)
    registry_url = receipt.get('registry_url', f'https://idrshield.com/verify/{domain}')
    subject      = f'Welcome to IDR Shield \u2014 {domain} is now in the registry'
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="color-scheme" content="dark"></head>
<body style="margin:0;padding:0;background-color:#060A14;">
<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#060A14" style="background-color:#060A14;">
<tr><td align="center" bgcolor="#060A14" style="background-color:#060A14;padding:24px 16px;">
<table width="600" cellpadding="0" cellspacing="0" bgcolor="#0A0E1A" style="background-color:#0A0E1A;max-width:600px;width:100%;">
<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;">&nbsp;</td></tr>
<tr><td bgcolor="#08101F" style="background-color:#08101F;padding:28px 40px;text-align:center;">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#8A6F2E;margin-bottom:8px;">FOUNDING MEMBER CONFIRMED</div>
<div style="font-family:Georgia,serif;font-size:24px;font-weight:700;color:#F0E8D8;margin-bottom:5px;">You&#39;re in the registry.</div>
<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#4A3A2A;">{domain} is now an active IDR Shield member.</div>
</td></tr>
<tr><td bgcolor="#060E1C" style="background-color:#060E1C;padding:26px 40px;text-align:center;">
<div style="font-family:Georgia,serif;font-size:52px;font-weight:700;color:#C9A84C;line-height:1;">{score}</div>
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#2A1A08;margin-top:4px;">/ 100 &#8212; Your Baseline Score</div>
<div style="margin-top:20px;"><table cellpadding="0" cellspacing="0" border="0" align="center"><tr>
<td bgcolor="#C9A84C" style="background-color:#C9A84C;"><a href="{registry_url}" style="display:block;padding:12px 28px;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#060A14;text-decoration:none;">VIEW YOUR REGISTRY RECORD</a></td>
</tr></table></div></td></tr>
<tr><td bgcolor="#04080F" style="background-color:#04080F;padding:12px 40px;">
<div style="font-family:Georgia,serif;font-size:10px;font-style:italic;color:#0F0C06;">Not a law firm. Institute of Digital Remediation &middot; idrshield.com</div>
</td></tr>
<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;">&nbsp;</td></tr>
</table></td></tr></table></body></html>"""
    _send(email, subject, html)


def send_scan_alert(email, domain, score, new_issues):
    subject = f'New accessibility issues detected on {domain}'
    rows = ''.join(
        f'<tr><td bgcolor="#06101C" style="background-color:#06101C;padding:9px 0;border-bottom:1px solid #0F1A2A;font-family:Georgia,serif;font-size:12px;color:#4A3A2A;">{i}</td></tr>'
        for i in new_issues[:10]
    )
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="color-scheme" content="dark"></head>
<body style="margin:0;padding:0;background-color:#060A14;">
<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#060A14" style="background-color:#060A14;">
<tr><td align="center" bgcolor="#060A14" style="background-color:#060A14;padding:24px 16px;">
<table width="600" cellpadding="0" cellspacing="0" bgcolor="#0A0E1A" style="background-color:#0A0E1A;max-width:600px;width:100%;">
<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;">&nbsp;</td></tr>
<tr><td bgcolor="#08101F" style="background-color:#08101F;padding:24px 40px;">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#E63946;margin-bottom:7px;">SCAN ALERT</div>
<div style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#F0E8D8;margin-bottom:4px;">New issues detected on {domain}</div>
<div style="font-family:Georgia,serif;font-size:12px;color:#3A2A0A;">Current score: {score}/100</div>
</td></tr>
<tr><td bgcolor="#060E1C" style="background-color:#060E1C;padding:22px 40px;"><table width="100%" cellpadding="0" cellspacing="0">{rows}</table></td></tr>
<tr><td bgcolor="#08101F" style="background-color:#08101F;padding:20px 40px;text-align:center;">
<table cellpadding="0" cellspacing="0" align="center"><tr>
<td bgcolor="#C9A84C" style="background-color:#C9A84C;"><a href="https://idrshield.com/portal" style="display:block;padding:11px 26px;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#060A14;text-decoration:none;">VIEW IN MEMBER PORTAL</a></td>
</tr></table></td></tr>
<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;">&nbsp;</td></tr>
</table></td></tr></table></body></html>"""
    _send(email, subject, html)


def send_fix_confirmation_email(email, domain, categories, new_score):
    subject  = f'Remediation recorded \u2014 {domain}'
    cat_list = ', '.join(categories) if categories else 'General'
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="color-scheme" content="dark"></head>
<body style="margin:0;padding:0;background-color:#060A14;">
<table width="100%" cellpadding="0" cellspacing="0" bgcolor="#060A14" style="background-color:#060A14;">
<tr><td align="center" bgcolor="#060A14" style="background-color:#060A14;padding:24px 16px;">
<table width="600" cellpadding="0" cellspacing="0" bgcolor="#0A0E1A" style="background-color:#0A0E1A;max-width:600px;width:100%;">
<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;">&nbsp;</td></tr>
<tr><td bgcolor="#08101F" style="background-color:#08101F;padding:24px 40px;">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#52B788;margin-bottom:7px;">REMEDIATION CONFIRMED</div>
<div style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#F0E8D8;margin-bottom:4px;">Fix recorded for {domain}</div>
<div style="font-family:Georgia,serif;font-size:12px;color:#3A2A0A;">Categories: {cat_list}</div>
</td></tr>
<tr><td bgcolor="#060E1C" style="background-color:#060E1C;padding:26px 40px;text-align:center;">
<div style="font-family:Georgia,serif;font-size:52px;font-weight:700;color:#52B788;line-height:1;">{new_score}</div>
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#1A3A2A;margin-top:4px;">/ 100 &#8212; Updated Score</div>
<div style="margin-top:12px;font-family:Georgia,serif;font-size:12px;font-style:italic;color:#1A2A1A;">This remediation has been logged with a timestamp in your evidence record.</div>
</td></tr>
<tr><td bgcolor="#04080F" style="background-color:#04080F;padding:12px 40px;">
<div style="font-family:Georgia,serif;font-size:10px;font-style:italic;color:#0F0C06;">Not a law firm. Institute of Digital Remediation &middot; idrshield.com</div>
</td></tr>
<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;">&nbsp;</td></tr>
</table></td></tr></table></body></html>"""
    _send(email, subject, html)
