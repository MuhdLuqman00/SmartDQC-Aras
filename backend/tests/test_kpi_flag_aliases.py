"""KPI dashboard must populate from the Bahasa Ind_* columns the cleaners
emit, not only from canonical English flag columns."""
import pandas as pd

from backend.eda.kpi import compute_kpi_dashboard


def test_kpi_populates_from_cleaner_ind_columns():
    df = pd.DataFrame({
        "STATE":                  ["Sabah", "Sabah", "Selangor", "Selangor"],
        "Gender":                 ["Male", "Female", "Male", "Female"],
        "Age_Months":             [12, 30, 18, 40],
        "Ind_Bantut":             [True, False, False, False],   # stunting    1/4 = 25%
        "Ind_Susut":              [False, False, False, False],  # wasting     0/4 = 0%
        "Ind_Kurang_Berat_Badan": [True, True, False, False],    # underweight 2/4 = 50%
        "Ind_Berlebihan_BB":      [False, False, True, False],   # overweight  1/4 = 25%
    })

    out = compute_kpi_dashboard(df)
    by_key = {i["key"]: i for i in out["indicators"]}

    assert set(by_key) == {"stunting", "wasting", "underweight", "overweight"}
    assert by_key["stunting"]["actual"] == 25.0
    assert by_key["wasting"]["actual"] == 0.0
    assert by_key["underweight"]["actual"] == 50.0
    assert by_key["overweight"]["actual"] == 25.0
    assert out["total_children"] == 4
    assert {r["state"] for r in out["by_state"]} == {"Sabah", "Selangor"}


def test_kpi_still_accepts_canonical_flag_columns():
    """Regression guard — canonical English columns must keep working
    unchanged (this test stays GREEN before and after the fix)."""
    df = pd.DataFrame({
        "STATE":       ["Johor", "Johor"],
        "stunting":    [True, False],    # 50%
        "wasting":     [False, False],   # 0%
        "underweight": [False, False],   # 0%
        "overweight":  [False, True],    # 50%
    })

    out = compute_kpi_dashboard(df)
    by_key = {i["key"]: i for i in out["indicators"]}

    assert by_key["stunting"]["actual"] == 50.0
    assert by_key["overweight"]["actual"] == 50.0
