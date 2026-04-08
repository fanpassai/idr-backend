"""
IDR Shield — emailer.py
All transactional email via SendGrid.
Email-safe HTML: solid hex bgcolor on every td, no rgba(), no linear-gradient.
Three scan result states: PASS (green), MONITORING (amber), FAIL (red).
Tested against iOS Mail + Gmail mobile.
"""

import os
from datetime import datetime, timezone, timedelta

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


# ── Shared email components ───────────────────────────────────────────────────

def _email_header(display_date):
    return (
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
        # Header row
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
        '</svg></td>'
        '<td width="10">&nbsp;</td>'
        '<td style="vertical-align:middle;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#C9A84C;line-height:1.2;">Institute of Digital Remediation</div>'
        '<div style="font-family:Georgia,serif;font-size:10px;font-style:italic;color:#8A6F2E;margin-top:2px;">IDR Protocol Series &middot; 2026 Edition</div>'
        '</td></tr></table></td>'
        '<td align="right" style="vertical-align:middle;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;color:#AAAAAA;letter-spacing:0.1em;text-transform:uppercase;">Scan Receipt</div>'
        '<div style="font-family:Georgia,serif;font-size:10px;color:#BBBBBB;margin-top:2px;font-style:italic;">' + display_date + '</div>'
        '</td></tr></table></td></tr>'
        # Header divider
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:0 40px;"><div style="height:1px;background:#E8E4DC;"></div></td></tr>'
    )


def _score_block(domain, score, crits, total, score_color, status_label, status_badge, badge_color):
    crits_word = 'violation' if crits == 1 else 'violations'
    return (
        # Domain + status banner
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:20px 40px 0;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td style="vertical-align:bottom;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.3em;text-transform:uppercase;color:#BBBBBB;margin-bottom:6px;">Your Store Scan Results</div>'
        '<div style="font-family:Georgia,serif;font-size:26px;font-weight:700;color:#0A0E1A;letter-spacing:-0.01em;line-height:1;">' + domain + '</div>'
        '</td>'
        '<td align="right" style="vertical-align:bottom;padding-bottom:2px;">'
        '<div style="border:1.5px solid ' + badge_color + ';padding:5px 12px;display:inline-block;">'
        '<span style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:' + badge_color + ';">' + status_badge + '</span>'
        '</div></td></tr></table></td></tr>'
        # Score block
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px 32px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td width="130" align="center" style="vertical-align:top;">'
        '<table width="110" height="110" cellpadding="0" cellspacing="0" border="0" style="border:2px solid ' + score_color + ';margin:0 auto;">'
        '<tr><td align="center" style="vertical-align:middle;background-color:#FFFFFF;">'
        '<div style="font-family:Georgia,serif;font-size:58px;font-weight:700;color:' + score_color + ';line-height:1;">' + str(score) + '</div>'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;font-weight:600;letter-spacing:0.2em;color:#CCCCCC;text-transform:uppercase;margin-top:3px;">/ 100</div>'
        '</td></tr></table>'
        '<div style="margin-top:10px;text-align:center;">'
        '<span style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:' + score_color + ';border:1px solid ' + score_color + ';padding:4px 14px;display:inline-block;">' + status_label + '</span>'
        '</div></td>'
        '<td width="20">&nbsp;</td>'
        '<td style="vertical-align:top;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#CCCCCC;margin-bottom:14px;">Scan Summary</div>'
        '<table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:18px;"><tr>'
        '<td style="padding-right:28px;border-right:1px solid #E8E4DC;">'
        '<div style="font-family:Georgia,serif;font-size:40px;font-weight:700;color:#0A0E1A;line-height:1;">' + str(crits) + '</div>'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#AAAAAA;margin-top:4px;">Critical</div>'
        '</td><td style="padding-left:28px;">'
        '<div style="font-family:Georgia,serif;font-size:40px;font-weight:700;color:#0A0E1A;line-height:1;">' + str(total) + '</div>'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#AAAAAA;margin-top:4px;">Total Issues</div>'
        '</td></tr></table>'
        '<div style="border-left:2px solid #E8E4DC;padding-left:14px;">'
        '<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#888888;line-height:1.65;">'
        + str(crits) + ' critical ' + crits_word + ' detected &mdash; the exact issue profile plaintiff scanners flag when building demand letter queues.'
        '</div></div></td></tr></table></td></tr>'
    )


