"""
IDR Cron Scheduler — v4
Jobs run on background threads:

1. HHS auto-deliver (every 3 minutes) — generates PDF and emails client after reviewer submits
2. Email queue processor (every hour)
3. Weekly rescan engine (every hour check)
4. HHS monitoring cycle (every hour check)
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

HHS_UPSELL_STEPS = [
    (2, 48),
    (5, 120),
    (9, 216),
]

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
        if sequence == 'free_scanner':
            from emailer import (
                send_nurture_day1, send_nurture_day3, send_nurture_day5,
                send_nurture_day7, send_nurture_day14,
            )
            dispatch = {
                2: send_nurture_day1, 3: send_nurture_day3, 4: send_nurture_day5,
                5: send_nurture_day7, 6: send_nurture_day14,
            }
            fn = dispatch.get(step)
            if fn:
                return fn(email, domain, receipt)

        elif sequence == 'founder':
            from emailer import (
                send_founder_badge_guide, send_founder_monitoring_active,
                send_founder_rescan_incoming, send_founder_30day_summary,
            )
            dispatch = {
                3: send_founder_badge_guide, 4: send_founder_monitoring_active,
                5: send_founder_rescan_incoming, 6: send_founder_30day_summary,
            }
            fn = dispatch.get(step)
            if fn:
                return fn(email, domain, receipt)

        elif sequence == 'win_back':
            from emailer import send_winback_deactivated, send_winback_status_changed
            dispatch = {1: send_winback_deactivated, 2: send_winback_status_changed}
            fn = dispatch.get(step)
            if fn:
                return fn(email, domain)

        elif sequence == 'rescan_nudge':
            from emailer import send_fix_nudge
            hours_map = {1: 48, 2: 96, 3: 144}
            hours = hours_map.get(step, 48)
            receipt_id = json.loads(row['receipt_json']).get('receipt_id', '') if row.get('receipt_json') else ''
            return send_fix_nudge(email, domain, hours, receipt_id=receipt_id)

        elif sequence == 'hhs_upsell':
            from hhs_emailer import send_hhs_day2_monitoring, send_hhs_day5_snapshot, send_hhs_day9_final
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
        mark_email_sent(row['id'])
        if success:
            sent += 1
        else:
            skipped += 1
    print(f"[QUEUE] Cycle complete — {sent} sent, {skipped} skipped")


# ── E-commerce/ADA weekly rescan engine ──────────────────────────────────────

def get_domains_due_for_rescan(db_conn_fn) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RESCAN_INTERVAL_DAYS)
    try:
        conn = db_conn_fn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT domain, activated_by FROM registry
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
                from database import queue_sequence
                queue_sequence(email=email, domain=domain, sequence='rescan_nudge',
                               receipt=receipt, steps=RESCAN_NUDGE_STEPS)
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
    for domain, email in domains:
        rescan_domain(domain, email)
        time.sleep(3)


# ── HHS auto-deliver ──────────────────────────────────────────────────────────
# Runs every 3 minutes. Finds reviewer_submitted audits older than 3 minutes,
# generates the Good Faith Effort Record PDF, emails the client, marks delivered.

def run_hhs_auto_deliver():
    try:
        from database import get_conn
        conn = get_conn()
        if not conn:
            return
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, domain, client_email, audit_surface,
                       org_name, org_contact, org_title, org_phone, org_address,
                       scan_json, registry_id,
                       reviewer_name_submitted, reviewer_credentials_submitted,
                       reviewer_cred_number_submitted, reviewer_role_submitted,
                       reviewer_verify_url, cert_date, cert_total_pages,
                       audit_setup_browser, audit_setup_os, audit_setup_sr,
                       audit_setup_sr_version, audit_setup_primary_url,
                       reviewer_session_start, reviewer_session_end,
                       reviewer_submitted_at
                FROM hhs_audits
                WHERE status = 'reviewer_submitted'
                  AND reviewer_submitted_at <= NOW() - INTERVAL '3 minutes'
            """)
            audits = cur.fetchall()
        conn.close()

        if not audits:
            return

        print(f"[HHS_AUTO_DELIVER] {len(audits)} audit(s) ready for delivery")

        for audit in audits:
            audit_id     = audit[0]
            domain       = audit[1]
            client_email = audit[2]
            surface      = audit[3]

            try:
                # Get findings
                conn2 = get_conn()
                if not conn2:
                    continue
                with conn2.cursor() as cur2:
                    cur2.execute("""
                        SELECT f.check_slug, f.check_name, f.result, f.finding_text,
                               f.wcag_criterion, f.severity, f.screenshot_count,
                               COALESCE(f.pages_count, 0),
                               COALESCE(f.pages_visited, ''),
                               f.pdf_found, COALESCE(f.pdf_docs, ''),
                               COALESCE(
                                   json_agg(
                                       json_build_object('screenshot_id', s.id, 'filename', s.filename)
                                   ) FILTER (WHERE s.id IS NOT NULL), '[]'
                               ) AS screenshots
                        FROM hhs_reviewer_findings f
                        LEFT JOIN hhs_reviewer_screenshots s ON s.finding_id = f.id
                        WHERE f.audit_id = %s
                        GROUP BY f.id, f.check_slug, f.check_name, f.result,
                                 f.finding_text, f.wcag_criterion, f.severity,
                                 f.screenshot_count, f.pages_count, f.pages_visited,
                                 f.pdf_found, f.pdf_docs
                        ORDER BY f.id
                    """, (audit_id,))
                    findings = cur2.fetchall()
                conn2.close()

                surface_label = 'Full Patient Access' if surface == 'primary_and_transaction' else 'Primary Web Presence'

                checks = [{
                    'slug':             f[0], 'check_name':     f[1],
                    'result':           f[2], 'finding_text':   f[3] or '',
                    'wcag_criterion':   f[4] or '', 'severity': f[5] or '',
                    'screenshot_count': f[6] or 0,
                    'pages_count':      f[7], 'pages_visited':  f[8],
                    'pdf_found':        f[9], 'pdf_docs':       f[10],
                    'screenshots':      f[11] or [],
                } for f in findings]

                # Build scan object — ensure domain is set
                raw_scan = audit[9] or {}
                if isinstance(raw_scan, str):
                    import json as _j
                    raw_scan = _j.loads(raw_scan)
                raw_scan['domain'] = raw_scan.get('domain') or domain
                raw_scan['url']    = raw_scan.get('url') or f'https://{domain}'

                # Calculate session duration in minutes
                session_start = audit[23]
                session_end   = audit[24]
                session_duration = None
                if session_start and session_end:
                    diff = session_end - session_start
                    session_duration = round(diff.total_seconds() / 60, 1)

                # Build receipt_data in the exact structure the PDF generator expects
                receipt_data = {
                    # Top-level identifiers
                    'receipt_id':    '',
                    'registry_id':   audit[10] or f'IDR-HHS-{domain.upper().replace(".", "-")}',
                    'timestamp_utc': audit[25].isoformat() if audit[25] else '',
                    'hash':          'PENDING',
                    'activated_by':  client_email,
                    'audit_surface': surface,

                    # Organization block — what the PDF reads
                    'organization': {
                        'name':         audit[4] or domain,
                        'address':      audit[8] or '',
                        'contact_name': audit[5] or '',
                        'phone':        audit[7] or '',
                        'email':        client_email,
                        'title':        audit[6] or '',
                    },

                    # Automated scan data
                    'scan': raw_scan,

                    # Reviewer block — what the PDF certification section reads
                    'reviewer': {
                        'name':               audit[11] or 'Hans-Peter Nkansah',
                        'credentials':        audit[12] or '',
                        'credential_number':  audit[13] or '',
                        'role':               audit[14] or '',
                        'verify_url':         audit[15] or '',
                        'surface_label':      surface_label,
                        'session_start':      audit[23].isoformat() if audit[23] else '',
                        'session_end':        audit[24].isoformat() if audit[24] else '',
                        'session_duration_minutes': session_duration,
                        'submitted_at':       audit[25].isoformat() if audit[25] else '',
                        'cert_date':          audit[16] or '',
                        'total_pages':        audit[17] or '',
                        'setup_browser':      audit[18] or '',
                        'setup_os':           audit[19] or '',
                        'setup_sr':           audit[20] or '',
                        'setup_sr_version':   audit[21] or '',
                        'setup_primary_url':  audit[22] or '',
                        # Checker findings for the human validation section
                        'checks': checks,
                    },
                }

                # If scan_json is empty or missing pages, run the crawl first
                scan_data = receipt_data.get('scan') or {}
                if not scan_data.get('categories') or not scan_data.get('overall_score'):
                    print(f'[HHS_AUTO_DELIVER] scan_json missing for audit_id={audit_id} — running crawl')
                    try:
                        from hhs_crawler import run_hhs_crawl
                        crawl_result = run_hhs_crawl(f'https://{domain}', max_pages=15)
                        receipt_data['scan'] = crawl_result
                        # Store it for future use
                        conn_scan = get_conn()
                        if conn_scan:
                            import json as _json
                            with conn_scan.cursor() as cs:
                                cs.execute('UPDATE hhs_audits SET scan_json=%s, updated_at=NOW() WHERE id=%s',
                                           (_json.dumps(crawl_result), audit_id))
                                conn_scan.commit()
                            conn_scan.close()
                        print(f'[HHS_AUTO_DELIVER] Crawl complete for {domain} — score {crawl_result.get("overall_score",0)}/100')
                    except Exception as crawl_err:
                        print(f'[HHS_AUTO_DELIVER] Crawl failed (non-fatal): {crawl_err}')

                # Generate PDF
                from receipt.hhs_pdf_generator import generate_hhs_pdf
                pdf_bytes = generate_hhs_pdf(receipt_data)

                # Email to client with PDF attached
                from hhs_emailer import send_hhs_reviewer_delivery
                send_hhs_reviewer_delivery(
                    to_email      = client_email,
                    domain        = domain,
                    org_name      = audit[4] or domain,
                    surface_label = surface_label,
                    pdf_bytes     = pdf_bytes,
                    audit_id      = audit_id,
                    registry_id   = audit[10] or '',
                )

                # Mark delivered
                conn3 = get_conn()
                if conn3:
                    with conn3.cursor() as cur3:
                        cur3.execute("""
                            UPDATE hhs_audits SET
                                status = 'delivered', delivered_at = NOW(), updated_at = NOW()
                            WHERE id = %s
                        """, (audit_id,))
                        conn3.commit()
                    conn3.close()

                print(f"[HHS_AUTO_DELIVER] audit_id={audit_id} domain={domain} delivered to {client_email}")

            except Exception as inner_e:
                import traceback as _tb
                print(f"[HHS_AUTO_DELIVER] Error on audit_id={audit_id}: {inner_e}")
                print(_tb.format_exc())

    except Exception as e:
        import traceback as _tb
        print(f"[HHS_AUTO_DELIVER] Outer error: {e}")
        print(_tb.format_exc())


