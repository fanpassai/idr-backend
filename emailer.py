"""
IDR Shield — emailer.py
Handles all transactional email via SendGrid.
Drop this file into the idr-backend repo root.
"""

import os
import sendgrid
from sendgrid.helpers.mail import Mail


SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
FROM_EMAIL       = 'hello@idrshield.com'
FROM_NAME        = 'Institute of Digital Remediation'
GUMROAD_URL      = os.environ.get('GUMROAD_URL', 'https://idrshield.gumroad.com/l/oadcfq')


def _send(to_email, subject, html):
    """Internal SendGrid dispatcher."""
    if not SENDGRID_API_KEY:
        print(f'[EMAIL] No SENDGRID_API_KEY — skipping: {subject}')
        return
    try:
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


# ══════════════════════════════════════════════════════════════════════════════
# FREE SCAN SUMMARY EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def send_free_summary_email(email, receipt):
    """
    Sends the free scan results email immediately after a scan.
    Called from app.py at: send_free_summary_email(email, receipt)

    Receipt shape expected:
    {
      "receipt_id": "FAB4EF10-...",
      "registry_id": "IDR-REG-2026-FAB4EF10",
      "scan": {
        "domain": "kyliecosmetics.com",
        "overall_score": 36,
        "overall_status": "fail",   # "pass" | "warning" | "fail"
        "critical_count": 21,
        "total_issues": 47,
        "timestamp": "2026-04-07T22:26:09Z",
        "categories": [
          { "name": "Image Alt Text",      "slug": "image_alt_text",     "score": 80, "status": "warning", "issues": [...] },
          { "name": "Form Labels",         "slug": "form_labels",        "score": 80, "status": "warning", "issues": [...] },
          { "name": "Keyboard Navigation", "slug": "keyboard_navigation","score": 100,"status": "pass",    "issues": [] },
          { "name": "Heading Structure",   "slug": "heading_structure",  "score": 80, "status": "warning", "issues": [...] },
          { "name": "ARIA & Links",        "slug": "aria_links",         "score": 0,  "status": "fail",    "issues": [...] }
        ]
      }
    }
    """
    sc        = receipt.get('scan', {})
    domain    = sc.get('domain', 'your store')
    score     = sc.get('overall_score', 0)
    status    = sc.get('overall_status', 'warning')
    crits     = sc.get('critical_count', 0)
    total     = sc.get('total_issues', 0)
    cats      = sc.get('categories', [])
    receipt_id = receipt.get('receipt_id', '')
    registry_id = receipt.get('registry_id', '')
    timestamp  = sc.get('timestamp', '')

    # ── Derive display date ──
    try:
        from datetime import datetime
        dt = datetime.strptime(timestamp[:19], '%Y-%m-%dT%H:%M:%S')
        display_date = dt.strftime('%b %-d, %Y · %H:%M UTC')
    except Exception:
        display_date = timestamp[:16].replace('T', ' ') + ' UTC' if timestamp else ''

    # ── Status colors ──
    if status == 'pass':
        score_color  = '#52B788'
        status_label = 'REGISTRY ELIGIBLE'
        status_bg    = 'rgba(82,183,136,0.1)'
        status_border= 'rgba(82,183,136,0.35)'
    elif status == 'warning':
        score_color  = '#E9C46A'
        status_label = 'MONITORING STATUS'
        status_bg    = 'rgba(233,196,106,0.1)'
        status_border= 'rgba(233,196,106,0.35)'
    else:
        score_color  = '#E63946'
        status_label = 'REMEDIATION REQUIRED'
        status_bg    = 'rgba(230,57,70,0.1)'
        status_border= 'rgba(230,57,70,0.35)'

    # ── Subject line ──
    if status == 'pass':
        subject = f'{domain} passed — {score}/100 · No critical violations'
    elif crits > 0:
        subject = f'Your store flagged {crits} critical ADA issue{"s" if crits != 1 else ""} — {domain}'
    else:
        subject = f'Your store scored {score}/100 on ADA accessibility — {domain}'

    # ── Score context ──
    if status == 'pass':
        score_context = (
            'This store has no critical violations — currently eligible for Active '
            'registry status. Fewer than 20% of scanned stores reach this threshold.'
        )
    elif crits > 0:
        score_context = (
            f'{crits} critical violation{"s" if crits != 1 else ""} detected. '
            'This is exactly the issue profile automated plaintiff scanners flag '
            'when building demand letter queues.'
        )
    else:
        score_context = (
            f'{total} issues flagged across the five IDR audit categories — the '
            'same categories plaintiff firms prioritize when identifying targets.'
        )

    # ── Urgency block ──
    if status == 'pass':
        urgency_block = f'''
  <tr>
    <td style="background:rgba(82,183,136,0.07);border-left:4px solid #52B788;
               padding:28px 40px 28px 36px;">
      <div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;
                  letter-spacing:0.26em;text-transform:uppercase;color:#52B788;margin-bottom:12px;">
        COMPLIANCE STATUS
      </div>
      <div style="font-family:Georgia,serif;font-size:17px;font-weight:700;
                  color:#F0E8D8;line-height:1.45;margin-bottom:12px;">
        This store scored above the IDR threshold for Active registry status —
        placing it ahead of the majority of scanned e-commerce stores.
      </div>
      <div style="font-family:Georgia,serif;font-size:14px;
                  color:rgba(240,232,216,0.5);line-height:1.75;">
        Activating IDR Shield locks in this record with a SHA-256 signed receipt,
        weekly automated rescans, and a publicly verifiable registry entry.
      </div>
    </td>
  </tr>'''
    else:
        urgency_block = f'''
  <tr>
    <td style="background:rgba(100,15,15,0.25);border-left:4px solid #CC3333;
               padding:28px 40px 28px 36px;">
      <div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;
                  letter-spacing:0.26em;text-transform:uppercase;color:#CC3333;margin-bottom:12px;">
        RISK ASSESSMENT
      </div>
      <div style="font-family:Georgia,serif;font-size:18px;font-weight:700;
                  color:#F0E8D8;line-height:1.45;margin-bottom:14px;">
        Most store owners don't find out until they receive a legal notice —
        often without warning.
      </div>
      <div style="font-family:Georgia,serif;font-size:14px;
                  color:rgba(240,232,216,0.55);line-height:1.75;">
        At that point, the cost is no longer optional. Typical settlement ranges
        in comparable cases run
        <span style="color:#F0E8D8;font-weight:700;">$25,000–$95,000</span>
        — resolved quietly, quickly, and without trial.
      </div>
    </td>
  </tr>
  <tr>
    <td style="background:#060e1c;padding:24px 40px;
               border-top:1px solid rgba(201,168,76,0.07);">
      <div style="font-family:Georgia,serif;font-size:14px;
                  color:rgba(240,232,216,0.4);line-height:1.85;">
        These scans are not manual. Automated systems crawl thousands of stores
        every day — reading source code, flagging violations, and logging domain
        names before anyone picks up a phone.<br><br>
        <span style="color:rgba(201,168,76,0.65);font-style:italic;">
          Your store can be scanned at any time, by anyone. The only question
          is whether you see the results first — or they do.
        </span>
      </div>
    </td>
  </tr>'''

    # ── Category rows ──
    def cat_color(s):
        return '#52B788' if s == 'pass' else '#E9C46A' if s == 'warning' else '#E63946'

    def cat_label_html(cat):
        issues = cat.get('issues', [])
        s = cat.get('status', 'warning')
        if s == 'pass' or not issues:
            return '<span style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:#52B788;">&#x2713; Clean</span>'
        crit_count = sum(1 for i in issues if i.get('severity') == 'critical')
        count = len(issues)
        if crit_count:
            label = f'{crit_count} critical'
            color = '#E63946'
        else:
            label = f'{count} issue{"s" if count != 1 else ""}'
            color = '#E9C46A'
        return f'<span style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:{color};">{label}</span>'

    cat_rows_html = ''
    for i, cat in enumerate(cats):
        bg        = '#08101f' if i % 2 == 0 else '#060e1c'
        s         = cat.get('status', 'warning')
        cat_score = cat.get('score', 0)
        bar_color = cat_color(s)
        bar_pct   = max(4, cat_score)  # min 4% so bar is always visible

        cat_rows_html += f'''
  <tr>
    <td style="background:{bg};padding:0 40px;
               border-bottom:1px solid rgba(201,168,76,0.06);">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="padding:13px 0;vertical-align:middle;">
            <div style="font-family:Arial,Helvetica,sans-serif;font-size:9px;font-weight:700;
                        letter-spacing:0.12em;text-transform:uppercase;
                        color:rgba(240,232,216,0.45);">{cat.get("name","")}</div>
            <table cellpadding="0" cellspacing="0" border="0" style="margin-top:7px;">
              <tr>
                <td style="background:rgba(201,168,76,0.08);border-radius:1px;
                            height:3px;width:160px;">
                  <div style="width:{bar_pct}%;height:3px;background:{bar_color};
                               border-radius:1px;max-width:160px;"></div>
                </td>
              </tr>
            </table>
          </td>
          <td align="right" style="vertical-align:middle;white-space:nowrap;padding:13px 0;">
            {cat_label_html(cat)}
          </td>
        </tr>
      </table>
    </td>
  </tr>'''

    # ── Locked items ──
    locked_items = [
        'Full 10-section legal-grade Defense Package PDF',
        'Step-by-step remediation code for every flagged issue',
        'Plaintiff simulation — exactly how a law firm scores your store',
        'Legal positioning documentation for demand letter response',
        'SHA-256 tamper-proof Scan Receipt — your immutable evidence record',
        'IDR Verified badge + weekly automated rescans with real-time alerts',
    ]
    locked_html = ''.join(f'''
            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                   style="margin-bottom:{"0" if i == len(locked_items)-1 else "12px"};">
              <tr>
                <td width="24" style="vertical-align:top;padding-top:2px;font-size:13px;">&#x1F512;</td>
                <td style="font-family:Georgia,serif;font-size:13.5px;
                            color:rgba(240,232,216,0.55);line-height:1.5;">{item}</td>
              </tr>
            </table>'''
        for i, item in enumerate(locked_items)
    )

    # ── Benefits grid ──
    benefits_left_items = [
        'The 2026 Accessibility Shield — full digital book',
        '10-section legal-grade Defense Package PDF',
        'SHA-256 Scan Receipt — cryptographic compliance proof',
        'IDR Registry entry — publicly verifiable',
    ]
    benefits_right_items = [
        'IDR Verified badge for your store footer',
        'Weekly automated rescans + real-time alerts',
        '<strong style="color:#C9A84C;">$29/month — locked permanently for founding members</strong>',
    ]

    def benefit_col(items):
        rows = ''
        for i, item in enumerate(items):
            border = '' if i == len(items) - 1 else 'border-bottom:1px solid rgba(201,168,76,0.07);'
            rows += f'''
              <table width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="padding-{"top" if i > 0 else "bottom"}:11px;{border}">
                <tr>
                  <td width="18" style="vertical-align:top;padding-top:2px;
                                         font-size:11px;color:#C9A84C;font-family:Arial,Helvetica,sans-serif;">&#x2713;</td>
                  <td style="font-family:Georgia,serif;font-size:12.5px;
                              color:rgba(240,232,216,0.6);line-height:1.45;padding-left:6px;">{item}</td>
                </tr>
              </table>'''
        return rows

    benefits_left  = benefit_col(benefits_left_items)
    benefits_right = benefit_col(benefits_right_items)

    # ── Assemble full HTML ──
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#060A14;
             font-family:Georgia,'Times New Roman',serif;">

