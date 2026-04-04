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
GUMROAD_URL = 'https://idrshield.gumroad.com/l/oadcfq'


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
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#555;line-height:1.7;margin:0 0 14px;">
      Your store is now in the IDR Registry. Your rate of $29/month is locked permanently —
      it will never increase regardless of what we charge in the future.
    </p>
    <p style="font-family:Georgia,serif;font-size:15px;color:#1a1a1a;line-height:1.7;margin:0;font-style:italic;border-left:3px solid #C4A052;padding-left:16px;">
      Most stores never take this step — you just put yourself ahead of them.
    </p>
  </div>

  <div style="padding:24px 36px;background:#fafaf5;border-bottom:1px solid #e8e4dc;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#C4A052;margin:0 0 16px;">Your Founding Member Perks</p>
    <table style="width:100%;border-collapse:collapse;">
      <tr><td style="padding:8px 0;border-bottom:1px solid #eee;font-family:Arial,sans-serif;font-size:13px;color:#C4A052;font-weight:700;">✓ The 2026 Accessibility Shield — full digital book</td></tr>
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
    <p style="font-family:Georgia,serif;font-size:16px;color:#1a1a1a;line-height:1.75;margin:0 0 18px;font-style:italic;border-left:3px solid #C4A052;padding-left:16px;">
      You now have something most stores don't: a documented, timestamped defense record.
    </p>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#333;line-height:1.7;margin:0 0 6px;">
      Your full 10-section IDR Defense Package is attached to this email.
    </p>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:#888;line-height:1.6;margin:0 0 16px;">
      You don't need to understand everything in this report — what matters is that your store now has a documented compliance record that precedes any potential demand letter.
    </p>
    <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§01 · IDR Letterhead &amp; Receipt ID</td></tr>
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§02 · Store Identity Record</td></tr>
      <tr><td style="padding:5px 0;font-family:Arial,sans-serif;font-size:12px;color:#555;">§03 · Executive Summary &amp; Risk Assessment</td></tr>
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

def send_activation_receipt(email: str, receipt: dict) -> bool:
    """
    Full purchase flow: Email 2 + Email 3.
    Called by Gumroad webhook after successful payment.
    """
    send_founding_member_welcome(email, receipt)
    send_defense_package_pdf(email, receipt)
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


