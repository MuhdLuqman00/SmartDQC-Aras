import pandas as pd


def calc_age_months(dob, ref_date) -> float | None:
    try:
        if pd.isna(dob) or pd.isna(ref_date):
            return None
        dob = pd.to_datetime(dob)
        ref = pd.to_datetime(ref_date)
        return (ref.year - dob.year) * 12 + (ref.month - dob.month)
    except Exception:
        return None


def age_group_label(months) -> str | None:
    if months is None:
        return None
    if months < 12:  return "Bawah 1 Tahun (0–11 bulan)"
    if months < 24:  return "1 Tahun (12–23 bulan)"
    if months < 36:  return "2 Tahun (24–35 bulan)"
    if months < 48:  return "3 Tahun (36–47 bulan)"
    if months < 60:  return "4 Tahun (48–59 bulan)"
    return "5 Tahun ke atas (≥60 bulan)"


def add_age_columns(df: pd.DataFrame, report: dict, changes: list) -> pd.DataFrame:
    """Compute age, age group, measurement month/quarter, and out-of-range age flags."""
    if "tarikh_lahir" not in df.columns or "tarikh_ukur" not in df.columns:
        return df

    df["tarikh_lahir_dt"] = pd.to_datetime(
        df["tarikh_lahir"], errors="coerce", dayfirst=True, format="mixed")
    df["tarikh_ukur_dt"] = pd.to_datetime(
        df["tarikh_ukur"], errors="coerce", dayfirst=True, format="mixed")

    df["age_months_computed"] = df.apply(
        lambda r: calc_age_months(r["tarikh_lahir_dt"], r["tarikh_ukur_dt"]), axis=1
    )
    df["age_group_computed"] = df["age_months_computed"].apply(age_group_label)
    df["bulan_ukur"]  = df["tarikh_ukur_dt"].dt.month
    df["suku_tahun"]  = df["tarikh_ukur_dt"].dt.quarter.apply(
        lambda q: f"S{int(q)}" if pd.notna(q) else None
    )
    df["flag_bawah_2"]  = (df["age_months_computed"] < 24).fillna(False)
    df["flag_bawah_5"]  = (df["age_months_computed"] < 60).fillna(False)
    df["is_missing_age"] = df["age_months_computed"].isna()

    # Date sanity validation
    df["flag_date_invalid"] = (
        df["tarikh_ukur_dt"].notna() &
        df["tarikh_lahir_dt"].notna() &
        (df["tarikh_ukur_dt"] < df["tarikh_lahir_dt"])
    )
    # Flag future measurement dates (post today = April 2026)
    today = pd.Timestamp("2026-04-17")
    df["flag_date_future"] = df["tarikh_ukur_dt"].notna() & (df["tarikh_ukur_dt"] > today)

    n_invalid_date = int(df["flag_date_invalid"].sum())
    n_future_date  = int(df["flag_date_future"].sum())

    valid_ages = df["age_months_computed"].dropna()
    report["age_distribution"] = {
        "min_months":    float(valid_ages.min()) if len(valid_ages) else None,
        "max_months":    float(valid_ages.max()) if len(valid_ages) else None,
        "mean_months":   round(float(valid_ages.mean()), 1) if len(valid_ages) else None,
        "median_months": round(float(valid_ages.median()), 1) if len(valid_ages) else None,
        "age_group_counts": df["age_group_computed"].value_counts().to_dict(),
        "under_2_years": int((df["age_months_computed"] < 24).sum()),
        "under_5_years": int((df["age_months_computed"] < 60).sum()),
        "over_5_years":  int((df["age_months_computed"] >= 60).sum()),
        "missing_age":   int(df["is_missing_age"].sum()),
        "invalid_dates": n_invalid_date,
        "future_dates":  n_future_date,
    }

    if n_invalid_date > 0:
        changes.append({
            "action": "flag_invalid_dates",
            "description": f"{n_invalid_date} rekod: tarikh_ukur < tarikh_lahir (tidak logik)",
            "column": "flag_date_invalid",
            "before": {}, "after": {"n_flagged": n_invalid_date},
            "impact_pct": round(n_invalid_date / len(df) * 100, 1),
            "rows_affected": n_invalid_date,
        })

    if n_future_date > 0:
        changes.append({
            "action": "flag_future_dates",
            "description": f"{n_future_date} rekod: tarikh_ukur dalam masa hadapan",
            "column": "flag_date_future",
            "before": {}, "after": {"n_flagged": n_future_date},
            "impact_pct": round(n_future_date / len(df) * 100, 1),
            "rows_affected": n_future_date,
        })

    changes.append({
        "action": "age_and_date_parts_computed",
        "description": "Umur (bulan), kumpulan umur, bulan_ukur, suku_tahun dikira",
        "column": "age_months_computed",
        "before": {}, "after": {"n_valid_ages": int(len(valid_ages))},
        "impact_pct": None,
        "rows_affected": int(len(valid_ages)),
    })
    return df
