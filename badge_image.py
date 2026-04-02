"""
IDR Shield — Badge PNG Image Generator
Per IDR Badge System Brand Guide 2026 (IDR-BRAND-2026-01)

Endpoint: GET /badge-image/<domain>
          GET /badge-image/<domain>?status=active&score=84

Returns:  image/png, 880×220px, RGBA
Fonts:    Poppins Bold/Medium, Lora, Liberation Serif Bold (all ship on Railway/Ubuntu)
"""

import math
import io
import os
from PIL import Image, ImageDraw, ImageFont


# ── Brand Guide Colors ────────────────────────────────────────────────────────
_NAVY       = (10,  14,  26)
_GOLD       = (201, 168,  76)
_GOLD_DEEP  = (138, 111,  46)
_GOLD_LIGHT = (226, 201, 126)
_CREAM      = (250, 247, 242)
_WHITE      = (255, 255, 255)
_GREEN      = (39,  174,  96)
_ORANGE     = (214, 117,  45)
_GREY       = (100, 100, 100)

_STATUS_COLORS = {
    'active':     _GREEN,
    'monitoring': _ORANGE,
    'expired':    _GREY,
}

# ── Output dimensions ─────────────────────────────────────────────────────────
_DISP_W, _DISP_H = 440, 110   # logical CSS pixels
_RENDER_SCALE    = 4           # render at 4× internally
_OUT_SCALE       = 2           # output at 2× (retina)


# ── Font paths ────────────────────────────────────────────────────────────────
_F_POPPINS_BOLD = '/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf'
_F_POPPINS_MED  = '/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf'
_F_LORA         = '/usr/share/fonts/truetype/google-fonts/Lora-Variable.ttf'
_F_SERIF_BOLD   = '/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf'
_F_SANS_BOLD    = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'


def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype(_F_SANS_BOLD, size)
        except Exception:
            return ImageFont.load_default()