# ── HHS monitoring cycle ──────────────────────────────────────────────────────

def _get_hhs_monitoring_domains() -> list:
    from database import get_conn
    try:
        conn = get_conn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT domain, activated_by, registry_id,
                       last_scanned, scan_count, latest_score
                FROM registry
                WHERE hhs_enrolled = TRUE AND status = 'active'
                  AND (last_scanned IS NULL OR last_scanned < NOW() - INTERVAL '6 days')
                ORDER BY last_scanned ASC NULLS FIRST
                LIMIT 100
            """)
            rows = cur.fetchall()
        conn.close()
        return [{'domain': r[0], 'email': r[1], 'registry_id': r[2],
                 'last_scanned': r[3], 'scan_count': r[4] or 0, 'prev_score': r[5]}
                for r in rows]
    except Exception as e:
        print(f"[HHS_CRON] Error fetching HHS domains: {e}")
        return []


def _get_original_violations(domain: str) -> list:
    from database import get_conn
    try:
        conn = get_conn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT receipt_json FROM receipts
                WHERE domain = %s ORDER BY timestamp_utc ASC LIMIT 1
            """, (domain,))
            row = cur.fetchone()
        conn.close()
        if not row:
            return []
        receipt = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        violations = []
        for cat in receipt.get('scan', {}).get('categories', []):
            for issue in cat.get('issues', []):
                violations.append({'rule': issue.get('rule', ''), 'category': cat.get('name', ''),
                                   'severity': issue.get('severity', ''), 'wcag': issue.get('wcag', ''),
                                   'count': issue.get('count', 0)})
        return violations
    except Exception as e:
        print(f"[HHS_CRON] Error fetching original violations for {domain}: {e}")
        return []


