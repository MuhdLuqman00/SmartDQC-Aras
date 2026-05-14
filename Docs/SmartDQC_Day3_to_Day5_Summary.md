# SmartDQC — Days 3 to 5 Technical Summary

> Written for an AI engineer audience. Covers what was built, why each piece exists, and how the components connect.

---

## The System: SmartDQC

SmartDQC is a data quality and analytics backend for the Malaysian Ministry of Health (KKM). The raw data is child nutrition records — weight, height, IC number, district — collected from clinics via myVASS and NCDC. The system ingests this data, cleans it, runs ML/analytics on it, and produces reports for health officers.

**Stack:** FastAPI + PostgreSQL + pandas + scikit-learn + python-pptx/reportlab

**Key nutrition indicators tracked:**
- **WAZ** — Weight-for-Age Z-score → underweight flag
- **HAZ** — Height-for-Age Z-score → stunting flag
- **WHZ/BAZ** — Weight-for-Height / BMI-for-Age Z-score → wasting / overweight flag

All Z-scores use the WHO 2006 Child Growth Standards. A Z-score below −2 SD triggers the corresponding flag.

---

## Day 3: ML Inference Layer

Before Day 3, the system could clean and validate data (completeness, range checks, IC number validation). Day 3 added the **ML inference tier**.

### Anomaly Detection — `POST /ml/flag`

**IsolationForest** (contamination=0.05) on all numeric columns. Fits on the uploaded dataset, flags outliers by anomaly score, and for each flagged row generates correction suggestions:

```json
{
  "row_index": 42,
  "anomaly_score": -0.112,
  "values": { "weight_kg": 320.0, "haz": -1.5 },
  "suggestions": [
    {
      "column": "weight_kg",
      "current_value": 320.0,
      "suggested_value": 32.0,
      "reason": "Value 320.0 is outside the 3x IQR fence [10.2, 58.8]; column median is 32.0"
    }
  ]
}
```

This is **unsupervised** — no labels needed, works on any numeric schema.

### Schema Mapping — `POST /schema/map`

Given an unknown CSV with arbitrary column names, a small LLM call maps them to the canonical KKM schema (`waz`, `haz`, `baz`, `ic_no`, `district`, etc.). Handles three scenarios:

| Scenario | Behaviour |
|----------|-----------|
| Exact match | Direct rename |
| Fuzzy / semantic match | LLM maps + confidence score |
| Unknown column | Flagged as unmapped, human review |

This ensures downstream code always receives a consistent field set regardless of the source system's naming conventions.

### ML Suggest — `POST /ml/suggest`

Combined endpoint: takes a `cache_id` from a prior clean run, runs IsolationForest, returns flagged rows with suggestions. This is what the frontend calls to populate the anomaly review UI.

### Risk Scoring — `POST /risk/score`

Weighted sum of flag columns:

| Flag | Weight |
|------|--------|
| Wasting | 30 |
| Stunting | 25 |
| Underweight | 20 |
| Overweight | 15 |

Produces a **0–100 composite risk score per child**, plus district-level aggregation. Entirely deterministic — no model. Intentional so health officers can audit and explain every score to a non-technical stakeholder.

---

## Day 4: Reporting + KPI Dashboard

Day 4 took the analytics outputs and made them consumable by decision-makers.

### Report Builders — `POST /report/pptx`, `POST /report/pdf`

Given an EDA result dict and an AI narrative dict, builds a 4-slide PPTX or multi-section PDF using **python-pptx** and **reportlab**.

| Slide / Section | Content |
|-----------------|---------|
| 1 — Title | Source system, record count, date |
| 2 — Quality Overview | Completeness %, missing rate, outlier count, indicator rates |
| 3 — AI Narrative | Bilingual executive summary (BM + EN) |
| 4 — Recommendations | Priority-ranked actions |

All **in-memory** — no temp files, bytes returned directly in the HTTP response.

### KPI Dashboard — `POST /kpi/dashboard`

Takes the cleaned DataFrame, computes flag rates (e.g. stunting rate = % of rows where `stunting == 1`), and benchmarks each against **NPAN 2021–2025 national targets**.

**RAG traffic-light logic:**

```python
def _rag(actual, target):
    if actual <= target:         return "Green"
    if actual <= target * 1.20:  return "Amber"
    return "Red"
```

Also produces a per-district breakdown if a district column is present. This is the primary executive view for district health officers.

**At end of Day 4:** 33 tests, ~34 endpoints.

---

## Day 5: Gap Remediation

The Day 3–4 builds shipped fast but were spec-incomplete in 4 features. Day 5 closed those gaps.

### Pre-req: DB Foundation

