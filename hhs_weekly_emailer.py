"""
IDR Shield — hhs_weekly_emailer.py
Weekly scan summary and monthly compliance report emails for HHS monitoring clients.
"""

import os
from datetime import datetime, timezone

SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY', '')
FROM_EMAIL       = 'hello@idrshield.com'
FROM_NAME        = 'Hans-Peter Nkansah — Institute of Digital Remediation'
VERIFY_BASE      = 'https://idrshield.com/hhs-verify'
STRIPE_CONT_LINK = os.environ.get('STRIPE_CONT_LINK', 'https://buy.stripe.com/REPLACE')


def _send(to_email, subject, html):
    if not SENDGRID_API_KEY:
        print(f'[HHS_WEEKLY] No SENDGRID_API_KEY — skipping: {subject}')
        return False
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
        message = Mail(
            from_email=(FROM_EMAIL, FROM_NAME),
            to_emails=to_email,
            subject=subject,
            html_content=html,
        )
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        r  = sg.client.mail.send.post(request_body=message.get())
        print(f'[HHS_WEEKLY] Sent "{subject}" to {to_email} — {r.status_code}')
        return True
    except Exception as e:
        print(f'[HHS_WEEKLY] SendGrid error: {e}')
        return False


def _send_with_attachment(to_email, subject, html, pdf_bytes, filename):
    if not SENDGRID_API_KEY:
        print(f'[HHS_WEEKLY] No SENDGRID_API_KEY — skipping: {subject}')
        return False
    try:
        import base64, sendgrid
        from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
        message = Mail(
            from_email=(FROM_EMAIL, FROM_NAME),
            to_emails=to_email,
            subject=subject,
            html_content=html,
        )
        a = Attachment()
        a.file_content = FileContent(base64.b64encode(pdf_bytes).decode())
        a.file_name    = FileName(filename)
        a.file_type    = FileType('application/pdf')
        a.disposition  = Disposition('attachment')
        message.add_attachment(a)
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        r  = sg.client.mail.send.post(request_body=message.get())
        print(f'[HHS_WEEKLY] Sent "{subject}" + PDF to {to_email} — {r.status_code}')
        return True
    except Exception as e:
        print(f'[HHS_WEEKLY] SendGrid error: {e}')
        return False


def _sc(score):
    if score >= 80: return '#1A7A3C'
    if score >= 60: return '#C47F00'
    return '#B8280A'


def _hdr(eyebrow):
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
        '<body style="margin:0;padding:0;background:#F2EFE9;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F2EFE9;">'
        '<tr><td align="center" style="padding:32px 16px 0;">'
        '<table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;">'
        '<tr><td bgcolor="#C9A84C" height="4" style="font-size:0;">&nbsp;</td></tr>'
        '<tr><td bgcolor="#0A0E1A" style="padding:22px 40px 18px;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0"><tr>'
        '<td><div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.22em;'
        'text-transform:uppercase;color:rgba(201,168,76,0.55);">Institute of Digital Remediation · HHS Compliance</div>'
        '<div style="font-family:Georgia,serif;font-size:10px;font-style:italic;color:rgba(201,168,76,0.3);margin-top:2px;">'
        'Active Monitoring · 2026</div></td>'
        '<td align="right"><div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;'
        f'letter-spacing:0.18em;text-transform:uppercase;color:rgba(201,168,76,0.35);">{eyebrow}</div></td>'
        '</tr></table></td></tr>'
        '<tr><td bgcolor="#0A0E1A" style="padding:0 40px;">'
        '<div style="height:1px;background:rgba(201,168,76,0.12);"></div></td></tr>'
    )


