"""
IDR Cron Scheduler — v3
Three jobs run on background threads:

1. Email queue processor (every hour, fires due sequence emails)
2. Weekly rescan engine (every hour check, rescan e-commerce/ADA clients if due)
3. HHS monitoring cycle (every hour check, weekly scan for $49/mo HHS clients)
"""

import os
import threading
import time
import json
from datetime import datetime, timezone, timedelta


RESCAN_INTERVAL_DAYS = int(os.environ.get('RESCAN_INTERVAL_DAYS', '7'))
CRON_ENABLED = os.environ.get('CRON_ENABLED', 'true').lower() == 'true'


# ── Sequence definitions ──────────────────────────────────────────────────────

FREE_SCANNER_STEPS = [
    (2, 23),
    (3, 72),
    (4, 120),
    (5, 168),
    (6, 336),
]

FOUNDER_STEPS = [
    (3, 48),
    (4, 168),
    (5, 336),
    (6, 720),
]

WIN_BACK_STEPS = [
    (1, 1),
    (2, 168),
]

RESCAN_NUDGE_STEPS = [
    (1, 48),
    (2, 96),
    (3, 144),
]

# ── HHS Upsell Sequence ───────────────────────────────────────────────────────
# Fires after $497 audit payment. Stops if $49/mo monitoring purchased.

HHS_UPSELL_STEPS = [
    (2, 48),    # Day 2  — monitoring comparison
    (5, 120),   # Day 5  — record snapshot
    (9, 216),   # Day 9  — final window
]

# HHS monitoring uses run_hhs_monitoring_cycle() directly, not the queue
HHS_MONITORING_STEPS = []


# ── Email dispatcher ──────────────────────────────────────────────────────────

def dispatch_email(row: dict) -> bool:
    sequence = row['sequence']
    step     = row['step']
    email    = row['email']
    domain   = row['domain']
    receipt  = json.loads(row['receipt_json']) if row.get('receipt_json') else {}

    print(f"[QUEUE] Dispatching {sequence} step {step} → {email}")

    try:
        # ── Free scanner nurture ──────────────────────────────────────────────
        if sequence == 'free_scanner':
            from emailer import (
                send_nurture_day1,
                send_nurture_day3,
                send_nurture_day5,
                send_nurture_day7,
                send_nurture_day14,
            )
            dispatch = {
                2: send_nurture_day1,
                3: send_nurture_day3,
                4: send_nurture_day5,
                5: send_nurture_day7,
                6: send_nurture_day14,
            }
            fn = dispatch.get(step)
            if fn:
                return fn(email, domain, receipt)

        # ── Founder onboarding ────────────────────────────────────────────────
        elif sequence == 'founder':
            from emailer import (
                send_founder_badge_guide,
                send_founder_monitoring_active,
                send_founder_rescan_incoming,
                send_founder_30day_summary,
            )
            dispatch = {
                3: send_founder_badge_guide,
                4: send_founder_monitoring_active,
                5: send_founder_rescan_incoming,
                6: send_founder_30day_summary,
            }
            fn = dispatch.get(step)
            if fn:
                return fn(email, domain, receipt)

        # ── Win-back ──────────────────────────────────────────────────────────
        elif sequence == 'win_back':
            from emailer import (
                send_winback_deactivated,
                send_winback_status_changed,
            )
            dispatch = {
                1: send_winback_deactivated,
                2: send_winback_status_changed,
            }
            fn = dispatch.get(step)
            if fn:
                return fn(email, domain)

        # ── Rescan nudge ──────────────────────────────────────────────────────
        elif sequence == 'rescan_nudge':
            from emailer import send_fix_nudge
            hours_map = {1: 48, 2: 96, 3: 144}
            hours = hours_map.get(step, 48)
            receipt_id = json.loads(row['receipt_json']).get('receipt_id', '') if row.get('receipt_json') else ''
            return send_fix_nudge(email, domain, hours, receipt_id=receipt_id)

        # ── HHS upsell sequence ───────────────────────────────────────────────
        elif sequence == 'hhs_upsell':
            from hhs_emailer import (
                send_hhs_day2_monitoring,
                send_hhs_day5_snapshot,
                send_hhs_day9_final,
            )
            registry_id = receipt.get('registry_id') or None
            if step == 2:
                return send_hhs_day2_monitoring(email, domain, registry_id=registry_id)
            elif step == 5:
                return send_hhs_day5_snapshot(email, domain, registry_id=registry_id)
            elif step == 9:
                return send_hhs_day9_final(email, domain, registry_id=registry_id)

        print(f"[QUEUE] No handler for {sequence} step {step}")
        return False

    except ImportError as e:
        print(f"[QUEUE] Email function not yet implemented: {e} — skipping")
        return False
    except Exception as e:
        print(f"[QUEUE] Dispatch error for {sequence} step {step}: {e}")
        return False


