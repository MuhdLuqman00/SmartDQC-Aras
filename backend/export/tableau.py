"""
Tableau-ready flat aggregated table builder.
NO ROW CAP — exports ALL aggregated rows.
Schema: one row per geo_level × location × age_group × indicator × year.
"""

import pandas as pd
import io


AGE_LABELS = {
    "bawah_2_tahun": "Bawah 2 Tahun",
    "bawah_5_tahun": "Bawah 5 Tahun",
}

GEO_LEVELS = [
    ("negeri",           "Negeri"),
    ("kawasan_bahagian", "Kawasan / Bahagian"),
    ("daerah",           "Daerah"),
]


def build_aggregated_table(report: dict) -> list[dict]:
    """
    Flatten the indicators report into Tableau-ready rows.
    Returns a list of dicts (every row = one data point).
    """
    indicators = report.get("indicators", {})
    if not indicators:
        return []

    rows = []

    for age_key, age_data in indicators.items():
        age_label = AGE_LABELS.get(age_key, age_key)

        for ind_key, ind_data in age_data.items():
            overall = ind_data.get("overall", {})
            source  = ind_data.get("source", "unknown")

            # ── National (overall) ─────────────────────────────────────────
            rows.append({
                "kumpulan_umur":    age_label,
                "indikator":        ind_key,
                "indikator_label":  ind_data.get("label", ind_key),
                "sumber_indikator": source,
                "peringkat_geo":    "Kebangsaan",
                "lokasi":           "Malaysia",
                "negeri":           None,
                "kawasan_bahagian": None,
                "daerah":           None,
                "jantina":          None,
                "pendapatan":       None,
                "tahun_ukur":       None,
                "n_total":          overall.get("n_total", 0),
                "n_affected":       overall.get("n_affected", 0),
                "pct":              overall.get("pct", 0),
            })

            # ── Geo level breakdowns ───────────────────────────────────────
            for geo_key, geo_label in GEO_LEVELS:
                for rec in ind_data.get(f"by_{geo_key}", []):
                    rows.append({
                        "kumpulan_umur":    age_label,
                        "indikator":        ind_key,
                        "indikator_label":  ind_data.get("label", ind_key),
                        "sumber_indikator": source,
                        "peringkat_geo":    geo_label,
                        "lokasi":           rec.get(geo_key, ""),
                        "negeri":           rec.get("negeri"),
                        "kawasan_bahagian": rec.get("kawasan_bahagian"),
                        "daerah":           rec.get("daerah"),
                        "jantina":          None,
                        "pendapatan":       None,
                        "tahun_ukur":       None,
                        "n_total":          rec.get("n_total", 0),
                        "n_affected":       rec.get("n_affected", 0),
                        "pct":              rec.get("pct", 0),
                    })

            # ── Negeri × Jantina ──────────────────────────────────────────
            for rec in ind_data.get("by_negeri_jantina", []):
                rows.append({
                    "kumpulan_umur":    age_label,
                    "indikator":        ind_key,
                    "indikator_label":  ind_data.get("label", ind_key),
                    "sumber_indikator": source,
                    "peringkat_geo":    "Negeri × Jantina",
                    "lokasi":           rec.get("negeri", ""),
                    "negeri":           rec.get("negeri"),
                    "kawasan_bahagian": None,
                    "daerah":           None,
                    "jantina":          rec.get("jantina"),
                    "pendapatan":       None,
                    "tahun_ukur":       None,
                    "n_total":          rec.get("n_total", 0),
                    "n_affected":       rec.get("n_affected", 0),
                    "pct":              rec.get("pct", 0),
                })

            # ── Negeri × Pendapatan ───────────────────────────────────────
            for rec in ind_data.get("by_negeri_pendapatan", []):
                rows.append({
                    "kumpulan_umur":    age_label,
                    "indikator":        ind_key,
                    "indikator_label":  ind_data.get("label", ind_key),
                    "sumber_indikator": source,
                    "peringkat_geo":    "Negeri × Pendapatan",
                    "lokasi":           rec.get("negeri", ""),
                    "negeri":           rec.get("negeri"),
                    "kawasan_bahagian": None,
                    "daerah":           None,
                    "jantina":          None,
                    "pendapatan":       rec.get("pendapatan"),
                    "tahun_ukur":       None,
                    "n_total":          rec.get("n_total", 0),
                    "n_affected":       rec.get("n_affected", 0),
                    "pct":              rec.get("pct", 0),
                })

            # ── Pendapatan (national income breakdown) ─────────────────────
            for rec in ind_data.get("by_pendapatan", []):
                rows.append({
                    "kumpulan_umur":    age_label,
                    "indikator":        ind_key,
                    "indikator_label":  ind_data.get("label", ind_key),
                    "sumber_indikator": source,
                    "peringkat_geo":    "Pendapatan (Kebangsaan)",
                    "lokasi":           rec.get("pendapatan", ""),
                    "negeri":           None,
                    "kawasan_bahagian": None,
                    "daerah":           None,
                    "jantina":          None,
                    "pendapatan":       rec.get("pendapatan"),
                    "tahun_ukur":       None,
                    "n_total":          rec.get("n_total", 0),
                    "n_affected":       rec.get("n_affected", 0),
                    "pct":              rec.get("pct", 0),
                })

            # ── Trend by year ─────────────────────────────────────────────
            for rec in ind_data.get("by_tahun", []):
                rows.append({
                    "kumpulan_umur":    age_label,
                    "indikator":        ind_key,
                    "indikator_label":  ind_data.get("label", ind_key),
                    "sumber_indikator": source,
                    "peringkat_geo":    "Trend Tahunan",
                    "lokasi":           str(rec.get("tahun_ukur", "")),
                    "negeri":           None,
                    "kawasan_bahagian": None,
                    "daerah":           None,
                    "jantina":          None,
                    "pendapatan":       None,
                    "tahun_ukur":       rec.get("tahun_ukur"),
                    "n_total":          rec.get("n_total", 0),
                    "n_affected":       rec.get("n_affected", 0),
                    "pct":              rec.get("pct", 0),
                })

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