def _ftr(domain, registry_id):
    verify_url = f'{VERIFY_BASE}/{domain}'
    return (
        '<tr><td bgcolor="#F2EFE9" style="padding:20px 40px;">'
        '<div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.2em;'
        'text-transform:uppercase;color:#AAAAAA;margin-bottom:6px;">Your Live Compliance Record</div>'
        f'<a href="{verify_url}" style="font-family:\'Courier New\',monospace;font-size:11px;'
        f'color:#8A6F2E;text-decoration:none;">{verify_url}</a>'
        f'<div style="margin-top:5px;font-family:\'Courier New\',monospace;font-size:9px;color:#BBBBBB;">'
        f'REGISTRY ID · {registry_id}</div></td></tr>'
        '<tr><td bgcolor="#FFFFFF" style="padding:16px 40px;border-top:1px solid #E8E4DC;">'
        '<div style="font-family:Arial,sans-serif;font-size:8px;color:#CCCCCC;line-height:1.6;">'
        'Institute of Digital Remediation · idrshield.com · IDR-BRAND-2026-01<br>'
        '<span style="font-style:italic;">Not a law firm. This is a compliance documentation system.</span>'
        '</div></td></tr>'
        '<tr><td bgcolor="#C9A84C" height="4" style="font-size:0;">&nbsp;</td></tr>'
        '</table></td></tr></table></body></html>'
    )


def _kv(key, val, highlight=False):
    bg  = '#FDF8F0' if highlight else '#FDFCF9'
    col = '#C9A84C' if highlight else '#555555'
    return (
        f'<tr><td bgcolor="{bg}" style="background:{bg};padding:9px 16px;border-bottom:1px solid #F0EDE8;">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.12em;'
        f'text-transform:uppercase;color:#AAAAAA;">{key}</span></td>'
        f'<td bgcolor="{bg}" style="background:{bg};padding:9px 16px;border-bottom:1px solid #F0EDE8;text-align:right;">'
        f'<span style="font-family:\'Courier New\',monospace;font-size:11px;color:{col};font-weight:{"700" if highlight else "400"};">'
        f'{val}</span></td></tr>'
    )


def _violation_row(rule, category, severity, status, days_open=None, closed_date=None):
    if status == 'CLOSED':
        st_col = '#1A7A3C'; st_bg = '#EEF8F2'
        st_label = f'CLOSED  {closed_date or ""}'
    elif days_open and days_open >= 30:
        st_col = '#B8280A'; st_bg = '#FDF0EE'
        st_label = f'OVERDUE · {days_open}d open'
    else:
        days_str = f' · {days_open}d' if days_open else ''
        st_col = '#C47F00' if severity == 'serious' else '#B8280A'
        st_bg  = '#FDFBF4' if severity == 'serious' else '#FDF4F4'
        st_label = f'OPEN{days_str}'
    sev_col = '#B8280A' if severity == 'critical' else '#C47F00' if severity == 'serious' else '#888888'
    return (
        f'<tr><td style="padding:8px 12px;border-bottom:1px solid #F0EDE8;vertical-align:middle;">'
        f'<div style="font-family:\'Courier New\',monospace;font-size:10px;color:#333;">{rule}</div>'
        f'<div style="font-family:Arial,sans-serif;font-size:8px;color:#AAAAAA;margin-top:2px;">{category}</div></td>'
        f'<td style="padding:8px 12px;border-bottom:1px solid #F0EDE8;text-align:center;">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;color:{sev_col};">'
        f'{severity.upper()}</span></td>'
        f'<td style="padding:8px 12px;border-bottom:1px solid #F0EDE8;text-align:right;">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;color:{st_col};'
        f'background:{st_bg};padding:3px 8px;border-radius:2px;">{st_label}</span></td></tr>'
    )


# ── WEEKLY SUMMARY EMAIL ──────────────────────────────────────────────────────

