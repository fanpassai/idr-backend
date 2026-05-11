"""
ICC — icc_routes.py  v2.0
Flask routes for ICC Command Center.
Register as a blueprint in app.py.

WHAT'S NEW vs v1:
- /api/prospects now uses new get_prospects() with org_lane, priority_only,
  unscanned_only filter params matching the new icc.html filters
- /api/prospects/<pid>/contact-email — stores contact email permanently
- /api/prospects/scan/<pid> — uses new save_scan_result() with scan history
- /api/harvest — updated to call new run_harvest_cycle() Scout Agent
- /api/content/pending — serves generated LinkedIn posts for approval
- /api/content/generate — triggers content engine
- /api/content/<id>/approve — approves a content item
- /api/intelligence — serves intelligence items for briefing
- /api/ai — updated with HHS extension context and new response key
- /api/sendgrid/webhook — now calls log_email_event() in new schema
- All messaging updated: HHS extended to May 2027, not enforcement pending
"""

import os
import json
import hashlib
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from flask_cors import cross_origin

icc_bp = Blueprint('icc', __name__, url_prefix='/icc')

ICC_PASSWORD  = os.environ.get('ICC_PASSWORD', 'Praise_GodICC')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
ICC_TOKEN     = hashlib.sha256(ICC_PASSWORD.encode()).hexdigest()[:32]


def _auth(req):
    token = (req.headers.get('Authorization', '').replace('Bearer ', '') or
             req.headers.get('X-ICC-Token', '') or
             req.args.get('token', ''))
    return token == ICC_TOKEN


def _unauth():
    return jsonify({'error': 'Unauthorized'}), 401


def _serialize(obj):
    """Serialize datetime fields in dicts/lists."""
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict):
                for k, v in item.items():
                    if hasattr(v, 'isoformat'):
                        item[k] = v.isoformat()
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if hasattr(v, 'isoformat'):
                obj[k] = v.isoformat()
    return obj


# ── Auth ──────────────────────────────────────────────────────────────────────

@icc_bp.route('/api/login', methods=['POST', 'OPTIONS'])
@cross_origin()
def icc_login():
    if request.method == 'OPTIONS':
        return '', 200
    body = request.get_json(silent=True) or {}
    pw = body.get('password', '')
    if pw == ICC_PASSWORD:
        return jsonify({'success': True, 'token': ICC_TOKEN})
    return jsonify({'success': False, 'error': 'Wrong password'}), 401


# ── Stats / Dashboard ─────────────────────────────────────────────────────────

@icc_bp.route('/api/stats', methods=['GET'])
@cross_origin()
def icc_stats():
    if not _auth(request):
        return _unauth()
    from icc_database import get_icc_stats
    stats = get_icc_stats()
    print(f'[ICC_STATS] Returning: total={stats.get("total",0)} '
          f'scanned={stats.get("scanned",0)} priority={stats.get("priority",0)}')
    return jsonify(stats)


# ── Prospects ─────────────────────────────────────────────────────────────────

@icc_bp.route('/api/prospects', methods=['GET'])
@cross_origin()
def icc_get_prospects():
    if not _auth(request):
        return _unauth()
    from icc_database import get_prospects

    state          = request.args.get('state') or None
    org_type       = request.args.get('org_type') or request.args.get('type') or None
    org_lane       = request.args.get('org_lane') or None
    priority_only  = request.args.get('priority_only') == 'true'
    unscanned_only = request.args.get('unscanned_only') == 'true'
    limit          = int(request.args.get('limit', 200))
    offset         = int(request.args.get('offset', 0))

    prospects = get_prospects(
        state=state, org_type=org_type, org_lane=org_lane,
        priority_only=priority_only, unscanned_only=unscanned_only,
        limit=limit, offset=offset,
    )
    _serialize(prospects)
    return jsonify({'prospects': prospects, 'count': len(prospects)})


@icc_bp.route('/api/prospects/<pid>', methods=['GET'])
@cross_origin()
def icc_get_prospect(pid):
    if not _auth(request):
        return _unauth()
    from icc_database import get_prospect_by_id
    p = get_prospect_by_id(pid)
    if not p:
        return jsonify({'error': 'Not found'}), 404
    _serialize(p)
    return jsonify(p)


