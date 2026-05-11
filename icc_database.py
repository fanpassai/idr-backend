"""
ICC — icc_database.py  v2.0
Complete database layer for the IDR Command Center.

WHAT'S NEW vs v1:
- 8 tables (was 5): adds icc_contacts, icc_email_events,
  icc_content, icc_intelligence, icc_scan_history, icc_media
- startup_seed() — seeds prospects at app boot, not browser open
- Brand DNA constants used by content engine and image generator
- Transparency Scorecard maturity levels per prospect
- Government lane support (org_lane field)
- contact_email stored per prospect — typed once, never again
"""

import os
import json
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone


# ── Brand DNA — single source of truth for all visual output ─────────────────

BRAND = {
    'colors': {
        'deep_navy':   '#0B1220',
        'midnight':    '#111A2E',
        'gold':        '#C8A75A',
        'stone':       '#E6E2DA',
        'slate':       '#6B7280',
        'cream':       '#F8F6F1',
        'white':       '#FFFFFF',
        'red_fail':    '#DC2626',
        'amber_warn':  '#D97706',
        'green_pass':  '#059669',
        'red_critical':'#B91C1C',
    },
    'fonts': {
        'primary':   'Cinzel',        # headlines, authority moments
        'secondary': 'Suisse Int\'l', # body, UI, data
        'fallback':  'Georgia, serif',
    },
    'tagline': 'Digital Access. Trust. Compliance.',
    'positioning': 'The Registry Is Your Defense.',
    'institution': 'Institute of Digital Remediation',
    'product': 'IDR Shield',
    'est': '2026',
    'stripe_link': 'https://buy.stripe.com/14A00i4QX9so6UF11q2sM01',
    'verify_base': 'https://idrshield.com/verify',   # placeholder until idrtrust.org acquired
    'scan_page':  'https://idrshield.com/healthscan',
}

# Transparency Scorecard maturity levels — visible on every prospect card
MATURITY_LEVELS = [
    {'level': 'ABSENT',     'color': '#6B7280', 'description': 'No accessibility statement or documentation found.'},
    {'level': 'REACTIVE',   'color': '#D97706', 'description': 'Some efforts taken but no documented record.'},
    {'level': 'DOCUMENTED', 'color': '#2563EB', 'description': 'Remediation efforts documented with internal records.'},
    {'level': 'VERIFIED',   'color': '#7C3AED', 'description': 'Independent verification of remediation efforts.'},
    {'level': 'ACTIVE',     'color': '#059669', 'description': 'Continuous monitoring and public registry verification active.'},
]

# Visual content directions — used by content engine to pick style per post type
VISUAL_DIRECTIONS = {
    'institutional_noir': {
        'bg': '#0B1220', 'text': '#F8F6F1', 'accent': '#C8A75A',
        'use_for': ['enforcement', 'scan_reveal', 'field_report', 'warnings'],
    },
    'archival_ivory': {
        'bg': '#F8F6F1', 'text': '#0B1220', 'accent': '#C8A75A',
        'use_for': ['certifications', 'reports', 'formal_notices'],
    },
    'technical_precision': {
        'bg': '#FFFFFF', 'text': '#111A2E', 'accent': '#2563EB',
        'use_for': ['scan_data', 'dashboards', 'evidence', 'verification'],
    },
    'monumental_stone': {
        'bg': '#2C2C2C', 'text': '#F8F6F1', 'accent': '#C8A75A',
        'use_for': ['brand_statements', 'institutional_messaging', 'hero'],
    },
    'executive_minimal': {
        'bg': '#FAFAFA', 'text': '#111A2E', 'accent': '#C8A75A',
        'use_for': ['insights', 'thought_leadership', 'quotes'],
    },
}

# Post-deadline enforcement language — used in all outreach and content
ENFORCEMENT_COPY = {
    'healthcare': {
        'deadline_passed': 'The HHS Section 504 digital accessibility deadline passed on May 11, 2026.',
        'status_absent':   'Registry Status: ABSENT. Your organization is currently in the enforcement window.',
        'urgency':         'Every day without a documented record increases your exposure.',
        'authority':       'HHS 89 FR 40066 — WCAG 2.1 Level AA — 45 CFR Part 84',
        'cta':             'Establish your documented record. $497. 48-hour delivery.',
    },
    'government': {
        'deadline_passed': 'The ADA Title II digital accessibility deadline for government entities passed on April 24, 2026.',
        'status_absent':   'Registry Status: ABSENT. Your organization is currently exposed to constituent complaints.',
        'urgency':         'DOJ enforcement is active. Every day without documentation is additional liability.',
        'authority':       'ADA Title II — DOJ April 2024 Final Rule — WCAG 2.1 Level AA',
        'cta':             'Establish your documented record. $497. 48-hour delivery.',
    },
    'education': {
        'deadline_passed': 'The Section 508 digital accessibility requirement applies to your institution now.',
        'status_absent':   'Registry Status: ABSENT. Student and parent complaints can trigger DOE investigation.',
        'urgency':         'Document your compliance posture before the academic year begins.',
        'authority':       'Section 508 — DOE Enforcement — WCAG 2.1 Level AA',
        'cta':             'Establish your documented record. $497. 48-hour delivery.',
    },
}


# ── DB connection ─────────────────────────────────────────────────────────────

def get_conn():
    from database import get_conn as _get
    return _get()


# ── Full schema — all 8 ICC tables ───────────────────────────────────────────

