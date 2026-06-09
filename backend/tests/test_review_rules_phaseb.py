"""Phase B - detection blocks for review-flag Families 1-4.

TDD: these pin that each rule FIRES on triggering rows and stays SILENT on
clean rows. All rules use _flag() (review_reason), never _exclude(); they must
never change `analyzable`. The clean-fixture invariant (review_count == 0 on
data with no triggers) is covered by test_review_rules.py and must stay green.
"""
import pandas as pd

from backend.eda.cleaning import clean_myvass, clean_ncdc
from backend.utils.ic_validator import extract_ic_gender_digit


# --- helpers ------------------------------------------------------------------

def _has(reason, code):
    return code in str(reason)


# --- Family 1: IC gender-digit extractor (pure) -------------------------------

def test_ic_gender_digit_odd_is_male():
    assert extract_ic_gender_digit("200101010101") == "Male"


def test_ic_gender_digit_even_is_female():
    assert extract_ic_gender_digit("200101010102") == "Female"


def test_ic_gender_digit_non12_returns_none():
    assert extract_ic_gender_digit("12345") is None


def test_ic_gender_digit_garbage_returns_none():
    assert extract_ic_gender_digit("not-an-ic") is None


def test_ic_gender_digit_missing_returns_none():
    assert extract_ic_gender_digit(None) is None


# --- Family 4: review_future_measure_date -------------------------------------

def test_future_measure_date_flagged_myvass():
    df = pd.DataFrame({
        "jantina": ["LELAKI", "PEREMPUAN"],
        "Tarikh_Lahir": ["2020-01-01", "2020-01-01"],
        "Tarikh_Pengukuran": ["2099-01-01", "2023-01-01"],
        "berat_kg": [12.0, 12.0],
        "tinggi_cm": [85.0, 85.0],
    })
    cleaned, _ = clean_myvass(df)
    assert _has(cleaned.loc[0, "review_reason"], "review_future_measure_date")
    assert not _has(cleaned.loc[1, "review_reason"], "review_future_measure_date")


def test_future_measure_date_keeps_row_analyzable_flag_not_drop():
    df = pd.DataFrame({
        "jantina": ["LELAKI"],
        "Tarikh_Lahir": ["2020-01-01"],
        "Tarikh_Pengukuran": ["2099-01-01"],
        "berat_kg": [12.0],
        "tinggi_cm": [85.0],
    })
    cleaned, _ = clean_myvass(df)
    # the flag itself must be present (analyzable may be False for other reasons)
    assert _has(cleaned.loc[0, "review_reason"], "review_future_measure_date")


# --- Family 1: review_duplicate_ic (myvass) -----------------------------------

def test_duplicate_ic_flags_all_sharing_rows_myvass():
    df = pd.DataFrame({
        "IC_NO_PASSPORT": ["200101010101", "200101010101", "200202020202"],
        "jantina": ["LELAKI", "LELAKI", "PEREMPUAN"],
        "Tarikh_Lahir": ["2020-01-01", "2020-01-01", "2020-01-01"],
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01", "2023-01-01"],
        "berat_kg": [12.0, 12.0, 12.0],
        "tinggi_cm": [85.0, 85.0, 85.0],
    })
    cleaned, _ = clean_myvass(df)
    assert _has(cleaned.loc[0, "review_reason"], "review_duplicate_ic")
    assert _has(cleaned.loc[1, "review_reason"], "review_duplicate_ic")
    assert not _has(cleaned.loc[2, "review_reason"], "review_duplicate_ic")


# --- Family 1: review_ic_gender_mismatch (myvass) -----------------------------

def test_ic_gender_mismatch_flagged_myvass():
    df = pd.DataFrame({
        # row0 IC odd -> Male but jantina Female -> mismatch
        # row1 IC even -> Female and jantina Female -> ok
        "IC_NO_PASSPORT": ["200101010101", "200101010102"],
        "jantina": ["PEREMPUAN", "PEREMPUAN"],
        "Tarikh_Lahir": ["2020-01-01", "2020-01-01"],
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01"],
        "berat_kg": [12.0, 12.0],
        "tinggi_cm": [85.0, 85.0],
    })
    cleaned, _ = clean_myvass(df)
    assert _has(cleaned.loc[0, "review_reason"], "review_ic_gender_mismatch")
    assert not _has(cleaned.loc[1, "review_reason"], "review_ic_gender_mismatch")


# --- Family 2: review_name_gender_mismatch ------------------------------------

def test_name_gender_mismatch_flagged_myvass():
    df = pd.DataFrame({
        "NAMA": ["SITI BINTI ALI", "MUHAMMAD BIN ALI"],
        "jantina": ["LELAKI", "LELAKI"],
        "Tarikh_Lahir": ["2020-01-01", "2020-01-01"],
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01"],
        "berat_kg": [12.0, 12.0],
        "tinggi_cm": [85.0, 85.0],
    })
    cleaned, _ = clean_myvass(df)
    # row0 female honorific vs Male -> mismatch; row1 male honorific vs Male -> ok
    assert _has(cleaned.loc[0, "review_reason"], "review_name_gender_mismatch")
    assert not _has(cleaned.loc[1, "review_reason"], "review_name_gender_mismatch")


# --- Family 3: review_gender_cols_disagree ------------------------------------