def _tw(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


def _th(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[3] - bb[1]


def _draw_arc_text(img, draw, text, cx, cy, radius, font, color, start_deg, spacing=0.85):
    """Render text following a circular arc path."""
    chars = list(text)
    char_angles = []
    for ch in chars:
        bb = draw.textbbox((0, 0), ch, font=font)
        cw = bb[2] - bb[0]
        angle = math.degrees(cw / radius) * spacing
        char_angles.append((ch, angle))

    total_angle = sum(a for _, a in char_angles)
    current = start_deg - total_angle / 2

    for ch, angle in char_angles:
        mid_angle = current + angle / 2
        rad = math.radians(mid_angle)
        x = cx + radius * math.cos(rad)
        y = cy + radius * math.sin(rad)
        bb = draw.textbbox((0, 0), ch, font=font)
        cw = bb[2] - bb[0]
        ch_img = Image.new('RGBA', (cw + 6, int(font.size * 1.6)), (0, 0, 0, 0))
        ch_draw = ImageDraw.Draw(ch_img)
        ch_draw.text((3, 0), ch, font=font, fill=color)
        rot = ch_img.rotate(-(mid_angle + 90), expand=True, resample=Image.BICUBIC)
        img.paste(rot, (int(x - rot.width / 2), int(y - rot.height / 2)), rot)
        current += angle


def render_badge(status: str = 'monitoring', score: int | None = None) -> bytes:
    """
    Render an IDR Shield badge PNG per Brand Guide 2026.

    Parameters
    ----------
    status : 'active' | 'monitoring' | 'expired'
    score  : integer 0–100 or None

    Returns
    -------
    bytes — PNG, 880×220px
    """
    status = status.lower().strip()
    if status not in _STATUS_COLORS:
        status = 'monitoring'

    S  = _RENDER_SCALE
    W  = _DISP_W * S    # 1760
    H  = _DISP_H * S    # 440

    img  = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    PAD  = 16 * S

    # Background + border
    draw.rounded_rectangle([0, 0, W-1, H-1], radius=6*S,
                            fill=_NAVY, outline=_GOLD, width=2*S)

    # ── Institutional Seal (Asset 01 / 02 style) ──────────────────────────────
    SR = 38 * S
    SX = PAD + SR + 4 * S
    SY = H // 2

    # Outer gold ring
    draw.ellipse([SX-SR, SY-SR, SX+SR, SY+SR],
                 fill=_NAVY, outline=_GOLD, width=2*S)
    # Inner ring (Gold Deep, faint)
    IR = SR - 8 * S
    draw.ellipse([SX-IR, SY-IR, SX+IR, SY+IR],
                 fill=None, outline=(*_GOLD_DEEP, 180), width=max(1, S // 2))

    # Top arc — "INSTITUTE OF DIGITAL REMEDIATION"
    f_arc_top = _load_font(_F_POPPINS_BOLD, 5 * S)
    _draw_arc_text(img, draw, 'INSTITUTE OF DIGITAL REMEDIATION',
                   SX, SY, SR - 4*S, f_arc_top, (*_GOLD, 160), -90, spacing=0.85)

    # Bottom arc — "IDR PROTOCOL REGISTRY"
    f_arc_bot = _load_font(_F_POPPINS_BOLD, 4 * S)
    _draw_arc_text(img, draw, 'IDR PROTOCOL REGISTRY',
                   SX, SY, SR - 4*S, f_arc_bot, (*_GOLD, 120), 90, spacing=0.95)

    # IDR Monogram (serif, brand guide: Playfair Display → Liberation Serif here)
    f_mono = _load_font(_F_SERIF_BOLD, 18 * S)
    idr_w  = _tw(draw, 'IDR', f_mono)
    idr_h  = _th(draw, 'IDR', f_mono)
    draw.text((SX - idr_w // 2, SY - idr_h // 2 - 3 * S), 'IDR',
              font=f_mono, fill=_GOLD)

    # Separator line
    line_y = SY + idr_h // 2 + 1 * S
    draw.line([(SX - 12*S, line_y), (SX + 12*S, line_y)],
              fill=_GOLD_DEEP, width=max(1, S // 2))

    # Status text inside seal
    f_seal_st = _load_font(_F_POPPINS_BOLD, 4 * S)
    st_map    = {'active': 'ACTIVE', 'monitoring': 'MONITORING', 'expired': 'EXPIRED'}
    st_label  = st_map.get(status, 'MONITORING')
    st_w      = _tw(draw, st_label, f_seal_st)
    draw.text((SX - st_w // 2, line_y + 2 * S), st_label,
              font=f_seal_st, fill=(*_GOLD, 145))

    # ── Text column ───────────────────────────────────────────────────────────
    TX = SX + SR + 20 * S
    TY = H // 2 - 22 * S

    # Institution label (Poppins Medium, Montserrat equivalent)
    f_inst = _load_font(_F_POPPINS_MED, 5 * S)
    draw.text((TX, TY), 'INSTITUTE OF DIGITAL REMEDIATION',
              font=f_inst, fill=(*_GOLD, 180))

    # Product name (Lora — EB Garamond equivalent)
    f_name = _load_font(_F_LORA, 13 * S)
    draw.text((TX, TY + 7 * S), 'IDR Shield', font=f_name, fill=_CREAM)

    # Status pill
    pill_color = _STATUS_COLORS[status]
    f_pill     = _load_font(_F_POPPINS_BOLD, 5 * S)
    pill_text  = st_label + (f'  {score}/100' if score is not None else '')
    ptb  = draw.textbbox((0, 0), pill_text, font=f_pill)
    pw   = ptb[2] - ptb[0] + 10 * S
    ph   = ptb[3] - ptb[1] + 4  * S
    PX, PY = TX, TY + 23 * S
    draw.rounded_rectangle([PX, PY, PX + pw, PY + ph], radius=3 * S, fill=pill_color)
    draw.text((PX + 5 * S, PY + 2 * S), pill_text, font=f_pill, fill=_WHITE)

    # ── Downsample 4× → 2× retina ────────────────────────────────────────────
    out_w = _DISP_W * _OUT_SCALE   # 880
    out_h = _DISP_H * _OUT_SCALE   # 220
    final = img.resize((out_w, out_h), Image.LANCZOS)

    buf = io.BytesIO()
    final.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


def badge_for_domain(domain: str, get_registry_fn) -> tuple:
    """Look up registry, render matching badge. Returns (png_bytes, status, score)."""
    try:
        reg    = get_registry_fn(domain)
        status = reg.get('status', 'monitoring') if reg else 'expired'
        score  = reg.get('latest_score')         if reg else None
    except Exception:
        status, score = 'monitoring', None
    return render_badge(status=status, score=score), status, score