ICC_SCHEMA = """

-- CORE: Every healthcare/gov org we know about
CREATE TABLE IF NOT EXISTS icc_prospects (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    org_type        TEXT NOT NULL DEFAULT 'fqhc',
    org_lane        TEXT NOT NULL DEFAULT 'healthcare',
    address         TEXT DEFAULT '',
    city            TEXT DEFAULT '',
    state           TEXT DEFAULT '',
    zip             TEXT DEFAULT '',
    phone           TEXT DEFAULT '',
    website         TEXT DEFAULT '',
    idr_score       INTEGER,
    critical_count  INTEGER,
    total_issues    INTEGER DEFAULT 0,
    scanned         BOOLEAN DEFAULT FALSE,
    scanned_at      TIMESTAMPTZ,
    priority        BOOLEAN DEFAULT FALSE,
    maturity_level  TEXT DEFAULT 'ABSENT',
    outreach_msg    TEXT,
    contact_email   TEXT DEFAULT '',
    source          TEXT DEFAULT 'seed',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_icc_prospects_state    ON icc_prospects(state);
CREATE INDEX IF NOT EXISTS idx_icc_prospects_type     ON icc_prospects(org_type);
CREATE INDEX IF NOT EXISTS idx_icc_prospects_lane     ON icc_prospects(org_lane);
CREATE INDEX IF NOT EXISTS idx_icc_prospects_priority ON icc_prospects(priority);
CREATE INDEX IF NOT EXISTS idx_icc_prospects_score    ON icc_prospects(idr_score);
CREATE INDEX IF NOT EXISTS idx_icc_prospects_scanned  ON icc_prospects(scanned);

-- CONTACTS: Named humans at organizations — typed once, stored forever
CREATE TABLE IF NOT EXISTS icc_contacts (
    id              SERIAL PRIMARY KEY,
    prospect_id     TEXT REFERENCES icc_prospects(id) ON DELETE CASCADE,
    name            TEXT,
    title           TEXT,
    email           TEXT,
    phone           TEXT,
    linkedin_url    TEXT,
    last_contacted  TIMESTAMPTZ,
    notes           TEXT,
    next_action     TEXT,
    next_action_date DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_icc_contacts_prospect ON icc_contacts(prospect_id);

-- OUTREACH: Every contact attempt with full lifecycle
CREATE TABLE IF NOT EXISTS icc_outreach (
    id              SERIAL PRIMARY KEY,
    prospect_id     TEXT REFERENCES icc_prospects(id),
    prospect_name   TEXT,
    contact_email   TEXT,
    contact_name    TEXT,
    contact_title   TEXT,
    message_type    TEXT DEFAULT 'email',
    subject         TEXT,
    status          TEXT DEFAULT 'sent',
    revenue         INTEGER DEFAULT 0,
    notes           TEXT,
    sent_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_icc_outreach_status   ON icc_outreach(status);
CREATE INDEX IF NOT EXISTS idx_icc_outreach_prospect ON icc_outreach(prospect_id);
CREATE INDEX IF NOT EXISTS idx_icc_outreach_sent     ON icc_outreach(sent_at DESC);

-- EMAIL EVENTS: Every SendGrid event — opens, clicks, bounces
CREATE TABLE IF NOT EXISTS icc_email_events (
    id              SERIAL PRIMARY KEY,
    outreach_id     INTEGER REFERENCES icc_outreach(id),
    prospect_id     TEXT,
    event_type      TEXT NOT NULL,
    email_address   TEXT,
    timestamp_utc   TIMESTAMPTZ DEFAULT NOW(),
    raw_payload     JSONB
);
CREATE INDEX IF NOT EXISTS idx_icc_events_prospect  ON icc_email_events(prospect_id);
CREATE INDEX IF NOT EXISTS idx_icc_events_type      ON icc_email_events(event_type);
CREATE INDEX IF NOT EXISTS idx_icc_events_time      ON icc_email_events(timestamp_utc DESC);

-- SCAN HISTORY: Every scan ever run — not just latest. Enables trend analysis.
CREATE TABLE IF NOT EXISTS icc_scan_history (
    id              SERIAL PRIMARY KEY,
    prospect_id     TEXT REFERENCES icc_prospects(id),
    domain          TEXT,
    score           INTEGER,
    critical_count  INTEGER,
    total_issues    INTEGER,
    scan_source     TEXT DEFAULT 'manual',
    scanned_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_icc_scan_hist_prospect ON icc_scan_history(prospect_id);
CREATE INDEX IF NOT EXISTS idx_icc_scan_hist_time     ON icc_scan_history(scanned_at DESC);

-- CONTENT: Generated posts, carousels, images — approval workflow
CREATE TABLE IF NOT EXISTS icc_content (
    id              SERIAL PRIMARY KEY,
    content_type    TEXT NOT NULL,
    visual_direction TEXT,
    title           TEXT,
    body_text       TEXT,
    caption         TEXT,
    hashtags        TEXT,
    first_comment   TEXT,
    image_path      TEXT,
    pdf_path        TEXT,
    platform        TEXT DEFAULT 'linkedin',
    status          TEXT DEFAULT 'draft',
    prospect_id     TEXT,
    scan_score      INTEGER,
    publish_date    DATE,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_icc_content_status ON icc_content(status);
CREATE INDEX IF NOT EXISTS idx_icc_content_date   ON icc_content(publish_date);

-- INTELLIGENCE: News, regulatory updates, lawsuit filings
CREATE TABLE IF NOT EXISTS icc_intelligence (
    id              SERIAL PRIMARY KEY,
    intel_type      TEXT NOT NULL,
    source          TEXT,
    headline        TEXT,
    summary         TEXT,
    url             TEXT,
    relevance_score INTEGER DEFAULT 50,
    used_in_briefing BOOLEAN DEFAULT FALSE,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_icc_intel_type ON icc_intelligence(intel_type);
CREATE INDEX IF NOT EXISTS idx_icc_intel_time ON icc_intelligence(created_at DESC);

-- MEDIA: Auto-generated images and PDFs
CREATE TABLE IF NOT EXISTS icc_media (
    id              SERIAL PRIMARY KEY,
    media_type      TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    prospect_id     TEXT,
    content_id      INTEGER,
    visual_direction TEXT,
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_icc_media_prospect ON icc_media(prospect_id);

-- ASSOCIATIONS: The 10 mouthpiece channels
CREATE TABLE IF NOT EXISTS icc_associations (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    serves          TEXT,
    member_count    TEXT,
    website         TEXT,
    contact_name    TEXT,
    contact_title   TEXT,
    contact_email   TEXT,
    status          TEXT DEFAULT 'not_contacted',
    pitch_sent_at   TIMESTAMPTZ,
    opened_at       TIMESTAMPTZ,
    replied_at      TIMESTAMPTZ,
    notes           TEXT,
    priority_order  INTEGER DEFAULT 99,
    org_lane        TEXT DEFAULT 'healthcare',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ACTIVITY: Everything ICC does — feeds briefing and radar
CREATE TABLE IF NOT EXISTS icc_activity (
    id              SERIAL PRIMARY KEY,
    event_type      TEXT NOT NULL,
    detail          TEXT,
    count           INTEGER DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_icc_activity_type ON icc_activity(event_type);
CREATE INDEX IF NOT EXISTS idx_icc_activity_time ON icc_activity(created_at DESC);

-- SETTINGS
CREATE TABLE IF NOT EXISTS icc_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
"""


def init_icc_db() -> bool:
    conn = get_conn()
    if not conn:
        print('[ICC_DB] No database connection')
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(ICC_SCHEMA)
        print('[ICC_DB] Schema v2.0 initialized — all 8 tables ready')
        _seed_associations()
        return True
    except Exception as e:
        print(f'[ICC_DB] Schema error: {e}')
        return False
    finally:
        conn.close()


# ── Startup seed — runs at app boot, not browser open ────────────────────────