Added 3 new SQLAlchemy models + Alembic migration `0003_day5_tables.py`:

#### `zscore_archive`
Per-child, per-period Z-score rows. The **historical time-series store** that makes trend analysis possible.

```
ic_no | period  | district | state    | waz   | haz   | baz   | age_months
IC001 | 2025-01 | Petaling | Selangor | -1.80 | -1.50 | -0.50 | 12
IC001 | 2025-02 | Petaling | Selangor | -1.75 | -1.47 | -0.48 | 13
```

#### `indicator_snapshots`
Pre-aggregated per-district, per-period rates. Cheaper to query than re-aggregating `zscore_archive` every request.

```
period  | district | stunting_rate | wasting_rate | underweight_rate | n_records
2025-01 | Petaling | 18.5          | 3.2          | 9.1              | 540
2025-02 | Petaling | 17.1          | 3.0          | 8.8              | 537
```

#### `entity_linkage`
Cross-dataset identity linkage (myVASS ↔ NCDC ↔ KPM). Stores `match_confidence` so the system can flag uncertain deduplication for human review.

---

### Gap 1 — Feature #12: Pattern Classification

The original corrections module said "this value is outside 3×IQR — here's the median." Day 5 added **why it's wrong**.

#### `_detect_decimal_shift(val, median) → str | None`

```python
ratio = val / median
if 9.5 <= ratio <= 10.5:    return "decimal_shift_x10"    # 320 entered instead of 32.0
if 0.095 <= ratio <= 0.105: return "decimal_shift_div10"  # 3.2 entered instead of 32.0
```

Catches the classic data entry error of a misplaced decimal point.

#### `_detect_transposition(val, median) → bool`

Iterates all adjacent-digit swaps of `int(val)`, checks if any result is within 5% of median. Catches `139` entered as `319`.

```python
iv = str(int(abs(val)))       # "139"
for i in range(len(iv) - 1):
    swapped = iv[:i] + iv[i+1] + iv[i] + iv[i+2:]   # "319"
    if abs(int(swapped) - median) / max(abs(median), 1) < 0.05:
        return True
```

#### `_detect_column_swap(val, current_col, col_stats) → str | None`

Checks if the outlier value falls within 1 IQR of *another* column's median. Catches pasting weight into the height column.

```python
# val=25.0 for column "waz" (median=-1.5)
# but 25.0 fits within weight_kg median(25.5) ± IQR(5.0)
# → returns "column_swap:weight_kg"
```

#### `_classify_error_type(pattern) → str`

Maps pattern to a coarse label for the frontend:

```python
if pattern in ("decimal_shift_x10", "decimal_shift_div10", "digit_transposition"):
    return "entry_error"
if pattern and pattern.startswith("column_swap:"):
    return "entry_error"
return "unknown"
```

**Each correction suggestion now carries `pattern` + `error_type`** alongside the existing `suggested_value` + `reason`. A data entry clerk knows *how* they likely made the mistake, not just *that* the value is wrong.

---

### Gap 2 — Feature #11: Historical Z-score Forecasting

`backend/ml/zscore_history.py` — **longitudinal district risk forecasting**.

#### `aggregate_zscore_archive(records) → DataFrame`

Groups raw per-child zscore rows by `(district, period)`, computes mean waz/haz/baz per group. Produces a clean time-series DataFrame for the forecaster.

#### `forecast_district_risk(records) → list[dict]`

For each district:

1. Sort by period → build index `x = [0, 1, 2, ..., n]`
2. Fit `numpy.polyfit(x, waz_mean, deg=1)` → slope + intercept
3. Extrapolate: `forecast = slope * (n + 1) + intercept`
4. Classify trend:
   - slope > 0.05 → `"improving"`
   - slope < -0.05 → `"declining"`
   - else → `"stable"`
5. Map forecasted WAZ to risk tier:
   - < −2.0 → `"High"`
   - < −1.5 → `"Medium"`
   - ≥ −1.5 → `"Low"`

> **Why `numpy.polyfit` not scipy?** Keeps the dependency surface minimal. OLS on 6–12 data points doesn't need anything heavier.

**New endpoint:** `POST /risk/forecast` — accepts zscore_archive records, returns per-district next-quarter risk forecasts. Health program managers use this to prioritize which districts need intervention *before* the next quarter's data arrives.

---

### Gap 3 — Feature #16: WHO Targets + Trajectory Narratives

#### WHO Targets Added to KPI Dashboard

The original dashboard only had NPAN national targets. Day 5 added the **WHO Global Nutrition Targets 2025** as a second benchmark layer:

```python
_WHO_TARGETS = {
    "stunting_rate":    20.0,
    "wasting_rate":     5.0,
    "underweight_rate": 10.0,
    "overweight_rate":  3.0,
}
```

