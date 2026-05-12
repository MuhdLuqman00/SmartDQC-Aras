"""
EDA Pipeline Orchestrator — run_eda()
Coordinates all analysis modules. The full cleaned DataFrame is stored as
private keys (_cleaned_data, _cleaned_columns) and stripped before the
public /eda/run response. Export endpoints re-run EDA to get the full data.
"""

import re
import pandas as pd
import numpy as np
import math

from ..config import (
    STANDARD_SCHEMA, NULL_SENTINELS, BMI_GROUPED_MAP,
    auto_suggest_mapping, detect_source_type,
)
from ..utils.ic_validator import validate_ic, analyze_and_deduplicate_ids
from ..utils.normaliser  import (
    normalise_gender, normalise_income, normalise_assessment,
    run_spelling_checks, severity_score,
)
from ..utils.age import add_age_columns
from ..utils.geo import add_geo_columns
from .who_zscore    import add_who_zscores, zscore_mismatch_report
from .outliers      import detect_outliers, flag_outliers
from .missing       import compute_missing_values, apply_null_strategy
from .numerical     import compute_numerical_summary
from .categorical   import compute_categorical_summary
from .bmi           import check_bmi_consistency
from .indicators    import compute_indicators, compute_trajectory
from .quality       import compute_quality_score
from .completeness  import compute_data_completeness
from .charts        import build_chart_blocks


# ─── JSON SAFE HELPER ─────────────────────────────────────────────────────────

def json_safe(obj):
    if obj is None: return None
    if isinstance(obj, dict):  return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):  return [json_safe(v) for v in obj]
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, (np.integer,)):  return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, (np.bool_,)):    return bool(obj)
    if isinstance(obj, (np.ndarray,)):  return json_safe(obj.tolist())
    try:
        if pd.isna(obj): return None
    except (ValueError, TypeError): pass
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat() if pd.notna(obj) else None
    return obj



# ─── SMART COLUMN TYPE INFERENCE ──────────────────────────────────────────────

def _infer_col_type(col_name: str, series: pd.Series, n_rows: int) -> str:
    """Infer a human-readable column type for profiling."""
    name_lower = col_name.lower()

    # Identifier heuristics (by name)
    id_keywords = ["_ic", "birth_ic", "mykid", "nric", "no_ic", " ic",
                   "patient_id", "child_id", "id_", "_id"]
    if name_lower in ("id",) or any(x in name_lower for x in id_keywords):
        return "identifier"

    # Date heuristics (by name)
    if any(x in name_lower for x in ["tarikh", "date", "dob", "birthdate"]):
        return "date"

    # Purely numeric dtype
    if series.dtype.kind in ("i", "u", "f"):
        n_unique = int(series.nunique())
        return "categorical" if n_unique <= 20 else "numerical"

    # Object/string columns — sample-based inference
    sample = series.dropna().astype(str).head(300)
    if len(sample) == 0:
        return "text"

    # Try numeric
    n_numeric = pd.to_numeric(sample, errors="coerce").notna().sum()
    if n_numeric / len(sample) > 0.75:
        n_unique = int(series.nunique())
        return "categorical" if n_unique <= 30 else "numerical"

    # Try date (quick heuristic on small sample)
    try:
        parsed = pd.to_datetime(sample.head(40), errors="coerce",
                                dayfirst=True, format="mixed")
        if parsed.notna().sum() / len(parsed.head(40)) > 0.7:
            return "date"
    except Exception:
        pass

    # Low cardinality → categorical
    n_unique = int(series.nunique())
    if n_unique <= 30 or (n_rows > 100 and n_unique / n_rows < 0.04):
        return "categorical"

    # High cardinality strings with lots of unique values → text/free-form
    return "text"


# ─── TABLEAU PREP ANALYSIS ────────────────────────────────────────────────────

