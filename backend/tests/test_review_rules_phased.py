"""Phase D - detection blocks for Families 10-11 (categorical vocabularies).

NCDC: vaccine / agensi / taska.  MyVASS: ethnicity / facility type.
Validated case-insensitively against the canonical sets in config.py; a flag
means "value outside the recognised default vocabulary, for review". Each test pins
fire-on-unknown / silent-on-known.
"""
import pandas as pd

from backend.eda.cleaning import clean_wide_multiyear, clean_wide_registry


def _has(reason, code):
    return code in str(reason)


def _wide_registry_base(n=2, **extra):
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


def _wide_multiyear_base(n=2, **extra):
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


# --- Family 10: wide_registry -------------------------------------------------

def test_vaccine_unknown():
    df = _wide_registry_base(vaccine_name=["BCG", "Quaxin"])  # known, unknown
    c, _ = clean_wide_registry(df)
    assert not _has(c.loc[0, "review_reason"], "review_vaccine_unknown")
    assert _has(c.loc[1, "review_reason"], "review_vaccine_unknown")


def test_agensi_unknown_disabled():
    # DISABLED 2026-06-16: AGENSI_SET completeness unprovable from contoh data.
    # Even an obviously-unknown agency must NOT be flagged while the rule is dormant.
    df = _wide_registry_base(Agensi=["PERMATA", "AcmeCorp"])
    c, _ = clean_wide_registry(df)
    assert not _has(c.loc[0, "review_reason"], "review_agensi_unknown")
    assert not _has(c.loc[1, "review_reason"], "review_agensi_unknown")


def test_taska_blank():
    df = _wide_registry_base(Agensi=["PERMATA", "PERMATA"], Nama_Taska=["Taska A", ""])
    c, _ = clean_wide_registry(df)
    assert not _has(c.loc[0, "review_reason"], "review_taska_blank")
    assert _has(c.loc[1, "review_reason"], "review_taska_blank")


# --- Family 11: wide_multiyear ------------------------------------------------

def test_ethnicity_unknown_disabled():
    # DISABLED 2026-06-16: ETHNIC_VALID completeness unprovable from contoh data.
    # An unknown ethnicity must NOT be flagged while the rule is dormant.
    df = _wide_multiyear_base(ETHNICITY=["Melayu", "Klingon"])
    c, _ = clean_wide_multiyear(df)
    assert not _has(c.loc[0, "review_reason"], "review_ethnicity_unknown")
    assert not _has(c.loc[1, "review_reason"], "review_ethnicity_unknown")


def test_facility_unknown_disabled():
    # DISABLED 2026-06-16: FACILITY_SET demonstrably incomplete (real categories like
    # "government hospital"/"private clinic" missing). An unknown facility must NOT be
    # flagged while the rule is dormant.
    df = _wide_multiyear_base(Kategori_Fasiliti=["Klinik Kesihatan", "Spaceport"])
    c, _ = clean_wide_multiyear(df)
    assert not _has(c.loc[0, "review_reason"], "review_facility_unknown")
    assert not _has(c.loc[1, "review_reason"], "review_facility_unknown")


# --- flag-not-drop invariant --------------------------------------------------

def test_phased_flags_keep_analyzable_semantics():
    # Uses a still-active review rule (future measurement date) to assert the
    # invariant that review flags land in review_reason, never exclude_reason.
    df = _wide_multiyear_base(Tarikh_Pengukuran=["2099-01-01", "2023-01-01"])
    c, _ = clean_wide_multiyear(df)
    assert _has(c.loc[0, "review_reason"], "review_future_measure_date")
    assert "review_future_measure_date" not in str(c.loc[0, "exclude_reason"])
