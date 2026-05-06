"""
ICC — icc_routes.py
Flask routes for ICC Command Center.
Register as a blueprint in app.py.
"""

import os
import json
import hashlib
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin

icc_bp = Blueprint('icc', __name__, url_prefix='/icc')

ICC_PASSWORD  = os.environ.get('ICC_PASSWORD', 'Praise_GodICC')
ANTHROPIC_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
ICC_TOKEN     = hashlib.sha256(ICC_PASSWORD.encode()).hexdigest()[:32]


def _auth(req):
    token = req.headers.get('X-ICC-Token','') or req.args.get('token','')
    return token == ICC_TOKEN


def _unauth():
    return jsonify({'error': 'Unauthorized'}), 401


# ── Auth ──────────────────────────────────────────────────────────────────────

@icc_bp.route('/api/login', methods=['POST', 'OPTIONS'])
@cross_origin()
def icc_login():
    if request.method == 'OPTIONS': return '', 200
    body = request.get_json(silent=True) or {}
    pw   = body.get('password','')
    if pw == ICC_PASSWORD:
        return jsonify({'success': True, 'token': ICC_TOKEN})
    return jsonify({'success': False, 'error': 'Wrong password'}), 401


# ── Stats / Dashboard ─────────────────────────────────────────────────────────

@icc_bp.route('/api/stats', methods=['GET'])
@cross_origin()
def icc_stats():
    if not _auth(request): return _unauth()
    from icc_database import get_icc_stats
    return jsonify(get_icc_stats())


# ── Prospects ─────────────────────────────────────────────────────────────────

@icc_bp.route('/api/prospects', methods=['GET'])
@cross_origin()
def icc_get_prospects():
    if not _auth(request): return _unauth()
    from icc_database import get_prospects
    state        = request.args.get('state')
    org_type     = request.args.get('type')
    priority_only= request.args.get('priority') == '1'
    limit        = int(request.args.get('limit', 200))
    offset       = int(request.args.get('offset', 0))
    prospects    = get_prospects(state=state, org_type=org_type,
                                 priority_only=priority_only,
                                 limit=limit, offset=offset)
    # Serialize datetimes
    for p in prospects:
        for k, v in p.items():
            if hasattr(v, 'isoformat'):
                p[k] = v.isoformat()
    return jsonify({'prospects': prospects, 'count': len(prospects)})


@icc_bp.route('/api/prospects/<pid>', methods=['GET'])
@cross_origin()
def icc_get_prospect(pid):
    if not _auth(request): return _unauth()
    from icc_database import get_prospect_by_id
    p = get_prospect_by_id(pid)
    if not p: return jsonify({'error': 'Not found'}), 404
    for k, v in p.items():
        if hasattr(v, 'isoformat'): p[k] = v.isoformat()
    return jsonify(p)