# Priority states — seeded immediately so the DB has data before anyone opens ICC
SEED_PROSPECTS = {
    'FL': [
        {'id':'FL-FQHC-001','name':'Tampa Family Health Centers','org_type':'fqhc','city':'Tampa','state':'FL','zip':'33604','phone':'(813) 866-6300','website':'tampafamilyhc.com'},
        {'id':'FL-FQHC-002','name':'Neighborhood Health Source','org_type':'fqhc','city':'Clearwater','state':'FL','zip':'33756','phone':'(727) 442-9041','website':'nhshealth.org'},
        {'id':'FL-FQHC-003','name':'Bayfront Health St. Petersburg','org_type':'fqhc','city':'St. Petersburg','state':'FL','zip':'33701','phone':'(727) 823-1234','website':'bayfronthealth.com'},
        {'id':'FL-FQHC-004','name':'Orange Blossom Family Health','org_type':'fqhc','city':'Orlando','state':'FL','zip':'32805','phone':'(407) 905-8827','website':'orangeblossomfamilyhealth.com'},
        {'id':'FL-FQHC-005','name':'Community Health of South Florida','org_type':'fqhc','city':'Miami','state':'FL','zip':'33176','phone':'(305) 252-4820','website':'chisouthfl.org'},
        {'id':'FL-FQHC-006','name':'Family Health Centers of SW Florida','org_type':'fqhc','city':'Fort Myers','state':'FL','zip':'33901','phone':'(239) 334-0404','website':'fhcswfl.org'},
        {'id':'FL-FQHC-007','name':'North Florida Medical Centers','org_type':'fqhc','city':'Live Oak','state':'FL','zip':'32064','phone':'(386) 330-2300','website':'nfmc.us'},
        {'id':'FL-FQHC-008','name':'Marion County Health Dept','org_type':'fqhc','city':'Ocala','state':'FL','zip':'34471','phone':'(352) 629-0137','website':'marioncountyfl.org/health'},
        {'id':'FL-FQHC-009','name':'C.L. Brumback Primary Care','org_type':'fqhc','city':'West Palm Beach','state':'FL','zip':'33407','phone':'(561) 840-4500','website':'clbrumback.org'},
        {'id':'FL-FQHC-010','name':'Osceola Community Health Services','org_type':'fqhc','city':'Kissimmee','state':'FL','zip':'34741','phone':'(407) 846-4600','website':'ochs.org'},
        {'id':'FL-FQHC-011','name':'Suncoast Community Health Centers','org_type':'fqhc','city':'Ruskin','state':'FL','zip':'33570','phone':'(813) 672-4000','website':'suncoastchc.org'},
        {'id':'FL-FQHC-012','name':'UF Health Family Medicine','org_type':'fqhc','city':'Jacksonville','state':'FL','zip':'32209','phone':'(904) 244-4000','website':'ufhealth.org'},
        {'id':'FL-FQHC-013','name':'SunCoast Community Health Center','org_type':'fqhc','city':'Brooksville','state':'FL','zip':'34601','phone':'(352) 796-0900','website':'suncoastchc.org'},
        {'id':'FL-FQHC-014','name':'I.M. Sulzbacher Center','org_type':'fqhc','city':'Jacksonville','state':'FL','zip':'32206','phone':'(904) 695-9032','website':'sulzbacher.org'},
        {'id':'FL-FQHC-015','name':'Bond Community Health Center','org_type':'fqhc','city':'Tallahassee','state':'FL','zip':'32304','phone':'(850) 576-4073','website':'bondchc.com'},
        {'id':'FL-FQHC-016','name':'Sarasota Memorial Hospital Primary Care','org_type':'fqhc','city':'Sarasota','state':'FL','zip':'34239','phone':'(941) 917-9000','website':'smh.com'},
        {'id':'FL-FQHC-017','name':'Shands Jacksonville Medical Center','org_type':'fqhc','city':'Jacksonville','state':'FL','zip':'32209','phone':'(904) 244-0411','website':'ufhealth.org/jax'},
        {'id':'FL-FQHC-018','name':'Health Department Broward','org_type':'fqhc','city':'Fort Lauderdale','state':'FL','zip':'33311','phone':'(954) 467-4700','website':'broward.org/health'},
        {'id':'FL-FQHC-019','name':'Lakeland Regional Health','org_type':'fqhc','city':'Lakeland','state':'FL','zip':'33805','phone':'(863) 687-1100','website':'mylrh.org'},
        {'id':'FL-FQHC-020','name':'Cape Coral Hospital','org_type':'fqhc','city':'Cape Coral','state':'FL','zip':'33990','phone':'(239) 424-2000','website':'leehealth.org'},
    ],
    'TX': [
        {'id':'TX-FQHC-001','name':'People\'s Community Clinic','org_type':'fqhc','city':'Austin','state':'TX','zip':'78751','phone':'(512) 478-4939','website':'austinpcc.org'},
        {'id':'TX-FQHC-002','name':'Legacy Community Health','org_type':'fqhc','city':'Houston','state':'TX','zip':'77006','phone':'(832) 548-5000','website':'legacycommunityhealth.org'},
        {'id':'TX-FQHC-003','name':'CommuniCare Health Centers','org_type':'fqhc','city':'San Antonio','state':'TX','zip':'78207','phone':'(210) 233-3300','website':'communicaresa.org'},
        {'id':'TX-FQHC-004','name':'Oak Cliff Community Health','org_type':'fqhc','city':'Dallas','state':'TX','zip':'75208','phone':'(214) 941-9500','website':'oakcliff-fhc.org'},
        {'id':'TX-FQHC-005','name':'Central Texas Community Health Centers','org_type':'fqhc','city':'Temple','state':'TX','zip':'76501','phone':'(254) 778-4161','website':'ctchcs.org'},
        {'id':'TX-FQHC-006','name':'El Paso Community Health Center','org_type':'fqhc','city':'El Paso','state':'TX','zip':'79901','phone':'(915) 532-2000','website':'epchc.org'},
        {'id':'TX-FQHC-007','name':'Su Clinica Familiar','org_type':'fqhc','city':'Harlingen','state':'TX','zip':'78550','phone':'(956) 423-0130','website':'suclinica.com'},
        {'id':'TX-FQHC-008','name':'Lone Star Circle of Care','org_type':'fqhc','city':'Georgetown','state':'TX','zip':'78626','phone':'(512) 863-8322','website':'lscctx.org'},
        {'id':'TX-FQHC-009','name':'Lubbock Health Department','org_type':'fqhc','city':'Lubbock','state':'TX','zip':'79401','phone':'(806) 775-2910','website':'mylubbock.us/health'},
        {'id':'TX-FQHC-010','name':'Nueces County Community Health','org_type':'fqhc','city':'Corpus Christi','state':'TX','zip':'78401','phone':'(361) 826-7205','website':'nuecescounty.net'},
    ],
    'GA': [
        {'id':'GA-FQHC-001','name':'Grady Health System','org_type':'fqhc','city':'Atlanta','state':'GA','zip':'30303','phone':'(404) 616-1000','website':'gradyhealth.org'},
        {'id':'GA-FQHC-002','name':'Good Samaritan Health Center','org_type':'fqhc','city':'Atlanta','state':'GA','zip':'30303','phone':'(404) 523-6571','website':'gshcofatlanta.org'},
        {'id':'GA-FQHC-003','name':'Federally Qualified Health Center Savannah','org_type':'fqhc','city':'Savannah','state':'GA','zip':'31401','phone':'(912) 629-0900','website':'savannah-fqhc.org'},
        {'id':'GA-FQHC-004','name':'Albany Area Primary Health Care','org_type':'fqhc','city':'Albany','state':'GA','zip':'31701','phone':'(229) 446-8600','website':'aaphc.org'},
        {'id':'GA-FQHC-005','name':'Phoebe Putney Memorial Hospital','org_type':'fqhc','city':'Albany','state':'GA','zip':'31701','phone':'(229) 312-1000','website':'phoebehealth.com'},
    ],
    'NY': [
        {'id':'NY-FQHC-001','name':'Urban Health Plan','org_type':'fqhc','city':'Bronx','state':'NY','zip':'10456','phone':'(718) 589-2440','website':'urbanhealthplan.org'},
        {'id':'NY-FQHC-002','name':'Community Healthcare Network','org_type':'fqhc','city':'New York','state':'NY','zip':'10013','phone':'(212) 366-4500','website':'chnnyc.org'},
        {'id':'NY-FQHC-003','name':'Bedford Stuyvesant Family Health Center','org_type':'fqhc','city':'Brooklyn','state':'NY','zip':'11216','phone':'(718) 636-4500','website':'bsfhc.org'},
        {'id':'NY-FQHC-004','name':'Montefiore Medical Center','org_type':'fqhc','city':'Bronx','state':'NY','zip':'10467','phone':'(718) 920-4321','website':'montefiore.org'},
        {'id':'NY-FQHC-005','name':'Ryan Health','org_type':'fqhc','city':'New York','state':'NY','zip':'10025','phone':'(212) 749-1820','website':'ryanhealth.org'},
    ],
    'NC': [
        {'id':'NC-FQHC-001','name':'Piedmont Health Services','org_type':'fqhc','city':'Carrboro','state':'NC','zip':'27510','phone':'(919) 968-4011','website':'piedmonthealth.org'},
        {'id':'NC-FQHC-002','name':'Buncombe County Health Services','org_type':'fqhc','city':'Asheville','state':'NC','zip':'28801','phone':'(828) 250-5000','website':'buncombehealth.org'},
        {'id':'NC-FQHC-003','name':'Cabarrus Health Alliance','org_type':'fqhc','city':'Concord','state':'NC','zip':'28025','phone':'(704) 920-1200','website':'cabarrushealth.org'},
        {'id':'NC-FQHC-004','name':'Columbus County Health Department','org_type':'fqhc','city':'Whiteville','state':'NC','zip':'28472','phone':'(910) 640-6615','website':'columbuscounty.gov/health'},
        {'id':'NC-FQHC-005','name':'Mountain Area Health Education Center','org_type':'fqhc','city':'Asheville','state':'NC','zip':'28801','phone':'(828) 257-4400','website':'mahec.net'},
    ],
    'CA': [
        {'id':'CA-FQHC-001','name':'Venice Family Clinic','org_type':'fqhc','city':'Los Angeles','state':'CA','zip':'90291','phone':'(310) 392-8630','website':'venicefamilyclinic.org'},
        {'id':'CA-FQHC-002','name':'Northeast Community Clinic','org_type':'fqhc','city':'San Diego','state':'CA','zip':'92113','phone':'(619) 434-5000','website':'northeastcommunityclinic.org'},
        {'id':'CA-FQHC-003','name':'Central Valley Health Network','org_type':'fqhc','city':'Fresno','state':'CA','zip':'93721','phone':'(559) 228-1011','website':'cvhn.org'},
        {'id':'CA-FQHC-004','name':'Asian Health Services','org_type':'fqhc','city':'Oakland','state':'CA','zip':'94607','phone':'(510) 986-6800','website':'asianhealthservices.org'},
        {'id':'CA-FQHC-005','name':'Clinica de Salud del Valle de Salinas','org_type':'fqhc','city':'Salinas','state':'CA','zip':'93901','phone':'(831) 422-7696','website':'clinicasalinas.com'},
    ],
    'OH': [
        {'id':'OH-FQHC-001','name':'Columbus Public Health','org_type':'fqhc','city':'Columbus','state':'OH','zip':'43215','phone':'(614) 645-7417','website':'publichealth.columbus.gov'},
        {'id':'OH-FQHC-002','name':'Care Source','org_type':'fqhc','city':'Dayton','state':'OH','zip':'45402','phone':'(937) 531-2000','website':'caresource.com'},
        {'id':'OH-FQHC-003','name':'MetroHealth System','org_type':'fqhc','city':'Cleveland','state':'OH','zip':'44109','phone':'(216) 778-7800','website':'metrohealth.org'},
        {'id':'OH-FQHC-004','name':'University Hospitals Health System','org_type':'fqhc','city':'Cleveland','state':'OH','zip':'44106','phone':'(216) 844-1000','website':'uhhospitals.org'},
        {'id':'OH-FQHC-005','name':'Nationwide Children\'s Hospital','org_type':'fqhc','city':'Columbus','state':'OH','zip':'43205','phone':'(614) 722-2000','website':'nationwidechildrens.org'},
    ],
    'PA': [
        {'id':'PA-FQHC-001','name':'Philadelphia Department of Public Health','org_type':'fqhc','city':'Philadelphia','state':'PA','zip':'19107','phone':'(215) 686-5000','website':'phila.gov/health'},
        {'id':'PA-FQHC-002','name':'Pittsburgh Mercy Health System','org_type':'fqhc','city':'Pittsburgh','state':'PA','zip':'15219','phone':'(412) 232-8111','website':'pittsburghmercy.org'},
        {'id':'PA-FQHC-003','name':'Lehigh Valley Health Network','org_type':'fqhc','city':'Allentown','state':'PA','zip':'18103','phone':'(610) 402-2273','website':'lvhn.org'},
        {'id':'PA-FQHC-004','name':'PinnacleHealth System','org_type':'fqhc','city':'Harrisburg','state':'PA','zip':'17104','phone':'(717) 782-5000','website':'pinnaclehealth.org'},
        {'id':'PA-FQHC-005','name':'Geisinger Health System','org_type':'fqhc','city':'Danville','state':'PA','zip':'17822','phone':'(570) 271-6211','website':'geisinger.org'},
    ],
}