def send_hhs_weekly_summary(email, domain, org_name, registry_id,
                             scan_num, score_now, score_prev,
                             violations_closed, violations_open,
                             violations_new, timestamp_utc=''):
    """
    Fires every week for $49/month HHS monitoring clients.

    Args:
        scan_num        : int   — which scan this is (1, 2, 3, 4 in month)
        score_now       : int   — this week's score
        score_prev      : int   — last week's score (None if first scan)
        violations_closed: list — [{rule, category, severity, closed_date}]
        violations_open : list — [{rule, category, severity, days_open}]
        violations_new  : list — [{rule, category, severity}]
    """
    verify_url  = f'{VERIFY_BASE}/{domain}'
    date_str    = datetime.now(timezone.utc).strftime('%B %d, %Y')
    sc_col      = _sc(score_now)

    # Score delta
    if score_prev is not None:
        delta     = score_now - score_prev
        delta_str = f'+{delta}' if delta > 0 else str(delta)
        delta_col = '#1A7A3C' if delta > 0 else '#B8280A' if delta < 0 else '#AAAAAA'
        delta_html = (f'<span style="font-family:Arial,sans-serif;font-size:13px;font-weight:700;'
                      f'color:{delta_col};">({delta_str} from last week)</span>')
    else:
        delta_html = '<span style="font-family:Arial,sans-serif;font-size:11px;color:#AAAAAA;">(first scan)</span>'

    subject = f'Week {scan_num} Scan — {domain} · Score: {score_now}/100'

    html = (
        _hdr(f'Weekly Scan · Week {scan_num}') +

        f'<tr><td bgcolor="#FFFFFF" style="padding:32px 40px 24px;">'
        f'<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;'
        f'text-transform:uppercase;color:#8A6F2E;margin-bottom:10px;">Weekly Compliance Scan</div>'
        f'<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#0A0E1A;'
        f'margin-bottom:6px;line-height:1.3;">'
        f'<span style="color:{sc_col};">{score_now}/100</span> &nbsp; {delta_html}</div>'
        f'<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#888888;line-height:1.6;">'
        f'Automated weekly compliance scan for {org_name} ({domain}) — {date_str}</div>'
        f'</td></tr>'

        # Score + stats strip
        f'<tr><td bgcolor="#F2EFE9" style="padding:0 40px;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;">'
        + _kv('ACCESSIBILITY SCORE', f'{score_now} / 100', highlight=True)
        + _kv('VIOLATIONS CLOSED THIS WEEK', str(len(violations_closed)))
        + _kv('NEW VIOLATIONS FOUND', str(len(violations_new)))
        + _kv('TOTAL OPEN VIOLATIONS', str(len(violations_open)))
        + _kv('SCAN DATE', date_str)
        + _kv('REGISTRY STATUS', 'MONITORING ACTIVE')
        + f'</table></td></tr>'
    )

    # Closed violations
    if violations_closed:
        html += (
            f'<tr><td bgcolor="#FFFFFF" style="padding:24px 40px 8px;">'
            f'<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;'
            f'text-transform:uppercase;color:#1A7A3C;margin-bottom:12px;">✓ Closed This Week '
            f'({len(violations_closed)})</div></td></tr>'
            f'<tr><td bgcolor="#FFFFFF" style="padding:0 40px 16px;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="border:1px solid #E8E4DC;">'
        )
        for v in violations_closed:
            html += _violation_row(v['rule'], v['category'], v['severity'],
                                   'CLOSED', closed_date=v.get('closed_date', date_str))
        html += '</table></td></tr>'

    # New violations
    if violations_new:
        html += (
            f'<tr><td bgcolor="#FFFFFF" style="padding:24px 40px 8px;">'
            f'<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;'
            f'text-transform:uppercase;color:#B8280A;margin-bottom:12px;">⚠ New This Week '
            f'({len(violations_new)})</div></td></tr>'
            f'<tr><td bgcolor="#FFFFFF" style="padding:0 40px 16px;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="border:1px solid #E8E4DC;">'
        )
        for v in violations_new:
            html += _violation_row(v['rule'], v['category'], v['severity'], 'OPEN')
        html += '</table></td></tr>'

    # Still open
    if violations_open:
        overdue = [v for v in violations_open if v.get('days_open', 0) >= 30]
        html += (
            f'<tr><td bgcolor="#FFFFFF" style="padding:24px 40px 8px;">'
            f'<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;'
            f'text-transform:uppercase;color:#888888;margin-bottom:12px;">Still Open '
            f'({len(violations_open)})'
            + (f' · <span style="color:#B8280A;">{len(overdue)} OVERDUE</span>' if overdue else '')
            + f'</div></td></tr>'
            f'<tr><td bgcolor="#FFFFFF" style="padding:0 40px 16px;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="border:1px solid #E8E4DC;">'
        )
        for v in violations_open[:10]:  # cap at 10 in weekly
            html += _violation_row(v['rule'], v['category'], v['severity'],
                                   'OPEN', days_open=v.get('days_open', 0))
        if len(violations_open) > 10:
            html += (f'<tr><td colspan="3" style="padding:8px 12px;text-align:center;">'
                     f'<span style="font-family:Arial,sans-serif;font-size:9px;color:#AAAAAA;">'
                     f'+ {len(violations_open)-10} more — see full record at {verify_url}</span>'
                     f'</td></tr>')
        html += '</table></td></tr>'

    # No issues
    if not violations_open and not violations_new:
        html += (
            f'<tr><td bgcolor="#EEF8F2" style="padding:20px 40px;border-top:1px solid #D1FAE5;'
            f'border-bottom:1px solid #D1FAE5;">'
            f'<div style="font-family:Georgia,serif;font-size:14px;color:#1A7A3C;line-height:1.7;">'
            f'✓ No open violations detected this week. '
            f'{org_name} is currently meeting WCAG 2.1 Level AA requirements.</div></td></tr>'
        )

    # Public record note
    html += (
        f'<tr><td bgcolor="#FDFCF9" style="padding:20px 40px;border-top:1px solid #F0EDE8;">'
        f'<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.18em;'
        f'text-transform:uppercase;color:#C9A84C;margin-bottom:6px;">This Scan Is Now On Your Public Record</div>'
        f'<div style="font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.65;">'
        f'This week\'s scan results are logged to your public compliance record at '
        f'<a href="{verify_url}" style="color:#8A6F2E;">{verify_url}</a>. '
        f'HHS auditors, legal counsel, and investigators can view your continuous monitoring history there.'
        f'</div></td></tr>'
    )

    # Signature
    html += (
        f'<tr><td bgcolor="#FFFFFF" style="padding:20px 40px 28px;border-top:1px solid #F0EDE8;">'
        f'<div style="font-family:Georgia,serif;font-size:13px;color:#777777;line-height:1.75;">'
        f'Hans-Peter Nkansah<br>'
        f'<span style="font-family:Arial,sans-serif;font-size:10px;color:#AAAAAA;">'
        f'Lead Accessibility Auditor · Institute of Digital Remediation</span>'
        f'</div></td></tr>'
        + _ftr(domain, registry_id)
    )

    return _send(email, subject, html)


