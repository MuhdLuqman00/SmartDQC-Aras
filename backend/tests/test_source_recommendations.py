"""Phase 5A/5B — soft-detection scorer + general→known re-route recommendation.

5A: score_source_types returns per-signal evidence + confidence for ALL schemas,
    using the same distinctive signal lists as detect_source_type.
5B: /clean/detect-type surfaces AT MOST ONE re-route card when auto-detect falls
    to "general" but a known schema matches >=1 distinctive signal. The card is
    a recommendation (never auto-applied); generic files produce none.

Design facts pinned here (verified empirically during the verification pass):
  - The gate is an absolute matched-signal count (>=1), BELOW the hard-detect bar,
    so the card can actually fire on a general-bound file. A fraction threshold
    over the multi-signal wide_multiyear list sat above the bar and never triggered.
  - Signals are distinctive (nama taska, ic no passport, …), so a generic file
    scores zero and gets no card — the false-positive guard.
  - Only one schema is recommended (rank by matched_count, tie -> wide_multiyear) so a
    column-identical wide_multiyear/wide_registry pair can't throw two competing cards.
"""
import io

import pandas as pd
import pytest
from fastapi.testclient import TestClient


# ─── 5A: score_source_types ───────────────────────────────────────────────────

def test_score_source_types_ranks_wide_multiyear_with_evidence():
    from backend.config import score_source_types

    cols = ["IC_NO_PASSPORT", "Nama", "Jantina", "Nama TASKA",
            "Kumpulan Umur", "2024 Berat (kg)", "Negeri"]
    scores = score_source_types(pd.DataFrame(columns=cols))

    by_type = {s["type"]: s for s in scores}
    assert set(by_type) == {"wide_multiyear", "wide_registry", "school_age"}  # all schemas scored
    # wide_multiyear should have a cluster of matched distinctive signals
    assert by_type["wide_multiyear"]["matched_count"] >= 2
    matched_names = [s["name"] for s in by_type["wide_multiyear"]["signals"] if s["matched"]]
    assert "nama taska" in matched_names
    assert "ic no passport" in matched_names
    # every matched signal carries human-readable evidence
    for s in by_type["wide_multiyear"]["signals"]:
        if s["matched"]:
            assert s["evidence"] and "column" in s["evidence"]
    # confidence is a 0-1 fraction
    assert 0.0 < by_type["wide_multiyear"]["confidence"] <= 1.0


def test_score_source_types_school_age_top_for_school_columns():
    from backend.config import score_source_types

    cols = ["ID_MURID", "Nama Sekolah", "THN_TING", "Jantina", "Berat (kg)"]
    scores = score_source_types(pd.DataFrame(columns=cols))
    assert scores[0]["type"] == "school_age"  # sorted by confidence desc
    assert scores[0]["matched_count"] >= 2


def test_score_source_types_generic_file_scores_zero():
    """The false-positive guard: a generic file matches no distinctive signal."""
    from backend.config import score_source_types

    cols = ["patient_id", "name", "age", "weight", "height", "visit_date"]
    scores = score_source_types(pd.DataFrame(columns=cols))
    assert all(s["matched_count"] == 0 for s in scores)
    assert all(s["confidence"] == 0.0 for s in scores)


def test_score_source_types_sub_threshold_but_nonzero():
    """A processed MyVASS export that fell into general still shows >=1 signal."""
    from backend.config import score_source_types, detect_source_type

    cols = ["IC_NO_PASSPORT", "Nama", "Jantina", "Berat_kg", "Tinggi_cm",
            "BMI", "Negeri", "Daerah", "Tahun_Ukur"]
    assert detect_source_type(cols) == "general"  # below hard-detect bar
    scores = score_source_types(pd.DataFrame(columns=cols))
    wide_multiyear = next(s for s in scores if s["type"] == "wide_multiyear")
    assert wide_multiyear["matched_count"] >= 1  # but not zero


# ─── 5B: /clean/detect-type re-route recommendation ────────────────────────────

@pytest.fixture()
def client():
    from backend import main
    return TestClient(main.app)


def _upload(client, headers: list[str], filename: str = "data.csv"):
    """POST a tiny CSV with the given headers to /clean/detect-type."""
    csv = (",".join(headers) + "\n" + ",".join(["x"] * len(headers)) + "\n")
    files = {"file": (filename, io.BytesIO(csv.encode()), "text/csv")}
    return client.post("/clean/detect-type", files=files)


def test_detect_type_recommends_reroute_for_general_wide_multiyear(client):
    """A general-bound file resembling MyVASS yields one re-route card.

    Headers use soft TASKA signals (No. MyKID, Kumpulan Umur, Pendapatan
    Keluarga) that detect_data_type does NOT hard-match — it has no year-prefix,
    no IC_NO_PASSPORT/DOSE_DATE/FACILITY_NAME, no ID_MURID/THN_TING — so it lands
    in general, while score_source_types still recognises the MyVASS cluster.
    """
    r = _upload(client, ["No. MyKID", "Nama Anak", "Jantina", "Kumpulan Umur",
                         "Pendapatan Keluarga", "Negeri", "Daerah"])
    assert r.status_code == 200
    data = r.json()
    assert data["detected_type"] == "general"
    recs = data["recommendations"]
    reroute_cards = [r for r in recs if r["kind"] == "reroute"]
    assert len(reroute_cards) == 1, f"expected exactly one reroute card, got {recs}"
    rec = reroute_cards[0]
    assert rec["kind"] == "reroute"
    assert rec["type"] == "wide_multiyear"
    assert rec["matched_count"] >= 1
    assert rec["signals"]  # matched-signal evidence present
    assert all(s["matched"] for s in rec["signals"])  # only matched signals surfaced
    assert rec["rationale_en"] and rec["rationale_bm"]  # bilingual