def _category_rows(cats):
    cat_map = {}
    for c in (cats or []):
        slug = c.get('slug', '')
        cat_map[slug] = c
        if 'aria' in slug:
            cat_map['aria_links'] = c
        if 'contrast' in slug and 'aria' not in slug:
            cat_map['contrast'] = c

    cat_labels = {
        'alt_text':          'Image Alt Text',
        'form_labels':       'Form Labels',
        'keyboard_nav':      'Keyboard Navigation',
        'heading_structure': 'Heading Structure',
        'contrast':          'Color Contrast',
        'aria_links':        'ARIA & Links',
    }

    def count_by_severity(cat_data, severity):
        return sum(1 for i in cat_data.get('issues', []) if i.get('severity') == severity)

    html = (
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:0 40px;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#C9A84C;padding:20px 0 12px;border-bottom:1px solid #E8E4DC;">Category Breakdown</div>'
        '</td></tr>'
    )

    row_bg = ['#FFFFFF', '#FAFAF8']
    items  = list(cat_labels.items())
    for i, (cat_key, cat_name) in enumerate(items):
        bg       = row_bg[i % 2]
        cat_data = cat_map.get(cat_key, {})
        cat_crits = count_by_severity(cat_data, 'critical')
        cat_total = len(cat_data.get('issues', []))
        is_last   = (i == len(items) - 1)
        border    = '' if is_last else 'border-bottom:1px solid #F2EFE9;'

        if cat_crits > 0:
            bar_color  = '#E05252'
            bar_width  = max(20, min(160, cat_crits * 20))
            count_html = '<span style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:#E05252;">' + str(cat_crits) + ' critical</span>'
        elif cat_total > 0:
            bar_color  = '#E9C46A'
            bar_width  = max(40, min(160, cat_total * 25))
            count_html = '<span style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:#E9A030;">' + str(cat_total) + (' issues' if cat_total != 1 else ' issue') + '</span>'
        else:
            bar_color  = '#52B788'
            bar_width  = 160
            count_html = '<span style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:#52B788;">&#x2713; Clean</span>'

        html += (
            '<tr><td bgcolor="' + bg + '" style="background-color:' + bg + ';padding:0 40px;">'
            '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="' + border + '"><tr>'
            '<td style="padding:13px 0;vertical-align:middle;">'
            '<div style="font-family:Arial,Helvetica,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#333333;margin-bottom:7px;">' + cat_name + '</div>'
            '<table cellpadding="0" cellspacing="0" border="0"><tr>'
            '<td bgcolor="#F0ECE4" width="160" height="3" style="background-color:#F0ECE4;width:160px;height:3px;font-size:0;">'
            '<table cellpadding="0" cellspacing="0" border="0"><tr>'
            '<td bgcolor="' + bar_color + '" width="' + str(bar_width) + '" height="3" style="background-color:' + bar_color + ';width:' + str(bar_width) + 'px;height:3px;font-size:0;">&nbsp;</td>'
            '</tr></table></td></tr></table></td>'
            '<td align="right" style="vertical-align:middle;white-space:nowrap;">' + count_html + '</td>'
            '</tr></table></td></tr>'
        )

    return html


