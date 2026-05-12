import pandas as pd


def compute_data_completeness(df: pd.DataFrame) -> dict:
    critical  = [c for c in ["berat_kg", "tinggi_cm", "bmi"] if c in df.columns]
    important = [c for c in ["negeri", "daerah", "jantina", "pendapatan"] if c in df.columns]
    n = len(df)

    n_missing_anthro = int(df[critical].isnull().any(axis=1).sum()) if critical else 0
    complete_cases   = (int(df[critical + important].dropna().shape[0])
                        if (critical + important) else n)

    coverage_by_negeri = []
    if "negeri" in df.columns and critical and "is_missing_critical" in df.columns:
        grp = (df.groupby("negeri")["is_missing_critical"]
               .agg(["sum", "count"])
               .reset_index())
        grp.columns = ["negeri", "n_missing", "n_total"]
        grp["pct_complete"] = ((1 - grp["n_missing"] / grp["n_total"]) * 100).round(1)
        coverage_by_negeri = grp.sort_values("pct_complete").to_dict(orient="records")

    # Z-score completeness
    n_zscore_complete = 0
    if all(c in df.columns for c in ["waz", "haz", "baz"]):
        n_zscore_complete = int(df[["waz", "haz", "baz"]].notna().all(axis=1).sum())

    return {
        "total_rows": n,
        "complete_cases": complete_cases,
        "pct_complete": round(complete_cases / n * 100, 1) if n > 0 else 0,
        "missing_critical_rows": n_missing_anthro,
        "pct_missing_critical": round(n_missing_anthro / n * 100, 1) if n > 0 else 0,
        "critical_fields_checked": critical,
        "coverage_by_negeri": coverage_by_negeri,
        "zscore_complete_rows": n_zscore_complete,
        "pct_zscore_complete": round(n_zscore_complete / n * 100, 1) if n > 0 else 0,
        "note": (
            "Rekod dengan berat/tinggi/BMI hilang dikecualikan dari pengiraan indikator. "
            "Z-skor WHO 2006 memerlukan berat + tinggi + umur + jantina."
        ),
    }
