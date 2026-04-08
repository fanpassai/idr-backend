"""
IDR Shield — emailer.py
All transactional email via SendGrid.
Design rules: dark navy bg, one status accent, white text. No multicolor chaos.
Email-safe: solid hex on every bgcolor attr, no rgba/gradients on backgrounds.
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

    # ── Display date ──
    try:
        from datetime import datetime
        dt = datetime.strptime(timestamp[:19], '%Y-%m-%dT%H:%M:%S')
        display_date = dt.strftime('%b %-d, %Y · %H:%M UTC')
    except Exception:
        display_date = (timestamp[:16].replace('T', ' ') + ' UTC') if timestamp else ''

    # ── ONE accent color based on status. That's it. ──
    if status == 'pass':
        accent      = '#52B788'   # green
        status_label = 'REGISTRY ELIGIBLE'
    elif status == 'warning':
        accent      = '#C9A84C'   # gold
        status_label = 'MONITORING STATUS'
    else:
        accent      = '#E05252'   # red
        status_label = 'REMEDIATION REQUIRED'

    # ── Subject ──
    if status == 'pass':
        subject = f'{domain} passed — {score}/100 · No critical violations'
    elif crits > 0:
        subject = f'Your store flagged {crits} critical ADA issue{"s" if crits != 1 else ""} — {domain}'
    else:
        subject = f'Your store scored {score}/100 on ADA accessibility — {domain}'

    # ── Category rows ──
    cat_rows = ''
    for i, cat in enumerate(cats):
        bg = '#0D1526' if i % 2 == 0 else '#0A1020'
        s  = cat.get('status', 'warning')
        bar_w = max(4, int(cat.get('score', 0) * 1.4))  # scale to ~140px max
        bar_color = '#52B788' if s == 'pass' else accent

        issues = cat.get('issues', [])
        if s == 'pass' or not issues:
            issue_label = f'<span style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:#52B788;">&#x2713; Clean</span>'
        else:
            crit_n = sum(1 for x in issues if x.get('severity') == 'critical')
            n = crit_n if crit_n else len(issues)
            lbl = f'{n} critical' if crit_n else f'{n} issue{"s" if n != 1 else ""}'
            issue_label = f'<span style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:{accent};">{lbl}</span>'

        cat_rows += (
            f'<tr><td bgcolor="{bg}" style="background-color:{bg};padding:12px 36px;border-bottom:1px solid #0A1020;">'
            '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
            '<td style="vertical-align:middle;">'
            f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:9px;font-weight:700;'
            f'letter-spacing:0.12em;text-transform:uppercase;color:#8A9AAA;margin-bottom:7px;">{cat.get("name","")}</div>'
            '<table cellpadding="0" cellspacing="0" border="0"><tr>'
            '<td bgcolor="#1A2535" width="140" height="3" style="background-color:#1A2535;width:140px;height:3px;font-size:0;line-height:0;">'
            f'<table cellpadding="0" cellspacing="0" border="0"><tr>'
            f'<td bgcolor="{bar_color}" width="{bar_w}" height="3" style="background-color:{bar_color};width:{bar_w}px;height:3px;font-size:0;line-height:0;">&nbsp;</td>'
            '</tr></table></td></tr></table>'
            '</td>'
            f'<td align="right" style="vertical-align:middle;white-space:nowrap;">{issue_label}</td>'
            '</tr></table></td></tr>'
        )

    # ── Urgency / compliance block ──
    if status == 'pass':
        urgency = (
            '<tr><td bgcolor="#0A1A12" style="background-color:#0A1A12;padding:24px 36px;border-left:3px solid #52B788;">'
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#52B788;margin-bottom:10px;">COMPLIANCE STATUS</div>'
            '<div style="font-family:Georgia,serif;font-size:16px;font-weight:700;color:#E8F0EC;line-height:1.5;margin-bottom:8px;">This store has no critical violations — currently eligible for Active registry status.</div>'
            '<div style="font-family:Georgia,serif;font-size:13px;color:#6A9A7A;line-height:1.65;">Fewer than 20% of scanned stores reach this threshold. Activating IDR Shield locks in this record with weekly automated rescans and a publicly verifiable registry entry.</div>'
            '</td></tr>'
        )
    else:
        urgency = (
            '<tr><td bgcolor="#160808" style="background-color:#160808;padding:24px 36px;border-left:3px solid #E05252;">'
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#E05252;margin-bottom:10px;">RISK ASSESSMENT</div>'
            '<div style="font-family:Georgia,serif;font-size:16px;font-weight:700;color:#F0E8E8;line-height:1.5;margin-bottom:10px;">Most store owners don\'t find out until they receive a legal notice — often without warning.</div>'
            '<div style="font-family:Georgia,serif;font-size:13px;color:#9A7070;line-height:1.65;">At that point, the cost is no longer optional. Typical settlement ranges run <span style="color:#F0E8E8;font-weight:700;">$25,000–$95,000</span> — resolved quietly, quickly, and without trial. These scans run continuously. Your store can be scanned at any time, by anyone.</div>'
            '</td></tr>'
        )

    # ── Benefits ──
    benefits = [
        'The 2026 Accessibility Shield &#8212; full digital book',
        '10-section legal-grade Defense Package PDF',
        'SHA-256 Scan Receipt &#8212; cryptographic compliance proof',
        'IDR Registry entry &#8212; publicly verifiable',
        'IDR Verified badge for your store footer',
        'Weekly automated rescans + real-time alerts',
    ]
    ben_rows = ''.join(
        f'<tr><td bgcolor="#0D1526" style="background-color:#0D1526;padding:10px 0;border-bottom:1px solid #0A1020;">'
        f'<table cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td width="20" style="font-family:Arial,Helvetica,sans-serif;font-size:10px;color:{accent};vertical-align:top;padding-top:2px;">&#x2713;</td>'
        f'<td style="font-family:Georgia,serif;font-size:13px;color:#A0B0C0;line-height:1.45;padding-left:6px;">{b}</td>'
        f'</tr></table></td></tr>'
        for b in benefits
    )

    gumroad_link = f'{GUMROAD_URL}?ref={receipt_id}'


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
            '<tr>'
            '<td width="20" style="vertical-align:top;padding-top:2px;font-size:12px;">&#x1F512;</td>'
            f'<td style="font-family:Georgia,serif;font-size:13px;color:#6A7A8A;line-height:1.5;">{item}</td>'
            '</tr></table>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#060A14;">

<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#060A14" style="background-color:#060A14;">
<tr><td align="center" style="padding:28px 16px;" bgcolor="#060A14">

<table width="580" cellpadding="0" cellspacing="0" border="0" style="max-width:580px;width:100%;">

  <!-- GOLD TOP BAR -->
  <tr><td bgcolor="#C9A84C" height="3" style="background-color:#C9A84C;height:3px;font-size:0;line-height:0;">&nbsp;</td></tr>

  <!-- HEADER -->
  <tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:20px 36px 18px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td style="vertical-align:middle;">
          <table cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td width="34" height="34" bgcolor="#0A0E1A"
                  style="width:34px;height:34px;border:1.5px solid #8A6F2E;border-radius:17px;
                         font-family:Georgia,serif;font-size:9px;font-weight:700;
                         color:#C9A84C;text-align:center;line-height:34px;background-color:#0A0E1A;">IDR</td>
              <td width="10">&nbsp;</td>
              <td style="vertical-align:middle;">
                <div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;font-weight:700;
                             letter-spacing:0.2em;text-transform:uppercase;color:#C9A84C;">INSTITUTE OF DIGITAL REMEDIATION</div>
                <div style="font-family:Georgia,serif;font-size:10px;font-style:italic;color:#6A5A30;margin-top:2px;">IDR Protocol Series &middot; 2026 Edition</div>
              </td>
            </tr>
          </table>
        </td>
        <td align="right" style="vertical-align:middle;">
          <div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;letter-spacing:0.16em;text-transform:uppercase;color:#3A3020;">SCAN RECEIPT</div>
          <div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;color:#2A2518;margin-top:3px;">{display_date}</div>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- THIN DIVIDER -->
  <tr><td bgcolor="#1A1A1A" height="1" style="background-color:#1A1A1A;height:1px;font-size:0;line-height:0;">&nbsp;</td></tr>

  <!-- DOMAIN BANNER -->
  <tr><td bgcolor="#0D1120" style="background-color:#0D1120;padding:18px 36px 16px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <td style="vertical-align:middle;">
          <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                       letter-spacing:0.28em;text-transform:uppercase;color:#3A3A4A;margin-bottom:6px;">YOUR STORE SCAN RESULTS</div>
          <div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#E8EAF0;">{domain}</div>
        </td>
        <td align="right" style="vertical-align:middle;">
          <table cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td bgcolor="#0A0E1A" style="background-color:#0A0E1A;border:1px solid {accent};padding:5px 12px;">
                <span style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;
                              letter-spacing:0.16em;text-transform:uppercase;color:{accent};">{status_label}</span>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- SCORE BLOCK -->
  <tr><td bgcolor="#0A1020" style="background-color:#0A1020;padding:32px 36px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <!-- Score box -->
        <td width="130" align="center" style="vertical-align:top;">
          <table cellpadding="0" cellspacing="0" border="0" width="110"
                 style="border:2px solid {accent};">
            <tr>
              <td width="110" height="110" bgcolor="#0A0E1A" align="center"
                  style="background-color:#0A0E1A;width:110px;height:110px;vertical-align:middle;text-align:center;">
                <div style="font-family:Georgia,serif;font-size:52px;font-weight:700;
                             color:{accent};line-height:1;">{score}</div>
                <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                             letter-spacing:0.18em;color:#2A2A3A;text-transform:uppercase;margin-top:4px;">/ 100</div>
              </td>
            </tr>
          </table>
          <table cellpadding="0" cellspacing="0" border="0" style="margin-top:10px;">
            <tr>
              <td bgcolor="#0A0E1A" style="background-color:#0A0E1A;border:1px solid {accent};padding:4px 14px;">
                <span style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                              letter-spacing:0.16em;text-transform:uppercase;color:{accent};">
                  {"PASS" if status == "pass" else "WARNING" if status == "warning" else "FAIL"}
                </span>
              </td>
            </tr>
          </table>
        </td>

        <td width="20">&nbsp;</td>

        <!-- Stats -->
        <td style="vertical-align:top;">
          <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                       letter-spacing:0.24em;text-transform:uppercase;color:#3A3A4A;margin-bottom:12px;">SCAN SUMMARY</div>
          <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:16px;">
            <tr>
              <td style="padding-right:24px;">
                <div style="font-family:Georgia,serif;font-size:36px;font-weight:700;
                             color:#E8EAF0;line-height:1;">{crits}</div>
                <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                             letter-spacing:0.14em;text-transform:uppercase;color:#3A3A4A;margin-top:3px;">Critical</div>
              </td>
              <td style="padding-left:24px;border-left:1px solid #1A2030;">
                <div style="font-family:Georgia,serif;font-size:36px;font-weight:700;
                             color:#E8EAF0;line-height:1;">{total}</div>
                <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                             letter-spacing:0.14em;text-transform:uppercase;color:#3A3A4A;margin-top:3px;">Total Issues</div>
              </td>
            </tr>
          </table>
          <div style="border-left:2px solid #1A2535;padding-left:12px;">
            <div style="font-family:Georgia,serif;font-size:12px;font-style:italic;
                         color:#4A5060;line-height:1.6;">
              {'No critical violations detected — currently eligible for Active registry status. Fewer than 20% of scanned stores reach this threshold.' if status == 'pass' else f'{crits} critical violation{"s" if crits != 1 else ""} detected. This is the issue profile automated plaintiff scanners flag when building demand letter queues.' if crits > 0 else f'{total} issues flagged across the five IDR audit categories — the same categories plaintiff firms prioritize.'}
            </div>
          </div>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- URGENCY BLOCK -->
  {urgency}

  <!-- DIVIDER -->
  <tr><td bgcolor="#1A1A2A" height="1" style="background-color:#1A1A2A;height:1px;font-size:0;line-height:0;">&nbsp;</td></tr>

  <!-- CATEGORY BREAKDOWN -->
  <tr><td bgcolor="#080C18" style="background-color:#080C18;padding:20px 36px 0;">
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                 letter-spacing:0.28em;text-transform:uppercase;color:#2A2A38;">CATEGORY BREAKDOWN</div>
  </td></tr>
  {cat_rows}

  <!-- DIVIDER -->
  <tr><td bgcolor="#1A1A2A" height="1" style="background-color:#1A1A2A;height:1px;font-size:0;line-height:0;">&nbsp;</td></tr>

  <!-- SURFACE / LOCKED ITEMS -->
  <tr><td bgcolor="#080C18" style="background-color:#080C18;padding:28px 36px;">
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                 letter-spacing:0.26em;text-transform:uppercase;color:#2A2A38;margin-bottom:6px;">WHAT YOU'RE SEEING HERE IS ONLY THE SURFACE</div>
    <div style="font-family:Georgia,serif;font-size:13px;color:#3A3A4A;margin-bottom:18px;line-height:1.5;">This summary does not include:</div>
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           bgcolor="#0D1526" style="background-color:#0D1526;border-left:3px solid #C9A84C;">
      <tr><td bgcolor="#0D1526" style="background-color:#0D1526;padding:20px 24px;">
        {locked_html}
      </td></tr>
    </table>
  </td></tr>

  <!-- BRIDGE -->
  <tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:24px 36px;border-top:1px solid #1A1A2A;">
    <div style="font-family:Georgia,serif;font-size:17px;font-weight:700;
                 color:#E8EAF0;line-height:1.4;margin-bottom:10px;">
      Most stores wait until they're forced to respond.<br>
      <span style="color:{accent};font-style:italic;">Founding members act before that moment.</span>
    </div>
    <div style="font-family:Georgia,serif;font-size:13px;color:#3A4050;line-height:1.75;">
      The Defense Package gives you the documentation, proof, and positioning to protect your store if it's ever challenged.
    </div>
  </td></tr>

  <!-- FOUNDING CTA -->
  <tr><td bgcolor="#0D1120" style="background-color:#0D1120;padding:32px 36px;border-top:1px solid #1A2030;">
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                 letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:8px;">FOUNDING MEMBER ACCESS</div>
    <div style="font-family:Georgia,serif;font-size:24px;font-weight:700;color:#E8EAF0;margin-bottom:4px;">Activate Your IDR Shield</div>
    <div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#3A3A4A;margin-bottom:24px;">Lock in founding access. First 500 stores only.</div>

    <!-- Benefits -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           bgcolor="#080C18" style="background-color:#080C18;margin-bottom:24px;">
      <tr><td bgcolor="#080C18" style="background-color:#080C18;padding:4px 0;">
        {ben_rows}
      </td></tr>
    </table>

    <!-- Price + CTA -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           bgcolor="#0A0E1A" style="background-color:#0A0E1A;border:1px solid #2A2010;margin-bottom:20px;">
      <tr>
        <td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:16px 24px;vertical-align:middle;">
          <div style="font-family:Georgia,serif;font-size:40px;font-weight:700;color:#C9A84C;line-height:1;">$97</div>
          <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#3A2A10;margin-top:4px;">
            Founding Access &middot; First 500 Stores &middot; Standard $127
          </div>
        </td>
        <td bgcolor="#0A0E1A" align="right" style="background-color:#0A0E1A;padding:16px 24px;vertical-align:middle;">
          <div style="font-family:Georgia,serif;font-size:11px;font-style:italic;color:#2A2A38;line-height:1.6;text-align:right;">
            One settlement conversation<br>costs many times more<br>than this protocol.
          </div>
        </td>
      </tr>
    </table>

    <!-- Button -->
    <table cellpadding="0" cellspacing="0" border="0" width="100%">
      <tr>
        <td bgcolor="#C9A84C" align="center" style="background-color:#C9A84C;">
          <a href="{gumroad_link}"
             style="display:block;padding:16px 36px;font-family:Arial,Helvetica,sans-serif;
                     font-size:11px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;
                     color:#060A14;text-decoration:none;text-align:center;">
            ACTIVATE FOUNDING MEMBERSHIP &mdash; $97
          </a>
        </td>
      </tr>
    </table>
    <div style="text-align:center;margin-top:10px;font-family:Arial,Helvetica,sans-serif;
                 font-size:8px;color:#2A2010;letter-spacing:0.1em;">
      Limited to the first 500 stores &nbsp;&middot;&nbsp; 30 days free &nbsp;&middot;&nbsp; $29/month locked permanently
    </div>
  </td></tr>

  <!-- REGISTRY -->
  <tr><td bgcolor="#060A14" style="background-color:#060A14;padding:20px 36px;border-top:1px solid #1A1A2A;">
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                 letter-spacing:0.22em;text-transform:uppercase;color:#2A2A38;margin-bottom:7px;">
      YOUR PUBLIC REGISTRY RECORD
    </div>
    <a href="https://idrshield.com/verify/{domain}"
       style="font-family:Arial,Helvetica,sans-serif;font-size:11px;
               color:#8A6F2E;text-decoration:none;">
      https://idrshield.com/verify/{domain}
    </a>
    <div style="margin-top:10px;font-family:Arial,Helvetica,sans-serif;font-size:8px;color:#1A1A28;line-height:1.8;">
      RECEIPT &middot; {receipt_id[:20]}&#8230; &nbsp;&nbsp; REGISTRY &middot; {registry_id}
    </div>
  </td></tr>

  <!-- FOOTER -->
  <tr><td bgcolor="#040609" style="background-color:#040609;padding:16px 36px;border-top:1px solid #0A0A14;">
    <div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;color:#1A1A28;
                 letter-spacing:0.12em;text-transform:uppercase;margin-bottom:6px;">
      Institute of Digital Remediation &middot; idrshield.com &middot; IDR-BRAND-2026-01
    </div>
    <div style="font-family:Georgia,serif;font-size:10px;font-style:italic;color:#1A1A28;line-height:1.65;">
      Not a law firm. This is a compliance documentation system.
      Settlement ranges cited reflect publicly available case data
      and are not a prediction of any specific legal action.
    </div>
  </td></tr>

  <!-- GOLD BOTTOM BAR -->
  <tr><td bgcolor="#C9A84C" height="3" style="background-color:#C9A84C;height:3px;font-size:0;line-height:0;">&nbsp;</td></tr>

</table>

</td></tr>
</table>
</body>
</html>"""

    _send(email, subject, html)