def send_free_summary_email(email: str, receipt: dict) -> bool:
    """
    Free visitor summary email — critic-upgraded conversion copy.
    Emotional arc: realization → consequence → certainty → CTA.
    """
    scan         = receipt.get('scan', {})
    domain       = scan.get('domain', 'your store')
    score        = scan.get('overall_score', 0)
    status       = scan.get('overall_status', 'fail').upper()
    critical     = scan.get('critical_count', 0)
    total        = scan.get('total_issues', 0)
    cats         = scan.get('categories', [])
    receipt_id   = receipt.get('receipt_id', '')
    registry_url = receipt.get('registry_url', f'https://idrshield.com/verify/{domain}')
    gumroad_url  = 'https://idrshield.gumroad.com/l/oadcfq'

    # Subject line — specific, personal, urgent
    if critical >= 5:
        subject = f'Your store flagged {critical} critical ADA issues — {domain}'
    elif critical >= 1:
        subject = f'Your store flagged {critical} critical ADA issue{"s" if critical != 1 else ""} — {domain}'
    elif total >= 1:
        subject = f'Your IDR scan result — {domain}'
    else:
        subject = f'Your store passed — {domain}'

    # Risk line — critic upgrade: trigger consequence, not just description
    if critical >= 3:
        risk_line = f'<strong style="color:#D94F4F;">{critical} critical issues detected</strong> — this is exactly the type of profile plaintiff scanners target first.'
        risk_color = '#D94F4F'
    elif critical >= 1:
        risk_line = f'<strong style="color:#D97B2F;">{critical} critical issue{"s" if critical != 1 else ""} detected</strong> — elevated plaintiff risk profile.'
        risk_color = '#D97B2F'
    elif total >= 1:
        risk_line = f'No critical issues — but {total} issue{"s" if total != 1 else ""} found that should be addressed before someone else runs this scan.'
        risk_color = '#C9A84C'
    else:
        risk_line = 'No accessibility issues detected. Your store is clean.'
        risk_color = '#27AE60'

    status_color = '#D94F4F' if status == 'FAIL' else ('#D97B2F' if status == 'WARNING' else '#27AE60')

    # Category rows
    cat_rows_html = ''
    for cat in cats[:5]:
        failed = cat.get('failed', 0)
        if failed == 0:
            dot_color, count_str, count_color = '#27AE60', 'Clean', '#27AE60'
        elif cat.get('score', 100) < 70:
            dot_color, count_str, count_color = '#D94F4F', f'{failed} issue{"s" if failed != 1 else ""}', '#D94F4F'
        else:
            dot_color, count_str, count_color = '#D97B2F', f'{failed} issue{"s" if failed != 1 else ""}', '#D97B2F'
        cat_rows_html += f'''
        <tr>
          <td style="padding:11px 0;border-bottom:1px solid #f0f0f0;font-family:Arial,sans-serif;font-size:14px;color:#222;">
            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dot_color};margin-right:10px;vertical-align:middle;flex-shrink:0;"></span>
            {cat.get('name', '')}
          </td>
          <td style="padding:11px 0;border-bottom:1px solid #f0f0f0;text-align:right;font-family:Arial,sans-serif;font-size:13px;color:{count_color};font-weight:600;">{count_str}</td>
        </tr>'''

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:Georgia,serif;background:#f0ede6;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #ddd;">

  <!-- Header -->
  <div style="background:#07091A;padding:32px 40px;border-bottom:3px solid #C9A84C;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:rgba(201,168,76,0.65);margin:0 0 8px;">Institute of Digital Remediation</p>
    <h1 style="font-family:Georgia,serif;font-size:24px;font-weight:normal;color:#F0E8D4;margin:0 0 4px;">Your Store Scan Results</h1>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:rgba(240,232,212,0.45);margin:0;">{domain}</p>
  </div>

  <!-- Score -->
  <div style="background:#0C0F22;padding:32px 40px;border-bottom:1px solid rgba(201,168,76,0.2);text-align:center;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:rgba(201,168,76,0.6);margin:0 0 12px;">Overall Score</p>
    <div style="font-family:Georgia,serif;font-size:72px;font-weight:700;color:#F0E8D4;line-height:1;">{score}</div>
    <div style="font-family:Georgia,serif;font-size:22px;color:rgba(240,232,212,0.3);margin-bottom:14px;">/ 100</div>
    <span style="background:{status_color};color:#fff;font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;padding:5px 18px;border-radius:20px;">{status}</span>
    <p style="font-family:Arial,sans-serif;font-size:14px;color:rgba(240,232,212,0.7);margin:16px 0 0;line-height:1.65;">{risk_line}</p>
    {f'<p style="font-family:Arial,sans-serif;font-size:13px;color:rgba(240,232,212,0.55);margin:10px 0 0;line-height:1.65;">{critical} critical issues is not minor — it places your store in a high-risk category for automated demand targeting.</p>' if critical >= 1 else ''}
  </div>

  <!-- Issue breakdown -->
  <div style="padding:28px 40px;border-bottom:1px solid #ebebeb;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#999;margin:0 0 16px;">Issue Breakdown</p>
    <table style="width:100%;border-collapse:collapse;">
      {cat_rows_html}
    </table>
  </div>

  <!-- Consequence block — critic: "what happens if you do nothing" -->
  <div style="padding:28px 40px;background:#faf8f4;border-bottom:1px solid #ebebeb;">
    <p style="font-family:Georgia,serif;font-size:16px;color:#1a1a1a;line-height:1.75;margin:0 0 14px;">
      Most store owners only discover these issues after receiving a legal notice.
    </p>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#555;line-height:1.75;margin:0;">
      At that point, the cost is no longer optional. Typical settlement ranges in comparable cases run <strong>$25,000–$95,000</strong> — resolved quietly, quickly, without warning.
    </p>
  </div>

  <!-- Locked teaser -->
  <div style="padding:28px 40px;border-bottom:1px solid #ebebeb;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#999;margin:0 0 14px;">What you're seeing here is only the surface</p>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#444;line-height:1.9;margin:0;">
      🔒 &nbsp;Full 10-section Defense Package PDF<br>
      🔒 &nbsp;Step-by-step remediation code for every issue<br>
      🔒 &nbsp;Plaintiff simulation — exactly how a law firm scores your store<br>
      🔒 &nbsp;Legal positioning documentation<br>
      🔒 &nbsp;SHA-256 tamper-proof Scan Receipt — your immutable evidence record<br>
      🔒 &nbsp;IDR Verified badge + weekly automated monitoring
    </p>
  </div>

  <!-- Book section -->
  <div style="padding:28px 40px;background:#07091A;border-bottom:1px solid rgba(201,168,76,0.2);">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:rgba(201,168,76,0.6);margin:0 0 10px;">Included with Founding Membership</p>
    <p style="font-family:Georgia,serif;font-size:17px;font-weight:normal;color:#F0E8D4;margin:0 0 6px;">The 2026 Accessibility Shield</p>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:rgba(240,232,212,0.5);margin:0 0 16px;font-style:italic;">ADA Website Lawsuit Defense for Online Store Owners</p>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:rgba(240,232,212,0.65);line-height:1.8;margin:0;">
      &#x2022; &nbsp;How plaintiff firms scan and identify targets — and how to not be one<br>
      &#x2022; &nbsp;The exact documentation that gives you a defensible compliance posture<br>
      &#x2022; &nbsp;How to become a hard target before a demand letter arrives
    </p>
  </div>

  <!-- Founding member benefits -->
  <div style="padding:28px 40px;background:#faf8f4;border-bottom:1px solid #ebebeb;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#C9A84C;margin:0 0 16px;">Founding Member Benefits</p>
    <table style="width:100%;border-collapse:collapse;">
      <tr><td style="padding:8px 0;border-bottom:1px solid #ebebeb;font-family:Arial,sans-serif;font-size:13px;color:#333;">&#x2713; &nbsp;The 2026 Accessibility Shield — full digital book</td></tr>
      <tr><td style="padding:8px 0;border-bottom:1px solid #ebebeb;font-family:Arial,sans-serif;font-size:13px;color:#333;">&#x2713; &nbsp;10-section legal-grade Defense Package PDF</td></tr>
      <tr><td style="padding:8px 0;border-bottom:1px solid #ebebeb;font-family:Arial,sans-serif;font-size:13px;color:#333;">&#x2713; &nbsp;SHA-256 Scan Receipt — cryptographic compliance proof</td></tr>
      <tr><td style="padding:8px 0;border-bottom:1px solid #ebebeb;font-family:Arial,sans-serif;font-size:13px;color:#333;">&#x2713; &nbsp;IDR Registry entry — publicly verifiable</td></tr>
      <tr><td style="padding:8px 0;border-bottom:1px solid #ebebeb;font-family:Arial,sans-serif;font-size:13px;color:#333;">&#x2713; &nbsp;IDR Verified badge for your store footer</td></tr>
      <tr><td style="padding:8px 0;border-bottom:1px solid #ebebeb;font-family:Arial,sans-serif;font-size:13px;color:#333;">&#x2713; &nbsp;Weekly automated rescans + immediate violation alerts</td></tr>
      <tr><td style="padding:8px 0;font-family:Arial,sans-serif;font-size:13px;color:#C9A84C;font-weight:700;">&#x2713; &nbsp;$29/month — locked permanently for founding members</td></tr>
    </table>
  </div>

  <!-- Closer — critic: "this is happening whether you act or not" -->
  <div style="padding:28px 40px;border-bottom:1px solid #ebebeb;text-align:center;">
    <p style="font-family:Georgia,serif;font-size:16px;color:#1a1a1a;line-height:1.75;margin:0 0 8px;">
      The Defense Package doesn't just show you the issues —
    </p>
    <p style="font-family:Georgia,serif;font-size:16px;color:#1a1a1a;line-height:1.75;margin:0 0 20px;">
      it gives you the exact documentation, proof, and positioning to protect your store if it's ever challenged.
    </p>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#555;font-style:italic;margin:0 0 10px;line-height:1.7;">
      This is exactly the moment most stores ignore — and regret later.
    </p>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#777;font-style:italic;margin:0 0 24px;line-height:1.7;">
      Your store can be scanned at any time — by anyone.<br>
      The only question is whether you see the results first&hellip; or they do.
    </p>
    <a href="{gumroad_url}" style="display:inline-block;background:#C9A84C;color:#07091A;font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;padding:16px 40px;text-decoration:none;border-radius:3px;">
      Activate Founding Membership &mdash; $97
    </a>
    <p style="font-family:Arial,sans-serif;font-size:11px;color:#aaa;margin:12px 0 0;">Limited to the first 500 stores &nbsp;&#xB7;&nbsp; 30 days free &nbsp;&#xB7;&nbsp; $29/month locked forever</p>
  </div>

  <!-- Registry -->
  <div style="padding:20px 40px;border-bottom:1px solid #ebebeb;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#999;margin:0 0 6px;">Your Public Registry Record</p>
    <a href="{registry_url}" style="color:#C9A84C;font-family:Arial,sans-serif;font-size:13px;text-decoration:none;">{registry_url}</a>
    <p style="font-family:Arial,sans-serif;font-size:11px;color:#bbb;margin:5px 0 0;">Publicly verifiable. Anyone can confirm your compliance record.</p>
  </div>

  <!-- Footer -->
  <div style="padding:20px 40px;background:#07091A;">
    <p style="font-family:Arial,sans-serif;font-size:11px;color:rgba(240,232,212,0.3);margin:0;line-height:1.7;">
      Scan Receipt: {receipt_id[:16] if receipt_id else 'N/A'}&hellip; &nbsp;&#xB7;&nbsp; Institute of Digital Remediation &nbsp;&#xB7;&nbsp; idrshield.com<br>
      Not a law firm. This is a compliance documentation system.<br>
      Settlement ranges cited reflect publicly available case data and are not a prediction of any specific legal action.
    </p>
  </div>

</div>
</body>
</html>"""

    text = f"""IDR SCAN RESULTS — {domain}

Score: {score}/100 — {status}
Critical Issues: {critical} | Total Issues: {total}

{critical} critical issues detected — this is exactly the type of profile plaintiff scanners target first.

---

ISSUE BREAKDOWN:
{chr(10).join([f"  {c.get('name','')}: {'Clean' if c.get('failed',0)==0 else str(c.get('failed',0))+' issue(s)'}" for c in cats[:5]])}

---

Most store owners only discover these issues after receiving a legal notice.
At that point, the cost is no longer optional.

---

INCLUDED WITH FOUNDING MEMBERSHIP:

The 2026 Accessibility Shield (book)
- How plaintiff firms identify targets — and how to not be one
- The exact documentation that gives you a defensible compliance posture
- How to become a hard target before a demand letter arrives

+ 10-section Defense Package PDF
+ SHA-256 Scan Receipt
+ IDR Registry entry
+ IDR Verified badge
+ Weekly rescans + violation alerts
+ $29/month — locked permanently

---

Your store can be scanned at any time — by anyone.
The only question is whether you see the results first... or they do.

Activate Founding Membership — $97
Limited to the first 500 stores · 30 days free · $29/month locked forever

{gumroad_url}

---

