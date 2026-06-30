"""Regression: /charts/blocks must produce the same chart keys as run_eda for a
raw (non-pre-baked) wide_multiyear-shaped fixture.

Root cause being guarded: the cleaned DataFrame cached by /clean/run carries
mixed-case columns (Berat_kg, Tinggi_cm) with no z-score classification cols.
/charts/blocks was calling build_chart_blocks() directly on this raw cache
entry, producing only 3-6 charts.  run_eda normalises via auto_suggest_mapping
+ add_who_zscores before building charts and produces ~19.

This test pins that normalize_for_charts(df, source_type) closes the gap so
both paths produce identical key sets.

Requires the WHO z-score Excel tables under data/zscore/ — skipped otherwise.
"""
import importlib
import os
import pathlib

import pandas as pd
import pytest

_ZDIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "zscore"
os.environ["WHO_ZSCORE_DIR"] = str(_ZDIR)

from backend.eda import who_zscore  # noqa: E402

importlib.reload(who_zscore)

pytestmark = pytest.mark.skipif(
    not who_zscore.ZSCORE_AVAILABLE,
    reason="WHO z-score tables not present — key-parity test requires real z-scores",
)


def _raw_wide_multiyear_df() -> pd.DataFrame:
    """Df shaped like the REAL /clean/run cache output for a wide multi-year file.

    This deliberately mirrors what clean_data() actually emits (verified against
    synthetic_wide_multiyear_12000.csv), NOT a convenience fixture:
      - Mixed-case canonical-mappable columns (Berat_kg, Tinggi_cm, BMI, Negeri).
      - Date columns the cleaner keeps (Tarikh_Lahir, Tarikh_Pengukuran) — NOT a
        pre-computed lowercase ``age_months_computed``.
      - The cleaner's own UPPERCASE analytic columns (Age_Months, WAZ, WAZ_Status)
        which build_chart_blocks does NOT read.
      - Two distinct measurement years so trend_by_year can aggregate.

    The earlier version of this fixture supplied a lowercase ``age_months_computed``
    and no pre-baked z-scores, which exercised the add_who_zscores fresh-compute
    path real cached frames never hit — so parity-equality passed while BOTH paths
    were silently missing the 12 z-score/trend charts. This fixture forces the
    real path: age must be DERIVED from the dates before z-scores can compute.
    """
    return pd.DataFrame(
        {
            "IC_NO_PASSPORT":    ["010101010001", "020202020002", "030303030003",
                                  "040404040004", "050505050005", "060606060006"],
            "Jantina":           ["L", "P", "L", "P", "L", "P"],
            "Tarikh_Lahir":      ["2021-01-15", "2020-06-10", "2021-03-20",
                                  "2020-09-05", "2021-02-12", "2020-11-30"],
            "Tarikh_Pengukuran": ["2023-06-20", "2023-07-11", "2023-08-02",
                                  "2024-06-18", "2024-07-09", "2024-08-21"],
            "Tahun_Ukur":        [2023, 2023, 2023, 2024, 2024, 2024],
            "Berat_kg":          [12.5, 14.0, 13.0, 15.5, 12.8, 16.0],
            "Tinggi_cm":         [88.0, 95.0, 91.0, 99.0, 89.0, 101.0],
            "BMI":               [16.1, 15.5, 15.7, 15.8, 16.1, 15.7],
            "Negeri":            ["Selangor", "Johor", "Selangor", "Sabah", "Johor", "Selangor"],
            # Cleaner's own UPPERCASE analytic columns — present but unread by charts.
            "Age_Months":        [29, 37, 28, 45, 41, 44],
            "WAZ":               [0.1, -0.5, 0.3, -1.2, 0.0, -0.8],
            "WAZ_Status":        ["Normal", "Normal", "Normal", "Normal", "Normal", "Normal"],
            "analyzable":        [True, True, True, True, True, True],
            "exclude_reason":    [None, None, None, None, None, None],
        }
    )


def test_charts_blocks_keys_match_run_eda():
    """After normalize_for_charts, /charts/blocks keys == run_eda keys (real-shaped)."""
    from backend.eda.charts import normalize_for_charts, build_chart_blocks
    from backend.eda.runner import run_eda_auto

    df = _raw_wide_multiyear_df()

    # Path A: normalize_for_charts(df, source_type) + build_chart_blocks
    # This simulates the /charts/blocks endpoint after the Phase 1 fix.
    normalized = normalize_for_charts(df.copy(), "wide_multiyear")
    blocks_keys = set(build_chart_blocks(normalized, source_type="wide_multiyear").keys())

    # Path B: run_eda_auto — the gold-standard path that already normalises.
    eda_keys = set(run_eda_auto(df.copy(), "wide_multiyear").get("charts", {}).keys())

    assert blocks_keys == eda_keys, (
        f"Chart key mismatch:\n"
        f"  Missing from /charts/blocks: {eda_keys - blocks_keys}\n"
        f"  Extra in  /charts/blocks:    {blocks_keys - eda_keys}"
    )


def test_charts_blocks_has_zscore_and_trend_charts():
    """normalize_for_charts must unlock the z-score AND trend_by_year charts.

    These are the exact charts that vanished before the fix — they depend on
    age_months_computed (derived from the dates) + tahun_ukur, neither of which
    a set-equality-only assertion would have caught if both paths were broken.
    """
    from backend.eda.charts import normalize_for_charts, build_chart_blocks

    df = _raw_wide_multiyear_df()
    normalized = normalize_for_charts(df.copy(), "wide_multiyear")
    blocks = build_chart_blocks(normalized, source_type="wide_multiyear")

    required = {
        "waz_distribution", "haz_distribution", "baz_distribution",
        "waz_class_pie",    "haz_class_pie",    "baz_class_pie",
        "scatter_waz_vs_age_months_computed",
        "trend_by_year",
    }
    missing = required - set(blocks.keys())
    assert not missing, f"Charts still missing after normalization: {missing}"
    # status_bmi_pie must NOT appear for wide_multiyear (Phase 2 clinical decision)
    assert "status_bmi_pie" not in blocks


def test_charts_blocks_derives_age_when_absent():
    """The cached frame ships dates (not age_months_computed); the helper must
    derive it so z-scores compute. Guards against regression to the old fixture
    that pre-supplied age and hid this dependency."""
    from backend.eda.charts import normalize_for_charts

    df = _raw_wide_multiyear_df()
    assert "age_months_computed" not in df.columns  # real cached shape
    normalized = normalize_for_charts(df.copy(), "wide_multiyear")
    assert "age_months_computed" in normalized.columns
    assert "waz" in normalized.columns  # proof add_who_zscores ran