Every KPI entry now carries `who_target`, `who_status` (its own RAG), and `gap_to_who`. A district can be **Green on NPAN but Red on WHO** — that's a meaningful policy signal. National targets are political commitments; WHO targets are the clinical standard.

#### `compute_trajectory_narratives(historical_snapshots, current_breakdown) → list[dict]`

Same OLS approach as the Z-score forecaster, but applied to indicator rates from `indicator_snapshots`. Forecasts **4 periods ahead**, classifies trajectory:

| Status | Condition |
|--------|-----------|
| On Track | `forecast_rate <= target` |
| At Risk | `target < forecast_rate <= target × 1.30` |
| Off Track | `forecast_rate > target × 1.30` |

Generates **bilingual narratives automatically** (BM + EN):

```
EN: "Petaling is projected to meet the stunting_rate target of 15% by 2027.
     At the current trend (-3.00pp/period), the rate will reach 3.0%."

BM: "Petaling dijangka mencapai sasaran stunting_rate sebanyak 15% menjelang 2027.
     Pada kadar semasa (-3.00 mata peratusan/tempoh), kadar akan mencapai 3.0%."
```

These go directly into reports — no human writing required.

**New endpoint:** `POST /kpi/trajectory`

---

### Gap 4 — Feature #15: Reports with Indicator Tables + Methodology

The PPTX/PDF reports gained two new optional sections (only appended when `kpi_result` is passed to the builder).

#### Indicator Table Slide / Section

District-by-district breakdown: N records, stunting %, wasting %, underweight %, overweight %.

- **PPTX:** `pptx.table` with alternating row shading, navy header row
- **PDF:** `reportlab.Table` with matching styling, column widths tuned for A4

#### Methodology Appendix

10-line plain-English/technical description of every analytical choice:

```
- Data Sources: myVASS, CCMS, KPM, NCDC
- Z-Score Standard: WHO 2006 Child Growth Standards (WHO_Anthro v3.2.2)
- Classification: WAZ<-2 SD=Underweight; HAZ<-2 SD=Stunted; WHZ<-2 SD=Wasted
- Anomaly Detection: IsolationForest (contamination=0.05) + 3x IQR fence
- Pattern Classification: Decimal shift (x10/div10), digit transposition, column swap
- Risk Scoring: Weighted flag-sum (Stunting x25, Wasting x30, Underweight x20)
- KPI Benchmarks: NPAN 2021-2025 national targets; WHO Global Targets 2025
- Trend Analysis: OLS linear regression (>=3 periods per district)
- Trajectory: Forecasts 4 periods ahead; On Track if forecast <= NPAN target
```

This matters for a health ministry deliverable — the methodology must be auditable by non-engineers.

`ReportRequest` gained `kpi_result: dict | None = None` as an optional field. Existing integrations don't break.

---

## Net Result: Days 3 to 5

| Metric | Day 3 Start | Day 5 End |
|--------|-------------|-----------|
| Tests | 0 | **59** |
| Endpoints | ~20 | **~37** |
| ML modules | 0 | corrections, schema_mapper, risk_score, zscore_history |
| DB tables | 3 | **6** |
| Report types | none | PPTX (4–6 slides) + PDF |
| KPI benchmarks | none | NPAN national + WHO global |
| Correction insight | "value is wrong" | pattern + error type classification |
| Risk view | point-in-time per child | point-in-time + next-quarter district forecast |
| Narratives | none | AI-generated bilingual, auto-trajectory |

---

## New Endpoints Added (Days 3–5)

| Endpoint | Description |
|----------|-------------|
| `POST /ml/flag` | IsolationForest anomaly detection on uploaded data |
| `POST /ml/suggest` | Anomaly detection + correction suggestions via cache_id |
| `POST /schema/map` | LLM-powered column name mapping to KKM schema |
| `POST /risk/score` | Weighted composite risk score per child + district rollup |
| `POST /risk/forecast` | Next-quarter district risk from historical Z-score archive |
| `POST /kpi/dashboard` | RAG KPI status vs NPAN + WHO targets |
| `POST /kpi/trajectory` | Per-district trajectory narratives (BM + EN) |
| `POST /report/pptx` | PPTX report (4–6 slides depending on kpi_result) |
| `POST /report/pdf` | PDF report with matching content |

---

## Open Items (as of Day 5)

| # | Item | Status |
|---|------|--------|
| 7 | KKM-branded MOH quarterly report template | **Blocked** — awaiting template from client |

The indicator table and methodology appendix in Feature #15 are implemented. The KKM-specific branding/layout for the official MOH quarterly format is on hold until the template is received.