<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#060A14;">
<tr><td align="center" style="padding:32px 16px;">

<table width="600" cellpadding="0" cellspacing="0" border="0"
       style="max-width:600px;width:100%;
              box-shadow:0 0 80px rgba(0,0,0,0.8),0 0 0 1px rgba(201,168,76,0.15);">

  <!-- TOP GOLD BAR -->
  <tr>
    <td height="4" style="background:linear-gradient(90deg,#5a4520,#C9A84C,#E2C97E,#C9A84C,#5a4520);
                           font-size:0;line-height:0;">&nbsp;</td>
  </tr>

  <!-- HEADER -->
  <tr>
    <td style="background:#08101f;padding:24px 40px 22px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="vertical-align:middle;">
            <table cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td style="width:36px;height:36px;border-radius:50%;
                            border:1.5px solid #8A6F2E;
                            text-align:center;vertical-align:middle;
                            font-family:Georgia,serif;font-size:9px;font-weight:700;
                            color:#C9A84C;line-height:36px;
                            background:rgba(201,168,76,0.04);">IDR</td>
                <td width="12">&nbsp;</td>
                <td style="vertical-align:middle;">
                  <div style="font-family:Arial,Helvetica,sans-serif;font-size:8.5px;
                               font-weight:700;letter-spacing:0.22em;text-transform:uppercase;
                               color:#C9A84C;line-height:1.3;">
                    Institute of Digital Remediation
                  </div>
                  <div style="font-family:Georgia,serif;font-size:10px;font-style:italic;
                               color:rgba(201,168,76,0.45);margin-top:2px;">
                    IDR Protocol Series &middot; 2026 Edition
                  </div>
                </td>
              </tr>
            </table>
          </td>
          <td align="right" style="vertical-align:middle;">
            <div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;font-weight:600;
                         letter-spacing:0.18em;text-transform:uppercase;
                         color:rgba(201,168,76,0.25);">SCAN RECEIPT</div>
            <div style="font-family:'Courier New',Courier,monospace;font-size:9px;
                         color:rgba(201,168,76,0.2);margin-top:3px;">{display_date}</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- HEADER DIVIDER -->
  <tr>
    <td height="1" style="background:linear-gradient(90deg,transparent,rgba(201,168,76,0.2),transparent);
                           font-size:0;">&nbsp;</td>
  </tr>

  <!-- DOMAIN BANNER -->
  <tr>
    <td style="background:#060e1c;padding:20px 40px 18px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td>
            <div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;
                         letter-spacing:0.32em;text-transform:uppercase;
                         color:rgba(201,168,76,0.35);margin-bottom:7px;">
              YOUR STORE SCAN RESULTS
            </div>
            <div style="font-family:Georgia,serif;font-size:24px;font-weight:700;
                         color:#F0E8D8;letter-spacing:-0.01em;">{domain}</div>
          </td>
          <td align="right" style="vertical-align:bottom;">
            <div style="display:inline-block;background:{status_bg};
                         border:1px solid {status_border};border-radius:2px;
                         padding:5px 12px;font-family:Arial,Helvetica,sans-serif;
                         font-size:8px;font-weight:700;letter-spacing:0.18em;
                         text-transform:uppercase;color:{score_color};">
              {status_label}
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- SCORE BLOCK -->
  <tr>
    <td style="background:linear-gradient(160deg,#0a1628 0%,#060e1c 100%);
                padding:40px 40px 36px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <!-- Score circle -->
          <td width="156" align="center" style="vertical-align:top;">
            <table cellpadding="0" cellspacing="0" border="0"
                   style="width:140px;height:140px;border-radius:50%;
                           border:2.5px solid {score_color};
                           background:rgba(6,14,28,0.9);margin:0 auto;">
              <tr>
                <td align="center" style="vertical-align:middle;padding-top:4px;">
                  <div style="font-family:Georgia,serif;font-size:62px;font-weight:700;
                               color:{score_color};line-height:1;">{score}</div>
                  <div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;
                               font-weight:700;letter-spacing:0.2em;
                               color:rgba(201,168,76,0.4);text-transform:uppercase;
                               margin-top:5px;">/ 100</div>
                </td>
              </tr>
            </table>
            <div style="margin-top:14px;text-align:center;">
              <span style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;
                            letter-spacing:0.18em;text-transform:uppercase;color:{score_color};
                            border:1px solid {status_border};padding:4px 12px;
                            background:{status_bg};">
                {"PASS" if status == "pass" else "WARNING" if status == "warning" else "FAIL"}
              </span>
            </div>
          </td>

          <td width="24">&nbsp;</td>

          <!-- Stats -->
          <td style="vertical-align:top;">
            <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                         letter-spacing:0.26em;text-transform:uppercase;
                         color:rgba(201,168,76,0.35);margin-bottom:12px;">SCAN SUMMARY</div>
            <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:20px;">
              <tr>
                <td style="padding-right:28px;border-right:1px solid rgba(201,168,76,0.1);">
                  <div style="font-family:Georgia,serif;font-size:42px;font-weight:700;
                               color:#E63946;line-height:1;">{crits}</div>
                  <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                               letter-spacing:0.16em;text-transform:uppercase;
                               color:rgba(240,232,216,0.25);margin-top:4px;">Critical</div>
                </td>
                <td style="padding-left:28px;">
                  <div style="font-family:Georgia,serif;font-size:42px;font-weight:700;
                               color:#E9C46A;line-height:1;">{total}</div>
                  <div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;
                               letter-spacing:0.16em;text-transform:uppercase;
                               color:rgba(240,232,216,0.25);margin-top:4px;">Total Issues</div>
                </td>
              </tr>
            </table>
            <div style="border-left:2px solid rgba(201,168,76,0.2);padding-left:14px;">
              <div style="font-family:Georgia,serif;font-size:13px;font-style:italic;
                           color:rgba(240,232,216,0.4);line-height:1.65;">
                {score_context}
              </div>
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- URGENCY BLOCK -->
  {urgency_block}

  <!-- SECTION DIVIDER -->
  <tr>
    <td height="1" style="background:linear-gradient(90deg,transparent,rgba(201,168,76,0.12),transparent);
                           font-size:0;">&nbsp;</td>
  </tr>

  <!-- CATEGORY BREAKDOWN HEADER -->
  <tr>
    <td style="background:#08101f;padding:28px 40px 0;">
      <div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;
                   letter-spacing:0.32em;text-transform:uppercase;color:#8A6F2E;">
        CATEGORY BREAKDOWN
      </div>
    </td>
  </tr>

  <!-- CATEGORY ROWS -->
  {cat_rows_html}

  <!-- SECTION DIVIDER -->
  <tr>
    <td height="1" style="background:linear-gradient(90deg,transparent,rgba(201,168,76,0.12),transparent);
                           font-size:0;margin-top:4px;">&nbsp;</td>
  </tr>

  <!-- SURFACE SECTION -->
  <tr>
    <td style="background:#060e1c;padding:32px 40px;">
      <div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;
                   letter-spacing:0.3em;text-transform:uppercase;
                   color:rgba(201,168,76,0.35);margin-bottom:6px;">
        WHAT YOU'RE SEEING HERE IS ONLY THE SURFACE
      </div>
      <div style="font-family:Georgia,serif;font-size:14px;
                   color:rgba(240,232,216,0.35);margin-bottom:22px;line-height:1.6;">
        This summary does not include:
      </div>
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="background:rgba(13,21,38,0.7);border:1px solid rgba(201,168,76,0.1);
                     border-left:3px solid rgba(201,168,76,0.3);">
        <tr>
          <td style="padding:24px 28px;">
            {locked_html}
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- BRIDGE COPY -->
  <tr>
    <td style="background:#08101f;padding:28px 40px;
               border-top:1px solid rgba(201,168,76,0.07);">
      <div style="font-family:Georgia,serif;font-size:18px;font-weight:700;
                   color:#F0E8D8;line-height:1.45;margin-bottom:12px;">
        Most stores wait until they're forced to respond.<br>
        <span style="color:#C9A84C;font-style:italic;">
          Founding members act before that moment.
        </span>
      </div>
      <div style="font-family:Georgia,serif;font-size:14px;
                   color:rgba(240,232,216,0.4);line-height:1.75;">
        The Defense Package doesn't just show you the issues — it gives you
        the documentation, proof, and positioning to protect your store if
        it's ever challenged. This is exactly the moment most stores ignore
        — and regret later.
      </div>
    </td>
  </tr>

  <!-- FOUNDING CTA BLOCK -->
  <tr>
    <td style="background:linear-gradient(160deg,#0d1a2e 0%,#060e1c 100%);
                padding:40px 40px 36px;border-top:1px solid rgba(201,168,76,0.15);">

      <div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;
                   letter-spacing:0.32em;text-transform:uppercase;
                   color:#8A6F2E;margin-bottom:8px;">FOUNDING MEMBER ACCESS</div>
      <div style="font-family:Georgia,serif;font-size:28px;font-weight:700;
                   color:#F0E8D8;line-height:1.15;margin-bottom:5px;">
        Activate Your IDR Shield
      </div>
      <div style="font-family:Georgia,serif;font-size:14px;font-style:italic;
                   color:rgba(240,232,216,0.35);margin-bottom:28px;">
        Lock in founding access. First 500 stores only.
      </div>

      <!-- Benefits grid -->
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="margin-bottom:28px;">
        <tr>
          <td width="50%" style="vertical-align:top;padding-right:16px;">
            {benefits_left}
          </td>
          <td width="50%" style="vertical-align:top;padding-left:16px;
                                   border-left:1px solid rgba(201,168,76,0.08);">
            {benefits_right}
          </td>
        </tr>
      </table>

      <!-- Price display -->
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="background:rgba(201,168,76,0.04);border:1px solid rgba(201,168,76,0.15);
                     margin-bottom:24px;">
        <tr>
          <td style="padding:20px 24px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td style="vertical-align:middle;">
                  <div style="font-family:Georgia,serif;font-size:48px;font-weight:700;
                               color:#C9A84C;line-height:1;">$97</div>
                  <div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;
                               letter-spacing:0.18em;text-transform:uppercase;
                               color:rgba(201,168,76,0.4);margin-top:4px;">
                    Founding Access &middot; First 500 Stores &middot; Standard $127
                  </div>
                </td>
                <td align="right" style="vertical-align:middle;">
                  <div style="font-family:Georgia,serif;font-size:12px;font-style:italic;
                               color:rgba(240,232,216,0.3);text-align:right;line-height:1.7;">
                    For most merchants, one rushed<br>settlement conversation costs<br>
                    many times more than this.
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>

      <!-- CTA Button -->
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td align="center" style="background:#C9A84C;border-radius:2px;">
            <a href="{GUMROAD_URL}?ref={receipt_id}"
               style="display:block;padding:18px 40px;
                       font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:700;
                       letter-spacing:0.18em;text-transform:uppercase;
                       color:#060e1c;text-decoration:none;text-align:center;">
              ACTIVATE FOUNDING MEMBERSHIP &mdash; $97
            </a>
          </td>
        </tr>
      </table>
      <div style="text-align:center;margin-top:12px;font-family:Arial,Helvetica,sans-serif;
                   font-size:9px;color:rgba(201,168,76,0.3);letter-spacing:0.1em;">
        Limited to the first 500 stores &nbsp;&middot;&nbsp; 30 days free &nbsp;&middot;&nbsp; $29/month locked permanently
      </div>
    </td>
  </tr>

  <!-- REGISTRY RECORD -->
  <tr>
    <td style="background:#060e1c;padding:24px 40px;
               border-top:1px solid rgba(201,168,76,0.1);">
      <div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;
                   letter-spacing:0.24em;text-transform:uppercase;
                   color:rgba(201,168,76,0.3);margin-bottom:8px;">
        YOUR PUBLIC REGISTRY RECORD
      </div>
      <a href="https://idrshield.com/verify/{domain}"
         style="font-family:'Courier New',Courier,monospace;font-size:11.5px;
                 color:#8A6F2E;text-decoration:none;">
        https://idrshield.com/verify/{domain}
      </a>
      <div style="margin-top:8px;font-family:Georgia,serif;font-size:11px;font-style:italic;
                   color:rgba(240,232,216,0.18);">
        Publicly verifiable. Anyone can confirm your compliance record.
      </div>
      <table width="100%" cellpadding="0" cellspacing="0" border="0"
             style="margin-top:16px;border-top:1px solid rgba(201,168,76,0.06);padding-top:14px;">
        <tr>
          <td>
            <div style="font-family:'Courier New',Courier,monospace;font-size:9px;
                         color:rgba(201,168,76,0.2);line-height:1.8;">
              RECEIPT &middot; {receipt_id[:16]}&#8230;<br>
              REGISTRY &middot; {registry_id}<br>
              OPERATOR &middot; IDR_SCANNER_v1 &middot; PROTOCOL &middot; IDR-BRAND-2026-01
            </div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- FOOTER -->
  <tr>
    <td style="background:#04080f;padding:18px 40px;
               border-top:1px solid rgba(201,168,76,0.07);">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td>
            <div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;
                         color:rgba(201,168,76,0.18);letter-spacing:0.14em;
                         text-transform:uppercase;margin-bottom:7px;">
              Institute of Digital Remediation &middot; idrshield.com &middot; IDR-BRAND-2026-01
            </div>
            <div style="font-family:Georgia,serif;font-size:10.5px;font-style:italic;
                         color:rgba(240,232,216,0.12);line-height:1.7;">
              Not a law firm. This is a compliance documentation system.
              Settlement ranges cited reflect publicly available case data
              and are not a prediction of any specific legal action.
            </div>
          </td>
          <td width="60" align="right" style="vertical-align:middle;">
            <div style="width:32px;height:32px;border-radius:50%;
                         border:1px solid rgba(201,168,76,0.15);
                         text-align:center;line-height:32px;font-family:Georgia,serif;
                         font-size:8px;font-weight:700;color:rgba(201,168,76,0.2);">IDR</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- BOTTOM GOLD BAR -->
  <tr>
    <td height="4" style="background:linear-gradient(90deg,#5a4520,#C9A84C,#E2C97E,#C9A84C,#5a4520);
                           font-size:0;line-height:0;">&nbsp;</td>
  </tr>

