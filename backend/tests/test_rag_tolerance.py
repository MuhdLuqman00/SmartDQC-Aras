"""C2 — configurable RAG amber band.

The amber band used to be hard-coded at target×1.20. _rag now takes an
amber_tolerance (fraction above target) so admins can widen/narrow the
Green→Amber→Red cutoffs from Settings → Thresholds. Default 0.20 preserves
the historical behaviour.
"""
from backend.eda.kpi import _rag


def test_rag_default_amber_band_matches_historical_120():
    # target 10, default tolerance 0.20 → amber up to 12.0
    assert _rag(9.0, 10.0) == "Green"
    assert _rag(10.0, 10.0) == "Green"      # at target is still Green
    assert _rag(11.0, 10.0) == "Amber"
    assert _rag(12.0, 10.0) == "Amber"      # boundary inclusive
    assert _rag(12.5, 10.0) == "Red"


def test_rag_widened_tolerance():
    # tolerance 0.50 → amber up to 15.0, so 14 is Amber (was Red at 0.20)
    assert _rag(14.0, 10.0, amber_tolerance=0.50) == "Amber"
    assert _rag(15.0, 10.0, amber_tolerance=0.50) == "Amber"
    assert _rag(16.0, 10.0, amber_tolerance=0.50) == "Red"


def test_rag_zero_tolerance_makes_any_excess_red():
    # tolerance 0.0 → no amber room; anything above target is Red
    assert _rag(10.0, 10.0, amber_tolerance=0.0) == "Green"
    assert _rag(10.01, 10.0, amber_tolerance=0.0) == "Red"
