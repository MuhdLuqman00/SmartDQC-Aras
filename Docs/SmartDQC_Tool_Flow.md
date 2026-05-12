# SmartDQC — Tool Flow Visualization
> Per-dataset: Upload → Process → Output with AI / Data feature labels

---

## Overview — Supported Datasets

```
          ┌──────────────────────────────────────────────────┐
          │                     UPLOAD                        │
          │            CSV / XLSX / XLS                       │
          │         (single or multi-file)                    │
          └──────────────────┬───────────────────────────────┘
                             │
              Auto-detect source type
                             │
     ┌───────────┬───────────┼───────────┬───────────┐
     │           │           │           │           │
 ┌───▼────┐ ┌───▼────┐ ┌───▼────┐ ┌───▼──────────────┐
 │ MyVASS │ │  NCDC  │ │  KPM  │ │      KKM          │
 │(Klinik/│ │(TASKA) │ │(Sekolah│ │ (KKM BeratTinggi │
 │  GIS)  │ │        │ │ KPM)  │ │  7-yr standalone) │
 └───┬────┘ └───┬────┘ └───┬────┘ └───┬──────────────┘
     │          │          │          │
  PROCESS    PROCESS    PROCESS    PROCESS
     │          │          │          │
  OUTPUT     OUTPUT     OUTPUT     OUTPUT
```

> **Architecture note:** MyVASS, NCDC, and KPM run through the **FastAPI backend** (`/clean/*`, `/eda/*` endpoints).
> KKM runs as a **standalone desktop script** (`clean_kkm_data.py`) with a Tkinter file-picker UI — it is NOT part of the API.

---

## Legend

| Label | Meaning |
|-------|---------|
| `[DATA]` | Pure data processing — deterministic rules, computation, statistics |
| `[AI]` | AI / LLM-assisted — model inference, intelligent suggestions, narrative generation |
| `[DATA+AI]` | Hybrid — data computation feeds AI output |

---

---

# Dataset 1 — MyVASS

> Child vaccination + anthropometry records from Klinik/GIS.
> Supports single-file upload **or** multi-file merge (dedup by IC + latest DOSE_DATE).

---

## 1A. Upload

```
┌─────────────────────────────────────────────────────────┐
│  UPLOAD — MyVASS                                        │
│                                                         │
│  Single file  ──►  POST /upload/preview                 │
│  Multi-file   ──►  POST /upload/merge-preview           │
│                        ↓                               │
│  • Header mismatch check across files        [DATA]     │
│  • Concatenate all files                     [DATA]     │
│  • Dedup by IC_NO_PASSPORT                   [DATA]     │
│    (keep row with latest DOSE_DATE)                     │
│  • Remove rows with any null cell            [DATA]     │
│                        ↓                               │
│  • Auto-detect source type (myvass/klinik)   [DATA]     │
│  • Column preview (paginated)                [DATA]     │
│  • Auto-suggest schema mapping               [DATA]     │
│  • AI schema mapping confirmation         ── [AI]       │
│    (LLM validates/corrects mapping,                     │
│     handles unknown/drifted column names)               │
└─────────────────────────────────────────────────────────┘
```

**Endpoints:** `POST /upload/preview` · `POST /upload/merge-preview`
**Mapping validation:** `POST /mapping/validate`

---

## 1B. Process — MyVASS Cleaning Pipeline