</table>

</td></tr>
</table>
</body>
</html>'''

    _send(email, subject, html)


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVATION RECEIPT EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def send_activation_receipt(email, receipt):
    """Sends post-purchase welcome email. Called from Gumroad webhook handler."""
    domain     = receipt.get('domain', 'your store')
    score      = receipt.get('score', 0)
    registry_url = receipt.get('registry_url', f'https://idrshield.com/verify/{domain}')

    subject = f'Welcome to IDR Shield — {domain} is now in the registry'

    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#060A14;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;box-shadow:0 0 0 1px rgba(201,168,76,0.15);">
  <tr><td height="4" style="background:linear-gradient(90deg,#5a4520,#C9A84C,#E2C97E,#C9A84C,#5a4520);font-size:0;">&nbsp;</td></tr>
  <tr><td style="background:#08101f;padding:32px 40px;text-align:center;">
    <div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.3em;text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">FOUNDING MEMBER CONFIRMED</div>
    <div style="font-family:Georgia,serif;font-size:28px;font-weight:700;color:#F0E8D8;margin-bottom:6px;">You're in the registry.</div>
    <div style="font-family:Georgia,serif;font-size:15px;font-style:italic;color:rgba(240,232,216,0.4);">{domain} is now an active IDR Shield member.</div>
  </td></tr>
  <tr><td style="background:#060e1c;padding:28px 40px;text-align:center;">
    <div style="font-family:Georgia,serif;font-size:48px;font-weight:700;color:#C9A84C;line-height:1;">{score}</div>
    <div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:rgba(201,168,76,0.4);margin-top:4px;">/ 100 — Your Baseline Score</div>
    <div style="margin-top:20px;">
      <a href="{registry_url}" style="display:inline-block;background:#C9A84C;padding:14px 36px;font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#060e1c;text-decoration:none;">VIEW YOUR REGISTRY RECORD</a>
    </div>
  </td></tr>
  <tr><td style="background:#04080f;padding:18px 40px;border-top:1px solid rgba(201,168,76,0.07);">
    <div style="font-family:Georgia,serif;font-size:10.5px;font-style:italic;color:rgba(240,232,216,0.12);line-height:1.7;">
      Not a law firm. Institute of Digital Remediation &middot; idrshield.com
    </div>
  </td></tr>
  <tr><td height="4" style="background:linear-gradient(90deg,#5a4520,#C9A84C,#E2C97E,#C9A84C,#5a4520);font-size:0;">&nbsp;</td></tr>
</table>
</td></tr></table>
</body></html>'''

    _send(email, subject, html)