@icc_bp.route('/api/prospects/<pid>/contact-email', methods=['POST'])
@cross_origin()
def icc_store_contact_email(pid):
    """
    Store contact email permanently on a prospect record.
    Called when user types an email in the Email Queue — stored forever.
    Never have to type it again.
    """
    if not _auth(request):
        return _unauth()
    body = request.get_json(silent=True) or {}
    email = body.get('email', '').strip()
    if not email:
        return jsonify({'success': False, 'error': 'No email provided'}), 400
    try:
        from icc_database import update_prospect_contact_email
        ok = update_prospect_contact_email(pid, email)
        return jsonify({'success': ok})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@icc_bp.route('/api/prospects/scan/<pid>', methods=['POST'])
@cross_origin()
def icc_scan_prospect(pid):
    """
    Save scan result permanently.
    Uses new save_scan_result() which writes to both icc_prospects
    and icc_scan_history for trend analysis.
    Auto-queues email for FAIL scores.
    """
    if not _auth(request):
        return _unauth()
    body      = request.get_json(silent=True) or {}
    score     = body.get('score')
    criticals = int(body.get('criticals', 0))
    website   = body.get('website', '')
    name      = body.get('name', '')
    total     = int(body.get('total_issues', 0))

    if score is None:
        return jsonify({'success': False, 'error': 'No score provided'}), 400

    try:
        from icc_database import save_scan_result, get_prospect_by_id
        ok = save_scan_result(pid, website, name, int(score), criticals, total)

        # Auto-queue FAIL email
        if ok and int(score) < 60:
            try:
                from icc_email_queue import generate_prospect_email, queue_prospect_email
                p = get_prospect_by_id(pid) or {
                    'id': pid, 'name': name, 'website': website,
                    'idr_score': score, 'critical_count': criticals,
                    'org_type': 'fqhc', 'org_lane': 'healthcare',
                    'city': '', 'state': '',
                }
                email_data = generate_prospect_email(p)
                if email_data:
                    queue_prospect_email(email_data)
            except Exception as eq_err:
                print(f'[ICC] Auto-queue error: {eq_err}')

        return jsonify({
            'success': ok,
            'prospect': {
                'id': pid, 'idr_score': int(score),
                'critical_count': criticals, 'scanned': True,
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@icc_bp.route('/api/prospects/seed', methods=['POST'])
@cross_origin()
def icc_seed_prospects():
    """
    Called by icc.html on login — triggers startup_seed() if DB is empty.
    Also accepts a prospects array for backward compatibility.
    """
    if not _auth(request):
        return _unauth()
    body = request.get_json(silent=True) or {}
    prospects = body.get('prospects', [])

    try:
        from icc_database import get_icc_stats, startup_seed, bulk_upsert_prospects
        stats = get_icc_stats()
        if stats.get('total', 0) < 10:
            # DB is empty — run full startup seed
            saved = startup_seed()
            return jsonify({'success': True, 'saved': saved, 'source': 'startup_seed'})
        elif prospects:
            # Browser sent prospects — upsert them
            saved = bulk_upsert_prospects(prospects)
            return jsonify({'success': True, 'saved': saved, 'source': 'browser_seed'})
        else:
            return jsonify({'success': True, 'saved': 0,
                            'message': f'DB already has {stats["total"]} prospects'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@icc_bp.route('/api/prospects/scanned', methods=['GET'])
@cross_origin()
def icc_get_scanned():
    if not _auth(request):
        return _unauth()
    try:
        from icc_database import get_scanned_prospects
        limit = int(request.args.get('limit', 200))
        prospects = get_scanned_prospects(limit=limit)
        _serialize(prospects)
        return jsonify({'success': True, 'prospects': prospects, 'count': len(prospects)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Harvest (Scout Agent) ─────────────────────────────────────────────────────

@icc_bp.route('/api/harvest', methods=['POST'])
@cross_origin()
def icc_trigger_harvest():
    """
    Trigger the Scout Agent harvest cycle.
    Uses hybrid data strategy: HRSA → CMS → data.gov → seed fallback.
    Never returns zero.
    """
    if not _auth(request):
        return _unauth()
    body   = request.get_json(silent=True) or {}
    states = body.get('states', ['FL', 'TX', 'GA', 'NY', 'NC'])
    limit  = int(body.get('limit', 50))

    try:
        from icc_worker import run_harvest_cycle
        import threading
        # Run in background thread so request returns immediately
        t = threading.Thread(
            target=run_harvest_cycle,
            kwargs={'states': states, 'limit_per_state': limit},
            daemon=True,
        )
        t.start()
        return jsonify({
            'success': True,
            'message': f'Harvest started for {len(states)} states — '
                       f'prospects will appear in database within 60 seconds',
            'states': states,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Outreach Tracker ──────────────────────────────────────────────────────────

@icc_bp.route('/api/outreach', methods=['GET'])
@cross_origin()
def icc_get_outreach():
    if not _auth(request):
        return _unauth()
    from icc_database import get_outreach_list, get_followups_due
    status   = request.args.get('status')
    limit    = int(request.args.get('limit', 100))
    outreach = get_outreach_list(status=status, limit=limit)
    followups = get_followups_due()
    _serialize(outreach)
    _serialize(followups)
    return jsonify({'outreach': outreach, 'followups': followups})


@icc_bp.route('/api/outreach', methods=['POST'])
@cross_origin()
def icc_log_outreach():
    if not _auth(request):
        return _unauth()
    body = request.get_json(silent=True) or {}
    from icc_database import log_outreach, log_activity
    oid = log_outreach(
        prospect_id   = body.get('prospect_id', ''),
        prospect_name = body.get('prospect_name', ''),
        contact_email = body.get('contact_email', ''),
        contact_name  = body.get('contact_name', ''),
        contact_title = body.get('contact_title', ''),
        message_type  = body.get('message_type', 'email'),
        subject       = body.get('subject', ''),
        notes         = body.get('notes', ''),
    )
    log_activity('outreach_sent',
                 f"Sent to {body.get('prospect_name', '')} ({body.get('message_type', 'email')})")
    return jsonify({'success': True, 'id': oid})


@icc_bp.route('/api/outreach/<int:oid>', methods=['PUT'])
@cross_origin()
def icc_update_outreach(oid):
    if not _auth(request):
        return _unauth()
    body = request.get_json(silent=True) or {}
    from icc_database import update_outreach_status, log_activity
    status  = body.get('status', '')
    revenue = int(body.get('revenue', 0))
    update_outreach_status(oid, status, revenue, body.get('notes', ''))
    if status == 'converted':
        log_activity('conversion', f'Client converted — ${revenue} revenue')
    return jsonify({'success': True})


# ── Associations ──────────────────────────────────────────────────────────────

@icc_bp.route('/api/associations', methods=['GET'])
@cross_origin()
def icc_get_associations():
    if not _auth(request):
        return _unauth()
    from icc_database import get_associations
    lane   = request.args.get('lane')
    assocs = get_associations(lane=lane)
    _serialize(assocs)
    return jsonify({'associations': assocs})


@icc_bp.route('/api/associations/<aid>', methods=['PUT'])
@cross_origin()
def icc_update_association(aid):
    if not _auth(request):
        return _unauth()
    body = request.get_json(silent=True) or {}
    from icc_database import update_association_status, log_activity
    status = body.get('status', '')
    update_association_status(aid, status, body.get('notes', ''))
    log_activity('association_updated', f'Association {aid} updated to {status}')
    return jsonify({'success': True})


# ── AI Advisor ────────────────────────────────────────────────────────────────

@icc_bp.route('/api/ai', methods=['POST', 'OPTIONS'])
@cross_origin()
def icc_ai():
    if request.method == 'OPTIONS':
        return '', 200
    if not _auth(request):
        return _unauth()
    if not ANTHROPIC_KEY:
        return jsonify({'error': 'AI not configured — add ANTHROPIC_API_KEY to Railway'}), 503

    body    = request.get_json(silent=True) or {}
    message = (body.get('message') or body.get('prompt', '')).strip()
    context = body.get('context', {})
    history = body.get('history', [])

    if not message:
        return jsonify({'error': 'message required'}), 400

    days_past = max(0, (datetime.now(timezone.utc) -
                        datetime(2026, 5, 11, tzinfo=timezone.utc)).days)

    # Updated system prompt — HHS extension context
    system = f"""You are the ICC AI Advisor for the Institute of Digital Remediation.

CURRENT SITUATION — READ THIS CAREFULLY:
- HHS has extended the Section 504 digital accessibility deadline to May 2027
- This does NOT mean enforcement paused — OCR complaint investigations continue
- Organizations that received complaints between May 11 and the extension announcement
  have no documented record — they are still exposed
- The extension creates a new opportunity: most organizations just exhaled and stopped
  paying attention — exactly when they are most vulnerable
- The record is still the defense. The extension moved the goalposts, not the game.

PRODUCT:
- $497 one-time HHS Accessibility Audit — 30-page PDF, SHA-256 certified, delivered in 48hrs
- $49/month monitoring — weekly scans, monthly reports, verification certificate
- Registry verification at idrshield.com/verify
- Scan page: idrshield.com/healthscan
- Stripe: https://buy.stripe.com/14A00i4QX9so6UF11q2sM01
- Founder: Hans-Peter Nkansah, Institute of Digital Remediation
- Email: hans-peter@instituteofdigitalremediation.org

BRAND VOICE:
- Institutional authority — never hype, never fear-mongering
- Specific and factual — cite real regulation (HHS 89 FR 40066, 45 CFR Part 84, WCAG 2.1 AA)
- The record is the defense — not the score, not the statement
- Post-deadline positioning: enforcement window still open, extension does not erase exposure

LIVE PIPELINE CONTEXT:
{json.dumps(context, indent=2)}

CONVERSATION HISTORY: {len(history)} messages

RULES:
- Answer in the same language the user is using
- Be specific and actionable — ready to copy and use immediately
- When writing LinkedIn posts: institutional noir voice, real data, no emojis
- When writing outreach: plain text, specific, no dashes, no hype
- Always end with a clear next action"""

    try:
        import urllib.request as urlreq
        import ssl

        # Build messages including history
        messages = []
        for h in history[-6:]:  # Last 6 exchanges for context
            if h.get('role') and h.get('content'):
                messages.append({'role': h['role'], 'content': h['content']})
        messages.append({'role': 'user', 'content': message})

        payload = json.dumps({
            'model':      'claude-sonnet-4-20250514',
            'max_tokens': 1200,
            'system':     system,
            'messages':   messages,
        }).encode()

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urlreq.Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={
                'x-api-key':         ANTHROPIC_KEY,
                'anthropic-version': '2023-06-01',
                'Content-Type':      'application/json',
            },
            method='POST',
        )
        with urlreq.urlopen(req, timeout=30, context=ctx) as r:
            data = json.loads(r.read())

        reply = ''.join(
            b.get('text', '') for b in data.get('content', [])
            if b.get('type') == 'text'
        )
        # Return both 'reply' and 'response' keys for compatibility
        return jsonify({'success': True, 'reply': reply, 'response': reply})

    except Exception as e:
        print(f'[ICC_AI] Error: {e}')
        return jsonify({'error': str(e)}), 500


# ── Content Engine ────────────────────────────────────────────────────────────

@icc_bp.route('/api/content/pending', methods=['GET'])
@cross_origin()
def icc_content_pending():
    """Return pending LinkedIn content for approval in the Content room."""
    if not _auth(request):
        return _unauth()
    try:
        from icc_database import get_pending_content
        limit = int(request.args.get('limit', 20))
        items = get_pending_content(limit=limit)
        _serialize(items)
        return jsonify({'content': items, 'count': len(items)})
    except Exception as e:
        return jsonify({'content': [], 'error': str(e)})


@icc_bp.route('/api/content/generate', methods=['POST'])
@cross_origin()
def icc_content_generate():
    """Trigger the content engine to generate today's posts from scan data."""
    if not _auth(request):
        return _unauth()
    try:
        from icc_worker import generate_daily_content
        import threading
        t = threading.Thread(target=generate_daily_content, daemon=True)
        t.start()
        return jsonify({'success': True, 'message': 'Content generation started'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@icc_bp.route('/api/content/<int:cid>/approve', methods=['POST'])
@cross_origin()
def icc_content_approve(cid):
    """Mark a content item as approved."""
    if not _auth(request):
        return _unauth()
    try:
        from icc_database import get_conn
        conn = get_conn()
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE icc_content SET
                        status='approved', published_at=NOW()
                    WHERE id=%s
                """, (cid,))
            conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Intelligence ──────────────────────────────────────────────────────────────

@icc_bp.route('/api/intelligence', methods=['GET'])
@cross_origin()
def icc_get_intelligence():
    """Return latest intelligence items for the briefing and radar."""
    if not _auth(request):
        return _unauth()
    try:
        from icc_database import get_fresh_intelligence
        limit = int(request.args.get('limit', 10))
        items = get_fresh_intelligence(limit=limit)
        _serialize(items)
        return jsonify({'intelligence': items, 'count': len(items)})
    except Exception as e:
        return jsonify({'intelligence': [], 'error': str(e)})


# ── Email Queue ───────────────────────────────────────────────────────────────

@icc_bp.route('/api/queue/stats', methods=['GET'])
@cross_origin()
def icc_queue_stats():
    if not _auth(request):
        return _unauth()
    from icc_email_queue import get_queue_stats
    return jsonify(get_queue_stats())


@icc_bp.route('/api/queue/prospects', methods=['GET'])
@cross_origin()
def icc_queue_prospects():
    if not _auth(request):
        return _unauth()
    from icc_email_queue import get_pending_emails
    limit  = int(request.args.get('limit', 50))
    emails = get_pending_emails(limit=limit)
    _serialize(emails)
    return jsonify({'emails': emails, 'count': len(emails)})


@icc_bp.route('/api/queue/associations', methods=['GET'])
@cross_origin()
def icc_queue_associations():
    if not _auth(request):
        return _unauth()
    from icc_email_queue import get_pending_association_emails
    emails = get_pending_association_emails()
    _serialize(emails)
    return jsonify({'emails': emails, 'count': len(emails)})


@icc_bp.route('/api/queue/approve/<int:qid>', methods=['POST'])
@cross_origin()
def icc_approve_email(qid):
    if not _auth(request):
        return _unauth()
    body = request.get_json(silent=True) or {}
    from icc_email_queue import approve_and_send
    result = approve_and_send(
        qid,
        to_email=body.get('to_email', ''),
        edited_body=body.get('body_text'),
    )
    # Store contact email permanently if provided
    if body.get('to_email') and result.get('prospect_id'):
        try:
            from icc_database import update_prospect_contact_email
            update_prospect_contact_email(result['prospect_id'], body['to_email'])
        except Exception:
            pass
    return jsonify(result)


@icc_bp.route('/api/queue/approve-association/<int:qid>', methods=['POST'])
@cross_origin()
def icc_approve_association(qid):
    if not _auth(request):
        return _unauth()
    body = request.get_json(silent=True) or {}
    from icc_email_queue import approve_and_send_association
    result = approve_and_send_association(qid, edited_body=body.get('body_text'))
    if result.get('success'):
        try:
            from icc_database import mark_association_contacted
            from database import get_conn
            conn = get_conn()
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        'SELECT assoc_id, contact_email FROM icc_association_queue WHERE id=%s',
                        (qid,)
                    )
                    row = cur.fetchone()
                    if row:
                        mark_association_contacted(row[0], row[1] or '')
                conn.close()
        except Exception as e:
            print(f'[ICC] mark_assoc error: {e}')
    return jsonify(result)


@icc_bp.route('/api/queue/seed-associations', methods=['POST'])
@cross_origin()
def icc_seed_associations():
    if not _auth(request):
        return _unauth()
    from icc_email_queue import queue_association_emails
    added = queue_association_emails()
    return jsonify({'success': True, 'added': added})


@icc_bp.route('/api/queue/generate', methods=['POST'])
@cross_origin()
def icc_generate_queue():
    if not _auth(request):
        return _unauth()
    from icc_email_queue import generate_and_queue_from_prospects
    added = generate_and_queue_from_prospects(limit=200)
    return jsonify({'success': True, 'queued': added})


@icc_bp.route('/api/queue/reset-associations', methods=['POST'])
@cross_origin()
def icc_reset_associations():
    if not _auth(request):
        return _unauth()
    from icc_email_queue import reset_and_reseed_associations
    added = reset_and_reseed_associations()
    return jsonify({'success': True, 'reseeded': added})


@icc_bp.route('/api/queue/send-test', methods=['POST'])
@cross_origin()
def icc_send_test():
    if not _auth(request):
        return _unauth()
    from icc_email_queue import send_test_email
    result = send_test_email('idrshieldhq@gmail.com')
    return jsonify(result)


@icc_bp.route('/api/queue/resend-bounced', methods=['POST'])
@cross_origin()
def icc_resend_bounced():
    if not _auth(request):
        return _unauth()
    from icc_email_queue import (generate_association_emails,
                                  _send_via_sendgrid)
    corrections = {
        'nachc':  'mking@nachc.org',
        'mgma':   'memberservices@mgma.com',
        'ahip':   'info@ahip.org',
        'ahla':   'info@americanhealthlaw.org',
        'nahc':   'nahc@nahc.org',
    }
    sent, failed = [], []
    assocs = generate_association_emails()
    for a in assocs:
        if a['id'] not in corrections:
            continue
        email = corrections[a['id']]
        try:
            _send_via_sendgrid(
                email, a['subject'], a['body'],
                salutation=a.get('salutation', 'Team'),
                institutional=True,
            )
            sent.append({'name': a['name'], 'email': email})
            try:
                from icc_database import mark_association_contacted
                mark_association_contacted(a['id'], email)
            except Exception:
                pass
        except Exception as e:
            failed.append({'name': a['name'], 'email': email, 'error': str(e)})
    return jsonify({'success': True, 'sent': sent, 'failed': failed,
                    'sent_count': len(sent)})


# ── Briefing ──────────────────────────────────────────────────────────────────

@icc_bp.route('/api/briefing/send-now', methods=['POST'])
@cross_origin()
def icc_send_briefing_now():
    if not _auth(request):
        return _unauth()
    try:
        from icc_worker import send_daily_briefing
        # Run inline so errors surface immediately — not silently swallowed
        send_daily_briefing()
        return jsonify({'success': True,
                        'message': 'Briefing sent to idrshieldhq@gmail.com'})
    except Exception as e:
        print(f'[BRIEFING_ROUTE] Error: {e}')
        return jsonify({'success': False, 'error': str(e)})


# ── SendGrid Webhook ──────────────────────────────────────────────────────────

@icc_bp.route('/api/sendgrid/webhook', methods=['POST'])
@cross_origin()
def icc_sendgrid_webhook():
    """
    Receive SendGrid open/click/bounce events.
    Uses new log_email_event() which writes to icc_email_events
    and auto-flags warm leads.
    """
    events = request.get_json(silent=True) or []
    if not isinstance(events, list):
        events = [events]

    from icc_database import log_email_event, log_activity

    for event in events:
        event_type  = event.get('event', '')
        email_to    = event.get('email', '')
        sg_tags     = event.get('unique_args', {}) or {}
        prospect_id = sg_tags.get('prospect_id', '')

        if event_type in ('open', 'click', 'bounce', 'unsubscribe'):
            log_email_event(
                prospect_id=prospect_id,
                event_type=event_type,
                email_address=email_to,
                raw_payload=event,
            )
            if event_type in ('open', 'click') and prospect_id:
                log_activity(
                    'email_opened' if event_type == 'open' else 'email_clicked',
                    f'Prospect {prospect_id} {event_type}ed — WARM LEAD',
                )

    return jsonify({'success': True}), 200


# ── Scanner Visitors ──────────────────────────────────────────────────────────

@icc_bp.route('/api/scanner/visitors', methods=['GET'])
@cross_origin()
def icc_scanner_visitors():
    """
    Returns organizations that ran a scan on healthscan.html.
    Pulls from receipts table — every external scan is a warm lead.
    Also checks icc_scan_history for any logged scans.
    """
    if not _auth(request):
        return _unauth()
    from database import get_conn
    conn = get_conn()
    if not conn:
        return jsonify({'visitors': []})
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT ON (domain)
                    domain,
                    score,
                    critical_count,
                    created_at as timestamp_utc,
                    receipt_id
                FROM receipts
                WHERE domain IS NOT NULL
                  AND domain NOT IN ('idrshield.com','idrshieldhq',
                                     'instituteofdigitalremediation.org')
                ORDER BY domain, created_at DESC
                LIMIT 100
            """)
            cols = [d[0] for d in cur.description]
            rows = []
            for r in cur.fetchall():
                row = dict(zip(cols, r))
                if row.get('timestamp_utc'):
                    row['timestamp_utc'] = row['timestamp_utc'].isoformat()
                rows.append(row)
        rows.sort(key=lambda x: x.get('timestamp_utc', ''), reverse=True)
        return jsonify({'visitors': rows, 'count': len(rows)})
    except Exception as e:
        print(f'[ICC] Scanner visitors error: {e}')
        return jsonify({'visitors': [], 'error': str(e)})
    finally:
        conn.close()


# ── Playbook ──────────────────────────────────────────────────────────────────

@icc_bp.route('/api/playbook', methods=['GET'])
@cross_origin()
def icc_playbook():
    """
    Post-deadline playbook. HHS extended to May 2027.
    Messaging: enforcement still open, extension does not erase prior exposure.
    """
    if not _auth(request):
        return _unauth()

    days_past = max(0, (datetime.now(timezone.utc) -
                        datetime(2026, 5, 11, tzinfo=timezone.utc)).days)

    playbook = {
        'situation': {
            'headline': 'HHS Extended to May 2027 — Enforcement Still Active',
            'summary': (
                'HHS announced an extension of the Section 504 digital accessibility '
                'deadline to May 2027. This does not pause OCR complaint investigations. '
                'Organizations that received complaints during the May 11 window have '
                'no documented record. The extension creates a new opportunity: most '
                'organizations just exhaled and stopped paying attention.'
            ),
            'days_past_original_deadline': days_past,
        },
        'positioning': {
            'do_not_say': [
                'X days to the new deadline',
                'You have until 2027',
                'The deadline has been extended so you have time',
            ],
            'do_say': [
                'The extension moved the deadline — not the enforcement window',
                'OCR complaint investigations did not pause',
                'Organizations without a record are still exposed',
                'The record is the defense — the extension does not create one retroactively',
                'Most organizations just stopped paying attention — that is your opening',
            ],
        },
        'immediate_actions': [
            'Update LinkedIn posts to extension-aware messaging — post today',
            'Send updated outreach to all FAIL prospects with new angle',
            'Contact associations with the extension-as-opportunity framing',
            'Email the attorney channel — this is their most urgent client alert',
        ],
        'weekly_rhythm': {
            'monday':    'Review radar — approve email queue — post LinkedIn Observatory',
            'tuesday':   'Scan 20 new prospects — call warm leads',
            'wednesday': 'Post LinkedIn Intelligence Brief — follow up associations',
            'thursday':  'Generate weekly report data — check scanner visitors',
            'friday':    'Publish Weekly Intelligence Brief — review conversion pipeline',
        },
    }
    return jsonify({'playbook': playbook, 'days_past': days_past})


# ── Health ────────────────────────────────────────────────────────────────────

@icc_bp.route('/health', methods=['GET'])
def icc_health():
    return jsonify({
        'status':    'ICC operational',
        'version':   '2.0',
        'timestamp': datetime.now(timezone.utc).isoformat(),
    })