# ── MONTHLY COMPLIANCE REPORT EMAIL ──────────────────────────────────────────

def send_hhs_monthly_report(email, domain, org_name, registry_id,
                             month_label, scans, score_start, score_end,
                             total_closed, total_open, overdue_violations,
                             pdf_bytes=None):
    """
    Fires at end of month (4th weekly scan). Includes monthly PDF if generated.

    Args:
        month_label      : str  — e.g. "April 2026"
        scans            : list — [{week, date, score, closed, new_found}]
        score_start      : int  — score at start of month
        score_end        : int  — score at end of month
        total_closed     : int  — total violations closed this month
        total_open       : int  — total violations still open
        overdue_violations: list — [{rule, category, severity, days_open}]
        pdf_bytes        : bytes or None — monthly report PDF attachment
    """
    verify_url = f'{VERIFY_BASE}/{domain}'
    delta      = score_end - score_start
    delta_str  = f'+{delta}' if delta > 0 else str(delta)
    delta_col  = '#1A7A3C' if delta > 0 else '#B8280A' if delta < 0 else '#AAAAAA'

    subject = f'Monthly Compliance Report — {domain} · {month_label}'

    html = (
        _hdr(f'Monthly Report · {month_label}') +

        f'<tr><td bgcolor="#0A0E1A" style="padding:28px 40px;">'
        f'<div style="font-family:Arial,sans-serif;font-size:7px;font-weight:700;letter-spacing:0.26em;'
        f'text-transform:uppercase;color:rgba(201,168,76,0.5);margin-bottom:14px;">'
        f'HHS Compliance Monthly Summary · {month_label}</div>'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="padding:8px 0;border-bottom:1px solid rgba(240,232,216,0.08);">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.12em;'
        f'text-transform:uppercase;color:rgba(240,232,216,0.3);">Organization</span>'
        f'<span style="font-family:\'Courier New\',monospace;font-size:10px;color:#C9A84C;float:right;">'
        f'{org_name}</span></td></tr>'
        f'<tr><td style="padding:8px 0;border-bottom:1px solid rgba(240,232,216,0.08);">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.12em;'
        f'text-transform:uppercase;color:rgba(240,232,216,0.3);">Score This Month</span>'
        f'<span style="font-family:\'Courier New\',monospace;font-size:12px;font-weight:700;'
        f'color:{_sc(score_end)};float:right;">{score_end}/100 '
        f'<span style="color:{delta_col};font-size:10px;">({delta_str})</span></span></td></tr>'
        f'<tr><td style="padding:8px 0;border-bottom:1px solid rgba(240,232,216,0.08);">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.12em;'
        f'text-transform:uppercase;color:rgba(240,232,216,0.3);">Violations Closed</span>'
        f'<span style="font-family:\'Courier New\',monospace;font-size:11px;color:#1A7A3C;'
        f'font-weight:700;float:right;">{total_closed}</span></td></tr>'
        f'<tr><td style="padding:8px 0;">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.12em;'
        f'text-transform:uppercase;color:rgba(240,232,216,0.3);">Still Open</span>'
        f'<span style="font-family:\'Courier New\',monospace;font-size:11px;'
        f'color:{"#B8280A" if total_open > 0 else "#1A7A3C"};font-weight:700;float:right;">'
        f'{total_open}</span></td></tr>'
        f'</table></td></tr>'

        # Monthly scan history
        f'<tr><td bgcolor="#FFFFFF" style="padding:24px 40px 8px;">'
        f'<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;'
        f'text-transform:uppercase;color:#8A6F2E;margin-bottom:12px;">4-Week Scan History</div>'
        f'</td></tr>'
        f'<tr><td bgcolor="#FFFFFF" style="padding:0 40px 20px;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E8E4DC;">'
        f'<tr bgcolor="#F2EFE9">'
        f'<td style="padding:8px 12px;font-family:Arial,sans-serif;font-size:7px;font-weight:700;'
        f'letter-spacing:0.12em;text-transform:uppercase;color:#AAAAAA;">WEEK</td>'
        f'<td style="padding:8px 12px;font-family:Arial,sans-serif;font-size:7px;font-weight:700;'
        f'letter-spacing:0.12em;text-transform:uppercase;color:#AAAAAA;">DATE</td>'
        f'<td style="padding:8px 12px;font-family:Arial,sans-serif;font-size:7px;font-weight:700;'
        f'letter-spacing:0.12em;text-transform:uppercase;color:#AAAAAA;text-align:center;">SCORE</td>'
        f'<td style="padding:8px 12px;font-family:Arial,sans-serif;font-size:7px;font-weight:700;'
        f'letter-spacing:0.12em;text-transform:uppercase;color:#AAAAAA;text-align:center;">CLOSED</td>'
        f'<td style="padding:8px 12px;font-family:Arial,sans-serif;font-size:7px;font-weight:700;'
        f'letter-spacing:0.12em;text-transform:uppercase;color:#AAAAAA;text-align:center;">NEW</td>'
        f'</tr>'
    )
    for s in scans:
        sc_c = _sc(s['score'])
        html += (
            f'<tr><td style="padding:9px 12px;border-top:1px solid #F0EDE8;">'
            f'<span style="font-family:Arial,sans-serif;font-size:9px;color:#555;">Week {s["week"]}</span></td>'
            f'<td style="padding:9px 12px;border-top:1px solid #F0EDE8;">'
            f'<span style="font-family:Arial,sans-serif;font-size:9px;color:#888;">{s["date"]}</span></td>'
            f'<td style="padding:9px 12px;border-top:1px solid #F0EDE8;text-align:center;">'
            f'<span style="font-family:Georgia,serif;font-size:13px;font-weight:700;color:{sc_c};">'
            f'{s["score"]}</span></td>'
            f'<td style="padding:9px 12px;border-top:1px solid #F0EDE8;text-align:center;">'
            f'<span style="font-family:Arial,sans-serif;font-size:10px;color:#1A7A3C;font-weight:700;">'
            f'{s.get("closed", 0)}</span></td>'
            f'<td style="padding:9px 12px;border-top:1px solid #F0EDE8;text-align:center;">'
            f'<span style="font-family:Arial,sans-serif;font-size:10px;'
            f'color:{"#B8280A" if s.get("new_found",0) > 0 else "#AAAAAA"};">'
            f'{s.get("new_found", 0)}</span></td></tr>'
        )
    html += '</table></td></tr>'

    # Overdue violations
    if overdue_violations:
        html += (
            f'<tr><td bgcolor="#FDF0EE" style="padding:20px 40px;border-top:2px solid #B8280A;">'
            f'<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;'
            f'text-transform:uppercase;color:#B8280A;margin-bottom:10px;">'
            f'⚠ Overdue Violations — Action Required ({len(overdue_violations)})</div>'
            f'<div style="font-family:Georgia,serif;font-size:13px;color:#333;line-height:1.65;margin-bottom:12px;">'
            f'The following violations have been open for 30 or more days. '
            f'These represent the highest regulatory risk and should be escalated to your development team immediately.'
            f'</div>'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #F0C0B8;">'
        )
        for v in overdue_violations:
            html += _violation_row(v['rule'], v['category'], v['severity'],
                                   'OPEN', days_open=v.get('days_open', 30))
        html += '</table></td></tr>'

    # Public record + next month
    html += (
        f'<tr><td bgcolor="#FFFFFF" style="padding:20px 40px;border-top:1px solid #F0EDE8;">'
        f'<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.18em;'
        f'text-transform:uppercase;color:#C9A84C;margin-bottom:6px;">Your Public Compliance Record</div>'
        f'<div style="font-family:Georgia,serif;font-size:13px;color:#555555;line-height:1.65;">'
        f'Every scan this month is logged to your public compliance record at '
        f'<a href="{verify_url}" style="color:#8A6F2E;">{verify_url}</a>. '
        f'HHS OCR investigators, plaintiff counsel, and the general public can verify your '
        f'continuous monitoring history there. Weekly scans continue next month.'
        f'</div></td></tr>'
        f'<tr><td bgcolor="#FFFFFF" style="padding:16px 40px 24px;border-top:1px solid #F0EDE8;">'
        f'<div style="font-family:Georgia,serif;font-size:13px;color:#777;line-height:1.75;">'
        f'Hans-Peter Nkansah<br>'
        f'<span style="font-family:Arial,sans-serif;font-size:10px;color:#AAAAAA;">'
        f'Lead Accessibility Auditor · Institute of Digital Remediation</span>'
        f'</div></td></tr>'
        + _ftr(domain, registry_id)
    )

    # Send with or without PDF attachment
    if pdf_bytes:
        filename = f'IDR-HHS-MonthlyReport-{domain}-{month_label.replace(" ","-")}.pdf'
        return _send_with_attachment(email, subject, html, pdf_bytes, filename)
    return _send(email, subject, html)


