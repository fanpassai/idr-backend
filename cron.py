"""
IDR Cron Scheduler — v2
Two jobs run on background threads:

1. Weekly rescan engine (every hour check, rescan if due)
2. Email queue processor (every hour, fires due sequence emails)
"""

import os
import threading
import time
import json
from datetime import datetime, timezone, timedelta


RESCAN_INTERVAL_DAYS = int(os.environ.get('RESCAN_INTERVAL_DAYS', '7'))
CRON_ENABLED = os.environ.get('CRON_ENABLED', 'true').lower() == 'true'


# ── Sequence definitions ──────────────────────────────────────────────────────
# Each entry: (step_number, delay_hours)
# Delay is from the moment the sequence is queued (scan or purchase time)

FREE_SCANNER_STEPS = [
    # A2 — 23 hours: next morning, before inbox gets crowded
    (2, 23),
    # A3 — 72 hours (3 days): consequence / story email
    (3, 72),
    # A4 — 120 hours (5 days): social proof / what protection looks like
    (4, 120),
    # A5 — 168 hours (7 days): direct close / scarcity
    (5, 168),
    # A6 — 336 hours (14 days): loss aversion / final email
    (6, 336),
]

FOUNDER_STEPS = [
    # B3 — 48 hours (2 days): badge installation guide
    (3, 48),
    # B4 — 168 hours (7 days): store is being monitored
    (4, 168),
    # B5 — 336 hours (14 days): first rescan coming up
    (5, 336),
    # B6 — 720 hours (30 days): 30-day compliance summary
    (6, 720),
]

WIN_BACK_STEPS = [
    # D1 — 1 hour after cancellation: immediate consequences
    (1, 1),
    # D2 — 168 hours (7 days): registry status changed
    (2, 168),
]


# Nudge steps after weekly rescan finds issues
# These fire if no fix-report submitted within 48h of rescan
RESCAN_NUDGE_STEPS = [
    (1, 48),   # 48 hours — gentle nudge
    (2, 96),   # 96 hours — developer path emphasis
    (3, 144),  # 144 hours — escalation, cite legal risk
]


# ── Email dispatcher ──────────────────────────────────────────────────────────

def dispatch_email(row: dict) -> bool:
    """
    Fire the correct email function for a queued row.
    Returns True if sent successfully.
    """
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

        elif sequence == 'rescan_nudge':
            from emailer import send_fix_nudge
            hours_map = { 1: 48, 2: 96, 3: 144 }
            hours = hours_map.get(step, 48)
            return send_fix_nudge(email, domain, hours,
                                  receipt_id=row.get('receipt_json', {}) and
                                  json.loads(row['receipt_json']).get('receipt_id','') if row.get('receipt_json') else '')

        print(f"[QUEUE] No handler for {sequence} step {step}")
        return False

    except ImportError as e:
        # Email function not yet written — skip gracefully, don't mark sent
        print(f"[QUEUE] Email function not yet implemented: {e} — skipping")
        return False
    except Exception as e:
        print(f"[QUEUE] Dispatch error for {sequence} step {step}: {e}")
        return False


# ── Email queue processor ─────────────────────────────────────────────────────

def process_email_queue():
    """
    Check email_queue for due emails and fire them.
    Marks each as sent after successful dispatch.
    Skips gracefully if email function not yet written.
    """
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
            # If function not implemented yet, cancel this step so we
            # don't retry it every hour forever
            mark_email_sent(row['id'])
            skipped += 1

    print(f"[QUEUE] Cycle complete — {sent} sent, {skipped} skipped")


# ── Weekly rescan engine ──────────────────────────────────────────────────────

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
                # Queue 48h nudge sequence
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


# ── Scheduler startup ─────────────────────────────────────────────────────────

def start_cron_scheduler():
    if not CRON_ENABLED:
        print("[CRON] Disabled via CRON_ENABLED=false")
        return

    def _loop():
        # Wait 60s after startup before first run
        time.sleep(60)
        while True:
            try:
                # 1. Process email queue
                process_email_queue()
            except Exception as e:
                print(f"[QUEUE] Cycle error: {e}")
            try:
                # 2. Run weekly rescans
                run_rescan_cycle()
            except Exception as e:
                print(f"[CRON] Cycle error: {e}")
            # Check every hour
            time.sleep(3600)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    print(f"[CRON] Scheduler started — rescan interval: {RESCAN_INTERVAL_DAYS} days")
