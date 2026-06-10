"""Phase D - detection blocks for Families 10-11 (categorical vocabularies).

NCDC: vaccine / agensi / taska.  MyVASS: ethnicity / facility type.
Validated case-insensitively against the canonical sets in config.py; a flag
means "value outside the recognised KKM vocabulary, for review". Each test pins
fire-on-unknown / silent-on-known.
"""
import pandas as pd

from backend.eda.cleaning import clean_myvass, clean_ncdc


def _has(reason, code):
    return code in str(reason)


def _ncdc_base(n=2, **extra):
    base = {
        "MyKid": ["230208155554", "230208155555"][:n] + ["230208155554"] * max(0, n - 2),
        "Jantina": ["Lelaki"] * n,
        "Tarikh_Lahir": ["2022-02-08"] * n,
        "Tarikh_Pengukuran": ["2024-02-08"] * n,
        "Berat_kg": [12.0] * n,
        "Tinggi_cm": [85.0] * n,
    }
    base.update(extra)
    return pd.DataFrame(base)


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


# --- Family 10: NCDC ----------------------------------------------------------

def test_vaccine_unknown():
    df = _ncdc_base(vaccine_name=["BCG", "Quaxin"])  # known, unknown
    c, _ = clean_ncdc(df)
    assert not _has(c.loc[0, "review_reason"], "review_vaccine_unknown")
    assert _has(c.loc[1, "review_reason"], "review_vaccine_unknown")


def test_agensi_unknown():
    df = _ncdc_base(Agensi=["PERMATA", "AcmeCorp"])
    c, _ = clean_ncdc(df)
    assert not _has(c.loc[0, "review_reason"], "review_agensi_unknown")
    assert _has(c.loc[1, "review_reason"], "review_agensi_unknown")


def test_taska_blank():
    df = _ncdc_base(Agensi=["PERMATA", "PERMATA"], Nama_Taska=["Taska A", ""])
    c, _ = clean_ncdc(df)
    assert not _has(c.loc[0, "review_reason"], "review_taska_blank")
    assert _has(c.loc[1, "review_reason"], "review_taska_blank")


# --- Family 11: MyVASS --------------------------------------------------------

def test_ethnicity_unknown():
    df = _myvass_base(ETHNICITY=["Melayu", "Klingon"])  # known, unknown
    c, _ = clean_myvass(df)
    assert not _has(c.loc[0, "review_reason"], "review_ethnicity_unknown")
    assert _has(c.loc[1, "review_reason"], "review_ethnicity_unknown")


def test_ethnicity_english_variant_not_flagged():
    df = _myvass_base(ETHNICITY=["Malay", "Orang Asli"])  # both recognised synonyms
    c, _ = clean_myvass(df)
    assert not _has(c.loc[0, "review_reason"], "review_ethnicity_unknown")
    assert not _has(c.loc[1, "review_reason"], "review_ethnicity_unknown")


def test_facility_unknown():
    df = _myvass_base(Kategori_Fasiliti=["Klinik Kesihatan", "Spaceport"])
    c, _ = clean_myvass(df)
    assert not _has(c.loc[0, "review_reason"], "review_facility_unknown")
    assert _has(c.loc[1, "review_reason"], "review_facility_unknown")


# --- flag-not-drop invariant --------------------------------------------------

def test_phased_flags_keep_analyzable_semantics():
    df = _myvass_base(ETHNICITY=["Klingon", "Melayu"])
    c, _ = clean_myvass(df)
    assert _has(c.loc[0, "review_reason"], "review_ethnicity_unknown")
    assert "review_ethnicity_unknown" not in str(c.loc[0, "exclude_reason"])