# ── Email queue processor ─────────────────────────────────────────────────────

def process_email_queue():
    from database import get_due_emails, mark_email_sent
    due = get_due_emails()
    if not due:
        return
    print(f"[QUEUE] {len(due)} email(s) due")
    sent, skipped = 0, 0
    for row in due:
        success = dispatch_email(row)
        if success:
            mark_email_sent(row['id'])
            sent += 1
        else:
            mark_email_sent(row['id'])
            skipped += 1
    print(f"[QUEUE] Cycle complete — {sent} sent, {skipped} skipped")


# ── E-commerce/ADA weekly rescan engine ──────────────────────────────────────
# Rescans ALL non-expired domains (e-commerce ADA clients).
# HHS monitoring clients are handled separately by run_hhs_monitoring_cycle().

def get_domains_due_for_rescan(db_conn_fn) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RESCAN_INTERVAL_DAYS)
    try:
        conn = db_conn_fn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT domain, activated_by
                FROM registry
                WHERE (last_scanned < %s OR last_scanned IS NULL)
                  AND status != 'expired'
                  AND (hhs_enrolled = FALSE OR hhs_enrolled IS NULL)
                ORDER BY last_scanned ASC NULLS FIRST
                LIMIT 50
            """, (cutoff,))
            rows = cur.fetchall()
        conn.close()
        return [(row[0], row[1]) for row in rows]
    except Exception as e:
        print(f"[CRON] Error fetching domains: {e}")
        return []


def rescan_domain(domain: str, email: str = None):
    from scanner.engine import scan_url
    from receipt.generator import generate_receipt
    from emailer import send_weekly_scan_alert

    try:
        url = f"https://{domain}"
        print(f"[CRON] Rescanning {url}")
        result = scan_url(url)
        if result.error:
            print(f"[CRON] Scan failed for {domain}: {result.error}")
            return False

        receipt = generate_receipt(result)
        if email:
            receipt['activated_by'] = email

        from database import save_receipt, upsert_registry, log_evidence, get_conn
        save_receipt(receipt, email)
        upsert_registry(domain, receipt, email)
        log_evidence(domain, receipt['receipt_id'], 'WEEKLY_RESCAN',
                     f"Automated weekly rescan. Score: {result.overall_score}/100")

        if email and result.critical_count > 0:
            scan_data = receipt.get('scan', {})
            new_issues = []
            for cat in scan_data.get('categories', []):
                for issue in cat.get('issues', []):
                    if issue.get('severity') in ('critical', 'serious'):
                        new_issues.append(issue)
            if new_issues:
                send_weekly_scan_alert(email, domain, new_issues, receipt['receipt_id'])
                print(f"[CRON] Alert sent to {email} for {domain}")
                from database import queue_sequence
                queue_sequence(
                    email    = email,
                    domain   = domain,
                    sequence = 'rescan_nudge',
                    receipt  = receipt,
                    steps    = RESCAN_NUDGE_STEPS
                )

        print(f"[CRON] Rescan complete: {domain} → {result.overall_score}/100")
        return True

    except Exception as e:
        print(f"[CRON] Exception rescanning {domain}: {e}")
        return False


def run_rescan_cycle():
    from database import get_conn
    print(f"[CRON] Rescan cycle at {datetime.now(timezone.utc).isoformat()}")
    domains = get_domains_due_for_rescan(get_conn)
    if not domains:
        print("[CRON] No domains due for rescan")
        return
    print(f"[CRON] {len(domains)} domain(s) due")
    success, failed = 0, 0
    for domain, email in domains:
        ok = rescan_domain(domain, email)
        if ok:
            success += 1
        else:
            failed += 1
        time.sleep(3)
    print(f"[CRON] Rescan cycle complete — {success} ok, {failed} failed")


# ── HHS monitoring cycle ──────────────────────────────────────────────────────
# Only runs for $49/month HHS monitoring clients.
# hhs_enrolled = TRUE AND status = 'active'
# Sends: weekly summary, monthly report, overdue notices, verification certificate.

def _get_hhs_monitoring_domains() -> list:
    """Return HHS monitoring clients due for weekly scan."""
    from database import get_conn
    cutoff_days = 6
    try:
        conn = get_conn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT domain, activated_by, registry_id,
                       last_scanned, scan_count, latest_score
                FROM registry
                WHERE hhs_enrolled = TRUE
                  AND status = 'active'
                  AND (
                    last_scanned IS NULL
                    OR last_scanned < NOW() - INTERVAL '6 days'
                  )
                ORDER BY last_scanned ASC NULLS FIRST
                LIMIT 100
            """)
            rows = cur.fetchall()
        conn.close()
        return [
            {
                'domain':      r[0],
                'email':       r[1],
                'registry_id': r[2],
                'last_scanned': r[3],
                'scan_count':  r[4] or 0,
                'prev_score':  r[5],
            }
            for r in rows
        ]
    except Exception as e:
        print(f"[HHS_CRON] Error fetching HHS domains: {e}")
        return []


