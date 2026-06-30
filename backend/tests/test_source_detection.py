"""Source-type detection + auto-mapping after the klinik removal.

Supported schemas: wide_multiyear / wide_registry (TASKA, column-identical to wide_multiyear) / school_age
(school) / unknown. 'klinik' no longer exists as a source type.
"""
from backend.config import detect_source_type, auto_suggest_mapping, AUTO_MAPPING_HINTS


def test_detects_wide_multiyear_taska_wide():
    cols = ["No. MyKID", "Nama Anak", "Jantina", "Nama TASKA",
            "2025 Berat (kg)", "2025 Status Berat", "Kumpulan Umur"]
    assert detect_source_type(cols) == "wide_multiyear"


def test_detects_school_age_school():
    cols = ["ID_MURID", "Nama Sekolah", "THN_TING", "Jantina", "Berat (kg)", "Tinggi (cm)"]
    assert detect_source_type(cols) == "school_age"


def test_unrecognised_columns_are_general():
    assert detect_source_type(["foo", "bar", "baz"]) == "general"


def test_klinik_is_no_longer_a_source_type():
    # Old clinic/vaccine signals must NOT resolve to a 'klinik' type anymore.
    cols = ["BIRTH_IC", "VACCINE_NAME", "ASSESSMENT_STATUS", "FACILITY_NAME"]
    assert detect_source_type(cols) != "klinik"
    assert "klinik" not in AUTO_MAPPING_HINTS


def test_school_age_mapping_resolves_school_columns():
    m = auto_suggest_mapping(["ID_MURID", "Nama Sekolah", "Jantina", "Berat (kg)"], "school_age")
    assert m["id"] == "ID_MURID"
    assert m["taska"] == "Nama Sekolah"
    assert m["jantina"] == "Jantina"


def test_wide_registry_maps_taska_columns():
    # NCDC has its own independent hint set that currently mirrors MyVASS's TASKA
    # layout, so the two map shared columns equivalently (NCDC-specific cleaning
    # lives in clean_wide_registry, not in these hints).
    cols = ["No. MyKID", "Nama TASKA", "Jantina", "2025 Berat (kg)"]
    m = auto_suggest_mapping(cols, "wide_registry")
    assert m["id"] == "No. MyKID"
    assert m["taska"] == "Nama TASKA"
    assert m == auto_suggest_mapping(cols, "wide_multiyear")


def test_wide_registry_and_wide_multiyear_hints_are_independent_objects():
    # Decoupled: editing one source's hints must not mutate the other.
    assert AUTO_MAPPING_HINTS["wide_registry"] is not AUTO_MAPPING_HINTS["wide_multiyear"]
