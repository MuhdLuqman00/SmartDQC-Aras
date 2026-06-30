"""
Clinical and quality range registry — single source of truth for every numeric
bound used by SmartDQC's cleaning and QC rules.

Default values are verbatim copies of the pre-existing constants — no behaviour
change. See Docs/clinical_ranges_provenance.md for tier, source and rationale of
each value.

Three-layer precedence at runtime:
  per-run override (cleaning flow) → global setting (app_settings DB) → defaults here
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


# ─── Registry ─────────────────────────────────────────────────────────────────

RANGES: dict[str, dict[str, Any]] = {

    # ── §1  Cohort plausibility bounds ────────────────────────────────────────

    "infant_weight": {
        "min": 0.5, "max": 35.0, "unit": "kg",
        "tier": "DOM", "source": "cleaning.py:33",
        "group": "Cohort bounds",
        "label_en": "Infant weight bounds",
        "label_bm": "Had berat bayi",
        "recommended": "0.5 – 35.0 kg",
        "why": (
            "Covers the 0–5y cohort: a newborn can be ~0.5 kg (extreme prematurity) "
            "and a heavy 5-year-old tops out around the low-30s kg. Below 0.5 or "
            "above 35 kg for an under-5 is almost certainly an entry error (e.g. "
            "grams typed as kg)."
        ),
    },
    "infant_height": {
        "min": 30.0, "max": 130.0, "unit": "cm",
        "tier": "DOM", "source": "cleaning.py:34",
        "group": "Cohort bounds",
        "label_en": "Infant height/length bounds",
        "label_bm": "Had tinggi/panjang bayi",
        "recommended": "30 – 130 cm",
        "why": (
            "A newborn length is ~45–50 cm (30 cm allows extreme prematurity); "
            "a tall 5-year-old is ~115–120 cm so 130 cm leaves headroom. "
            "Outside this is implausible for an under-5."
        ),
    },
    "school_weight": {
        "min": 12.0, "max": 50.0, "unit": "kg",
        "tier": "DOM", "source": "cleaning.py:37 ≡ weight_height.py:21",
        "group": "Cohort bounds",
        "label_en": "School-age weight bounds",
        "label_bm": "Had berat usia sekolah",
        "recommended": "12 – 50 kg",
        "why": (
            "A small Year-1 (~7y) child is ~15–18 kg; 12 kg is a conservative floor. "
            "50 kg is a generous ceiling for upper primary. Outside → likely entry error."
        ),
    },
    "school_height": {
        "min": 100.0, "max": 160.0, "unit": "cm",
        "tier": "DOM", "source": "cleaning.py:38 ≡ weight_height.py:22",
        "group": "Cohort bounds",
        "label_en": "School-age height bounds",
        "label_bm": "Had tinggi usia sekolah",
        "recommended": "100 – 160 cm",
        "why": (
            "A 7-year-old is ~115–125 cm; 100 cm floor catches infant data misfiled "
            "into a school cohort, 160 cm ceiling catches decimal/units errors."
        ),
    },
    "bio_weight": {
        "min": 0.5, "max": 80.0, "unit": "kg",
        "tier": "DOM", "source": "config.py:59",
        "group": "Cohort bounds",
        "label_en": "Generic weight plausibility bounds",
        "label_bm": "Had plausibiliti berat umum",
        "recommended": "0.5 – 80 kg",
        "why": (
            "Wide safety net for the generic completeness check (not the cohort "
            "cleaners). Wide on purpose — only catches gross nonsense. "
            "Max 80 is intentionally looser than infant_weight (35); different code path."
        ),
    },
    "bio_height": {
        "min": 30.0, "max": 130.0, "unit": "cm",
        "tier": "DOM", "source": "config.py:60",
        "group": "Cohort bounds",
        "label_en": "Generic height plausibility bounds",
        "label_bm": "Had plausibiliti tinggi umum",
        "recommended": "30 – 130 cm",
        "why": "Wide safety net for generic checks; newborn to tall 5-year-old.",
    },
    "bio_bmi": {
        "min": 5.0, "max": 40.0, "unit": "kg/m²",
        "tier": "DOM", "source": "config.py:61",
        "group": "Cohort bounds",
        "label_en": "Generic BMI plausibility bounds",
        "label_bm": "Had plausibiliti BMI umum",
        "recommended": "5 – 40 kg/m²",
        "why": "Catches only gross nonsense; real clinical BMI ceiling is bmi_max.",
    },
    "bio_age_months": {
        "min": 0.0, "max": 120.0, "unit": "months",
        "tier": "DOM", "source": "config.py:62",
        "group": "Cohort bounds",
        "label_en": "Generic age plausibility bounds",
        "label_bm": "Had plausibiliti umur umum",
        "recommended": "0 – 120 months",
        "why": "0 months (newborn) to 10 years (120 months) — outer safety net.",
    },

    # ── §2  WHO biologically-implausible z-score cutoffs ─────────────────────

    "biv_waz": {
        "min": -6.0, "max": 5.0, "unit": "SD",
        "tier": "WHO", "source": "who_zscore.py:131 ≡ cleaning.py:53",
        "group": "WHO BIV z-scores",
        "label_en": "BIV: Weight-for-Age Z (WAZ)",
        "label_bm": "BIV: Z Berat-untuk-Umur (WAZ)",
        "recommended": "−6 to +5",
        "why": (
            "WHO/UNICEF biologically-implausible value flagging limit for WAZ. "
            "A z below −6 or above +5 indicates a data error, not a real child. "
            "Asymmetry (allows +5 not +6) follows the WHO definition."
        ),
    },
    "biv_haz": {
        "min": -6.0, "max": 6.0, "unit": "SD",
        "tier": "WHO", "source": "who_zscore.py:132 ≡ cleaning.py:54",
        "group": "WHO BIV z-scores",
        "label_en": "BIV: Height-for-Age Z (HAZ)",
        "label_bm": "BIV: Z Tinggi-untuk-Umur (HAZ)",
        "recommended": "−6 to +6",
        "why": "WHO/UNICEF BIV limit for HAZ. Symmetric at ±6 per the WHO definition.",
    },
    "biv_baz": {
        "min": -5.0, "max": 5.0, "unit": "SD",
        "tier": "WHO", "source": "who_zscore.py:133 ≡ cleaning.py:55",
        "group": "WHO BIV z-scores",
        "label_en": "BIV: BMI-for-Age Z (BAZ)",
        "label_bm": "BIV: Z BMI-untuk-Umur (BAZ)",
        "recommended": "−5 to +5",
        "why": "WHO/UNICEF BIV limit for BAZ. Tighter than HAZ at ±5 per the WHO definition.",
    },
    "zscore_cap": {
        "value": 6.0, "unit": "SD",
        "tier": "WHO", "source": "who_zscore.py:121",
        "group": "WHO BIV z-scores",
        "label_en": "Z-score computation cap",
        "label_bm": "Had pengiraan z-skor",
        "recommended": "±6",
        "why": (
            "WHO recommends capping computed z at ±6; values past this are treated "
            "as implausible rather than carried into summaries."
        ),
    },

    # ── §3  BMI thresholds ────────────────────────────────────────────────────

    "bmi_max": {
        "value": 40.0, "unit": "kg/m²",
        "tier": "DOM", "source": "cleaning.py:40",
        "group": "BMI thresholds",
        "label_en": "Implausible BMI ceiling",
        "label_bm": "Had siling BMI mustahil",
        "recommended": "40.0 kg/m²",
        "why": (
            "A BMI above 40 in a young child is almost always a height/weight entry "
            "error, not real morbid obesity. Used to drop rows with impossible BMI."
        ),
    },
    "bmi_underweight": {
        "value": 13.5, "unit": "kg/m²",
        "tier": "WHO", "source": "weight_height.py:26",
        "group": "BMI thresholds",
        "label_en": "BMI: underweight cutpoint (age 7, WHO 2007)",
        "label_bm": "BMI: titik potong kurang berat (umur 7, WHO 2007)",
        "recommended": "13.5 kg/m²",
        "why": (
            "Rounded approximation of the WHO 2007 BMI-for-age −2 SD band at age 7. "
            "Applied as a fixed single value across the cohort; adequate for a "
            "7-year focus but a per-age/sex z-score would be more precise."
        ),
    },
    "bmi_overweight": {
        "value": 16.5, "unit": "kg/m²",
        "tier": "WHO", "source": "weight_height.py:27",
        "group": "BMI thresholds",
        "label_en": "BMI: overweight cutpoint (age 7, WHO 2007)",
        "label_bm": "BMI: titik potong berlebihan berat (umur 7, WHO 2007)",
        "recommended": "16.5 kg/m²",
        "why": "Rounded approximation of WHO 2007 BMI-for-age +1 SD band at age 7.",
    },
    "bmi_obese": {
        "value": 18.5, "unit": "kg/m²",
        "tier": "WHO", "source": "weight_height.py:28",
        "group": "BMI thresholds",
        "label_en": "BMI: obese cutpoint (age 7, WHO 2007)",
        "label_bm": "BMI: titik potong obes (umur 7, WHO 2007)",
        "recommended": "18.5 kg/m²",
        "why": "Rounded approximation of WHO 2007 BMI-for-age +2 SD band at age 7.",
    },

    # ── §4  Stunting proxies ──────────────────────────────────────────────────

    "stunted_threshold": {
        "value": 112.0, "unit": "cm",
        "tier": "PROXY", "source": "weight_height.py:31",
        "group": "Stunting proxies",
        "label_en": "Stunted height threshold (proxy)",
        "label_bm": "Had tinggi stunting (proksi)",
        "recommended": "112.0 cm",
        "why": (
            "WEAKEST range in the system — admitted approximation of ≈ −2 SD from the "
            "WHO median height (~120 cm) for a 7-year-old. Stands in for a proper "
            "height-for-age z-score (HAZ) calculation. First candidate to replace."
        ),
    },
    "tall_threshold": {
        "value": 132.0, "unit": "cm",
        "tier": "PROXY", "source": "weight_height.py:32",
        "group": "Stunting proxies",
        "label_en": "Tall height threshold (proxy)",
        "label_bm": "Had tinggi 'tall' (proksi)",
        "recommended": "132.0 cm",
        "why": (
            "PROXY — ≈ +2 SD from WHO median ~120 cm for a 7-year-old. Same caveat "
            "as stunted_threshold: replace with HAZ when possible."
        ),
    },

    # ── §5  Age windows ───────────────────────────────────────────────────────

    "infant_age_cap": {
        "value": 60.0, "unit": "months",
        "tier": "DOM", "source": "cleaning.py:41",
        "group": "Age windows",
        "label_en": "Under-5 age ceiling",
        "label_bm": "Had usia bawah-5",
        "recommended": "60 months",
        "why": (
            "Defines the infant cohort boundary; WHO infant growth standards apply "
            "to 0–5y. Older children route to the school-age BMI path instead."
        ),
    },
    "school_age_min": {
        "value": 6.0, "unit": "years",
        "tier": "DOM", "source": "weight_height.py:23",
        "group": "Age windows",
        "label_en": "School cohort minimum age",
        "label_bm": "Umur minimum kohort sekolah",
        "recommended": "6.0 years",
        "why": (
            "The weight & height sheet targets the Tahun-1 (~7y) intake; "
            "6 years brackets it with one year of tolerance."
        ),
    },
    "school_age_max": {
        "value": 8.0, "unit": "years",
        "tier": "DOM", "source": "weight_height.py:23",
        "group": "Age windows",
        "label_en": "School cohort maximum age",
        "label_bm": "Umur maksimum kohort sekolah",
        "recommended": "8.0 years",
        "why": "Upper tolerance bracket for the Tahun-1 (~7y) intake.",
    },

    # ── §6  Quality-checker outlier bounds (looser tier) ──────────────────────

    "br02_weight_impossible": {
        "min": 10.0, "max": 125.0, "unit": "kg",
        "tier": "DOM", "source": "quality_rules.py:99",
        "group": "Quality checker bounds",
        "label_en": "BR-02: impossible weight bounds",
        "label_bm": "BR-02: had berat mustahil",
        "recommended": "10 – 125 kg",
        "why": (
            "Intentionally LOOSER than school_weight (12–50). Flags only the "
            "physiologically impossible — a 7-year-old cannot be <10 or >125 kg. "
            "Two-tier design: this is 'definitely wrong'; school_weight is "
            "'outside expected cohort'."
        ),
    },
    "br03_height_impossible": {
        "min": 50.0, "max": 200.0, "unit": "cm",
        "tier": "DOM", "source": "quality_rules.py:131",
        "group": "Quality checker bounds",
        "label_en": "BR-03: impossible height bounds",
        "label_bm": "BR-03: had tinggi mustahil",
        "recommended": "50 – 200 cm",
        "why": (
            "Intentionally LOOSER than school_height (100–160). Flags only the "
            "physiologically impossible (<50 or >200 cm for a child). "
            "Same two-tier rationale as BR-02."
        ),
    },
    "br06_year_level": {
        "min": 1, "max": 7, "unit": "year",
        "tier": "DOM", "source": "quality_rules.py:240",
        "group": "Quality checker bounds",
        "label_en": "BR-06: school year level range",
        "label_bm": "BR-06: julat tahun persekolahan",
        "recommended": "1 – 7",
        "why": (
            "Primary school is Tahun 1–6 (+ special class Kelas Khas Rendah). "
            "A level outside 1–7 is a data error for this cohort."
        ),
    },
    "br09_date_window_years": {
        "value": 20, "unit": "years",
        "tier": "DOM", "source": "quality_rules.py:361",
        "group": "Quality checker bounds",
        "label_en": "BR-09: suspicious-date look-back window",
        "label_bm": "BR-09: tetingkap tarikh syak",
        "recommended": "20 years",
        "why": (
            "A measurement date more than 20 years old or in the future is a "
            "system/entry error. Anchored to the runtime clock (not hardcoded year) "
            "so it never goes stale. The '20' is the tunable part."
        ),
    },
    "height_unit_suspect": {
        "value": 200.0, "unit": "cm",
        "tier": "DOM", "source": "cleaning.py:533",
        "group": "Quality checker bounds",
        "label_en": "Height unit-confusion threshold",
        "label_bm": "Had kekeliruan unit tinggi",
        "recommended": "200.0 cm",
        "why": (
            "A height >200 cm for a child suggests a units error (175 entered as "
            "metres, or a stray digit). Flagged for review, not dropped."
        ),
    },

    # ── §7  Geographic bounds ─────────────────────────────────────────────────

    "geo_lat_min": {
        "value": 1.0, "unit": "°N",
        "tier": "GEO", "source": "cleaning.py:524",
        "group": "Geographic bounds",
        "label_en": "Malaysia latitude minimum",
        "label_bm": "Latitud minimum Malaysia",
        "recommended": "1.0 °N",
        "why": "Malaysia's southern extent. Only change if data geography changes.",
    },
    "geo_lat_max": {
        "value": 7.5, "unit": "°N",
        "tier": "GEO", "source": "cleaning.py:524",
        "group": "Geographic bounds",
        "label_en": "Malaysia latitude maximum",
        "label_bm": "Latitud maksimum Malaysia",
        "recommended": "7.5 °N",
        "why": "Malaysia's northern extent.",
    },
    "geo_lon_min": {
        "value": 99.5, "unit": "°E",
        "tier": "GEO", "source": "cleaning.py:525",
        "group": "Geographic bounds",
        "label_en": "Malaysia longitude minimum",
        "label_bm": "Longitud minimum Malaysia",
        "recommended": "99.5 °E",
        "why": "Malaysia's western extent.",
    },
    "geo_lon_max": {
        "value": 119.5, "unit": "°E",
        "tier": "GEO", "source": "cleaning.py:525",
        "group": "Geographic bounds",
        "label_en": "Malaysia longitude maximum",
        "label_bm": "Longitud maksimum Malaysia",
        "recommended": "119.5 °E",
        "why": "Malaysia's eastern extent (Sabah east coast).",
    },

    # ── §8  Birth-weight classification ──────────────────────────────────────

    "birth_weight_elbw": {
        "value": 1.0, "unit": "kg",
        "tier": "WHO", "source": "config.py:70",
        "group": "Birth weight categories",
        "label_en": "Extremely low birth weight ceiling",
        "label_bm": "Had atas berat lahir sangat rendah",
        "recommended": "1.0 kg",
        "why": "WHO: ELBW = <1.0 kg (Extremely Low Birth Weight).",
    },
    "birth_weight_vlbw": {
        "value": 1.5, "unit": "kg",
        "tier": "WHO", "source": "config.py:71",
        "group": "Birth weight categories",
        "label_en": "Very low birth weight ceiling",
        "label_bm": "Had atas berat lahir amat rendah",
        "recommended": "1.5 kg",
        "why": "WHO: VLBW = 1.0–1.499 kg.",
    },
    "birth_weight_lbw": {
        "value": 2.5, "unit": "kg",
        "tier": "WHO", "source": "config.py:72",
        "group": "Birth weight categories",
        "label_en": "Low birth weight ceiling",
        "label_bm": "Had atas berat lahir rendah",
        "recommended": "2.5 kg",
        "why": "WHO: LBW = <2.5 kg — canonical public-health cutoff.",
    },
    "birth_weight_normal_max": {
        "value": 4.0, "unit": "kg",
        "tier": "WHO", "source": "config.py:73",
        "group": "Birth weight categories",
        "label_en": "Normal birth weight ceiling",
        "label_bm": "Had atas berat lahir normal",
        "recommended": "4.0 kg",
        "why": "WHO: normal = 2.5–3.999 kg; ≥4.0 kg → macrosomia.",
    },
}


# ─── Editability governance ───────────────────────────────────────────────────
# Tier-governed editability (decided 2026-06-13, operator perspective): a domain
# officer may SEE every threshold + its source, but may only CHANGE the
# operational DOM-tier bounds that are reachable with override plumbing AND
# proven by a propagation test (see test_clinical_ranges_propagation.py).
#
# Everything else is read-only reference: WHO standards (z-scores, BMI-for-age
# categories, birth-weight bands), PROXY/legacy values, display-only DOM values
# without override plumbing (bio_*), and GEO bounds. Editing those would silently
# desync from international reporting — a clinical-safety footgun, not a feature.
EDITABLE_KEYS: frozenset[str] = frozenset({
    "infant_weight", "infant_height",      # cohort bounds → CohortProfile
    "school_weight", "school_height",       # cohort bounds → CohortProfile
    "bmi_max",                              # _apply_bmi_outlier (override-aware local)
    "infant_age_cap",                       # under-5 age ceiling (override-aware local)
    "br02_weight_impossible",               # QualityChecker ctor injection
    "br03_height_impossible",               # QualityChecker ctor injection
})


# ─── Accessors ────────────────────────────────────────────────────────────────

def get_range(key: str, overrides: dict | None = None) -> tuple[float, float]:
    """Return (min, max) for a range-type key, applying per-run overrides."""
    entry = RANGES[key]
    if overrides and key in overrides:
        ov = overrides[key]
        return (float(ov.get("min", entry["min"])), float(ov.get("max", entry["max"])))
    return (float(entry["min"]), float(entry["max"]))


def get_val(key: str, overrides: dict | None = None) -> float:
    """Return single float for a value-type key, applying per-run overrides."""
    entry = RANGES[key]
    if overrides and key in overrides:
        ov = overrides[key]
        return float(ov if isinstance(ov, (int, float)) else ov.get("value", entry["value"]))
    return float(entry["value"])


def get_biv(overrides: dict | None = None) -> dict[str, tuple[float, float]]:
    """Return BIV thresholds dict {WAZ/HAZ/BAZ: (lo, hi)}, applying overrides."""
    return {
        "WAZ": get_range("biv_waz", overrides),
        "HAZ": get_range("biv_haz", overrides),
        "BAZ": get_range("biv_baz", overrides),
    }


@dataclass(frozen=True)
class CohortProfile:
    """Population-dependent plausibility bounds for one cohort (override-aware)."""
    name: str
    berat_min: float
    berat_max: float
    tinggi_min: float
    tinggi_max: float


def make_infant_profile(overrides: dict | None = None) -> CohortProfile:
    bmin, bmax = get_range("infant_weight", overrides)
    tmin, tmax = get_range("infant_height", overrides)
    return CohortProfile("infant", bmin, bmax, tmin, tmax)


def make_school_profile(overrides: dict | None = None) -> CohortProfile:
    bmin, bmax = get_range("school_weight", overrides)
    tmin, tmax = get_range("school_height", overrides)
    return CohortProfile("school", bmin, bmax, tmin, tmax)


# Module-level default profiles (backward-compat aliases)
PROFILE_INFANT_DEFAULT = make_infant_profile()
PROFILE_SCHOOL_DEFAULT = make_school_profile()


def validate_overrides(overrides: dict) -> tuple[bool, list[str]]:
    """
    Validate an override dict.  Returns (ok, [error_message, ...]).
    Keys must exist in RANGES; min < max for range types; values must be positive.
    """
    errors: list[str] = []
    for key, ov in overrides.items():
        if key not in RANGES:
            errors.append(f"Unknown range key: {key!r}")
            continue
        entry = RANGES[key]
        if "min" in entry:
            lo = float(ov.get("min", entry["min"]))
            hi = float(ov.get("max", entry["max"]))
            if lo >= hi:
                errors.append(f"{key}: min ({lo}) must be < max ({hi})")
        else:
            val = float(ov if isinstance(ov, (int, float)) else ov.get("value", entry["value"]))
            if val <= 0:
                errors.append(f"{key}: value ({val}) must be > 0")
    return (len(errors) == 0, errors)


def to_api_dict(overrides: dict | None = None) -> dict:
    """
    Serialize the full registry for GET /config/clinical-ranges.
    Each entry includes defaults, effective values (with overrides applied),
    tier, recommended, and why — everything the Settings UI and flow panel need.
    """
    result: dict[str, Any] = {}
    for key, entry in RANGES.items():
        item: dict[str, Any] = {
            "tier": entry["tier"],
            "unit": entry["unit"],
            "group": entry["group"],
            "label_en": entry["label_en"],
            "label_bm": entry["label_bm"],
            "recommended": entry["recommended"],
            "why": entry["why"],
            "source": entry["source"],
            # Tier-governed: only EDITABLE_KEYS have working override plumbing.
            # All other keys are read-only reference (shown with source citation).
            "editable": key in EDITABLE_KEYS,
        }
        if "min" in entry:
            lo, hi = get_range(key, overrides)
            item["type"] = "range"
            item["default_min"] = entry["min"]
            item["default_max"] = entry["max"]
            item["effective_min"] = lo
            item["effective_max"] = hi
            item["overridden"] = overrides is not None and key in overrides
        else:
            val = get_val(key, overrides)
            item["type"] = "value"
            item["default_value"] = entry["value"]
            item["effective_value"] = val
            item["overridden"] = overrides is not None and key in overrides
        result[key] = item
    return result