# Government lane seed — ADA Title II deadline passed April 24, 2026
SEED_GOVERNMENT = [
    {'id':'GOV-FL-001','name':'City of Orlando','org_type':'city','org_lane':'government','city':'Orlando','state':'FL','zip':'32801','phone':'(407) 246-2121','website':'orlando.gov'},
    {'id':'GOV-FL-002','name':'Miami-Dade County','org_type':'county','org_lane':'government','city':'Miami','state':'FL','zip':'33128','phone':'(305) 375-5311','website':'miamidade.gov'},
    {'id':'GOV-FL-003','name':'Broward County Government','org_type':'county','org_lane':'government','city':'Fort Lauderdale','state':'FL','zip':'33301','phone':'(954) 357-7000','website':'broward.org'},
    {'id':'GOV-FL-004','name':'City of Tampa','org_type':'city','org_lane':'government','city':'Tampa','state':'FL','zip':'33602','phone':'(813) 274-8211','website':'tampa.gov'},
    {'id':'GOV-FL-005','name':'Palm Beach County','org_type':'county','org_lane':'government','city':'West Palm Beach','state':'FL','zip':'33401','phone':'(561) 355-2001','website':'discover.pbcgov.org'},
    {'id':'GOV-TX-001','name':'City of Houston','org_type':'city','org_lane':'government','city':'Houston','state':'TX','zip':'77002','phone':'(832) 393-0000','website':'houstontx.gov'},
    {'id':'GOV-TX-002','name':'Dallas County','org_type':'county','org_lane':'government','city':'Dallas','state':'TX','zip':'75202','phone':'(214) 653-7011','website':'dallascounty.org'},
    {'id':'GOV-GA-001','name':'City of Atlanta','org_type':'city','org_lane':'government','city':'Atlanta','state':'GA','zip':'30303','phone':'(404) 330-6000','website':'atlantaga.gov'},
    {'id':'GOV-NY-001','name':'New York City Government','org_type':'city','org_lane':'government','city':'New York','state':'NY','zip':'10007','phone':'(212) 639-9675','website':'nyc.gov'},
    {'id':'GOV-CA-001','name':'City of Los Angeles','org_type':'city','org_lane':'government','city':'Los Angeles','state':'CA','zip':'90012','phone':'(213) 978-0600','website':'lacity.org'},
]


