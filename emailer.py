"""
IDR Email Delivery
SendGrid integration for receipt delivery and alerts.
Falls back gracefully if SENDGRID_API_KEY not set.
"""

import os
import json
import base64
from datetime import datetime, timezone

SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'hello@idrshield.com')
FROM_NAME = 'Institute of Digital Remediation'


def _send(to_email: str, subject: str, html_body: str,
          text_body: str = None, attachments: list = None) -> bool:
    if not SENDGRID_API_KEY:
        print(f"[EMAIL SKIPPED — no API key] To: {to_email} | Subject: {subject}")
        return False

    try:
        import urllib.request
        import urllib.error

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

        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            'https://api.sendgrid.com/v3/mail/send',
            data=data,
            headers={
                'Authorization': f'Bearer {SENDGRID_API_KEY}',
                'Content-Type': 'application/json'
            },
            method='POST'
        )
        with urllib.request.urlopen(req) as response:
            print(f"Email sent to {to_email} — status {response.status}")
            return True

    except Exception as e:
        print(f"Email error: {e}")
        return False


def send_activation_receipt(email: str, receipt: dict) -> bool:
    scan = receipt.get('scan', {})
    domain = scan.get('domain', 'your store')
    score = scan.get('overall_score', 0)
    status = scan.get('overall_status', 'unknown').upper()
    receipt_id = receipt.get('receipt_id', '')
    registry_id = receipt.get('registry_id', '')
    registry_url = receipt.get('registry_url', '')
    timestamp = receipt.get('timestamp_utc', '')
    critical = scan.get('critical_count', 0)
    total = scan.get('total_issues', 0)
    hash_val = receipt.get('hash', {}).get('value', '')

    # Generate PDF attachment
    attachments = []
    try:
        from receipt.pdf_generator import generate_pdf
        pdf_bytes = generate_pdf(receipt)
        pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
        filename = f"IDR-Receipt-{domain}-{receipt_id[:8]}.pdf"
        attachments = [{
            "content": pdf_b64,
            "type": "application/pdf",
            "filename": filename,
            "disposition": "attachment"
        }]
        print(f"PDF attached: {filename} ({len(pdf_bytes):,} bytes)")
    except Exception as e:
        print(f"PDF generation for email failed (sending without): {e}")

    status_color = '#e05555' if status == 'FAIL' else ('#f0a500' if status == 'WARNING' else '#50c878')

    subject = f"Your IDR Scan Receipt — {domain}"

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Georgia,serif;background:#f5f5f5;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">

  <!-- Header -->
  <div style="background:#080d1a;padding:32px 40px;border-bottom:3px solid #C4A052;">
    <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;letter-spacing:0.2em;text-transform:uppercase;color:rgba(196,160,82,0.6);margin:0 0 8px;">Institute of Digital Remediation</p>
    <h1 style="font-size:24px;font-weight:normal;color:#F0E8D8;margin:0;">IDR Scan Receipt</h1>
    <p style="font-size:13px;color:rgba(240,232,216,0.5);margin:8px 0 0;font-family:Arial,sans-serif;">Official Compliance Record — {timestamp[:10]}</p>
  </div>

  <!-- Receipt IDs -->
  <div style="background:#0d1526;padding:24px 40px;border-bottom:1px solid rgba(196,160,82,0.2);">
    <table style="width:100%;font-family:Arial,sans-serif;font-size:12px;">
      <tr>
        <td style="color:rgba(196,160,82,0.6);letter-spacing:0.1em;text-transform:uppercase;padding-bottom:8px;">Receipt ID</td>
        <td style="color:#F0E8D8;font-family:monospace;text-align:right;">{receipt_id}</td>
      </tr>
      <tr>
        <td style="color:rgba(196,160,82,0.6);letter-spacing:0.1em;text-transform:uppercase;padding-bottom:8px;">Registry ID</td>
        <td style="color:#F0E8D8;font-family:monospace;text-align:right;">{registry_id}</td>
      </tr>
      <tr>
        <td style="color:rgba(196,160,82,0.6);letter-spacing:0.1em;text-transform:uppercase;">Domain</td>
        <td style="color:#F0E8D8;text-align:right;">{domain}</td>
      </tr>
    </table>
  </div>

  <!-- Score -->
  <div style="padding:32px 40px;border-bottom:1px solid #e0e0e0;text-align:center;">
    <p style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#666;margin:0 0 12px;">Overall Score</p>
    <div style="font-size:56px;font-weight:bold;color:#080d1a;line-height:1;">{score}</div>
    <div style="font-size:18px;color:#999;margin-bottom:16px;">/ 100</div>
    <span style="background:{status_color};color:#fff;font-family:Arial,sans-serif;font-size:12px;font-weight:700;letter-spacing:0.1em;padding:6px 20px;border-radius:20px;">{status}</span>
    <p style="font-family:Arial,sans-serif;font-size:13px;color:#666;margin:16px 0 0;">{critical} critical issues &nbsp;·&nbsp; {total} total issues</p>
  </div>

  <!-- Registry -->
  <div style="padding:24px 40px;background:#f9f9f9;border-bottom:1px solid #e0e0e0;">
    <p style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#666;margin:0 0 8px;">Registry Record</p>
    <a href="{registry_url}" style="color:#C4A052;font-size:14px;">{registry_url}</a>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin:8px 0 0;">This URL is publicly verifiable. Anyone can confirm your compliance record.</p>
  </div>

  <!-- Hash -->
  <div style="padding:24px 40px;border-bottom:1px solid #e0e0e0;">
    <p style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#666;margin:0 0 8px;">SHA-256 Verification Hash</p>
    <p style="font-family:monospace;font-size:11px;color:#333;word-break:break-all;background:#f5f5f5;padding:12px;border-radius:3px;">{hash_val}</p>
    <p style="font-family:Arial,sans-serif;font-size:12px;color:#999;margin:8px 0 0;">Any change to this receipt produces a different hash. Tamper-evident by design.</p>
  </div>

  <!-- Next Steps -->
  <div style="padding:32px 40px;border-bottom:1px solid #e0e0e0;">
    <p style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:0.15em;text-transform:uppercase;color:#666;margin:0 0 16px;">Next Steps</p>
    <p style="font-family:Georgia,serif;font-size:15px;color:#333;line-height:1.7;margin:0 0 12px;">1. Add your IDR Verified badge to your store footer — instructions at <a href="https://idrshield.com" style="color:#C4A052;">idrshield.com</a></p>
    <p style="font-family:Georgia,serif;font-size:15px;color:#333;line-height:1.7;margin:0 0 12px;">2. Your next automated scan is scheduled for 7 days from today</p>
    <p style="font-family:Georgia,serif;font-size:15px;color:#333;line-height:1.7;margin:0;">3. You will be alerted immediately if any new violations are detected</p>
  </div>

  <!-- Footer -->
  <div style="padding:24px 40px;background:#080d1a;">
    <p style="font-family:Arial,sans-serif;font-size:11px;color:rgba(240,232,216,0.4);margin:0;line-height:1.6;">Institute of Digital Remediation is not a law firm and does not provide legal advice. This receipt is a compliance documentation system.<br>IDR-PROTOCOL-2026 &nbsp;·&nbsp; idrshield.com &nbsp;·&nbsp; hello@idrshield.com</p>
  </div>

