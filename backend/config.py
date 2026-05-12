# ─── config.py ─────────────────────────────────────────────────────────────────
# Central configuration: schema, geo maps, valid-value sets, auto-mapping hints.
# No hardcoded assumptions about status labels — valid sets are used for
# *spelling correction only*; the source of truth for classification is WHO 2006.

# ─── STANDARD SCHEMA ──────────────────────────────────────────────────────────

STANDARD_SCHEMA = {
    # Identity
    "id":               {"type": "identifier",  "description": "Unique child ID (MyKid / NRIC / IC)"},
    "nama":             {"type": "text",         "description": "Child name"},
    "jantina":          {"type": "categorical",  "description": "Gender (M/F)"},
    "tarikh_lahir":     {"type": "date",         "description": "Date of birth"},
    # Geography
    "negeri":           {"type": "categorical",  "description": "State (Negeri)"},
    "daerah":           {"type": "categorical",  "description": "District (Daerah)"},
    "taska":            {"type": "text",         "description": "TASKA / Clinic name"},
    # Socioeconomic
    "pendapatan":       {"type": "categorical",  "description": "Income group (B40/M40/T20)"},
    "kumpulan_umur":    {"type": "categorical",  "description": "Age group label (from source)"},
    # Measurement
    "tarikh_ukur":      {"type": "date",         "description": "Measurement / assessment date"},
    "berat_kg":         {"type": "numerical",    "description": "Weight (kg)"},
    "tinggi_cm":        {"type": "numerical",    "description": "Height / Length (cm)"},
    "bmi":              {"type": "numerical",    "description": "BMI value"},
    # Birth measurements (Clinic data)
    "berat_lahir_kg":   {"type": "numerical",    "description": "Birth weight (kg)"},
    "panjang_lahir_cm": {"type": "numerical",    "description": "Birth length (cm)"},
    # Nutrition status labels (from source — validated against WHO 2006 z-scores)
    "status_berat":     {"type": "categorical",  "description": "Weight-for-age status label"},
    "status_tinggi":    {"type": "categorical",  "description": "Height-for-age status label"},
    "status_bmi":       {"type": "categorical",  "description": "BMI-for-age status label"},
    # Metadata
    "tahun_ukur":       {"type": "categorical",  "description": "Measurement year"},
    "sumber":           {"type": "categorical",  "description": "Data source tag"},
    # Klinik-specific
    "vaccine_name":     {"type": "categorical",  "description": "Vaccine administered (klinik data)"},
    "status_assessment":{"type": "categorical",  "description": "Assessment completion status"},
}

# ─── CORE FIELDS (used for quality scoring) ───────────────────────────────────

CORE_FIELDS = [
    "id", "berat_kg", "tinggi_cm", "bmi", "negeri", "jantina",
    "status_berat", "status_tinggi", "status_bmi", "tarikh_lahir", "tarikh_ukur",
]

# ─── BIOLOGICAL PLAUSIBILITY RANGES ───────────────────────────────────────────

BIO_RANGES = {
    "berat_kg":           (0.5, 80.0),   # child 0–5 years
    "tinggi_cm":          (30.0, 130.0),  # newborn to 5 years
    "bmi":                (5.0,  40.0),
    "age_months_computed": (0.0, 120.0),
}

# ─── BIRTH WEIGHT CLASSIFICATION (WHO standards) ──────────────────────────────

BIRTH_WEIGHT_CATEGORIES = {
    "extremely_low": (0.0, 1.0),      # <1.0 kg - Extremely Low Birth Weight (ELBW)
    "very_low":      (1.0, 1.5),      # 1.0-1.499 kg - Very Low Birth Weight (VLBW)
    "low":           (1.5, 2.5),      # 1.5-2.499 kg - Low Birth Weight (LBW)
    "normal":        (2.5, 4.0),      # 2.5-3.999 kg - Normal
    "macrosomia":    (4.0, 7.0),      # ≥4.0 kg - Macrosomia (high birth weight)
}

