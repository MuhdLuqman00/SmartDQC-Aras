"""Generate two synthetic SmartDQC datasets that exercise every feature.

Outputs:
  data/test/smartdqc_test_myvass.csv   (~1500 rows)
  data/test/smartdqc_test_klinik.csv   (~800 rows, ~30% IC overlap with the
                                        MyVASS file plus a handful of
                                        near-matches for fuzzy linkage)

Run:  python scripts/generate_test_data.py

Designed to make ALL 20 chart blocks render:
  • Histograms (BMI, weight, height, age, WAZ/HAZ/BAZ)
  • Scatters (weight×height, BMI×age, z-scores × age)
  • Donuts (WAZ/HAZ/BAZ class, BMI status)
  • Trend by year (3 years of measurements)
  • Gender split, records by state, income split, vaccine distribution

Includes deliberate quality issues so the cleaner / quality report has
something to find:
  • ~3% missing values in non-key columns
  • ~2% duplicate rows (same IC + same measurement date)
  • ~5% measurement outliers (impossible heights / weights)
  • A handful of bad IC formats
"""
from __future__ import annotations

import csv
import os
import random
from datetime import date, datetime, timedelta
from pathlib import Path

RNG_SEED = 20260520
random.seed(RNG_SEED)

# ── Geography ────────────────────────────────────────────────────────────────
# state -> (state_code_for_ic, [sample districts])
STATES: dict[str, tuple[str, list[str]]] = {
    "Johor":           ("01", ["Johor Bahru", "Batu Pahat", "Kluang", "Muar", "Segamat"]),
    "Kedah":           ("02", ["Alor Setar", "Sungai Petani", "Kulim", "Langkawi"]),
    "Kelantan":        ("03", ["Kota Bharu", "Pasir Mas", "Tumpat", "Tanah Merah"]),
    "Melaka":          ("04", ["Melaka Tengah", "Alor Gajah", "Jasin"]),
    "Negeri Sembilan": ("05", ["Seremban", "Port Dickson", "Nilai", "Jelebu"]),
    "Pahang":          ("06", ["Kuantan", "Temerloh", "Bentong", "Raub"]),
    "Pulau Pinang":    ("07", ["George Town", "Bukit Mertajam", "Butterworth", "Bayan Lepas"]),
    "Perak":           ("08", ["Ipoh", "Taiping", "Teluk Intan", "Sitiawan"]),
    "Perlis":          ("09", ["Kangar", "Arau"]),
    "Selangor":        ("10", ["Shah Alam", "Petaling Jaya", "Klang", "Kajang", "Subang Jaya"]),
    "Terengganu":      ("11", ["Kuala Terengganu", "Kemaman", "Dungun"]),
    "Sabah":           ("12", ["Kota Kinabalu", "Sandakan", "Tawau", "Lahad Datu"]),
    "Sarawak":         ("13", ["Kuching", "Miri", "Sibu", "Bintulu"]),
    "Kuala Lumpur":    ("14", ["Cheras", "Wangsa Maju", "Kepong", "Bangsar"]),
    "Labuan":          ("15", ["Labuan"]),
    "Putrajaya":       ("16", ["Putrajaya"]),
}

# State frequency weights (rough — bigger states get more records). Tuned so
# the choropleth shows clear variation between Selangor (dense) and Perlis
# (sparse).
STATE_WEIGHTS = {
    "Selangor": 18, "Kuala Lumpur": 12, "Johor": 12, "Pulau Pinang": 8,
    "Perak": 9,    "Kedah": 7,         "Sabah": 9,  "Sarawak": 7,
    "Pahang": 6,   "Negeri Sembilan": 5, "Kelantan": 6, "Terengganu": 4,
    "Melaka": 4,   "Perlis": 2,        "Labuan": 1, "Putrajaya": 1,
}

NAMES_MALE   = ["Ahmad", "Muhammad", "Aiman", "Adam", "Daniel", "Hakim", "Iman", "Faris", "Zaid", "Harith",
                "Aravind", "Karthik", "Rajesh", "Wei Jian", "Jun Hao"]