def _get_original_violations(domain: str) -> list:
    """Fetch violations from the original (first) audit receipt."""
    from database import get_conn
    try:
        conn = get_conn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT receipt_json FROM receipts
                WHERE domain = %s
                ORDER BY timestamp_utc ASC
                LIMIT 1
            """, (domain,))
            row = cur.fetchone()
        conn.close()
        if not row:
            return []
        receipt = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        violations = []
        for cat in receipt.get('scan', {}).get('categories', []):
            for issue in cat.get('issues', []):
                violations.append({
                    'rule':     issue.get('rule', ''),
                    'category': cat.get('name', ''),
                    'severity': issue.get('severity', ''),
                    'wcag':     issue.get('wcag', ''),
                    'count':    issue.get('count', 0),
                })
        return violations
    except Exception as e:
        print(f"[HHS_CRON] Error fetching original violations for {domain}: {e}")
        return []


def _get_previous_scan_violations(domain: str) -> list:
    """Get violations from the most recent previous scan."""
    from database import get_conn
    try:
        conn = get_conn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT receipt_json FROM receipts
                WHERE domain = %s
                ORDER BY timestamp_utc DESC
                LIMIT 1
            """, (domain,))
            row = cur.fetchone()
        conn.close()
        if not row:
            return []
        receipt = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        violations = []
        for cat in receipt.get('scan', {}).get('categories', []):
            for issue in cat.get('issues', []):
                violations.append({
                    'rule':     issue.get('rule', ''),
                    'category': cat.get('name', ''),
                    'severity': issue.get('severity', ''),
                    'wcag':     issue.get('wcag', ''),
                })
        return violations
    except Exception as e:
        print(f"[HHS_CRON] Error fetching previous scan for {domain}: {e}")
        return []


