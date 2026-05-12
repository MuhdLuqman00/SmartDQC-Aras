import re
import pandas as pd


# ─── IC VALIDATION ─────────────────────────────────────────────────────────────

def validate_ic(ic_val) -> dict:
    """
    Validate a Malaysian NRIC / MyKid number.
    Returns dict with keys: valid, issue, cleaned, type
    """
    if pd.isna(ic_val) or str(ic_val).strip() in ["", "<NA>", "nan", "NaN", "None"]:
        return {"valid": False, "issue": "missing", "cleaned": None, "type": "missing"}

    raw = str(ic_val).strip()

    # Handle scientific notation (e.g. 2.21E+11)
    if re.match(r"^\d+\.?\d*[Ee][+\-]?\d+$", raw):
        try:
            raw = str(int(float(raw)))
        except Exception:
            return {"valid": False, "issue": "scientific_notation_unconvertible",
                    "cleaned": None, "type": "invalid"}

    # Starts with a letter → system_id (e.g. DEPOTSDK0021) — do NOT try to fix
    if re.match(r"[A-Za-z]", raw):
        return {"valid": False, "issue": "system_id", "cleaned": None, "type": "system_id"}

    # Detect embedded text: digits followed by letters then more content
    # e.g. "8905241251RAFIZAH BINTI MOHD ALI44" — extract only leading digit run
    leading_digits = re.match(r"^(\d+)", raw)
    has_embedded_text = bool(re.search(r"\d[A-Za-z]", raw))

    if has_embedded_text and leading_digits:
        # Only take the leading digit sequence, not digits scattered throughout
        candidate = leading_digits.group(1)
        if len(candidate) >= 12:
            digits_only = candidate[:12]
        else:
            digits_only = candidate
        return {
            "valid": False,
            "issue": "embedded_text_after_digits",
            "cleaned": digits_only if len(digits_only) == 12 else None,
            "type": "corrupted_ic",
        }

    # Strip common suffix variants: _1, _2, -1
    base = re.split(r"[_\-]", raw)[0]
    digits_only = re.sub(r"\D", "", base)

    if len(digits_only) == 12:
        try:
            yy = digits_only[0:2]
            mm = int(digits_only[2:4])
            dd = int(digits_only[4:6])
            if not (1 <= mm <= 12):
                return {"valid": False, "issue": "invalid_month_in_ic",
                        "cleaned": digits_only, "type": "invalid_ic"}
            if not (1 <= dd <= 31):
                return {"valid": False, "issue": "invalid_day_in_ic",
                        "cleaned": digits_only, "type": "invalid_ic"}
            _ = yy  # suppress unused warning
        except Exception:
            return {"valid": False, "issue": "date_parse_error",
                    "cleaned": digits_only, "type": "invalid_ic"}
        return {"valid": True, "issue": None, "cleaned": digits_only, "type": "valid_ic"}

    elif len(digits_only) < 12:
        return {
            "valid": False,
            "issue": f"too_short_{len(digits_only)}_digits",
            "cleaned": digits_only if digits_only else None,
            "type": "short_id",
        }
    else:
        return {
            "valid": False,
            "issue": f"too_long_{len(digits_only)}_digits",
            "cleaned": digits_only[:12],
            "type": "invalid_ic",
        }


def analyze_and_deduplicate_ids(df: pd.DataFrame, report: dict):
    """
    Classify all IC values, add id_cleaned / id_type / is_valid_ic columns.
    Returns (df, dedup_df) — always a 2-tuple.
    """
    if "id" not in df.columns:
        return df, df.copy()

    results = df["id"].apply(validate_ic)
    df["id_cleaned"] = [r["cleaned"] for r in results]
    df["id_type"]    = [r["type"]    for r in results]
    df["is_valid_ic"] = df["id_type"] == "valid_ic"

    type_counts     = df["id_type"].value_counts().to_dict()
    unique_children = int(df[df["is_valid_ic"]]["id_cleaned"].nunique())

    child_counts = (
        df[df["is_valid_ic"]]
        .groupby("id_cleaned")
        .size()
        .reset_index(name="n_records")
    )
    multi_records = int((child_counts["n_records"] > 1).sum())

    # Dedup — keep the latest measurement per cleaned IC
    dedup_df = df.copy()
    if "tarikh_ukur" in df.columns:
        dedup_df["_tarikh_ukur_dt"] = pd.to_datetime(
            df["tarikh_ukur"], errors="coerce")
        dedup_df = (
            dedup_df.sort_values("_tarikh_ukur_dt")
            .drop_duplicates(subset=["id_cleaned"], keep="last")
            .drop(columns=["_tarikh_ukur_dt"])
        )

    report["id_analysis"] = {
        "total_records": len(df),
        "valid_ic_records": int(df["is_valid_ic"].sum()),
        "unique_children": unique_children,
        "children_with_multiple_records": multi_records,
        "id_type_distribution": type_counts,
        "note": "Dedup berdasarkan id_cleaned (IC 12 digit). Rekod tarikh_ukur terbaru disimpan.",
    }

    report["changes_applied"].append({
        "action": "id_classification_and_dedup_ready",
        "description": f"{unique_children} kanak-kanak unik dari {len(df)} rekod",
        "column": "id_cleaned",
        "before": {"total_records": len(df)},
        "after":  {"unique_children": unique_children},
        "impact_pct": round((1 - unique_children / len(df)) * 100, 1) if len(df) else 0,
        "rows_affected": len(df),
    })
    return df, dedup_df
