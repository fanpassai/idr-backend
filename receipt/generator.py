"""
IDR Receipt Generator
Produces immutable, SHA-256 hashed Scan Receipts from ScanResult objects.
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from dataclasses import asdict
from typing import Optional


def _result_to_dict(result) -> dict:
    """Convert ScanResult to a clean serializable dict."""
    cats = []
    for c in result.categories:
        slug = c.name.lower().replace(" ", "_").replace("&", "and")
        failed = len(c.issues)
        cats.append({
            "name": c.name,
            "slug": slug,
            "score": c.score,
            "status": c.status,
            "passed": 0,
            "failed": failed,
            "issues": [
                {
                    "category": i.category,
                    "severity": i.severity,
                    "rule": i.rule,
                    "description": i.description,
                    "element": i.element,
                    "impact": i.impact,
                    "wcag": i.wcag,
                    "count": i.count
                }
                for i in c.issues
            ]
        })
    return {
        "url": result.url,
        "domain": result.domain,
        "page_title": result.title,
        "scan_duration_ms": result.scan_duration_ms,
        "overall_score": result.overall_score,
        "overall_status": result.overall_status,
        "total_issues": result.total_issues,
        "critical_count": result.critical_count,
        "categories": cats,
        "error": result.error
    }


def generate_receipt(result, operator: str = "IDR_SCANNER_v1") -> dict:
    """
    Build a signed, immutable Scan Receipt from a ScanResult.

    The receipt hash is computed over a canonical JSON payload so that
    any tampering — even a single character — produces a different hash.
    """
    receipt_id = str(uuid.uuid4()).upper()
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    registry_id = f"IDR-REG-2026-{receipt_id[:8]}"

    scan_data = _result_to_dict(result)

    # Canonical payload for hashing (sorted keys, no whitespace variation)
    canonical = {
        "receipt_id": receipt_id,
        "registry_id": registry_id,
        "timestamp_utc": timestamp_utc,
        "operator": operator,
        "scan": scan_data
    }

    canonical_str = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
    sha256_hash = hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()

    receipt = {
        **canonical,
        "hash": {
            "algorithm": "SHA-256",
            "value": sha256_hash,
            "input_bytes": len(canonical_str.encode('utf-8'))
        },
        "registry_url": f"https://idrshield.com/verify/{result.domain.replace('www.', '').replace('/', '-')}",
        "idr_protocol": "IDR-BRAND-2026-01",
        "verified_by": "Institute of Digital Remediation"
    }

    return receipt


def verify_receipt(receipt: dict) -> dict:
    """
    Verify the integrity of a receipt by re-computing its hash.
    Returns {'valid': bool, 'reason': str}
    """
    try:
        # Reconstruct ONLY the original canonical fields that were hashed at generation time
        canonical_keys = ('receipt_id', 'registry_id', 'timestamp_utc', 'operator', 'scan')
        canonical = {k: receipt[k] for k in canonical_keys if k in receipt}
        canonical_str = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
        expected_hash = hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()
        stored_hash = receipt.get('hash', {}).get('value', '')

        if expected_hash == stored_hash:
            return {"valid": True, "reason": "Receipt integrity verified. Hash matches canonical payload."}
        else:
            return {
                "valid": False,
                "reason": f"Hash mismatch. Receipt may have been altered. Expected {expected_hash[:16]}... got {stored_hash[:16]}..."
            }
    except Exception as e:
        return {"valid": False, "reason": f"Verification error: {str(e)}"}


def format_receipt_summary(receipt: dict) -> str:
    """
    Human-readable one-page receipt summary for console/email output.
    """
    scan = receipt.get('scan', {})
    lines = [
        "═" * 64,
        "  INSTITUTE OF DIGITAL REMEDIATION",
        "  SCAN RECEIPT — OFFICIAL RECORD",
        "═" * 64,
        f"  Receipt ID   : {receipt.get('receipt_id', 'N/A')}",
        f"  Registry ID  : {receipt.get('registry_id', 'N/A')}",
        f"  Timestamp    : {receipt.get('timestamp_utc', 'N/A')}",
        f"  Domain       : {scan.get('domain', 'N/A')}",
        f"  URL          : {scan.get('url', 'N/A')}",
        f"  Page Title   : {scan.get('page_title', 'N/A')}",
        "─" * 64,
        f"  Overall Score  : {scan.get('overall_score', 0)}/100",
        f"  Overall Status : {scan.get('overall_status', 'N/A').upper()}",
        f"  Total Issues   : {scan.get('total_issues', 0)}",
        f"  Critical       : {scan.get('critical_count', 0)}",
        f"  Scan Duration  : {scan.get('scan_duration_ms', 0)}ms",
        "─" * 64,
        "  CATEGORY BREAKDOWN",
        "─" * 64,
    ]

    for cat in scan.get('categories', []):
        status_icon = "✓" if cat['status'] == 'pass' else ("⚠" if cat['status'] == 'warning' else "✗")
        lines.append(f"  {status_icon} {cat['name']:<28} {cat['score']:>3}/100  ({cat['failed']} issues)")
        for issue in cat.get('issues', []):
            sev = issue['severity'].upper()
            lines.append(f"      [{sev}] {issue['description'][:70]}")
            lines.append(f"             WCAG {issue['wcag']} — {issue['impact'][:60]}")

    lines += [
        "─" * 64,
        "  INTEGRITY",
        "─" * 64,
        f"  Algorithm : {receipt.get('hash', {}).get('algorithm', 'N/A')}",
        f"  Hash      : {receipt.get('hash', {}).get('value', 'N/A')}",
        f"  Operator  : {receipt.get('operator', 'N/A')}",
        f"  Protocol  : {receipt.get('idr_protocol', 'N/A')}",
        "═" * 64,
        f"  Registry  : {receipt.get('registry_url', 'N/A')}",
        "═" * 64,
    ]

    return "\n".join(lines)