```
  Raw Data (post-upload)
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 1 — Gender Standardisation                [DATA]   │
│  • Normalise: LELAKI→Male, PEREMPUAN→Female, etc.       │
│  • DROP rows where gender = invalid/missing             │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 2 — Date Parsing                          [DATA]   │
│  • Parse Tarikh_Lahir (DOB)                             │
│  • Parse Tarikh_Ukur (measurement date)                 │
│  • DROP rows where Tarikh_Ukur < Tarikh_Lahir           │
│    (Rule 4: date before birth)                          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 3 — Age Computation                       [DATA]   │
│  • Age_Days  = Tarikh_Ukur − Tarikh_Lahir               │
│  • Age_Months = Age_Days / 30.4375                      │
│  • DROP rows where Age_Months ≥ 60                      │
│    (Rule 3: over 5 years)                               │
│  • Kategori_Umur: Bawah 2 Tahun / Bawah 5 Tahun        │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 4 — Measurement Outlier Filter            [DATA]   │
│  • Berat_kg valid range: 0.5 – 35.0 kg                  │
│  • Tinggi_cm valid range: 30.0 – 130.0 cm               │
│  • DROP rows outside biological range (Rule 2)          │
│  • DROP rows where BOTH weight AND height null (Rule 6) │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 5 — BMI Recalculation                     [DATA]   │
│  • Drop source BMI column (unreliable)                  │
│  • BMI = weight / (height/100)²                         │
│  • DROP rows where BMI > 40 (Rule 5: implausible)       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 6 — WHO Z-Score Computation               [DATA]   │
│  • WAZ (Weight-for-Age Z-score)                         │
│  • HAZ (Height-for-Age Z-score)                         │
│  • BAZ (BMI-for-Age Z-score)                            │
│  • Uses daily LMS tables (WHO 2006 standards)           │
│  • BIV filter: WAZ −6↔+5 · HAZ −6↔+6 · BAZ −5↔+5      │
│  • DROP rows with any null z-score (Rule 7)             │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 7 — Z-Score Classification                [DATA]   │
│  WAZ_Status:                                            │
│    kurang_berat_badan_teruk / kurang_berat_badan /      │
│    risiko_kurang_berat_badan / berat_badan_normal /     │
│    mungkin_masalah_pertumbuhan                          │
│  HAZ_Status:                                            │
│    bantut_teruk / bantut / risiko_bantut /              │
│    normal / mungkin_masalah_endokrin                    │
│  BAZ_Status:                                            │
│    susut_teruk / susut / berisiko_susut /               │
│    normal / risiko_lebih_berat_badan /                  │
│    berlebihan_berat_badan / obes                        │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 8 — Indicator Flags                       [DATA]   │
│  • Ind_Kurang_Berat_Badan  (WAZ < −2)                   │
│  • Ind_Bantut              (HAZ < −2)                   │
│  • Ind_Susut               (BAZ < −2)                   │
│  • Ind_Berlebihan_BB       (BAZ > +1)                   │
│  • Ind_Obes                (BAZ > +2)                   │
│  • Ind_Normal                                           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 9 — EDA Analysis Modules                  [DATA]   │
│  • Completeness scoring                                 │
│  • Outlier detection (statistical)                      │
│  • Numerical summary (mean/sd/quartiles)                │
│  • Categorical summary (frequency, unique counts)       │
│  • BMI consistency check (flag_bmi_mismatch)            │
│  • Geo enrichment: Kawasan (Sabah) / Bahagian (Sarawak) │
│  • IC/MyKid validation & dedup analysis                 │
│  • Spelling check on status labels                      │
│  • Quality score (overall completeness %)               │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 10 — ML Correction Suggestions          [DATA+AI]  │
│  • Flag mismatches: source status label vs z-score      │
│    (flag_status_berat_vs_zscore, etc.)                  │
│  • AI suggests corrections for mislabelled records      │
│  • User reviews and accepts/rejects per-row  [AI]       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 11 — Narrative Report Generation          [AI]     │
│  • LLM reads EDA stats + indicator distributions        │
│  • Generates written summary:                           │
│    - Completeness narrative                             │
│    - Malnutrition trend observations                    │
│    - Geographic hotspot commentary                      │
│    - Anomaly / outlier flags explained in plain text    │
└─────────────────────────────────────────────────────────┘
```

---

## 1C. Output — MyVASS

```
┌─────────────────────────────────────────────────────────┐
│  OUTPUTS — MyVASS                                       │
│                                                         │
│  [DATA] Cleaned Data                                    │
│    • POST /download/cleaned        → CSV or XLSX        │
│    • POST /download/cleaned-merged → CSV or XLSX        │
│    • GET  /clean/download-cached/{id}                   │
│                                                         │
│  [DATA] EDA Report (JSON)                               │
│    • POST /eda/run                                      │
│    • POST /eda/run-merged                               │
│    • Includes: z-scores, indicators, quality, charts    │
│                                                         │
│  [DATA] Data Quality Report (9-tab Excel)               │
│    • GET /clean/download-report/{cache_id}              │
│    • Tab 1: Executive Summary                           │
│    • Tab 2: Cleaning Rules Applied                      │
│    • Tab 3: Records Dropped (rule-by-rule)              │
│    • Tabs 4–9: Pivot tables per indicator × geo         │
│      (WAZ Negeri, WAZ Daerah, HAZ Negeri, HAZ Daerah,  │
│       BAZ Negeri, BAZ Daerah)                           │
│                                                         │
│  [DATA] Tableau-Ready Aggregated Table                  │
│    • POST /export/aggregated → CSV or XLSX              │
│    • Flat geo × age_group × indicator rows              │
│    • Includes sumber_indikator column (zscore/label)    │
│                                                         │
│  [AI]   Narrative Report                                │
│    • Natural language summary of findings               │
│    • Explainability panel (per-row explanations)        │
│                                                         │
│  [DATA] Cleaned Data Preview (paginated)                │
│    • POST /cleaned/preview                              │
└─────────────────────────────────────────────────────────┘
```

### MyVASS — Feature Summary Table

| Feature | Type | Description |
|---------|------|-------------|
| Multi-file merge + dedup | DATA | Merge N files, keep latest DOSE_DATE per IC |
| Schema auto-mapping | DATA | Rule-based column name matching |
| Schema mapping confirmation | AI | LLM validates ambiguous/drifted column names |
| Gender normalisation | DATA | Map variants → Male/Female |
| Date validation | DATA | DOB, measurement date logic checks |
| Age computation & filter | DATA | Age in days/months; drop >60 months |
| Measurement outlier filter | DATA | Biological plausibility bounds |
| BMI recalculation | DATA | Recomputed from weight/height |
| WHO 2006 Z-scores (WAZ/HAZ/BAZ) | DATA | Daily LMS table lookup |
| Z-score classification | DATA | 5-category status per indicator |
| Nutritional indicator flags | DATA | Binary flags per condition |
| IC/MyKid validation | DATA | Format check, dedup analysis |
| Geo enrichment | DATA | Kawasan (Sabah) / Bahagian (Sarawak) |
| Completeness scoring | DATA | Missing value analysis per column |
| Statistical outlier detection | DATA | IQR/z-method outlier flagging |
| BMI consistency check | DATA | Source BMI vs computed BMI mismatch |
| Spelling check on labels | DATA | Status label correction to valid set |
| Quality score | DATA | Overall data quality % |
| Pivot tables (WAZ/HAZ/BAZ) | DATA | Geo × age × indicator breakdowns |
| Tableau export | DATA | Flat aggregated rows for Tableau |
| ML correction suggestions | AI | Flag label mismatches, suggest fixes |
| Narrative report | AI | LLM-generated written findings |
| Explainability panel | AI | Per-row reasoning for flags |

