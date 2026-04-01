"""
IDR Email Delivery — 3-Email Purchase Flow
Email 1: Free scan summary + unlock CTA (prospect)
Email 2: Founding member welcome (purchase confirmation)
Email 3: Full Defense Package PDF (purchase delivery)

SendGrid via urllib. Falls back gracefully if key not set.
"""

import os
import json
import base64
from datetime import datetime, timezone

SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'hello@idrshield.com')
FROM_NAME  = 'Institute of Digital Remediation'
GUMROAD_URL = os.environ.get('GUMROAD_URL', 'https://gum.co/idrshield')


def _send(to_email: str, subject: str, html_body: str,
          text_body: str = None, attachments: list = None) -> bool:
    if not SENDGRID_API_KEY:
        print(f"[EMAIL SKIPPED] To: {to_email} | {subject}")
        return False
    try:
        import urllib.request
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": FROM_EMAIL, "name": FROM_NAME},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_body or subject},
                {"type": "text/html",  "value": html_body}
            ]
        }
        if attachments:
            payload["attachments"] = attachments
        req = urllib.request.Request(
            'https://api.sendgrid.com/v3/mail/send',
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {SENDGRID_API_KEY}',
                'Content-Type': 'application/json'
            },
            method='POST'
        )
        with urllib.request.urlopen(req) as r:
            print(f"[EMAIL SENT] {to_email} | {subject} | status {r.status}")
            return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return False


# ────────────────────────────────────────────────────────────────────────────
# EMAIL 1 — Free Scan Summary (prospect nurture trigger)
# ────────────────────────────────────────────────────────────────────────────

def send_free_scan_summary(email: str, receipt: dict) -> bool:
    """
    Sent immediately after free scan.
    Shows summary results. Primary CTA is the $97 Founding offer.
    """
    scan = receipt.get('scan', {})
    domain     = scan.get('domain', 'your store')
    score      = scan.get('overall_score', 0)
    status     = scan.get('overall_status', 'fail').upper()
    critical   = scan.get('critical_count', 0)
    total      = scan.get('total_issues', 0)

    status_color = '#C0392B' if status == 'FAIL' else ('#E67E22' if status == 'WARNING' else '#27AE60')
    risk_level   = 'CRITICAL' if critical >= 3 else ('HIGH' if critical >= 1 else 'MODERATE')
    risk_color   = '#C0392B' if risk_level == 'CRITICAL' else ('#E67E22' if risk_level == 'HIGH' else '#D4AC0D')

    subject = f"Your free IDR scan — {domain}"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f5f5f5;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">

  <div style="background:#080d1a;padding:28px 36px;border-bottom:3px solid #C4A052;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:rgba(196,160,82,0.6);margin:0 0 6px;">Institute of Digital Remediation</p>
    <h1 style="font-size:22px;font-weight:normal;color:#F0E8D8;margin:0;">Your Free Scan Results</h1>
    <p style="font-size:12px;color:rgba(240,232,216,0.45);margin:6px 0 0;font-family:Arial,sans-serif;">{domain}</p>
  </div>

  <div style="padding:28px 36px;text-align:center;border-bottom:1px solid #f0ede6;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#999;margin:0 0 10px;">Overall Score</p>
    <div style="font-size:58px;font-weight:700;color:#080d1a;line-height:1;">{score}</div>
    <div style="font-size:14px;color:#999;margin-bottom:12px;">/ 100</div>
    <span style="background:{status_color};color:#fff;font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.1em;padding:5px 18px;border-radius:20px;">{status}</span>
    <div style="margin-top:16px;display:flex;justify-content:center;gap:24px;">
      <div style="text-align:center;">
        <div style="font-size:26px;font-weight:700;color:#C0392B;">{critical}</div>
        <div style="font-family:Arial,sans-serif;font-size:9px;letter-spacing:0.1em;text-transform:uppercase;color:#999;">Critical Issues</div>
      </div>
      <div style="text-align:center;">
        <div style="font-size:26px;font-weight:700;color:#333;">{total}</div>
        <div style="font-family:Arial,sans-serif;font-size:9px;letter-spacing:0.1em;text-transform:uppercase;color:#999;">Total Issues</div>
      </div>
      <div style="text-align:center;">
        <div style="font-size:16px;font-weight:700;color:{risk_color};">{risk_level}</div>
        <div style="font-family:Arial,sans-serif;font-size:9px;letter-spacing:0.1em;text-transform:uppercase;color:#999;">Plaintiff Risk</div>
      </div>
    </div>
  </div>

  <div style="padding:28px 36px;border-bottom:1px solid #f0ede6;">
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#333;line-height:1.7;margin:0 0 16px;">
      Plaintiff law firms use the same automated scanners to identify stores before sending demand letters.
      <strong>Typical settlement ranges in comparable cases run $25,000–$95,000.</strong>
    </p>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#555;line-height:1.7;margin:0;">
      Your full Defense Package — including remediation code, plaintiff simulation,
      comparable case law, and your SHA-256 tamper-evident Scan Receipt — is waiting.
    </p>
  </div>

  <div style="padding:28px 36px;background:#fafaf5;border-bottom:1px solid #e8e4dc;text-align:center;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#C4A052;margin:0 0 8px;">Founding Member Offer</p>
    <p style="font-size:22px;font-weight:700;color:#080d1a;margin:0 0 4px;">$97 — Everything Included</p>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:#888;margin:0 0 16px;">Book · Full Defense Package · 30 days free · then $29/month forever</p>
    <a href="{GUMROAD_URL}" style="display:inline-block;background:#C4A052;color:#080d1a;font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;padding:14px 32px;text-decoration:none;">Unlock Your Defense Package →</a>
    <p style="font-family:Arial,sans-serif;font-size:11px;color:#aaa;margin:12px 0 0;">First 500 stores only. After that: $127 activation + $39/month.</p>
  </div>

  <div style="padding:20px 36px;background:#080d1a;">
    <p style="font-family:Arial,sans-serif;font-size:10px;color:rgba(240,232,216,0.35);margin:0;line-height:1.6;">
      Institute of Digital Remediation · idrshield.com · hello@idrshield.com<br>
      Ranges cited reflect typical cases observed in comparable accessibility claims and are not a prediction of any specific legal action.
    </p>
  </div>