def _get_previous_scan_violations(domain: str) -> list:
    from database import get_conn
    try:
        conn = get_conn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT receipt_json FROM receipts
                WHERE domain = %s ORDER BY timestamp_utc DESC LIMIT 1
            """, (domain,))
            row = cur.fetchone()
        conn.close()
        if not row:
            return []
        receipt = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        violations = []
        for cat in receipt.get('scan', {}).get('categories', []):
            for issue in cat.get('issues', []):
                violations.append({'rule': issue.get('rule', ''), 'category': cat.get('name', ''),
                                   'severity': issue.get('severity', ''), 'wcag': issue.get('wcag', '')})
        return violations
    except Exception as e:
        print(f"[HHS_CRON] Error fetching previous scan for {domain}: {e}")
        return []


def _compare_scans(prev_violations, curr_violations, original_violations):
    prev_rules = {v['rule'] for v in prev_violations}
    curr_rules = {v['rule'] for v in curr_violations}
    orig_rules = {v['rule'] for v in original_violations}
    closed_rules = prev_rules - curr_rules
    new_rules    = curr_rules - prev_rules
    orig_closed  = orig_rules - curr_rules
    def _find(rules, source):
        return [v for v in source if v['rule'] in rules]
    return {
        'closed':          _find(closed_rules, prev_violations),
        'new_found':       _find(new_rules, curr_violations),
        'still_open':      list(curr_violations),
        'orig_closed':     [v for v in original_violations if v['rule'] in orig_closed],
        'orig_still_open': [v for v in original_violations if v['rule'] not in orig_closed],
    }


def _check_verification_ready(domain, curr_violations, original_violations):
    orig_crits = {v['rule'] for v in original_violations if v.get('severity', '').lower() == 'critical'}
    if not orig_crits:
        return False
    curr_rules = {v['rule'] for v in curr_violations}
    return not (orig_crits & curr_rules)


def _get_org_name(domain):
    from database import get_conn
    try:
        conn = get_conn()
        if not conn:
            return domain
        with conn.cursor() as cur:
            cur.execute("SELECT receipt_json FROM receipts WHERE domain = %s ORDER BY timestamp_utc ASC LIMIT 1", (domain,))
            row = cur.fetchone()
        conn.close()
        if not row:
            return domain
        receipt = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return receipt.get('organization', {}).get('name', domain)
    except Exception:
        return domain


def _get_monthly_scan_history(domain):
    from database import get_conn
    try:
        conn = get_conn()
        if not conn:
            return []
        with conn.cursor() as cur:
            cur.execute("SELECT overall_score, timestamp_utc FROM receipts WHERE domain = %s ORDER BY timestamp_utc DESC LIMIT 4", (domain,))
            rows = cur.fetchall()
        conn.close()
        return [{'week': i+1, 'date': r[1].strftime('%b %d') if r[1] else '—',
                 'score': r[0] or 0, 'closed': 0, 'new_found': 0}
                for i, r in enumerate(reversed(rows))]
    except Exception as e:
        print(f"[HHS_CRON] Error fetching scan history: {e}")
        return []


def run_hhs_monitoring_cycle():
    from database import save_receipt, upsert_registry, log_evidence, get_conn
    from scanner.engine import scan_url
    from receipt.generator import generate_receipt

    print(f"[HHS_CRON] HHS monitoring cycle at {datetime.now(timezone.utc).isoformat()}")
    domains = _get_hhs_monitoring_domains()
    if not domains:
        print("[HHS_CRON] No HHS monitoring domains due for scan")
        return

    for d in domains:
        domain      = d['domain']
        email       = d['email']
        registry_id = d['registry_id'] or f'IDR-HHS-{domain.upper().replace(".", "-")}'
        prev_score  = d['prev_score'] or 0
        scan_count  = d['scan_count']

        try:
            result = scan_url(f'https://{domain}')
            if result.error:
                print(f"[HHS_CRON] Scan failed for {domain}: {result.error}")
                continue

            receipt = generate_receipt(result)
            receipt['activated_by'] = email
            save_receipt(receipt, email)
            upsert_registry(domain, receipt, email)
            log_evidence(domain, receipt['receipt_id'], 'HHS_WEEKLY_SCAN',
                         f'HHS monitoring scan #{scan_count+1}. Score: {result.overall_score}/100.')

            curr_violations = []
            for cat in receipt.get('scan', {}).get('categories', []):
                for issue in cat.get('issues', []):
                    curr_violations.append({'rule': issue.get('rule',''), 'category': cat.get('name',''),
                                            'severity': issue.get('severity',''), 'wcag': issue.get('wcag','')})

            prev_violations     = _get_previous_scan_violations(domain)
            original_violations = _get_original_violations(domain)
            delta               = _compare_scans(prev_violations, curr_violations, original_violations)
            org_name            = _get_org_name(domain)
            is_month_end        = ((scan_count + 1) % 4 == 0)
            scan_num_in_month   = (scan_count % 4) + 1

            if email:
                from hhs_weekly_emailer import (
                    send_hhs_weekly_summary, send_hhs_monthly_report,
                    send_hhs_overdue_notice, send_hhs_verification_certificate,
                )
                if is_month_end:
                    month_label = datetime.now(timezone.utc).strftime('%B %Y')
                    scans = _get_monthly_scan_history(domain)
                    overdue = [v for v in delta['orig_still_open'] if v.get('severity','').lower() == 'critical']
                    send_hhs_monthly_report(email=email, domain=domain, org_name=org_name,
                                            registry_id=registry_id, month_label=month_label, scans=scans,
                                            score_start=scans[0]['score'] if scans else prev_score,
                                            score_end=result.overall_score,
                                            total_closed=len(delta['orig_closed']),
                                            total_open=len(delta['orig_still_open']),
                                            overdue_violations=overdue)
                    if overdue:
                        send_hhs_overdue_notice(email=email, domain=domain, org_name=org_name,
                                                registry_id=registry_id, overdue_violations=overdue,
                                                days_since_audit=30*((scan_count+1)//4))
                else:
                    send_hhs_weekly_summary(email=email, domain=domain, org_name=org_name,
                                            registry_id=registry_id, scan_num=scan_num_in_month,
                                            score_now=result.overall_score, score_prev=prev_score,
                                            violations_closed=delta['closed'],
                                            violations_open=delta['still_open'],
                                            violations_new=delta['new_found'])

            if (email and original_violations and
                    _check_verification_ready(domain, curr_violations, original_violations)):
                orig_score, orig_date = 0, ''
                try:
                    conn = get_conn()
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT overall_score, timestamp_utc FROM receipts WHERE domain=%s ORDER BY timestamp_utc ASC LIMIT 1", (domain,))
                            row = cur.fetchone()
                        conn.close()
                        if row:
                            orig_score = row[0] or 0
                            orig_date  = row[1].strftime('%Y-%m-%d') if row[1] else ''
                except Exception:
                    pass

                cert_date_str = datetime.now(timezone.utc).strftime('%B %d, %Y')
                closed_with_dates = [{**v, 'closed_date': cert_date_str} for v in delta['orig_closed']]

                from receipt.hhs_certificate import generate_verification_certificate
                cert_pdf = generate_verification_certificate(
                    domain=domain, org_name=org_name, registry_id=registry_id,
                    receipt_id=receipt['receipt_id'], original_audit_date=orig_date,
                    verification_date=datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                    original_score=orig_score, verified_score=result.overall_score,
                    violations_closed=closed_with_dates, violations_still_open=delta['orig_still_open'])

                from hhs_weekly_emailer import send_hhs_verification_certificate
                send_hhs_verification_certificate(email=email, domain=domain, org_name=org_name,
                                                  registry_id=registry_id, original_score=orig_score,
                                                  verified_score=result.overall_score,
                                                  violations_closed=closed_with_dates, audit_date=orig_date,
                                                  certificate_pdf_bytes=cert_pdf)
                try:
                    conn = get_conn()
                    if conn:
                        with conn.cursor() as cur:
                            cur.execute("UPDATE registry SET status='remediation_verified', updated_at=NOW() WHERE domain=%s", (domain,))
                        conn.close()
                except Exception as e:
                    print(f"[HHS_CRON] Registry update error: {e}")

            time.sleep(5)

        except Exception as e:
            import traceback
            print(f"[HHS_CRON] Exception for {domain}: {traceback.format_exc()}")
            continue

    print(f"[HHS_CRON] HHS monitoring cycle complete — {len(domains)} processed")


# ── Scheduler startup ─────────────────────────────────────────────────────────

def start_cron_scheduler():
    if not CRON_ENABLED:
        print("[CRON] Disabled via CRON_ENABLED=false")
        return

    def _loop():
        time.sleep(60)
        tick = 0
        while True:
            # Every 3 minutes — auto-deliver submitted HHS audits
            try:
                run_hhs_auto_deliver()
            except Exception as e:
                import traceback as _tb
                print(f"[HHS_AUTO_DELIVER] Loop error: {e}\n{_tb.format_exc()}")

            # Every hour (every 20 ticks × 3 min = 60 min)
            if tick % 20 == 0:
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

            tick += 1
            time.sleep(180)  # 3 minutes

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    print(f"[CRON] Scheduler started — rescan interval: {RESCAN_INTERVAL_DAYS} days")