---

---

# Dataset 2 — NCDC (TASKA)

> Longitudinal TASKA child records. Wide format with year-prefixed columns (2023/2024/2025/2026).
> Must be reshaped wide-to-long before analysis.

---

## 2A. Upload

```
┌─────────────────────────────────────────────────────────┐
│  UPLOAD — NCDC/TASKA                                    │
│                                                         │
│  Single file  ──►  POST /upload/preview                 │
│                        ↓                               │
│  • Auto-detect: year-prefixed columns → "ncdc"          │
│  • Column preview                            [DATA]     │
│  • Auto-suggest schema mapping               [DATA]     │
│  • AI schema mapping confirmation            [AI]       │
│  • Wide-to-long preview                                 │
│    POST /transform/myvass-wide-to-long       [DATA]     │
│    (explodes 2023/2024/2025/2026 year rows)             │
└─────────────────────────────────────────────────────────┘
```

---

## 2B. Process — NCDC Cleaning Pipeline

```
  Raw Data (wide format)
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 1 — Wide-to-Long Reshape                  [DATA]   │
│  • Detect year-prefixed columns:                        │
│    2023 Berat / 2024 Berat / 2025 Berat etc.            │
│  • For each child row × each year with data:            │
│    create one record with Year, Berat_kg, Tinggi_cm,    │
│    Tarikh_Pengukuran                                    │
│  • Only creates record if weight OR height is present   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 2 — Gender Standardisation                [DATA]   │
│  • Normalise variants → Male/Female                     │
│  • DROP invalid gender rows                             │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 3 — Income Filter                         [DATA]   │
│  • DROP rows where Pendapatan = 'X'                     │
│    (Rule 9: excluded income group)                      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 4 — Date Validation                       [DATA]   │
│  • Parse Tarikh_Lahir (DOB)                             │
│  • DROP rows where DOB is null                          │
│  • DROP rows where Tarikh_Pengukuran < Tarikh_Lahir     │
│    (Rule 4: measurement before birth)                   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 5 — Age Computation & Filter              [DATA]   │
│  • Age_Days = measurement date − DOB                    │
│  • Age_Months = Age_Days / 30.4375                      │
│  • DROP negative age or Age_Months ≥ 60 (Rule 3)        │
│  • Kategori_Umur: Bawah 2 Tahun / Bawah 5 Tahun        │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 6 — Measurement Outlier Filter            [DATA]   │
│  • Berat_kg: 0.5 – 35.0 kg                              │
│  • Tinggi_cm: 30.0 – 130.0 cm                           │
│  • DROP outside biological range (Rule 2)               │
│  • DROP both measurements null (Rule 6)                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 7 — BMI Recalculation                     [DATA]   │
│  • Drop source BMI column                               │
│  • BMI = weight / (height/100)²                         │
│  • DROP implausible BMI > 40 (Rule 5)                   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 8 — Duplicate MyKid Removal               [DATA]   │
│  • Sort by Tarikh_Pengukuran descending                 │
│  • DROP duplicate No. MyKid — keep most recent          │
│    (Rule 8: one record per child)                       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 9 — WHO Z-Score Computation               [DATA]   │
│  • WAZ / HAZ / BAZ via daily LMS tables (WHO 2006)      │
│  • BIV filter applied                                   │
│  • DROP rows with any null z-score (Rule 7)             │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 10 — Z-Score Classification & Indicators  [DATA]   │
│  (same classification as MyVASS)                        │
│  + Year-based breakdown (year_counts in stats)          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 11 — EDA Analysis                         [DATA]   │
│  • Completeness, outliers, quality score                │
│  • Categorical/numerical summaries                      │
│  • Geo enrichment                                       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 12 — ML Correction + Narrative          [DATA+AI]  │
│  • Source label vs z-score mismatch flags   [DATA]      │
│  • AI correction suggestions                [AI]        │
│  • LLM narrative report                     [AI]        │
└─────────────────────────────────────────────────────────┘
```

---

## 2C. Output — NCDC