def classify_birth_weight(weight_kg):
    """Classify birth weight according to WHO categories."""
    if weight_kg is None or weight_kg <= 0:
        return None
    if weight_kg < 1.0:
        return "Extremely Low (<1.0 kg)"
    elif weight_kg < 1.5:
        return "Very Low (1.0-1.5 kg)"
    elif weight_kg < 2.5:
        return "Low (1.5-2.5 kg)"  # LBW
    elif weight_kg < 4.0:
        return "Normal (2.5-4.0 kg)"
    else:
        return "Macrosomia (≥4.0 kg)"


# ─── VALID VALUE SETS (spelling check only — NOT used for classification) ──────

STATUS_BERAT_VALID = {
    "normal", "kurang berat badan", "lebihan berat badan",
    "pemantauan lanjut", "obes", "risiko berlebihan berat badan",
    "berlebihan berat badan",
}
STATUS_TINGGI_VALID = {
    "tinggi normal", "bantut", "bantut teruk", "tinggi",
}
STATUS_BMI_VALID = {
    "berat badan normal", "susut", "obes", "berlebihan berat badan",
    "risiko berlebihan berat badan", "kurang berat badan",
}
INCOME_VALID = {"B40", "M40", "T20"}
GENDER_VALID = {"M", "F"}

# ─── NORMALISATION MAPS ───────────────────────────────────────────────────────

GENDER_MAP = {
    "male": "M", "lelaki": "M", "l": "M", "m": "M", "1": "M",
    "female": "F", "perempuan": "F", "wanita": "F", "p": "F", "f": "F", "2": "F",
}
INCOME_MAP = {"b40": "B40", "m40": "M40", "t20": "T20"}

# BMI grouped for chart/Tableau use
BMI_GROUPED_MAP = {
    "susut":                         "susut",
    "berat badan normal":            "normal",
    "kurang berat badan":            "kurang",
    "risiko berlebihan berat badan": "obes_berlebihan",
    "berlebihan berat badan":        "obes_berlebihan",
    "obes":                          "obes_berlebihan",
}

# ─── SENTINEL STRINGS → NaN ───────────────────────────────────────────────────

NULL_SENTINELS = ["<NA>", "nan", "NaN", "None", "NA", "N/A", "n/a", "#N/A", "-", "--", ""]

# ─── GEO HIERARCHY ────────────────────────────────────────────────────────────

SABAH_KAWASAN_MAP = {
    # Pantai Barat
    "kota kinabalu": "Pantai Barat", "penampang": "Pantai Barat",
    "papar": "Pantai Barat", "tuaran": "Pantai Barat",
    "menggatal": "Pantai Barat", "putatan": "Pantai Barat",
    "lok kawi": "Pantai Barat", "inanam": "Pantai Barat",
    # Pedalaman
    "keningau": "Pedalaman", "tambunan": "Pedalaman",
    "nabawan": "Pedalaman", "tenom": "Pedalaman",
    "pensiangan": "Pedalaman", "kemabong": "Pedalaman",
    # Pedalaman Selatan
    "beaufort": "Pedalaman Selatan", "sipitang": "Pedalaman Selatan",
    "membakut": "Pedalaman Selatan",
    # Kudat
    "kudat": "Kudat", "kota marudu": "Kudat",
    "pitas": "Kudat", "banggi": "Kudat",
    # Sandakan
    "sandakan": "Sandakan", "beluran": "Sandakan",
    "kinabatangan": "Sandakan", "tongod": "Sandakan",
    "telupid": "Sandakan",
    # Lahad Datu
    "lahad datu": "Lahad Datu", "semporna": "Lahad Datu",
    "kunak": "Lahad Datu", "silam": "Lahad Datu",
    # Tawau
    "tawau": "Tawau", "kalabakan": "Tawau", "cowie": "Tawau",
}