</div>
</body></html>"""

    text = f"""IDR FREE SCAN RESULTS
{domain}

Score: {score}/100 — {status}
Critical Issues: {critical}
Total Issues: {total}
Plaintiff Risk: {risk_level}

Your full Defense Package is waiting.

Unlock Founders Pricing — $97 (first 500 only)
Includes: Book · Full Defense PDF · 30 days free · $29/month forever

{GUMROAD_URL}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ────────────────────────────────────────────────────────────────────────────
# EMAIL 2 — Founding Member Welcome (elite membership)
# ────────────────────────────────────────────────────────────────────────────

def send_founding_member_welcome(email: str, receipt: dict) -> bool:
    """
    Sent immediately on purchase. Elite membership confirmation.
    No PDF yet — that arrives in Email 3.
    """
    scan       = receipt.get('scan', {})
    domain     = scan.get('domain', 'your store')
    registry_id = receipt.get('registry_id', '')
    registry_url = receipt.get('registry_url', '')

    subject = f"Welcome to IDR Shield — You're a Founding Member"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f5f5f5;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">

  <div style="background:#080d1a;padding:32px 36px;border-bottom:3px solid #C4A052;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.25em;text-transform:uppercase;color:rgba(196,160,82,0.6);margin:0 0 8px;">Institute of Digital Remediation</p>
    <h1 style="font-size:26px;font-weight:normal;color:#F0E8D8;margin:0 0 6px;">Founding Member Confirmed</h1>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:rgba(240,232,216,0.45);margin:0;">IDR Shield · {domain}</p>
  </div>

  <div style="padding:32px 36px;border-bottom:1px solid #f0ede6;">
    <p style="font-size:16px;color:#1a1a1a;line-height:1.7;margin:0 0 16px;">
      You are one of the first 500 stores to join IDR Shield. That number will not grow.
    </p>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#555;line-height:1.7;margin:0;">
      Your store is now in the IDR Registry. Your rate of $29/month is locked permanently —
      it will never increase regardless of what we charge in the future.
    </p>
  </div>

  <div style="padding:24px 36px;background:#fafaf5;border-bottom:1px solid #e8e4dc;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#C4A052;margin:0 0 16px;">Your Founding Member Perks</p>
    <table style="width:100%;border-collapse:collapse;">
      <tr><td style="padding:8px 0;border-bottom:1px solid #eee;font-family:Arial,sans-serif;font-size:13px;color:#333;">✓ Full 10-section Defense Package PDF</td></tr>
      <tr><td style="padding:8px 0;border-bottom:1px solid #eee;font-family:Arial,sans-serif;font-size:13px;color:#333;">✓ SHA-256 tamper-evident Scan Receipt</td></tr>
      <tr><td style="padding:8px 0;border-bottom:1px solid #eee;font-family:Arial,sans-serif;font-size:13px;color:#333;">✓ IDR Registry entry — publicly verifiable</td></tr>
      <tr><td style="padding:8px 0;border-bottom:1px solid #eee;font-family:Arial,sans-serif;font-size:13px;color:#333;">✓ IDR Verified badge for your store footer</td></tr>
      <tr><td style="padding:8px 0;border-bottom:1px solid #eee;font-family:Arial,sans-serif;font-size:13px;color:#333;">✓ Weekly automated rescans</td></tr>
      <tr><td style="padding:8px 0;border-bottom:1px solid #eee;font-family:Arial,sans-serif;font-size:13px;color:#333;">✓ Immediate alert if new violations detected</td></tr>
      <tr><td style="padding:8px 0;font-family:Arial,sans-serif;font-size:13px;color:#C4A052;font-weight:700;">✓ $29/month — locked for life</td></tr>
    </table>
  </div>

  <div style="padding:24px 36px;border-bottom:1px solid #f0ede6;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#999;margin:0 0 8px;">Registry ID</p>
    <p style="font-family:'Courier New',monospace;font-size:13px;color:#333;margin:0 0 16px;">{registry_id}</p>
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#999;margin:0 0 8px;">Registry Record</p>
    <a href="{registry_url}" style="font-family:Arial,sans-serif;font-size:13px;color:#0645AD;">{registry_url}</a>
  </div>

  <div style="padding:24px 36px;background:#fafaf5;border-bottom:1px solid #e8e4dc;">
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#333;line-height:1.7;margin:0 0 12px;">
      <strong>Your full Defense Package is on its way.</strong> You will receive a second email
      in the next minute with your complete 10-section PDF — including your remediation
      instructions, plaintiff simulation, and SHA-256 receipt.
    </p>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:#888;margin:0;">
      While you wait — your Registry record is already live at the link above.
    </p>
  </div>

  <div style="padding:20px 36px;background:#080d1a;">
    <p style="font-family:Arial,sans-serif;font-size:10px;color:rgba(240,232,216,0.35);margin:0;line-height:1.6;">
      Institute of Digital Remediation · idrshield.com · hello@idrshield.com<br>
      IDR-PROTOCOL-2026 · This is not legal advice.
    </p>
  </div>