# ── OVERDUE NOTICE EMAIL ──────────────────────────────────────────────────────

def send_hhs_overdue_notice(email, domain, org_name, registry_id,
                             overdue_violations, days_since_audit):
    """
    Fires when critical violations remain open 30+ days after initial audit.
    Documents that the organization was formally notified.
    """
    verify_url = f'{VERIFY_BASE}/{domain}'
    date_str   = datetime.now(timezone.utc).strftime('%B %d, %Y')

    subject = f'Compliance Action Required — {domain} · Overdue Violations'

    html = (
        _hdr('Overdue Notice') +

        f'<tr><td bgcolor="#FFFFFF" style="padding:32px 40px 24px;">'
        f'<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;'
        f'text-transform:uppercase;color:#B8280A;margin-bottom:10px;">Remediation Overdue</div>'
        f'<div style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#0A0E1A;'
        f'margin-bottom:8px;line-height:1.3;">'
        f'{len(overdue_violations)} critical violation(s) remain unresolved after {days_since_audit} days.</div>'
        f'<div style="font-family:Georgia,serif;font-size:13px;font-style:italic;color:#888888;line-height:1.6;">'
        f'This notice is being sent to {org_name} ({domain}) and logged to your compliance record '
        f'as formal notification of overdue remediation.</div></td></tr>'

        f'<tr><td bgcolor="#FDF0EE" style="padding:20px 40px;border-top:2px solid #B8280A;'
        f'border-bottom:2px solid #B8280A;">'
        f'<div style="font-family:Georgia,serif;font-size:14px;color:#333;line-height:1.7;">'
        f'The violations listed below were identified in your initial IDR HHS Accessibility Audit '
        f'and have not been resolved. Your development team has the fix guidance in your audit report '
        f'(Section 14). These must be addressed immediately to reduce regulatory exposure under '
        f'HHS Section 504 and Section 1557.'
        f'</div></td></tr>'

        f'<tr><td bgcolor="#FFFFFF" style="padding:20px 40px 8px;">'
        f'<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.22em;'
        f'text-transform:uppercase;color:#B8280A;margin-bottom:10px;">'
        f'Overdue Violations ({len(overdue_violations)})</div></td></tr>'
        f'<tr><td bgcolor="#FFFFFF" style="padding:0 40px 20px;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #F0C0B8;">'
    )
    for v in overdue_violations:
        html += _violation_row(v['rule'], v['category'], v['severity'],
                               'OPEN', days_open=v.get('days_open', days_since_audit))
    html += '</table></td></tr>'

    html += (
        f'<tr><td bgcolor="#FDFCF9" style="padding:20px 40px;border-top:1px solid #F0EDE8;">'
        f'<div style="font-family:Arial,sans-serif;font-size:7.5px;font-weight:700;letter-spacing:0.18em;'
        f'text-transform:uppercase;color:#8A6F2E;margin-bottom:8px;">What Happens Next</div>'
        f'<div style="font-family:Georgia,serif;font-size:13px;color:#555;line-height:1.65;">'
        f'IDR will continue weekly monitoring scans. The moment a violation disappears from your '
        f'live site, it is automatically marked closed in your registry record. '
        f'This overdue notice is logged to your public compliance record at '
        f'<a href="{verify_url}" style="color:#8A6F2E;">{verify_url}</a> as evidence that '
        f'your organization was formally notified and given every opportunity to remediate.'
        f'</div></td></tr>'
        f'<tr><td bgcolor="#FFFFFF" style="padding:16px 40px 24px;border-top:1px solid #F0EDE8;">'
        f'<div style="font-family:Georgia,serif;font-size:13px;color:#777;line-height:1.75;">'
        f'Hans-Peter Nkansah<br>'
        f'<span style="font-family:Arial,sans-serif;font-size:10px;color:#AAAAAA;">'
        f'Lead Accessibility Auditor · Institute of Digital Remediation</span>'
        f'</div></td></tr>'
        + _ftr(domain, registry_id)
    )

    return _send(email, subject, html)


