import pandas as pd
import numpy as np

COLORS = ['#38d9c0', '#8b5cf6', '#faad14', '#ef4444', '#3b82f6',
          '#10b981', '#f97316', '#ec4899', '#06b6d4', '#a855f7']


def build_chart_blocks(df: pd.DataFrame) -> dict:
    charts = {}

    # ── Histograms ────────────────────────────────────────────────────────────
    hist_cols = [
        ("bmi",                "BMI"),
        ("berat_kg",           "Berat (kg)"),
        ("tinggi_cm",          "Tinggi (cm)"),
        ("age_months_computed","Umur (bulan)"),
        ("waz",                "WAZ z-score"),
        ("haz",                "HAZ z-score"),
        ("baz",                "BAZ z-score"),
    ]
    for col, label in hist_cols:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(s) == 0:
            continue
        # For z-score columns use narrower bins
        bins = 14 if col in ("waz", "haz", "baz") else 20
        counts, edges = np.histogram(s, bins=bins)
        charts[f"{col}_distribution"] = {
            "label": label,
            "data": [
                {"range": f"{round(edges[i],1)}–{round(edges[i+1],1)}",
                 "count": int(counts[i])}
                for i in range(len(counts))
            ],
        }

    # ── Scatter plots ─────────────────────────────────────────────────────────
    scatter_pairs = [
        ("berat_kg",  "tinggi_cm",           "Berat vs Tinggi"),
        ("bmi",       "age_months_computed",  "BMI vs Umur"),
        ("waz",       "age_months_computed",  "WAZ vs Umur"),
        ("haz",       "age_months_computed",  "HAZ vs Umur"),
        ("baz",       "age_months_computed",  "BAZ vs Umur"),
    ]
    for xc, yc, title in scatter_pairs:
        if xc not in df.columns or yc not in df.columns:
            continue
        sub = df[[xc, yc]].dropna()
        if len(sub) == 0:
            continue
        if len(sub) > 3000:
            sub = sub.sample(3000, random_state=42)
        charts[f"scatter_{xc}_vs_{yc}"] = {
            "title":   title,
            "x_label": xc,
            "y_label": yc,
            "points":  [
                {"x": round(float(row[xc]), 3), "y": round(float(row[yc]), 3)}
                for _, row in sub.iterrows()
            ],
        }

    # ── Status BMI grouped pie ────────────────────────────────────────────────
    if "status_bmi_grouped" in df.columns:
        vc = df["status_bmi_grouped"].value_counts()
        charts["status_bmi_pie"] = [
            {"label": k, "count": int(v)} for k, v in vc.items()]

    # ── WHO z-score classification donut charts ───────────────────────────────
    for col, label in [("waz_class", "WAZ (Weight-for-Age)"),
                       ("haz_class", "HAZ (Height-for-Age)"),
                       ("baz_class", "BAZ (BMI-for-Age)")]:
        if col not in df.columns:
            continue
        vc = df[col].value_counts()
        charts[f"{col}_pie"] = {
            "label": label,
            "data":  [{"label": k, "count": int(v)} for k, v in vc.items()],
        }

    # ── Trend by year ─────────────────────────────────────────────────────────
    ind_cols = ["ind_bantut_zscore", "ind_obes_zscore",
                "ind_kurang_berat_zscore", "ind_susut_zscore",
                "ind_bantut_label",  "ind_obes_label",
                "ind_kurang_berat_label", "ind_susut_label"]
    active_ind = [c for c in ind_cols if c in df.columns]

    if "tahun_ukur" in df.columns and active_ind:
        agg_dict: dict = {"n_total": (active_ind[0], "count")}
        for ic in active_ind:
            short = ic.replace("_zscore", "").replace("_label", "").replace("ind_", "")
            agg_dict[short] = (ic, "sum")
        grp = df.groupby("tahun_ukur").agg(**agg_dict).reset_index()
        charts["trend_by_year"] = grp.replace({np.nan: None}).to_dict(orient="records")

    # ── Gender split ──────────────────────────────────────────────────────────
    if "jantina" in df.columns:
        vc = df["jantina"].value_counts()
        charts["gender_split"] = [{"label": k, "count": int(v)} for k, v in vc.items()]

    # ── Records by Negeri ─────────────────────────────────────────────────────
    if "negeri" in df.columns:
        vc = df["negeri"].value_counts().head(16)
        charts["records_by_negeri"] = [
            {"negeri": k, "count": int(v)} for k, v in vc.items()]

    # ── Income distribution ───────────────────────────────────────────────────
    if "pendapatan" in df.columns:
        vc = df["pendapatan"].value_counts()
        charts["income_split"] = [{"label": k, "count": int(v)} for k, v in vc.items()]

    # ── Vaccine distribution (klinik data) ───────────────────────────────────
    if "vaccine_name" in df.columns:
        vc = df["vaccine_name"].value_counts().head(12)
        charts["vaccine_distribution"] = [
            {"vaccine": k, "count": int(v)} for k, v in vc.items()]

    return charts