NAMES_FEMALE = ["Nur", "Siti", "Aisyah", "Hana", "Aaliyah", "Maryam", "Sofea", "Nurul", "Lina", "Zahra",
                "Priya", "Lakshmi", "Mei Ling", "Xin Yi", "Hui Min"]
SURNAMES     = ["bin Ismail", "binti Ismail", "bin Hassan", "binti Hassan", "bin Rahman", "binti Rahman",
                "a/l Subramaniam", "a/p Subramaniam", "Lim", "Tan", "Lee", "Wong", "Ng",
                "bin Abdullah", "binti Abdullah"]

INCOMES  = ["B40", "M40", "T20"]
INCOME_W = [60, 30, 10]

VACCINES = ["BCG", "Hepatitis B", "DTaP", "Polio", "Hib", "MMR", "Pneumococcal", "Rotavirus"]


# ── Helpers ──────────────────────────────────────────────────────────────────

def random_dob(min_age_months: int = 1, max_age_months: int = 60,
               ref: date = date(2026, 4, 30)) -> date:
    """Pick a DOB so the child is between min_age_months and max_age_months
    old as of `ref`."""
    days_old = random.randint(min_age_months * 30, max_age_months * 30)
    return ref - timedelta(days=days_old)


def make_ic(dob: date, state_code: str) -> str:
    """12-digit Malaysian IC: YYMMDD + 2-digit state + 4-digit serial."""
    serial = random.randint(1, 9999)
    return f"{dob.strftime('%y%m%d')}{state_code}{serial:04d}"


def fuzzy_one_digit(ic: str) -> str:
    """Flip a single digit in the serial portion — produces an IC that v2
    fuzzy matching should still link via Levenshtein ≤1."""
    digits = list(ic)
    pos = random.randint(8, 11)
    orig = digits[pos]
    repl = random.choice([d for d in "0123456789" if d != orig])
    digits[pos] = repl
    return "".join(digits)


def compute_age_months(dob: date, when: date) -> int:
    return max(0, (when.year - dob.year) * 12 + (when.month - dob.month))


def reference_weight_height(age_months: int, gender: str) -> tuple[float, float]:
    """Rough WHO-aligned reference. Not authoritative — just produces
    plausibly-distributed data."""
    # Height ~ logarithmic growth from 50cm at 0mo to ~110cm at 60mo
    base_h = 50 + 16.5 * (age_months ** 0.5) * 0.7
    if gender == "P":
        base_h -= 1.5  # slight gender offset
    base_w = 0.20 * base_h - 6.5  # rough linear height→weight relationship
    return round(base_w, 1), round(base_h, 1)


def add_noise(value: float, sd_pct: float) -> float:
    return round(value * (1 + random.gauss(0, sd_pct)), 1)


def waz_class_from_z(z: float) -> str:
    if z < -3: return "Severely underweight"
    if z < -2: return "Underweight"
    if z <= 2: return "Normal"
    return "Overweight"


def haz_class_from_z(z: float) -> str:
    if z < -3: return "Severely stunted"
    if z < -2: return "Stunted"
    if z <= 2: return "Normal"
    return "Tall"


def baz_class_from_z(z: float) -> str:
    if z < -3: return "Severely wasted"
    if z < -2: return "Wasted"
    if z <= 1: return "Normal"
    if z <= 2: return "Overweight"
    return "Obese"


def bmi_status_grouped(bmi: float, age_months: int) -> str:
    """Coarse BMI-status grouping — under-fives use different cutoffs but
    we keep it readable. Drives the `status_bmi_grouped` column."""
    if bmi < 14: return "Underweight"
    if bmi <= 17: return "Normal"
    if bmi <= 18.5: return "Overweight"
    return "Obese"


# Upstream Malay status columns the backend cleaner expects — derived
# from Z-scores using standard nomenclature. Without these, the
# label-based flag pipeline in eda/indicators.py:_add_label_based_flags
# falls back to False for every row → trend chart is empty.