# ── VERIFICATION CERTIFICATE EMAIL ────────────────────────────────────────────

def send_hhs_verification_certificate(email, domain, org_name, registry_id,
                                       original_score, verified_score,
                                       violations_closed, audit_date,
                                       certificate_pdf_bytes):
    """
    Fires when all critical violations from original audit are confirmed closed.
    Attaches the Verification Certificate PDF.
    """
    verify_url = f'{VERIFY_BASE}/{domain}'
    date_str   = datetime.now(timezone.utc).strftime('%B %d, %Y')

    subject = f'Remediation Verified — {domain} · IDR Verification Certificate'

    html = (
        _hdr('Remediation Verified') +

        f'<tr><td bgcolor="#FFFFFF" style="padding:32px 40px 24px;">'
        f'<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.28em;'
        f'text-transform:uppercase;color:#1A7A3C;margin-bottom:10px;">Remediation Verified</div>'
        f'<div style="font-family:Georgia,serif;font-size:24px;font-weight:700;color:#0A0E1A;'
        f'margin-bottom:8px;line-height:1.25;">'
        f'Your Verification Certificate is attached.</div>'
        f'<div style="font-family:Georgia,serif;font-size:14px;font-style:italic;color:#AAAAAA;line-height:1.7;">'
        f'All critical violations from the initial audit of {org_name} have been verified closed '
        f'by IDR external re-scan on {date_str}.</div></td></tr>'

        f'<tr><td bgcolor="#EEF8F2" style="padding:20px 40px;border-top:2px solid #1A7A3C;'
        f'border-bottom:2px solid #1A7A3C;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="padding:7px 0;border-bottom:1px solid rgba(26,122,60,0.1);">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.12em;'
        f'text-transform:uppercase;color:rgba(26,122,60,0.6);">Registry Status</span>'
        f'<span style="font-family:\'Courier New\',monospace;font-size:11px;font-weight:700;'
        f'color:#1A7A3C;float:right;">REMEDIATION VERIFIED</span></td></tr>'
        f'<tr><td style="padding:7px 0;border-bottom:1px solid rgba(26,122,60,0.1);">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.12em;'
        f'text-transform:uppercase;color:rgba(26,122,60,0.6);">Original Audit Score</span>'
        f'<span style="font-family:\'Courier New\',monospace;font-size:11px;color:#888;float:right;">'
        f'{original_score}/100</span></td></tr>'
        f'<tr><td style="padding:7px 0;border-bottom:1px solid rgba(26,122,60,0.1);">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.12em;'
        f'text-transform:uppercase;color:rgba(26,122,60,0.6);">Verified Score</span>'
        f'<span style="font-family:\'Courier New\',monospace;font-size:12px;font-weight:700;'
        f'color:#1A7A3C;float:right;">{verified_score}/100</span></td></tr>'
        f'<tr><td style="padding:7px 0;">'
        f'<span style="font-family:Arial,sans-serif;font-size:8px;letter-spacing:0.12em;'
        f'text-transform:uppercase;color:rgba(26,122,60,0.6);">Violations Closed</span>'
        f'<span style="font-family:\'Courier New\',monospace;font-size:12px;font-weight:700;'
        f'color:#1A7A3C;float:right;">{len(violations_closed)}</span></td></tr>'
        f'</table></td></tr>'

        f'<tr><td bgcolor="#0A0E1A" style="padding:16px 40px;">'
        f'<table cellpadding="0" cellspacing="0" border="0"><tr>'
        f'<td width="24" style="vertical-align:middle;padding-right:10px;">'
        f'<div style="font-size:18px;">📄</div></td>'
        f'<td style="vertical-align:middle;">'
        f'<div style="font-family:Arial,sans-serif;font-size:8px;font-weight:700;letter-spacing:0.18em;'
        f'text-transform:uppercase;color:rgba(201,168,76,0.6);margin-bottom:2px;">Attached</div>'
        f'<div style="font-family:\'Courier New\',monospace;font-size:10px;color:#C9A84C;">'
        f'IDR-HHS-VerificationCertificate-{domain}.pdf</div>'
        f'<div style="font-family:Arial,sans-serif;font-size:9px;color:rgba(255,255,255,0.25);margin-top:2px;">'
        f'Court-ready remediation verification · Signed by Hans-Peter Nkansah</div>'
        f'</td></tr></table></td></tr>'

        f'<tr><td bgcolor="#FFFFFF" style="padding:20px 40px;border-top:1px solid #F0EDE8;">'
        f'<div style="font-family:Georgia,serif;font-size:13px;color:#555;line-height:1.65;">'
        f'Your public verification page at <a href="{verify_url}" style="color:#8A6F2E;">{verify_url}</a> '
        f'has been updated to reflect <strong>REMEDIATION VERIFIED</strong> status. '
        f'Any party — including HHS OCR and legal counsel — can verify this record in real time.'
        f'</div></td></tr>'

        f'<tr><td bgcolor="#FFFFFF" style="padding:16px 40px 24px;border-top:1px solid #F0EDE8;">'
        f'<div style="font-family:Georgia,serif;font-size:13px;color:#777;line-height:1.75;">'
        f'Hans-Peter Nkansah<br>'
        f'<span style="font-family:Arial,sans-serif;font-size:10px;color:#AAAAAA;">'
        f'Lead Accessibility Auditor · Institute of Digital Remediation</span>'
        f'</div></td></tr>'
        + _ftr(domain, registry_id)
    )

    filename = f'IDR-HHS-VerificationCertificate-{domain}.pdf'
    return _send_with_attachment(email, subject, html, certificate_pdf_bytes, filename)