def send_activation_receipt(email, receipt):
    domain       = receipt.get('domain', 'your store')
    score        = receipt.get('score', 0)
    registry_url = receipt.get('registry_url', f'https://idrshield.com/verify/{domain}')
    subject      = f'Welcome to IDR Shield — {domain} is now in the registry'
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background-color:#060A14;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#060A14">
<tr><td align="center" style="padding:28px 16px;" bgcolor="#060A14">
<table width="580" cellpadding="0" cellspacing="0" border="0" style="max-width:580px;width:100%;">
  <tr><td bgcolor="#C9A84C" height="3" style="background-color:#C9A84C;height:3px;font-size:0;">&nbsp;</td></tr>
  <tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:28px 36px;text-align:center;">
    <div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:8px;">FOUNDING MEMBER CONFIRMED</div>
    <div style="font-family:Georgia,serif;font-size:24px;font-weight:700;color:#E8EAF0;margin-bottom:4px;">You're in the registry.</div>
    <div style="font-family:Georgia,serif;font-size:14px;font-style:italic;color:#3A3A4A;">{domain} is now an active IDR Shield member.</div>
  </td></tr>
  <tr><td bgcolor="#0D1120" style="background-color:#0D1120;padding:28px 36px;text-align:center;">
    <div style="font-family:Georgia,serif;font-size:48px;font-weight:700;color:#C9A84C;line-height:1;">{score}</div>
    <div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#3A2A10;margin-top:4px;">/ 100 — Baseline Score</div>
    <table cellpadding="0" cellspacing="0" border="0" style="margin:20px auto 0;">
      <tr><td bgcolor="#C9A84C" style="background-color:#C9A84C;">
        <a href="{registry_url}" style="display:block;padding:13px 32px;font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#060A14;text-decoration:none;">VIEW YOUR REGISTRY RECORD</a>
      </td></tr>
    </table>
  </td></tr>
  <tr><td bgcolor="#040609" style="background-color:#040609;padding:14px 36px;border-top:1px solid #0A0A14;">
    <div style="font-family:Georgia,serif;font-size:10px;font-style:italic;color:#1A1A28;line-height:1.65;">Not a law firm. Institute of Digital Remediation &middot; idrshield.com</div>
  </td></tr>
  <tr><td bgcolor="#C9A84C" height="3" style="background-color:#C9A84C;height:3px;font-size:0;">&nbsp;</td></tr>