</div>
</body>
</html>
"""

    text = f"""IDR SCAN RECEIPT
Institute of Digital Remediation

Receipt ID:   {receipt_id}
Registry ID:  {registry_id}
Domain:       {domain}
Score:        {score}/100 — {status}
Critical:     {critical}
Total Issues: {total}

Registry URL: {registry_url}

SHA-256 Hash: {hash_val}

This receipt is tamper-evident. Any modification produces a different hash.

Next steps:
1. Add IDR badge to your store footer at idrshield.com
2. Your next scan is scheduled in 7 days
3. You will be alerted if new violations are detected

Institute of Digital Remediation
hello@idrshield.com | idrshield.com
"""

    return _send(email, subject, html, text, attachments=attachments)


def send_scan_alert(email: str, domain: str, scanner_ip: str, findings: dict) -> bool:
    subject = f"⚠️ Your store was scanned by an unknown party — {domain}"
    score = findings.get('overall_score', 0)
    critical = findings.get('critical_count', 0)
    total = findings.get('total_issues', 0)

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Georgia,serif;background:#f5f5f5;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">
  <div style="background:#080d1a;padding:32px 40px;border-bottom:3px solid #e05555;">
    <h1 style="font-size:22px;font-weight:normal;color:#F0E8D8;margin:0;">⚠️ Scan Alert</h1>
    <p style="font-size:13px;color:rgba(240,232,216,0.5);margin:8px 0 0;font-family:Arial,sans-serif;">Your store was scanned by an unknown party</p>
  </div>
  <div style="padding:32px 40px;">
    <p style="font-size:16px;color:#333;line-height:1.7;">An automated accessibility scan was run against <strong>{domain}</strong> by an external party.</p>
    <p style="font-size:15px;color:#666;">Score: <strong>{score}/100</strong> &nbsp;·&nbsp; Critical issues: <strong>{critical}</strong> &nbsp;·&nbsp; Total: <strong>{total}</strong></p>
    <p style="font-size:15px;color:#333;line-height:1.7;">Plaintiff law firms use automated scanners exactly like this one to identify stores before sending demand letters. Your IDR Shield is monitoring and documenting your compliance record.</p>
    <p style="margin-top:24px;"><a href="https://idrshield.com" style="background:#C4A052;color:#080d1a;padding:12px 24px;text-decoration:none;font-family:Arial,sans-serif;font-weight:700;font-size:12px;letter-spacing:0.1em;">VIEW YOUR REGISTRY RECORD</a></p>
  </div>
  <div style="padding:24px 40px;background:#f9f9f9;border-top:1px solid #e0e0e0;">
    <p style="font-family:Arial,sans-serif;font-size:11px;color:#999;margin:0;">Institute of Digital Remediation &nbsp;·&nbsp; idrshield.com</p>
  </div>
</div>
</body>
</html>
"""

    text = f"""SCAN ALERT — {domain}

Your store was scanned by an unknown party.

Score: {score}/100 | Critical: {critical} | Total: {total}

Plaintiff firms use automated scanners like this to identify targets before sending demand letters. Your IDR Shield is active.

View your registry: https://idrshield.com/verify/{domain}

Institute of Digital Remediation
idrshield.com
"""

    return _send(email, subject, html, text)


