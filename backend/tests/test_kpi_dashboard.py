import pandas as pd

from backend.eda.kpi import _group_breakdown


def _df():
    return pd.DataFrame({
        "NEGERI":      ["Johor", "Johor", "Kedah", "Kedah"],
        "stunting":    [1, 0, 1, 1],
        "wasting":     [0, 0, 1, 0],
        "underweight": [0, 1, 0, 0],
        "overweight":  [0, 0, 0, 0],
    })


def test_group_breakdown_rates_and_status():
    rows = _group_breakdown(_df(), "NEGERI", "state")
    johor = next(r for r in rows if r["state"] == "Johor")
    assert johor["n"] == 2
    assert johor["rates"]["stunting"] == 50.0          # 1 of 2
    assert johor["status"]["stunting"] == "Red"        # 50 > 15*1.2
    kedah = next(r for r in rows if r["state"] == "Kedah")
    assert kedah["rates"]["stunting"] == 100.0
    assert kedah["rates"]["wasting"] == 50.0


def test_group_breakdown_missing_flag_column():
    df = _df().drop(columns=["overweight"])
    rows = _group_breakdown(df, "NEGERI", "state")
    assert "overweight" not in rows[0]["rates"]
    assert "stunting" in rows[0]["rates"]


from backend.eda.kpi import compute_kpi_dashboard


def _full_df():
    return pd.DataFrame({
        "NEGERI":      ["Johor", "Johor", "Kedah", "Kedah"],
        "Jantina":     ["Lelaki", "Perempuan", "Lelaki", "Perempuan"],
        "Age_Months":  [12, 30, 18, 48],
        "stunting":    [1, 0, 1, 1],
        "wasting":     [0, 0, 1, 0],
        "underweight": [0, 1, 0, 0],
        "overweight":  [0, 0, 0, 0],
    })


def test_compute_contract_shape():
    out = compute_kpi_dashboard(_full_df())
    assert set(out) >= {
        "overall_status", "total_children", "indicators",
        "by_state", "by_gender", "by_age",
    }
    assert out["total_children"] == 4
    ind = {i["key"]: i for i in out["indicators"]}
    assert ind["stunting"]["actual"] == 75.0          # 3 of 4
    assert ind["stunting"]["npan_target"] == 15.0
    assert ind["stunting"]["who_target"] == 20.0
    assert ind["stunting"]["gap"] == 60.0             # 75 - 15
    assert ind["stunting"]["rag"] == "Red"
    assert ind["stunting"]["label_en"] == "Stunting Rate"
    assert {r["state"] for r in out["by_state"]} == {"Johor", "Kedah"}
    assert {r["gender"] for r in out["by_gender"]} == {"Lelaki", "Perempuan"}
    assert {r["group"] for r in out["by_age"]} == {"Bawah 2 Tahun", "2-5 Tahun"}


def test_compute_empty_df():
    out = compute_kpi_dashboard(pd.DataFrame())
    assert out["indicators"] == []
    assert out["by_state"] == []
    assert out["total_children"] == 0


def test_compute_missing_optional_columns():
    df = _full_df().drop(columns=["Jantina", "Age_Months"])
    out = compute_kpi_dashboard(df)
    assert out["by_gender"] == []
    assert out["by_age"] == []
    assert len(out["by_state"]) == 2


if __name__ == "__main__":
    test_group_breakdown_rates_and_status()
    test_group_breakdown_missing_flag_column()
    test_compute_contract_shape()
    test_compute_empty_df()
    test_compute_missing_optional_columns()
    print("ALL PASS")
