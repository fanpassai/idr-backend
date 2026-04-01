"""
IDR Webhook Handler — Gumroad Ping verification
Gumroad sends sale data as form-encoded POST to the Ping endpoint.
Validation uses seller_id matching, not HMAC signature.
"""

import os
import json
from datetime import datetime, timezone


GUMROAD_SELLER_ID = os.environ.get('GUMROAD_SELLER_ID', '')

GUMROAD_PRODUCTS = {
    'idrshield':       'founding',
    'idr-shield':      'founding',
    'idrshield-pro':   'pro',
    'idrshield-basic': 'basic',
}


def verify_gumroad_seller(seller_id: str) -> bool:
    if not GUMROAD_SELLER_ID:
        print("[WEBHOOK] WARNING: GUMROAD_SELLER_ID not set — skipping seller validation")
        return True
    if not seller_id:
        print("[WEBHOOK] No seller_id in payload")
        return False
    match = seller_id.strip() == GUMROAD_SELLER_ID.strip()
    if not match:
        print(f"[WEBHOOK] seller_id mismatch: "
              f"got '{seller_id[:12]}' expected '{GUMROAD_SELLER_ID[:12]}'")
    return match


def parse_gumroad_payload(form_data: dict) -> dict:
    """
    Parse Gumroad Ping payload.
    Gumroad sends custom field LABELS as key names verbatim.
    So a field labeled 'Your store URL to activate...' arrives
    with that full string as the key. We find it by scanning for
    any key whose VALUE looks like a URL.
    """
    store_url = ''

    # Strategy: scan ALL form values for anything that looks like a URL
    # This handles any field label the merchant sets in Gumroad
    for key, value in form_data.items():
        if not value:
            continue
        val = value.strip()
        # Skip the example placeholder text
        if 'yourstore.com' in val.lower() or 'example.com' in val.lower():
            continue
        if val.startswith(('http://', 'https://', 'www.')):
            # Extra check: make sure it's not an internal Gumroad URL
            if 'gumroad.com' not in val and 'gum.co' not in val:
                store_url = val
                print(f"[WEBHOOK] store_url found in field '{key[:60]}': {val}")
                break

    # Add https:// if missing
    if store_url and not store_url.startswith(('http://', 'https://')):
        store_url = 'https://' + store_url

    # Determine plan from permalink
    permalink = form_data.get('permalink', '').lower()
    plan = 'founding'
    for key, val in GUMROAD_PRODUCTS.items():
        if key in permalink:
            plan = val
            break

    return {
        'email':      form_data.get('email', '').strip(),
        'store_url':  store_url,
        'sale_id':    form_data.get('sale_id', ''),
        'seller_id':  form_data.get('seller_id', ''),
        'product_id': form_data.get('product_id', ''),
        'permalink':  permalink,
        'price':      form_data.get('price', '0'),
        'currency':   form_data.get('currency', 'USD'),
        'full_name':  form_data.get('full_name', ''),
        'refunded':   str(form_data.get('refunded', 'false')).lower() == 'true',
        'disputed':   str(form_data.get('disputed', 'false')).lower() == 'true',
        'test':       str(form_data.get('test', 'false')).lower() == 'true',
        'timestamp':  datetime.now(timezone.utc).isoformat(),
        'plan':       plan,
    }


def is_valid_sale(parsed: dict) -> tuple:
    if parsed.get('refunded'):
        return False, "Sale has been refunded"
    if parsed.get('disputed'):
        return False, "Sale is under dispute"
    if not parsed.get('email') or '@' not in parsed['email']:
        return False, "No valid email in payload"
    if not parsed.get('store_url'):
        return False, (
            "No store URL found in purchase data. "
            "Make sure your Gumroad product has a required field "
            "where customers enter their store URL."
        )
    return True, "OK"