Your Registry Record: {registry_url}
Scan Receipt: {receipt_id[:16] if receipt_id else 'N/A'}

Institute of Digital Remediation · idrshield.com
Not a law firm. This is a compliance documentation system.
"""

    return _send(email, subject, html, text)


# ────────────────────────────────────────────────────────────────────────────
# Fix Confirmation Email — sent after confirmation scan completes
# ────────────────────────────────────────────────────────────────────────────

def send_fix_confirmation_email(email: str, domain: str, result: dict) -> bool:
    """
    Sent to merchant after a confirmation scan resolves their reported fixes.
    Shows which issues were confirmed fixed, still present, or newly detected.
    """
    confirmed  = result.get('confirmed_fixed', [])
    still_open = result.get('still_present', [])
    new_issues = result.get('new_issues', [])
    new_score  = result.get('new_score', 0)
    old_score  = result.get('original_score', 0)
    delta      = result.get('score_delta', 0)
    delta_sign = '+' if delta >= 0 else ''

    subject = f"IDR Confirmation Scan — {domain}"

    confirmed_rows  = ''.join(
        f'<tr><td style="padding:6px 0;border-bottom:1px solid #f0f0f0;font-family:Arial,sans-serif;font-size:13px;color:#27AE60;">✓ {c.get("rule_id","")}</td></tr>'
        for c in confirmed
    ) or '<tr><td style="padding:6px 0;font-family:Arial,sans-serif;font-size:13px;color:#999;">No issues confirmed fixed yet.</td></tr>'

    open_rows = ''.join(
        f'<tr><td style="padding:6px 0;border-bottom:1px solid #f0f0f0;font-family:Arial,sans-serif;font-size:13px;color:#E67E22;">⚠ {s.get("rule_id","")}</td></tr>'
        for s in still_open
    )

    new_rows = ''.join(
        f'<tr><td style="padding:6px 0;border-bottom:1px solid #f0f0f0;font-family:Arial,sans-serif;font-size:13px;color:#C0392B;">✗ {n.get("rule_id","")}</td></tr>'
        for n in new_issues
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f5f5f5;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">

  <div style="background:#080d1a;padding:28px 36px;border-bottom:3px solid #C4A052;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:rgba(196,160,82,0.6);margin:0 0 6px;">Institute of Digital Remediation</p>
    <h1 style="font-size:22px;font-weight:normal;color:#F0E8D8;margin:0;">Confirmation Scan Complete</h1>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:rgba(240,232,216,0.45);margin:6px 0 0;">{domain}</p>
  </div>

  <div style="padding:28px 36px;text-align:center;border-bottom:1px solid #f0ede6;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#999;margin:0 0 8px;">New Score</p>
    <div style="font-size:52px;font-weight:700;color:#080d1a;line-height:1;">{new_score}</div>
    <div style="font-size:13px;color:#999;margin-bottom:8px;">/ 100</div>
    <span style="font-family:Arial,sans-serif;font-size:13px;font-weight:700;color:{'#27AE60' if delta >= 0 else '#C0392B'};">{delta_sign}{delta} points from {old_score}</span>
  </div>

  <div style="padding:24px 36px;border-bottom:1px solid #f0ede6;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#27AE60;margin:0 0 10px;">Confirmed Fixed</p>
    <table style="width:100%;border-collapse:collapse;">{confirmed_rows}</table>
  </div>

  {'<div style="padding:24px 36px;border-bottom:1px solid #f0ede6;"><p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#E67E22;margin:0 0 10px;">Still Present</p><table style="width:100%;border-collapse:collapse;">' + open_rows + '</table></div>' if still_open else ''}

  {'<div style="padding:24px 36px;border-bottom:1px solid #f0ede6;"><p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#C0392B;margin:0 0 10px;">New Issues Detected</p><table style="width:100%;border-collapse:collapse;">' + new_rows + '</table></div>' if new_issues else ''}

  <div style="padding:20px 36px;background:#080d1a;">
    <p style="font-family:Arial,sans-serif;font-size:10px;color:rgba(240,232,216,0.35);margin:0;line-height:1.6;">
      Institute of Digital Remediation · idrshield.com · hello@idrshield.com<br>
      IDR-PROTOCOL-2026 · This is not legal advice.
    </p>
  </div>

</div>
</body></html>"""

    text = f"""IDR CONFIRMATION SCAN — {domain}

New Score: {new_score}/100 ({delta_sign}{delta} from {old_score})

Confirmed Fixed: {len(confirmed)}
Still Present: {len(still_open)}
New Issues: {len(new_issues)}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ═══════════════════════════════════════════════════════════════════════════════
# SEQUENCE A — Free Scanner Nurture (A2–A6)
# Triggered by: free scan with email provided
# Goal: convert free scanner to founding member
# ═══════════════════════════════════════════════════════════════════════════════

def _email_header(title: str, subtitle: str = '') -> str:
    """Shared dark header for all sequence emails."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:Georgia,serif;background:#f0ede6;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#ffffff;border:1px solid #ddd;">
  <div style="background:#07091A;padding:32px 40px;border-bottom:3px solid #C9A84C;">
    <p style="font-family:Arial,sans-serif;font-size:9px;font-weight:700;letter-spacing:0.22em;text-transform:uppercase;color:rgba(201,168,76,0.65);margin:0 0 8px;">Institute of Digital Remediation</p>
    <h1 style="font-family:Georgia,serif;font-size:22px;font-weight:normal;color:#F0E8D4;margin:0 0 4px;">{title}</h1>
    {f'<p style="font-family:Arial,sans-serif;font-size:12px;color:rgba(240,232,212,0.45);margin:0;">{subtitle}</p>' if subtitle else ''}
  </div>"""


def _email_footer(receipt_id: str = '') -> str:
    """Shared footer for all sequence emails."""
    receipt_line = f'Scan Receipt: {receipt_id[:16]}&#x2026; &nbsp;&#xB7;&nbsp; ' if receipt_id else ''
    return f"""  <div style="padding:20px 40px;background:#07091A;">
    <p style="font-family:Arial,sans-serif;font-size:10px;color:rgba(240,232,212,0.3);margin:0;line-height:1.8;">
      {receipt_line}Institute of Digital Remediation &nbsp;&#xB7;&nbsp; idrshield.com<br>
      Not a law firm. This is a compliance documentation system. IDR-PROTOCOL-2026.
    </p>
  </div>
