"""Source-type detection + auto-mapping after the klinik removal.

Supported schemas: myvass / ncdc (TASKA, column-identical to myvass) / kpm
(school) / unknown. 'klinik' no longer exists as a source type.
"""
from backend.config import detect_source_type, auto_suggest_mapping, AUTO_MAPPING_HINTS


def test_detects_myvass_taska_wide():
    cols = ["No. MyKID", "Nama Anak", "Jantina", "Nama TASKA",
            "2025 Berat (kg)", "2025 Status Berat", "Kumpulan Umur"]
    assert detect_source_type(cols) == "myvass"


def test_detects_kpm_school():
    cols = ["ID_MURID", "Nama Sekolah", "THN_TING", "Jantina", "Berat (kg)", "Tinggi (cm)"]
    assert detect_source_type(cols) == "kpm"


def test_unrecognised_columns_are_unknown():
    assert detect_source_type(["foo", "bar", "baz"]) == "unknown"


def test_klinik_is_no_longer_a_source_type():
    # Old clinic/vaccine signals must NOT resolve to a 'klinik' type anymore.
    cols = ["BIRTH_IC", "VACCINE_NAME", "ASSESSMENT_STATUS", "FACILITY_NAME"]
    assert detect_source_type(cols) != "klinik"
    assert "klinik" not in AUTO_MAPPING_HINTS


def test_kpm_mapping_resolves_school_columns():
    m = auto_suggest_mapping(["ID_MURID", "Nama Sekolah", "Jantina", "Berat (kg)"], "kpm")
    assert m["id"] == "ID_MURID"
    assert m["taska"] == "Nama Sekolah"
    assert m["jantina"] == "Jantina"


def test_ncdc_reuses_myvass_hints():
    # NCDC is column-identical to MyVASS; mapping must behave the same.
    cols = ["No. MyKID", "Nama TASKA", "Jantina", "2025 Berat (kg)"]
    assert auto_suggest_mapping(cols, "ncdc") == auto_suggest_mapping(cols, "myvass")