# ══════════════════════════════════════════════════════════════════════════════
# SCAN ALERT EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def send_scan_alert(email, domain, score, new_issues):
    """Sends weekly rescan alert when new violations are detected."""
    subject = f'New accessibility issues detected — {domain}'
    issue_rows = ''.join(
        f'<tr><td style="padding:10px 0;border-bottom:1px solid rgba(201,168,76,0.07);font-family:Georgia,serif;font-size:13px;color:rgba(240,232,216,0.6);">{i}</td></tr>'
        for i in new_issues[:10]
    )
    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#060A14;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;box-shadow:0 0 0 1px rgba(201,168,76,0.15);">
  <tr><td height="4" style="background:linear-gradient(90deg,#5a4520,#C9A84C,#E2C97E,#C9A84C,#5a4520);font-size:0;">&nbsp;</td></tr>
  <tr><td style="background:#08101f;padding:28px 40px;">
    <div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.3em;text-transform:uppercase;color:#E63946;margin-bottom:10px;">SCAN ALERT</div>
    <div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#F0E8D8;margin-bottom:6px;">New issues detected on {domain}</div>
    <div style="font-family:Georgia,serif;font-size:14px;color:rgba(240,232,216,0.4);">Current score: {score}/100</div>
  </td></tr>
  <tr><td style="background:#060e1c;padding:28px 40px;">
    <table width="100%" cellpadding="0" cellspacing="0">{issue_rows}</table>
  </td></tr>
  <tr><td style="background:#08101f;padding:24px 40px;text-align:center;">
    <a href="https://idrshield.com/portal" style="display:inline-block;background:#C9A84C;padding:13px 32px;font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#060e1c;text-decoration:none;">VIEW IN MEMBER PORTAL</a>
  </td></tr>
  <tr><td height="4" style="background:linear-gradient(90deg,#5a4520,#C9A84C,#E2C97E,#C9A84C,#5a4520);font-size:0;">&nbsp;</td></tr>
