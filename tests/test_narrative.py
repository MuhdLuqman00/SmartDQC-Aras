"""build_context() must consume run_eda()'s ACTUAL output schema.

Regression: build_context historically read legacy keys (summary, quality,
by_negeri, flat indicators) that run_eda does not produce. The result was an
empty/garbage context, so the LLM replied "no dataset provided". This pins the
real producer -> consumer contract without needing Ollama or a live server.
"""
import pandas as pd

from backend.eda.runner import run_eda
from backend.ai.narrative import build_context


def _realistic_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "NAMA": [f"Child {i}" for i in range(10)],
            "JANTINA": ["L", "P"] * 5,
            "NEGERI": ["Selangor", "Johor"] * 5,
            "BERAT_KG": [12.0, 14.5, 9.0, 18.0, 11.0, 13.0, 10.5, 16.0, 12.5, 15.0],
            "TINGGI_CM": [85, 92, 70, 105, 80, 88, 75, 100, 86, 95],
            "STATUS_BERAT": [
                "Normal", "Kurang Berat", "Normal", "Normal", "Kurang Berat",
                "Normal", "Normal", "Normal", "Kurang Berat", "Normal",
            ],
        }
    )


def test_build_context_consumes_real_run_eda_schema():
    result = run_eda(_realistic_df(), {}, "klinik")

    # Document the real contract: run_eda has NO legacy keys.
    assert "total_rows" in result
    assert "data_quality_score" in result
    assert "summary" not in result and "quality" not in result

    ctx = build_context(result)

    # Must be data-bearing, not the empty sentinel.
    assert ctx != "No structured context available."
    # Dataset framing comes from top-level keys run_eda actually emits.
    assert "klinik" in ctx
    assert str(result["total_rows"]) in ctx
    # Quality signal comes from data_quality_score, not the missing "quality" key.
    assert "quality" in ctx.lower()
    # No raw stringified nested dicts leaking in as "context".
    assert "'overall'" not in ctx and "'by_negeri'" not in ctx


def test_build_context_formats_nested_indicators():
    """Pin the indicators[age][ind] walker against run_eda's real nesting."""
    ctx = build_context(
        {
            "total_rows": 100,
            "total_columns": 5,
            "source_type": "klinik",
            "indicators": {
                "under_5": {
                    "stunting": {
                        "label": "Stunting",
                        "overall": {"n_total": 100, "n_affected": 24, "pct": 24.0},
                        "by_negeri": {"Selangor": 12, "Johor": 12},
                    }
                }
            },
        }
    )
    assert "Stunting" in ctx
    assert "24" in ctx and "100" in ctx
    # Nested dicts must be formatted, never stringified into context.
    assert "'overall'" not in ctx and "'by_negeri'" not in ctx
