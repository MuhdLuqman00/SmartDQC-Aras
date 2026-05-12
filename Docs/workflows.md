# SmartDQC — Key Workflows

> Four primary end-to-end workflows.
> For per-dataset step-by-step processing detail, see [SmartDQC_Tool_Flow.md](SmartDQC_Tool_Flow.md).

---

## 1. Schema Mapping (3-Scenario AI Flow)

Triggered on every upload. AI is always-on — not a fallback. See ADR-008.

```
Upload CSV/Excel
       |
Extract column headers + sample data (first 5 rows)
       |
thefuzz: compare against known source schemas
       |
    +---------------------+---------------------+
    |                     |                     |
Exact match          Schema drift          Unknown schema
    |                     |                     |
Auto-map via         AI contextual          AI generates new
thefuzz rules        mapping:               compatible schema
(config.py)          - map new columns      dynamically
                     - infer renames
                     - warn on missing
                     - flag type changes
    |                     |                     |
    +---------------------+---------------------+
                     |
           User reviews + confirms
                     |
             Pipeline proceeds
```

**Current state (Day 1):** Scenario 1 only. Scenarios 2 and 3 are Day 5 scope.

**Endpoints:** `POST /upload/preview` | `POST /mapping/validate`

---

## 2. Data Cleaning Pipeline

```
Upload confirmed
       |
Schema Mapping (Workflow 1)
       |
Column Mapping (user confirms / AI validates)
       |
[DATA] Derived Field Computation
  - Age in days/months/years
  - Geo enrichment (Kawasan Sabah, Bahagian Sarawak)
  - WHO Z-scores: WAZ, HAZ, BAZ (daily LMS tables)
  - BMI recalculation; source BMI dropped
  - Nutritional indicator flags
       |
[DATA] Data Quality Assessment
  - Predefined business rules (9 known KKM rules)
  - Data quality rules (completeness, outliers, biological plausibility)
  - Overall quality score
       |
[DATA] Data Cleaning
  - Normalise: gender, dates, IC, text
  - Validate: IC format, measurement bounds, z-score BIV range
  - Remove: invalid rows per source-specific rules
       |
[Day 3 - DATA+AI] ML Correction Suggestions (Feature #12)
  - Detect decimal shifts, digit transpositions, column swaps
  - Row-level editing: accept / reject / manual override
  - All edits appended to audit_log
       |
[Day 2 - AI] Narrative Generation (Features #9 + #10)
  - Call 1: insights + explainability (see Workflow 3)
  - Call 2: recommendations using Call 1 as context
  - Stored in analysis_results
       |
[Day 3 - AI] Report Generation (Feature #15)
  - Reads stored JSON from analysis_results — no new LLM call
  - Renders: React component (in-app) + PDF/PPTX (report)
       |
Export
  - Cleaned CSV/XLSX
  - 9-tab Data Quality Report Excel
  - Tableau-ready aggregated flat table
  - AI narrative (in-app + PDF/PPTX)
```

---

## 3. AI Narrative Generation (Features #9 + #10)

Two sequential LLM calls. Result stored in `analysis_results`, reused by Feature #15. See ADR-004 and ADR-005.

```
EDA pipeline completes
       |
Call 1 - Insights
  Input:  dataset summary, indicator distributions, outlier counts, historical comparison
  Output: executive_summary + insights_5w1h (6 dimensions x BM/EN) + explainability.flags
       |
Call 2 - Recommendations
  Input:  Call 1 output + same dataset context
  Output: recommendations[] (action, priority, BM/EN, reasoning)
       |
Merge both -> stored as one analysis_results record (result_type="narrative")
       |
       +-- Render A: React component — casual, present tense, interactive
       +-- Render B: PDF/PPTX template — formal BM/EN, ministry section structure
```

**5W1H Framework:**

| Dimension | Per-Record Example | Dataset-Level Example |
|-----------|-------------------|----------------------|
| **Who** | Patient IC 123456 | Children aged 6-24 months in Selangor |
| **What** | WAZ = -3.2 (severely underweight) | 12.4% severe undernutrition rate |
| **When** | Measured March 2025 | Q1 2025 vs Q1 2024 |
| **Where** | Klinik Kesihatan Petaling | Districts: Klang, Petaling, Gombak |
| **Why** | Z-score below -3 SD | Rate exceeds national benchmark by 4.1pp |
| **How** | WHO 2006 Growth Standards applied | Trend analysis across 4 quarters |

---

## 4. Multi-Dataset Analysis Workflow

**Status:** Day 5 scope. Not yet implemented.

```
User opens Dataset Library (UI)
       |
Browse past uploads (source, date, row count, quality score)
  <- all stored in datasets table (Day 1)
       |
Select 2+ datasets
       |
Trigger combined analysis:
  - Side-by-side quality comparison
  - Trend deltas (same source, different time periods)
  - Cross-source entity matching (Feature #14 - IC + DOB fuzzy match)
  - AI narrative for the comparison (BM + English)
       |
Export comparative report
```

**Prerequisites:**
- `datasets` table (Day 1 complete)
- `entity_linkage` table (Day 5)
- Feature #14 MVP (Day 5)
- Dataset Library UI (Day 5 frontend scaffold)

---

*Source: `Docs/SmartDQC_Master.md` §6*