def _build_tableau_prep(df: pd.DataFrame, report: dict, mapping: dict,
                        source_type: str) -> dict:
    """Analyse the data and produce a Tableau Prep readiness checklist."""
    n_rows = len(df)
    mapped = report.get("mapped_fields", [])
    has = lambda col: col in df.columns  # noqa

    # ── Data Grain ─────────────────────────────────────────────────────────
    id_col = next((c for c in ["id", "id_cleaned"] if has(c)), None)
    unique_ids = int(df[id_col].nunique()) if id_col else None
    if source_type == "myvass":
        grain_desc = "1 row = 1 child (wide format — multiple year columns per child)"
        grain_note = "Needs PIVOT to long format before Tableau: one row per child per measurement year."
    elif unique_ids and n_rows > 0 and (n_rows / max(unique_ids, 1)) > 1.5:
        visits_per_child = round(n_rows / max(unique_ids, 1), 1)
        grain_desc = f"1 row = 1 child visit ({visits_per_child:.1f} records per child on average)"
        grain_note = (
            "Multiple visits per child. For child-level analysis in Tableau, "
            "add LOD calc or filter to latest visit."
        )
    else:
        grain_desc = "1 row = 1 child measurement"
        grain_note = "Grain looks good for Tableau — one record per child."

    # ── Required Transforms (checked against what runner already applied) ──
    transforms = []

    def tfm(label, field_hint, status, description, priority="required"):
        transforms.append({
            "label": label, "field": field_hint, "status": status,
            "description": description, "priority": priority,
        })

    # Pivot
    if source_type == "myvass":
        tfm("Wide → Long Pivot", "year columns", "needed",
            "MyVASS data is wide-format. Must pivot so each row is one measurement year.", "critical")
    else:
        tfm("Wide → Long Pivot", "—", "not_required",
            "Klinik data is already long-format.", "info")

    # Date parsing
    date_cols = [c for c in ["tarikh_lahir", "tarikh_ukur", "tarikh_antropometri"] if has(c)]
    if date_cols:
        tfm("Parse Date Fields", ", ".join(date_cols), "done",
            "Date columns parsed to datetime format for age computation.", "critical")
    else:
        tfm("Parse Date Fields", "tarikh_lahir, tarikh_ukur", "needed",
            "No date columns mapped — cannot compute age or group by time period.", "critical")

    # Age computation
    if has("age_months_computed"):
        tfm("Compute Age in Months", "age_months_computed", "done",
            "Age in months computed from date_of_birth to measurement_date.")
    else:
        tfm("Compute Age in Months", "tarikh_lahir + tarikh_ukur", "needed",
            "Required for WHO z-score lookup and KKM age-group classification.")

    # Age group
    if has("age_group_computed"):
        tfm("Age Group Classification", "age_group_computed", "done",
            "Classified into 'Bawah 2 Tahun' and 'Bawah 5 Tahun' per KKM standard.")
    else:
        tfm("Age Group Classification", "age_months_computed", "needed",
            "Required to filter KKM indicators by age group.")

    # BMI
    if has("bmi"):
        tfm("BMI Calculation", "bmi", "done",
            "BMI computed from weight and height (kg / m²).")
    elif has("berat_kg") and has("tinggi_cm"):
        tfm("BMI Calculation", "berat_kg + tinggi_cm", "done",
            "BMI will be computed from weight and height.")
    else:
        tfm("BMI Calculation", "berat_kg, tinggi_cm", "needed",
            "Weight and/or height not mapped — BMI cannot be computed.", "critical")

    # WHO z-scores
    if has("waz") and has("haz") and has("baz"):
        pct = report.get("data_completeness", {}).get("pct_zscore_complete", 0)
        tfm("WHO 2006 Z-Scores", "waz, haz, baz", "done",
            f"Z-scores computed for {pct}% of records. Required for KKM indicator flags.")
    else:
        tfm("WHO 2006 Z-Scores", "berat_kg, tinggi_cm, tarikh_lahir, tarikh_ukur, jantina",
            "needed",
            "Z-scores (WAZ/HAZ/BAZ) needed for KKM indicator classification.", "critical")

    # KKM indicator flags
    if has("ind_kurang_berat_zscore") or has("ind_kurang_berat"):
        tfm("KKM Indicator Flags", "ind_kurang_berat, ind_bantut, ind_susut, ind_obes",
            "done", "4 KKM indicator columns added (0/1 per child per visit).")
    else:
        tfm("KKM Indicator Flags", "—", "needed",
            "Indicator columns missing — z-scores must be computed first.", "critical")

    # IC deduplication
    if id_col and unique_ids and n_rows > unique_ids:
        tfm("Deduplicate by Child IC", "id_cleaned", "needed",
            f"{n_rows - unique_ids:,} extra records vs unique children. "
            "Dedup to latest visit per child for prevalence analysis.",
            "recommended")
    elif id_col:
        tfm("Deduplicate by Child IC", "id_cleaned", "done",
            "Each child appears once — no deduplication needed.")

    # Geo hierarchy
    if has("kawasan_bahagian"):
        tfm("Geo Hierarchy (Kawasan/Bahagian)", "kawasan_bahagian", "done",
            "Sabah Kawasan and Sarawak Bahagian computed from Daerah.")
    elif has("negeri") and has("daerah"):
        tfm("Geo Hierarchy (Kawasan/Bahagian)", "negeri + daerah", "needed",
            "For Tableau drill-down: Negeri → Kawasan/Bahagian → Daerah hierarchy.",
            "recommended")

    # Vaccine grouping (klinik only)
    if source_type == "klinik" and has("vaccine_name"):
        n_vaccines = int(df["vaccine_name"].nunique())
        tfm("Vaccine Name Grouping", "vaccine_name", "needed" if n_vaccines > 10 else "optional",
            f"{n_vaccines} distinct vaccine names. Group into categories for Tableau filter.",
            "recommended")

    # ── Calculated Fields Tableau Will Need ───────────────────────────────
    calc_fields = [
        {"field": "Age Band",
         "formula": "IF [age_months_computed] <= 24 THEN 'Bawah 2 Tahun' ELSE 'Bawah 5 Tahun' END",
         "notes": "For KKM indicator age-group filter"},
        {"field": "WAZ Band",
         "formula": "IF [waz] < -3 THEN 'Severely Underweight' ELSEIF [waz] < -2 THEN 'Underweight' ELSEIF [waz] <= 2 THEN 'Normal' ELSE 'Overweight' END",
         "notes": "Weight-for-age classification label"},
        {"field": "HAZ Band",
         "formula": "IF [haz] < -3 THEN 'Severely Stunted' ELSEIF [haz] < -2 THEN 'Stunted' ELSE 'Normal' END",
         "notes": "Height-for-age classification label"},
        {"field": "BAZ Band",
         "formula": "IF [baz] < -2 THEN 'Wasted' ELSEIF [baz] <= 2 THEN 'Normal' ELSE 'Overweight/Obese' END",
         "notes": "BMI-for-age classification label"},
        {"field": "Measurement Year",
         "formula": "YEAR([tarikh_ukur])",
         "notes": "For time trend analysis"},
        {"field": "Measurement Quarter",
         "formula": "DATETRUNC('quarter', [tarikh_ukur])",
         "notes": "For quarterly trend charts"},
    ]
    if source_type == "klinik" and has("vaccine_name"):
        calc_fields.append({
            "field": "Has Measurement (flag)",
            "formula": "IF [berat_kg] > 0 AND [tinggi_cm] > 0 THEN 1 ELSE 0 END",
            "notes": "Filter out vaccination-only visits with no anthropometric data",
        })

    # ── Potential Join Keys (multi-source) ────────────────────────────────
    join_keys = []
    if id_col:
        n_valid_ic = int(df.get("is_valid_ic", pd.Series(dtype=bool)).sum()) if has("is_valid_ic") else None
        join_keys.append({
            "field": "id_cleaned",
            "description": "12-digit IC/MyKid — primary key for joining MyVASS + Klinik",
            "valid_count": n_valid_ic,
            "note": "Both sources must have IC column to join. 26% null in BIRTH_IC (Klinik) may limit join coverage.",
        })

    # ── Summary stats ─────────────────────────────────────────────────────
    n_done     = sum(1 for t in transforms if t["status"] == "done")
    n_needed   = sum(1 for t in transforms if t["status"] == "needed")
    n_critical = sum(1 for t in transforms if t["status"] == "needed" and t["priority"] == "critical")

    return {
        "data_grain": grain_desc,
        "grain_note": grain_note,
        "row_count":  n_rows,
        "unique_id_count": unique_ids,
        "transforms_done":    n_done,
        "transforms_needed":  n_needed,
        "critical_blockers":  n_critical,
        "transforms":   transforms,
        "calculated_fields": calc_fields,
        "join_keys":    join_keys,
        "source_type":  source_type,
    }



