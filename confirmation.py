"""
IDR Confirmation Scan Loop — Phase 2C
When a merchant marks issues as fixed, this module:
  1. Reruns the scanner against their domain
  2. Diffs new results against the original reported fixes
  3. Updates fix_request statuses (confirmed / partial / failed)
  4. Logs every outcome to the evidence log
  5. Updates the registry score if things improved
"""

from datetime import datetime, timezone
from scanner.engine import scan_url
from receipt.generator import generate_receipt
from database import (
    get_fix_requests_by_domain,
    update_fix_request,
    save_receipt,
    upsert_registry,
    log_evidence,
    get_registry
)


# Maps the issue category slugs (used in fix_requests) to the
# axe-core rule IDs / scan result keys used in scanner output.
CATEGORY_MAP = {
    "alt_text":         "alt_text",
    "form_labels":      "form_labels",
    "keyboard_nav":     "keyboard_nav",
    "heading_structure":"heading_structure",
    "contrast":         "contrast",
    "aria_links":       "aria_links",
}


def _count_issues_by_category(scan_result: dict) -> dict:
    """
    Pull per-category issue counts out of a scan receipt.
    Returns {category_slug: issue_count}
    """
    categories = scan_result.get("scan", {}).get("categories", {})
    counts = {}
    for slug, mapped_key in CATEGORY_MAP.items():
        cat = categories.get(mapped_key, categories.get(slug, {}))
        counts[slug] = int(cat.get("issues_count", cat.get("count", 0)))
    return counts


def run_confirmation_scan(domain: str, triggered_by: str = "system") -> dict:
    """
    Core confirmation loop entry point.

    Args:
        domain:       The merchant domain to rescan (e.g. 'shop.example.com')
        triggered_by: Who triggered this — 'merchant', 'cron', or 'system'

    Returns a summary dict:
    {
        "domain":            str,
        "new_receipt_id":    str,
        "new_score":         int,
        "confirmed":         [{"id", "category", "original_count", "new_count"}],
        "partial":           [...],
        "failed":            [...],
        "no_pending":        bool,
        "error":             str | None
    }
    """
    clean = domain.replace("www.", "")
    result = {
        "domain": clean,
        "new_receipt_id": None,
        "new_score": None,
        "confirmed": [],
        "partial": [],
        "failed": [],
        "no_pending": False,
        "error": None,
        "triggered_by": triggered_by,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    # ── 1. Fetch pending fix requests ─────────────────────────────────────────
    pending = get_fix_requests_by_domain(clean, status="pending")
    if not pending:
        result["no_pending"] = True
        return result

    # ── 2. Pull the original scan to get baseline counts ──────────────────────
    # We grab the counts from the first pending fix_request's receipt
    original_receipt_id = pending[0].get("receipt_id")
    original_counts = {}
    for req in pending:
        original_counts[req["issue_category"]] = req.get("issue_count", 0)

    # ── 3. Run fresh scan ─────────────────────────────────────────────────────
    url = f"https://{clean}"
    scan_result = scan_url(url)
    if scan_result.error:
        result["error"] = f"Rescan failed: {scan_result.error}"
        log_evidence(clean, original_receipt_id or "N/A",
                     "CONFIRMATION_SCAN_ERROR",
                     f"Rescan error: {scan_result.error}")
        return result

    new_receipt = generate_receipt(scan_result)
    new_receipt["confirmation_for"] = original_receipt_id
    new_receipt["triggered_by"] = triggered_by

    # Save to DB
    save_receipt(new_receipt)
    upsert_registry(clean, new_receipt)

    new_receipt_id = new_receipt["receipt_id"]
    new_score = new_receipt.get("scan", {}).get("overall_score", 0)
    result["new_receipt_id"] = new_receipt_id
    result["new_score"] = new_score

    # Log the confirmation scan itself
    log_evidence(clean, new_receipt_id, "CONFIRMATION_SCAN_STARTED",
                 f"Triggered by: {triggered_by} | Checking {len(pending)} fix request(s)")

    # ── 4. Diff new results vs. reported fixes ────────────────────────────────
    new_counts = _count_issues_by_category(new_receipt)

    for req in pending:
        req_id       = req["id"]
        category     = req["issue_category"]
        original_cnt = req.get("issue_count", 0)
        new_cnt      = new_counts.get(category, 0)

        entry = {
            "id":             req_id,
            "category":       category,
            "original_count": original_cnt,
            "new_count":      new_cnt,
        }

        if new_cnt == 0:
            # All issues in this category cleared
            status = "confirmed"
            detail = (f"FIXED — {category}: was {original_cnt} issues, "
                      f"now 0 after confirmation scan {new_receipt_id}")
            result["confirmed"].append(entry)

        elif new_cnt < original_cnt:
            # Partially fixed
            status = "partial"
            detail = (f"PARTIAL — {category}: reduced from {original_cnt} "
                      f"to {new_cnt} (confirmation scan {new_receipt_id})")
            result["partial"].append(entry)

        else:
            # No improvement detected
            status = "failed"
            detail = (f"NOT RESOLVED — {category}: still {new_cnt} issues "
                      f"(was {original_cnt}, confirmation scan {new_receipt_id})")
            result["failed"].append(entry)

        # Update the fix_request record
        update_fix_request(req_id, status, new_receipt_id)

        # Write to evidence log
        log_evidence(clean, new_receipt_id,
                     f"FIX_{status.upper()}",
                     detail)

    # ── 5. Final summary evidence entry ───────────────────────────────────────
    confirmed_n = len(result["confirmed"])
    partial_n   = len(result["partial"])
    failed_n    = len(result["failed"])
    log_evidence(clean, new_receipt_id,
                 "CONFIRMATION_SCAN_COMPLETE",
                 (f"Score: {new_score}/100 | "
                  f"Confirmed: {confirmed_n} | "
                  f"Partial: {partial_n} | "
                  f"Failed: {failed_n}"))

    return result
