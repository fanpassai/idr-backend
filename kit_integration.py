"""
IDR Kit (ConvertKit) Integration
Auto-tags buyers, manages sequences, removes prospect tags.
Called from Gumroad webhook on every verified purchase.
"""

import os
import json
import urllib.request
import urllib.error

KIT_API_KEY = os.environ.get('KIT_API_KEY', '')
KIT_API_BASE = 'https://api.convertkit.com/v3'

# Tag IDs from your Kit account (set these as env vars or hardcode after confirming)
TAG_FOUNDING_MEMBER  = os.environ.get('KIT_TAG_FOUNDING_MEMBER', '')
TAG_SCANNER_VISITOR  = os.environ.get('KIT_TAG_SCANNER_VISITOR', '')
TAG_PRO_MEMBER       = os.environ.get('KIT_TAG_PRO_MEMBER', '')

# Sequence IDs
SEQ_CUSTOMER_ONBOARDING = os.environ.get('KIT_SEQ_CUSTOMER_ONBOARDING', '')
SEQ_PROSPECT_NURTURE    = os.environ.get('KIT_SEQ_PROSPECT_NURTURE', '')


def _kit_request(method: str, path: str, data: dict = None) -> dict:
    """Make a Kit API request. Returns response dict or empty dict on error."""
    if not KIT_API_KEY:
        print("[KIT] No KIT_API_KEY set — skipping Kit action")
        return {}

    url = f"{KIT_API_BASE}{path}"
    if data is None:
        data = {}
    data['api_key'] = KIT_API_KEY

    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method=method
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8') if e.fp else ''
        print(f"[KIT] HTTP {e.code} on {method} {path}: {body[:200]}")
        return {}
    except Exception as ex:
        print(f"[KIT] Request error on {method} {path}: {ex}")
        return {}


def subscribe_and_tag(email: str, first_name: str = '',
                      tag_id: str = None, fields: dict = None) -> bool:
    """
    Subscribe an email to Kit and apply a tag.
    Creates subscriber if they don't exist.
    """
    if not KIT_API_KEY:
        return False

    # Subscribe / update subscriber
    sub_data = {
        'email': email,
        'first_name': first_name or '',
    }
    if fields:
        sub_data['fields'] = fields

    # If we have a tag, use the tag-subscribe endpoint
    if tag_id:
        resp = _kit_request('POST', f'/tags/{tag_id}/subscribe', sub_data)
        success = bool(resp.get('subscription'))
    else:
        resp = _kit_request('POST', '/subscribers', sub_data)
        success = bool(resp.get('subscriber'))

    if success:
        print(f"[KIT] Subscribed and tagged: {email} → tag {tag_id}")
    return success


def remove_tag(email: str, tag_id: str) -> bool:
    """Remove a tag from a subscriber."""
    if not KIT_API_KEY or not tag_id:
        return False

    # First get subscriber ID
    resp = _kit_request('GET', f'/subscribers?email_address={email}', {})
    subscribers = resp.get('subscribers', [])
    if not subscribers:
        return False

    subscriber_id = subscribers[0].get('id')
    if not subscriber_id:
        return False

    result = _kit_request(
        'DELETE',
        f'/subscribers/{subscriber_id}/tags/{tag_id}',
        {}
    )
    print(f"[KIT] Removed tag {tag_id} from {email}")
    return True


def add_to_sequence(email: str, sequence_id: str) -> bool:
    """Add a subscriber to a sequence."""
    if not KIT_API_KEY or not sequence_id:
        return False

    resp = _kit_request('POST', f'/sequences/{sequence_id}/subscribe', {
        'email': email
    })
    success = bool(resp.get('subscription'))
    if success:
        print(f"[KIT] Added {email} to sequence {sequence_id}")
    return success


def on_purchase(email: str, domain: str, plan: str = 'founding',
                full_name: str = '') -> bool:
    """
    Full Kit workflow triggered when a Gumroad purchase is verified.

    1. Subscribe with founding_member tag
    2. Remove scanner_visitor tag (if present)
    3. Add to customer onboarding sequence
    4. Set custom fields
    """
    if not KIT_API_KEY:
        print(f"[KIT] No API key — skipping Kit workflow for {email}")
        return False

    tag_id = TAG_FOUNDING_MEMBER
    if plan == 'pro':
        tag_id = TAG_PRO_MEMBER

    # Custom fields to store on the subscriber
    custom_fields = {
        'store_domain': domain,
        'idr_plan': plan,
        'activated_date': __import__('datetime').datetime.now(
            __import__('datetime').timezone.utc
        ).strftime('%Y-%m-%d'),
    }

    # 1. Subscribe + tag as founding_member
    subscribe_and_tag(
        email=email,
        first_name=full_name.split()[0] if full_name else '',
        tag_id=tag_id,
        fields=custom_fields
    )

    # 2. Remove prospect/scanner tag
    if TAG_SCANNER_VISITOR:
        remove_tag(email, TAG_SCANNER_VISITOR)

    # 3. Add to customer onboarding sequence
    if SEQ_CUSTOMER_ONBOARDING:
        add_to_sequence(email, SEQ_CUSTOMER_ONBOARDING)

    print(f"[KIT] Purchase workflow complete for {email} | "
          f"plan={plan} | domain={domain}")
    return True


def on_free_scan(email: str, domain: str) -> bool:
    """
    Kit workflow for free scanner visitors.
    Tags as scanner_visitor and starts prospect nurture.
    """
    if not KIT_API_KEY:
        return False

    subscribe_and_tag(
        email=email,
        tag_id=TAG_SCANNER_VISITOR,
        fields={'store_domain': domain}
    )

    if SEQ_PROSPECT_NURTURE:
        add_to_sequence(email, SEQ_PROSPECT_NURTURE)

    print(f"[KIT] Free scan workflow complete for {email}")
    return True