</div>
</body></html>"""

    text = f"""FOUNDING MEMBER CONFIRMED
Institute of Digital Remediation

You are one of the first 500 stores to join IDR Shield.
Your $29/month rate is locked permanently.

Registry ID: {registry_id}
Registry: {registry_url}

Your full Defense Package PDF is arriving in the next email.

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ────────────────────────────────────────────────────────────────────────────
# EMAIL 3 — Full Defense Package PDF
# ────────────────────────────────────────────────────────────────────────────

def send_defense_package_pdf(email: str, receipt: dict) -> bool:
    """
    Sent ~1 minute after Email 2.
    Contains the full 10-section Defense Package as PDF attachment.
    """
    scan       = receipt.get('scan', {})
    domain     = scan.get('domain', 'your store')
    score      = scan.get('overall_score', 0)
    status     = scan.get('overall_status', 'fail').upper()
    receipt_id = receipt.get('receipt_id', '')

    # Generate PDF
    attachments = []
    try:
        from receipt.pdf_generator import generate_pdf
        pdf_bytes = generate_pdf(receipt)
        pdf_b64   = base64.b64encode(pdf_bytes).decode('utf-8')
        filename  = f"IDR-Defense-Package-{domain}-{receipt_id[:8]}.pdf"
        attachments = [{
            "content":     pdf_b64,
            "type":        "application/pdf",
            "filename":    filename,
            "disposition": "attachment"
        }]
        print(f"[EMAIL] PDF attached: {filename} ({len(pdf_bytes):,} bytes)")
    except Exception as e:
        print(f"[EMAIL] PDF generation failed: {e}")

    status_color = '#C0392B' if status == 'FAIL' else ('#E67E22' if status == 'WARNING' else '#27AE60')
    subject = f"Your IDR Defense Package — {domain}"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f5f5f5;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">

  <div style="background:#080d1a;padding:28px 36px;border-bottom:3px solid #C4A052;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:rgba(196,160,82,0.6);margin:0 0 6px;">Institute of Digital Remediation</p>
    <h1 style="font-size:22px;font-weight:normal;color:#F0E8D8;margin:0;">Your Defense Package</h1>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:rgba(240,232,216,0.45);margin:6px 0 0;">{domain} · Score: {score}/100 · <span style="color:{'#C0392B' if status=='FAIL' else '#27AE60'}">{status}</span></p>
  </div>

  <div style="padding:28px 36px;border-bottom:1px solid #f0ede6;">
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#333;line-height:1.7;margin:0 0 12px;">
      Your full 10-section IDR Defense Package is attached to this email.
    </p>
    <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§01 · IDR Letterhead & Receipt ID</td></tr>
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§02 · Store Identity Record</td></tr>
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§03 · Executive Summary & Risk Assessment</td></tr>
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§04 · Full Category Breakdown</td></tr>
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§05 · Plaintiff Simulation Report</td></tr>
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§06 · Remediation Guidance (before/after code)</td></tr>
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§07 · Evidence Log Chain</td></tr>
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§08 · SHA-256 Verification Block</td></tr>
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§09 · Registry Record</td></tr>
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§10 · Legal Positioning Statement</td></tr>
    </table>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:#888;margin:0;">
      Receipt ID: <span style="font-family:'Courier New',monospace;">{receipt_id}</span>
    </p>
  </div>

  <div style="padding:24px 36px;background:#fafaf5;border-bottom:1px solid #e8e4dc;">
    <p style="font-family:Arial,sans-serif;font-size:12px;color:#555;line-height:1.7;margin:0 0 10px;"><strong>Next step:</strong> Add your IDR Verified badge to your store footer.</p>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:#555;line-height:1.7;margin:0;">Instructions and your badge embed code are in §09 of the PDF, or visit <a href="https://idrshield.com" style="color:#C4A052;">idrshield.com</a>.</p>
  </div>

  <div style="padding:20px 36px;background:#080d1a;">
    <p style="font-family:Arial,sans-serif;font-size:10px;color:rgba(240,232,216,0.35);margin:0;line-height:1.6;">
      Institute of Digital Remediation · idrshield.com · hello@idrshield.com<br>
      IDR-PROTOCOL-2026 · This is not legal advice.
    </p>
  </div>