```
┌─────────────────────────────────────────────────────────┐
│  OUTPUTS — NCDC                                         │
│                                                         │
│  [DATA] Cleaned Long-Format Data                        │
│    • CSV or XLSX (one row per child per year)           │
│                                                         │
│  [DATA] EDA Report (JSON)                               │
│    • Z-scores, indicators, quality, per-year counts     │
│                                                         │
│  [DATA] Data Quality Report (9-tab Excel)               │
│    • Same structure as MyVASS report                    │
│    • Additional: year_counts breakdown                  │
│                                                         │
│  [DATA] Tableau-Ready Aggregated Table                  │
│    • Geo × age_group × indicator × year                 │
│                                                         │
│  [AI]   Narrative Report                                │
│    • Longitudinal trend narrative (year-over-year)      │
│    • Explainability panel                               │
└─────────────────────────────────────────────────────────┘
```

### NCDC — Feature Summary Table

| Feature | Type | Description |
|---------|------|-------------|
| Wide-to-long reshape | DATA | Explode year-prefixed columns into rows |
| Schema auto-mapping | DATA | Year-aware column matching |
| Schema mapping confirmation | AI | LLM handles year-prefixed/drifted names |
| Gender normalisation | DATA | Map variants → Male/Female |
| Income filter (Pendapatan=X) | DATA | Exclude invalid income records |
| Null DOB drop | DATA | Remove records with no birth date |
| Date validation | DATA | Measurement before DOB → drop |
| Age computation & filter | DATA | Age in days/months; drop >60 months |
| Measurement outlier filter | DATA | Biological bounds |
| BMI recalculation | DATA | Recomputed from weight/height |
| Duplicate MyKid dedup | DATA | Keep most recent measurement per child |
| WHO 2006 Z-scores | DATA | WAZ/HAZ/BAZ with daily LMS lookup |
| Z-score classification | DATA | 5-category per indicator |
| Nutritional indicator flags | DATA | Binary flags per condition |
| Year-breakdown stats | DATA | Record count per measurement year |
| Geo enrichment | DATA | Kawasan/Bahagian mapping |
| Completeness + quality score | DATA | Per-column missing analysis |
| Pivot tables | DATA | Geo × age × indicator × year |
| ML correction suggestions | AI | Mislabelled status detection + fix |
| Narrative report | AI | LLM longitudinal trend summary |
| Explainability panel | AI | Per-row reasoning for anomalies |

---

---

# Dataset 3 — KPM

> Ministry of Education school-age children (6–8 years).
> **No WHO z-scores** — uses BMI thresholds for school age instead.

---

## 3A. Upload

```
┌─────────────────────────────────────────────────────────┐
│  UPLOAD — KPM                                           │
│                                                         │
│  Single file  ──►  POST /upload/preview                 │
│  or POST /clean/detect-type                             │
│                        ↓                               │
│  • Detect: ID_MURID / THN_TING / NAMA SEKOLAH → "kpm"  │
│  • Column preview                            [DATA]     │
│  • Auto-suggest schema mapping               [DATA]     │
│  • AI schema mapping confirmation            [AI]       │
│  • Pre-cleaning quality check                           │
│    POST /clean/quality-check                 [DATA]     │
└─────────────────────────────────────────────────────────┘
```

---

## 3B. Process — KPM Cleaning Pipeline

```
  Raw Data
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 1 — Gender Standardisation                [DATA]   │
│  • DROP rows where Jantina = 'RAGU' (Rule 3)            │
│  • Normalise remaining → Male/Female                    │
│  • DROP invalid gender rows                             │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 2 — Duplicate Student ID Removal          [DATA]   │
│  • DROP duplicate ID_MURID — keep first (Rule 2)        │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 3 — Date Validation                       [DATA]   │
│  • Parse Tarikh_Lahir, Tarikh_Pengukuran                │
│  • DROP rows where date is in the future (Rule 5)       │
│  • DROP rows where Tarikh_Pengukuran < Tarikh_Lahir     │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 4 — Age Computation & Filter              [DATA]   │
│  • Age_Years = Age_Days / 365.25                        │
│  • DROP rows where Age_Years < 5 or > 10 (Rule 4)       │
│    (KPM targets 6–8 years school children)              │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 5 — Measurement Outlier Filter            [DATA]   │
│  • Berat_kg valid range: 12.0 – 50.0 kg (school)        │
│  • Tinggi_cm valid range: 100.0 – 160.0 cm (school)     │
│  • DROP rows outside school-age range (Rules 6 & 7)     │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 6 — BMI Calculation & Classification      [DATA]   │
│  • BMI = weight / (height/100)²                         │
│  • School-age BMI categories (Rule 9):                  │
│    BMI < 13.5          → Kurus (Underweight)            │
│    13.5 ≤ BMI < 16.5   → Normal                         │
│    16.5 ≤ BMI < 18.5   → Berlebihan Berat Badan         │
│    BMI ≥ 18.5          → Obes                           │
│  • DROP rows with no BMI computable                     │
│                                                         │
│  ⚠ NOTE: No WHO z-scores for KPM                        │
│    (WHO LMS tables only cover 0–60 months)              │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 7 — Indicator Flags                       [DATA]   │
│  • Ind_Kurus         (BMI < 13.5)                       │
│  • Ind_Normal        (13.5 ≤ BMI < 16.5)               │
│  • Ind_Berlebihan    (16.5 ≤ BMI < 18.5)               │
│  • Ind_Obes          (BMI ≥ 18.5)                       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 8 — EDA Analysis                          [DATA]   │
│  • Completeness scoring                                 │
│  • Statistical outlier detection                        │
│  • Numerical/categorical summaries                      │
│  • Quality score                                        │
│  • Geo enrichment (Negeri, Daerah)                      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 9 — Narrative Report                      [AI]     │
│  • LLM summarises BMI distribution findings             │
│  • School-age obesity/underweight commentary            │
│  • Geographic patterns narrative                        │
└─────────────────────────────────────────────────────────┘
```

