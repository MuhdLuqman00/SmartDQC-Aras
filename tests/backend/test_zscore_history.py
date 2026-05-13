from backend.ml.zscore_history import aggregate_zscore_archive, forecast_district_risk


def _make_records(
    district: str,
    n_periods: int = 6,
    waz_start: float = -1.0,
    waz_slope: float = -0.2,
) -> list[dict]:
    """Deterministic records with no noise so regression values are exact."""
    records = []
    for p in range(n_periods):
        period = f"2025-{p + 1:02d}"
        for i in range(20):
            records.append({
                "ic_no":    f"IC{district}{i:04d}",
                "period":   period,
                "district": district,
                "waz":      waz_start + p * waz_slope,
                "haz":      -1.5,
                "baz":      -0.5,
            })
    return records


def test_aggregate_empty_returns_empty_df():
    result = aggregate_zscore_archive([])
    assert result.empty


def test_aggregate_groups_by_district_and_period():
    records = _make_records("KualaLumpur", n_periods=3)
    agg = aggregate_zscore_archive(records)
    assert len(agg) == 3
    assert set(agg["district"]) == {"KualaLumpur"}
    assert set(agg["period"]) == {"2025-01", "2025-02", "2025-03"}


def test_forecast_empty_returns_empty():
    assert forecast_district_risk([]) == []


def test_forecast_declining_trend_gives_high_risk():
    # waz_start=-1.0, slope=-0.4: period 7 forecast = -1 + 6*(-0.4) = -3.4 -> High
    records = _make_records("Selangor", n_periods=6, waz_start=-1.0, waz_slope=-0.4)
    results = forecast_district_risk(records)
    assert len(results) == 1
    r = results[0]
    assert r["district"] == "Selangor"
    assert r["waz_mean_trend"] == "declining"
    assert r["next_quarter_risk"] == "High"


def test_forecast_improving_trend_gives_low_risk():
    # waz_start=-2.5, slope=+0.3: period 7 forecast = -2.5 + 6*0.3 = -0.7 -> Low
    records = _make_records("Putrajaya", n_periods=6, waz_start=-2.5, waz_slope=0.3)
    results = forecast_district_risk(records)
    r = results[0]
    assert r["waz_mean_trend"] == "improving"
    assert r["next_quarter_risk"] == "Low"


def test_forecast_multiple_districts():
    records = _make_records("KL", 6) + _make_records("Johor", 6)
    results = forecast_district_risk(records)
    assert len(results) == 2
    assert {r["district"] for r in results} == {"KL", "Johor"}


def test_insufficient_data_returns_none_forecast():
    # Only 2 periods -> not enough for regression (need >= 3)
    records = _make_records("Kedah", n_periods=2)
    results = forecast_district_risk(records)
    r = results[0]
    assert r["waz_mean_forecast"] is None
    assert r["waz_mean_trend"] == "insufficient_data"
