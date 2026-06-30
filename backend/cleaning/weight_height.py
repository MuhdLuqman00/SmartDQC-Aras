"""Weight & height clinical-bound constants for the school-age cohort.

Sourced from the clinical_ranges registry (config-driven — override via global
settings or per-run range_overrides). These mirror the registry values and are
consumed where the school-age bounds are needed (and to assert registry
consistency in tests).

The former source-specific cleaner that lived here (year-conditional drop logic,
2024 measurement-date forcing, fixed cohort BMI categories, client column-rename
map) has been removed: it was dead code, and the live cleaning pipeline in
backend/eda/cleaning.py is the single source of truth. Cohort-specific behaviour
is now driven entirely by the config-overridable clinical_ranges registry.
"""
from backend.clinical_ranges import get_range as _cr_get_range, get_val as _cr_get_val

BERAT_MIN, BERAT_MAX   = _cr_get_range("school_weight")
TINGGI_MIN, TINGGI_MAX = _cr_get_range("school_height")
AGE_MIN_YEARS          = _cr_get_val("school_age_min")
AGE_MAX_YEARS          = _cr_get_val("school_age_max")

BMI_UNDERWEIGHT = _cr_get_val("bmi_underweight")
BMI_OVERWEIGHT  = _cr_get_val("bmi_overweight")
BMI_OBESE       = _cr_get_val("bmi_obese")

STUNTED_THRESHOLD = _cr_get_val("stunted_threshold")
TALL_THRESHOLD    = _cr_get_val("tall_threshold")