SARAWAK_BAHAGIAN_MAP = {
    "kuching": "Bahagian Kuching", "bau": "Bahagian Kuching", "lundu": "Bahagian Kuching",
    "samarahan": "Bahagian Samarahan", "kota samarahan": "Bahagian Samarahan",
    "asajaya": "Bahagian Samarahan", "simunjan": "Bahagian Samarahan",
    "serian": "Bahagian Serian", "tebedu": "Bahagian Serian",
    "sri aman": "Bahagian Sri Aman", "lubok antu": "Bahagian Sri Aman",
    "betong": "Bahagian Betong", "spaoh": "Bahagian Betong",
    "sarikei": "Bahagian Sarikei", "meradong": "Bahagian Sarikei",
    "julau": "Bahagian Sarikei", "pakan": "Bahagian Sarikei",
    "sibu": "Bahagian Sibu", "dalat": "Bahagian Sibu", "kanowit": "Bahagian Sibu",
    "mukah": "Bahagian Mukah", "selangau": "Bahagian Mukah", "daro": "Bahagian Mukah",
    "kapit": "Bahagian Kapit", "song": "Bahagian Kapit", "belaga": "Bahagian Kapit",
    "bintulu": "Bahagian Bintulu", "tatau": "Bahagian Bintulu",
    "miri": "Bahagian Miri", "marudi": "Bahagian Miri",
    "niah": "Bahagian Miri", "subis": "Bahagian Miri",
    "limbang": "Bahagian Limbang", "lawas": "Bahagian Limbang",
}

# ─── AUTO-MAPPING HINTS ───────────────────────────────────────────────────────
# Each source type maps standard field names to lists of possible column header
# variants (lowercased). First match wins.

AUTO_MAPPING_HINTS = {
    "myvass": {
        "id":             ["no. mykid", "no mykid", "mykid", "no.mykid", "id kanak-kanak"],
        "nama":           ["nama anak", "nama kanak-kanak", "nama"],
        "jantina":        ["jantina"],
        "tarikh_lahir":   ["tarikh lahir", "dob", "date of birth"],
        "negeri":         ["negeri"],
        "daerah":         ["daerah"],
        "taska":          ["nama taska", "taska", "pusat jagaan"],
        "pendapatan":     ["pendapatan keluarga", "pendapatan", "kumpulan pendapatan"],
        "kumpulan_umur":  ["kumpulan umur"],
        "berat_kg":       ["2026 berat (kg)", "2025 berat (kg)", "2024 berat (kg)",
                           "2023 berat (kg)", "berat (kg)", "berat_kg", "berat"],
        "tinggi_cm":      ["2026 tinggi (cm)", "2025 tinggi (cm)", "2024 tinggi (cm)",
                           "2023 tinggi (cm)", "tinggi (cm)", "tinggi_cm", "tinggi",
                           "2026 panjang (cm)", "2025 panjang (cm)", "2024 panjang (cm)",
                           "2023 panjang (cm)", "panjang (cm)"],
        "bmi":            ["2026 bmi", "2025 bmi", "2024 bmi", "2023 bmi", "bmi"],
        "status_berat":   ["2026 status berat", "2025 status berat", "2024 status berat",
                           "2023 status berat", "status berat", "status_berat"],
        "status_tinggi":  ["2026 status tinggi", "2025 status tinggi", "2024 status tinggi",
                           "2023 status tinggi", "status tinggi", "status_tinggi"],
        "status_bmi":     ["2026 status bmi", "2025 status bmi", "2024 status bmi",
                           "2023 status bmi", "status bmi", "status_bmi"],
        "tarikh_ukur":    ["2026 tarikh pengukuran", "2025 tarikh pengukuran",
                           "2024 tarikh pengukuran", "2023 tarikh pengukuran",
                           "tarikh pengukuran", "tarikh ukur"],
        "tahun_ukur":     ["tahun ukur", "tahun pengukuran"],
        "sumber":         ["sumber", "agensi"],
    },
    "klinik": {
        # "id" first in priority — "ID" column (child MyKid) beats "BIRTH_IC" (parent MyKad)
        "id":             ["id", "no. mykid", "no mykid", "mykid", "birth_ic", "no_ic",
                           "ic", "no. ic", "nric", "child_id", "child id"],
        "nama":           ["nama", "patient name", "nama pesakit", "nama anak"],
        "jantina":        ["jantina", "gender", "sex"],
        "tarikh_lahir":   ["tarikh lahir", "date of birth", "dob", "birthdate"],
        "negeri":         ["negeri", "state"],
        "daerah":         ["daerah", "district"],
        "taska":          ["nama klinik", "klinik", "clinic", "hospital", "nama hospital"],
        "berat_kg":       ["berat lahir (kg)", "berat lahir", "berat (kg)", "weight",
                           "berat", "birth weight", "berat_lahir_kg"],
        "tinggi_cm":      ["panjang lahir (cm)", "panjang lahir (kg)", "panjang lahir",
                           "tinggi (cm)", "tinggi", "panjang", "height", "length",
                           "birth length", "panjang_lahir_cm"],
        "tarikh_ukur":    ["tarikh antropometri", "assessment date", "tarikh assessment",
                           "tarikh pemeriksaan", "visit date", "tarikh_antropometri"],
        "vaccine_name":   ["vaccine_name", "vaccine name", "vaksin", "nama vaksin",
                           "vaccine", "imunisasi"],
        "status_assessment": ["assessment_status", "assessment status", "status assessment",
                               "assessment", "completion status", "status_completion"],
        "pendapatan":     ["pendapatan", "income", "income group"],
        "tahun_ukur":     ["tahun", "year"],
    },
}