</div>
</body>
</html>"""


def _cta_button(text: str, url: str, secondary: bool = False) -> str:
    """Reusable CTA button."""
    if secondary:
        return f'<a href="{url}" style="display:inline-block;background:transparent;color:#C9A84C;font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;padding:13px 32px;text-decoration:none;border:1px solid #C9A84C;border-radius:3px;">{text}</a>'
    return f'<a href="{url}" style="display:inline-block;background:#C9A84C;color:#07091A;font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.16em;text-transform:uppercase;padding:16px 40px;text-decoration:none;border-radius:3px;">{text}</a>'


def _body_section(content: str, bg: str = '#ffffff') -> str:
    """Reusable body section wrapper."""
    return f'<div style="padding:28px 40px;background:{bg};border-bottom:1px solid #ebebeb;">{content}</div>'


def _p(text: str, size: int = 14, color: str = '#1a1a1a', margin: str = '0 0 16px') -> str:
    return f'<p style="font-family:Arial,sans-serif;font-size:{size}px;color:{color};line-height:1.78;margin:{margin};">{text}</p>'


def _pull_quote(text: str) -> str:
    return f'<p style="font-family:Georgia,serif;font-size:16px;color:#1a1a1a;line-height:1.75;margin:0 0 16px;font-style:italic;border-left:3px solid #C9A84C;padding-left:18px;">{text}</p>'


GUMROAD = 'https://idrshield.gumroad.com/l/oadcfq'
REGISTRY_BASE = 'https://idrshield.com/verify'
SCANNER_URL = 'https://idrshield.com/idrshield_scanner.html'


# ── A2 — 23 hours ─────────────────────────────────────────────────────────────

def send_nurture_day1(email: str, domain: str, receipt: dict = None) -> bool:
    """
    A2 — 23 hours after scan.
    Angle: The scan didn't expire. The exposure didn't either.
    """
    subject  = f'Your store is still carrying the same risk profile'
    registry = f'{REGISTRY_BASE}/{domain}'

    html = _email_header('Your store is still exposed.', domain)
    html += _body_section(
        _p('Your scan from yesterday is still on file.') +
        _p('That means the same issues are still visible today — to anyone running the same type of automated scan on your store.') +
        _pull_quote('Most store owners assume the danger is the lawsuit itself. It\'s not. The real danger is being evaluated before you\'ve documented anything.') +
        _p('Right now, your store has a score, a visible issue profile, and no active Defense Package attached to it.') +
        _p('<strong>That is exactly the gap plaintiff-side scanners look for.</strong>', color='#1a1a1a')
    )
    html += _body_section(
        '<p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#C9A84C;margin:0 0 16px;">Founding Membership gives you what the free scan does not</p>' +
        '<p style="font-family:Arial,sans-serif;font-size:13px;color:#444;line-height:1.9;margin:0;">' +
        '&#x2713; &nbsp;Full 10-section legal-grade Defense Package<br>' +
        '&#x2713; &nbsp;Remediation code — before/after for every issue<br>' +
        '&#x2713; &nbsp;SHA-256 tamper-evident Scan Receipt<br>' +
        '&#x2713; &nbsp;Public registry record tied to your domain<br>' +
        '&#x2713; &nbsp;IDR Verified badge + weekly automated monitoring</p>',
        '#faf8f4'
    )
    html += _body_section(
        _p('If you wait until someone else scans your store first, you\'re already reacting.') +
        _pull_quote('Activate while you still control the timeline.') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('Activate Founding Membership &#x2014; $97', GUMROAD) +
        '<p style="font-family:Arial,sans-serif;font-size:11px;color:#aaa;margin:12px 0 0;">First 500 stores only &nbsp;&#xB7;&nbsp; 30 days free &nbsp;&#xB7;&nbsp; $29/month locked for life</p>' +
        '</div>'
    )
    html += _email_footer(receipt.get('receipt_id', '') if receipt else '')

    text = f"""Your store is still carrying the same risk profile — {domain}

Your scan from yesterday is still on file. The same issues are still visible today to anyone running automated accessibility scans.

Most store owners assume the danger is the lawsuit itself. It's not. The real danger is being evaluated before you've documented anything.

Founding Membership gives you:
✓ Full 10-section Defense Package
✓ Remediation code for every issue
✓ SHA-256 tamper-evident Scan Receipt
✓ Public registry record
✓ IDR Verified badge + weekly monitoring

If you wait until someone else scans your store first, you're already reacting.

Activate while you still control the timeline.

Activate Founding Membership — $97
{GUMROAD}

First 500 stores only · 30 days free · $29/month locked for life

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ── A3 — 72 hours ─────────────────────────────────────────────────────────────

def send_nurture_day3(email: str, domain: str, receipt: dict = None) -> bool:
    """
    A3 — 3 days after scan.
    Angle: Most stores don't act until the letter arrives.
    """
    subject = 'Most stores don\'t act until the letter arrives'

    html = _email_header('By then, the conversation is no longer on their terms.', domain)
    html += _body_section(
        _p('Three days ago, your store was scanned.') +
        _p('Most people do what most people always do: they look at the result, feel a little uneasy, then move on.') +
        _p('Nothing feels urgent because nothing visible has happened yet.') +
        _p('<strong>That\'s exactly why so many stores stay exposed.</strong>', color='#1a1a1a')
    )
    html += _body_section(
        _pull_quote('The first real sign for most store owners is not a dashboard. It\'s not a score. It\'s a legal notice.') +
        _p('And by then, they\'re no longer asking, "What should we do?"') +
        _p('They\'re asking, "<strong>How much will this cost us?</strong>"', color='#1a1a1a'),
        '#faf8f4'
    )
    html += _body_section(
        _p('The stores that put themselves in a stronger position early usually do one thing differently:') +
        _pull_quote('They document first.') +
        _p('That is what IDR Shield is built to do. Not just show you what\'s wrong. Not just flag the risk. <strong>Create proof of active effort. Establish a record before someone else creates one for you.</strong>', color='#1a1a1a') +
        _p('Your scan already told you there\'s a problem.') +
        _p('Now decide whether you want a summary&hellip; or a defensible position.') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('Unlock Your Full Defense Package', GUMROAD) +
        '<p style="font-family:Arial,sans-serif;font-size:11px;color:#aaa;margin:12px 0 0;">$97 activation &nbsp;&#xB7;&nbsp; 30 days free &nbsp;&#xB7;&nbsp; $29/month locked for life</p>' +
        '</div>'
    )
    html += _email_footer(receipt.get('receipt_id', '') if receipt else '')

    text = f"""Most stores don't act until the letter arrives — {domain}

Three days ago, your store was scanned.

Most people look at the result, feel a little uneasy, then move on. Nothing feels urgent because nothing visible has happened yet. That's exactly why so many stores stay exposed.

The first real sign for most store owners is not a dashboard. It's not a score. It's a legal notice.

The stores that put themselves in a stronger position early do one thing differently: they document first.

That is what IDR Shield is built to do. Create proof of active effort. Establish a record before someone else creates one for you.

Your scan already told you there's a problem. Now decide whether you want a summary... or a defensible position.

Unlock Your Full Defense Package — $97
{GUMROAD}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ── A4 — 120 hours ────────────────────────────────────────────────────────────

def send_nurture_day5(email: str, domain: str, receipt: dict = None) -> bool:
    """
    A4 — 5 days after scan.
    Angle: The difference is proof, not perfection.
    """
    subject = 'Here\'s what serious store owners do differently'

    html = _email_header('They don\'t wait for perfect. They document movement.', domain)
    html += _body_section(
        _pull_quote('The difference between an exposed store and a protected one is not perfection. It\'s proof.') +
        _p('Serious store owners understand something most people miss:') +
        _p('<strong>No site stays perfect.</strong>', color='#1a1a1a') +
        _p('Themes change. Apps update. New products get added. Buttons break. Labels disappear. Accessibility gaps reopen quietly.', color='#555')
    )
    html += _body_section(
        _p('That\'s why the strongest position is not, "My site has no issues."') +
        _pull_quote('"My store is actively monitored, documented, and being maintained."') +
        _p('That is what Founding Membership gives you.') +
        '<p style="font-family:Arial,sans-serif;font-size:13px;color:#444;line-height:1.9;margin:0 0 16px;">' +
        '&#x2022; &nbsp;Your Defense Package creates the baseline<br>' +
        '&#x2022; &nbsp;Your registry record makes that baseline visible and verifiable<br>' +
        '&#x2022; &nbsp;Your weekly rescans keep the record alive and current</p>' +
        _p('Without that continuity, you\'re relying on hope. With it, you\'re building a documented compliance posture.', color='#555'),
        '#faf8f4'
    )
    html += _body_section(
        _p('The first 500 stores lock in the founding rate permanently.') +
        _p('If your store matters to you, your documentation should too.') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('Become a Founding Member &#x2014; $97', GUMROAD) +
        '<p style="font-family:Arial,sans-serif;font-size:11px;color:#aaa;margin:12px 0 0;">First 500 stores only &nbsp;&#xB7;&nbsp; 30 days free &nbsp;&#xB7;&nbsp; $29/month locked for life</p>' +
        '</div>'
    )
    html += _email_footer(receipt.get('receipt_id', '') if receipt else '')

    text = f"""Here's what serious store owners do differently — {domain}

