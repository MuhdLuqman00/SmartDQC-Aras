"""Auto-selected chart generators for Feature #15 report generation.

Three charts keyed to the data always present in a SmartDQC report:
  chart_quality_bar        — quality dimensions horizontal bar
  chart_nutritional_rates  — indicator rates by district grouped bar
  chart_kpi_vs_target      — actual vs NPAN vs WHO target per KPI
Each function returns PNG bytes (or None if insufficient data).
"""
from __future__ import annotations

import io
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Palette mirrors frontend tokens.css light-theme --status-* tokens.
# Names retained so the chart functions stay unchanged.
_NAVY       = "#1B2A4A"   # primary fill / axis text
_NAVY_DARK  = "#0F1B2F"
_SKY        = "#2BB6A8"   # status-good      (Soft Teal)
_GOLD       = "#E9A23B"   # status-watch     (Warm Amber)
_BRICK      = "#E56B6F"   # status-critical  (Soft Coral Red)
_GRAY       = "#4A5568"
# Legacy aliases used by chart bodies — point to the new palette.
_TEAL       = _NAVY        # primary bar fill
_TEAL_DARK  = _NAVY_DARK
_AMBER      = _GOLD
_GREEN      = _SKY
_RED        = _BRICK

_FONT = "DejaVu Sans"


def _save(fig: plt.Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _apply_spine_style(ax: plt.Axes) -> None:
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#C8D8DC")
    ax.spines["bottom"].set_color("#C8D8DC")
    ax.tick_params(colors=_GRAY, labelsize=8)
    ax.set_facecolor("#FAFCFC")


# ---------------------------------------------------------------------------
# Chart 1 — Data Quality Dimensions bar
# ---------------------------------------------------------------------------

_QUALITY_DIM_LABELS = {
    "field_coverage":   "Field Coverage",
    "ic_validity":      "IC Validity",
    "missing_critical": "Critical Completeness",
    "duplicates":       "Uniqueness",
    "bmi_consistency":  "BMI Consistency",
    "spelling":         "Spelling",
    "zscore_coverage":  "Z-score Coverage",
}


def chart_quality_bar(eda_result: dict[str, Any]) -> bytes | None:
    """Horizontal bar chart of quality dimension scores.

    Reads data_quality_score.breakdown (run_eda's actual schema). Each
    dimension is normalised to a 0-100 percentage (score / max * 100) so
    bars with different point weights stay comparable. The legacy
    eda["quality"] dict this once read is never emitted by run_eda, so
    the chart always returned None / blank.
    """
    dq = eda_result.get("data_quality_score") or {}
    breakdown = dq.get("breakdown") or {}

    dims: dict[str, float] = {}
    for key, label in _QUALITY_DIM_LABELS.items():
        dim = breakdown.get(key)
        if not isinstance(dim, dict):
            continue
        score = dim.get("score")
        mx = dim.get("max")
        if score is None or not mx:
            continue
        dims[label] = round(float(score) / float(mx) * 100, 1)

    # Fall back to the composite score if the breakdown is unavailable.
    if not dims:
        overall = dq.get("score")
        if overall is None:
            return None
        dims["Overall Score"] = float(overall)

    labels = list(dims.keys())
    values = [dims[l] for l in labels]
    colors = [_GREEN if v >= 80 else _AMBER if v >= 60 else _RED for v in values]

    fig, ax = plt.subplots(figsize=(5.5, max(1.8, len(labels) * 0.45 + 0.6)))
    fig.patch.set_facecolor("#FFFFFF")
    bars = ax.barh(labels, values, color=colors, height=0.55, zorder=2)

    for bar, val in zip(bars, values):
        ax.text(
            min(val + 1.5, 97), bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}", va="center", ha="left",
            fontsize=8, color=_NAVY, fontname=_FONT,
        )

    ax.set_xlim(0, 110)
    ax.set_xlabel("Score (%)", fontsize=8, color=_GRAY, fontname=_FONT)
    ax.set_title("Data Quality Overview", fontsize=10, color=_TEAL_DARK,
                 fontweight="bold", fontname=_FONT, pad=8)
    ax.axvline(x=80, color=_TEAL, linewidth=0.7, linestyle="--", alpha=0.6, zorder=1)
    ax.text(80.5, len(labels) - 0.3, "Target 80", fontsize=7, color=_TEAL, fontname=_FONT)
    ax.invert_yaxis()
    _apply_spine_style(ax)
    ax.grid(axis="x", color="#E2EEF0", linewidth=0.5, zorder=0)
    fig.tight_layout(pad=0.8)
    return _save(fig)


# ---------------------------------------------------------------------------
# Chart 2 — Nutritional indicator rates by district (top 10 by stunting)
# ---------------------------------------------------------------------------

_INDICATOR_COLS = [
    ("stunting_rate_rate",    "Stunting"),
    ("wasting_rate_rate",     "Wasting"),
    ("underweight_rate_rate", "Underweight"),
    ("overweight_rate_rate",  "Overweight"),
]
_BAR_COLORS = [_TEAL, _AMBER, _NAVY, _RED]


