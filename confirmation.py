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


# ── Slug mapping ──────────────────────────────────────────────────────────────
#
# The merchant-facing API uses friendly slugs (VALID_CATEGORIES in app.py).
# The receipt generator creates slugs from the scanner's display names via:
#     name.lower().replace(" ", "_").replace("&", "and")
#
# Scanner category names → generated slugs:
#   "Image Alt Text"     → "image_alt_text"
#   "Form Labels"        → "form_labels"
#   "Keyboard Navigation"→ "keyboard_navigation"
#   "Heading Structure"  → "heading_structure"
#   "ARIA & Links"       → "aria_and_links"
#
# This table maps the merchant-facing API slugs to the receipt slugs.
# Add new rows here whenever the scanner grows a new category.

API_SLUG_TO_RECEIPT_SLUG = {
    "alt_text":          "image_alt_text",
    "form_labels":       "form_labels",
    "keyboard_nav":      "keyboard_navigation",
    "heading_structure": "heading_structure",
    "contrast":          None,   # not yet in scanner — always returns 0
    "aria_links":        "aria_and_links",
}


def _build_category_counts(receipt: dict) -> dict:
    """
    Build a lookup of {receipt_slug: issue_count} from a scan receipt.

    The receipt stores categories as a LIST of objects:
        [{"name": "Image Alt Text", "slug": "image_alt_text", "failed": 3, ...}, ...]

    The issue count field is "failed" (number of failing checks in that category).
    """
    counts = {}
    categories = receipt.get("scan", {}).get("categories", [])

    # categories is always a list — never a dict
    for cat in categories:
        slug  = cat.get("slug", "")
        count = int(cat.get("failed", cat.get("issues_count", cat.get("count", 0))))
        if slug:
            counts[slug] = count

    return counts


def _get_count_for_api_slug(api_slug: str, receipt_counts: dict) -> int:
    """
    Translate an API-facing category slug to a receipt slug,
    then return the issue count. Returns 0 if no mapping or not found.
    """
    receipt_slug = API_SLUG_TO_RECEIPT_SLUG.get(api_slug)
    if receipt_slug is None:
        return 0  # category not in scanner (e.g. "contrast")
    return receipt_counts.get(receipt_slug, 0)


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
        "domain":         clean,
        "new_receipt_id": None,
        "new_score":      None,
        "confirmed":      [],
        "partial":        [],
        "failed":         [],
        "no_pending":     False,
        "error":          None,
        "triggered_by":   triggered_by,
        "timestamp_utc":  datetime.now(timezone.utc).isoformat(),
    }

    # ── 1. Fetch pending fix requests ─────────────────────────────────────────
    pending = get_fix_requests_by_domain(clean, status="pending")
    if not pending:
        result["no_pending"] = True
        return result

    original_receipt_id = pending[0].get("receipt_id")
    original_counts = {
        req["issue_category"]: req.get("issue_count", 0)
        for req in pending
    }

    # ── 2. Run fresh scan ─────────────────────────────────────────────────────
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
    new_receipt["triggered_by"]     = triggered_by

    # Save to DB
    save_receipt(new_receipt)
    upsert_registry(clean, new_receipt)

    new_receipt_id = new_receipt["receipt_id"]
    new_score      = new_receipt.get("scan", {}).get("overall_score", 0)
    result["new_receipt_id"] = new_receipt_id
    result["new_score"]      = new_score

    log_evidence(clean, new_receipt_id, "CONFIRMATION_SCAN_STARTED",
                 f"Triggered by: {triggered_by} | "
                 f"Checking {len(pending)} fix request(s)")

    # ── 3. Diff new results vs. reported fixes ────────────────────────────────
    # Build {receipt_slug: count} lookup from new receipt — categories is a LIST
    new_receipt_counts = _build_category_counts(new_receipt)

    for req in pending:
        req_id       = req["id"]
        api_slug     = req["issue_category"]
        original_cnt = req.get("issue_count", 0)
        new_cnt      = _get_count_for_api_slug(api_slug, new_receipt_counts)

        entry = {
            "id":             req_id,
            "category":       api_slug,
            "original_count": original_cnt,
            "new_count":      new_cnt,
        }

        if new_cnt == 0:
            status = "confirmed"
            detail = (f"FIXED — {api_slug}: was {original_cnt} issues, "
                      f"now 0 after confirmation scan {new_receipt_id}")
            result["confirmed"].append(entry)

        elif new_cnt < original_cnt:
            status = "partial"
            detail = (f"PARTIAL — {api_slug}: reduced from {original_cnt} "
                      f"to {new_cnt} (confirmation scan {new_receipt_id})")
            result["partial"].append(entry)

        else:
            status = "failed"
            detail = (f"NOT RESOLVED — {api_slug}: still {new_cnt} issues "
                      f"(was {original_cnt}, confirmation scan {new_receipt_id})")
            result["failed"].append(entry)

        update_fix_request(req_id, status, new_receipt_id)
        log_evidence(clean, new_receipt_id,
                     f"FIX_{status.upper()}",
                     detail)

    # ── 4. Final summary evidence entry ───────────────────────────────────────
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