def startup_seed() -> int:
    """
    Runs at app startup — not when browser opens.
    Seeds all prospects from all states into icc_prospects DB.
    Uses bulk upsert so re-running is safe — never duplicates.
    Returns total prospects seeded.
    """
    all_prospects = []

    # Healthcare lane — all 8 states
    for state, prospects in SEED_PROSPECTS.items():
        for p in prospects:
            all_prospects.append({
                **p,
                'org_lane': 'healthcare',
                'source': 'seed',
            })

    # Government lane
    for p in SEED_GOVERNMENT:
        all_prospects.append({**p, 'source': 'seed'})

    total = bulk_upsert_prospects(all_prospects)
    print(f'[ICC_DB] Startup seed complete — {total}/{len(all_prospects)} prospects in database')
    return total


# ── Association seed data ─────────────────────────────────────────────────────

ASSOCIATIONS = [
    {
        'id': 'nachc', 'org_lane': 'healthcare',
        'name': 'NACHC — National Association of Community Health Centers',
        'serves': 'Every FQHC in America — 1,400+ health centers',
        'member_count': '1,400+', 'website': 'nachc.org',
        'contact_name': 'Policy and Advocacy Team',
        'contact_title': 'Director of Policy',
        'contact_email': 'advocacy@nachc.org', 'priority_order': 1,
    },
    {
        'id': 'nhsa', 'org_lane': 'healthcare',
        'name': 'NHSA — National Head Start Association',
        'serves': 'Every Head Start program director in America',
        'member_count': '2,700+', 'website': 'nhsa.org',
        'contact_name': 'Communications Team',
        'contact_title': 'Director of Communications',
        'contact_email': 'info@nhsa.org', 'priority_order': 2,
    },
    {
        'id': 'ahca', 'org_lane': 'healthcare',
        'name': 'AHCA — American Health Care Association',
        'serves': 'Nursing homes and post-acute care facilities',
        'member_count': '14,000+', 'website': 'ahcancal.org',
        'contact_name': 'Government Affairs Team',
        'contact_title': 'VP of Government Affairs',
        'contact_email': 'info@ahca.org', 'priority_order': 3,
    },
    {
        'id': 'mgma', 'org_lane': 'healthcare',
        'name': 'MGMA — Medical Group Management Association',
        'serves': 'Physician practice executives and administrators',
        'member_count': '350,000+', 'website': 'mgma.com',
        'contact_name': 'Advocacy Team',
        'contact_title': 'Director of Government Affairs',
        'contact_email': 'advocacy@mgma.org', 'priority_order': 4,
    },
    {
        'id': 'nahc', 'org_lane': 'healthcare',
        'name': 'NAHC — National Association for Home Care and Hospice',
        'serves': 'Home health agencies and hospices',
        'member_count': '6,000+', 'website': 'nahc.org',
        'contact_name': 'Communications Team',
        'contact_title': 'Director of Communications',
        'contact_email': 'info@nahc.org', 'priority_order': 5,
    },
    {
        'id': 'leadingage', 'org_lane': 'healthcare',
        'name': 'LeadingAge',
        'serves': 'Non-profit aging services — nursing homes, assisted living, hospice',
        'member_count': '5,000+', 'website': 'leadingage.org',
        'contact_name': 'Policy Team',
        'contact_title': 'VP of Policy',
        'contact_email': 'info@leadingage.org', 'priority_order': 6,
    },
    {
        'id': 'ahla', 'org_lane': 'healthcare',
        'name': 'AHLA — American Health Law Association',
        'serves': 'Healthcare attorneys who advise every covered organization',
        'member_count': '13,000+', 'website': 'americanhealthlaw.org',
        'contact_name': 'Publications Team',
        'contact_title': 'Director of Publications',
        'contact_email': 'info@americanhealthlaw.org', 'priority_order': 7,
    },
    {
        'id': 'ada_dental', 'org_lane': 'healthcare',
        'name': 'ADA — American Dental Association',
        'serves': 'Dentists and dental practices across America',
        'member_count': '161,000+', 'website': 'ada.org',
        'contact_name': 'Practice Resources Team',
        'contact_title': 'Director of Practice Success',
        'contact_email': 'memberservice@ada.org', 'priority_order': 8,
    },
    {
        'id': 'ahip', 'org_lane': 'healthcare',
        'name': "AHIP — America's Health Insurance Plans",
        'serves': 'Health insurers and managed care organizations',
        'member_count': '1,300+', 'website': 'ahip.org',
        'contact_name': 'Policy Team',
        'contact_title': 'VP of Policy',
        'contact_email': 'info@ahip.org', 'priority_order': 9,
    },
    {
        'id': 'jdsupra', 'org_lane': 'healthcare',
        'name': 'JD Supra — Healthcare Legal Publications',
        'serves': 'Healthcare attorneys and in-house counsel',
        'member_count': '250,000+ readers', 'website': 'jdsupra.com',
        'contact_name': 'Content Team',
        'contact_title': 'Editor',
        'contact_email': 'editorial@jdsupra.com', 'priority_order': 10,
    },
    # Government lane associations
    {
        'id': 'icma', 'org_lane': 'government',
        'name': 'ICMA — International City/County Management Association',
        'serves': 'City and county managers across the US',
        'member_count': '10,000+', 'website': 'icma.org',
        'contact_name': 'Communications Team',
        'contact_title': 'Director of Communications',
        'contact_email': 'icma@icma.org', 'priority_order': 11,
    },
    {
        'id': 'naco', 'org_lane': 'government',
        'name': 'NACo — National Association of Counties',
        'serves': 'County governments across the US',
        'member_count': '3,000+', 'website': 'naco.org',
        'contact_name': 'Communications Team',
        'contact_title': 'Director of Communications',
        'contact_email': 'info@naco.org', 'priority_order': 12,
    },
]


