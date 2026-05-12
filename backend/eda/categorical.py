import pandas as pd


def compute_categorical_summary(df: pd.DataFrame) -> dict:
    summary = {}
    cols = [
        "negeri", "daerah", "jantina", "pendapatan",
        "status_berat", "status_tinggi", "status_bmi",
        "age_group_computed", "vaccine_name", "status_assessment",
        "waz_class", "haz_class", "baz_class",
    ]
    for col in cols:
        if col not in df.columns:
            continue
        filled  = df[col].fillna("TIADA DATA")
        counts  = filled.value_counts(dropna=False)
        pcts    = (filled.value_counts(normalize=True, dropna=False) * 100).round(2)
        summary[col] = {
            "counts": counts.to_dict(),
            "pct":    pcts.to_dict(),
            "unique": int(df[col].nunique(dropna=True)),
        }
    return summary