---

## 3C. Output — KPM

```
┌─────────────────────────────────────────────────────────┐
│  OUTPUTS — KPM                                          │
│                                                         │
│  [DATA] Cleaned Data                                    │
│    • POST /clean/download → CSV or XLSX                 │
│    • Sheets: Cleaned Data + Cleaning Stats              │
│                                                         │
│  [DATA] Quality Check Report                            │
│    • POST /clean/quality-check                          │
│    • Column-level: null%, unique count, min/max/mean    │
│    • Overall completeness %                             │
│                                                         │
│  [DATA] Data Quality Report (9-tab Excel)               │
│    • GET /clean/download-report/{cache_id}              │
│    • Tabs: Executive Summary, Cleaning Rules,           │
│      Records Dropped, BMI Negeri, BMI Daerah            │
│                                                         │
│  [AI]   Narrative Report                                │
│    • School-age BMI distribution summary                │
│    • Explainability panel                               │
└─────────────────────────────────────────────────────────┘
```

### KPM — Feature Summary Table

| Feature | Type | Description |
|---------|------|-------------|
| Auto-detect (ID_MURID/THN_TING) | DATA | Column pattern → KPM classification |
| Schema auto-mapping | DATA | Rule-based matching |
| Schema mapping confirmation | AI | LLM for ambiguous column names |
| Gender: drop 'RAGU' | DATA | School-specific rule |
| Gender normalisation | DATA | Map variants → Male/Female |
| Duplicate student ID removal | DATA | First-occurrence kept |
| Date validation (no future) | DATA | School-specific: also no future dates |
| Age filter (5–10 years) | DATA | School-age range validation |
| School-age measurement bounds | DATA | Different bounds from infant data |
| BMI calculation | DATA | Same formula, different categories |
| School-age BMI classification | DATA | Kurus/Normal/Berlebihan/Obes |
| Indicator flags (BMI-based) | DATA | No z-scores — BMI threshold flags |
| Completeness + quality score | DATA | Per-column missing analysis |
| Geo enrichment | DATA | Negeri, Daerah, Sekolah |
| Narrative report | AI | LLM school-age BMI summary |
| Explainability panel | AI | Per-row reasoning |

---

---

# Dataset 4 — KKM (Kementerian Kesihatan Malaysia)

> Ministry of Health school health data — weight & height for **7-year-olds** specifically.
> Covers **2024 and 2025** datasets.
> **Standalone desktop script** (`clean_kkm_data.py`) — NOT integrated into the FastAPI backend.
> Behaviour differs by year: 2024 = **flag-and-keep** mode; 2025 = **drop-invalid** mode.

---

## 4A. Upload

```
┌─────────────────────────────────────────────────────────┐
│  UPLOAD — KKM                                           │
│                                                         │
│  Desktop script — Tkinter file-picker dialog            │
│  (No API endpoint — standalone execution only)          │
│                                                         │
│  User selects:                                          │
│  • Which year(s): 2024 / 2025 / Both          [DATA]    │
│  • Input XLSX file(s) per year                          │
│  • Output folder for reports                            │
│                                                         │
│  Auto-detect sheet name:                      [DATA]    │
│  • Matches sheet containing year digit                  │
│  • Validates required columns present:                  │
│    NEGERI, JANTINA, ID_MURID, BERAT (KG), TINGGI (CM)  │
│  • Falls back to user sheet-picker if ambiguous         │
│                                                         │
│  Column rename to clean snake_case IDs        [DATA]    │
│  Text normalisation (UPPER + STRIP on all text)[DATA]   │
└─────────────────────────────────────────────────────────┘
```

**Source columns:**
`TAHUN PERSEKOLAHAN · NEGERI · DAERAH · NAMA SEKOLAH · LOKASI (BANDAR/LUAR BANDAR) · JENIS SEKOLAH · THN_TING · JANTINA · ID_MURID · TARIKH LAHIR · TARIKH PENGUKURAN BERAT/TINGGI · BERAT (kg) · TINGGI (cm)`

---

## 4B. Process — KKM Cleaning Pipeline

