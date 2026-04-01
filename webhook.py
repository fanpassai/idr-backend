"""
IDR Webhook Handler — Gumroad Ping verification
Gumroad sends sale data as form-encoded POST to the Ping endpoint.
Validation uses seller_id matching, not HMAC signature.
"""

import os
import json
from datetime import datetime, timezone


# Your Gumroad seller_id — visible in Settings → Advanced
# Set as env var: GUMROAD_SELLER_ID=AHFXde0wKu1at1UEzZUNyRg==
GUMROAD_SELLER_ID = os.environ.get('GUMROAD_SELLER_ID', '')

# Product permalink → plan mapping
GUMROAD_PRODUCTS = {
    'idrshield':       'founding',   # $97 Founding Activation
    'idrshield-pro':   'pro',        # $29/month Pro
    'idrshield-basic': 'basic',      # $9/month Basic
}


def verify_gumroad_seller(seller_id: str) -> bool:
    """
    Validate that the ping came from your Gumroad account.
    Gumroad Ping includes seller_id in every payload.
    If GUMROAD_SELLER_ID env var is not set, skip validation (dev mode).
    """
    if not GUMROAD_SELLER_ID:
        print("[WEBHOOK] WARNING: GUMROAD_SELLER_ID not set — skipping seller validation")
        return True

    if not seller_id:
        print("[WEBHOOK] No seller_id in payload")
        return False

    match = seller_id.strip() == GUMROAD_SELLER_ID.strip()
    if not match:
        print(f"[WEBHOOK] seller_id mismatch: got '{seller_id[:8]}...' "
              f"expected '{GUMROAD_SELLER_ID[:8]}...'")
    return match


def parse_gumroad_payload(form_data: dict) -> dict:
    """
    Parse Gumroad Ping form POST into clean activation data.
    Gumroad sends application/x-www-form-urlencoded.

    Custom fields set up on the product (e.g. store_url) come through
    as custom_fields[store_url] in the form data.
    """
    # Gumroad sends custom fields as custom_fields[field_name]
    # Try both formats: nested key and JSON string
    store_url = ''

    # Format 1: custom_fields[store_url] as direct form key
    store_url = form_data.get('custom_fields[store_url]', '').strip()

    # Format 2: custom_fields as JSON string
    if not store_url:
        try:
            cf_raw = form_data.get('custom_fields', '{}')
            if isinstance(cf_raw, str) and cf_raw:
                custom_fields = json.loads(cf_raw)
                store_url = custom_fields.get('store_url', '').strip()
        except Exception:
            pass

    # Format 3: store_url directly in form data (fallback)
    if not store_url:
        store_url = form_data.get('store_url', '').strip()

    return {
        'email':      form_data.get('email', '').strip(),
        'store_url':  store_url,
        'sale_id':    form_data.get('sale_id', ''),
        'seller_id':  form_data.get('seller_id', ''),
        'product_id': form_data.get('product_id', ''),
        'permalink':  form_data.get('permalink', ''),
        'price':      form_data.get('price', '0'),
        'currency':   form_data.get('currency', 'USD'),
        'full_name':  form_data.get('full_name', ''),
        'refunded':   str(form_data.get('refunded', 'false')).lower() == 'true',
        'disputed':   str(form_data.get('disputed', 'false')).lower() == 'true',
        'test':       str(form_data.get('test', 'false')).lower() == 'true',
        'timestamp':  datetime.now(timezone.utc).isoformat(),
        'plan':       GUMROAD_PRODUCTS.get(
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
        return False, (
            "No store_url provided. Make sure your Gumroad product has a "
            "custom field named 'store_url' that customers fill in at checkout."
        )

    url = parsed['store_url']
    if not url.startswith(('http://', 'https://')):
        # Try adding https:// if missing
        parsed['store_url'] = 'https://' + url
        if not parsed['store_url'].startswith('https://'):
            return False, f"Invalid store_url: {url}"

    return True, "OK"