# ─── SOURCE TYPE DETECTION ────────────────────────────────────────────────────

def detect_source_type(columns: list) -> str:
    """Detect data source from column names (case-insensitive)."""
    cols_lower = {c.lower().strip() for c in columns}
    joined = " ".join(cols_lower)

    # NCDC/TASKA signals (year-prefixed columns + TASKA name)
    ncdc_signals = ["nama taska", "no. mykid", "pendapatan keluarga", "kumpulan umur",
                    "2023 berat", "2024 berat", "2025 berat", "2026 berat",
                    "2023 status berat", "agensi"]
    
    # Clinic/vaccine signals
    klinik_signals = ["birth_ic", "vaccine_name", "tarikh antropometri",
                      "assessment_status", "panjang lahir", "berat lahir",
                      "nama klinik", "assessment status",
                      "ic_no_passport", "dose_date", "facility_name"]

    ncdc_score = sum(1 for s in ncdc_signals if s in joined or s in cols_lower)
    klinik_score = sum(1 for s in klinik_signals if s in joined or s in cols_lower)

    # If NCDC signals dominate, classify as myvass (TASKA/NCDC format)
    # Otherwise check klinik
    if ncdc_score >= 2:
        return "myvass"
    elif klinik_score > 0:
        return "klinik"
    return "unknown"


def auto_suggest_mapping(columns: list, source_type: str) -> dict:
    """Return a {standard_field: raw_column} mapping based on column name hints."""
    cols_lower = {c.lower().strip(): c for c in columns}
    mapping = {k: None for k in STANDARD_SCHEMA.keys()}
    hints = AUTO_MAPPING_HINTS.get(source_type, {})

    for field, possible in hints.items():
        for p in possible:
            if p.lower() in cols_lower:
                mapping[field] = cols_lower[p.lower()]
                break

    # Fuzzy fallback: if standard field name itself is in columns, use it
    for field in STANDARD_SCHEMA:
        if mapping.get(field) is None and field in cols_lower:
            mapping[field] = cols_lower[field]

    return mapping
