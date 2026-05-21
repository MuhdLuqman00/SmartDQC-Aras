import pandas as pd
import pytest
from backend.eda.kpi import compute_kpi_dashboard

@pytest.fixture
def green_df():
    """All rates well below national targets."""
    return pd.DataFrame({
        "stunting":    [1] * 20  + [0] * 180,   # 10%  — target 15%  — Green
        "wasting":     [1] * 6   + [0] * 194,   # 3%   — target 5%   — Green
        "underweight": [1] * 20  + [0] * 180,   # 10%  — target 12%  — Green
        "overweight":  [1] * 15  + [0] * 185,   # 7.5% — target 10%  — Green
        "NEGERI":      ["Selangor"] * 100 + ["Johor"] * 100,
    })

@pytest.fixture
def red_df():
    """All rates far above national targets."""
    return pd.DataFrame({
        "stunting":    [1] * 40 + [0] * 60,     # 40% — target 15% — Red
        "wasting":     [1] * 20 + [0] * 80,     # 20% — target 5%  — Red
        "underweight": [1] * 30 + [0] * 70,     # 30% — target 12% — Red
        "overweight":  [1] * 25 + [0] * 75,     # 25% — target 10% — Red
        "NEGERI":      ["Kelantan"] * 50 + ["Sabah"] * 50,
    })

def test_returns_required_keys(green_df):
    result = compute_kpi_dashboard(green_df)
    assert "indicators" in result
    assert "overall_status" in result
    assert "by_state" in result

def test_green_overall_status(green_df):
    result = compute_kpi_dashboard(green_df)
    assert result["overall_status"] == "Green"

def test_red_overall_status(red_df):
    result = compute_kpi_dashboard(red_df)
    assert result["overall_status"] == "Red"

def test_kpi_entries_have_required_keys(green_df):
    result = compute_kpi_dashboard(green_df)
    for kpi in result["indicators"]:
        for key in ["key", "npan_target", "actual", "actual_count", "total", "rag", "gap"]:
            assert key in kpi

def test_stunting_green_when_below_target(green_df):
    result = compute_kpi_dashboard(green_df)
    stunting = next(k for k in result["indicators"] if k["key"] == "stunting")
    assert stunting["rag"] == "Green"

def test_stunting_red_when_far_above_target(red_df):
    result = compute_kpi_dashboard(red_df)
    stunting = next(k for k in result["indicators"] if k["key"] == "stunting")
    assert stunting["rag"] == "Red"

def test_district_breakdown_present_when_negeri_col(green_df):
    result = compute_kpi_dashboard(green_df)
    assert result["by_state"]
    names = [r["state"] for r in result["by_state"]]
    assert "Selangor" in names and "Johor" in names

def test_no_district_breakdown_without_negeri_col():
    df = pd.DataFrame({"stunting": [0, 1, 0] * 10, "wasting": [0, 0, 1] * 10})
    result = compute_kpi_dashboard(df)
    assert result["by_state"] == []

def test_gap_equals_actual_minus_target(green_df):
    result = compute_kpi_dashboard(green_df)
    for kpi in result["indicators"]:
        assert abs(kpi["gap"] - round(kpi["actual"] - kpi["npan_target"], 2)) < 0.01

def test_empty_df_returns_empty_kpis():
    df = pd.DataFrame({"stunting": pd.Series([], dtype=int)})
    result = compute_kpi_dashboard(df)
    assert result["indicators"] == []
    assert result["overall_status"] == "Green"

def test_amber_boundary():
    # 17% stunting — above 15% target but below 15% * 1.20 = 18% ceiling → Amber
    df = pd.DataFrame({"stunting": [1] * 17 + [0] * 83})
    result = compute_kpi_dashboard(df)
    stunting = next(k for k in result["indicators"] if k["key"] == "stunting")
    assert stunting["rag"] == "Amber", (
        f"Expected Amber for 17% stunting (target 15%, ceiling 18%), got {stunting['rag']}"
    )
