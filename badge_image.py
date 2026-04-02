"""
IDR Shield — Badge PNG Image Generator
=======================================
Generates a static PNG badge matching the badge.js design exactly.
Used for email embeds, press kits, and social sharing.

Endpoint: GET /badge-image/<domain>
          GET /badge-image/<domain>?score=84&status=active

Returns:  image/png, 220x52px, RGBA, 2x retina source downsampled.
Caching:  Cache-Control: public, max-age=3600 (1 hour)

Drop this file alongside app.py.
Requires: Pillow  (pip install Pillow)
Fonts:    DejaVu Sans Bold (ships on most Linux servers — including Railway)
          Falls back to PIL default font if not found.
"""

import io
import os
from PIL import Image, ImageDraw, ImageFont


# ── Palette — mirrors badge.js exactly ───────────────────────────────────────
_BG        = (8,   13,  26)          # #080d1a
_GOLD      = (196, 160, 82)          # #C4A052
_GOLD_DIM  = (196, 160, 82, 155)     # ~60% opacity for label/inner ring
_CREAM     = (240, 232, 216)         # #F0E8D8
_GREEN     = (39,  174, 96)          # #27AE60 — active
_ORANGE    = (230, 126, 34)          # #E67E22 — monitoring
_GREY      = (85,  85,  85)          # #555    — expired
_WHITE     = (255, 255, 255)

_STATUS_COLORS = {
    'active':     _GREEN,
    'monitoring': _ORANGE,
    'expired':    _GREY,
}

# ── Dimensions ────────────────────────────────────────────────────────────────
_W_OUT, _H_OUT = 220, 52   # final output size in CSS pixels
_SCALE         = 2          # render at 2× then downsample for crisp edges


# ── Font resolution ───────────────────────────────────────────────────────────
_FONT_CANDIDATES = [
    # Railway / Ubuntu / Debian
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    # macOS
    '/System/Library/Fonts/Helvetica.ttc',
    '/Library/Fonts/Arial Bold.ttf',
    # Windows (if ever)
    'C:/Windows/Fonts/arialbd.ttf',
]


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # Last resort — PIL built-in bitmap font (no size param)
    return ImageFont.load_default()


def _text_width(draw: ImageDraw.ImageDraw, text: str,
                font: ImageFont.ImageFont) -> int:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0]


# ── Core renderer ─────────────────────────────────────────────────────────────

def render_badge(
    status: str = 'monitoring',
    score: int | None = None,
) -> bytes:
    """
    Render a badge PNG and return raw bytes.

    Parameters
    ----------
    status : 'active' | 'monitoring' | 'expired'
    score  : integer 0-100 or None

    Returns
    -------
    bytes — PNG image data, 220×52 px
    """
    status = status.lower().strip()
    if status not in _STATUS_COLORS:
        status = 'monitoring'

    S = _SCALE
    W = _W_OUT * S
    H = _H_OUT * S

    img  = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    PAD = 8 * S

    # ── Background + gold border ──────────────────────────────────────────
    draw.rounded_rectangle(
        [0, 0, W - 1, H - 1],
        radius=4 * S,
        fill=_BG,
        outline=_GOLD,
        width=S,
    )

    # ── Seal circle ───────────────────────────────────────────────────────
    SX = PAD + 14 * S          # center x
    SY = H // 2                # center y
    SR = 13 * S                # radius

    # Outer ring
    draw.ellipse(
        [SX - SR, SY - SR, SX + SR, SY + SR],
        fill=_BG, outline=_GOLD, width=S,
    )
    # Inner faint ring
    draw.ellipse(
        [SX - SR + 4, SY - SR + 4, SX + SR - 4, SY + SR - 4],
        fill=None,
        outline=(196, 160, 82, 55),
        width=max(1, S // 2),
    )

    # "IDR" label in seal
    f_idr = _load_font(7 * S)
    idr_w = _text_width(draw, 'IDR', f_idr)
    draw.text(
        (SX - idr_w // 2, SY - 11 * S),
        'IDR', font=f_idr,
        fill=(196, 160, 82, 155),
    )

    # Checkmark ✓
    f_check = _load_font(12 * S)
    ck_w = _text_width(draw, '✓', f_check)
    draw.text(
        (SX - ck_w // 2 + S, SY - 2 * S),
        '✓', font=f_check, fill=_GOLD,
    )

    # ── Text block ────────────────────────────────────────────────────────
    TX   = SX + SR + 8 * S
    TY   = H // 2 - 14 * S

    f_lbl  = _load_font(5 * S)
    f_name = _load_font(9 * S)
    f_pill = _load_font(6 * S)

    # Top label — institution name
    draw.text(
        (TX, TY),
        'INSTITUTE OF DIGITAL REMEDIATION',
        font=f_lbl,
        fill=(196, 160, 82, 155),
    )

    # Product name
    draw.text(
        (TX, TY + 8 * S),
        'IDR Shield',
        font=f_name,
        fill=_CREAM,
    )

    # Status pill
    pill_color = _STATUS_COLORS[status]
    pill_label = status.upper()
    pill_text  = pill_label + (f'  {score}/100' if score is not None else '')

    ptb = draw.textbbox((0, 0), pill_text, font=f_pill)
    pw  = ptb[2] - ptb[0] + 8 * S
    ph  = ptb[3] - ptb[1] + 4 * S
    PX, PY = TX, TY + 20 * S

    draw.rounded_rectangle(
        [PX, PY, PX + pw, PY + ph],
        radius=3 * S,
        fill=pill_color,
    )
    draw.text(
        (PX + 4 * S, PY + 2 * S),
        pill_text,
        font=f_pill,
        fill=_WHITE,
    )

    # ── Downsample to output resolution ──────────────────────────────────
    final = img.resize((_W_OUT, _H_OUT), Image.LANCZOS)

    buf = io.BytesIO()
    final.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


# ── Convenience: pre-render and cache for a given domain ─────────────────────

def badge_for_domain(
    domain: str,
    get_registry_fn,
) -> tuple[bytes, str, int | None]:
    """
    Look up registry status for a domain and render the matching badge.

    Returns
    -------
    (png_bytes, status_str, score_int_or_None)
    """
    try:
        reg = get_registry_fn(domain)
        if reg:
            status = reg.get('status', 'monitoring')
            score  = reg.get('latest_score')
        else:
            status = 'expired'
            score  = None
    except Exception:
        status = 'monitoring'
        score  = None

    png = render_badge(status=status, score=score)
    return png, status, score