</div>
</body></html>"""

    text = f"""YOUR IDR DEFENSE PACKAGE
{domain} · {score}/100 · {status}

Your full 10-section Defense Package is attached.

Receipt ID: {receipt_id}

Next step: Add your IDR Verified badge to your store footer.
Instructions are in §09 of the attached PDF.

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text, attachments=attachments)


# ────────────────────────────────────────────────────────────────────────────
# Convenience wrappers (used by app.py and cron)
# ────────────────────────────────────────────────────────────────────────────

def send_badge_setup(email: str, receipt: dict) -> bool:
    """
    Email 4 — Badge setup instructions.
    Sent after the Defense Package. Covers both HTML embed and PNG image options.
    """
    scan        = receipt.get('scan', {})
    domain      = scan.get('domain', 'your store')
    registry_id = receipt.get('registry_id', '')
    registry_url = receipt.get('registry_url', '')

    badge_code = (
        f'&lt;script src="https://idrshield.com/badge.js"<br>'
        f'&nbsp;&nbsp;data-store="{domain}"<br>'
        f'&nbsp;&nbsp;data-registry="{registry_id}"&gt;<br>'
        f'&lt;/script&gt;'
    )

    subject = f"Add your IDR Verified badge — {domain}"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f5f5f5;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">

  <div style="background:#080d1a;padding:28px 36px;border-bottom:3px solid #C4A052;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.25em;text-transform:uppercase;color:rgba(196,160,82,0.6);margin:0 0 6px;">Institute of Digital Remediation</p>
    <h1 style="font-size:22px;font-weight:normal;color:#F0E8D8;margin:0;">Add Your IDR Verified Badge</h1>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:rgba(240,232,216,0.45);margin:6px 0 0;">{domain}</p>
  </div>

  <div style="padding:24px 36px;border-bottom:1px solid #f0ede6;">
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#333;line-height:1.7;margin:0;">
      Your IDR Verified badge is live and ready. Every visitor who clicks it sees your
      publicly verifiable registry record — proof your store takes accessibility seriously.
      Choose the installation method that matches your setup below.
    </p>
  </div>

  <!-- OPTION A: Code embed -->
  <div style="padding:24px 36px;border-bottom:1px solid #f0ede6;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#C4A052;margin:0 0 6px;">Option A — For Custom / Coded Stores</p>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#333;line-height:1.7;margin:0 0 12px;">
      Paste this code snippet into your store footer HTML. Works on Shopify (theme.liquid), WooCommerce, and any custom site.
    </p>
    <div style="background:#0d1526;padding:16px;border-radius:4px;border-left:3px solid #C4A052;margin-bottom:12px;">
      <code style="font-family:'Courier New',monospace;font-size:11px;color:#C8E6C9;line-height:1.8;">
        {badge_code}
      </code>
    </div>
    <p style="font-family:Arial,sans-serif;font-size:11px;color:#888;margin:0;">
      The badge loads automatically, shows your live compliance status, and links to your registry record.
    </p>
  </div>

  <!-- OPTION B: Shopify step by step -->
  <div style="padding:24px 36px;border-bottom:1px solid #f0ede6;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#C4A052;margin:0 0 6px;">Option B — Shopify (Step by Step)</p>
    <ol style="font-family:Arial,sans-serif;font-size:13px;color:#333;line-height:2;margin:0;padding-left:20px;">
      <li>Go to <strong>Online Store → Themes → Edit Code</strong></li>
      <li>Open <strong>Sections → footer.liquid</strong> (or footer-group.json)</li>
      <li>Paste the code above just before the closing <code style="background:#f0f0f0;padding:1px 4px;">&lt;/footer&gt;</code> tag</li>
      <li>Click <strong>Save</strong></li>
      <li>Visit your store — the IDR badge will appear in your footer</li>
    </ol>
  </div>

  <!-- OPTION C: Drag and drop / image -->
  <div style="padding:24px 36px;border-bottom:1px solid #f0ede6;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#C4A052;margin:0 0 6px;">Option C — Drag & Drop Builders (Wix, Squarespace, Webflow)</p>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#333;line-height:1.7;margin:0 0 12px;">
      If your website builder doesn't support custom code in the footer, use the badge image instead:
    </p>
    <ol style="font-family:Arial,sans-serif;font-size:13px;color:#333;line-height:2;margin:0 0 12px;padding-left:20px;">
      <li>Download your IDR badge image from: <a href="https://idrshield.com/badge-image/{domain}" style="color:#C4A052;">idrshield.com/badge-image/{domain}</a></li>
      <li>Upload the image to your website footer section</li>
      <li>Set the image link to: <strong>{registry_url}</strong></li>
      <li>Alt text: <em>IDR Verified — Accessibility Compliance Badge</em></li>
    </ol>
    <p style="font-family:Arial,sans-serif;font-size:11px;color:#888;margin:0;">
      The image badge is static — it displays your verified status as of your last scan.
      The code version updates automatically with every weekly scan.
    </p>
  </div>

  <!-- Registry verification -->
  <div style="padding:24px 36px;background:#fafaf5;border-bottom:1px solid #e8e4dc;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#999;margin:0 0 8px;">Your Registry Record</p>
    <a href="{registry_url}" style="font-family:Arial,sans-serif;font-size:13px;color:#0645AD;">{registry_url}</a>
    <p style="font-family:Arial,sans-serif;font-size:11px;color:#888;margin:8px 0 0;">
      This is the page your badge links to. Share it with customers, legal counsel, or anyone who asks about your accessibility compliance.
    </p>
  </div>

  <div style="padding:16px 36px;background:#080d1a;">
    <p style="font-family:Arial,sans-serif;font-size:10px;color:rgba(240,232,216,0.35);margin:0;line-height:1.6;">
      Institute of Digital Remediation · idrshield.com · hello@idrshield.com<br>
      IDR-PROTOCOL-2026 · This is not legal advice.
    </p>
  </div>