def _cta_block(gumroad_url, cta_headline, cta_sub):
    return (
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:36px 40px;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.28em;text-transform:uppercase;color:#8A6F2E;margin-bottom:8px;">Founding Member Access</div>'
        '<div style="font-family:Georgia,serif;font-size:26px;font-weight:700;color:#0A0E1A;margin-bottom:4px;line-height:1.15;">' + cta_headline + '</div>'
        '<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#AAAAAA;margin-bottom:28px;">' + cta_sub + '</div>'
        # Benefits 2-col
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
        # Price block
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#FDFCF9;border:1px solid #E8E4DC;margin-bottom:20px;"><tr>'
        '<td style="padding:18px 24px;vertical-align:middle;">'
        '<span style="font-family:Georgia,serif;font-size:44px;font-weight:700;color:#C9A84C;line-height:1;">$97</span>'
        '<span style="font-family:Arial,Helvetica,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#CCCCCC;margin-left:10px;white-space:nowrap;">Founding Access &middot; First 500 Stores</span>'
        '</td>'
        '<td align="right" style="padding:18px 24px;vertical-align:middle;">'
        '<div style="font-family:Georgia,serif;font-size:11px;font-style:italic;color:#AAAAAA;text-align:right;line-height:1.6;">Standard price $127<br>after founding window closes</div>'
        '</td></tr></table>'
        # CTA button
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td bgcolor="#C9A84C" align="center" style="background-color:#C9A84C;">'
        '<a href="' + gumroad_url + '" style="display:block;padding:18px 40px;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#FFFFFF;text-decoration:none;text-align:center;">ACTIVATE FOUNDING MEMBERSHIP &mdash; $97</a>'
        '</td></tr></table>'
        '<div style="text-align:center;margin-top:10px;font-family:Arial,Helvetica,sans-serif;font-size:9px;color:#CCCCCC;letter-spacing:0.1em;">Limited to the first 500 stores &nbsp;&middot;&nbsp; 30 days free &nbsp;&middot;&nbsp; $29/month locked permanently</div>'
        '</td></tr>'
    )


def _registry_footer(domain, receipt_short, registry_id):
    return (
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:22px 40px;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:#AAAAAA;margin-bottom:8px;">Your Public Registry Record</div>'
        '<a href="https://idrshield.com/verify/' + domain + '" style="font-family:\'Courier New\',Courier,monospace;font-size:12px;color:#8A6F2E;text-decoration:none;">https://idrshield.com/verify/' + domain + '</a>'
        '<div style="margin-top:8px;font-family:Georgia,serif;font-size:11px;font-style:italic;color:#BBBBBB;">Publicly verifiable. Anyone can confirm your compliance record.</div>'
        '<div style="margin-top:14px;padding-top:12px;border-top:1px solid #E8E4DC;font-family:\'Courier New\',Courier,monospace;font-size:9px;color:#CCCCCC;line-height:1.8;">RECEIPT &middot; ' + receipt_short + ' &nbsp;&nbsp; REGISTRY &middot; ' + registry_id + ' &nbsp;&nbsp; OPERATOR &middot; IDR_SCANNER_v1</div>'
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:18px 40px;border-top:1px solid #E8E4DC;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td>'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:8px;color:#CCCCCC;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:6px;">Institute of Digital Remediation &nbsp;&middot;&nbsp; idrshield.com &nbsp;&middot;&nbsp; IDR-BRAND-2026-01</div>'
        '<div style="font-family:Georgia,serif;font-size:10.5px;font-style:italic;color:#CCCCCC;line-height:1.7;">Not a law firm. This is a compliance documentation system. Settlement ranges cited reflect publicly available case data and are not a prediction of any specific legal action.</div>'
        '<div style="margin-top:10px;font-family:Arial,Helvetica,sans-serif;font-size:8px;color:#DDDDDD;letter-spacing:0.06em;">'
        '<a href="https://idrshield.com/privacy" style="color:#CCCCCC;text-decoration:none;">Privacy Policy</a>'
        ' &nbsp;&middot;&nbsp; <a href="https://idrshield.com/terms" style="color:#CCCCCC;text-decoration:none;">Terms of Service</a>'
        ' &nbsp;&middot;&nbsp; <a href="mailto:hello@idrshield.com" style="color:#CCCCCC;text-decoration:none;">hello@idrshield.com</a>'
        '</div></td>'
        '<td width="50" align="right" style="vertical-align:middle;">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 30 30">'
        '<circle cx="15" cy="15" r="14" fill="none" stroke="#E8E4DC" stroke-width="1"/>'
        '<text x="15" y="19" font-family="Georgia,serif" font-size="8" font-weight="700" fill="#DDDDDD" text-anchor="middle">IDR</text>'
        '</svg></td></tr></table></td></tr>'
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;height:4px;font-size:0;line-height:0;">&nbsp;</td></tr>'
        '</table></td></tr></table></body></html>'
    )


# ── State-specific content ────────────────────────────────────────────────────

