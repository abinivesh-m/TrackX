"""
theme.py

Presentation-layer helpers ONLY for dashboard/dashboard.py.

Nothing in this file touches detection, OCR, database, trajectory,
alert, or analytics logic. It exists purely to give the Streamlit UI a
consistent "command center" look: CSS injection + small HTML-building
helper functions (KPI cards, status badges, plate evidence cards,
timeline steps, empty states).

Every helper takes already-computed, real values as arguments — it never
invents data. Callers in dashboard.py are responsible for passing real
numbers/strings pulled from the database/analytics/pipeline; if a value
is unknown the caller should pass "N/A" / "NO DATA AVAILABLE" rather
than this module inventing a placeholder.
"""

import html as _html
from datetime import datetime

import streamlit as st

# --------------------------------------------------------------------------
# Palette (kept in one place so every component below stays consistent)
# --------------------------------------------------------------------------
BG = "#0b0e13"
SURFACE = "#12161d"
SURFACE_2 = "#171c25"
BORDER = "#232a36"
TEXT = "#e6e9ef"
TEXT_MUTED = "#8892a0"
ACCENT = "#3aa0ff"        # cyan/blue — active / intelligence
GOOD = "#2ecc71"          # green — healthy / verified
WARN = "#f5a524"          # amber — medium severity
BAD = "#ef4444"           # red — critical / alert
BAD_DIM = "#7f1d1d"


