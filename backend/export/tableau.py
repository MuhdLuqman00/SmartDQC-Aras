"""
Tableau-ready flat aggregated table builder.
NO ROW CAP — exports ALL aggregated rows.

Tidy long format: every row is one data point described by a (pecahan, kategori)
pair — the breakdown TYPE and its VALUE — instead of a wide table with one
sparse column per dimension (negeri / daerah / jantina / pendapatan / tahun).
This is the shape Tableau expects: filter/pivot on `pecahan`, plot `peratus`.

Columns:
  kumpulan_umur     age band (Bawah 2 Tahun / Bawah 5 Tahun)
  indikator         indicator key (bantut / susut / ...)
  indikator_label   human label
  sumber_indikator  classification source (zscore | source_label)
  pecahan           breakdown type (Kebangsaan / Negeri / Daerah / Jantina ...)
  kategori          breakdown value (e.g. "Selangor", "Lelaki", "2024")
  n_total           denominator for this cell
  n_kes             affected count
  peratus           percentage (0-100, 2 dp)
"""

import pandas as pd
import io


AGE_LABELS = {
    "bawah_2_tahun": "Bawah 2 Tahun",
    "bawah_5_tahun": "Bawah 5 Tahun",
}

COLUMNS = [
    "kumpulan_umur", "indikator", "indikator_label", "sumber_indikator",
    "pecahan", "kategori", "n_total", "n_kes", "peratus",
]

# (report key, pecahan label, value field within each record)
BREAKDOWNS = [
    ("by_negeri",            "Negeri",              "negeri"),
    ("by_kawasan_bahagian",  "Kawasan / Bahagian",  "kawasan_bahagian"),
    ("by_daerah",            "Daerah",              "daerah"),
    ("by_negeri_jantina",    "Negeri × Jantina",    None),  # composite value
    ("by_negeri_pendapatan", "Negeri × Pendapatan", None),  # composite value
    ("by_pendapatan",        "Pendapatan",          "pendapatan"),
    ("by_tahun",             "Trend Tahunan",       "tahun_ukur"),
]


def _row(age_label, ind_key, ind_data, source, pecahan, kategori, rec) -> dict:
    return {
        "kumpulan_umur":    age_label,
        "indikator":        ind_key,
        "indikator_label":  ind_data.get("label", ind_key),
        "sumber_indikator": source,
        "pecahan":          pecahan,
        "kategori":         kategori,
        "n_total":          rec.get("n_total", 0),
        "n_kes":            rec.get("n_affected", 0),
        "peratus":          round(float(rec.get("pct", 0) or 0), 2),
    }


def build_aggregated_table(report: dict) -> list[dict]:
    """Flatten the indicators report into tidy Tableau-ready long rows."""
    indicators = report.get("indicators", {})
    if not indicators:
        return []

    rows: list[dict] = []
    for age_key, age_data in indicators.items():
        age_label = AGE_LABELS.get(age_key, age_key)
        for ind_key, ind_data in age_data.items():
            source = ind_data.get("source", "unknown")

            # National overall
            rows.append(_row(age_label, ind_key, ind_data, source,
                             "Kebangsaan", "National", ind_data.get("overall", {})))

            # Every breakdown collapses into one (pecahan, kategori) pair
            for key, pecahan, val_field in BREAKDOWNS:
                for rec in ind_data.get(key, []):
                    if val_field is not None:
                        kategori = rec.get(val_field, "")
                    elif key == "by_negeri_jantina":
                        kategori = f"{rec.get('negeri', '')} · {rec.get('jantina', '')}"
                    elif key == "by_negeri_pendapatan":
                        kategori = f"{rec.get('negeri', '')} · {rec.get('pendapatan', '')}"
                    else:
                        kategori = ""
                    rows.append(_row(age_label, ind_key, ind_data, source,
                                     pecahan, str(kategori), rec))

    return rows


def to_excel(rows: list[dict], base_filename: str) -> bytes:
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Indikator_Aggregated")
    buf.seek(0)
    return buf.read()


def to_csv(rows: list[dict]) -> bytes:
    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    return buf.getvalue().encode("utf-8-sig")