def _seed_associations():
    conn = get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            for a in ASSOCIATIONS:
                cur.execute("""
                    INSERT INTO icc_associations
                        (id, name, serves, member_count, website,
                         contact_name, contact_title, contact_email,
                         priority_order, org_lane)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO NOTHING
                """, (
                    a['id'], a['name'], a['serves'], a['member_count'],
                    a['website'], a['contact_name'], a['contact_title'],
                    a['contact_email'], a['priority_order'],
                    a.get('org_lane', 'healthcare'),
                ))
        print(f'[ICC_DB] Seeded {len(ASSOCIATIONS)} associations')
    except Exception as e:
        print(f'[ICC_DB] Association seed error: {e}')
    finally:
        conn.close()


# ── Prospect operations ───────────────────────────────────────────────────────

def upsert_prospect(p: dict) -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO icc_prospects
                    (id, name, org_type, org_lane, address, city, state,
                     zip, phone, website, source, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name,
                    phone=COALESCE(NULLIF(EXCLUDED.phone,''), icc_prospects.phone),
                    website=COALESCE(NULLIF(EXCLUDED.website,''), icc_prospects.website),
                    updated_at=NOW()
            """, (
                p['id'], p['name'],
                p.get('org_type', 'fqhc'),
                p.get('org_lane', 'healthcare'),
                p.get('address', ''), p.get('city', ''),
                p.get('state', ''), p.get('zip', ''),
                p.get('phone', ''), p.get('website', ''),
                p.get('source', 'api'),
            ))
        return True
    except Exception as e:
        print(f'[ICC_DB] upsert_prospect error: {e}')
        return False
    finally:
        conn.close()


def bulk_upsert_prospects(prospects: list) -> int:
    if not prospects:
        return 0
    conn = get_conn()
    if not conn:
        return 0
    saved = 0
    try:
        with conn.cursor() as cur:
            for p in prospects:
                try:
                    cur.execute("""
                        INSERT INTO icc_prospects
                            (id, name, org_type, org_lane, address, city, state,
                             zip, phone, website, source, updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
                        ON CONFLICT (id) DO UPDATE SET
                            name=EXCLUDED.name,
                            phone=COALESCE(NULLIF(EXCLUDED.phone,''), icc_prospects.phone),
                            website=COALESCE(NULLIF(EXCLUDED.website,''), icc_prospects.website),
                            updated_at=NOW()
                    """, (
                        p['id'], p['name'],
                        p.get('org_type', 'fqhc'),
                        p.get('org_lane', 'healthcare'),
                        p.get('address', ''), p.get('city', ''),
                        p.get('state', ''), p.get('zip', ''),
                        p.get('phone', ''), p.get('website', ''),
                        p.get('source', 'seed'),
                    ))
                    saved += 1
                except Exception:
                    pass
        print(f'[ICC_DB] bulk_upsert: {saved}/{len(prospects)} saved')
        return saved
    except Exception as e:
        print(f'[ICC_DB] bulk_upsert error: {e}')
        return 0
    finally:
        conn.close()


def save_scan_result(prospect_id: str, website: str, name: str,
                     score: int, criticals: int,
                     total_issues: int = 0) -> bool:
    """
    Saves scan result permanently.
    1. Ensures prospect row exists (upsert).
    2. Updates score fields.
    3. Sets maturity level based on score and registry status.
    4. Writes to icc_scan_history for trend analysis.
    """
    maturity = _calc_maturity(score)
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            # Guarantee the row exists
            cur.execute("""
                INSERT INTO icc_prospects
                    (id, name, org_type, website, source, updated_at)
                VALUES (%s,%s,'fqhc',%s,'browser',NOW())
                ON CONFLICT (id) DO UPDATE SET
                    website=COALESCE(NULLIF(EXCLUDED.website,''), icc_prospects.website),
                    updated_at=NOW()
            """, (prospect_id, name or prospect_id, website))

            # Write score
            cur.execute("""
                UPDATE icc_prospects SET
                    idr_score=%s, critical_count=%s, total_issues=%s,
                    scanned=TRUE, scanned_at=NOW(),
                    priority=(%s < 60),
                    maturity_level=%s,
                    updated_at=NOW()
                WHERE id=%s
            """, (score, criticals, total_issues, score, maturity, prospect_id))

            # Write to scan history
            cur.execute("""
                INSERT INTO icc_scan_history
                    (prospect_id, domain, score, critical_count, total_issues, scan_source)
                VALUES (%s,%s,%s,%s,%s,'icc')
            """, (prospect_id, website, score, criticals, total_issues))

        log_activity('scan_complete',
                     f'{name}: {score}/100 ({criticals} critical)' +
                     (' — PRIORITY' if score < 60 else ''))
        return True
    except Exception as e:
        print(f'[ICC_DB] save_scan_result error: {e}')
        return False
    finally:
        conn.close()


def _calc_maturity(score) -> str:
    """Determine Transparency Scorecard level from scan score."""
    if score is None:
        return 'ABSENT'
    if score < 40:
        return 'REACTIVE'
    if score < 60:
        return 'DOCUMENTED'
    if score < 80:
        return 'VERIFIED'
    return 'ACTIVE'


def update_prospect_contact_email(prospect_id: str, email: str) -> bool:
    """Store contact email permanently — never type it twice."""
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_prospects SET
                    contact_email=%s, updated_at=NOW()
                WHERE id=%s
            """, (email, prospect_id))
        return True
    except Exception as e:
        print(f'[ICC_DB] update_contact_email error: {e}')
        return False
    finally:
        conn.close()


def update_prospect_score(prospect_id: str, score: int,
                           criticals: int, msg: str) -> bool:
    maturity = _calc_maturity(score)
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_prospects SET
                    idr_score=%s, critical_count=%s,
                    scanned=TRUE, scanned_at=NOW(),
                    priority=(%s < 60),
                    maturity_level=%s,
                    outreach_msg=%s, updated_at=NOW()
                WHERE id=%s
            """, (score, criticals, score, maturity, msg, prospect_id))
        return True
    except Exception as e:
        print(f'[ICC_DB] update_score error: {e}')
        return False
    finally:
        conn.close()


def get_prospects(state=None, org_type=None, org_lane=None,
                  priority_only=False, unscanned_only=False,
                  limit=200, offset=0) -> list:
    conn = get_conn()
    if not conn:
        return []
    try:
        conditions, params = [], []
        if state:
            conditions.append('state = %s'); params.append(state)
        if org_type:
            conditions.append('org_type = %s'); params.append(org_type)
        if org_lane:
            conditions.append('org_lane = %s'); params.append(org_lane)
        if priority_only:
            conditions.append('priority = TRUE')
        if unscanned_only:
            conditions.append('scanned = FALSE')
            conditions.append("website != ''")
        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        params += [limit, offset]
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"""
                SELECT * FROM icc_prospects
                {where}
                ORDER BY priority DESC, idr_score ASC NULLS LAST, name ASC
                LIMIT %s OFFSET %s
            """, params)
            rows = [dict(r) for r in cur.fetchall()]
            # Serialize datetimes
            for r in rows:
                for k, v in r.items():
                    if hasattr(v, 'isoformat'):
                        r[k] = v.isoformat()
            return rows
    except Exception as e:
        print(f'[ICC_DB] get_prospects error: {e}')
        return []
    finally:
        conn.close()


def get_prospect_by_id(pid: str) -> dict:
    conn = get_conn()
    if not conn:
        return {}
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM icc_prospects WHERE id=%s', (pid,))
            row = cur.fetchone()
            if not row:
                return {}
            r = dict(row)
            for k, v in r.items():
                if hasattr(v, 'isoformat'):
                    r[k] = v.isoformat()
            return r
    except Exception as e:
        return {}
    finally:
        conn.close()


def get_unscanned_with_websites(limit=20) -> list:
    return get_prospects(unscanned_only=True, limit=limit)


def get_scanned_prospects(limit=100) -> list:
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, name, org_type, org_lane, city, state, phone,
                       website, idr_score, critical_count, total_issues,
                       scanned_at, priority, maturity_level, contact_email
                FROM icc_prospects
                WHERE scanned=TRUE AND idr_score IS NOT NULL
                ORDER BY priority DESC, idr_score ASC
                LIMIT %s
            """, (limit,))
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                for k, v in r.items():
                    if hasattr(v, 'isoformat'):
                        r[k] = v.isoformat()
            return rows
    except Exception as e:
        print(f'[ICC_DB] get_scanned_prospects error: {e}')
        return []
    finally:
        conn.close()