</div>
</body></html>"""

    text = f"""ADD YOUR IDR VERIFIED BADGE
{domain}

OPTION A — Code embed (Shopify / custom sites)
Paste into your footer HTML:
<script src="https://idrshield.com/badge.js"
  data-store="{domain}"
  data-registry="{registry_id}">
</script>

OPTION B — Shopify step by step
1. Online Store → Themes → Edit Code
2. Open Sections → footer.liquid
3. Paste the code above before </footer>
4. Save

OPTION C — Drag & drop (Wix, Squarespace, Webflow)
Download badge image: https://idrshield.com/badge-image/{domain}
Upload to footer, link to: {registry_url}

Registry: {registry_url}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


def send_activation_receipt(email: str, receipt: dict) -> bool:
    """
    Full purchase flow — fired by Gumroad webhook.
    Email 2: Founding Member Welcome (fires immediately)
    Email 3: Defense Package PDF (fires after 90 second delay)
    Email 4: Badge Setup (fires after another 90 second delay)
    """
    import threading

    # Email 2 — fires immediately
    send_founding_member_welcome(email, receipt)

    # Email 3 — fires after 90 seconds in background thread
    def send_pdf_delayed():
        import time
        time.sleep(90)
        send_defense_package_pdf(email, receipt)

    # Email 4 — fires after 3 minutes in background thread
    def send_badge_delayed():
        import time
        time.sleep(180)
        send_badge_setup(email, receipt)

    threading.Thread(target=send_pdf_delayed, daemon=True).start()
    threading.Thread(target=send_badge_delayed, daemon=True).start()

    return True


