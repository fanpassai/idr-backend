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
    score       = sc.get('overall_score', 0)
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
        display_date = dt.strftime('%b %-d, %Y %H:%M UTC')
    except Exception:
        display_date = (timestamp[:16].replace('T', ' ') + ' UTC') if timestamp else ''

    if status == 'pass':
        score_color = '#52B788'; status_label = 'REGISTRY ELIGIBLE'; status_bg = '#0A1F14'
    elif status == 'warning':
        score_color = '#C9A84C'; status_label = 'MONITORING STATUS'; status_bg = '#1A1508'
    else:
        score_color = '#E63946'; status_label = 'REMEDIATION REQUIRED'; status_bg = '#1F0A0A'

    fail_label = 'PASS' if status == 'pass' else 'WARNING' if status == 'warning' else 'FAIL'

    if status == 'pass':
        subject = f'{domain} passed — {score}/100 \xb7 No critical violations'
    elif crits > 0:
        subject = f'Your store flagged {crits} critical ADA issue{"s" if crits != 1 else ""} \u2014 {domain}'
    else:
        subject = f'Your store scored {score}/100 on ADA accessibility \u2014 {domain}'

    if status == 'pass':
        score_context = 'No critical violations detected \u2014 currently eligible for Active registry status. Fewer than 20% of scanned stores reach this threshold.'
    elif crits > 0:
        score_context = f'{crits} critical violation{"s" if crits != 1 else ""} detected. This is exactly the issue profile automated plaintiff scanners flag when building demand letter queues.'
    else:
        score_context = f'{total} issues flagged across the five IDR audit categories \u2014 the same categories plaintiff firms prioritize.'

    if status == 'pass':
        urgency_block = (
            '<tr><td bgcolor="#0A1F14" style="background-color:#0A1F14;border-left:4px solid #52B788;padding:22px 40px 22px 36px;">'
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#52B788;margin-bottom:8px;">COMPLIANCE STATUS</div>'
            '<div style="font-family:Georgia,serif;font-size:15px;font-weight:700;color:#F0E8D8;line-height:1.4;margin-bottom:8px;">This store has no critical violations \u2014 currently eligible for Active registry status.</div>'
            '<div style="font-family:Georgia,serif;font-size:13px;color:#2A4A38;line-height:1.7;">Activating IDR Shield locks in this record with a SHA-256 signed receipt, weekly rescans, and a publicly verifiable registry entry.</div>'
            '</td></tr>'
        )
    else:
        urgency_block = (
            '<tr><td bgcolor="#1F0A0A" style="background-color:#1F0A0A;border-left:4px solid #CC3333;padding:22px 40px 22px 36px;">'
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#CC3333;margin-bottom:8px;">RISK ASSESSMENT</div>'
            '<div style="font-family:Georgia,serif;font-size:16px;font-weight:700;color:#F0E8D8;line-height:1.4;margin-bottom:10px;">Most store owners don&#39;t find out until they receive a legal notice &#8212; often without warning.</div>'
            '<div style="font-family:Georgia,serif;font-size:13px;color:#6A3A3A;line-height:1.75;">At that point, the cost is no longer optional. Typical settlement ranges in comparable cases run <span style="color:#F0E8D8;font-weight:700;">$25,000&#8211;$95,000</span> &#8212; resolved quietly, quickly, and without trial.</div>'
            '</td></tr>'
            '<tr><td bgcolor="#060E1C" style="background-color:#060E1C;padding:18px 40px;">'
            '<div style="font-family:Georgia,serif;font-size:13px;color:#4A3A2A;line-height:1.85;">These scans are not manual. Automated systems crawl thousands of stores every day &#8212; reading source code, flagging violations, and logging domain names before anyone picks up a phone.<br><br>'
            '<span style="color:#8A6F2E;font-style:italic;">Your store can be scanned at any time, by anyone. The only question is whether you see the results first &#8212; or they do.</span></div>'
            '</td></tr>'
        )

    def bar_color(s):
        return '#52B788' if s == 'pass' else '#C9A84C' if s == 'warning' else '#E63946'

    def issue_label(cat):
        issues = cat.get('issues', [])
        s = cat.get('status', 'warning')
        if s == 'pass' or not issues:
            return '<span style="font-family:Arial,Helvetica,sans-serif;font-size:9px;font-weight:700;color:#52B788;">&#x2713; Clean</span>'
        cc = sum(1 for i in issues if i.get('severity') == 'critical')
        cnt = len(issues)
        label = f'{cc} critical' if cc else f'{cnt} issue{"s" if cnt != 1 else ""}'
        col   = '#E63946' if cc else '#C9A84C'
        return f'<span style="font-family:Arial,Helvetica,sans-serif;font-size:9px;font-weight:700;color:{col};">{label}</span>'

    cat_rows = ''
    for i, cat in enumerate(cats):
        bg  = '#08101F' if i % 2 == 0 else '#060E1C'
        s   = cat.get('status', 'warning')
        pct = max(3, cat.get('score', 0))
        bc  = bar_color(s)
        w   = int(pct * 1.6)
        cat_rows += (
            f'<tr><td bgcolor="{bg}" style="background-color:{bg};padding:11px 40px;border-bottom:1px solid #0F1A2A;">'
            '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
            '<td style="vertical-align:middle;">'
            f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#4A3A2A;margin-bottom:6px;">{cat.get("name","")}</div>'
            '<table cellpadding="0" cellspacing="0" border="0"><tr>'
            '<td bgcolor="#1A2030" width="160" height="3" style="background-color:#1A2030;width:160px;height:3px;font-size:0;">'
            f'<table cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td bgcolor="{bc}" width="{w}" height="3" style="background-color:{bc};width:{w}px;height:3px;font-size:0;">&nbsp;</td>'
            '</tr></table></td></tr></table></td>'
            f'<td align="right" style="vertical-align:middle;white-space:nowrap;">{issue_label(cat)}</td>'
            '</tr></table></td></tr>'
        )

    locked_items = [
        'Full 10-section legal-grade Defense Package PDF',
        'Step-by-step remediation code for every flagged issue',
        'Plaintiff simulation &#8212; exactly how a law firm scores your store',
        'Legal positioning documentation for demand letter response',
        'SHA-256 tamper-proof Scan Receipt &#8212; your immutable evidence record',
        'IDR Verified badge + weekly automated rescans with real-time alerts',
    ]
    locked_html = ''
    for i, item in enumerate(locked_items):
        mb = '0' if i == len(locked_items)-1 else '9px'
        locked_html += (
            f'<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:{mb};">'
            '<tr><td width="20" style="vertical-align:top;font-size:12px;">&#x1F512;</td>'
            f'<td style="font-family:Georgia,serif;font-size:13px;color:#6A5A3A;line-height:1.5;">{item}</td></tr></table>'
        )

    def ben_row(text, last=False):
        b = '' if last else 'border-bottom:1px solid #1A2030;'
        return (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="padding:7px 0;{b}">'
            '<tr><td width="16" style="vertical-align:top;padding-top:2px;font-family:Arial,Helvetica,sans-serif;font-size:10px;color:#C9A84C;">&#x2713;</td>'
            f'<td style="font-family:Georgia,serif;font-size:12px;color:#6A5A3A;line-height:1.45;padding-left:6px;">{text}</td></tr></table>'
        )

    bl = ['The 2026 Accessibility Shield &#8212; full digital book',
          '10-section legal-grade Defense Package PDF',
          'SHA-256 Scan Receipt &#8212; cryptographic compliance proof',
          'IDR Registry entry &#8212; publicly verifiable']
    br = ['IDR Verified badge for your store footer',
          'Weekly automated rescans + real-time alerts',
          '<strong style="color:#C9A84C;">$29/month &#8212; locked permanently</strong>']

    benefits_left  = ''.join(ben_row(b, i == len(bl)-1) for i, b in enumerate(bl))
    benefits_right = ''.join(ben_row(b, i == len(br)-1) for i, b in enumerate(br))

    html = f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="color-scheme" content="dark">