def test_detect_type_single_card_for_taska_overlap(client):
    """A TASKA-shaped general file scores wide_multiyear AND wide_registry; only ONE card shows."""
    r = _upload(client, ["Nama TASKA", "Nama", "Jantina", "Berat", "Tinggi"])
    data = r.json()
    if data["detected_type"] == "general":
        assert len(data["recommendations"]) <= 1


def test_detect_type_no_recommendation_for_generic(client):
    """Generic file -> general detect, zero re-route cards (false-positive guard)."""
    r = _upload(client, ["patient_id", "name", "age", "weight", "height", "visit_date"])
    data = r.json()
    assert data["detected_type"] == "general"
    assert data["recommendations"] == []


def test_detect_type_no_recommendation_when_already_detected(client):
    """A file that hard-detects as a schema gets no re-route card (not general)."""
    r = _upload(client, ["No. MyKID", "Nama Anak", "Jantina", "Nama TASKA",
                         "Kumpulan Umur", "2024 Berat (kg)", "2024 Status Berat"])
    data = r.json()
    assert data["detected_type"] != "general"
    assert data["recommendations"] == []


# ─── Track C: /upload/preview re-route recommendation ──────────────────────────
# These tests use detect_source_type (col-only) which /upload/preview calls,
# NOT detect_data_type (col+filename) used by /clean/detect-type. Fixtures are
# verified for the right detector before being baked in.
#
# Fixture A: IC_NO_PASSPORT + anon cols — detect_source_type=='general',
#   wide_multiyear matched_count==1 (sub-threshold for hard-detect, above reroute bar).
# Fixture B: generic patient_id cols — all matched_count==0.
# Fixture C: adds Nama TASKA + year-prefix col — detect_source_type=='wide_multiyear'.

def _preview_upload(client, headers: list[str], filename: str = "data.csv"):
    """POST a tiny CSV with the given headers to /upload/preview."""
    csv = (",".join(headers) + "\n" + ",".join(["x"] * len(headers)) + "\n")
    files = {"file": (filename, io.BytesIO(csv.encode()), "text/csv")}
    return client.post("/upload/preview", files=files)


def test_preview_reroute_card_for_general_wide_multiyear_file(client):
    """General-bound file with one wide_multiyear signal → exactly one reroute card."""
    headers = ["IC_NO_PASSPORT", "Nama", "Jantina", "Berat_kg",
               "Tinggi_cm", "BMI", "Negeri", "Daerah", "Tahun_Ukur"]
    r = _preview_upload(client, headers)
    assert r.status_code == 200
    data = r.json()
    assert data["source_type"] == "general"
    recs = data["recommendations"]
    reroutes = [c for c in recs if c["kind"] == "reroute"]
    assert len(reroutes) == 1, f"expected exactly one reroute card, got {recs}"
    card = reroutes[0]
    assert card["type"] == "wide_multiyear"
    assert card["matched_count"] >= 1
    assert card["signals"] and all(s["matched"] for s in card["signals"])
    assert card["rationale_en"] and card["rationale_bm"]


def test_preview_no_reroute_card_for_generic_file(client):
    """Generic file → general detect, zero re-route cards (false-positive guard)."""
    headers = ["patient_id", "name", "age", "weight", "height", "visit_date"]
    r = _preview_upload(client, headers)
    assert r.status_code == 200
    data = r.json()
    assert data["source_type"] == "general"
    assert data["recommendations"] == []


def test_preview_no_reroute_card_when_hard_detected(client):
    """Hard-detected file → non-general source_type, no reroute card."""
    headers = ["IC_NO_PASSPORT", "Nama", "Jantina", "Nama TASKA",
               "Kumpulan Umur", "2024 Berat (kg)", "2024 Status Berat"]
    r = _preview_upload(client, headers)
    assert r.status_code == 200
    data = r.json()
    assert data["source_type"] != "general"
    assert data["recommendations"] == []


def test_preview_detect_type_endpoint_behavior_unchanged(client):
    """Verify /clean/detect-type still produces its reroute card after refactor."""
    r = _upload(client, ["No. MyKID", "Nama Anak", "Jantina", "Kumpulan Umur",
                         "Pendapatan Keluarga", "Negeri", "Daerah"])
    assert r.status_code == 200
    data = r.json()
    assert data["detected_type"] == "general"
    reroutes = [c for c in data["recommendations"] if c["kind"] == "reroute"]
    assert len(reroutes) == 1
    assert reroutes[0]["type"] == "wide_multiyear"