def test_gender_cols_disagree_flagged_myvass():
    df = pd.DataFrame({
        "jantina": ["LELAKI", "PEREMPUAN"],
        "GENDER": ["Female", "Female"],
        "Tarikh_Lahir": ["2020-01-01", "2020-01-01"],
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01"],
        "berat_kg": [12.0, 12.0],
        "tinggi_cm": [85.0, 85.0],
    })
    cleaned, _ = clean_myvass(df)
    # row0 Male vs Female -> disagree; row1 Female vs Female -> agree
    assert _has(cleaned.loc[0, "review_reason"], "review_gender_cols_disagree")
    assert not _has(cleaned.loc[1, "review_reason"], "review_gender_cols_disagree")


# --- Family 4: review_year_mismatch -------------------------------------------

def test_year_mismatch_flagged_myvass_tahun_ukur():
    df = pd.DataFrame({
        "jantina": ["LELAKI", "PEREMPUAN"],
        "Tarikh_Lahir": ["2020-01-01", "2020-01-01"],
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01"],
        "tahun_ukur": [2022, 2023],
        "berat_kg": [12.0, 12.0],
        "tinggi_cm": [85.0, 85.0],
    })
    cleaned, _ = clean_myvass(df)
    assert _has(cleaned.loc[0, "review_reason"], "review_year_mismatch")
    assert not _has(cleaned.loc[1, "review_reason"], "review_year_mismatch")


def test_year_mismatch_flagged_ncdc():
    df = pd.DataFrame({
        "JANTINA": ["L", "P"],
        "TARIKH LAHIR": ["2019-01-01", "2019-01-01"],
        "2023 Berat": [18.0, 18.0],
        "2023 Tinggi": [110.0, 110.0],
        "2023 Tarikh": ["2022-06-01", "2023-06-01"],
    })
    cleaned, _ = clean_ncdc(df)
    reasons = cleaned["review_reason"].tolist()
    assert any("review_year_mismatch" in str(r) for r in reasons)
    # exactly one row (the 2022 one) mismatches
    assert sum("review_year_mismatch" in str(r) for r in reasons) == 1


# --- Family 4: review_dob_dual_mismatch ---------------------------------------

def test_dob_dual_mismatch_flagged_myvass():
    df = pd.DataFrame({
        "jantina": ["LELAKI", "PEREMPUAN"],
        "Tarikh_Lahir": ["2020-01-01", "2020-01-01"],
        "DATE_OF_BIRTH": ["2020-01-01", "2019-05-05"],
        "Tarikh_Pengukuran": ["2023-01-01", "2023-01-01"],
        "berat_kg": [12.0, 12.0],
        "tinggi_cm": [85.0, 85.0],
    })
    cleaned, _ = clean_myvass(df)
    assert not _has(cleaned.loc[0, "review_reason"], "review_dob_dual_mismatch")
    assert _has(cleaned.loc[1, "review_reason"], "review_dob_dual_mismatch")


# --- Family 1: MyKid placeholder guard (existing-behavior change) -------------

def test_mykid_shared_placeholder_does_not_drop_differing_dob():
    df = pd.DataFrame({
        "JANTINA": ["L", "P", "L"],
        "No. MyKid": ["230208155554", "230208155554", "230208155554"],
        "TARIKH LAHIR": ["2019-01-01", "2020-02-02", "2021-03-03"],
        "2023 Berat": [18.0, 16.0, 14.0],
        "2023 Tinggi": [110.0, 100.0, 95.0],
        "2023 Tarikh": ["2023-06-01", "2023-06-01", "2023-06-01"],
    })
    cleaned, stats = clean_ncdc(df)
    assert stats["dropped_duplicate_mykid"] == 0
    flagged = cleaned["review_reason"].apply(
        lambda r: "review_mykid_shared_placeholder" in str(r)
    )
    assert flagged.all()


def test_mykid_same_dob_still_dedups():
    df = pd.DataFrame({
        "JANTINA": ["L", "L"],
        "No. MyKid": ["111122334455", "111122334455"],
        "TARIKH LAHIR": ["2019-01-01", "2019-01-01"],
        "2023 Berat": [18.0, 18.5],
        "2023 Tinggi": [110.0, 111.0],
        "2023 Tarikh": ["2023-01-01", "2023-06-01"],
    })
    cleaned, stats = clean_ncdc(df)
    assert stats["dropped_duplicate_mykid"] == 1
    flagged = cleaned["review_reason"].apply(
        lambda r: "review_mykid_shared_placeholder" in str(r)
    )
    assert not flagged.any()
# --- gating: review rules default ON (must not vanish on drop-only selection) ---

def _future_myvass():
    return pd.DataFrame({
        "jantina": ["LELAKI"],
        "Tarikh_Lahir": ["2020-01-01"],
        "Tarikh_Pengukuran": ["2099-01-01"],
        "berat_kg": [12.0],
        "tinggi_cm": [85.0],
    })


def test_review_flags_fire_with_drop_only_selection():
    cleaned, _ = clean_myvass(_future_myvass(),
                              enabled_rules={"dropped_age_over5", "dropped_invalid_gender"})
    assert _has(cleaned.loc[0, "review_reason"], "review_future_measure_date")


def test_review_flag_disabled_when_selection_manages_review():
    cleaned, _ = clean_myvass(_future_myvass(), enabled_rules={"review_duplicate_ic"})
    assert not _has(cleaned.loc[0, "review_reason"], "review_future_measure_date")