def status_berat_from_waz(waz: float) -> str:
    if waz < -3: return "Sangat Kurang Berat Badan"
    if waz < -2: return "Kurang Berat Badan"
    if waz > 2:  return "Berlebihan Berat Badan"
    return "Normal"


def status_tinggi_from_haz(haz: float) -> str:
    if haz < -3: return "Bantut Teruk"
    if haz < -2: return "Bantut"
    return "Normal"


def status_bmi_from_baz(baz: float) -> str:
    if baz < -3: return "Susut Teruk"
    if baz < -2: return "Susut"
    if baz > 2:  return "Obes"
    if baz > 1:  return "Risiko Berlebihan Berat Badan"
    return "Normal"


# ── Row generator ────────────────────────────────────────────────────────────

def build_myvass_row(force_ic: str | None = None) -> dict:
    state = random.choices(list(STATE_WEIGHTS.keys()), weights=list(STATE_WEIGHTS.values()))[0]
    state_code, districts = STATES[state]
    district = random.choice(districts)

    dob = random_dob()
    gender = random.choice(["L", "P"])
    ic = force_ic or make_ic(dob, state_code)

    # Measurement date spread across 3 years for the trend chart.
    measure_date = date(
        random.choice([2024, 2025, 2026]),
        random.randint(1, 12),
        random.randint(1, 28),
    )
    if measure_date < dob:
        measure_date = dob + timedelta(days=random.randint(30, 365))
    age_m = compute_age_months(dob, measure_date)

    ref_w, ref_h = reference_weight_height(age_m, gender)
    weight = add_noise(ref_w, 0.10)
    height = add_noise(ref_h, 0.05)
    # ~5% outliers — flip weight or height to an implausible value.
    if random.random() < 0.05:
        if random.random() < 0.5:
            weight = round(weight * random.choice([0.3, 3.0]), 1)
        else:
            height = round(height * random.choice([0.4, 2.5]), 1)

    bmi = round(weight / ((height / 100) ** 2), 1) if height > 0 else None

    # Simplified z-scores: deviation from population mean of (weight, height,
    # bmi) at this age, scaled to roughly ±3.
    waz = round(random.gauss(0, 1.05), 2)
    haz = round(random.gauss(0, 1.10), 2)
    baz = round(random.gauss(0, 1.00), 2)
    # Deliberate malnutrition injection so the trend chart has real
    # shape across all 3 years. Rates chosen to roughly match Malaysia's
    # NPAN baseline: stunting ~21%, underweight ~14%, wasting ~9%,
    # obesity ~6%. The independent rolls let each indicator hit its own
    # target prevalence rather than always co-occurring.
    if random.random() < 0.14:
        waz = round(random.gauss(-2.5, 0.4), 2)  # underweight tail
    if random.random() < 0.21:
        haz = round(random.gauss(-2.5, 0.4), 2)  # stunting tail
    roll = random.random()
    if roll < 0.09:
        baz = round(random.gauss(-2.5, 0.4), 2)  # wasting tail
    elif roll < 0.15:
        baz = round(random.gauss(2.7, 0.4), 2)   # obesity tail

    first  = (random.choice(NAMES_FEMALE) if gender == "P" else random.choice(NAMES_MALE))
    second = random.choice(NAMES_FEMALE + NAMES_MALE)
    surname = random.choice(SURNAMES)
    name = f"{first} {second} {surname}"

    kat_umur = "Bawah 2 Tahun" if age_m < 24 else "Bawah 5 Tahun"

    return {
        "IC_NO_PASSPORT": ic,
        "NAMA": name,
        "Tarikh_Lahir": dob.isoformat(),
        "jantina": gender,
        "negeri": state,
        "daerah": district,
        "pendapatan": random.choices(INCOMES, weights=INCOME_W)[0],
        "Tarikh_Pengukuran": measure_date.isoformat(),
        "tahun_ukur": measure_date.year,
        "berat_kg": weight,
        "tinggi_cm": height,
        "bmi": bmi,
        "age_months_computed": age_m,
        "Kategori_Umur": kat_umur,
        "waz": waz,
        "haz": haz,
        "baz": baz,
        "waz_class": waz_class_from_z(waz),
        "haz_class": haz_class_from_z(haz),
        "baz_class": baz_class_from_z(baz),
        "status_bmi_grouped": bmi_status_grouped(bmi, age_m) if bmi else None,
        # Upstream status columns the cleaner's _add_label_based_flags()
        # consumes. Without these, the cleaner sets every ind_*_label
        # to False and the trend chart goes empty.
        "status_berat":  status_berat_from_waz(waz),
        "status_tinggi": status_tinggi_from_haz(haz),
        "status_bmi":    status_bmi_from_baz(baz),
        "ind_bantut_zscore":       1 if haz < -2 else 0,
        "ind_obes_zscore":         1 if baz > 2  else 0,
        "ind_kurang_berat_zscore": 1 if waz < -2 else 0,
        "ind_susut_zscore":        1 if baz < -2 else 0,
        "ind_bantut_label":        "Stunted"    if haz < -2 else "Normal",
        "ind_obes_label":          "Obese"      if baz > 2  else "Normal",
        "ind_kurang_berat_label":  "Underweight" if waz < -2 else "Normal",
        "ind_susut_label":         "Wasted"     if baz < -2 else "Normal",
    }