def _compare_scans(prev_violations: list, curr_violations: list,
                   original_violations: list) -> dict:
    """
    Compare previous scan to current scan.
    Returns closed, new_found, still_open, orig_closed, orig_still_open.
    """
    prev_rules = {v['rule'] for v in prev_violations}
    curr_rules = {v['rule'] for v in curr_violations}
    orig_rules = {v['rule'] for v in original_violations}

    closed_rules  = prev_rules - curr_rules
    new_rules     = curr_rules - prev_rules
    orig_closed   = orig_rules - curr_rules

    def _find(rules, source):
        return [v for v in source if v['rule'] in rules]

    still_open = [dict(v) for v in curr_violations]

    return {
        'closed':          _find(closed_rules, prev_violations),
        'new_found':       _find(new_rules, curr_violations),
        'still_open':      still_open,
        'orig_closed':     [v for v in original_violations if v['rule'] in orig_closed],
        'orig_still_open': [v for v in original_violations if v['rule'] not in orig_closed],
    }


def _check_verification_ready(domain: str, curr_violations: list,
                                original_violations: list) -> bool:
    """
    Returns True if ALL critical violations from the original audit are now gone.
    Triggers Verification Certificate generation.
    """
    orig_crits = {v['rule'] for v in original_violations
                  if v.get('severity', '').lower() == 'critical'}
    if not orig_crits:
        return False
    curr_rules = {v['rule'] for v in curr_violations}
    return not (orig_crits & curr_rules)  # no original criticals remain


def _get_org_name(domain: str) -> str:
    """Pull org name from the original receipt."""
    from database import get_conn
    try:
        conn = get_conn()
        if not conn:
            return domain
        with conn.cursor() as cur:
            cur.execute("""
                SELECT receipt_json FROM receipts
                WHERE domain = %s ORDER BY timestamp_utc ASC LIMIT 1
            """, (domain,))
            row = cur.fetchone()
        conn.close()
        if not row:
            return domain
        receipt = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return receipt.get('organization', {}).get('name', domain)
    except Exception:
        return domain


