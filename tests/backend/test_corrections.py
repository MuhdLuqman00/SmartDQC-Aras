import pandas as pd
import pytest
from backend.ml.corrections import flag_anomalies

@pytest.fixture
def clean_df():
    """Normal nutritional dataset — no anomalies."""
    return pd.DataFrame({
        "height_cm": [95.0, 96.5, 94.0, 97.0, 95.5] * 20,
        "weight_kg": [14.0, 14.5, 13.8, 15.0, 14.2] * 20,
        "age_months": [36, 37, 36, 38, 37] * 20,
    })

@pytest.fixture
def anomaly_df(clean_df):
    """Same dataset but row 0 has extreme values."""
    df = clean_df.copy()
    df.loc[0, "height_cm"] = 999.0   # obvious outlier
    df.loc[0, "weight_kg"] = 0.001   # obvious outlier
    return df

def test_flag_anomalies_returns_required_keys(clean_df):
    result = flag_anomalies(clean_df)
    assert "flagged_rows" in result
    assert "anomaly_count" in result
    assert "total_rows" in result
    assert "columns_used" in result

def test_total_rows_matches_input(clean_df):
    result = flag_anomalies(clean_df)
    assert result["total_rows"] == len(clean_df)

def test_detects_obvious_anomaly(anomaly_df):
    result = flag_anomalies(anomaly_df)
    flagged_indices = [r["row_index"] for r in result["flagged_rows"]]
    assert 0 in flagged_indices, "Row 0 with extreme values must be flagged"

def test_flagged_row_has_suggestions(anomaly_df):
    result = flag_anomalies(anomaly_df)
    row0 = next(r for r in result["flagged_rows"] if r["row_index"] == 0)
    assert isinstance(row0["suggestions"], list)
    assert len(row0["suggestions"]) > 0

def test_suggestion_has_required_keys(anomaly_df):
    result = flag_anomalies(anomaly_df)
    row0 = next(r for r in result["flagged_rows"] if r["row_index"] == 0)
    for s in row0["suggestions"]:
        assert "column" in s
        assert "current_value" in s
        assert "suggested_value" in s
        assert "reason" in s

def test_no_anomalies_on_uniform_data():
    df = pd.DataFrame({"x": [1.0] * 100, "y": [2.0] * 100})
    result = flag_anomalies(df)
    # IsolationForest on constant columns degenerates — must not crash
    assert isinstance(result["flagged_rows"], list)

def test_empty_df_returns_empty():
    df = pd.DataFrame({"x": pd.Series([], dtype=float)})
    result = flag_anomalies(df)
    assert result["flagged_rows"] == []
    assert result["anomaly_count"] == 0

def test_non_numeric_only_df_returns_empty():
    df = pd.DataFrame({"name": ["Alice", "Bob"] * 50, "state": ["Selangor", "Johor"] * 50})
    result = flag_anomalies(df)
    assert result["flagged_rows"] == []
    assert result["columns_used"] == []