def chart_nutritional_rates(kpi_result: dict[str, Any] | None) -> bytes | None:
    """Grouped horizontal bar chart of nutritional rates across districts (top 10)."""
    if not kpi_result:
        return None
    breakdown: list[dict] = kpi_result.get("district_breakdown") or []
    if not breakdown:
        return None

    sample = breakdown[0]
    present = [(col, lbl) for col, lbl in _INDICATOR_COLS if col in sample]
    if not present:
        return None

    sort_col = present[0][0]
    rows = sorted(breakdown, key=lambda r: r.get(sort_col) or 0, reverse=True)[:10]
    districts  = [r.get("district", "?") for r in rows]
    n_districts  = len(districts)
    n_indicators = len(present)

    bar_h = 0.7 / n_indicators
    y = np.arange(n_districts)

    fig, ax = plt.subplots(figsize=(6, max(2.5, n_districts * 0.4 + 1.0)))
    fig.patch.set_facecolor("#FFFFFF")

    for i, (col, lbl) in enumerate(present):
        vals   = [float(r.get(col) or 0) for r in rows]
        offset = (i - (n_indicators - 1) / 2) * bar_h
        bars   = ax.barh(y + offset, vals, height=bar_h * 0.88,
                         color=_BAR_COLORS[i % len(_BAR_COLORS)], label=lbl, zorder=2)
        for bar, val in zip(bars, vals):
            if val > 0:
                ax.text(
                    val + 0.3, bar.get_y() + bar.get_height() / 2,
                    f"{val:.1f}", va="center", ha="left",
                    fontsize=6.5, color=_NAVY, fontname=_FONT,
                )

    ax.set_yticks(y)
    ax.set_yticklabels(districts, fontsize=8, fontname=_FONT)
    ax.set_xlabel("Rate (%)", fontsize=8, color=_GRAY, fontname=_FONT)
    ax.set_title("Nutritional Indicator Rates by District", fontsize=10,
                 color=_TEAL_DARK, fontweight="bold", fontname=_FONT, pad=8)
    ax.invert_yaxis()
    ax.legend(fontsize=7, loc="lower right", framealpha=0.7)
    _apply_spine_style(ax)
    ax.grid(axis="x", color="#E2EEF0", linewidth=0.5, zorder=0)
    fig.tight_layout(pad=0.8)
    return _save(fig)


# ---------------------------------------------------------------------------
# Chart 3 — KPI actual vs NPAN target vs WHO target
# ---------------------------------------------------------------------------

_KPI_LABEL_MAP = {
    "stunting_rate":    "Stunting",
    "wasting_rate":     "Wasting",
    "underweight_rate": "Underweight",
    "overweight_rate":  "Overweight",
    "anaemia_rate":     "Anaemia",
}


def chart_kpi_vs_target(kpi_result: dict[str, Any] | None) -> bytes | None:
    """Grouped bar chart: actual vs NPAN target vs WHO target per KPI."""
    if not kpi_result:
        return None
    kpis: list[dict] = kpi_result.get("kpis") or []
    if not kpis:
        return None

    labels  = [_KPI_LABEL_MAP.get(k.get("kpi", ""), k.get("kpi", "?")) for k in kpis]
    actuals = [float(k.get("actual")     or 0) for k in kpis]
    npan    = [float(k.get("target")     or 0) for k in kpis]
    who     = [float(k.get("who_target") or 0) for k in kpis]

    n = len(labels)
    x = np.arange(n)
    w = 0.22

    fig, ax = plt.subplots(figsize=(max(4.5, n * 1.1 + 1.5), 3.8))
    fig.patch.set_facecolor("#FFFFFF")

    b1 = ax.bar(x - w, actuals, w, label="Actual",      color=_TEAL,  zorder=2)
    b2 = ax.bar(x,     npan,    w, label="NPAN Target", color=_AMBER, zorder=2)
    b3 = ax.bar(x + w, who,     w, label="WHO Target",  color=_NAVY,  alpha=0.75, zorder=2)

    for bars_set in (b1, b2, b3):
        for bar in bars_set:
            h = bar.get_height()
            if h > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2, h + 0.25,
                    f"{h:.1f}", ha="center", va="bottom",
                    fontsize=7, color=_NAVY, fontname=_FONT,
                )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, fontname=_FONT)
    ax.set_ylabel("Rate (%)", fontsize=8, color=_GRAY, fontname=_FONT)
    ax.set_title("KPI Achievement vs NPAN / WHO Targets", fontsize=10,
                 color=_TEAL_DARK, fontweight="bold", fontname=_FONT, pad=8)
    ax.legend(fontsize=7, framealpha=0.7)
    _apply_spine_style(ax)
    ax.grid(axis="y", color="#E2EEF0", linewidth=0.5, zorder=0)
    fig.tight_layout(pad=0.8)
    return _save(fig)
