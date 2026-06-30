"""The AI-narrative EDA path must NOT starve compute_quality_score.

Regression: /ai/narrative and _get_or_build_narrative called
run_eda(df, {}, source_type) with an EMPTY mapping. Cleaned data has
Title-Case canonical columns (Berat_kg, MyKid, WAZ); the rubric expects
lowercase (berat_kg, id, waz). With {} no rename happens, so the rubric
scores ~30/D and indicators come out empty -> the LLM was handed a wrong
"30.0 (grade D)" and no indicators, producing a generic, alarmist
narrative even when the dashboard showed 100.

run_eda_auto() derives the mapping the backend can already infer
(auto_suggest_mapping) so the rubric scores the data it actually has.
"""
import pandas as pd

from backend.eda.runner import run_eda, run_eda_auto
from backend.ai.narrative import build_context


def _titlecase_cleaned_df() -> pd.DataFrame:
    """Mirrors the real cached cleaned shape: Title-Case canonical columns,
    NOT the lowercase names the quality rubric / indicators expect."""
    return pd.DataFrame(
        {
            "Year": [2025] * 8,
            "Agensi": ["Agency A"] * 8,
            "Negeri": ["Selangor", "Johor"] * 4,
            "Daerah": ["Petaling", "Johor Bahru"] * 4,
            "MyKid": [f"0501{i:02d}010001" for i in range(8)],
            "Nama_Anak": [f"Child {i}" for i in range(8)],
            "Jantina": ["L", "P"] * 4,
            "Tarikh_Lahir": pd.to_datetime(
                ["2022-01-15", "2022-03-10", "2021-11-01", "2022-06-20",
                 "2021-09-05", "2022-02-28", "2021-12-12", "2022-04-18"]
            ),
            "Tarikh_Ukur": pd.to_datetime(["2024-06-01"] * 8),
            "Kumpulan_Umur": ["bawah_5_tahun"] * 8,
            "Berat_kg": [12.0, 11.5, 13.0, 10.8, 14.0, 9.5, 13.5, 11.0],
            "Tinggi_cm": [88.0, 86.0, 92.0, 84.0, 95.0, 78.0, 93.0, 85.0],
            "BMI": [15.5, 15.5, 15.3, 15.3, 15.5, 15.6, 15.6, 15.2],
        }
    )


def test_empty_mapping_starves_the_rubric_baseline():
    """Documents the bug: the OLD code path (empty mapping) is broken."""
    starved = run_eda(_titlecase_cleaned_df(), {}, "myvass")
    dq = starved["data_quality_score"]
    # The starvation signature: rubric collapses to grade D, no indicators.
    assert dq["grade"] == "D"
    assert not (starved.get("indicators") or {})


def test_run_eda_auto_scores_the_data_it_actually_has():
    result = run_eda_auto(_titlecase_cleaned_df(), "myvass")
    dq = result["data_quality_score"]

    # A dataset with valid IDs, weights, heights and computable z-scores
    # must NOT score grade D. It is a meaningful score, not the starved 30.
    assert dq["score"] >= 55, dq
    assert dq["grade"] in ("A", "B", "C"), dq

    # Indicators must populate so the narrative is specific, not generic.
    assert result.get("indicators"), "indicators empty -> narrative stays generic"


def test_build_context_carries_real_score_and_indicators():
    ctx = build_context(run_eda_auto(_titlecase_cleaned_df(), "myvass"))
    assert "No structured context available." not in ctx
    assert "(grade D)" not in ctx
    assert "Nutrition indicators" in ctx