def send_weekly_scan_alert(email: str, domain: str, new_issues: list, receipt_id: str) -> bool:
    count = len(new_issues)
    subject = f"IDR Weekly Scan — {count} new issue{'s' if count != 1 else ''} found on {domain}"

    issues_html = ""
    for issue in new_issues[:5]:
        severity_color = '#e05555' if issue.get('severity') == 'critical' else '#f0a500'
        issues_html += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">
                <span style="background:{severity_color};color:#fff;font-size:10px;padding:2px 8px;border-radius:10px;font-family:Arial,sans-serif;">{issue.get('severity','').upper()}</span>
            </td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;font-size:13px;color:#333;">{issue.get('description','')}</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;font-size:11px;color:#999;font-family:monospace;">WCAG {issue.get('wcag','')}</td>
        </tr>"""

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Georgia,serif;background:#f5f5f5;margin:0;padding:40px 20px;">
<div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #e0e0e0;">
  <div style="background:#080d1a;padding:32px 40px;border-bottom:3px solid #C4A052;">
    <p style="font-family:Arial,sans-serif;font-size:10px;letter-spacing:0.2em;text-transform:uppercase;color:rgba(196,160,82,0.6);margin:0 0 8px;">IDR Weekly Scan Report</p>
    <h1 style="font-size:22px;font-weight:normal;color:#F0E8D8;margin:0;">{count} New Issue{'s' if count != 1 else ''} Detected</h1>
    <p style="font-size:13px;color:rgba(240,232,216,0.5);margin:8px 0 0;font-family:Arial,sans-serif;">{domain}</p>
  </div>
  <div style="padding:32px 40px;">
    <p style="font-size:15px;color:#333;line-height:1.7;">Your weekly IDR scan found {count} new accessibility issue{'s' if count != 1 else ''} that were not present in your previous scan.</p>
    <table style="width:100%;border-collapse:collapse;margin-top:16px;">
      {issues_html}
    </table>
    <p style="font-size:13px;color:#666;margin-top:16px;">Fix these issues and mark them resolved in your IDR dashboard. IDR will run a confirmation scan within 24 hours.</p>
    <p style="margin-top:24px;"><a href="https://idrshield.com" style="background:#C4A052;color:#080d1a;padding:12px 24px;text-decoration:none;font-family:Arial,sans-serif;font-weight:700;font-size:12px;letter-spacing:0.1em;">VIEW FULL REPORT</a></p>
  </div>
  <div style="padding:24px 40px;background:#f9f9f9;border-top:1px solid #e0e0e0;">
    <p style="font-family:Arial,sans-serif;font-size:11px;color:#999;margin:0;">Receipt ID: {receipt_id} &nbsp;·&nbsp; Institute of Digital Remediation &nbsp;·&nbsp; idrshield.com</p>
  </div>
</div>
</body>
</html>
"""

    text = f"IDR Weekly Scan — {count} new issues on {domain}\n\nReceipt: {receipt_id}\n\nView at idrshield.com"
    return _send(email, subject, html, text)
