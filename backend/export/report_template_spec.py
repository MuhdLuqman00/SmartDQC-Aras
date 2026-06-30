"""Report template constants — section labels, colours, targets, column defs."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Colours — Brand Navy palette (matches frontend tokens.css). Names retained
# (BRAND_TEAL, BRAND_TEAL_DARK, BRAND_TEAL_LIGHT) so report.py keeps working with
# zero re-wiring; the values now resolve to the navy palette.
# ---------------------------------------------------------------------------
BRAND_NAVY        = "#1B2A4A"   # primary surface (sidebar / section bars)
BRAND_NAVY_DARK   = "#0F1B2F"   # cover background / footer
BRAND_SKY         = "#2E4A7A"   # secondary accent
BRAND_GOLD        = "#C8962E"   # warm accent / highlights
BRAND_GOLD_LIGHT  = "#E8C77A"
BRAND_BG          = "#EEF2F8"   # page surface

# Legacy aliases — point to the new palette so report.py reskin is automatic.
BRAND_TEAL        = BRAND_NAVY        # was #00697A (teal)
BRAND_TEAL_DARK   = BRAND_NAVY_DARK   # was #004F5C
BRAND_TEAL_LIGHT  = BRAND_BG          # was #E6F4F5 (pale teal)

BRAND_WHITE       = "#FFFFFF"
BRAND_LIGHT_GRAY  = "#F1F4FA"
BRAND_MID_GRAY    = "#4A5568"
BRAND_RULE_LINE   = "#D8DFEC"

# Data-viz status palette — must mirror the frontend light-theme
# --status-* tokens so PDF/PPTX exports look like the on-screen UI.
STATUS_ON_TRACK  = "#2BB6A8"   # Soft Teal      (good)
STATUS_AT_RISK   = "#E9A23B"   # Warm Amber     (watch)
STATUS_OFF_TRACK = "#E56B6F"   # Soft Coral Red (critical)
STATUS_NEUTRAL   = "#8A94A6"   # grey fallback

# ---------------------------------------------------------------------------
# Section labels (BM / EN pairs)
# ---------------------------------------------------------------------------
SECTION_LABELS: dict[str, dict[str, str]] = {
    "cover": {
        "bm": "LAPORAN PEMAKANAN",
        "en": "NUTRITION REPORT",
    },
    "executive_summary": {
        "bm": "RINGKASAN EKSEKUTIF",
        "en": "EXECUTIVE SUMMARY",
    },
    "nutritional_status": {
        "bm": "STATUS PEMAKANAN MENGIKUT DAERAH",
        "en": "NUTRITIONAL STATUS BY DISTRICT",
    },
    "kpi_achievement": {
        "bm": "PENCAPAIAN KPI BERBANDING SASARAN NPAN / WHO",
        "en": "KPI ACHIEVEMENT VS NPAN / WHO TARGETS",
    },
    "trajectory": {
        "bm": "TRAJEKTORI & NARATIF DAERAH",
        "en": "DISTRICT TRAJECTORY & NARRATIVE",
    },
    "at_risk": {
        "bm": "SENARAI KANAK-KANAK BERISIKO",
        "en": "AT-RISK CHILDREN LIST",
    },
    "quality_overview": {
        "bm": "GAMBARAN KESELURUHAN KUALITI DATA",
        "en": "DATA QUALITY OVERVIEW",
    },
    "recommendations": {
        "bm": "CADANGAN TINDAKAN",
        "en": "RECOMMENDATIONS",
    },
    "indicator_table": {
        "bm": "JADUAL PETUNJUK MENGIKUT DAERAH",
        "en": "INDICATOR TABLE BY DISTRICT",
    },
    "methodology": {
        "bm": "LAMPIRAN METODOLOGI",
        "en": "METHODOLOGY APPENDIX",
    },
}

# ---------------------------------------------------------------------------
# Footer template
# ---------------------------------------------------------------------------
FOOTER_TEMPLATE = "{district} | LAPORAN SmartDQC {year} | {org}"

# ---------------------------------------------------------------------------
# KPI table column definitions
# ---------------------------------------------------------------------------
KPI_TABLE_HEADERS = {
    "bm": ["Petunjuk", "Sebenar (%)", "Sasaran NPAN (%)", "Sasaran WHO (%)", "Status NPAN", "Status WHO"],
    "en": ["Indicator",  "Actual (%)",  "NPAN Target (%)",  "WHO Target (%)",  "NPAN Status", "WHO Status"],
}

NUTRITIONAL_TABLE_HEADERS = {
    "bm": ["Daerah", "N", "Stunting %", "Wasting %", "Kurus %", "Berat Lebih %"],
    "en": ["District", "N", "Stunting %", "Wasting %", "Underweight %", "Overweight %"],
}

AT_RISK_TABLE_HEADERS = {
    "bm": ["No. IC", "Daerah", "Skor Risiko", "Tahap", "Bendera Utama"],
    "en": ["IC No.",  "District", "Risk Score",  "Level", "Top Flags"],
}

# ---------------------------------------------------------------------------
# Trajectory status -> label (BM / EN)
# ---------------------------------------------------------------------------
TRAJECTORY_STATUS_LABELS: dict[str, dict[str, str]] = {
    "On Track":  {"bm": "Menuju Sasaran",       "en": "On Track"},
    "At Risk":   {"bm": "Berisiko",             "en": "At Risk"},
    "Off Track": {"bm": "Tidak Menuju Sasaran", "en": "Off Track"},
}


def trajectory_color(status: str) -> str:
    return {
        "On Track":  STATUS_ON_TRACK,
        "At Risk":   STATUS_AT_RISK,
        "Off Track": STATUS_OFF_TRACK,
    }.get(status, STATUS_NEUTRAL)


# ---------------------------------------------------------------------------
# Methodology lines (bilingual)
# ---------------------------------------------------------------------------
METHODOLOGY_LINES = [
    "Sumber Data / Data Sources: myVASS, CCMS, KPM, NCDC",
    "Piawaian Z-Score / Z-Score Standard: WHO 2006 Child Growth Standards (WHO_Anthro v3.2.2)",
    "Klasifikasi / Classification: WAZ<-2 SD=Kurus; HAZ<-2 SD=Stunted; WHZ<-2 SD=Wasted",
    "Peraturan Kualiti / Quality Rules: organisation-defined completeness, consistency & range checks",
    "Pengesanan Anomali / Anomaly Detection: IsolationForest (contamination=0.05) + 3xIQR fence",
    "Pengkelasan Corak / Pattern Classification: Decimal shift, digit transposition, column swap",
    "Pemarkahan Risiko / Risk Scoring: Weighted flag-sum (Stunting x25, Wasting x30, Underweight x20)",
    "Penanda Aras / Benchmarks: NPAN 2021-2025 national targets; WHO Global Targets 2025",
    "Analisis Trend / Trend Analysis: Ordinary least-squares linear regression (>=3 periods)",
    "Trajektori / Trajectory: Forecasts 4 periods ahead; On Track if forecast <= NPAN target",
]
