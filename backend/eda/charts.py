import pandas as pd
import numpy as np

COLORS = ['#38d9c0', '#8b5cf6', '#faad14', '#ef4444', '#3b82f6',
          '#10b981', '#f97316', '#ec4899', '#06b6d4', '#a855f7']


def normalize_for_charts(df: pd.DataFrame, source_type: str = None) -> pd.DataFrame:
    """Rename mixed-case cleaner columns to lowercase canonical names, derive the
    age prerequisite, and add WHO z-scores — the full pre-chart normalisation.

    Called in two contexts:
    - /charts/blocks endpoint: the cached cleaned frame carries mixed-case
      columns (Berat_kg, Tinggi_cm, Tarikh_Lahir, Age_Months) with NO lowercase
      analytic columns. Pass source_type to apply the rename + age derivation so
      add_who_zscores can compute waz/haz/baz, *_class, and ind_*_zscore — which
      in turn unlock the z-score distribution/scatter/class-pie and trend_by_year
      charts (the 12 that were silently lost before).
    - run_eda: df is already renamed to lowercase and add_age_columns has already
      produced age_months_computed; omit source_type. The age derivation below is
      guarded on "missing", so run_eda's existing column is left untouched and
      only add_who_zscores runs — behaviour identical to before.

    The rename uses auto_suggest_mapping (same as run_eda_auto), so both paths
    normalise identically. Duplicate labels after rename are deduplicated (keeps
    first occurrence), mirroring run_eda's dedup guard.
    """
    if source_type:
        from ..config import auto_suggest_mapping
        mapping = auto_suggest_mapping(list(df.columns), source_type) or {}
        inv_map = {v: k for k, v in mapping.items() if v and v in df.columns and v != k}
        if inv_map:
            df = df.rename(columns=inv_map)
            if df.columns.duplicated().any():
                df = df.loc[:, ~df.columns.duplicated()]

    # The cached cleaned frame lacks three lowercase derived columns that
    # build_chart_blocks (and add_who_zscores) read. run_eda creates each one
    # BEFORE calling this helper, so every derivation below is guarded on
    # "missing" — run_eda's own columns are left untouched and only the
    # endpoint path (which has none of them) does the work. Mirrors the exact
    # logic in runner.py (add_age_columns / lines 588, 617).

    # 1. age_months_computed — sole prerequisite for add_who_zscores (the cached
    #    frame ships Age_Months, not the lowercase canonical name). Unlocks all
    #    z-score distribution/scatter/class-pie + the ind_*_zscore trend inputs.
    if "age_months_computed" not in df.columns and {"tarikh_lahir", "tarikh_ukur"}.issubset(df.columns):
        from ..utils.age import calc_age_months
        tl = pd.to_datetime(df["tarikh_lahir"], errors="coerce", dayfirst=True, format="mixed")
        tu = pd.to_datetime(df["tarikh_ukur"], errors="coerce", dayfirst=True, format="mixed")
        df["age_months_computed"] = [calc_age_months(a, b) for a, b in zip(tl, tu)]

    # 2. tahun_ukur — required by trend_by_year (mirrors runner.py:617).
    if "tahun_ukur" not in df.columns and "tarikh_ukur" in df.columns:
        dt = pd.to_datetime(df["tarikh_ukur"], errors="coerce", dayfirst=True, format="mixed")
        df["tahun_ukur"] = dt.dt.year

    # 3. status_bmi_grouped — feeds status_bmi_pie for the general/school_age path
    #    (mirrors runner.py:588). Suppressed for wide_multiyear/wide_registry inside build_chart_blocks.
    if "status_bmi_grouped" not in df.columns and "status_bmi" in df.columns:
        from ..config import BMI_GROUPED_MAP
        df["status_bmi_grouped"] = (
            df["status_bmi"].astype(str).str.strip().str.lower()
            .map(BMI_GROUPED_MAP).fillna("lain-lain")
        )

    from .who_zscore import add_who_zscores
    return add_who_zscores(df)


def build_chart_blocks(df: pd.DataFrame, source_type: str = None) -> dict:
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

    # ── Status BMI grouped pie (general schema only — wide_multiyear/wide_registry use WHO z-score charts) ──
    _zscore_schemas = {"wide_multiyear", "wide_registry"}
    if "status_bmi_grouped" in df.columns and source_type not in _zscore_schemas:
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

    # Per-indicator assessable denominator: the count of children for whom
    # THIS indicator could actually be computed. The ind_* flag columns are
    # booleans (False — never null — when not assessable), so counting them
    # just yields all rows and is useless as a denominator. The WHO class
    # columns ARE null when the z-score can't be computed, so their non-null
    # count is the true denominator; fall back to the source status label for
    # label-only schemas. This lets the frontend show an exact per-indicator
    # prevalence instead of dividing every indicator by the same n_total.
    _denom_sources = {
        "bantut":       ["haz_class", "status_tinggi_norm", "status_tinggi"],
        "kurang_berat": ["waz_class", "status_berat_norm", "status_berat"],
        "susut":        ["baz_class", "status_bmi_norm", "status_bmi"],
        "obes":         ["baz_class", "status_bmi_norm", "status_bmi"],
    }

    if "tahun_ukur" in df.columns and active_ind:
        agg_dict: dict = {"n_total": (active_ind[0], "count")}
        for ic in active_ind:
            short = ic.replace("_zscore", "").replace("_label", "").replace("ind_", "")
            agg_dict[short] = (ic, "sum")
            denom_col = next(
                (c for c in _denom_sources.get(short, []) if c in df.columns), None)
            if denom_col is not None:
                agg_dict[f"{short}_n"] = (denom_col, "count")
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

    # ── Vaccine distribution (only if a vaccine column is present) ────────────
    if "vaccine_name" in df.columns:
        vc = df["vaccine_name"].value_counts().head(12)
        charts["vaccine_distribution"] = [
            {"vaccine": k, "count": int(v)} for k, v in vc.items()]

    return charts