The difference between an exposed store and a protected one is not perfection. It's proof.

No site stays perfect. Themes change. Apps update. New products get added. Accessibility gaps reopen quietly.

That's why the strongest position is not "My site has no issues." It's: "My store is actively monitored, documented, and being maintained."

That is what Founding Membership gives you:
• Your Defense Package creates the baseline
• Your registry record makes that baseline visible
• Your weekly rescans keep the record alive

The first 500 stores lock in the founding rate permanently.

Become a Founding Member — $97
{GUMROAD}

First 500 stores only · 30 days free · $29/month locked for life

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ── A5 — 168 hours ────────────────────────────────────────────────────────────

def send_nurture_day7(email: str, domain: str, receipt: dict = None) -> bool:
    """
    A5 — 7 days after scan.
    Angle: One week later. The scan is still on file.
    """
    subject = 'A week later, your scan is still on file'

    html = _email_header('One week is long enough to ignore a risk. It\'s also long enough to fix your position.', domain)
    html += _body_section(
        _p('It has been one week since your store was scanned.') +
        _p('Your results are still on file. Your issue profile has not disappeared. And unless something changed on your side, neither has the underlying exposure.') +
        _pull_quote('A week is usually the point where one of two things happens: some owners decide this mattered more than they first thought — others convince themselves they\'ll deal with it later.')
    )
    html += _body_section(
        _p('<strong>The problem with "later" is that the scan window never closes.</strong>', color='#1a1a1a') +
        _p('Your store can still be evaluated tomorrow. Or tonight. Or by someone you never see coming.') +
        _p('Founding Membership is how you stop treating this like a vague future concern and turn it into a documented, active process.', color='#555'),
        '#faf8f4'
    )
    html += _body_section(
        '<p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#C9A84C;margin:0 0 14px;">What you get</p>' +
        '<p style="font-family:Arial,sans-serif;font-size:13px;color:#444;line-height:1.9;margin:0 0 20px;">' +
        '&#x2713; &nbsp;The full Defense Package<br>' +
        '&#x2713; &nbsp;Your registry record<br>' +
        '&#x2713; &nbsp;Badge eligibility<br>' +
        '&#x2713; &nbsp;Weekly rescans<br>' +
        '&#x2713; &nbsp;Immediate alerts when new issues appear</p>' +
        _p('And if you join now, your $29/month rate stays locked permanently.') +
        _pull_quote('One week ago, you got visibility. Today, you decide whether to do anything with it.') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('Activate Founding Membership &#x2014; $97', GUMROAD) +
        '<p style="font-family:Arial,sans-serif;font-size:11px;color:#aaa;margin:12px 0 0;">First 500 stores only &nbsp;&#xB7;&nbsp; 30 days free &nbsp;&#xB7;&nbsp; $29/month locked for life</p>' +
        '</div>'
    )
    html += _email_footer(receipt.get('receipt_id', '') if receipt else '')

    text = f"""A week later, your scan is still on file — {domain}

It has been one week since your store was scanned.

Your results are still on file. Your issue profile has not disappeared. And unless something changed on your side, neither has the underlying exposure.

The problem with "later" is that the scan window never closes. Your store can still be evaluated tomorrow. Or tonight. Or by someone you never see coming.

What you get with Founding Membership:
✓ The full Defense Package
✓ Your registry record
✓ Badge eligibility
✓ Weekly rescans
✓ Immediate alerts when new issues appear

And if you join now, your $29/month rate stays locked permanently.

One week ago, you got visibility. Today, you decide whether to do anything with it.

Activate Founding Membership — $97
{GUMROAD}

First 500 stores only · 30 days free · $29/month locked for life

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ── A6 — 336 hours ────────────────────────────────────────────────────────────

def send_nurture_day14(email: str, domain: str, receipt: dict = None) -> bool:
    """
    A6 — 14 days after scan. Final email.
    Angle: This is the last follow-up. The risk remains.
    """
    subject = 'Final note about your scan'

    html = _email_header('After this, we\'ll assume you\'ve chosen to leave it where it is.', domain)
    html += _body_section(
        _p('This is the last follow-up we\'ll send about your scan.') +
        _p('Two weeks ago, your store was scanned and flagged.') +
        _p('Since then, you\'ve had the chance to ignore it, think about it, revisit it, or act on it. That decision is yours.')
    )
    html += _body_section(
        _pull_quote('Here\'s the truth as plainly as I can say it: the risk does not go away because the email sequence ends.') +
        _p('If your store is ever evaluated by someone else, what will matter is not whether you <em>meant</em> to deal with it eventually.') +
        _p('<strong>What will matter is whether you had documentation, proof, and an active record in place before that moment.</strong>', color='#1a1a1a') +
        _p('That is what IDR Shield was built for.', color='#555'),
        '#faf8f4'
    )
    html += _body_section(
        _p('If you want the full Defense Package, registry activation, and founding-rate access, this is the moment to do it.') +
        _p('If not, we\'ll leave you here.') +
        _pull_quote('But if you\'ve been waiting for the "right time" — this is it.') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('Claim Founding Access &#x2014; $97', GUMROAD) +
        '<p style="font-family:Arial,sans-serif;font-size:11px;color:#aaa;margin:12px 0 0;">First 500 stores only &nbsp;&#xB7;&nbsp; $97 activation &nbsp;&#xB7;&nbsp; 30 days free &nbsp;&#xB7;&nbsp; $29/month locked for life</p>' +
        '</div>'
    )
    html += _email_footer(receipt.get('receipt_id', '') if receipt else '')

    text = f"""Final note about your scan — {domain}

This is the last follow-up we'll send about your scan.

Two weeks ago, your store was scanned and flagged.

The risk does not go away because the email sequence ends. If your store is ever evaluated by someone else, what will matter is not whether you meant to deal with it eventually. What will matter is whether you had documentation, proof, and an active record in place before that moment.

If you want the full Defense Package, registry activation, and founding-rate access, this is the moment to do it.

If you've been waiting for the "right time" — this is it.

Claim Founding Access — $97
{GUMROAD}

First 500 stores only · $97 activation · 30 days free · $29/month locked for life

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ═══════════════════════════════════════════════════════════════════════════════
# SEQUENCE B — Founder Onboarding (B3–B6)
# Triggered by: Gumroad purchase confirmed
# Goal: activate badge, reinforce value, retain subscription
# ═══════════════════════════════════════════════════════════════════════════════

# ── B3 — 48 hours ─────────────────────────────────────────────────────────────