def get_warm_leads() -> list:
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT p.id, p.name, p.website, p.idr_score, p.phone,
                       p.contact_email, o.status, o.sent_at, o.notes
                FROM icc_prospects p
                JOIN icc_outreach o ON o.prospect_id = p.id
                WHERE o.status IN ('opened','clicked','replied','interested')
                ORDER BY o.updated_at DESC
                LIMIT 20
            """)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                for k, v in r.items():
                    if hasattr(v, 'isoformat'):
                        r[k] = v.isoformat()
            return rows
    except Exception as e:
        print(f'[ICC_DB] get_warm_leads error: {e}')
        return []
    finally:
        conn.close()


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_icc_stats() -> dict:
    """
    Bulletproof stats — each query isolated.
    One failing table never zeros out everything else.
    """
    conn = get_conn()
    if not conn:
        return {}

    def _q(cur, sql, default=0):
        try:
            cur.execute(sql)
            row = cur.fetchone()
            return row[0] if row else default
        except Exception as e:
            print(f'[ICC_DB] stats query error: {e} | SQL: {sql[:60]}')
            try:
                conn.rollback()
            except Exception:
                pass
            return default

    try:
        with conn.cursor() as cur:
            total    = _q(cur, "SELECT COUNT(*) FROM icc_prospects")
            scanned  = _q(cur, "SELECT COUNT(*) FROM icc_prospects WHERE scanned=TRUE")
            priority = _q(cur, "SELECT COUNT(*) FROM icc_prospects WHERE priority=TRUE")
            contacted= _q(cur, "SELECT COUNT(*) FROM icc_outreach")
            converted= _q(cur, "SELECT COUNT(*) FROM icc_outreach WHERE status='converted'")
            revenue  = _q(cur, "SELECT COALESCE(SUM(revenue),0) FROM icc_outreach WHERE status='converted'")
            warm     = _q(cur, "SELECT COUNT(*) FROM icc_outreach WHERE status IN ('replied','interested','opened','clicked')")
            gov_total= _q(cur, "SELECT COUNT(*) FROM icc_prospects WHERE org_lane='government'")

            # Optional tables — may not exist yet on first deploy
            content_pending = _q(cur, "SELECT COUNT(*) FROM icc_content WHERE status='draft'")
            assoc_contacted = _q(cur, "SELECT COUNT(*) FROM icc_associations WHERE status != 'not_contacted'")
            assoc_not_contacted = _q(cur, "SELECT COUNT(*) FROM icc_associations WHERE status = 'not_contacted'")

            # Activity feed
            activity = []
            try:
                cur.execute("""
                    SELECT event_type, detail, created_at FROM icc_activity
                    ORDER BY created_at DESC LIMIT 20
                """)
                activity = [
                    {'type': r[0], 'detail': r[1],
                     'time': r[2].strftime('%H:%M') if r[2] else ''}
                    for r in cur.fetchall()
                ]
            except Exception as e:
                print(f'[ICC_DB] activity query error: {e}')

        from datetime import date as _date
        days_past = max(0, (_date.today() - _date(2026, 5, 11)).days)

        result = {
            'total': total, 'scanned': scanned, 'priority': priority,
            'contacted': contacted, 'converted': converted,
            'revenue': int(revenue or 0), 'warm': warm,
            'days_past_deadline': days_past,
            'activity': activity,
            'assoc_contacted': assoc_contacted,
            'assoc_not_contacted': assoc_not_contacted,
            'gov_total': gov_total,
            'content_pending': content_pending,
        }
        print(f'[ICC_DB] Stats: total={total} scanned={scanned} priority={priority}')
        return result

    except Exception as e:
        print(f'[ICC_DB] stats fatal error: {e}')
        return {}
    finally:
        conn.close()


# ── Outreach operations ───────────────────────────────────────────────────────

def log_outreach(prospect_id: str, prospect_name: str,
                 contact_email: str = '', contact_name: str = '',
                 contact_title: str = '', message_type: str = 'email',
                 subject: str = '', notes: str = '') -> int:
    conn = get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO icc_outreach
                    (prospect_id, prospect_name, contact_email, contact_name,
                     contact_title, message_type, subject, notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """, (prospect_id, prospect_name, contact_email, contact_name,
                  contact_title, message_type, subject, notes))
            row = cur.fetchone()
            oid = row[0] if row else 0
        # Store contact email on prospect permanently
        if contact_email:
            update_prospect_contact_email(prospect_id, contact_email)
        return oid
    except Exception as e:
        print(f'[ICC_DB] log_outreach error: {e}')
        return 0
    finally:
        conn.close()