def build_klinik_row(force_ic: str | None = None) -> dict:
    """Klinik rows look similar to MyVASS but always have a vaccine column
    and a klinik-specific source_type. Used to exercise the cross-dataset
    linkage feature."""
    row = build_myvass_row(force_ic=force_ic)
    row["vaccine_name"] = random.choice(VACCINES)
    return row


# ── Quality-issue injection ──────────────────────────────────────────────────

NON_KEY_COLS_FOR_MISSING = [
    "pendapatan", "berat_kg", "tinggi_cm", "bmi", "waz", "haz", "baz",
    "waz_class", "haz_class", "baz_class", "status_bmi_grouped", "daerah",
]


def inject_issues(rows: list[dict], missing_rate: float = 0.03,
                  duplicate_rate: float = 0.02) -> list[dict]:
    """Blank ~missing_rate% of cells in non-key columns and add ~duplicate_rate%
    exact duplicates so the cleaner / quality report has issues to surface."""
    out = list(rows)

    # Missing values
    cells = len(out) * len(NON_KEY_COLS_FOR_MISSING)
    to_blank = int(cells * missing_rate)
    for _ in range(to_blank):
        r = random.randrange(len(out))
        c = random.choice(NON_KEY_COLS_FOR_MISSING)
        out[r] = {**out[r], c: ""}

    # Duplicates — pick rows at random and append a copy
    n_dup = max(1, int(len(out) * duplicate_rate))
    for _ in range(n_dup):
        out.append(dict(out[random.randrange(len(out))]))

    # A handful of malformed ICs to exercise the IC format check
    for _ in range(max(1, len(out) // 200)):
        r = random.randrange(len(out))
        out[r] = {**out[r], "IC_NO_PASSPORT": out[r]["IC_NO_PASSPORT"][:-2]}

    random.shuffle(out)
    return out


# ── Write ────────────────────────────────────────────────────────────────────

def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _inject_linkage_conflicts(klinik: list[dict], myvass_lookup: dict[str, dict]) -> dict:
    """Mutate klinik rows that share an IC with MyVASS so the v2 linkage UI
    has real contradictions to surface. Returns counts for logging."""
    counts = {"gender": 0, "dob_drift": 0, "name_variant": 0, "district_drift": 0}
    overlapping = [r for r in klinik if r["IC_NO_PASSPORT"] in myvass_lookup]
    random.shuffle(overlapping)

    # 15 hard gender mismatches (flip L↔P in klinik)
    for r in overlapping[:15]:
        r["jantina"] = "P" if r["jantina"] == "L" else "L"
        counts["gender"] += 1

    # 10 DOB drifts by ±1 day (still inside v2 tolerance default — these
    # should still LINK and NOT raise a hard conflict; v2 only flags hard
    # when drift > tolerance)
    for r in overlapping[15:25]:
        d = datetime.fromisoformat(r["Tarikh_Lahir"]).date()
        r["Tarikh_Lahir"] = (d + timedelta(days=random.choice([-1, 1]))).isoformat()
        counts["dob_drift"] += 1

    # 10 name variants: insert/remove "bin"/"binti" particles (should be
    # treated as soft conflict because fuzzy >= 0.85 but not exact)
    for r in overlapping[25:35]:
        parts = r["NAMA"].split()
        if "bin" in parts or "binti" in parts:
            r["NAMA"] = " ".join(p for p in parts if p.lower() not in ("bin", "binti"))
        else:
            # Insert "bin" between first and last token
            if len(parts) >= 2:
                parts.insert(1, "bin")
                r["NAMA"] = " ".join(parts)
        counts["name_variant"] += 1

    # 8 district drifts within the same state (soft conflict)
    for r in overlapping[35:43]:
        state = r["negeri"]
        if state in STATES:
            districts = STATES[state][1]
            other = [d for d in districts if d != r["daerah"]]
            if other:
                r["daerah"] = random.choice(other)
                counts["district_drift"] += 1
    return counts


def main() -> None:
    here = Path(__file__).resolve().parent.parent
    out_dir = here / "data" / "test"

    # ── MyVASS: 1500 unique children ─────────────────────────────────────
    myvass = [build_myvass_row() for _ in range(1500)]
    myvass_ics = [r["IC_NO_PASSPORT"] for r in myvass]
    myvass_lookup = {r["IC_NO_PASSPORT"]: r for r in myvass}

    # ── Klinik: 800 rows where ~30% share ICs with MyVASS for linkage ────
    overlap_n = 240   # 30% of 800
    fuzzy_n   = 20    # one-digit-off fuzzy IC variants
    fresh_n   = 800 - overlap_n - fuzzy_n

    overlap_ics = random.sample(myvass_ics, overlap_n)
    fuzzy_ics   = [fuzzy_one_digit(ic) for ic in random.sample(myvass_ics, fuzzy_n)]

    klinik = (
        [build_klinik_row(force_ic=ic) for ic in overlap_ics]
        + [build_klinik_row(force_ic=ic) for ic in fuzzy_ics]
        + [build_klinik_row()           for _  in range(fresh_n)]
    )

    # Inject linkage-specific conflicts BEFORE adding generic missing/dupe
    # noise so the conflict-bearing rows are guaranteed present.
    conflict_counts = _inject_linkage_conflicts(klinik, myvass_lookup)

    myvass = inject_issues(myvass, missing_rate=0.03, duplicate_rate=0.02)
    klinik = inject_issues(klinik, missing_rate=0.04, duplicate_rate=0.015)

    write_csv(out_dir / "smartdqc_test_myvass.csv", myvass)
    write_csv(out_dir / "smartdqc_test_klinik.csv", klinik)

    print("Wrote:")
    print(f"  {out_dir/'smartdqc_test_myvass.csv'}   {len(myvass):>5} rows × {len(myvass[0])} cols")
    print(f"  {out_dir/'smartdqc_test_klinik.csv'}   {len(klinik):>5} rows × {len(klinik[0])} cols")
    print()
    print("Linkage expectations (v2):")
    print(f"  exact-IC matches:   ~{overlap_n}")
    print(f"  fuzzy-IC matches:   ~{fuzzy_n}")
    print(f"  gender conflicts:    {conflict_counts['gender']} (hard)")
    print(f"  DOB drift ±1d:       {conflict_counts['dob_drift']} (matched, no conflict)")
    print(f"  name variants:       {conflict_counts['name_variant']} (soft conflict)")
    print(f"  district drifts:     {conflict_counts['district_drift']} (soft conflict)")


if __name__ == "__main__":
    main()