def inject_base_css():
    st.markdown(
        f"""
        <style>
        /* ---- hide default streamlit chrome ---- */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header[data-testid="stHeader"] {{background: transparent;}}
        .stDeployButton {{display: none;}}

        html, body, [class*="css"] {{
            font-family: "Inter", "Segoe UI", -apple-system, sans-serif;
        }}

        .stApp {{
            background: {BG};
            color: {TEXT};
        }}

        section[data-testid="stSidebar"] {{
            background: {SURFACE};
            border-right: 1px solid {BORDER};
        }}

        /* ---- tighten default block spacing ---- */
        .block-container {{
            padding-top: 1rem;
            padding-bottom: 2rem;
            max-width: 1400px;
        }}

        /* ---- tabs restyled as a premium product nav bar ---- */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 6px;
            border-bottom: 1px solid {BORDER};
            background: transparent;
            margin-bottom: 4px;
        }}
        .stTabs [data-baseweb="tab"] {{
            height: 44px;
            background: transparent;
            color: {TEXT_MUTED};
            opacity: 0.65;
            border-radius: 8px 8px 0 0;
            padding: 0 18px;
            font-weight: 700;
            font-size: 0.78rem;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            transition: opacity 0.15s ease, color 0.15s ease;
        }}
        .stTabs [data-baseweb="tab"]:hover {{
            opacity: 1;
            color: {ACCENT} !important;
        }}
        .stTabs [aria-selected="true"] {{
            color: {TEXT} !important;
            opacity: 1 !important;
            background: {SURFACE} !important;
            border-bottom: 3px solid {ACCENT} !important;
            box-shadow: 0 -1px 0 0 {BORDER} inset, 1px 0 0 0 {BORDER} inset, -1px 0 0 0 {BORDER} inset;
        }}

        /* ---- metrics ---- */
        div[data-testid="stMetric"] {{
            background: {SURFACE};
            border: 1px solid {BORDER};
            border-radius: 10px;
            padding: 12px 16px;
        }}
        div[data-testid="stMetricLabel"] {{
            color: {TEXT_MUTED} !important;
            font-size: 0.72rem !important;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}

        /* ---- containers/cards ---- */
        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border-color: {BORDER} !important;
            background: {SURFACE};
            border-radius: 10px;
        }}

        /* ---- buttons ---- */
        .stButton button {{
            border-radius: 6px;
            font-weight: 600;
            letter-spacing: 0.02em;
        }}

        /* ---- inputs ---- */
        .stTextInput input, .stSelectbox div[data-baseweb="select"], .stNumberInput input {{
            background: {SURFACE_2} !important;
            border-color: {BORDER} !important;
        }}

        hr {{border-color: {BORDER};}}

        /* ---- scrollbar ---- */
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 4px; }}

        /* ---- responsive improvements ---- */
        @media (max-width: 768px) {{
            .block-container {{
                padding-top: 0.5rem;
                padding-bottom: 1rem;
                max-width: 100%;
            }}
            
            .stTabs [data-baseweb="tab"] {{
                height: 40px;
                padding: 0 12px;
                font-size: 0.7rem;
            }}
            
            div[data-testid="stMetric"] {{
                padding: 8px 12px;
            }}
            
            div[data-testid="stMetricLabel"] {{
                font-size: 0.65rem !important;
            }}
        }}

        /* ---- performance optimizations ---- */
        .leaflet-container {{
            will-change: transform;
            backface-visibility: hidden;
            -webkit-backface-visibility: hidden;
        }}
        
        /* ---- better split layout ---- */
        [data-testid="stVerticalBlock"] > div > div {{
            gap: 1rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def top_header(system_status, camera_count, processing_status):
    """
    system_status: (label:str, ok:bool) e.g. ("OPERATIONAL", True)
    camera_count: int — real count from the camera network config
    processing_status: str — real current state, e.g. "IDLE — WAITING FOR INPUT"
                        or "PROCESSING CAM_01…"
    """
    dot_color = GOOD if system_status[1] else WARN
    now_str = datetime.now().strftime("%H:%M:%S")
    st.markdown(
        f"""
        <div style="
            display:flex; justify-content:space-between; align-items:center;
            padding:14px 18px; margin-bottom:6px;
            background:{SURFACE}; border:1px solid {BORDER}; border-radius:10px;">
          <div>
            <div style="font-size:1.15rem; font-weight:800; letter-spacing:0.04em; color:{TEXT};">
                TRACKX
            </div>
            <div style="font-size:0.72rem; color:{TEXT_MUTED}; letter-spacing:0.02em;">
                City-Wide Vehicle Intelligence Engine
            </div>
          </div>
          <div style="display:flex; align-items:center; gap:22px;">
            <div style="text-align:right;">
                <div style="font-size:0.68rem; color:{TEXT_MUTED}; text-transform:uppercase; letter-spacing:0.05em;">Cameras</div>
                <div style="font-size:0.85rem; color:{TEXT}; font-weight:600;">{camera_count} configured</div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:0.68rem; color:{TEXT_MUTED}; text-transform:uppercase; letter-spacing:0.05em;">Pipeline</div>
                <div style="font-size:0.85rem; color:{TEXT}; font-weight:600;">{_html.escape(processing_status)}</div>
            </div>
            <div style="text-align:right;">
                <div style="font-size:0.68rem; color:{TEXT_MUTED}; text-transform:uppercase; letter-spacing:0.05em;">Local time</div>
                <div style="font-size:0.85rem; color:{TEXT}; font-weight:600;">{now_str}</div>
            </div>
            <div style="display:flex; align-items:center; gap:6px; padding:6px 12px;
                        background:{SURFACE_2}; border:1px solid {BORDER}; border-radius:20px;">
                <span style="width:8px; height:8px; border-radius:50%; background:{dot_color};
                             display:inline-block; box-shadow:0 0 6px {dot_color};"></span>
                <span style="font-size:0.72rem; font-weight:700; color:{TEXT}; letter-spacing:0.03em;">
                    SYSTEM {_html.escape(system_status[0])}
                </span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title, subtitle=None):
    sub = f'<div style="font-size:0.82rem; color:{TEXT_MUTED}; margin-top:2px;">{_html.escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div style="margin:4px 0 14px 0;">
            <div style="font-size:1.05rem; font-weight:700; color:{TEXT}; letter-spacing:0.01em;">
                {_html.escape(title)}
            </div>
            {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_row(items):
    """
    items: list of dicts: {"label": str, "value": str, "hint": str (optional)}
    Renders a single-row grid of KPI cards. Values must already be
    real/computed strings — pass "N/A" if there's nothing to show.
    """
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        hint = item.get("hint")
        hint_html = f'<div style="font-size:0.68rem; color:{TEXT_MUTED}; margin-top:2px;">{_html.escape(hint)}</div>' if hint else ""
        with col:
            st.markdown(
                f"""
                <div style="background:{SURFACE}; border:1px solid {BORDER}; border-radius:10px;
                            padding:12px 14px; height:100%;">
                    <div style="font-size:0.68rem; color:{TEXT_MUTED}; text-transform:uppercase;
                                letter-spacing:0.05em; font-weight:600;">{_html.escape(item['label'])}</div>
                    <div style="font-size:1.35rem; color:{TEXT}; font-weight:800; margin-top:2px;">
                        {_html.escape(str(item['value']))}
                    </div>
                    {hint_html}
                </div>
                """,
                unsafe_allow_html=True,
            )


def status_badge(label):
    """Maps a real status string to a colored pill. Unknown strings fall back to neutral grey."""
    key = (label or "").upper()
    if any(k in key for k in ("READY", "CONNECTED", "HEALTHY", "OPERATIONAL", "ONLINE")):
        color, bg = GOOD, "#123322"
    elif any(k in key for k in ("NOT INSTALLED", "NOT CONFIGURED", "NOT FOUND", "NOT AVAILABLE",
                                  "OFFLINE", "ERROR", "DEGRADED")):
        color, bg = BAD, "#3a1414"
    else:
        color, bg = WARN, "#332512"
    return (
        f'<span style="display:inline-flex; align-items:center; gap:6px; padding:3px 10px; '
        f'border-radius:20px; background:{bg}; border:1px solid {color}55; '
        f'color:{color}; font-size:0.72rem; font-weight:700; letter-spacing:0.02em;">'
        f'<span style="width:6px;height:6px;border-radius:50%;background:{color};display:inline-block;"></span>'
        f'{_html.escape(label)}</span>'
    )


def render_status_badge(label):
    st.markdown(status_badge(label), unsafe_allow_html=True)


def severity_badge(severity):
    sev = (severity or "MEDIUM").upper()
    color = {"HIGH": BAD, "CRITICAL": BAD, "MEDIUM": WARN, "LOW": GOOD}.get(sev, TEXT_MUTED)
    bg = {"HIGH": "#3a1414", "CRITICAL": "#3a1414", "MEDIUM": "#332512", "LOW": "#123322"}.get(sev, SURFACE_2)
    return (
        f'<span style="padding:2px 9px; border-radius:5px; background:{bg}; '
        f'border:1px solid {color}55; color:{color}; font-size:0.68rem; font-weight:800; '
        f'letter-spacing:0.04em;">{_html.escape(sev)}</span>'
    )


def plate_evidence_card_html(plate_text, ocr_confidence, camera_id, timestamp, extra_line=None):
    conf_str = f"{ocr_confidence:.1%}" if isinstance(ocr_confidence, (int, float)) else (ocr_confidence or "N/A")
    extra = f'<div style="font-size:0.72rem; color:{TEXT_MUTED}; margin-top:6px;">{_html.escape(str(extra_line))}</div>' if extra_line else ""
    return f"""
    <div style="background:{SURFACE}; border:1px solid {BORDER}; border-radius:10px; padding:14px;">
        <div style="font-size:0.66rem; color:{ACCENT}; font-weight:700; letter-spacing:0.06em; margin-bottom:8px;">
            PLATE IDENTIFIED
        </div>
        <div style="font-size:1.5rem; font-weight:800; color:{TEXT}; letter-spacing:0.03em; font-family: monospace;">
            {_html.escape(str(plate_text) if plate_text else "UNREAD")}
        </div>
        <div style="display:flex; justify-content:space-between; margin-top:10px; font-size:0.78rem;">
            <span style="color:{TEXT_MUTED};">OCR CONFIDENCE</span>
            <span style="color:{TEXT}; font-weight:600;">{_html.escape(conf_str)}</span>
        </div>
        <div style="display:flex; justify-content:space-between; margin-top:4px; font-size:0.78rem;">
            <span style="color:{TEXT_MUTED};">CAMERA</span>
            <span style="color:{TEXT}; font-weight:600;">{_html.escape(str(camera_id) if camera_id else "N/A")}</span>
        </div>
        <div style="display:flex; justify-content:space-between; margin-top:4px; font-size:0.78rem;">
            <span style="color:{TEXT_MUTED};">TIME</span>
            <span style="color:{TEXT}; font-weight:600;">{_html.escape(str(timestamp) if timestamp else "N/A")}</span>
        </div>
        {extra}
    </div>
    """


def pipeline_stage_tracker(stages):
    """
    stages: ordered list of (label:str, done:bool)
    Renders a compact vertical "done/pending" pipeline visualization
    reflecting REAL state passed in by the caller — never animate/fake
    a stage that hasn't actually happened.
    """
    rows = []
    for label, done in stages:
        mark = f'<span style="color:{GOOD}; font-weight:800;">✓</span>' if done else \
               f'<span style="color:{TEXT_MUTED}; font-weight:800;">○</span>'
        color = TEXT if done else TEXT_MUTED
        rows.append(
            f'<div style="display:flex; align-items:center; gap:8px; padding:5px 0;">'
            f'{mark}<span style="font-size:0.8rem; color:{color};">{_html.escape(label)}</span></div>'
        )
    st.markdown(
        f'<div style="background:{SURFACE}; border:1px solid {BORDER}; border-radius:10px; padding:12px 16px;">'
        + "".join(rows) + "</div>",
        unsafe_allow_html=True,
    )


def empty_state(title, body):
    st.markdown(
        f"""
        <div style="text-align:center; padding:40px 20px; background:{SURFACE};
                    border:1px dashed {BORDER}; border-radius:10px;">
            <div style="font-size:0.9rem; font-weight:700; color:{TEXT}; letter-spacing:0.03em;">
                {_html.escape(title)}
            </div>
            <div style="font-size:0.8rem; color:{TEXT_MUTED}; margin-top:6px;">
                {_html.escape(body)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def alert_banner_html(icon, title, plate, camera_id, timestamp, severity, compact=False):
    """
    icon is accepted for backwards compatibility but intentionally unused —
    the design uses a colored severity dot/badge instead of emoji.
    compact=True renders a slimmer row for secondary items in a list under
    a hero alert.
    """
    color = {"HIGH": BAD, "CRITICAL": BAD, "MEDIUM": WARN, "LOW": GOOD}.get((severity or "").upper(), WARN)
    pad = "9px 14px" if compact else "12px 16px"
    title_size = "0.78rem" if compact else "0.85rem"
    plate_size = "0.95rem" if compact else "1.1rem"
    return f"""
    <div style="background:{SURFACE}; border:1px solid {color}55; border-left:4px solid {color};
                border-radius:8px; padding:{pad}; margin-bottom:8px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="font-size:{title_size}; font-weight:800; color:{TEXT};">
                {_html.escape(title)}
            </div>
            {severity_badge(severity)}
        </div>
        <div style="font-size:{plate_size}; font-weight:700; color:{TEXT}; margin-top:6px; font-family:monospace;">
            {_html.escape(str(plate)) if plate else ""}
        </div>
        <div style="font-size:0.75rem; color:{TEXT_MUTED}; margin-top:4px;">
            {_html.escape(str(camera_id) if camera_id else "")} &nbsp;·&nbsp; {_html.escape(str(timestamp) if timestamp else "")}
        </div>
    </div>
    """


def hero_alert_card_html(title, plate, detail_line, meta_line, severity):
    """
    A single, large, unmissable card for the single most severe active
    alert — the "something requires attention right now" moment at the
    top of the Alerts tab. Everything else renders underneath as compact
    alert_banner_html rows so the hero doesn't have to compete visually.
    """
    color = {"HIGH": BAD, "CRITICAL": BAD, "MEDIUM": WARN, "LOW": GOOD}.get((severity or "").upper(), WARN)
    detail_html = (
        f'<div style="font-size:0.85rem; color:{TEXT_MUTED}; margin-top:8px;">{_html.escape(str(detail_line))}</div>'
        if detail_line else ""
    )
    meta_html = (
        f'<div style="font-size:0.78rem; color:{TEXT_MUTED}; margin-top:10px;">{_html.escape(str(meta_line))}</div>'
        if meta_line else ""
    )
    return f"""
    <div style="background:{SURFACE}; border:1px solid {color}66; border-left:5px solid {color};
                border-radius:12px; padding:22px 26px; margin-bottom:14px;
                box-shadow:0 0 0 1px {color}22;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="width:9px; height:9px; border-radius:50%; background:{color};
                             display:inline-block; box-shadow:0 0 8px {color};"></span>
                <span style="font-size:0.78rem; font-weight:800; color:{TEXT_MUTED}; letter-spacing:0.06em;">
                    {_html.escape(title)}
                </span>
            </div>
            {severity_badge(severity)}
        </div>
        <div style="font-size:1.9rem; font-weight:800; color:{TEXT}; margin-top:10px; font-family:monospace; letter-spacing:0.02em;">
            {_html.escape(str(plate)) if plate else "UNKNOWN"}
        </div>
        {detail_html}
        {meta_html}
    </div>
    """


def alerts_hero_header(count):
    """Big 'N ACTIVE ALERTS' heading used above the alert cards."""
    label = "ACTIVE ALERT" if count == 1 else "ACTIVE ALERTS"
    color = BAD if count > 0 else GOOD
    return (
        f'<div style="display:flex; align-items:baseline; gap:10px; margin:2px 0 14px 0;">'
        f'<span style="font-size:1.6rem; font-weight:800; color:{color};">{count}</span>'
        f'<span style="font-size:0.85rem; font-weight:700; color:{TEXT_MUTED}; letter-spacing:0.04em;">{label}</span>'
        f'</div>'
    )