def send_founder_badge_guide(email: str, domain: str, receipt: dict = None) -> bool:
    """
    B3 — 48 hours after purchase.
    Angle: Get the badge live. Visibility is the other half.
    """
    subject = 'Your next step: get the badge live'
    registry_url = f'{REGISTRY_BASE}/{domain}'
    badge_code   = f'<script src="https://idrshield.com/badge.js" data-store="{domain}"></script>'

    html = _email_header('Your Defense Package is one part of the system. Visibility is the other.', domain)
    html += _body_section(
        _p('You\'re in.') +
        _p('Your store is already in the IDR Registry, and your Defense Package is already attached to your record.') +
        _p('Now do the next important step: <strong>get your IDR Verified badge live on your store.</strong>', color='#1a1a1a')
    )
    html += _body_section(
        '<p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#C9A84C;margin:0 0 14px;">Why this matters</p>' +
        _p('The badge is not decoration.') +
        _p('It is a visible signal that your store is part of an active monitoring and documentation system.') +
        _p('Anyone reviewing your site sees more than a storefront — they see a store with a registry record, a documented scan history, and an active process behind it.', color='#555'),
        '#faf8f4'
    )
    html += _body_section(
        '<p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#C9A84C;margin:0 0 14px;">Your badge embed code</p>' +
        f'<p style="font-family:\'Courier New\',monospace;font-size:12px;color:#333;background:#f5f5f5;padding:12px 16px;border-radius:3px;line-height:1.6;margin:0 0 16px;word-break:break-all;">{badge_code}</p>' +
        _p('Paste this in your store footer. On Shopify, your developer can place it in the theme footer in minutes. On Squarespace or similar platforms, use a custom code block.') +
        _p('Full instructions are also in §09 of your Defense Package PDF.') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('View Badge Setup Instructions', 'https://idrshield.com') +
        '&nbsp;&nbsp;' +
        _cta_button('View Your Registry Record', registry_url, secondary=True) +
        '</div>'
    )
    html += _email_footer(receipt.get('receipt_id', '') if receipt else '')

    text = f"""Your next step: get the badge live — {domain}

You're in. Your store is already in the IDR Registry and your Defense Package is attached to your record.

Now get your IDR Verified badge live on your store.

The badge is not decoration. It is a visible signal that your store is part of an active monitoring and documentation system.

Your badge embed code:
{badge_code}

Paste this in your store footer. Full instructions are in §09 of your Defense Package PDF.

View Your Registry Record: {registry_url}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ── B4 — 168 hours ────────────────────────────────────────────────────────────

def send_founder_monitoring_active(email: str, domain: str, receipt: dict = None) -> bool:
    """
    B4 — 7 days after purchase.
    Angle: This is not a one-time report. The system is working.
    """
    subject = 'Your store is being monitored'
    registry_url = f'{REGISTRY_BASE}/{domain}'

    html = _email_header('This is not a one-time report. The system is already working in the background.', domain)
    html += _body_section(
        _p('A quick reminder one week in:') +
        _pull_quote('Your store is being monitored. That matters more than people realize.') +
        _p('Most businesses think in terms of one scan, one fix, one report. That\'s not how exposure works.')
    )
    html += _body_section(
        _p('Stores change constantly.') +
        _p('A clean page today can become a problem page next week after a theme adjustment, app update, or new product upload.', color='#555') +
        _p('<strong>That\'s why IDR Shield is not just a receipt. It\'s an active record.</strong>', color='#1a1a1a'),
        '#faf8f4'
    )
    html += _body_section(
        '<p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#C9A84C;margin:0 0 14px;">Your founding membership includes</p>' +
        '<p style="font-family:Arial,sans-serif;font-size:13px;color:#444;line-height:1.9;margin:0 0 20px;">' +
        '&#x2713; &nbsp;Weekly automated rescans<br>' +
        '&#x2713; &nbsp;Immediate alerts if new issues appear<br>' +
        '&#x2713; &nbsp;Continuity in your registry record<br>' +
        '&#x2713; &nbsp;Preservation of your documented compliance posture</p>' +
        _p('In other words: your protection is not sitting still. It\'s being maintained.') +
        _pull_quote('That continuity is exactly what makes the $29/month worth keeping.') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('View Your Registry Record', registry_url) +
        '</div>'
    )
    html += _email_footer(receipt.get('receipt_id', '') if receipt else '')

    text = f"""Your store is being monitored — {domain}

A quick reminder one week in: your store is being monitored. That matters more than people realize.

Most businesses think in terms of one scan, one fix, one report. That's not how exposure works. A clean page today can become a problem page next week after a theme adjustment or app update.

That's why IDR Shield is not just a receipt. It's an active record.

Your founding membership includes:
✓ Weekly automated rescans
✓ Immediate alerts if new issues appear
✓ Continuity in your registry record
✓ Preservation of your documented compliance posture

Your protection is not sitting still. It's being maintained.

View Your Registry Record: {registry_url}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ── B5 — 336 hours ────────────────────────────────────────────────────────────

def send_founder_rescan_incoming(email: str, domain: str, receipt: dict = None) -> bool:
    """
    B5 — 14 days after purchase.
    Angle: Your next rescan is coming. Here's what to expect.
    """
    subject = 'Before your next rescan runs'
    registry_url = f'{REGISTRY_BASE}/{domain}'

    html = _email_header('Here\'s what to expect — and why it matters.', domain)
    html += _body_section(
        _p('You\'re about two weeks into your Founding Membership, which means your ongoing monitoring cycle is becoming real.') +
        _p('Before your next rescan runs, here\'s what to know:')
    )
    html += _body_section(
        _p('If your store changed since activation — new products, new buttons, layout changes, app behavior, or theme edits — the rescan may catch new issues.') +
        _pull_quote('That is not a failure of the system. That is the point of the system.') +
        _p('IDR Shield exists so those changes do not happen silently.', color='#555'),
        '#faf8f4'
    )
    html += _body_section(
        _p('If the rescan is clean, that strengthens your documentation trail.') +
        _p('If new issues appear, you\'ll know quickly — and can act before those gaps become exposure.') +
        _p('Either way, the result is useful because <strong>your record stays current.</strong>', color='#1a1a1a') +
        _pull_quote('You don\'t need your store to stay frozen. You need your record to stay alive.') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('View Your Registry Record', registry_url) +
        '</div>'
    )
    html += _email_footer(receipt.get('receipt_id', '') if receipt else '')

    text = f"""Before your next rescan runs — {domain}

You're about two weeks into your Founding Membership, which means your ongoing monitoring cycle is becoming real.

If your store changed since activation — new products, new buttons, layout changes, or theme edits — the rescan may catch new issues.

That is not a failure of the system. That is the point of the system.

If the rescan is clean, that strengthens your documentation trail.
If new issues appear, you'll know quickly and can act before those gaps become exposure.

You don't need your store to stay frozen. You need your record to stay alive.

View Your Registry Record: {registry_url}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ── B6 — 720 hours ────────────────────────────────────────────────────────────

def send_founder_30day_summary(email: str, domain: str, receipt: dict = None) -> bool:
    """
    B6 — 30 days after purchase.
    Angle: Here's what your first 30 days gave you. Justify the subscription.
    """
    subject = 'Here\'s what your first 30 days gave you'
    registry_url = f'{REGISTRY_BASE}/{domain}'

    html = _email_header('This is what your membership has already created for your store.', domain)
    html += _body_section(
        _p('It has now been 30 days since your store joined IDR Shield.') +
        _p('In that time, your membership has already created something most stores still do not have:')
    )
    html += _body_section(
        '<p style="font-family:Arial,sans-serif;font-size:13px;color:#444;line-height:2;margin:0 0 16px;">' +
        '&#x2713; &nbsp;A timestamped Defense Package<br>' +
        '&#x2713; &nbsp;A registry record tied to your domain<br>' +
        '&#x2713; &nbsp;An immutable SHA-256 receipt<br>' +
        '&#x2713; &nbsp;An active monitoring trail<br>' +
        '&#x2713; &nbsp;Continuity in your documented compliance posture</p>' +
        _pull_quote('That is what your first 30 days paid for. Not just a scan. Not just a PDF. A stronger position.'),
        '#faf8f4'
    )
    html += _body_section(
        _p('At this stage, the question is simple:') +
        _pull_quote('Do you want that record to continue&hellip; or do you want it to stop here?') +
        _p('If your monitoring continues, your store keeps building documented continuity.') +
        _p('If it stops, your record becomes stale — and <strong>stale documentation is weaker than active documentation.</strong>', color='#1a1a1a') +
        _p('That is why your founding rate matters. You are locked at $29/month for life.') +
        _p('Keep the system active, keep the record current, and keep your store in a stronger position than most.', color='#555') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('Keep My Monitoring Active', registry_url) +
        '</div>'
    )
    html += _email_footer(receipt.get('receipt_id', '') if receipt else '')

    text = f"""Here's what your first 30 days gave you — {domain}

