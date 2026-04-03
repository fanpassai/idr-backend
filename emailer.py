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
