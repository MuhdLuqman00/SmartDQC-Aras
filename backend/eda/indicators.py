"""
Nutrition indicator computation for KKM child nutrition dashboard.

Strategy (WHO 2006 first):
  1. If WHO z-scores are available (waz, haz, baz computed), use z-score-derived
     indicator flags as the primary source.
  2. If z-scores are missing (no anthropometric data), fall back to source status
     labels from the mapped columns.
  3. Always compute BOTH sources and report discrepancies.

KKM indicators required (per spec):
  1. Peratus kanak-kanak kurang berat badan  (WAZ < -2, Weight-for-Age)
  2. Peratus kanak-kanak bantut              (HAZ < -2, Height-for-Age)
  3. Peratus kanak-kanak susut               (BAZ < -2, BMI-for-Age)
  4. Peratus kanak-kanak berlebihan berat badan & obes (BAZ > +2, BMI-for-Age)

Age groups: bawah 2 tahun, bawah 5 tahun
Geo levels:  Negeri, Kawasan/Bahagian (Sabah & Sarawak), Daerah
Cross-cuts:  Negeri × Jantina, Negeri × Pendapatan, Tahun (trend)
"""

import pandas as pd
import numpy as np


# ─── INDICATOR DEFINITIONS ────────────────────────────────────────────────────

INDICATORS = {
    "kurang_berat_badan": {
        "label":       "Kurang Berat Badan (Weight-for-Age, WAZ < -2)",
        "zscore_col":  "ind_kurang_berat_zscore",
        "label_col":   "ind_kurang_berat_label",  # fallback from source labels
    },
    "bantut": {
        "label":       "Bantut (Height-for-Age, HAZ < -2)",
        "zscore_col":  "ind_bantut_zscore",
        "label_col":   "ind_bantut_label",
    },
    "susut": {
        "label":       "Susut / Wasted (BMI-for-Age, BAZ < -2)",
        "zscore_col":  "ind_susut_zscore",
        "label_col":   "ind_susut_label",
    },
    "obes_berlebihan": {
        "label":       "Berlebihan Berat Badan & Obes (BMI-for-Age, BAZ > +2)",
        "zscore_col":  "ind_obes_zscore",
        "label_col":   "ind_obes_label",
    },
}

AGE_GROUPS = {
    "bawah_2_tahun": lambda d: d[d["age_months_computed"] < 24]
                      if "age_months_computed" in d.columns else d,
    "bawah_5_tahun": lambda d: d[d["age_months_computed"] < 60]
                      if "age_months_computed" in d.columns else d,
}
AGE_LABELS = {
    "bawah_2_tahun": "Bawah 2 Tahun (< 24 bulan)",
    "bawah_5_tahun": "Bawah 5 Tahun (< 60 bulan)",
}


# ─── LABEL-BASED INDICATOR FLAGS (fallback) ────────────────────────────────────

