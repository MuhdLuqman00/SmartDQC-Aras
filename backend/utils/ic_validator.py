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


def extract_ic_gender_digit(ic_val):
    """Malaysian NRIC encodes sex in the final digit: odd = Male, even = Female.

    Returns "Male"/"Female" (matching canonical Gender), or None when the value
    is not a usable 12-digit NRIC. Reuses validate_ic for cleaning.
    """
    res = validate_ic(ic_val)
    cleaned = res.get("cleaned")
    if cleaned is None:
        return None
    s = str(cleaned)
    if len(s) != 12 or not s.isdigit():
        return None
    return "Male" if int(s[-1]) % 2 == 1 else "Female"


def extract_ic_birthdate(ic_val):
    """Malaysian NRIC encodes the birth date in the first six digits (YYMMDD).

    Returns a pd.Timestamp (date) or None when the value is not a usable
    12-digit NRIC with a valid embedded date. Century is inferred with a pivot
    at the current 2-digit year (00..pivot -> 2000s, else 1900s) — correct for
    an under-5 cohort whose ICs are issued in the 2000s/2010s/2020s.
    """
    res = validate_ic(ic_val)
    cleaned = res.get("cleaned")
    if cleaned is None:
        return None
    s = str(cleaned)
    if len(s) != 12 or not s.isdigit():
        return None
    yy, mm, dd = int(s[0:2]), int(s[2:4]), int(s[4:6])
    if not (1 <= mm <= 12 and 1 <= dd <= 31):
        return None
    pivot = pd.Timestamp.now().year % 100
    year = 2000 + yy if yy <= pivot else 1900 + yy
    try:
        return pd.Timestamp(year=year, month=mm, day=dd)
    except ValueError:
        return None


def analyze_and_deduplicate_ids(df: pd.DataFrame, report: dict):
    """
    Classify all IC values, add id_cleaned / id_type / is_valid_ic columns.
    Returns (df, dedup_df) — always a 2-tuple.
    """
    if "id" not in df.columns:
        return df, df.copy()

    id_series = df["id"].fillna("").astype(str).str.strip()

    # Fast path: vectorized check for clean 12-digit ICs (covers ~80% of rows)
    fast_mask = id_series.str.match(r"^\d{12}$", na=False)
    mm = pd.to_numeric(id_series.str[2:4], errors="coerce")
    dd = pd.to_numeric(id_series.str[4:6], errors="coerce")
    valid_date_mask = fast_mask & (mm >= 1) & (mm <= 12) & (dd >= 1) & (dd <= 31)

    id_cleaned = pd.Series(index=df.index, dtype=object)
    # dtype=object (not str/StringDtype): the slow path assigns a Python list
    # through a boolean mask below, which StringDtype's _putmask rejects with
    # "only integer scalar arrays can be converted to a scalar index".
    id_type    = pd.Series("", index=df.index, dtype=object)
    is_valid   = pd.Series(False, index=df.index, dtype=bool)

    id_cleaned[fast_mask]    = id_series[fast_mask]
    id_type[valid_date_mask] = "valid_ic"
    id_type[fast_mask & ~valid_date_mask] = "invalid_ic"
    is_valid[valid_date_mask] = True

    # Slow path: apply validate_ic only on rows that don't match the clean pattern
    slow_mask = ~fast_mask
    if slow_mask.any():
        slow_results = df.loc[slow_mask, "id"].apply(validate_ic)
        id_cleaned[slow_mask] = [r["cleaned"] for r in slow_results]
        id_type[slow_mask]    = [r["type"]    for r in slow_results]
        is_valid[slow_mask]   = [r["valid"]   for r in slow_results]

    df["id_cleaned"]  = id_cleaned
    df["id_type"]     = id_type
    df["is_valid_ic"] = is_valid

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
