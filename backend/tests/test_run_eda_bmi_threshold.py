import pandas as pd
from backend.eda.runner import run_eda


def test_run_eda_does_not_raise_nameerror_on_minimal_df():
    df = pd.DataFrame({
        "NAMA": ["A", "B"],
        "BERAT_KG": [12.0, 14.0],
        "TINGGI_CM": [85.0, 90.0],
    })
    result = run_eda(df, {}, "general")
    assert isinstance(result, dict)
    assert "bmi_consistency" in result
