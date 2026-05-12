import pandas as pd
import numpy as np
from ..config import CORE_FIELDS


def compute_quality_score(report: dict, df: pd.DataFrame) -> dict:
    """
    7-dimension quality score (total 100 pts):
      field_coverage    20  — core schema fields mapped
      ic_validity       15  — IC / MyKid validity rate
      missing_critical  20  — missing in anthropometric / status fields
      duplicates        15  — duplicate rows
      bmi_consistency   10  — BMI recalculation match
      spelling           5  — unrecognised status values
      zscore_coverage   15  — proportion with computable WHO z-scores (NEW)
    """
    score = 100
    breakdown = {}

    # ── FIELD COVERAGE ────────────────────────────────────────────────────────
    mapped_core = [f for f in CORE_FIELDS if f in df.columns]
    n_mapped    = len(mapped_core)
    n_total     = len(CORE_FIELDS)
    cov_score   = round(n_mapped / n_total * 20, 1)
    score      -= (20 - cov_score)
    breakdown["field_coverage"] = {
        "score": cov_score, "max": 20,
        "n_mapped": n_mapped, "n_total": n_total,
        "unmapped": [f for f in CORE_FIELDS if f not in df.columns],
    }

    # ── IC VALIDITY ───────────────────────────────────────────────────────────
    ic = report.get("ic_validation", {})
    if ic.get("total", 0) > 0:
        pct_valid = ic.get("pct_valid", 100)
        ic_score  = round(pct_valid * 0.15, 1)
        score    -= (15 - ic_score)
        breakdown["ic_validity"] = {
            "score": ic_score, "max": 15, "pct_valid": pct_valid}
    elif "id" not in df.columns:
        score -= 15
        breakdown["ic_validity"] = {
            "score": 0, "max": 15, "note": "Kolum ID tidak dipetakan"}
    else:
        breakdown["ic_validity"] = {
            "score": 15, "max": 15, "note": "ID tidak berformat NRIC"}

    # ── MISSING CRITICAL ──────────────────────────────────────────────────────
    critical_cols = ["berat_kg", "tinggi_cm", "bmi",
                     "status_berat", "status_tinggi", "status_bmi"]
    mv            = report.get("missing_values", {})
    crit_present  = [c for c in critical_cols if c in df.columns]
    if not crit_present:
        score -= 20
        breakdown["missing_critical"] = {
            "score": 0, "max": 20, "note": "Tiada medan antropometrik/status dipetakan"}
    else:
        crit_pcts  = [mv[c]["pct_missing"] for c in crit_present if c in mv]
        avg_miss   = round(sum(crit_pcts) / len(crit_pcts), 1) if crit_pcts else 0
        miss_score = round(max(0, 20 - avg_miss * 0.4), 1)
        score     -= (20 - miss_score)
        breakdown["missing_critical"] = {
            "score": miss_score, "max": 20, "avg_pct_missing": avg_miss}

    # ── DUPLICATES ────────────────────────────────────────────────────────────
    dups      = report.get("duplicates", {})
    pct_dup   = dups.get("pct_duplicate", 0)
    dup_score = round(max(0, 15 - pct_dup * 1.5), 1)
    score    -= (15 - dup_score)
    breakdown["duplicates"] = {
        "score": dup_score, "max": 15, "pct_duplicate": pct_dup}

    # ── BMI CONSISTENCY ───────────────────────────────────────────────────────
    bmi_c = report.get("bmi_consistency", {})
    if bmi_c.get("checked"):
        pct_mis   = bmi_c.get("pct_mismatch", 0)
        bmi_score = round(max(0, 10 - pct_mis * 0.3), 1)
        score    -= (10 - bmi_score)
        breakdown["bmi_consistency"] = {
            "score": bmi_score, "max": 10, "pct_mismatch": pct_mis}
    else:
        breakdown["bmi_consistency"] = {
            "score": 10, "max": 10, "note": "Tidak dapat disemak (tiada berat/tinggi/bmi)"}

    # ── SPELLING ──────────────────────────────────────────────────────────────
    sp       = report.get("spelling_issues", {})
    n_spell  = sum(len(v) if isinstance(v, list) else 1 for v in sp.values())
    sp_score = round(max(0, 5 - n_spell * 0.5), 1)
    score   -= (5 - sp_score)
    breakdown["spelling"] = {
        "score": sp_score, "max": 5, "n_issues": n_spell}

    # ── WHO Z-SCORE COVERAGE (NEW) ────────────────────────────────────────────
    # Reward datasets where z-scores can be computed (need berat+tinggi+umur+jantina)
    n = len(df)
    zscore_cols = [c for c in ["waz", "haz", "baz"] if c in df.columns]
    if zscore_cols:
        pct_computable = round(
            df[zscore_cols].notna().all(axis=1).sum() / n * 100, 1) if n > 0 else 0
        zs_score = round(pct_computable * 0.15, 1)
        score   -= (15 - zs_score)
        breakdown["zscore_coverage"] = {
            "score": zs_score, "max": 15, "pct_computable": pct_computable,
            "note": "% rekod dengan WAZ+HAZ+BAZ berjaya dikira (WHO 2006)"}
    else:
        missing_req = [c for c in ["berat_kg", "tinggi_cm", "age_months_computed", "jantina"]
                       if c not in df.columns]
        score -= 15
        breakdown["zscore_coverage"] = {
            "score": 0, "max": 15,
            "note": f"Z-skor tidak dapat dikira. Medan hilang: {missing_req}"}

    final = max(0, min(100, round(score, 1)))
    grade = "A" if final >= 85 else "B" if final >= 70 else "C" if final >= 55 else "D"
    labels = {"A": "Sangat Baik", "B": "Baik", "C": "Sederhana", "D": "Lemah"}
    return {
        "score": final,
        "grade": grade,
        "label": labels[grade],
        "breakdown": breakdown,
    }
