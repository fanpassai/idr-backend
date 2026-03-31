"""
IDR Cron Scheduler — Weekly rescan engine
Rescans all active registry domains every 7 days.
Runs as a background thread on startup.
Sends alert email if new critical issues are detected.
"""

import os
import threading
import time
from datetime import datetime, timezone, timedelta


RESCAN_INTERVAL_DAYS = int(os.environ.get('RESCAN_INTERVAL_DAYS', '7'))
CRON_ENABLED = os.environ.get('CRON_ENABLED', 'true').lower() == 'true'


def get_domains_due_for_rescan(db_conn_fn) -> list:
    """
    Query registry for domains whose last_scanned is older than RESCAN_INTERVAL_DAYS.
    Returns list of (domain, activated_by_email) tuples.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=RESCAN_INTERVAL_DAYS)
    try:
        conn = db_conn_fn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT domain, activated_by
                FROM registry
                WHERE last_scanned < %s
                   OR last_scanned IS NULL
                ORDER BY last_scanned ASC NULLS FIRST
                LIMIT 50
            """, (cutoff,))
            rows = cur.fetchall()
        conn.close()
        return [(row['domain'], row.get('activated_by')) for row in rows]
    except Exception as e:
        print(f"[CRON] Error fetching domains: {e}")
        return []


def rescan_domain(domain: str, email: str = None):
    """
    Run a fresh scan on a domain, save receipt, send alert if issues changed.
    """
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

        # Save to DB
        from database import save_receipt, upsert_registry, log_evidence, get_conn
        save_receipt(receipt, email)
        upsert_registry(domain, receipt, email)
        log_evidence(domain, receipt['receipt_id'], 'WEEKLY_RESCAN',
                     f"Automated weekly rescan. Score: {result.overall_score}/100")

        # Send alert email if there are critical issues and we have an email
        if email and result.critical_count > 0:
            scan_data = receipt.get('scan', {})
            new_issues = []
            for cat in scan_data.get('categories', []):
                for issue in cat.get('issues', []):
                    if issue.get('severity') in ('critical', 'serious'):
                        new_issues.append(issue)

            if new_issues:
                send_weekly_scan_alert(
                    email, domain, new_issues, receipt['receipt_id']
                )
                print(f"[CRON] Alert sent to {email} for {domain} — {len(new_issues)} issues")

        print(f"[CRON] Rescan complete: {domain} → {result.overall_score}/100")
        return True

    except Exception as e:
        print(f"[CRON] Exception rescanning {domain}: {e}")
        return False


def run_cron_cycle():
    """
    Single cron cycle — fetch due domains and rescan each one.
    """
    from database import get_conn
    print(f"[CRON] Starting rescan cycle at {datetime.now(timezone.utc).isoformat()}")

    domains = get_domains_due_for_rescan(get_conn)
    if not domains:
        print("[CRON] No domains due for rescan")
        return

    print(f"[CRON] {len(domains)} domain(s) due for rescan")
    success, failed = 0, 0
    for domain, email in domains:
        ok = rescan_domain(domain, email)
        if ok:
            success += 1
        else:
            failed += 1
        time.sleep(3)  # Respectful delay between scans

    print(f"[CRON] Cycle complete — {success} succeeded, {failed} failed")


def start_cron_scheduler():
    """
    Start the background cron thread.
    Checks every hour whether any domains are due.
    """
    if not CRON_ENABLED:
        print("[CRON] Disabled via CRON_ENABLED=false")
        return

    def _loop():
        # Wait 60 seconds after startup before first check
        time.sleep(60)
        while True:
            try:
                run_cron_cycle()
            except Exception as e:
                print(f"[CRON] Cycle error: {e}")
            # Check every hour — actual rescan only triggers if domain is due
            time.sleep(3600)

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    print(f"[CRON] Scheduler started — checking every hour, rescan interval: {RESCAN_INTERVAL_DAYS} days")