def _get_monthly_scan_history(domain: str) -> list:
    """Get last 4 scan scores for monthly report."""
    from database import get_conn
    try:
        conn = get_conn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT overall_score, timestamp_utc
                FROM receipts
                WHERE domain = %s
                ORDER BY timestamp_utc DESC
                LIMIT 4
            """, (domain,))
            rows = cur.fetchall()
        conn.close()
        scans = []
        for i, r in enumerate(reversed(rows)):
            scans.append({
                'week':      i + 1,
                'date':      r[1].strftime('%b %d') if r[1] else '—',
                'score':     r[0] or 0,
                'closed':    0,
                'new_found': 0,
            })
        return scans
    except Exception as e:
        print(f"[HHS_CRON] Error fetching scan history: {e}")
        return []


def run_hhs_monitoring_cycle():
    """
    HHS-specific weekly scan cycle for $49/month monitoring clients.
    - Week 1/2/3: weekly summary email
    - Week 4:     monthly report email (+ overdue notices if needed)
    - Any week:   Verification Certificate if all original criticals are closed
    """
    from database import save_receipt, upsert_registry, log_evidence, get_conn
    from scanner.engine import scan_url
    from receipt.generator import generate_receipt

    print(f"[HHS_CRON] HHS monitoring cycle at {datetime.now(timezone.utc).isoformat()}")

    domains = _get_hhs_monitoring_domains()
    if not domains:
        print("[HHS_CRON] No HHS monitoring domains due for scan")
        return

    print(f"[HHS_CRON] {len(domains)} HHS domain(s) due")

    for d in domains:
        domain      = d['domain']
        email       = d['email']
        registry_id = d['registry_id'] or f'IDR-HHS-{domain.upper().replace(".", "-")}'
        prev_score  = d['prev_score'] or 0
        scan_count  = d['scan_count']

        print(f"[HHS_CRON] Scanning {domain} (scan #{scan_count + 1})")

        try:
            # Run the scan
            result = scan_url(f'https://{domain}')
            if result.error:
                print(f"[HHS_CRON] Scan failed for {domain}: {result.error}")
                continue

            receipt = generate_receipt(result)
            receipt['activated_by'] = email
            save_receipt(receipt, email)
            upsert_registry(domain, receipt, email)
            log_evidence(
                domain, receipt['receipt_id'], 'HHS_WEEKLY_SCAN',
                f'HHS monitoring scan #{scan_count + 1}. '
                f'Score: {result.overall_score}/100. '
                f'Critical: {result.critical_count}.'
            )

            # Build current violations list
            curr_violations = []
            for cat in receipt.get('scan', {}).get('categories', []):
                for issue in cat.get('issues', []):
                    curr_violations.append({
                        'rule':     issue.get('rule', ''),
                        'category': cat.get('name', ''),
                        'severity': issue.get('severity', ''),
                        'wcag':     issue.get('wcag', ''),
                    })

            prev_violations     = _get_previous_scan_violations(domain)
            original_violations = _get_original_violations(domain)
            delta               = _compare_scans(prev_violations, curr_violations, original_violations)
            org_name            = _get_org_name(domain)

            is_month_end     = ((scan_count + 1) % 4 == 0)
            scan_num_in_month = (scan_count % 4) + 1

            if email:
                from hhs_weekly_emailer import (
                    send_hhs_weekly_summary,
                    send_hhs_monthly_report,
                    send_hhs_overdue_notice,
                    send_hhs_verification_certificate,
                )

                if is_month_end:
                    # ── Monthly report ────────────────────────────────────────
                    month_label = datetime.now(timezone.utc).strftime('%B %Y')
                    scans       = _get_monthly_scan_history(domain)
                    overdue     = [v for v in delta['orig_still_open']
                                   if v.get('severity', '').lower() == 'critical']

                    send_hhs_monthly_report(
                        email              = email,
                        domain             = domain,
                        org_name           = org_name,
                        registry_id        = registry_id,
                        month_label        = month_label,
                        scans              = scans,
                        score_start        = scans[0]['score'] if scans else prev_score,
                        score_end          = result.overall_score,
                        total_closed       = len(delta['orig_closed']),
                        total_open         = len(delta['orig_still_open']),
                        overdue_violations = overdue,
                    )
                    log_evidence(domain, receipt['receipt_id'], 'HHS_MONTHLY_REPORT',
                                 f'Monthly report sent for {month_label}')
                    print(f"[HHS_CRON] Monthly report sent to {email} for {domain}")

                    # Fire overdue notice for critical violations still open
                    if overdue:
                        send_hhs_overdue_notice(
                            email              = email,
                            domain             = domain,
                            org_name           = org_name,
                            registry_id        = registry_id,
                            overdue_violations = overdue,
                            days_since_audit   = 30 * ((scan_count + 1) // 4),
                        )
                        log_evidence(domain, receipt['receipt_id'], 'HHS_OVERDUE_NOTICE',
                                     f'{len(overdue)} critical violations overdue — notice sent')
                        print(f"[HHS_CRON] Overdue notice sent to {email} for {domain}")

                else:
                    # ── Weekly summary ────────────────────────────────────────
                    send_hhs_weekly_summary(
                        email             = email,
                        domain            = domain,
                        org_name          = org_name,
                        registry_id       = registry_id,
                        scan_num          = scan_num_in_month,
                        score_now         = result.overall_score,
                        score_prev        = prev_score,
                        violations_closed = delta['closed'],
                        violations_open   = delta['still_open'],
                        violations_new    = delta['new_found'],
                    )
                    log_evidence(domain, receipt['receipt_id'], 'HHS_WEEKLY_SUMMARY',
                                 f'Week {scan_num_in_month} summary sent to {email}. '
                                 f'Score: {result.overall_score}/100')
                    print(f"[HHS_CRON] Weekly summary sent to {email} for {domain} "
                          f"(Week {scan_num_in_month}, score: {result.overall_score})")

            # ── Check Verification Certificate ────────────────────────────────
            if (email and original_violations and
                    _check_verification_ready(domain, curr_violations, original_violations)):

                print(f"[HHS_CRON] All original criticals closed for {domain} — generating certificate")

                # Get original score and date
                orig_score = 0
                orig_date  = ''
                try:
                    conn = get_conn()
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                SELECT overall_score, timestamp_utc FROM receipts
                                WHERE domain = %s ORDER BY timestamp_utc ASC LIMIT 1
                            """, (domain,))
                            row = cur.fetchone()
                        conn.close()
                        if row:
                            orig_score = row[0] or 0
                            orig_date  = row[1].strftime('%Y-%m-%d') if row[1] else ''
                except Exception:
                    pass

                # Build closed list with dates
                cert_date_str = datetime.now(timezone.utc).strftime('%B %d, %Y')
                closed_with_dates = [
                    {**v, 'closed_date': cert_date_str}
                    for v in delta['orig_closed']
                ]

                from receipt.hhs_certificate import generate_verification_certificate
                cert_pdf = generate_verification_certificate(
                    domain                = domain,
                    org_name              = org_name,
                    registry_id           = registry_id,
                    receipt_id            = receipt['receipt_id'],
                    original_audit_date   = orig_date,
                    verification_date     = datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                    original_score        = orig_score,
                    verified_score        = result.overall_score,
                    violations_closed     = closed_with_dates,
                    violations_still_open = delta['orig_still_open'],
                )

                from hhs_weekly_emailer import send_hhs_verification_certificate
                send_hhs_verification_certificate(
                    email                 = email,
                    domain                = domain,
                    org_name              = org_name,
                    registry_id           = registry_id,
                    original_score        = orig_score,
                    verified_score        = result.overall_score,
                    violations_closed     = closed_with_dates,
                    audit_date            = orig_date,
                    certificate_pdf_bytes = cert_pdf,
                )

                # Update registry to remediation_verified
                try:
                    conn = get_conn()
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE registry SET
                                    status = 'remediation_verified',
                                    updated_at = NOW()
                                WHERE domain = %s
                            """, (domain,))
                        conn.close()
                except Exception as e:
                    print(f"[HHS_CRON] Registry update error for {domain}: {e}")

                log_evidence(
                    domain, receipt['receipt_id'],
                    'VERIFICATION_CERTIFICATE_ISSUED',
                    f'All original critical violations confirmed closed. '
                    f'Certificate issued to {email}.'
                )
                print(f"[HHS_CRON] Verification Certificate issued to {email} for {domain}")

            time.sleep(5)  # polite gap between scans

        except Exception as e:
            import traceback
            print(f"[HHS_CRON] Exception for {domain}: {traceback.format_exc()}")
            continue

    print(f"[HHS_CRON] HHS monitoring cycle complete — {len(domains)} domain(s) processed")


# ── Scheduler startup ─────────────────────────────────────────────────────────

def start_cron_scheduler():
    if not CRON_ENABLED:
        print("[CRON] Disabled via CRON_ENABLED=false")
        return

    def _loop():
        time.sleep(60)
        while True:
            try:
                process_email_queue()
            except Exception as e:
                print(f"[QUEUE] Cycle error: {e}")
            try:
                run_rescan_cycle()
            except Exception as e:
                print(f"[CRON] Cycle error: {e}")
            try:
                run_hhs_monitoring_cycle()
            except Exception as e:
                print(f"[HHS_CRON] HHS cycle error: {e}")
            time.sleep(3600)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    print(f"[CRON] Scheduler started — rescan interval: {RESCAN_INTERVAL_DAYS} days")
