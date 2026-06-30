"""Regression: an already-processed NCDC/TASKA export uses underscore date
columns (Tarikh_Lahir / Tarikh_Pengukuran). clean_wide_multiyear.find_col matched DOB
with the pattern "tarikh lahir" (a SPACE) which never matches "tarikh_lahir"
(an UNDERSCORE), and had no "pengukuran" synonym. dob_col/measure_date_col
resolved to None, the cleaner overwrote the file's valid dates with NaT,
Age_Days became null, z-scores could not be computed, and Rule 7 deleted every
row -> Step 4 showed 0.0%. This test pins that the cleaner keeps such rows.
"""
import importlib
import os
import pathlib

import pandas as pd

# who_zscore loads the WHO LMS tables at module-import time. The repo ships
# them under data/zscore; point the loader there BEFORE importing so the local
# test environment computes real z-scores (otherwise the row loss would be due
# to absent tables, not the find_col bug under test).
_ZDIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "zscore"
os.environ["WHO_ZSCORE_DIR"] = str(_ZDIR)

from backend.eda import who_zscore  # noqa: E402

importlib.reload(who_zscore)
from backend.eda import cleaning  # noqa: E402

importlib.reload(cleaning)


def _processed_shaped_df() -> pd.DataFrame:
    """Two valid ~12-month-old records, shaped like the real export: all
    string dtype (read_file uses dtype=str) and underscore date columns."""
    return pd.DataFrame(
        {
            "Gender": ["LELAKI", "PEREMPUAN"],
            "Tarikh_Lahir": ["2023-02-08 00:00:00", "2022-06-12 00:00:00"],
            "Tarikh_Pengukuran": ["2024-02-08", "2023-06-12"],
            "Berat_kg": ["9.5", "9.0"],
            "Tinggi_cm": ["75", "74"],
        }
    )


def test_processed_file_with_underscore_date_columns_is_not_wiped():
    assert who_zscore.ZSCORE_AVAILABLE and who_zscore._LMS_TABLES, (
        "WHO LMS tables must load for this test to isolate the find_col bug"
    )

    cleaned, stats = cleaning.clean_data(_processed_shaped_df(), "wide_multiyear")

    # The cleaner must recognise Tarikh_Lahir / Tarikh_Pengukuran, compute
    # Age_Days, and keep the valid rows — not null the dates and wipe via Rule 7.
    assert stats["dropped_null_zscore"] == 0, stats
    assert len(cleaned) == 2, f"all rows wiped — Rule 7 deleted everything: {stats}"


def test_parse_date_handles_iso_datetime_without_dayfirst_misparse():
    """Already-processed exports store dates as ISO "YYYY-MM-DD HH:MM:SS".
    _parse_date used dayfirst=True which coerced/misparsed these. ISO must
    parse correctly while genuine day-first (dd/mm/yyyy) is still respected.
    """
    s = pd.Series(
        [
            "2023-02-08 00:00:00",  # ISO datetime
            "2023-12-06 00:00:00",  # ISO — must be 6 Dec, NOT 12 Jun
            "24/07/2025 00:00",     # day-first — 24 can't be a month
            None,
        ]
    )
    out = cleaning._parse_date(s)

    assert out.isna().sum() == 1, f"only the None should be NaT: {list(out)}"
    assert out.iloc[0] == pd.Timestamp("2023-02-08")
    assert out.iloc[1] == pd.Timestamp("2023-12-06")
    assert out.iloc[2] == pd.Timestamp("2025-07-24")


def test_parse_date_keeps_dayfirst_for_ambiguous_raw_dates():
    """Raw MyVASS dates are dd/mm/yyyy. When day <= 12 the value is
    ambiguous; it must still be read day-first, not month-first."""
    out = cleaning._parse_date(pd.Series(["05/06/2024", "11/02/2023"]))
    assert out.iloc[0] == pd.Timestamp("2024-06-05"), out.iloc[0]
    assert out.iloc[1] == pd.Timestamp("2023-02-11"), out.iloc[1]