</table>
</td></tr>
</table>
</body></html>"""
    _send(email, subject, html)


def send_scan_alert(email, domain, score, new_issues):
    subject = f'New accessibility issues detected — {domain}'
    rows = ''.join(
        f'<tr><td bgcolor="#0D1526" style="background-color:#0D1526;padding:10px 0;border-bottom:1px solid #0A1020;font-family:Georgia,serif;font-size:13px;color:#6A7A8A;">{i}</td></tr>'
        for i in new_issues[:10]
    )
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background-color:#060A14;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#060A14">
<tr><td align="center" style="padding:28px 16px;" bgcolor="#060A14">
<table width="580" cellpadding="0" cellspacing="0" border="0" style="max-width:580px;width:100%;">
  <tr><td bgcolor="#C9A84C" height="3" style="background-color:#C9A84C;height:3px;font-size:0;">&nbsp;</td></tr>
  <tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:24px 36px;">
    <div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#E05252;margin-bottom:8px;">SCAN ALERT</div>
    <div style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#E8EAF0;margin-bottom:4px;">New issues detected on {domain}</div>
    <div style="font-family:Georgia,serif;font-size:13px;color:#3A3A4A;">Current score: {score}/100</div>
  </td></tr>
  <tr><td bgcolor="#0D1120" style="background-color:#0D1120;padding:20px 36px;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>
  </td></tr>
  <tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:20px 36px;text-align:center;">
    <table cellpadding="0" cellspacing="0" border="0" style="margin:0 auto;">
      <tr><td bgcolor="#C9A84C" style="background-color:#C9A84C;">
        <a href="https://idrshield.com/portal" style="display:block;padding:12px 28px;font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#060A14;text-decoration:none;">VIEW IN MEMBER PORTAL</a>
      </td></tr>
    </table>
  </td></tr>
  <tr><td bgcolor="#C9A84C" height="3" style="background-color:#C9A84C;height:3px;font-size:0;">&nbsp;</td></tr>
</table>
</td></tr>
</table>
</body></html>"""
    _send(email, subject, html)