It has now been 30 days since your store joined IDR Shield.

In that time, your membership has already created:
✓ A timestamped Defense Package
✓ A registry record tied to your domain
✓ An immutable SHA-256 receipt
✓ An active monitoring trail
✓ Continuity in your documented compliance posture

That is what your first 30 days paid for. Not just a scan. Not just a PDF. A stronger position.

The question now is simple: do you want that record to continue... or stop here?

Stale documentation is weaker than active documentation. You are locked at $29/month for life. Keep the system active.

View Your Registry Record: {registry_url}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ═══════════════════════════════════════════════════════════════════════════════
# SEQUENCE C — Transactional / Event-Triggered (C1–C6)
# These replace/upgrade the existing transactional emails
# ═══════════════════════════════════════════════════════════════════════════════

def send_weekly_rescan_issues(email: str, domain: str,
                              new_issues: list, receipt_id: str) -> bool:
    """
    C1 — Weekly rescan found new issues.
    Replaces existing send_weekly_scan_alert.
    """
    count        = len(new_issues)
    subject      = f'New issues detected on your store — {domain}'
    registry_url = f'{REGISTRY_BASE}/{domain}'

    html = _email_header(f'New issues detected on {domain}', f'{count} new issue{"s" if count != 1 else ""} found in your latest rescan')
    html += _body_section(
        _p('Your latest IDR rescan just completed.') +
        _pull_quote(f'{count} new issue{"s were" if count != 1 else " was"} detected on your store.') +
        _p('This doesn\'t mean something went wrong. It means your store changed — and the system caught it.') +
        _p('<strong>That\'s exactly why IDR Shield exists.</strong>', color='#1a1a1a') +
        _p('Without monitoring, these changes happen silently. With monitoring, you see them immediately.', color='#555')
    )
    html += _body_section(
        '<p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#C9A84C;margin:0 0 14px;">What to do next</p>' +
        '<p style="font-family:Arial,sans-serif;font-size:14px;color:#333;line-height:1.9;margin:0 0 20px;">' +
        '1. &nbsp;Review your updated report<br>' +
        '2. &nbsp;Apply the recommended fixes<br>' +
        '3. &nbsp;Submit for a confirmation scan</p>' +
        _p('The faster you act, the stronger your record stays.') +
        _pull_quote('Your store is not static. Your protection shouldn\'t be either.') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('View Updated Report', registry_url) +
        '</div>',
        '#faf8f4'
    )
    html += _email_footer(receipt_id)

    text = f"""New issues detected on your store — {domain}

Your latest IDR rescan found {count} new issue{"s" if count != 1 else ""}.

This doesn't mean something went wrong. It means your store changed — and the system caught it.

What to do next:
1. Review your updated report
2. Apply the recommended fixes
3. Submit for a confirmation scan

The faster you act, the stronger your record stays.

View Updated Report: {registry_url}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


def send_external_scan_alert(email: str, domain: str,
                              scanner_ip: str = '', findings: dict = None) -> bool:
    """
    C2 — External party scanned their store.
    Replaces existing send_scan_alert.
    """
    subject      = f'Your store was just scanned externally — {domain}'
    registry_url = f'{REGISTRY_BASE}/{domain}'
    findings     = findings or {}

    html = _email_header(f'External scan detected on {domain}', 'This is exactly why you\'re protected')
    html += _body_section(
        _p('Your store was just scanned by an external system.') +
        _p('We detected activity consistent with third-party accessibility scanning.') +
        _pull_quote('This is not unusual. But it is important. Most store owners never know this is happening. You do — because your store is monitored.')
    )
    html += _body_section(
        '<p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#C9A84C;margin:0 0 14px;">More importantly, your store already has</p>' +
        '<p style="font-family:Arial,sans-serif;font-size:13px;color:#444;line-height:1.9;margin:0 0 20px;">' +
        '&#x2713; &nbsp;A Defense Package<br>' +
        '&#x2713; &nbsp;A registry record<br>' +
        '&#x2713; &nbsp;A timestamped scan history</p>' +
        _pull_quote('That means your store is not being seen as "unprepared." It\'s being seen as documented. That difference matters.') +
        _p('No action needed right now. We\'re keeping you informed — exactly as promised.', color='#555'),
        '#faf8f4'
    )
    html += _body_section(
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('View Your Registry Record', registry_url) +
        '</div>'
    )
    html += _email_footer()

    text = f"""Your store was just scanned externally — {domain}

Your store was just scanned by an external system. We detected activity consistent with third-party accessibility scanning.

Most store owners never know this is happening. You do — because your store is monitored.

More importantly, your store already has:
✓ A Defense Package
✓ A registry record
✓ A timestamped scan history

That means your store is not being seen as "unprepared." It's being seen as documented. That difference matters.

No action needed right now.

View Your Registry Record: {registry_url}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


def send_fix_confirmed(email: str, domain: str, result: dict) -> bool:
    """
    C3 — Fix confirmed after confirmation scan.
    """
    new_score    = result.get('new_score', 0)
    old_score    = result.get('original_score', 0)
    delta        = result.get('score_delta', 0)
    delta_str    = f'+{delta}' if delta >= 0 else str(delta)
    delta_color  = '#27AE60' if delta >= 0 else '#D94F4F'
    subject      = f'Fix confirmed — your score just improved'
    registry_url = f'{REGISTRY_BASE}/{domain}'

    html = _email_header('Your update worked. Here\'s the result.', domain)
    html += _body_section(
        '<div style="text-align:center;padding:16px 0;">' +
        f'<p style="font-family:Georgia,serif;font-size:48px;font-weight:700;color:#1a1a1a;line-height:1;margin:0;">{new_score}</p>' +
        '<p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin:4px 0 0;">/ 100</p>' +
        f'<p style="font-family:Arial,sans-serif;font-size:14px;font-weight:700;color:{delta_color};margin:8px 0 0;">{delta_str} points from {old_score}</p>' +
        '</div>'
    )
    html += _body_section(
        _p('Your confirmation scan is complete. Your fix has been verified.') +
        _p('The issue you submitted is no longer present on your store.') +
        _pull_quote('This matters more than the fix itself. Because now you don\'t just have a better store — you have proof that it was improved.') +
        _p('That proof becomes part of your ongoing record.') +
        _p('Keep going. Each confirmed fix strengthens your position.', color='#555') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('View Updated Report', registry_url) +
        '</div>',
        '#faf8f4'
    )
    html += _email_footer()

    text = f"""Fix confirmed — your score just improved — {domain}

Your confirmation scan is complete. Your fix has been verified.

New score: {new_score}/100 ({delta_str} points from {old_score})

This matters more than the fix itself. Because now you don't just have a better store — you have proof that it was improved. That proof becomes part of your ongoing record.

Keep going. Each confirmed fix strengthens your position.

View Updated Report: {registry_url}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


def send_monthly_clean_pass(email: str, domain: str, receipt_id: str = '') -> bool:
    """
    C4 — Monthly rescan passed with no issues.
    Retention gold — reinforce value of subscription.
    """
    subject      = f'Clean scan — no issues detected on {domain}'
    registry_url = f'{REGISTRY_BASE}/{domain}'

    html = _email_header(f'Clean scan — {domain}', 'This is what a strong record looks like')
    html += _body_section(
        _p('Your latest scan just completed.') +
        _pull_quote('No issues were detected. Your store is currently in a clean state.') +
        _p('This is what the system is designed to create:') +
        _p('<strong>Not just fixes — but consistency.</strong>', color='#1a1a1a')
    )
    html += _body_section(
        _p('Your registry record now reflects a clean scan.') +
        _p('That strengthens your documentation and your overall compliance posture.') +
        _pull_quote('Most stores don\'t maintain this level of visibility. You are.') +
        _p('We\'ll continue monitoring automatically.', color='#555') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('View Your Registry Record', registry_url) +
        '</div>',
        '#faf8f4'
    )
    html += _email_footer(receipt_id)

    text = f"""Clean scan — no issues detected on {domain}