<meta name="supported-color-schemes" content="dark">
<title>{subject}</title>
<style>
body{{margin:0;padding:0;background-color:#060A14;}}
@media only screen and (max-width:600px){{
  .w600{{width:100%!important;}}
  .px20{{padding-left:20px!important;padding-right:20px!important;}}
}}
</style>
</head>
<body style="margin:0;padding:0;background-color:#060A14;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#060A14" style="background-color:#060A14;">
<tr><td align="center" bgcolor="#060A14" style="background-color:#060A14;padding:24px 16px;">
<table class="w600" width="600" cellpadding="0" cellspacing="0" border="0" bgcolor="#0A0E1A" style="background-color:#0A0E1A;max-width:600px;width:100%;">

<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;line-height:0;">&nbsp;</td></tr>

<tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:20px 40px 16px;" class="px20">
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td style="vertical-align:middle;">
<table cellpadding="0" cellspacing="0" border="0"><tr>
<td width="36" height="36" style="width:36px;height:36px;border:1px solid #8A6F2E;font-family:Georgia,serif;font-size:9px;font-weight:700;color:#C9A84C;text-align:center;vertical-align:middle;line-height:36px;padding:0;">IDR</td>
<td width="12">&nbsp;</td>
<td><div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#C9A84C;">INSTITUTE OF DIGITAL REMEDIATION</div>
<div style="font-family:Georgia,serif;font-size:10px;font-style:italic;color:#8A6F2E;margin-top:2px;">IDR Protocol Series &middot; 2026 Edition</div></td>
</tr></table></td>
<td align="right" style="vertical-align:middle;">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;letter-spacing:0.16em;text-transform:uppercase;color:#2A1A08;">SCAN RECEIPT</div>
<div style="font-family:'Courier New',monospace;font-size:8px;color:#1A1208;margin-top:2px;">{display_date}</div>
</td></tr></table>
</td></tr>

<tr><td bgcolor="#1A1208" height="1" style="background-color:#1A1208;font-size:0;line-height:0;">&nbsp;</td></tr>

<tr><td bgcolor="#060E1C" style="background-color:#060E1C;padding:16px 40px 14px;" class="px20">
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td><div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#2A1A08;margin-bottom:6px;">YOUR STORE SCAN RESULTS</div>
<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#F0E8D8;">{domain}</div></td>
<td align="right" style="vertical-align:bottom;">
<table cellpadding="0" cellspacing="0" border="0"><tr>
<td bgcolor="{status_bg}" style="background-color:{status_bg};border:1px solid {score_color};padding:5px 10px;">
<span style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:{score_color};">{status_label}</span>
</td></tr></table>
</td></tr></table>
</td></tr>

<tr><td bgcolor="#0A1628" style="background-color:#0A1628;padding:28px 40px 24px;" class="px20">
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td width="136" align="center" style="vertical-align:top;">
<table cellpadding="0" cellspacing="0" border="0" width="124" align="center">
<tr><td width="124" bgcolor="#060E1C" style="background-color:#060E1C;border:2px solid {score_color};padding:14px 6px 10px;text-align:center;vertical-align:middle;">
<div style="font-family:Georgia,serif;font-size:58px;font-weight:700;color:{score_color};line-height:1;">{score}</div>
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#2A1A08;margin-top:4px;">/ 100</div>
</td></tr>
<tr><td bgcolor="{status_bg}" align="center" style="background-color:{status_bg};border:2px solid {score_color};border-top:none;padding:5px 6px;">
<span style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:{score_color};">{fail_label}</span>
</td></tr></table>
</td>
<td width="18">&nbsp;</td>
<td style="vertical-align:top;">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#2A1A08;margin-bottom:10px;">SCAN SUMMARY</div>
<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:14px;"><tr>
<td style="padding-right:20px;border-right:1px solid #1A2030;vertical-align:bottom;">
<div style="font-family:Georgia,serif;font-size:38px;font-weight:700;color:#E63946;line-height:1;">{crits}</div>
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#2A1A08;margin-top:3px;">Critical</div>
</td>
<td style="padding-left:20px;vertical-align:bottom;">
<div style="font-family:Georgia,serif;font-size:38px;font-weight:700;color:#C9A84C;line-height:1;">{total}</div>
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#2A1A08;margin-top:3px;">Total Issues</div>
</td></tr></table>
<table cellpadding="0" cellspacing="0" border="0"><tr>
<td width="3" bgcolor="#3A2A0A" style="background-color:#3A2A0A;">&nbsp;</td>
<td width="10">&nbsp;</td>
<td><div style="font-family:Georgia,serif;font-size:12px;font-style:italic;color:#5A4A2A;line-height:1.6;">{score_context}</div></td>
</tr></table>
</td></tr></table>
</td></tr>

{urgency_block}

<tr><td bgcolor="#1A2030" height="1" style="background-color:#1A2030;font-size:0;line-height:0;">&nbsp;</td></tr>

<tr><td bgcolor="#08101F" style="background-color:#08101F;padding:18px 40px 2px;" class="px20">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#4A3010;">CATEGORY BREAKDOWN</div>
</td></tr>

{cat_rows}

<tr><td bgcolor="#1A2030" height="1" style="background-color:#1A2030;font-size:0;line-height:0;">&nbsp;</td></tr>

<tr><td bgcolor="#060E1C" style="background-color:#060E1C;padding:24px 40px;" class="px20">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.24em;text-transform:uppercase;color:#2A1A08;margin-bottom:5px;">WHAT YOU'RE SEEING IS ONLY THE SURFACE</div>
<div style="font-family:Georgia,serif;font-size:12px;color:#2A1A08;margin-bottom:16px;">This summary does not include:</div>
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td width="3" bgcolor="#3A2A0A" style="background-color:#3A2A0A;">&nbsp;</td>
<td bgcolor="#0D1526" style="background-color:#0D1526;padding:18px 20px;">{locked_html}</td>
</tr></table>
</td></tr>

<tr><td bgcolor="#08101F" style="background-color:#08101F;padding:20px 40px;" class="px20">
<div style="font-family:Georgia,serif;font-size:16px;font-weight:700;color:#F0E8D8;line-height:1.4;margin-bottom:8px;">Most stores wait until they&#39;re forced to respond.<br><span style="color:#C9A84C;font-style:italic;">Founding members act before that moment.</span></div>
<div style="font-family:Georgia,serif;font-size:12px;color:#2A1A08;line-height:1.7;">The Defense Package gives you the documentation, proof, and positioning to protect your store if it&#39;s ever challenged.</div>
</td></tr>

<tr><td bgcolor="#0D1A2E" style="background-color:#0D1A2E;padding:28px 40px 24px;" class="px20">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#4A3010;margin-bottom:6px;">FOUNDING MEMBER ACCESS</div>
<div style="font-family:Georgia,serif;font-size:23px;font-weight:700;color:#F0E8D8;margin-bottom:4px;">Activate Your IDR Shield</div>
<div style="font-family:Georgia,serif;font-size:12px;font-style:italic;color:#2A1A08;margin-bottom:20px;">Lock in founding access. First 500 stores only.</div>
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:18px;"><tr>
<td width="48%" style="vertical-align:top;padding-right:10px;">{benefits_left}</td>
<td width="4%" bgcolor="#1A2030" style="background-color:#1A2030;">&nbsp;</td>
<td width="48%" style="vertical-align:top;padding-left:10px;">{benefits_right}</td>
</tr></table>
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:16px;"><tr>
<td bgcolor="#0A0E1A" style="background-color:#0A0E1A;border:1px solid #2A1A08;padding:14px 18px;">
<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td><div style="font-family:Georgia,serif;font-size:46px;font-weight:700;color:#C9A84C;line-height:1;">$97</div>
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#2A1A08;margin-top:3px;">Founding Access &middot; First 500 Stores &middot; Standard $127</div></td>
<td align="right"><div style="font-family:Georgia,serif;font-size:11px;font-style:italic;color:#1A1208;text-align:right;line-height:1.7;">For most merchants,<br>one settlement costs<br>many times more.</div></td>
</tr></table>
</td></tr></table>
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:10px;"><tr>
<td bgcolor="#C9A84C" align="center" style="background-color:#C9A84C;">
<a href="{GUMROAD_URL}?ref={receipt_id}" style="display:block;padding:15px 40px;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#060A14;text-decoration:none;">ACTIVATE FOUNDING MEMBERSHIP &mdash; $97</a>
</td></tr></table>
<div style="text-align:center;font-family:Arial,Helvetica,sans-serif;font-size:7px;color:#1A1208;letter-spacing:0.1em;">First 500 stores only &nbsp;&middot;&nbsp; 30 days free &nbsp;&middot;&nbsp; $29/month locked permanently</div>
</td></tr>

<tr><td bgcolor="#060E1C" style="background-color:#060E1C;padding:18px 40px;" class="px20">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#1A1208;margin-bottom:6px;">YOUR PUBLIC REGISTRY RECORD</div>
<a href="https://idrshield.com/verify/{domain}" style="font-family:'Courier New',monospace;font-size:11px;color:#8A6F2E;text-decoration:none;">https://idrshield.com/verify/{domain}</a>
<div style="margin-top:8px;font-family:'Courier New',monospace;font-size:8px;color:#1A1208;line-height:1.8;">RECEIPT &middot; {receipt_id[:18]}&#8230;<br>REGISTRY &middot; {registry_id}<br>PROTOCOL &middot; IDR-BRAND-2026-01</div>
</td></tr>

<tr><td bgcolor="#04080F" style="background-color:#04080F;padding:12px 40px;" class="px20">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;color:#0F0C06;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:4px;">Institute of Digital Remediation &middot; idrshield.com</div>
<div style="font-family:Georgia,serif;font-size:10px;font-style:italic;color:#080604;line-height:1.7;">Not a law firm. This is a compliance documentation system. Settlement ranges cited reflect publicly available case data and are not a prediction of any specific legal action.</div>
</td></tr>

<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;line-height:0;">&nbsp;</td></tr>

</table></td></tr></table>
</body></html>"""

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