def _content_fail():
    urgency = (
        '<tr><td bgcolor="#FDF8F0" style="background-color:#FDF8F0;border-top:1px solid #F0E8D8;border-bottom:1px solid #F0E8D8;padding:24px 40px;border-left:4px solid #C9A84C;">'
        '<div style="font-family:Georgia,serif;font-size:18px;font-weight:700;color:#0A0E1A;line-height:1.45;margin-bottom:10px;">The same scanners that flagged your store are the ones plaintiff firms use to build their demand letter queues.</div>'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#666666;line-height:1.75;">These aren&rsquo;t manual reviews &mdash; they&rsquo;re automated, continuous, and running right now. A store with your violation profile gets added to outreach lists before any human ever looks at it. Typical settlement demand: <span style="color:#0A0E1A;font-weight:700;">$25,000&ndash;$95,000</span>. Most stores pay because they have no documented defense. You now know what they found. The question is what you do with it.</div>'
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" height="8" style="background-color:#FFFFFF;height:8px;font-size:0;">&nbsp;</td></tr>'
    )
    locked = (
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
    )
    bridge = (
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<div style="font-family:Georgia,serif;font-size:19px;font-weight:700;color:#0A0E1A;line-height:1.4;margin-bottom:8px;">You found this before they acted on it. That window is still open.</div>'
        '<div style="font-family:Georgia,serif;font-size:19px;color:#C9A84C;font-style:italic;line-height:1.4;margin-bottom:14px;">Founding members use that window. Most stores don&rsquo;t.</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#777777;line-height:1.8;">Activating IDR Shield creates a timestamped compliance record from this moment forward. If you&rsquo;re ever challenged, the evidence log, the Defense Package, and the receipt are what stand between you and a five-figure settlement demand.</div>'
        '</td></tr>'
    )
    return urgency, locked, bridge, 'Stop Being an Easy Target', 'Activate your defense record before someone else scans you first.'


def _content_monitoring():
    urgency = (
        '<tr><td bgcolor="#FDF8F0" style="background-color:#FDF8F0;border-top:1px solid #F0E8D8;border-bottom:1px solid #F0E8D8;padding:24px 40px;border-left:4px solid #C9A84C;">'
        '<div style="font-family:Georgia,serif;font-size:18px;font-weight:700;color:#0A0E1A;line-height:1.45;margin-bottom:10px;">Open violations with no remediation record is exactly the risk profile plaintiff firms look for.</div>'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#666666;line-height:1.75;">They don&rsquo;t need a failing score to send a demand letter &mdash; they need open violations and no documented compliance effort. That&rsquo;s the profile. Your violations are visible to the same automated systems building those queues right now. <span style="color:#0A0E1A;font-weight:700;">The stores that survive these letters aren&rsquo;t the ones with perfect scores &mdash; they&rsquo;re the ones with documented proof they were actively working on it.</span></div>'
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" height="8" style="background-color:#FFFFFF;height:8px;font-size:0;">&nbsp;</td></tr>'
    )
    locked = (
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#C9A84C;margin-bottom:6px;">What Turns a Monitoring Score Into a Defense</div>'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#888888;line-height:1.6;margin-bottom:20px;">This summary shows the surface. IDR Shield gives you the documentation that matters:</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;border-left:3px solid #C9A84C;">'
        '<tr><td bgcolor="#FDFCF9" style="background-color:#FDFCF9;padding:20px 24px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td style="padding-bottom:10px;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F512;&nbsp;&nbsp;Step-by-step remediation code for every open violation</td></tr>'
        '<tr><td style="padding:10px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F512;&nbsp;&nbsp;Legal-grade Defense Package PDF &mdash; proof of active remediation effort</td></tr>'
        '<tr><td style="padding:10px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F512;&nbsp;&nbsp;SHA-256 Scan Receipt &mdash; timestamped, immutable, court-admissible</td></tr>'
        '<tr><td style="padding:10px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F512;&nbsp;&nbsp;IDR Registry entry &mdash; public proof you&rsquo;re enrolled and monitoring</td></tr>'
        '<tr><td style="padding-top:10px;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F512;&nbsp;&nbsp;Weekly rescans &mdash; automatic alerts when violations are fixed or worsen</td></tr>'
        '</table></td></tr></table></td></tr>'
    )
    bridge = (
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<div style="font-family:Georgia,serif;font-size:19px;font-weight:700;color:#0A0E1A;line-height:1.4;margin-bottom:8px;">Your violations are visible. Your remediation record isn&rsquo;t.</div>'
        '<div style="font-family:Georgia,serif;font-size:19px;color:#C9A84C;font-style:italic;line-height:1.4;margin-bottom:14px;">IDR Shield creates the record that changes that conversation.</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#777777;line-height:1.8;">The moment you activate, IDR begins documenting your remediation effort &mdash; timestamped, hashed, publicly verifiable. If a demand letter arrives, your attorney doesn&rsquo;t say &ldquo;we&rsquo;re working on it.&rdquo; They produce the receipt, the evidence log, and the Defense Package. That&rsquo;s the difference between a $50,000 settlement and a dismissed claim.</div>'
        '</td></tr>'
    )
    return urgency, locked, bridge, 'Make Your Remediation Effort Official', 'Open violations with a documented record are defensible. Without one, they aren\'t.'