```
  Raw Data (per year)
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 1 — Column Normalisation                  [DATA]   │
│  • Strip whitespace + newlines from all column names    │
│  • Rename to snake_case (Berat_kg_Raw, etc.)            │
│  • UPPER + STRIP on: Negeri, Daerah, Jantina,           │
│    Jenis_Sekolah, Thn_Ting                              │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 2 — Negeri Validation (BR-01)             [DATA]   │
│  • Validate Negeri against 16-state whitelist           │
│  • Flag invalid state names (Negeri_Valid = False)      │
│  • Does NOT drop — flags only                           │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 3 — Lokasi Mapping                        [DATA]   │
│  • BANDAR → Urban                                       │
│  • LUAR BANDAR → Rural                                  │
│  • Unknown otherwise                                    │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 4 — Year Level Mapping                    [DATA]   │
│  • TAHUN SATU → Year 1                                  │
│  • TAHUN DUA → Year 2 · TAHUN TIGA → Year 3            │
│  • KELAS KHAS RENDAH → Special Ed                       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 5 — Gender Mapping (BR-03)                [DATA]   │
│  • LELAKI → Male · PEREMPUAN → Female                   │
│  • RAGU / other → Unknown (count logged)                │
│  • Unknown gender = flagged, NOT dropped                │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 6 — Date Parsing & Validation (BR-05)     [DATA]   │
│  • Parse Tarikh_Lahir (DOB)                             │
│  • Parse Tarikh_Pengukuran (measurement date)           │
│  • Flag as invalid if:                                  │
│    - Unix epoch (1970-01-01) — system error             │
│    - Before 2020-01-01 — implausible                    │
│    - Future date                                        │
│                                                         │
│  ⚠ YEAR-SPECIFIC BEHAVIOUR:                             │
│    2025 → DROP rows with invalid dates                  │
│    2024 → Set invalid dates to NULL (keep rows)         │
│                                                         │
│  ⚠ SPECIAL 2024 RULE:                                   │
│    ALL measurement dates set to 31/12/2024              │
│    (2024 dataset has no measurement dates —             │
│     31/12/2024 used as proxy for age calculation)       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 7 — Age Computation & Validation (BR-04)  [DATA]   │
│  • Age_Days = Tarikh_Pengukuran − Tarikh_Lahir          │
│  • Age_At_Measurement = Age_Days / 365.25               │
│  • Valid age: 6.0 – 8.0 years                           │
│  • Flag invalid age (Is_Valid_Age = False)              │
│  • Does NOT drop on age — flags only                    │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 8 — Weight Cleaning (BR-06)               [DATA]   │
│  • Valid range: 12.0 – 50.0 kg                          │
│                                                         │
│  ⚠ YEAR-SPECIFIC BEHAVIOUR:                             │
│    2025 → DROP rows outside range                       │
│    2024 → Set to NULL (keep rows, flag)                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 9 — Height Cleaning (BR-07)               [DATA]   │
│  • Valid range: 100.0 – 160.0 cm                        │
│                                                         │
│  ⚠ YEAR-SPECIFIC BEHAVIOUR:                             │
│    2025 → DROP rows outside range                       │
│    2024 → Set to NULL (keep rows, flag)                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 10 — BMI & Derived Categories (BR-13/14)  [DATA]   │
│  • BMI = weight / (height/100)²                         │
│  • School-age thresholds (WHO 7-yr, 2007 reference):    │
│    BMI < 13.5   → Underweight                           │
│    13.5 – 16.5  → Normal                                │
│    16.5 – 18.5  → Overweight                            │
│    ≥ 18.5       → Obese                                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 11 — Height Category (BR-15)              [DATA]   │
│  • Proxy stunting thresholds for 7-year-olds:           │
│    Height < 112.0 cm → Stunted                          │
│    112.0 – 132.0 cm  → Normal                           │
│    Height > 132.0 cm → Tall                             │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 12 — Completeness & Duplicate Flags       [DATA]   │
│  • Has_Complete_Measurements (weight AND height)        │
│  • Is_Valid_Age (6–8 years)                             │
│  • Is_Valid_Measurement_Date                            │
│  • Is_Duplicate_ID (BR-02: duplicate ID_MURID flagged,  │
│    NOT dropped — flagged for investigation)             │
│  • DOB encoding check (BR-07): validate DOB encoded     │
│    in ID_MURID prefix (format MDDMMYYYY)                │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 13 — Composite Data_Quality_Flag          [DATA]   │
│  Per-row composite flag combining all issues:           │
│  • "Valid" = passes all rules                           │
│  • Otherwise: semicolon-joined list of issues           │
│    e.g. "Missing Measurements; Invalid Age"             │
│  Issues flagged: Missing Measurements / Invalid Age /   │
│    Invalid Date / Unknown Gender / Duplicate ID         │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 14 — Multi-year Combination               [DATA]   │
│  • Combine 2024 + 2025 cleaned frames (if both run)     │
│  • Keyed by Tahun_Persekolahan column                   │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STEP 15 — Narrative Report                     [AI]     │
│  • LLM summarises BMI + height distribution findings    │
│  • Year-over-year comparison narrative                  │
│  • Geographic hotspot commentary                        │
│  • Flagged records explanation                          │
└─────────────────────────────────────────────────────────┘
```

---

## 4C. Output — KKM

