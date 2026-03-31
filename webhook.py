"""
IDR Webhook Handler — Gumroad payment verification
Receives Gumroad sale pings, verifies payment, triggers activation.
"""

import os
import hmac
import hashlib
import json
from datetime import datetime, timezone


GUMROAD_WEBHOOK_SECRET = os.environ.get('GUMROAD_WEBHOOK_SECRET', '')

# Product permalink → plan mapping
GUMROAD_PRODUCTS = {
    'idrshield':         'founding',   # $97 Founding Activation
    'idrshield-pro':     'pro',        # $29/month Pro
    'idrshield-basic':   'basic',      # $9/month Basic
}


def verify_gumroad_signature(payload_body: bytes, signature: str) -> bool:
    """
    Verify the Gumroad webhook signature.
    Gumroad signs with HMAC-SHA256 using your webhook secret.
    """
    if not GUMROAD_WEBHOOK_SECRET:
        # If no secret configured, skip verification (dev mode)
        print("WARNING: GUMROAD_WEBHOOK_SECRET not set — skipping signature verification")
        return True

    try:
        expected = hmac.new(
            GUMROAD_WEBHOOK_SECRET.encode('utf-8'),
            payload_body,
            hashlib.sha256
        ).hexdigest()  # hmac.new is the correct call (alias for hmac.HMAC)
        return hmac.compare_digest(expected, signature or '')
    except Exception as e:
        print(f"Signature verification error: {e}")
        return False


def parse_gumroad_payload(form_data: dict) -> dict:
    """
    Parse Gumroad webhook form POST into clean activation data.
    Gumroad sends form-encoded data, not JSON.
    """
    # Gumroad sends custom_fields as JSON string if you set them up
    # We use the 'url' custom field for the store URL
    custom_fields = {}
    try:
        cf_raw = form_data.get('custom_fields', '{}')
        if isinstance(cf_raw, str):
            custom_fields = json.loads(cf_raw)
    except Exception:
        pass

    return {
        'email':         form_data.get('email', '').strip(),
        'store_url':     custom_fields.get('store_url', '').strip(),
        'sale_id':       form_data.get('sale_id', ''),
        'product_id':    form_data.get('product_id', ''),
        'permalink':     form_data.get('permalink', ''),
        'price':         form_data.get('price', '0'),
        'currency':      form_data.get('currency', 'USD'),
        'refunded':      form_data.get('refunded', 'false').lower() == 'true',
        'disputed':      form_data.get('disputed', 'false').lower() == 'true',
        'timestamp':     datetime.now(timezone.utc).isoformat(),
        'plan':          GUMROAD_PRODUCTS.get(
                             form_data.get('permalink', ''), 'standard'
                         ),
    }


def is_valid_sale(parsed: dict) -> tuple:
    """
    Validate parsed Gumroad data before triggering activation.
    Returns (is_valid: bool, reason: str)
    """
    if parsed.get('refunded'):
        return False, "Sale has been refunded"

    if parsed.get('disputed'):
        return False, "Sale is under dispute"

    if not parsed.get('email') or '@' not in parsed['email']:
        return False, "No valid email in payload"

    if not parsed.get('store_url'):
        return False, "No store_url in custom fields — customer must provide store URL"

    if not parsed['store_url'].startswith(('http://', 'https://')):
        return False, f"Invalid store_url: {parsed['store_url']}"

    return True, "OK"