def _content_pass():
    urgency = (
        '<tr><td bgcolor="#F0FAF4" style="background-color:#F0FAF4;border-top:1px solid #C8EAD4;border-bottom:1px solid #C8EAD4;padding:24px 40px;border-left:4px solid #27AE60;">'
        '<div style="font-family:Georgia,serif;font-size:18px;font-weight:700;color:#0A0E1A;line-height:1.45;margin-bottom:10px;">Passing is the score. The record is what actually protects you.</div>'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#666666;line-height:1.75;">A clean scan with no documentation is the same as no scan at all &mdash; because in a legal challenge, the score isn&rsquo;t the evidence. The timestamped record, the receipt, the evidence log &mdash; those are the evidence. Plaintiff firms scan continuously. Your passing score today is a single snapshot. IDR Shield makes it a living, verifiable compliance record that grows stronger every week.</div>'
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" height="8" style="background-color:#FFFFFF;height:8px;font-size:0;">&nbsp;</td></tr>'
    )
    locked = (
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#27AE60;margin-bottom:6px;">What IDR Shield Adds on Top of Your Clean Scan</div>'
        '<div style="font-family:Georgia,serif;font-size:13.5px;color:#888888;line-height:1.6;margin-bottom:20px;">A passing score alone won&rsquo;t protect you. Here&rsquo;s what will:</div>'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;border-left:3px solid #27AE60;">'
        '<tr><td bgcolor="#F9FCF9" style="background-color:#F9FCF9;padding:20px 24px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        '<tr><td style="padding-bottom:10px;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F4DC;&nbsp;&nbsp;SHA-256 Scan Receipt &mdash; cryptographic, timestamped, court-admissible</td></tr>'
        '<tr><td style="padding:10px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F6E1;&nbsp;&nbsp;Public registry record at idrshield.com/verify/yourdomain</td></tr>'
        '<tr><td style="padding:10px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F504;&nbsp;&nbsp;Weekly automated rescans &mdash; instant alert if your score drops</td></tr>'
        '<tr><td style="padding:10px 0;border-bottom:1px solid #F0EDE8;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x2705;&nbsp;&nbsp;IDR Verified badge &mdash; visible signal of active monitoring</td></tr>'
        '<tr><td style="padding-top:10px;font-family:Georgia,serif;font-size:13.5px;color:#555555;line-height:1.5;">&#x1F4CB;&nbsp;&nbsp;Full Defense Package PDF &mdash; ready if you ever need it</td></tr>'
        '</table></td></tr></table></td></tr>'
    )
    bridge = (
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:28px 40px;">'
        '<div style="font-family:Georgia,serif;font-size:19px;font-weight:700;color:#0A0E1A;line-height:1.4;margin-bottom:8px;">You&rsquo;re clean today. The record proves it was intentional.</div>'
        '<div style="font-family:Georgia,serif;font-size:19px;color:#C9A84C;font-style:italic;line-height:1.4;margin-bottom:14px;">That distinction is worth more than the score itself.</div>'
        '<div style="font-family:Georgia,serif;font-size:14px;color:#777777;line-height:1.8;">Founding members lock in $29/month permanently and get the gold seal no future member will ever receive. But more than that &mdash; they get a growing evidence record that compounds in value every week. The longer you&rsquo;re enrolled, the stronger your defense becomes.</div>'
        '</td></tr>'
    )
    return urgency, locked, bridge, 'Your Score Is Clean. Now Make It Official.', 'A passing scan with no record is the same as no scan at all in a legal challenge.'