```
┌─────────────────────────────────────────────────────────┐
│  OUTPUTS — KKM                                          │
│                                                         │
│  [DATA] Cleaned Data (CSV, one file per year)           │
│    • KKM_BeratTinggi_Cleaned_2024.csv                   │
│    • KKM_BeratTinggi_Cleaned_2025.csv                   │
│    • Encoding: UTF-8 with BOM (Excel-friendly)          │
│    • Dates formatted YYYY-MM-DD                         │
│    • Booleans as strings ("True"/"False")               │
│                                                         │
│  [DATA] Quality Report Excel (7-tab)                    │
│    • KKM_BeratTinggi_QualityReport_2024_2025.xlsx       │
│    • Tab 1: Executive Summary                           │
│      - Raw count, rows after clean, valid/flagged       │
│      - Per-year and combined columns                    │
│      - Data Quality Rate %                              │
│      - All cleaning rule counts                         │
│    • Tab 2: Cleaning Rules Applied                      │
│      - Rule ID, column, category, description, action   │
│      - 2024 vs 2025 affected counts side-by-side        │
│    • Tab 3: BMI Distribution                            │
│      - Underweight/Normal/Overweight/Obese per year     │
│      - Combined total                                   │
│    • Tab 4: By State (Negeri)                           │
│      - BMI category counts per state                    │
│      - % with valid BMI per state                       │
│    • Tab 5: By Gender                                   │
│      - Male/Female/Unknown BMI breakdown                │
│    • Tab 6: Height Analysis (Stunting)                  │
│      - Stunted/Normal/Tall per year + combined          │
│    • Tab 7: Flagged Records (sample)                    │
│      - Up to 500 rows per issue type                    │
│      - Grouped by Data_Quality_Flag value               │
│                                                         │
│  [AI]   Narrative Report                                │
│    • LLM-generated BMI + stunting summary               │
│    • Year-over-year comparison commentary               │
│    • Explainability panel                               │
└─────────────────────────────────────────────────────────┘
```

### KKM — Feature Summary Table

| Feature | Type | Description |
|---------|------|-------------|
| Tkinter file-picker UI | DATA | Desktop dialog — not API-based |
| Year-mode selection (2024/2025/both) | DATA | User selects years to process |
| Sheet auto-detection | DATA | Year digit or required column match |
| Column normalisation | DATA | UPPER/STRIP + snake_case rename |
| Negeri validation | DATA | 16-state whitelist check (flag only) |
| Lokasi mapping | DATA | BANDAR→Urban / LUAR BANDAR→Rural |
| Year level mapping | DATA | TAHUN SATU→Year 1, Kelas Khas→Special Ed |
| Gender mapping (RAGU→Unknown) | DATA | Unknown flagged, not dropped |
| Date validation (epoch/pre-2020/future) | DATA | 2025: drop; 2024: nullify |
| 2024 proxy date (31/12/2024) | DATA | All 2024 measurement dates standardised |
| Age computation (in years) | DATA | Age_Days / 365.25 |
| Age validation (6–8 years) | DATA | Flag only, not drop |
| Weight range filter (12–50 kg) | DATA | 2025: drop; 2024: nullify |
| Height range filter (100–160 cm) | DATA | 2025: drop; 2024: nullify |
| BMI calculation | DATA | From cleaned weight/height |
| BMI classification (WHO 7-yr 2007) | DATA | Underweight/Normal/Overweight/Obese |
| Height classification (stunting proxy) | DATA | Stunted <112cm / Normal / Tall >132cm |
| Completeness flags | DATA | Has_Complete_Measurements etc. |
| Duplicate ID_MURID flag | DATA | Flagged for investigation, not dropped |
| DOB encoding check in ID_MURID | DATA | Extracts + cross-validates DOB in ID prefix |
| Composite Data_Quality_Flag | DATA | Per-row semicolon-joined issue list |
| Multi-year combine | DATA | 2024 + 2025 frames merged for reports |
| 7-tab Excel quality report | DATA | Summary, rules, BMI, state, gender, height, flagged |
| Narrative report | AI | LLM school health + stunting commentary |
| Explainability panel | AI | Per-row reasoning |

---

---

# Cross-Dataset Feature Matrix