Your latest scan just completed. No issues were detected. Your store is currently in a clean state.

Your registry record now reflects a clean scan. That strengthens your documentation and your overall compliance posture.

Most stores don't maintain this level of visibility. You are.

We'll continue monitoring automatically.

View Your Registry Record: {registry_url}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


def send_all_issues_resolved(email: str, domain: str, receipt_id: str = '') -> bool:
    """
    C5 — All issues fully resolved after confirmation scan.
    Best moment in the product experience.
    """
    subject      = f'Your store is now fully resolved — {domain}'
    registry_url = f'{REGISTRY_BASE}/{domain}'
    badge_url    = 'https://idrshield.com'

    html = _email_header('Everything flagged has been fixed and confirmed.', domain)
    html += _body_section(
        _p('Your latest confirmation scan just completed.') +
        _pull_quote('All previously identified issues have now been resolved.') +
        _p('Your store is currently in a <strong>fully remediated state.</strong>', color='#1a1a1a') +
        _p('Your Defense Package, registry record, and scan history now reflect this.')
    )
    html += _body_section(
        _pull_quote('This is the strongest position your store can be in.') +
        _p('If your badge is not already live, now is the time to activate it.') +
        _p('Because it\'s not just a clean store — <strong>it\'s a documented clean store.</strong>', color='#1a1a1a') +
        _p('We\'ll continue monitoring to keep it that way.', color='#555') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('Activate Your Badge', badge_url) +
        '&nbsp;&nbsp;' +
        _cta_button('View Registry Record', registry_url, secondary=True) +
        '</div>',
        '#faf8f4'
    )
    html += _email_footer(receipt_id)

    text = f"""Your store is now fully resolved — {domain}

Your latest confirmation scan just completed.

All previously identified issues have now been resolved. Your store is currently in a fully remediated state.

This is the strongest position your store can be in. It's not just a clean store — it's a documented clean store.

If your badge is not already live, now is the time to activate it.

Activate Your Badge: {badge_url}
View Registry Record: {registry_url}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


def send_issues_still_present(email: str, domain: str, result: dict) -> bool:
    """
    C6 — Some issues still present after confirmation scan.
    """
    still_open   = result.get('still_present', [])
    count        = len(still_open)
    subject      = f'Some issues are still present — {domain}'
    registry_url = f'{REGISTRY_BASE}/{domain}'

    html = _email_header(f'You\'re close — here\'s what remains', domain)
    html += _body_section(
        _p('Your confirmation scan is complete.') +
        _p(f'<strong>{count} issue{"s are" if count != 1 else " is"} still present on your store.</strong>', color='#D94F4F') +
        _pull_quote('That\'s normal. Most fixes take more than one pass.')
    )
    html += _body_section(
        '<p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#C9A84C;margin:0 0 14px;">Here\'s what to do</p>' +
        '<p style="font-family:Arial,sans-serif;font-size:14px;color:#333;line-height:1.9;margin:0 0 20px;">' +
        '1. &nbsp;Review the remaining issues<br>' +
        '2. &nbsp;Apply the updated recommendations<br>' +
        '3. &nbsp;Submit another confirmation scan</p>' +
        _p('You\'re not starting over. You\'re refining.') +
        _pull_quote('Each iteration gets you closer to a fully documented clean state.') +
        _p('Stay with it.', color='#555') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('View Remaining Issues', registry_url) +
        '</div>',
        '#faf8f4'
    )
    html += _email_footer()

    text = f"""Some issues are still present — {domain}

Your confirmation scan is complete. {count} issue{"s are" if count != 1 else " is"} still present on your store.

That's normal. Most fixes take more than one pass.

Here's what to do:
1. Review the remaining issues
2. Apply the updated recommendations
3. Submit another confirmation scan

You're not starting over. You're refining. Each iteration gets you closer to a fully documented clean state.

View Remaining Issues: {registry_url}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


# ═══════════════════════════════════════════════════════════════════════════════
# SEQUENCE D — Win-Back (D1–D2)
# Triggered by: cancellation or payment failure
# ═══════════════════════════════════════════════════════════════════════════════

def send_winback_deactivated(email: str, domain: str, receipt: dict = None) -> bool:
    """
    D1 — Immediately after cancellation.
    Angle: Consequences. No begging. Just facts.
    """
    subject = 'Your protection has been paused'

    html = _email_header('Here\'s what changes now.', domain)
    html += _body_section(
        _p('Your IDR Shield membership has been cancelled.') +
        _p('Here\'s what changes immediately:') +
        '<p style="font-family:Arial,sans-serif;font-size:13px;color:#D94F4F;line-height:1.9;margin:0 0 16px;">' +
        '&#x2717; &nbsp;Monitoring has stopped<br>' +
        '&#x2717; &nbsp;Weekly rescans are no longer running<br>' +
        '&#x2717; &nbsp;Your registry record will no longer update<br>' +
        '&#x2717; &nbsp;Your badge (if installed) is no longer active</p>' +
        _p('Your Defense Package remains yours. But your protection is no longer active.', color='#555')
    )
    html += _body_section(
        _pull_quote('This doesn\'t mean something will happen. It means nothing will alert you if something does.') +
        _p('If this was unintentional, you can reactivate instantly.') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('Reactivate Membership', GUMROAD) +
        '</div>',
        '#faf8f4'
    )
    html += _email_footer()

    text = f"""Your protection has been paused — {domain}

Your IDR Shield membership has been cancelled.

Here's what changes immediately:
✗ Monitoring has stopped
✗ Weekly rescans are no longer running
✗ Your registry record will no longer update
✗ Your badge (if installed) is no longer active

Your Defense Package remains yours. But your protection is no longer active.

This doesn't mean something will happen. It means nothing will alert you if something does.

If this was unintentional, you can reactivate instantly.

Reactivate Membership: {GUMROAD}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)


def send_winback_status_changed(email: str, domain: str, receipt: dict = None) -> bool:
    """
    D2 — 7 days after cancellation. Final email.
    Angle: One last check. No desperation.
    """
    subject      = 'One last check — want to reactivate?'
    registry_url = f'{REGISTRY_BASE}/{domain}'

    html = _email_header('After this, we\'ll leave you alone.', domain)
    html += _body_section(
        _p('Just checking in one last time.') +
        _p('Your store has been unmonitored for a week.') +
        '<p style="font-family:Arial,sans-serif;font-size:13px;color:#D94F4F;line-height:1.9;margin:0 0 16px;">' +
        '&#x2717; &nbsp;No rescans<br>' +
        '&#x2717; &nbsp;No alerts<br>' +
        '&#x2717; &nbsp;No updates to your record</p>' +
        _pull_quote('If everything stays perfect, nothing happens. But stores rarely stay perfect.')
    )
    html += _body_section(
        _p('If you want to restore monitoring, your founding rate is still available.') +
        _p('If not, we\'ll leave you here.') +
        _pull_quote('Either way — your choice.') +
        '<div style="text-align:center;padding:8px 0;">' +
        _cta_button('Reactivate IDR Shield', GUMROAD) +
        '</div>',
        '#faf8f4'
    )
    html += _email_footer()

    text = f"""One last check — want to reactivate? — {domain}

Just checking in one last time.

Your store has been unmonitored for a week.
✗ No rescans
✗ No alerts
✗ No updates to your record

If everything stays perfect, nothing happens. But stores rarely stay perfect.

If you want to restore monitoring, your founding rate is still available.
If not, we'll leave you here.

Reactivate IDR Shield: {GUMROAD}

Institute of Digital Remediation · idrshield.com
"""
    return _send(email, subject, html, text)