def update_outreach_status(outreach_id: int, status: str,
                            revenue: int = 0, notes: str = '') -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_outreach SET
                    status=%s, revenue=%s,
                    notes=COALESCE(NULLIF(%s,''), notes),
                    updated_at=NOW()
                WHERE id=%s
            """, (status, revenue, notes, outreach_id))
        return True
    except Exception as e:
        return False
    finally:
        conn.close()


def log_email_event(prospect_id: str, event_type: str,
                     email_address: str = '', raw_payload: dict = None,
                     outreach_id: int = None) -> bool:
    """Record every SendGrid event — opens, clicks, bounces."""
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO icc_email_events
                    (outreach_id, prospect_id, event_type, email_address, raw_payload)
                VALUES (%s,%s,%s,%s,%s)
            """, (outreach_id, prospect_id, event_type, email_address,
                  json.dumps(raw_payload) if raw_payload else None))
            # Update outreach status on open/click
            if event_type in ('open', 'click') and prospect_id:
                status = 'clicked' if event_type == 'click' else 'opened'
                cur.execute("""
                    UPDATE icc_outreach SET
                        status=%s, updated_at=NOW()
                    WHERE prospect_id=%s AND status='sent'
                """, (status, prospect_id))
        log_activity(
            'email_opened' if event_type == 'open' else f'email_{event_type}',
            f'Prospect {prospect_id} {event_type} — WARM LEAD'
        )
        return True
    except Exception as e:
        print(f'[ICC_DB] log_email_event error: {e}')
        return False
    finally:
        conn.close()


def get_outreach_list(status=None, limit=100) -> list:
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if status:
                cur.execute("""
                    SELECT * FROM icc_outreach WHERE status=%s
                    ORDER BY sent_at DESC LIMIT %s
                """, (status, limit))
            else:
                cur.execute("""
                    SELECT * FROM icc_outreach
                    ORDER BY sent_at DESC LIMIT %s
                """, (limit,))
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                for k, v in r.items():
                    if hasattr(v, 'isoformat'):
                        r[k] = v.isoformat()
            return rows
    except Exception as e:
        return []
    finally:
        conn.close()


def get_followups_due() -> list:
    """Outreach sent 48+ hours ago with no response."""
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT o.*, p.phone, p.website, p.idr_score, p.contact_email
                FROM icc_outreach o
                JOIN icc_prospects p ON p.id = o.prospect_id
                WHERE o.status = 'sent'
                  AND o.sent_at < NOW() - INTERVAL '48 hours'
                ORDER BY o.sent_at ASC
                LIMIT 50
            """)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                for k, v in r.items():
                    if hasattr(v, 'isoformat'):
                        r[k] = v.isoformat()
            return rows
    except Exception as e:
        return []
    finally:
        conn.close()


# ── Intelligence operations ───────────────────────────────────────────────────

def save_intelligence(intel_type: str, source: str, headline: str,
                       summary: str, url: str = '',
                       relevance: int = 50) -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            # Avoid duplicates by headline
            cur.execute("SELECT id FROM icc_intelligence WHERE headline=%s LIMIT 1", (headline,))
            if cur.fetchone():
                return True  # Already have it
            cur.execute("""
                INSERT INTO icc_intelligence
                    (intel_type, source, headline, summary, url, relevance_score)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (intel_type, source, headline, summary, url, relevance))
        return True
    except Exception as e:
        print(f'[ICC_DB] save_intelligence error: {e}')
        return False
    finally:
        conn.close()


def get_fresh_intelligence(limit=10) -> list:
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM icc_intelligence
                WHERE used_in_briefing = FALSE
                ORDER BY relevance_score DESC, created_at DESC
                LIMIT %s
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        return []
    finally:
        conn.close()


# ── Content operations ────────────────────────────────────────────────────────

def save_content(content_type: str, visual_direction: str,
                  caption: str, body_text: str = '',
                  image_path: str = '', hashtags: str = '',
                  prospect_id: str = None,
                  scan_score: int = None) -> int:
    conn = get_conn()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO icc_content
                    (content_type, visual_direction, body_text, caption,
                     hashtags, image_path, prospect_id, scan_score, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'draft')
                RETURNING id
            """, (content_type, visual_direction, body_text, caption,
                  hashtags, image_path, prospect_id, scan_score))
            row = cur.fetchone()
            return row[0] if row else 0
    except Exception as e:
        print(f'[ICC_DB] save_content error: {e}')
        return 0
    finally:
        conn.close()


def get_pending_content(limit=20) -> list:
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM icc_content
                WHERE status='draft'
                ORDER BY created_at DESC LIMIT %s
            """, (limit,))
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                for k, v in r.items():
                    if hasattr(v, 'isoformat'):
                        r[k] = v.isoformat()
            return rows
    except Exception as e:
        return []
    finally:
        conn.close()


# ── Activity log ──────────────────────────────────────────────────────────────

def log_activity(event_type: str, detail: str, count: int = 1):
    conn = get_conn()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO icc_activity (event_type, detail, count)
                VALUES (%s,%s,%s)
            """, (event_type, detail, count))
    except Exception:
        pass
    finally:
        conn.close()


# ── Association operations ────────────────────────────────────────────────────

def get_associations(lane=None) -> list:
    conn = get_conn()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if lane:
                cur.execute("""
                    SELECT * FROM icc_associations
                    WHERE org_lane=%s ORDER BY priority_order
                """, (lane,))
            else:
                cur.execute('SELECT * FROM icc_associations ORDER BY priority_order')
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                for k, v in r.items():
                    if hasattr(v, 'isoformat'):
                        r[k] = v.isoformat()
            return rows
    except Exception as e:
        return []
    finally:
        conn.close()


def mark_association_contacted(assoc_id: str, email: str = '') -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_associations SET
                    status='contacted',
                    pitch_sent_at=NOW(),
                    contact_email=COALESCE(NULLIF(%s,''), contact_email),
                    updated_at=NOW()
                WHERE id=%s AND status='not_contacted'
            """, (email or '', assoc_id))
        return True
    except Exception as e:
        print(f'[ICC_DB] mark_association_contacted error: {e}')
        return False
    finally:
        conn.close()


def update_association_status(assoc_id: str, status: str,
                               notes: str = '') -> bool:
    conn = get_conn()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE icc_associations SET
                    status=%s,
                    notes=COALESCE(NULLIF(%s,''), notes),
                    opened_at=CASE WHEN %s='opened' AND opened_at IS NULL
                              THEN NOW() ELSE opened_at END,
                    replied_at=CASE WHEN %s='replied' AND replied_at IS NULL
                               THEN NOW() ELSE replied_at END,
                    updated_at=NOW()
                WHERE id=%s
            """, (status, notes, status, status, assoc_id))
        return True
    except Exception as e:
        return False
    finally:
        conn.close()