| Feature | MyVASS | NCDC | KPM | KKM | Type |
|---------|:------:|:----:|:---:|:---:|------|
| **Integration** | API | API | API | Standalone script | — |
| Multi-file merge | ✅ | ❌ | ❌ | ❌ | DATA |
| Wide-to-long reshape | ❌ | ✅ | ❌ | ❌ | DATA |
| Schema auto-mapping | ✅ | ✅ | ✅ | ❌ | DATA |
| AI schema mapping (LLM) | ✅ | ✅ | ✅ | ❌ | AI |
| Gender normalisation | ✅ | ✅ | ✅ | ✅ | DATA |
| Gender: RAGU → Unknown (flag) | ❌ | ❌ | drop | flag | DATA |
| Income filter (Pendapatan X) | ❌ | ✅ | ❌ | ❌ | DATA |
| Null DOB drop | ❌ | ✅ | ❌ | ❌ | DATA |
| Date before DOB drop | ✅ | ✅ | ✅ | ✅ | DATA |
| Epoch / pre-threshold date filter | ❌ | ❌ | ❌ | ✅ | DATA |
| Future date drop | ❌ | ❌ | ✅ | ✅ | DATA |
| 2024 proxy date (31/12/2024) | ❌ | ❌ | ❌ | ✅ | DATA |
| Age filter (< 60 months / under 5) | ✅ | ✅ | ❌ | ❌ | DATA |
| Age filter (5–10 years) | ❌ | ❌ | ✅ | ❌ | DATA |
| Age filter (6–8 years, flag only) | ❌ | ❌ | ❌ | ✅ | DATA |
| Infant measurement bounds | ✅ | ✅ | ❌ | ❌ | DATA |
| School measurement bounds | ❌ | ❌ | ✅ | ✅ | DATA |
| Year-mode (2024 flag / 2025 drop) | ❌ | ❌ | ❌ | ✅ | DATA |
| BMI > 40 drop | ✅ | ✅ | ❌ | ❌ | DATA |
| Duplicate MyKid dedup (drop) | ❌ | ✅ | ❌ | ❌ | DATA |
| Duplicate student ID (drop) | ❌ | ❌ | ✅ | ❌ | DATA |
| Duplicate ID_MURID (flag only) | ❌ | ❌ | ❌ | ✅ | DATA |
| WHO Z-scores (WAZ/HAZ/BAZ) | ✅ | ✅ | ❌ | ❌ | DATA |
| Z-score classification | ✅ | ✅ | ❌ | ❌ | DATA |
| BMI-threshold classification | ❌ | ❌ | ✅ | ✅ | DATA |
| Height-for-age (stunting proxy) | ❌ | ❌ | ❌ | ✅ | DATA |
| Nutritional indicator flags | ✅ | ✅ | ✅ | ✅ | DATA |
| Composite quality flag per row | ❌ | ❌ | ❌ | ✅ | DATA |
| DOB encoding check in ID | ❌ | ❌ | ❌ | ✅ | DATA |
| Negeri whitelist validation | ❌ | ❌ | ❌ | ✅ | DATA |
| Lokasi (Urban/Rural) mapping | ❌ | ❌ | ❌ | ✅ | DATA |
| Year level mapping | ❌ | ❌ | ❌ | ✅ | DATA |
| IC/MyKid validation | ✅ | ✅ | ❌ | ❌ | DATA |
| Geo enrichment (Kawasan/Bahagian) | ✅ | ✅ | ❌ | ❌ | DATA |
| Geo by state + district | ✅ | ✅ | ✅ | ✅ | DATA |
| Year-breakdown stats | ❌ | ✅ | ❌ | ✅ | DATA |
| Completeness scoring | ✅ | ✅ | ✅ | ✅ | DATA |
| Quality score / report | ✅ | ✅ | ✅ | ✅ | DATA |
| Excel quality report tabs | 9 tabs | 9 tabs | 9 tabs | 7 tabs | DATA |
| Report: BMI by state/gender | ❌ | ❌ | ❌ | ✅ | DATA |
| Report: Height/stunting analysis | ❌ | ❌ | ❌ | ✅ | DATA |
| Report: Flagged records sheet | ❌ | ❌ | ❌ | ✅ | DATA |
| Tableau aggregated export | ✅ | ✅ | ❌ | ❌ | DATA |
| ML correction suggestions | ✅ | ✅ | ❌ | ❌ | AI |
| Narrative report (LLM) | ✅ | ✅ | ✅ | ✅ | AI |
| Explainability panel | ✅ | ✅ | ✅ | ✅ | AI |

---

---

# API Endpoint Reference

## Upload & Preview

| Endpoint | Method | Dataset | Description |
|----------|--------|---------|-------------|
| `/upload/preview` | POST | All | Single-file upload + preview + auto-detect |
| `/upload/merge-preview` | POST | MyVASS | Multi-file merge preview |
| `/mapping/validate` | POST | All | Validate column mapping |
| `/transform/myvass-wide-to-long` | POST | NCDC | Preview wide-to-long reshape |
| `/clean/detect-type` | POST | All | Auto-detect data type from columns |
| `/clean/quality-check` | POST | All | Pre-cleaning quality profile |
| `/clean/quality-check-multi` | POST | MyVASS | Multi-file pre-cleaning quality |

## EDA Pipeline

| Endpoint | Method | Dataset | Description |
|----------|--------|---------|-------------|
| `/eda/run` | POST | All | Full EDA pipeline (single file) |
| `/eda/run-merged` | POST | MyVASS | Full EDA on merged multi-file |
| `/clean/run` | POST | All | Cleaning + cache → returns cache_id |
| `/clean/run-multi` | POST | MyVASS | Multi-file merge + clean |
| `/cleaned/preview` | POST | All | Paginated cleaned data preview |

## Download & Export

| Endpoint | Method | Dataset | Description |
|----------|--------|---------|-------------|
| `/download/cleaned` | POST | All | Download cleaned CSV/XLSX |
| `/download/cleaned-merged` | POST | MyVASS | Download merged+cleaned |
| `/export/aggregated` | POST | MyVASS/NCDC | Tableau-ready flat table |
| `/clean/download` | POST | All | Download cleaned (re-run) |
| `/clean/download-multi` | POST | MyVASS | Merge + clean + download |
| `/clean/download-cached/{id}` | GET | All | Download from cache (no re-upload) |
| `/clean/download-report/{id}` | GET | All | 9-tab Data Quality Report Excel |

---

*Generated: 2026-05-11 | Source: data-cleaning-tool-new backend audit*
