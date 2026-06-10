"""Phase C - detection blocks for Families 5-9 (age, geographic, measurements,
z-scores, socioeconomic). Source-integrity flags read the pre-recompute
snapshot. Each test pins fire-on-trigger / silent-on-clean and flag-not-drop.

The real-CSV oracle test asserts counts against the C4 audit's measured
prevalences (the strongest signal that detection matches reality).
"""
import os
import pandas as pd
import pytest

from backend.eda.cleaning import clean_myvass, clean_ncdc

_DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "test")


def _has(reason, code):
    return code in str(reason)


def _myvass_base(n=2, **extra):
    base = {
        "IC_NO_PASSPORT": ["200101010101"] * n,
        "jantina": ["LELAKI"] * n,
        "Tarikh_Lahir": ["2020-01-01"] * n,
        "Tarikh_Pengukuran": ["2023-01-01"] * n,
        "berat_kg": [12.0] * n,
        "tinggi_cm": [85.0] * n,
    }
    base.update(extra)
    return pd.DataFrame(base)


# --- Family 5: AGE ------------------------------------------------------------

def test_age_source_mismatch():
    df = _myvass_base(age_months_computed=[99.0, 36.0])  # row0 wrong (real ~36mo)
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_age_source_mismatch")
    assert not _has(c.loc[1, "review_reason"], "review_age_source_mismatch")


def test_age_band_mismatch():
    # source label says "Bawah 2 Tahun" but source age is 36 months (-> u5)
    df = _myvass_base(age_months_computed=[36.0, 12.0],
                      Kategori_Umur=["Bawah 2 Tahun", "Bawah 2 Tahun"])
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_age_band_mismatch")
    assert not _has(c.loc[1, "review_reason"], "review_age_band_mismatch")


def test_age_vacc_range():
    # AGE_AT_VACCINATION assumed completed years; out of [0,5] -> flag
    df = _myvass_base(n=3, AGE_AT_VACCINATION=[7.0, -1.0, 3.0])
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_age_vacc_range")
    assert _has(c.loc[1, "review_reason"], "review_age_vacc_range")
    assert not _has(c.loc[2, "review_reason"], "review_age_vacc_range")


# --- Family 6: GEOGRAPHIC -----------------------------------------------------

def test_daerah_null():
    df = _myvass_base(daerah=["", "Petaling"])
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_daerah_null")
    assert not _has(c.loc[1, "review_reason"], "review_daerah_null")


def test_geo_out_of_bounds():
    df = _myvass_base(LATITUDE=[50.0, 3.1], LONGITUDE=[101.7, 101.7])  # row0 outside MY
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_geo_out_of_bounds")
    assert not _has(c.loc[1, "review_reason"], "review_geo_out_of_bounds")


def test_bahagian_null_ncdc():
    df = pd.DataFrame({
        "MyKid": ["230208155554", "230208155555"],
        "Jantina": ["Lelaki", "Lelaki"],
        "Tarikh_Lahir": ["2022-02-08", "2022-02-08"],
        "Tarikh_Pengukuran": ["2024-02-08", "2024-02-08"],
        "Berat_kg": [12.0, 12.0],
        "Tinggi_cm": [85.0, 85.0],
        "Bahagian": ["", "Sandakan"],
    })
    c, _ = clean_ncdc(df)
    assert _has(c.loc[0, "review_reason"], "review_bahagian_null")
    assert not _has(c.loc[1, "review_reason"], "review_bahagian_null")


# --- Family 7: MEASUREMENTS ---------------------------------------------------

def test_height_unit_suspect():
    df = _myvass_base(tinggi_cm=[376.0, 85.0])  # row0 cm/m confusion
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_height_unit_suspect")
    assert not _has(c.loc[1, "review_reason"], "review_height_unit_suspect")


def test_ghost_bmi():
    df = _myvass_base(bmi=[18.0, 18.0], tinggi_cm=[None, 85.0])  # row0 bmi w/o height
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_ghost_bmi")
    assert not _has(c.loc[1, "review_reason"], "review_ghost_bmi")


def test_dual_measure_mismatch():
    df = _myvass_base(LENGTH_HEIGHT_CM=[120.0, 85.0], Tinggi_cm=[85.0, 85.0])
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_dual_measure_mismatch")
    assert not _has(c.loc[1, "review_reason"], "review_dual_measure_mismatch")


# --- Family 8: Z-SCORES -------------------------------------------------------

def test_ghost_class():
    df = _myvass_base(waz=[None, -1.0], waz_class=["Normal", "Normal"])  # row0 class w/o z
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_ghost_class")
    assert not _has(c.loc[1, "review_reason"], "review_ghost_class")


def test_zscore_biv():
    df = _myvass_base(waz=[7.0, -1.0])  # row0 biologically implausible
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_zscore_biv")
    assert not _has(c.loc[1, "review_reason"], "review_zscore_biv")


def test_indicator_class_mismatch():
    # ind says stunted (1) but haz_class is blank -> mismatch; clean row agrees
    df = _myvass_base(ind_bantut_zscore=[1, 0], haz_class=["", "Normal"])
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_indicator_class_mismatch")
    assert not _has(c.loc[1, "review_reason"], "review_indicator_class_mismatch")


# --- Family 9: SOCIOECONOMIC --------------------------------------------------

def test_pendapatan_null_and_invalid():
    df = _myvass_base(n=3, pendapatan=["", "Z9", "B40"])
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_pendapatan_null")
    assert _has(c.loc[1, "review_reason"], "review_pendapatan_invalid")
    assert not _has(c.loc[2, "review_reason"], "review_pendapatan_null")
    assert not _has(c.loc[2, "review_reason"], "review_pendapatan_invalid")


# --- flag-not-drop invariant --------------------------------------------------

def test_phasec_flags_keep_analyzable_semantics():
    df = _myvass_base(daerah=["", "Petaling"])
    c, _ = clean_myvass(df)
    # a daerah-null flag must not, by itself, drive exclusion
    assert "review_daerah_null" not in str(c.loc[0, "exclude_reason"])


# --- real-CSV oracle (audit-measured prevalences) -----------------------------

@pytest.mark.parametrize("fname,expected", [
    ("smartdqc_test_myvass.csv", {
        "review_daerah_null": 47, "review_pendapatan_null": 52,
        "review_height_unit_suspect": 10, "review_ghost_bmi": 94,
        "review_age_band_mismatch": 19,
    }),
    ("smartdqc_test_klinik.csv", {
        "review_daerah_null": 32, "review_pendapatan_null": 21,
        "review_height_unit_suspect": 8, "review_ghost_bmi": 75,
        "review_age_band_mismatch": 14,
    }),
])
def test_phasec_real_csv_prevalences(fname, expected):
    path = os.path.join(_DATA, fname)
    if not os.path.exists(path):
        pytest.skip(f"fixture {fname} not present")
    df = pd.read_csv(path)
    c, _ = clean_myvass(df)
    rr = c["review_reason"].astype(str)
    for code, n in expected.items():
        assert int(rr.str.contains(code).sum()) == n, code