def _add_label_based_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Compute indicator flags from source status labels (fallback path)."""
    # Normalise to lowercase for comparison
    for col in ["status_berat", "status_tinggi", "status_bmi"]:
        if col in df.columns:
            df[f"{col}_norm"] = df[col].astype(str).str.strip().str.lower()

    if "status_berat_norm" in df.columns:
        df["ind_kurang_berat_label"] = df["status_berat_norm"].isin(
            ["kurang berat badan", "sangat kurang berat badan"])
    else:
        df["ind_kurang_berat_label"] = False

    if "status_tinggi_norm" in df.columns:
        df["ind_bantut_label"] = df["status_tinggi_norm"].isin(["bantut", "bantut teruk"])
    else:
        df["ind_bantut_label"] = False

    if "status_bmi_norm" in df.columns:
        df["ind_susut_label"] = df["status_bmi_norm"].isin(["susut", "susut teruk"])
        df["ind_obes_label"]  = df["status_bmi_norm"].isin(
            ["berlebihan berat badan", "obes", "risiko berlebihan berat badan"])
    else:
        df["ind_susut_label"] = False
        df["ind_obes_label"]  = False

    return df


def _resolve_indicator_col(df: pd.DataFrame, ind_meta: dict) -> str | None:
    """Return the best available indicator column name (z-score preferred)."""
    zscore_col = ind_meta["zscore_col"]
    label_col  = ind_meta["label_col"]
    if zscore_col in df.columns and df[zscore_col].notna().sum() > 0:
        return zscore_col
    if label_col in df.columns:
        return label_col
    return None


# ─── AGGREGATION HELPERS ──────────────────────────────────────────────────────

def _geo_agg(df_sub: pd.DataFrame, geo_col: str, ind_col: str) -> list:
    if geo_col not in df_sub.columns or ind_col not in df_sub.columns:
        return []
    grp = df_sub.groupby(geo_col)[ind_col].agg(["sum", "count"]).reset_index()
    grp.columns = [geo_col, "n_affected", "n_total"]
    grp["pct"] = (grp["n_affected"] / grp["n_total"] * 100).round(2)
    return grp.sort_values("pct", ascending=False).to_dict(orient="records")


def _cross_agg(df_sub: pd.DataFrame, col1: str, col2: str, ind_col: str) -> list:
    if not all(c in df_sub.columns for c in [col1, col2, ind_col]):
        return []
    grp = df_sub.groupby([col1, col2])[ind_col].agg(["sum", "count"]).reset_index()
    grp.columns = [col1, col2, "n_affected", "n_total"]
    grp["pct"] = (grp["n_affected"] / grp["n_total"] * 100).round(2)
    return grp.to_dict(orient="records")


def _trend_agg(df_sub: pd.DataFrame, ind_col: str) -> list:
    if "tahun_ukur" not in df_sub.columns or ind_col not in df_sub.columns:
        return []
    grp = df_sub.groupby("tahun_ukur")[ind_col].agg(["sum", "count"]).reset_index()
    grp.columns = ["tahun_ukur", "n_affected", "n_total"]
    grp["pct"] = (grp["n_affected"] / grp["n_total"] * 100).round(2)
    return grp.sort_values("tahun_ukur").to_dict(orient="records")


# ─── TRAJECTORY (MYVASS YEAR-ON-YEAR) ─────────────────────────────────────────

def compute_trajectory(df: pd.DataFrame) -> dict:
    """
    For MYVASS data with multiple years per child (id_cleaned + tahun_ukur),
    compute the trajectory of each indicator per child (improving/worsening/stable).
    Requires: id_cleaned, tahun_ukur, and at least one indicator column.
    """
    result = {}
    id_col = "id_cleaned"
    yr_col = "tahun_ukur"
    if id_col not in df.columns or yr_col not in df.columns:
        return result
    if not df[df["is_valid_ic"]].shape[0]:
        return result

    valid = df[df["is_valid_ic"]].copy()

    for ind_key, ind_meta in INDICATORS.items():
        ind_col = _resolve_indicator_col(valid, ind_meta)
        if ind_col is None:
            continue

        pivot = valid[[id_col, yr_col, ind_col]].dropna()
        if pivot.empty:
            continue

        # Get unique year pairs
        pivot = pivot.sort_values(yr_col)
        transitions = {"improved": 0, "worsened": 0, "stable_affected": 0, "stable_ok": 0}

        for child_id, group in pivot.groupby(id_col):
            group = group.sort_values(yr_col)
            years = group[yr_col].tolist()
            flags = group[ind_col].astype(bool).tolist()
            for i in range(1, len(flags)):
                if flags[i - 1] and not flags[i]:
                    transitions["improved"] += 1
                elif not flags[i - 1] and flags[i]:
                    transitions["worsened"] += 1
                elif flags[i - 1] and flags[i]:
                    transitions["stable_affected"] += 1
                else:
                    transitions["stable_ok"] += 1

        n_children = int(pivot[id_col].nunique())
        result[ind_key] = {
            "n_children_tracked": n_children,
            "transitions": transitions,
            "note": "Berdasarkan kanak-kanak yang mempunyai rekod multi-tahun",
        }
    return result


# ─── MAIN INDICATOR COMPUTATION ───────────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> dict:
    """
    Compute KKM nutrition indicators using WHO z-scores as primary source,
    falling back to source label columns. Returns nested dict:
      results[age_key][ind_key] = { overall, by_negeri, by_daerah, ... }
    """
    # Ensure label-based flags are present as fallback
    df = _add_label_based_flags(df)

    results = {}
    for age_key, age_filter in AGE_GROUPS.items():
        results[age_key] = {}
        df_age = age_filter(df)
        n_age  = len(df_age)

        for ind_key, ind_meta in INDICATORS.items():
            ind_col = _resolve_indicator_col(df_age, ind_meta)
            source  = "zscore"  if ind_col == ind_meta["zscore_col"] else "source_label"

            if ind_col is None or n_age == 0:
                results[age_key][ind_key] = {
                    "label": ind_meta["label"],
                    "source": "none",
                    "overall": {"n_total": n_age, "n_affected": 0, "pct": 0},
                }
                continue

            n_aff = int(df_age[ind_col].sum()) if ind_col in df_age.columns else 0
            pct   = round(n_aff / n_age * 100, 2) if n_age > 0 else 0

            results[age_key][ind_key] = {
                "label":   ind_meta["label"],
                "source":  source,
                "overall": {
                    "n_total": int(n_age),
                    "n_affected": n_aff,
                    "pct": pct,
                },
                "by_negeri":            _geo_agg(df_age, "negeri",           ind_col),
                "by_kawasan_bahagian":  _geo_agg(df_age, "kawasan_bahagian", ind_col),
                "by_daerah":            _geo_agg(df_age, "daerah",           ind_col),
                "by_negeri_jantina":    _cross_agg(df_age, "negeri", "jantina",    ind_col),
                "by_negeri_pendapatan": _cross_agg(df_age, "negeri", "pendapatan", ind_col),
                "by_tahun":             _trend_agg(df_age, ind_col),
                # National income breakdown
                "by_pendapatan": _geo_agg(df_age, "pendapatan", ind_col),
            }

    return results