# ── Main email function ───────────────────────────────────────────────────────

def send_free_summary_email(email, receipt):
    sc          = receipt.get('scan', {})
    domain      = sc.get('domain', 'your store')
    score       = int(sc.get('overall_score', 0))
    crits       = sc.get('critical_count', 0)
    total       = sc.get('total_issues', 0)
    cats        = sc.get('categories', [])
    receipt_id  = receipt.get('receipt_id', '')
    registry_id = receipt.get('registry_id', '')
    timestamp   = sc.get('timestamp', '')

    try:
        dt = datetime.strptime(timestamp[:19], '%Y-%m-%dT%H:%M:%S')
        display_date = dt.strftime('%b %-d, %Y · %H:%M UTC')
    except Exception:
        display_date = (timestamp[:16].replace('T', ' ') + ' UTC') if timestamp else ''

    # State routing
    if score >= 80:   # PASS: clean, minimal critical violations
        score_color  = '#27AE60'
        status_label = 'PASS'
        status_badge = 'Compliance Verified'
        badge_color  = '#27AE60'
        subject      = domain + ' passed — but your compliance record isn\'t protected yet'
        urgency, locked, bridge, cta_headline, cta_sub = _content_pass()
    elif score >= 60: # MONITORING: exposed but not worst profile
        score_color  = '#E9A030'
        status_label = 'MONITORING'
        status_badge = 'Remediation Required'
        badge_color  = '#E9A030'
        subject      = domain + ' has ' + str(crits) + ' open ADA violation' + ('s' if crits != 1 else '') + ' — here\'s your risk profile'
        urgency, locked, bridge, cta_headline, cta_sub = _content_monitoring()
    else:
        score_color  = '#E05252'
        status_label = 'FAIL'
        status_badge = 'Remediation Required'
        badge_color  = '#E05252'
        subject      = 'Your store flagged ' + str(crits) + ' critical ADA issue' + ('s' if crits != 1 else '') + ' — ' + domain
        urgency, locked, bridge, cta_headline, cta_sub = _content_fail()

    receipt_short = (receipt_id[:22] + '&hellip;') if len(receipt_id) > 22 else receipt_id

    html = (
        _email_header(display_date) +
        _score_block(domain, score, crits, total, score_color, status_label, status_badge, badge_color) +
        urgency +
        _category_rows(cats) +
        '<tr><td bgcolor="#F2EFE9" height="2" style="background-color:#F2EFE9;height:2px;font-size:0;">&nbsp;</td></tr>' +
        locked +
        bridge +
        _cta_block(GUMROAD_URL, cta_headline, cta_sub) +
        _registry_footer(domain, receipt_short, registry_id)
    )

    _send(email, subject, html)


# ── Other transactional emails ────────────────────────────────────────────────

def send_activation_receipt(email, receipt):
    domain       = receipt.get('domain', 'your store')
    score        = receipt.get('score', 0)
    registry_url = receipt.get('registry_url', 'https://idrshield.com/verify/' + domain)
    subject      = 'Welcome to IDR Shield \u2014 ' + domain + ' is now in the registry'
    html = (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
        '<body style="margin:0;padding:0;background-color:#F2EFE9;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#F2EFE9;">'
        '<tr><td align="center" style="padding:24px 16px;">'
        '<table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;background-color:#FFFFFF;">'
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;">&nbsp;</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:32px 40px;text-align:center;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.26em;text-transform:uppercase;color:#8A6F2E;margin-bottom:8px;">FOUNDING MEMBER CONFIRMED</div>'
        '<div style="font-family:Georgia,serif;font-size:24px;font-weight:700;color:#0A0E1A;margin-bottom:5px;">You&#39;re in the registry.</div>'
        '<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#AAAAAA;">' + domain + ' is now an active IDR Shield member.</div>'
        '</td></tr>'
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:32px 40px;text-align:center;">'
        '<div style="font-family:Georgia,serif;font-size:52px;font-weight:700;color:#C9A84C;line-height:1;">' + str(score) + '</div>'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#AAAAAA;margin-top:4px;">/ 100 &mdash; Your Baseline Score</div>'
        '<div style="margin-top:20px;">'
        '<a href="' + registry_url + '" style="display:inline-block;padding:12px 28px;background-color:#C9A84C;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#FFFFFF;text-decoration:none;">VIEW YOUR REGISTRY RECORD</a>'
        '</div></td></tr>'
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;">&nbsp;</td></tr>'
        '</table></td></tr></table></body></html>'
    )
    _send(email, subject, html)