@icc_bp.route('/api/prospects/scan/<pid>', methods=['POST'])
@cross_origin()
def icc_scan_prospect(pid):
    if not _auth(request): return _unauth()
    body = request.get_json(silent=True) or {}
    website = body.get('website', '')
    name = body.get('name', '')

    # Try DB first
    try:
        from icc_database import get_prospect_by_id, upsert_prospect
        from icc_worker import scan_prospect
        p = get_prospect_by_id(pid)
        if p:
            ok = scan_prospect(p)
            updated = get_prospect_by_id(pid)
            for k, v in updated.items():
                if hasattr(v, 'isoformat'): updated[k] = v.isoformat()
            return jsonify({'success': ok, 'prospect': updated})
    except Exception:
        pass

    # Fallback: scan the URL directly (works for browser-loaded seed prospects)
    if not website:
        return jsonify({'error': 'No website provided'}), 400

    try:
        import requests as req_lib
        from urllib.parse import urlparse
        url = website if website.startswith('http') else f'https://{website}'
        domain = urlparse(url).netloc or website.replace('https://','').replace('http://','')

        # Call the IDR scanner endpoint
        backend = 'https://idr-backend-production.up.railway.app'
        r = req_lib.post(f'{backend}/api/scan',
            json={'url': url},
            timeout=30)
        scan_data = r.json() if r.ok else {}

        score = scan_data.get('score', 0)
        criticals = scan_data.get('critical_count', 0)
        total = scan_data.get('total_issues', 0)

        # Save to DB for future use
        try:
            from icc_database import upsert_prospect
            upsert_prospect({
                'id': pid,
                'name': name,
                'website': website,
                'idr_score': score,
                'critical_count': criticals,
                'scanned': True,
            })
        except Exception:
            pass

        return jsonify({
            'success': True,
            'prospect': {
                'id': pid,
                'name': name,
                'website': website,
                'idr_score': score,
                'critical_count': criticals,
                'total_issues': total,
                'scanned': True,
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@icc_bp.route('/api/harvest', methods=['POST'])
@cross_origin()
def icc_trigger_harvest():
    if not _auth(request): return _unauth()
    body     = request.get_json(silent=True) or {}
    state    = body.get('state')
    org_type = body.get('type', 'fqhc')
    limit    = int(body.get('limit', 100))
    from icc_worker import harvest_fqhc, harvest_nursing_homes
    if org_type == 'fqhc':
        added = harvest_fqhc(state, limit)
    elif org_type == 'nh':
        added = harvest_nursing_homes(state, limit)
    else:
        added = 0
    return jsonify({'success': True, 'added': added,
                    'message': f'{added} prospects loaded'})


# ── Outreach Tracker ──────────────────────────────────────────────────────────

@icc_bp.route('/api/outreach', methods=['GET'])
@cross_origin()
def icc_get_outreach():
    if not _auth(request): return _unauth()
    from icc_database import get_outreach_list, get_followups_due
    status   = request.args.get('status')
    outreach = get_outreach_list(status=status)
    followups= get_followups_due()
    for row in outreach + followups:
        for k, v in row.items():
            if hasattr(v, 'isoformat'): row[k] = v.isoformat()
    return jsonify({'outreach': outreach, 'followups': followups})


@icc_bp.route('/api/outreach', methods=['POST'])
@cross_origin()
def icc_log_outreach():
    if not _auth(request): return _unauth()
    body = request.get_json(silent=True) or {}
    from icc_database import log_outreach, log_activity
    oid = log_outreach(
        prospect_id   = body.get('prospect_id',''),
        prospect_name = body.get('prospect_name',''),
        contact_name  = body.get('contact_name',''),
        contact_title = body.get('contact_title',''),
        message_type  = body.get('message_type','connection'),
        notes         = body.get('notes',''),
    )
    log_activity('outreach_sent',
                 f"Sent to {body.get('prospect_name','')} "
                 f"({body.get('message_type','')})")
    return jsonify({'success': True, 'id': oid})


@icc_bp.route('/api/outreach/<int:oid>', methods=['PUT'])
@cross_origin()
def icc_update_outreach(oid):
    if not _auth(request): return _unauth()
    body = request.get_json(silent=True) or {}
    from icc_database import update_outreach_status, log_activity
    status  = body.get('status','')
    revenue = int(body.get('revenue', 0))
    update_outreach_status(oid, status, revenue, body.get('notes',''))
    if status == 'converted':
        log_activity('conversion',
                     f"Client converted — ${revenue} revenue", 1)
    return jsonify({'success': True})


# ── Associations ──────────────────────────────────────────────────────────────

@icc_bp.route('/api/associations', methods=['GET'])
@cross_origin()
def icc_get_associations():
    if not _auth(request): return _unauth()
    from icc_database import get_associations
    assocs = get_associations()
    for a in assocs:
        for k, v in a.items():
            if hasattr(v, 'isoformat'): a[k] = v.isoformat()
    return jsonify({'associations': assocs})


@icc_bp.route('/api/associations/<aid>', methods=['PUT'])
@cross_origin()
def icc_update_association(aid):
    if not _auth(request): return _unauth()
    body = request.get_json(silent=True) or {}
    from icc_database import update_association_status, log_activity
    status = body.get('status','')
    update_association_status(aid, status, body.get('notes',''))
    log_activity('association_updated',
                 f"Association {aid} → {status}")
    return jsonify({'success': True})


# ── AI Writer ─────────────────────────────────────────────────────────────────

@icc_bp.route('/api/ai', methods=['POST', 'OPTIONS'])
@cross_origin()
def icc_ai():
    if request.method == 'OPTIONS': return '', 200
    if not _auth(request): return _unauth()
    if not ANTHROPIC_KEY:
        return jsonify({'error': 'AI not configured'}), 503

    body    = request.get_json(silent=True) or {}
    prompt  = body.get('prompt','').strip()
    context = body.get('context', {})

    if not prompt:
        return jsonify({'error': 'prompt required'}), 400

    # Build system prompt with full campaign context
    deadline = datetime(2026, 5, 11, tzinfo=timezone.utc)
    days     = max(0, (deadline - datetime.now(timezone.utc)).days)

    system = f"""You are the ICC AI Advisor for IDR Shield — an HHS healthcare accessibility compliance company.

CAMPAIGN CONTEXT:
- Product: $497 one-time HHS Accessibility Audit (30-page PDF, delivered within 48hrs)
- Monitoring: $49/month for weekly scans, monthly reports, verification certificate
- Deadline: May 11, 2026 — {days} days away
- Target: Healthcare organizations receiving federal funding (FQHCs, nursing homes, clinics, dental, home health)
- Website: idrshield.com/healthcare
- Stripe link: https://buy.stripe.com/14A00i4QX9so6UF11q2sM01
- Founder: Hans-Peter Nkansah, Institute of Digital Remediation

CAMPAIGN STATS:
{json.dumps(context, indent=2)}

RULES:
- Always be specific and actionable
- Never use generic marketing language
- Lead with information, not sales pitch
- Keep all copy professional, factual, urgent but not pushy
- When writing messages, make them ready to copy and send immediately
- When asked for LinkedIn posts, make them genuinely useful to healthcare compliance professionals"""

    try:
        import urllib.request as urlreq
        payload = json.dumps({
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 1000,
            'system': system,
            'messages': [{'role': 'user', 'content': prompt}]
        }).encode()
        req = urlreq.Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={
                'x-api-key':         ANTHROPIC_KEY,
                'anthropic-version': '2023-06-01',
                'Content-Type':      'application/json',
            },
            method='POST'
        )
        with urlreq.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        reply = ''.join(b.get('text','') for b in data.get('content',[])
                        if b.get('type') == 'text')
        return jsonify({'success': True, 'reply': reply})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Playbook ──────────────────────────────────────────────────────────────────

@icc_bp.route('/api/playbook', methods=['GET'])
@cross_origin()
def icc_playbook():
    if not _auth(request): return _unauth()
    deadline = datetime(2026, 5, 11, tzinfo=timezone.utc)
    days_left = max(0, (deadline - datetime.now(timezone.utc)).days)
    day_num   = 13 - days_left + 1  # which day of the campaign we're on

    playbook = [
        {'day': 1, 'title': 'Build Your List',
         'group': 'Setup',
         'tasks': ['Load 200 FQHC prospects from ICC database',
                   'Load 100 nursing home prospects',
                   'Run scanner on 50 websites',
                   'Review priority targets (score below 60)'],
         'linkedin': 'Publish anchor article: "The May 11 HHS Website Accessibility Deadline"',
         'target_group': 'All groups — setup day'},
        {'day': 2, 'title': 'First Outreach Wave',
         'group': 'FQHCs',
         'tasks': ['Send 40 LinkedIn connection requests to FQHC administrators',
                   'Use personalized scan message for priority prospects',
                   'Post LinkedIn article link in 3 healthcare compliance groups'],
         'linkedin': 'Post: "Speaking with healthcare compliance teams this week about May 11..."',
         'target_group': 'FQHCs — Executive Directors, Program Directors'},
        {'day': 3, 'title': 'Association Outreach Begins',
         'group': 'Associations',
         'tasks': ['Email NACHC with compliance alert pitch',
                   'Email your state primary care association',
                   'Email NHSA — Head Start programs',
                   'Follow up on Day 2 connections that accepted'],
         'linkedin': 'Share regulatory context post about Section 504 and patient portals',
         'target_group': 'NACHC, NHSA, State PCA'},
        {'day': 4, 'title': 'Nursing Home Wave',
         'group': 'Nursing Homes',
         'tasks': ['Send 40 LinkedIn messages to nursing home administrators',
                   'Email AHCA with compliance alert pitch',
                   'Email state nursing home association',
                   'Follow up on all pending connections'],
         'linkedin': 'Post about Section 504 vs CMS/QAPI — different enforcement mechanism',
         'target_group': 'Nursing homes — Directors of Compliance, Administrators'},
        {'day': 5, 'title': 'Attorney Pipeline',
         'group': 'Legal Channel',
         'tasks': ['Identify 20 healthcare attorneys in your state on LinkedIn',
                   'Send attorney outreach messages',
                   'Submit guest article to JD Supra',
                   'Email AHLA publications team'],
         'linkedin': 'Post: What healthcare attorneys need to know about the May 11 deadline',
         'target_group': 'Healthcare attorneys — highest leverage channel'},
        {'day': 6, 'title': 'Personalized Scan Blitz',
         'group': 'High-Value Targets',
         'tasks': ['Run scanner on 50 more healthcare websites',
                   'Send personalized scan messages to 20 worst-scoring sites',
                   'Follow up on association pitches sent Day 3-4',
                   'Follow up on 7-day non-responses'],
         'linkedin': 'Post a score breakdown — "what a 42/100 means for an FQHC"',
         'target_group': 'Priority prospects — use their real score in your message'},
        {'day': 7, 'title': 'Mid-Campaign Review',
         'group': 'All Groups',
         'tasks': ['Review ICC tracker — who has responded, who needs follow-up',
                   'Send follow-up to everyone who connected but has not replied',
                   'Post LinkedIn urgency update — 7 days remaining',
                   'Check association responses — deliver articles within 24hrs of yes'],
         'linkedin': '1 week to May 11. Post your progress and what you are seeing.',
         'target_group': 'All pending conversations'},
        {'day': 8, 'title': 'Home Health & Telehealth',
         'group': 'Home Health',
         'tasks': ['Load home health agency prospects from ICC',
                   'Send 30 LinkedIn messages to HHA administrators',
                   'Email NAHC with compliance alert pitch',
                   'Email state home care association'],
         'linkedin': 'Post: Telehealth platforms under HHS Section 504 — what is covered',
         'target_group': 'Home health agencies, telehealth providers'},
        {'day': 9, 'title': 'Dental & Specialty',
         'group': 'Dental',
         'tasks': ['LinkedIn outreach to dental practice administrators (Medicaid practices)',
                   'Email ADA and state dental association',
                   'Send final follow-up to all Day 2-3 non-responses',
                   'Convert any warm replies today'],
         'linkedin': 'Post about dental practices and Medicaid — overlooked coverage',
         'target_group': 'Dental practices, specialty clinics'},
        {'day': 10, 'title': 'Paid Amplification',
         'group': 'LinkedIn Ads',
         'tasks': ['Boost best-performing LinkedIn post — $100-200',
                   'Target: Compliance Officers, Practice Administrators, Executive Directors',
                   'All warm replies from week one — convert this week',
                   'Follow up on all association conversations'],
         'linkedin': 'Run paid boost on your highest-engagement post',
         'target_group': 'Paid — Healthcare compliance job titles'},
        {'day': 11, 'title': 'Urgency Push',
         'group': 'All Groups',
         'tasks': ['Send Day 11 urgency message to all non-converted contacts',
                   '2 days left messaging — be direct and specific',
                   'Post LinkedIn: "Last 48 hours to establish pre-deadline record"',
                   'Chase all warm association leads for quick publish'],
         'linkedin': 'Post: 2 days. Direct. Factual. No hype.',
         'target_group': 'Everyone in your pipeline who has not converted'},
        {'day': 12, 'title': 'Final Push',
         'group': 'All Groups',
         'tasks': ['Send final 48-hour close message to all warm leads',
                   'Post LinkedIn final call',
                   'Personal messages to everyone who ever replied',
                   'Monitor ICC for any new responses — convert same day'],
         'linkedin': 'Final post: May 11 deadline. Direct Stripe link.',
         'target_group': 'All warm and interested contacts'},
        {'day': 13, 'title': 'Deadline Day',
         'group': 'Close',
         'tasks': ['Post LinkedIn morning: "Today is May 11"',
                   'Respond personally to every outstanding message',
                   'Anyone who wants to activate — do it immediately',
                   'After midnight: update messaging to post-deadline positioning'],
         'linkedin': 'Post at 8am: The deadline is today. We can still deliver before midnight.',
         'target_group': 'Last chance — everyone in pipeline'},
    ]

    return jsonify({
        'playbook': playbook,
        'current_day': min(day_num, 13),
        'days_left': days_left,
    })


# ── Health check ──────────────────────────────────────────────────────────────

@icc_bp.route('/health', methods=['GET'])
def icc_health():
    return jsonify({'status': 'ICC operational',
                    'timestamp': datetime.now(timezone.utc).isoformat()})


# ── EMAIL QUEUE ROUTES ────────────────────────────────────────────────────────

@icc_bp.route('/api/queue/stats', methods=['GET'])
@cross_origin()
def icc_queue_stats():
    if not _auth(request): return _unauth()
    from icc_email_queue import get_queue_stats
    return jsonify(get_queue_stats())


@icc_bp.route('/api/queue/prospects', methods=['GET'])
@cross_origin()
def icc_queue_prospects():
    if not _auth(request): return _unauth()
    from icc_email_queue import get_pending_emails
    limit = int(request.args.get('limit', 50))
    emails = get_pending_emails(limit=limit)
    for e in emails:
        for k, v in e.items():
            if hasattr(v, 'isoformat'): e[k] = v.isoformat()
    return jsonify({'emails': emails, 'count': len(emails)})


@icc_bp.route('/api/queue/associations', methods=['GET'])
@cross_origin()
def icc_queue_associations():
    if not _auth(request): return _unauth()
    from icc_email_queue import get_pending_association_emails
    emails = get_pending_association_emails()
    for e in emails:
        for k, v in e.items():
            if hasattr(v, 'isoformat'): e[k] = v.isoformat()
    return jsonify({'emails': emails, 'count': len(emails)})


@icc_bp.route('/api/queue/approve/<int:qid>', methods=['POST'])
@cross_origin()
def icc_approve_email(qid):
    if not _auth(request): return _unauth()
    body = request.get_json(silent=True) or {}
    from icc_email_queue import approve_and_send
    result = approve_and_send(
        qid,
        to_email=body.get('to_email', ''),
        edited_body=body.get('body_text')
    )
    return jsonify(result)


@icc_bp.route('/api/queue/approve-association/<int:qid>', methods=['POST'])
@cross_origin()
def icc_approve_association(qid):
    if not _auth(request): return _unauth()
    body = request.get_json(silent=True) or {}
    from icc_email_queue import approve_and_send_association
    result = approve_and_send_association(qid, edited_body=body.get('body_text'))
    return jsonify(result)


@icc_bp.route('/api/queue/seed-associations', methods=['POST'])
@cross_origin()
def icc_seed_associations():
    if not _auth(request): return _unauth()
    from icc_email_queue import queue_association_emails
    added = queue_association_emails()
    return jsonify({'success': True, 'added': added})


@icc_bp.route('/api/queue/generate', methods=['POST'])
@cross_origin()
def icc_generate_queue():
    if not _auth(request): return _unauth()
    from icc_email_queue import generate_and_queue_from_prospects
    added = generate_and_queue_from_prospects(limit=200)
    return jsonify({'success': True, 'queued': added})


@icc_bp.route('/api/queue/reset-associations', methods=['POST'])
@cross_origin()
def icc_reset_associations():
    if not _auth(request): return _unauth()
    from icc_email_queue import reset_and_reseed_associations
    added = reset_and_reseed_associations()
    return jsonify({'success': True, 'reseeded': added})


@icc_bp.route('/api/queue/send-test', methods=['POST'])
@cross_origin()
def icc_send_test():
    if not _auth(request): return _unauth()
    from icc_email_queue import send_test_email
    result = send_test_email('idrshieldhq@gmail.com')
    return jsonify(result)


@icc_bp.route('/api/briefing/send-now', methods=['POST'])
@cross_origin()
def icc_send_briefing_now():
    if not _auth(request): return _unauth()
    try:
        from icc_worker import send_daily_briefing
        send_daily_briefing()
        return jsonify({'success': True, 'message': 'Morning briefing sent to idrshieldhq@gmail.com'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@icc_bp.route('/api/scanner/visitors', methods=['GET'])
@cross_origin()
def icc_scanner_visitors():
    if not _auth(request): return _unauth()
    from database import get_conn
    conn = get_conn()
    if not conn: return jsonify({'visitors': []})
    try:
        with conn.cursor() as cur:
            # Pull from receipts table - every external scan is a visitor
            cur.execute("""
                SELECT DISTINCT ON (domain)
                    domain,
                    score,
                    critical_count,
                    created_at as scanned_at,
                    receipt_id
                FROM receipts
                WHERE domain IS NOT NULL
                  AND domain != 'idrshield.com'
                  AND domain != 'idrshieldhq'
                ORDER BY domain, created_at DESC
                LIMIT 100
            """)
            cols = [d[0] for d in cur.description]
            rows = []
            for r in cur.fetchall():
                row = dict(zip(cols, r))
                if row.get('scanned_at'):
                    row['scanned_at'] = row['scanned_at'].isoformat()
                rows.append(row)
        # Sort by most recent
        rows.sort(key=lambda x: x.get('scanned_at',''), reverse=True)
        return jsonify({'visitors': rows, 'count': len(rows)})
    except Exception as e:
        print(f'[ICC] Scanner visitors error: {e}')
        return jsonify({'visitors': [], 'error': str(e)})
    finally:
        conn.close()


@icc_bp.route('/api/queue/resend-bounced', methods=['POST'])
@cross_origin()
def icc_resend_bounced():
    if not _auth(request): return _unauth()
    from icc_email_queue import (generate_association_emails,
                                  _send_via_sendgrid, _days_left)
    from database import get_conn

    # Corrected addresses for the 5 bounced associations
    corrections = {
        'nachc':      'mking@nachc.org',
        'mgma':       'memberservices@mgma.com',
        'ahip':       'info@ahip.org',
        'ahla':       'info@americanhealthlaw.org',
        'nahc':       'nahc@nahc.org',
    }

    sent = []
    failed = []

    assocs = generate_association_emails()
    for a in assocs:
        if a['id'] not in corrections:
            continue
        correct_email = corrections[a['id']]
        try:
            _send_via_sendgrid(
                correct_email,
                a['subject'],
                a['body'],
                salutation=a.get('salutation', 'Team'),
                institutional=True
            )
            sent.append({'name': a['name'], 'email': correct_email})

            # Log in DB
            conn = get_conn()
            if conn:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE icc_association_queue
                            SET status='sent', contact_email=%s,
                                approved_at=NOW(), sent_at=NOW()
                            WHERE assoc_id=%s AND status='pending'
                        """, (correct_email, a['id']))
                except Exception:
                    pass
                finally:
                    conn.close()

            # Send confirmation notification
            try:
                from icc_email_queue import _send_confirmation_notification
                _send_confirmation_notification(
                    a['name'], correct_email, 'Association Pitch (Resend)')
            except Exception:
                pass

        except Exception as e:
            failed.append({'name': a['name'], 'email': correct_email,
                           'error': str(e)})

    return jsonify({'success': True, 'sent': sent, 'failed': failed,
                    'sent_count': len(sent)})
