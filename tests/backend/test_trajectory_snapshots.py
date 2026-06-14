"""Per-district trajectory snapshot derivation (Feature 16).

compute_district_period_snapshots turns a cleaned multi-year dataset into the
per-district, per-period rate rows that compute_trajectory_narratives consumes.
"""
import os

import pandas as pd
import pytest

from backend.eda.cleaning import clean_data
from backend.eda.kpi import (
    compute_district_period_snapshots,
    compute_trajectory_narratives,
)


def _multiyear_df():
    # Two districts, three years; Beaufort stunting rising, KK falling.
    rows = []
    plan = {
        ("Beaufort", "2023"): 0.20, ("Beaufort", "2024"): 0.30, ("Beaufort", "2025"): 0.40,
        ("KK",       "2023"): 0.30, ("KK",       "2024"): 0.20, ("KK",       "2025"): 0.10,
    }
    for (district, year), rate in plan.items():
        n = 100
        flags = [1] * int(rate * n) + [0] * (n - int(rate * n))
        for f in flags:
            rows.append({"daerah": district, "tahun_ukur": year, "Ind_Bantut": f})
    return pd.DataFrame(rows)


def test_snapshots_have_one_row_per_district_period():
    snaps = compute_district_period_snapshots(_multiyear_df())
    keys = {(s["district"], s["period"]) for s in snaps}
    assert len(keys) == 6  # 2 districts x 3 years
    assert all("stunting_rate" in s for s in snaps)


def test_single_year_yields_no_trajectory():
    df = pd.DataFrame({
        "daerah": ["Beaufort"] * 10,
        "tahun_ukur": ["2025"] * 10,
        "Ind_Bantut": [1, 0] * 5,
    })
    snaps = compute_district_period_snapshots(df)
    # Only one period per district → trajectory needs >=2 points → empty narrative.
    assert compute_trajectory_narratives(snaps, []) == []


def test_no_year_column_yields_empty():
    df = pd.DataFrame({"daerah": ["X", "Y"], "Ind_Bantut": [1, 0]})
    assert compute_district_period_snapshots(df) == []


def test_rising_district_is_off_or_at_risk():
    snaps = compute_district_period_snapshots(_multiyear_df())
    narr = compute_trajectory_narratives(snaps, [])
    beaufort = next(
        n for n in narr if n["district"] == "Beaufort" and n["kpi_key"] == "stunting_rate"
    )
    assert beaufort["trajectory_status"] in ("At Risk", "Off Track")
    assert beaufort["will_meet_target"] is False


# ── B3 regression tests ───────────────────────────────────────────────────────


def test_capital_Y_year_column_yields_snapshots():
    """Regression: NCDC melt emits 'Year' (capital Y); resolver must match case-insensitively."""
    rows = []
    for year in ["2023", "2024"]:
        for district in ["Beaufort", "KK"]:
            for _ in range(20):
                rows.append({"Year": year, "daerah": district, "Ind_Bantut": 1})
    df = pd.DataFrame(rows)
    snaps = compute_district_period_snapshots(df)
    assert len(snaps) > 0


def test_snapshots_derive_year_from_date_column():
    """When a frame has no year column, the snapshot layer derives the period from
    a measurement-date column. Derivation lives in compute_district_period_snapshots,
    not in the cleaners (B2 layering fix)."""
    rows = []
    for year in ["2023", "2024"]:
        for district in ["Beaufort", "KK"]:
            for _ in range(20):
                rows.append({
                    "Tarikh_Pengukuran": f"{year}-06-15",
                    "daerah": district,
                    "Ind_Bantut": 1,
                })
    df = pd.DataFrame(rows)  # no year column at all
    snaps = compute_district_period_snapshots(df)
    assert len(snaps) > 0
    assert {s["period"] for s in snaps} == {"2023", "2024"}


def test_kpm_clean_does_not_bake_year_column():
    """Regression for the B2 layering fix: clean_kpm no longer adds Tahun_Ukur;
    trajectories still work because the snapshot layer derives the year itself."""
    rows = []
    for year in [2023, 2024]:
        for district in ["Kuala Lumpur", "Selangor"]:
            for _ in range(20):
                rows.append({
                    "Tarikh_Pengukuran": f"{year}-06-15",
                    "Daerah": district,
                    "Negeri": "Wilayah",
                })
    df = pd.DataFrame(rows)
    cleaned, _ = clean_data(df, "kpm")
    assert "Tahun_Ukur" not in cleaned.columns  # cleaner stays year-agnostic
    snaps = compute_district_period_snapshots(cleaned)
    assert len(snaps) > 0


def test_ncdc_integration_smoke():
    """Synthetic NCDC CSV must yield >0 trajectory snapshots after clean_data."""
    path = "data/test/synthetic_ncdc_wide_4500.csv"
    if not os.path.exists(path):
        pytest.skip("Synthetic NCDC CSV not present")
    df = pd.read_csv(path, dtype=str)
    cleaned, _ = clean_data(df.copy(), "ncdc")
    snaps = compute_district_period_snapshots(cleaned)
    assert len(snaps) > 0, "NCDC must produce trajectory snapshots"


def test_kpm_integration_smoke():
    """Synthetic KPM CSV must yield >0 trajectory snapshots after clean_data."""
    path = "data/test/synthetic_kpm_10000.csv"
    if not os.path.exists(path):
        pytest.skip("Synthetic KPM CSV not present")
    df = pd.read_csv(path, dtype=str)
    cleaned, _ = clean_data(df.copy(), "kpm")
    snaps = compute_district_period_snapshots(cleaned)
    assert len(snaps) > 0, "KPM must produce trajectory snapshots"