def myvass_wide_to_long(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot NCDC/TASKA wide-format (one row = one child, columns per year) to long."""
    id_cols   = [c for c in df.columns if not re.match(r"^(2023|2024|2025|2026)\s", str(c))]
    year_cols = [c for c in df.columns if re.match(r"^(2023|2024|2025|2026)\s", str(c))]
    if not year_cols:
        return df

    rows = []
    for _, row in df.iterrows():
        for year in ["2023", "2024", "2025", "2026"]:
            yr_cols = {c: row[c] for c in year_cols if str(c).startswith(year + " ")}
            if all(pd.isna(v) or str(v).strip() == "" for v in yr_cols.values()):
                continue
            new_row = {c: row[c] for c in id_cols}
            new_row["tahun_ukur"] = year
            for c, v in yr_cols.items():
                # Strip year prefix: "2025 Berat (kg)" -> "Berat (kg)"
                suffix = str(c).replace(f"{year} ", "", 1).strip()
                # Normalize to snake_case matching standard schema
                new_key = (
                    suffix.lower()
                    .replace("tarikh pengukuran", "tarikh_ukur")
                    .replace("berat (kg)", "berat_kg")
                    .replace("tinggi (cm)", "tinggi_cm")
                    .replace("panjang (cm)", "panjang_cm")
                    .replace("status berat", "status_berat")
                    .replace("status tinggi", "status_tinggi")
                    .replace("status bmi", "status_bmi")
                    .replace(" ", "_")
                    .replace("(", "").replace(")", "")
                )
                new_row[new_key] = v
            rows.append(new_row)
    return pd.DataFrame(rows) if rows else df


# ─── MAIN EDA FUNCTION ────────────────────────────────────────────────────────

def run_eda(df: pd.DataFrame, mapping: dict, source_type: str,
            config: dict = None) -> dict:
    """
    Run the complete EDA pipeline on the given DataFrame.
    mapping: {standard_field: raw_column_name}
    config: Processing configuration dict with keys:
        - outlier_action: 'remove', 'flag', or 'keep'
        - missing_strategy: 'exclude' or 'fallback'
        - normalize_spelling: bool
    Returns a report dict. Private keys (_cleaned_data, _cleaned_columns) hold
    the full cleaned dataset for download endpoints.
    """
    # Default config
    if config is None:
        config = {}
    outlier_action = config.get('outlier_action', 'flag')
    missing_strategy = config.get('missing_strategy', 'exclude')
    normalize_spelling = config.get('normalize_spelling', True)
    
    report = {
        "source_type":          source_type,
        "total_rows":           len(df),
        "total_columns":        len(df.columns),
        "missing_values":       {},
        "ic_validation":        {},
        "ic_audit_rows":        [],
        "id_analysis":          {},
        "column_types":         {},
        "spelling_issues":      {},
        "zscore_mismatch":      {},
        "duplicates":           {},
        "age_distribution":     {},
        "numerical_summary":    {},
        "categorical_summary":  {},
        "bmi_consistency":      {},
        "outliers":             {},
        "data_completeness":    {},
        "data_quality_score":   {},
        "indicators":           {},
        "trajectory":           {},
        "charts":               {},
        "tableau_prep":         {},
        "changes_applied":      [],
        "cleaned_preview":      [],
        "aggregated_preview":   [],
        "deduplicated_preview": [],
        "mapped_fields":        [],
        "unmapped_critical_fields": [],
    }

    # ── NCDC Wide-to-Long Pivot (BEFORE renaming) ────────────────────────────
    # Check if we have year-prefixed columns indicating wide format
    year_cols = [c for c in df.columns if re.match(r"^(2023|2024|2025|2026)\s", str(c))]
    if year_cols and source_type == "myvass":
        report["changes_applied"].append(
            f"Pivoted wide-format NCDC data from {len(df)} rows to long format "
            f"(found {len(year_cols)} year-prefixed columns)")
        df = myvass_wide_to_long(df)
        report["total_rows"] = len(df)
        
        # Update mapping to handle new column names after pivot
        # After pivot, year prefix is stripped: "2025 Berat (kg)" -> "berat_kg"
        # We need to remap based on the new column names
        new_cols = df.columns.tolist()
        from ..config import auto_suggest_mapping
        new_mapping = auto_suggest_mapping(new_cols, source_type)
        # Merge with original mapping, preferring new mapping for pivoted columns
        mapping.update({k: v for k, v in new_mapping.items() if v})

    # ── Rename columns per mapping ────────────────────────────────────────────
    inv_map = {v: k for k, v in mapping.items() if v}
    df = df.rename(columns=inv_map)

    # ── Mapping coverage ──────────────────────────────────────────────────────
    from ..config import CORE_FIELDS
    report["mapped_fields"]            = [f for f in STANDARD_SCHEMA if f in df.columns]
    report["n_mapped_standard"]        = len(report["mapped_fields"])
    report["unmapped_critical_fields"] = [f for f in CORE_FIELDS if f not in df.columns]

    # ── Wide-to-long for MYVASS ───────────────────────────────────────────────
    year_cols = [c for c in df.columns if re.match(r"^(2023|2024|2025|2026)", c)]
    if year_cols and source_type == "myvass":
        n_before = len(df)
        df = myvass_wide_to_long(df)
        n_after = len(df)
        report["changes_applied"].append({
            "action": "myvass_wide_to_long",
            "description": f"Format lebar → panjang: {n_before} baris → {n_after} baris",
            "column": "tahun_ukur",
            "before": {"n_rows": n_before}, "after": {"n_rows": n_after},
            "impact_pct": None, "rows_affected": n_after,
        })

    # ── Column profiling ──────────────────────────────────────────────────────
    n_rows_profile = len(df)
    for col in df.columns:
        inferred = _infer_col_type(col, df[col], n_rows_profile)
        report["column_types"][col] = {
            "original_dtype": str(df[col].dtype),
            "inferred": inferred,
            "unique_values": int(df[col].nunique()),
            "sample_values": df[col].dropna().astype(str).unique()[:5].tolist(),
        }

    # ── Sentinel → NaN ────────────────────────────────────────────────────────
    df = df.replace(r'^\s*$', np.nan, regex=True)
    for marker in NULL_SENTINELS:
        if marker:
            df = df.replace(marker, np.nan)

    # ── Compute BMI if missing ─────────────────────────────────────────────────
    if "berat_kg" in df.columns and "tinggi_cm" in df.columns and "bmi" not in df.columns:
        w = pd.to_numeric(df["berat_kg"], errors="coerce")
        h = pd.to_numeric(df["tinggi_cm"], errors="coerce")
        mask = w.notna() & h.notna() & (h > 0)
        df["bmi"] = np.nan
        df.loc[mask, "bmi"] = (w[mask] / ((h[mask] / 100) ** 2)).round(3)
        n_computed = int(mask.sum())
        report["changes_applied"].append({
            "action": "bmi_computed",
            "description": f"BMI dikira dari berat/tinggi untuk {n_computed} rekod",
            "column": "bmi",
            "before": {"bmi_column": "tidak wujud"},
            "after":  {"n_computed": n_computed},
            "impact_pct": round(n_computed / len(df) * 100, 1) if len(df) else 0,
            "rows_affected": n_computed,
        })

    # ── Outlier Detection & Flagging ──────────────────────────────────────────
    # Detect outliers using biological ranges + IQR method
    outlier_analysis = detect_outliers(df, method='biological+iqr')
    report["outliers"] = outlier_analysis
    
    # Flag outliers
    df = flag_outliers(df, method='biological')
    n_outliers = df.get('flag_outlier_any', pd.Series([False] * len(df))).sum()
    
    # Handle outliers based on config
    if outlier_action == 'remove' and n_outliers > 0:
        from .outliers import remove_outliers
        df_before_removal = len(df)
        df = remove_outliers(df, method='biological')
        df_after_removal = len(df)
        report["changes_applied"].append({
            "action": "outliers_removed",
            "description": f"{df_before_removal - df_after_removal} outlier rows removed (biological ranges)",
            "column": "flag_outlier_any",
            "before": {"n_rows": df_before_removal},
            "after": {"n_rows": df_after_removal},
            "impact_pct": round((df_before_removal - df_after_removal) / df_before_removal * 100, 1) if df_before_removal else 0,
            "rows_affected": df_before_removal - df_after_removal,
        })
    elif n_outliers > 0:
        report["changes_applied"].append({
            "action": "outliers_flagged",
            "description": f"{n_outliers} outlier rows flagged (biological ranges) — not removed",
            "column": "flag_outlier_any",
            "before": {},
            "after": {"n_flagged": int(n_outliers)},
            "impact_pct": round(n_outliers / len(df) * 100, 1) if len(df) else 0,
            "rows_affected": int(n_outliers),
        })

    # ── Missing values (before any normalisation) ──────────────────────────────
    report["missing_values"] = compute_missing_values(df)

    # ── IC validation ──────────────────────────────────────────────────────────
    if "id" in df.columns:
        ic_results  = df["id"].apply(validate_ic)
        valid_count = sum(1 for r in ic_results if r["valid"])
        issues      = {}
        for r in ic_results:
            if not r["valid"]:
                issues[r["issue"]] = issues.get(r["issue"], 0) + 1

        report["ic_validation"] = {
            "total":     len(df),
            "valid":     valid_count,
            "invalid":   len(df) - valid_count,
            "pct_valid": round(valid_count / len(df) * 100, 2) if len(df) else 0,
            "issue_breakdown": issues,
            "severity":  "high"   if valid_count / max(len(df), 1) < 0.5
                         else "medium" if valid_count / max(len(df), 1) < 0.8 else "low",
            "severity_score": severity_score(100 - round(valid_count / max(len(df), 1) * 100, 2)),
        }
        df["id_cleaned"] = [r["cleaned"] for r in ic_results]
        df, dedup_df = analyze_and_deduplicate_ids(df, report)
        report["deduplicated_preview"] = json_safe(
            dedup_df.head(50).replace({np.nan: None}).to_dict(orient="records"))
        report["changes_applied"].append({
            "action": "ic_cleaned",
            "description": f"Cleaned {len(df) - valid_count} non-standard IC numbers",
            "column": "id",
            "before": {"invalid_count": len(df) - valid_count},
            "after":  {"id_cleaned": "12-digit IC extracted"},
            "impact_pct": round((len(df) - valid_count) / len(df) * 100, 1) if len(df) else 0,
            "rows_affected": len(df) - valid_count,
        })
        # ── IC Audit: capture actual bad rows for analyst review ──────────────
        bad_mask = pd.Series([not r["valid"] for r in ic_results], index=df.index)
        if bad_mask.any():
            audit_cols = ["id", "id_cleaned", "id_type"] + \
                         [c for c in ["nama", "jantina", "tarikh_lahir", "negeri"] if c in df.columns]
            audit_df = df.loc[bad_mask, audit_cols].copy()
            audit_df["issue"] = [r["issue"] for r in ic_results if not r["valid"]]
            audit_df["original_value"] = df.loc[bad_mask, "id"].astype(str).values
            report["ic_audit_rows"] = json_safe(
                audit_df.head(200).replace({np.nan: None}).to_dict(orient="records"))

    # ── Gender normalisation ───────────────────────────────────────────────────
    if "jantina" in df.columns:
        original_vals = df["jantina"].value_counts().to_dict()
        df["jantina"] = df["jantina"].apply(normalise_gender)
        after_vals    = df["jantina"].value_counts().to_dict()
        non_std = {k: v for k, v in original_vals.items()
                   if str(k).strip() not in ("M", "F")}
        if non_std:
            report["spelling_issues"]["jantina"] = {"non_standard_values": non_std, "after_normalisation": after_vals}
            report["changes_applied"].append({
                "action": "gender_normalised",
                "description": f"Jantina dinormalisasi ke M/F — {sum(non_std.values())} nilai ditukar",
                "column": "jantina",
                "before": original_vals, "after": after_vals,
                "impact_pct": round(sum(non_std.values()) / len(df) * 100, 1) if len(df) else 0,
                "rows_affected": sum(non_std.values()),
            })

    # ── Income normalisation ───────────────────────────────────────────────────
    if "pendapatan" in df.columns:
        before_vals = df["pendapatan"].value_counts().to_dict()
        df["pendapatan"] = df["pendapatan"].apply(normalise_income)
        report["changes_applied"].append({
            "action": "income_normalised",
            "description": "Pendapatan dinormalisasi ke B40/M40/T20",
            "column": "pendapatan",
            "before": before_vals,
            "after":  df["pendapatan"].value_counts().to_dict(),
            "impact_pct": None,
            "rows_affected": int(df["pendapatan"].notna().sum()),
        })

    # ── Assessment normalisation ───────────────────────────────────────────────
    if "status_assessment" in df.columns:
        df["status_assessment"] = df["status_assessment"].apply(normalise_assessment)

    # ── Spelling checks on status columns ─────────────────────────────────────
    sp_issues = run_spelling_checks(df)
    report["spelling_issues"].update(sp_issues)

    # ── BMI grouped column ────────────────────────────────────────────────────
    if "status_bmi" in df.columns:
        df["status_bmi_grouped"] = (
            df["status_bmi"].astype(str).str.strip().str.lower()
            .map(BMI_GROUPED_MAP).fillna("lain-lain")
        )

    # ── Duplicates ────────────────────────────────────────────────────────────
    dup_cols = [c for c in ["id", "tarikh_ukur", "tahun_ukur"] if c in df.columns]
    if dup_cols:
        n_dups = int(df.duplicated(subset=dup_cols).sum())
        report["duplicates"] = {
            "duplicate_rows":           n_dups,
            "duplicate_check_columns":  dup_cols,
            "pct_duplicate":            round(n_dups / len(df) * 100, 2) if len(df) else 0,
            "before_count":             len(df),
            "after_dedup_count":        len(df) - n_dups,
        }
        if n_dups > 0:
            report["changes_applied"].append({
                "action": "duplicates_flagged",
                "description": f"{n_dups} baris duplikat dikesan",
                "column": ", ".join(dup_cols),
                "before": {"n_rows": len(df)},
                "after":  {"n_rows": len(df) - n_dups},
                "impact_pct": round(n_dups / len(df) * 100, 1) if len(df) else 0,
                "rows_affected": n_dups,
            })

    # ── Tahun_ukur from date ───────────────────────────────────────────────────
    if "tahun_ukur" not in df.columns and "tarikh_ukur" in df.columns:
        dt = pd.to_datetime(df["tarikh_ukur"], errors="coerce", dayfirst=True, format="mixed")
        df["tahun_ukur"] = dt.dt.year
        n_valid = int(df["tahun_ukur"].notna().sum())
        report["changes_applied"].append({
            "action": "tahun_ukur_extracted",
            "description": f"Tahun pengukuran diekstrak dari tarikh_ukur ({n_valid} rekod)",
            "column": "tahun_ukur", "before": {}, "after": {"n_valid": n_valid},
            "impact_pct": None, "rows_affected": n_valid,
        })

    # ── Age computation + date validation ─────────────────────────────────────
    df = add_age_columns(df, report, report["changes_applied"])

    # ── Geo hierarchy ──────────────────────────────────────────────────────────
    df = add_geo_columns(df, report["changes_applied"])

    # ── Null strategy ──────────────────────────────────────────────────────────
    df = apply_null_strategy(df, report["changes_applied"])

    # ── BMI consistency ───────────────────────────────────────────────────────
    report["bmi_consistency"] = check_bmi_consistency(df, threshold=bmi_threshold)

    # ── WHO z-scores (primary classification source) ───────────────────────────
    df = add_who_zscores(df)
    report["zscore_mismatch"] = zscore_mismatch_report(df)

    # ── Analytical summaries ──────────────────────────────────────────────────
    report["numerical_summary"]   = compute_numerical_summary(df)
    report["categorical_summary"] = compute_categorical_summary(df)
    report["data_completeness"]   = compute_data_completeness(df)

    # ── KKM Indicators ────────────────────────────────────────────────────────
    if any(c in df.columns for c in ["status_berat", "status_tinggi", "status_bmi",
                                     "waz", "haz", "baz"]):
        report["indicators"] = compute_indicators(df)
        report["trajectory"] = compute_trajectory(df)

    # ── Chart blocks ──────────────────────────────────────────────────────────
    report["charts"] = build_chart_blocks(df)

    # ── Aggregated Tableau-ready flat table (NO ROW CAP) ──────────────────────
    from ..export.tableau import build_aggregated_table
    report["aggregated_preview"] = build_aggregated_table(report)[:100]  # preview only
    report["_aggregated_full"]   = build_aggregated_table(report)        # used by export

    # ── Tableau Prep analysis ──────────────────────────────────────────────────
    report["tableau_prep"] = _build_tableau_prep(df, report, mapping, source_type)

    # ── Quality score ──────────────────────────────────────────────────────────
    report["data_quality_score"] = compute_quality_score(report, df)

    # ── Cleaned preview ───────────────────────────────────────────────────────
    exclude_suffixes = ("_norm", "_dt", "_was_null")
    preview_cols = [c for c in df.columns
                    if not any(c.endswith(s) for s in exclude_suffixes)]
    clean_df = df[preview_cols].where(df[preview_cols].notna(), other=None)
    report["cleaned_preview"]  = json_safe(clean_df.head(50).to_dict(orient="records"))
    report["_cleaned_data"]    = json_safe(clean_df.to_dict(orient="records"))
    report["_cleaned_columns"] = preview_cols

    return report