def send_fix_confirmation_email(email, domain, categories, new_score):
    subject  = f'Remediation recorded — {domain}'
    cat_list = ', '.join(categories) if categories else 'General'
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background-color:#060A14;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#060A14">
<tr><td align="center" style="padding:28px 16px;" bgcolor="#060A14">
<table width="580" cellpadding="0" cellspacing="0" border="0" style="max-width:580px;width:100%;">
  <tr><td bgcolor="#C9A84C" height="3" style="background-color:#C9A84C;height:3px;font-size:0;">&nbsp;</td></tr>
  <tr><td bgcolor="#0A0E1A" style="background-color:#0A0E1A;padding:24px 36px;">
    <div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#52B788;margin-bottom:8px;">REMEDIATION CONFIRMED</div>
    <div style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#E8EAF0;margin-bottom:4px;">Fix recorded for {domain}</div>
    <div style="font-family:Georgia,serif;font-size:13px;color:#3A3A4A;">Categories updated: {cat_list}</div>
  </td></tr>
  <tr><td bgcolor="#0D1120" style="background-color:#0D1120;padding:24px 36px;text-align:center;">
    <div style="font-family:Georgia,serif;font-size:48px;font-weight:700;color:#52B788;line-height:1;">{new_score}</div>
    <div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#1A3A28;margin-top:4px;">/ 100 — Updated Score</div>
    <div style="margin-top:12px;font-family:Georgia,serif;font-size:12px;font-style:italic;color:#2A3A30;">This remediation has been logged with a timestamp in your evidence record.</div>
  </td></tr>
  <tr><td bgcolor="#C9A84C" height="3" style="background-color:#C9A84C;height:3px;font-size:0;">&nbsp;</td></tr>
</table>
</td></tr>
</table>
</body></html>"""
    _send(email, subject, html)
