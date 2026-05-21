import pandas as pd
from backend.eda.kpi import compute_kpi_dashboard, compute_trajectory_narratives


def test_who_target_present_in_kpi_output():
    df = pd.DataFrame({
        "stunting":    [1, 0] * 5,
        "wasting":     [0] * 10,
        "underweight": [0] * 10,
        "overweight":  [0] * 10,
    })
    result = compute_kpi_dashboard(df)
    stunting_kpi = next(k for k in result["indicators"] if k["key"] == "stunting")
    assert "who_target" in stunting_kpi
    assert stunting_kpi["who_target"] == 20.0
    assert "who_status" in stunting_kpi


def test_who_status_red_when_far_above_who_target():
    # 50% stunting vs WHO target 20% -> Red
    df = pd.DataFrame({"stunting": [1, 0] * 5})
    result = compute_kpi_dashboard(df)
    stunting_kpi = next(k for k in result["indicators"] if k["key"] == "stunting")
    assert stunting_kpi["who_status"] == "Red"


def test_who_status_green_when_below_who_target():
    df = pd.DataFrame({"stunting": [0] * 10})
    result = compute_kpi_dashboard(df)
    stunting_kpi = next(k for k in result["indicators"] if k["key"] == "stunting")
    assert stunting_kpi["who_status"] == "Green"


def test_trajectory_empty_snapshots_returns_empty():
    assert compute_trajectory_narratives([], []) == []


def test_trajectory_on_track_when_rate_declining():
    # stunting_rate drops 3pp per period -> will meet NPAN target of 15%
    snapshots = [
        {"district": "Petaling", "period": "2025-01", "stunting_rate": 25.0},
        {"district": "Petaling", "period": "2025-02", "stunting_rate": 22.0},
        {"district": "Petaling", "period": "2025-03", "stunting_rate": 19.0},
        {"district": "Petaling", "period": "2025-04", "stunting_rate": 16.0},
    ]
    results = compute_trajectory_narratives(snapshots, [])
    petaling = next(
        (r for r in results if r["district"] == "Petaling" and r["kpi_key"] == "stunting_rate"),
        None,
    )
    assert petaling is not None
    assert petaling["will_meet_target"] is True
    assert petaling["trajectory_status"] == "On Track"


def test_trajectory_off_track_when_rate_rising():
    # stunting_rate rises 3pp per period -> will miss target
    snapshots = [
        {"district": "Kelantan", "period": "2025-01", "stunting_rate": 18.0},
        {"district": "Kelantan", "period": "2025-02", "stunting_rate": 21.0},
        {"district": "Kelantan", "period": "2025-03", "stunting_rate": 24.0},
        {"district": "Kelantan", "period": "2025-04", "stunting_rate": 27.0},
    ]
    results = compute_trajectory_narratives(snapshots, [])
    kelantan = next(
        (r for r in results if r["district"] == "Kelantan" and r["kpi_key"] == "stunting_rate"),
        None,
    )
    assert kelantan is not None
    assert kelantan["will_meet_target"] is False
    assert kelantan["trajectory_status"] in ("At Risk", "Off Track")


def test_trajectory_narrative_has_bm_and_en_keys():
    snapshots = [
        {"district": "KL", "period": "2025-01", "stunting_rate": 20.0},
        {"district": "KL", "period": "2025-02", "stunting_rate": 17.0},
        {"district": "KL", "period": "2025-03", "stunting_rate": 14.0},
    ]
    results = compute_trajectory_narratives(snapshots, [])
    kl = next((r for r in results if r["district"] == "KL"), None)
    assert kl is not None
    assert "narrative" in kl
    assert "en" in kl["narrative"]
    assert "bm" in kl["narrative"]
    assert len(kl["narrative"]["en"]) > 20
    assert len(kl["narrative"]["bm"]) > 20
