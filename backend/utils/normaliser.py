import pandas as pd
from difflib import get_close_matches
from ..config import (
    GENDER_MAP, INCOME_MAP, STATUS_BERAT_VALID,
    STATUS_TINGGI_VALID, STATUS_BMI_VALID,
)


def normalise_gender(val):
    if pd.isna(val):
        return None
    return GENDER_MAP.get(str(val).strip().lower(), str(val).strip())


def normalise_income(val):
    if pd.isna(val):
        return None
    return INCOME_MAP.get(str(val).strip().lower(), str(val).strip())


def normalise_assessment(val):
    """Normalise assessment status — handle truncated values like 'Completec'."""
    if pd.isna(val):
        return None
    raw = str(val).strip()
    low = raw.lower()
    if low.startswith("complete"):
        return "Completed"
    if low.startswith("incompl") or low.startswith("tidak"):
        return "Incomplete"
    if low.startswith("pending") or low.startswith("belum"):
        return "Pending"
    return raw


def check_spelling(val, valid_set, field_name) -> dict:
    """Check if val is in valid_set, suggest closest match if not."""
    if pd.isna(val) or str(val).strip() == "":
        return {"original": val, "issue": "missing", "suggestion": None,
                "severity": "medium", "severity_score": 2}
    clean = str(val).strip().lower()
    if clean in valid_set:
        return {"original": val, "issue": None, "suggestion": None}
    matches = get_close_matches(clean, valid_set, n=1, cutoff=0.6)
    return {
        "original": val,
        "issue": f"unrecognised_{field_name}",
        "suggestion": matches[0] if matches else None,
        "severity": "high" if not matches else "medium",
        "severity_score": 4 if not matches else 2,
    }


def run_spelling_checks(df: pd.DataFrame) -> dict:
    """Run spelling checks on all status columns. Returns issues dict."""
    issues = {}
    checks = {
        "status_berat":  STATUS_BERAT_VALID,
        "status_tinggi": STATUS_TINGGI_VALID,
        "status_bmi":    STATUS_BMI_VALID,
    }
    for col, valid_set in checks.items():
        if col not in df.columns:
            continue
        col_issues = [
            check_spelling(val, valid_set, col)
            for val in df[col].dropna().unique()
            if check_spelling(val, valid_set, col)["issue"]
        ]
        if col_issues:
            issues[col] = col_issues
    return issues


def severity_score(pct_missing: float) -> int:
    if pct_missing >= 50: return 5
    if pct_missing >= 30: return 4
    if pct_missing >= 15: return 3
    if pct_missing >= 5:  return 2
    return 1
