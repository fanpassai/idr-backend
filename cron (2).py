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
# Step numbers match email names for clarity.

HHS_UPSELL_STEPS = [
    (2, 48),    # Day 2  — monitoring comparison (what your record can/cannot do)
    (5, 120),   # Day 5  — record snapshot (monitoring status visible to auditors)
    (9, 216),   # Day 9  — final window before silence
]


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
            # Pull registry_id from receipt if available
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
            time.sleep(3600)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    print(f"[CRON] Scheduler started — rescan interval: {RESCAN_INTERVAL_DAYS} days")