def send_scan_alert(email, domain, score, new_issues):
    subject = 'New accessibility issues detected on ' + domain
    rows = ''.join(
        '<tr><td style="padding:9px 0;border-bottom:1px solid #F2EFE9;font-family:Georgia,serif;font-size:13px;color:#555555;">' + str(i) + '</td></tr>'
        for i in new_issues[:10]
    )
    html = (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
        '<body style="margin:0;padding:0;background-color:#F2EFE9;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#F2EFE9;">'
        '<tr><td align="center" style="padding:24px 16px;">'
        '<table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;background-color:#FFFFFF;">'
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;">&nbsp;</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#E05252;margin-bottom:7px;">SCAN ALERT</div>'
        '<div style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#0A0E1A;margin-bottom:4px;">New issues detected on ' + domain + '</div>'
        '<div style="font-family:Georgia,serif;font-size:12px;color:#AAAAAA;">Current score: ' + str(score) + '/100</div>'
        '</td></tr>'
        '<tr><td bgcolor="#FAFAF8" style="background-color:#FAFAF8;padding:22px 40px;">'
        '<table width="100%" cellpadding="0" cellspacing="0">' + rows + '</table>'
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:24px 40px;text-align:center;">'
        '<a href="https://idrshield.com/portal" style="display:inline-block;padding:12px 28px;background-color:#C9A84C;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#FFFFFF;text-decoration:none;">VIEW IN MEMBER PORTAL</a>'
        '</td></tr>'
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;">&nbsp;</td></tr>'
        '</table></td></tr></table></body></html>'
    )
    _send(email, subject, html)


def send_fix_confirmation_email(email, domain, categories, new_score):
    subject  = 'Remediation recorded \u2014 ' + domain
    cat_list = ', '.join(categories) if categories else 'General'
    html = (
        '<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
        '<body style="margin:0;padding:0;background-color:#F2EFE9;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#F2EFE9;">'
        '<tr><td align="center" style="padding:24px 16px;">'
        '<table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;background-color:#FFFFFF;">'
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;">&nbsp;</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:28px 40px;">'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:#52B788;margin-bottom:7px;">REMEDIATION CONFIRMED</div>'
        '<div style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#0A0E1A;margin-bottom:4px;">Fix recorded for ' + domain + '</div>'
        '<div style="font-family:Georgia,serif;font-size:12px;color:#AAAAAA;">Categories: ' + cat_list + '</div>'
        '</td></tr>'
        '<tr><td bgcolor="#F2EFE9" style="background-color:#F2EFE9;padding:32px 40px;text-align:center;">'
        '<div style="font-family:Georgia,serif;font-size:52px;font-weight:700;color:#52B788;line-height:1;">' + str(new_score) + '</div>'
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;color:#AAAAAA;margin-top:4px;">/ 100 &mdash; Updated Score</div>'
        '<div style="margin-top:12px;font-family:Georgia,serif;font-size:12px;font-style:italic;color:#AAAAAA;">This remediation has been logged with a timestamp in your evidence record.</div>'
        '</td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="background-color:#FFFFFF;padding:20px 40px;text-align:center;">'
        '<a href="https://idrshield.com/portal" style="display:inline-block;padding:12px 28px;background-color:#C9A84C;font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#FFFFFF;text-decoration:none;">VIEW EVIDENCE LOG</a>'
        '</td></tr>'
        '<tr><td bgcolor="#C9A84C" height="4" style="background-color:#C9A84C;font-size:0;">&nbsp;</td></tr>'
        '</table></td></tr></table></body></html>'
    )
    _send(email, subject, html)


# Backward compatibility alias
send_weekly_scan_alert = send_scan_alert
