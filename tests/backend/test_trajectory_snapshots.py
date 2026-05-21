"""Per-district trajectory snapshot derivation (Feature 16).

compute_district_period_snapshots turns a cleaned multi-year dataset into the
per-district, per-period rate rows that compute_trajectory_narratives consumes.
"""
import pandas as pd

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