</table>
</td></tr></table>
</body></html>'''

    _send(email, subject, html)


# ══════════════════════════════════════════════════════════════════════════════
# FIX CONFIRMATION EMAIL
# ══════════════════════════════════════════════════════════════════════════════

def send_fix_confirmation_email(email, domain, categories, new_score):
    """Confirms remediation recorded in the evidence log."""
    subject = f'Remediation recorded — {domain}'
    cat_list = ', '.join(categories) if categories else 'General'

    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#060A14;font-family:Georgia,serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:32px 16px;">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;box-shadow:0 0 0 1px rgba(201,168,76,0.15);">
  <tr><td height="4" style="background:linear-gradient(90deg,#5a4520,#C9A84C,#E2C97E,#C9A84C,#5a4520);font-size:0;">&nbsp;</td></tr>
  <tr><td style="background:#08101f;padding:28px 40px;">
    <div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.3em;text-transform:uppercase;color:#52B788;margin-bottom:10px;">REMEDIATION CONFIRMED</div>
    <div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#F0E8D8;margin-bottom:6px;">Fix recorded for {domain}</div>
    <div style="font-family:Georgia,serif;font-size:14px;color:rgba(240,232,216,0.4);">Categories: {cat_list}</div>
  </td></tr>
  <tr><td style="background:#060e1c;padding:28px 40px;text-align:center;">
    <div style="font-family:Georgia,serif;font-size:48px;font-weight:700;color:#52B788;line-height:1;">{new_score}</div>
    <div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:rgba(82,183,136,0.5);margin-top:4px;">/ 100 — Updated Score</div>
    <div style="margin-top:16px;font-family:Georgia,serif;font-size:13px;font-style:italic;color:rgba(240,232,216,0.35);">This remediation has been logged with a timestamp in your evidence record.</div>
  </td></tr>
  <tr><td height="4" style="background:linear-gradient(90deg,#5a4520,#C9A84C,#E2C97E,#C9A84C,#5a4520);font-size:0;">&nbsp;</td></tr>
</table>
</td></tr></table>
</body></html>'''

    _send(email, subject, html)