def send_scan_alert(email: str, domain: str,
                    scanner_ip: str, findings: dict) -> bool:
    """Alert when unknown party scans an enrolled store."""
    score    = findings.get('overall_score', 0)
    critical = findings.get('critical_count', 0)
    total    = findings.get('total_issues', 0)
    subject  = f"⚠️ Your store was scanned by an unknown party — {domain}"

    html = f"""<!DOCTYPE html>
<html><body style="font-family:Georgia,serif;background:#f5f5f5;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">
  <div style="background:#080d1a;padding:28px 36px;border-bottom:3px solid #C0392B;">
    <h1 style="font-size:20px;font-weight:normal;color:#F0E8D8;margin:0;">⚠️ External Scan Detected</h1>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:rgba(240,232,216,0.5);margin:6px 0 0;">{domain}</p>
  </div>
  <div style="padding:28px 36px;">
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#333;line-height:1.7;margin:0 0 12px;">
      An automated accessibility scan was run against <strong>{domain}</strong>.
      Score: <strong>{score}/100</strong> · Critical: <strong>{critical}</strong> · Total: <strong>{total}</strong>
    </p>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#555;line-height:1.7;margin:0 0 16px;">
      Plaintiff firms use automated scanners like this to identify targets before sending demand letters.
      Your IDR Shield is monitoring and your compliance record is up to date.
    </p>
    <a href="https://idrshield.com" style="background:#C4A052;color:#080d1a;font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.1em;padding:12px 24px;text-decoration:none;display:inline-block;">VIEW REGISTRY RECORD</a>
  </div>
  <div style="padding:16px 36px;background:#f9f9f9;border-top:1px solid #eee;">
    <p style="font-family:Arial,sans-serif;font-size:10px;color:#999;margin:0;">Institute of Digital Remediation · idrshield.com</p>
  </div>
</div>
</body></html>"""

    return _send(email, subject, html)


def send_weekly_scan_alert(email: str, domain: str,
                           new_issues: list, receipt_id: str) -> bool:
    """Weekly rescan alert — new issues found."""
    count   = len(new_issues)
    subject = f"IDR Weekly Scan — {count} new issue{'s' if count != 1 else ''} on {domain}"

    html = f"""<!DOCTYPE html>
<html><body style="font-family:Georgia,serif;background:#f5f5f5;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">
  <div style="background:#080d1a;padding:28px 36px;border-bottom:3px solid #C4A052;">
    <p style="font-family:Arial,sans-serif;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:rgba(196,160,82,0.6);margin:0 0 6px;">IDR Weekly Scan</p>
    <h1 style="font-size:20px;font-weight:normal;color:#F0E8D8;margin:0;">{count} New Issue{'s' if count != 1 else ''} Detected</h1>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:rgba(240,232,216,0.45);margin:6px 0 0;">{domain}</p>
  </div>
  <div style="padding:28px 36px;">
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#333;line-height:1.7;margin:0 0 16px;">
      Your weekly IDR scan found {count} new accessibility issue{'s' if count != 1 else ''} not present in your previous scan.
    </p>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:#888;margin:0 0 16px;">Receipt ID: <span style="font-family:'Courier New',monospace;">{receipt_id}</span></p>
    <a href="https://idrshield.com" style="background:#C4A052;color:#080d1a;font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.1em;padding:12px 24px;text-decoration:none;display:inline-block;">VIEW FULL REPORT</a>
  </div>
  <div style="padding:16px 36px;background:#f9f9f9;border-top:1px solid #eee;">
    <p style="font-family:Arial,sans-serif;font-size:10px;color:#999;margin:0;">Institute of Digital Remediation · idrshield.com</p>
  </div>
</div>
</body></html>"""

    return _send(email, subject, html)
