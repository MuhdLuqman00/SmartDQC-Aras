# SmartDQC — Architecture Reference

> **Status:** Day 4 complete. Frontend container is Day 6 scope.
> Last updated: 2026-05-13

---

## 1. System Components

| Component | Technology | Status | Notes |
|-----------|-----------|--------|-------|
| Backend API | Python 3.12, FastAPI | ✅ Running | Namespaces: `/eda/*`, `/clean/*`, `/join/*`, `/ai/*`, `/ml/*`, `/report/*`, `/risk/*`, `/kpi/*` |
| Database | PostgreSQL 16 + SQLAlchemy + Alembic | ✅ Running | Managed via Alembic migrations; pool_size=10 |
| SLM Model Server | Ollama | ✅ Running | GPU-served on port 11435 (DGX); model pulled on first start |
| Frontend | React (from scratch) | 🔜 Day 6 | KKM branding, light/dark mode, chatbot |

---

## 2. Docker Services

```yaml
# docker-compose.yml services
api:         # FastAPI backend — port 8000
db:          # PostgreSQL 16 — port 5432 (internal); tuned for analytics workloads
ollama:      # Ollama SLM server — port 11435 (DGX deployment)
ollama-init: # One-shot model pull on first startup
```

Frontend container is added on Day 6.

---

## 3. Repo Structure

```
SmartDQC/
├── backend/          # FastAPI app (all source code)
├── frontend/         # React app — Day 6 scope
├── tests/
│   ├── backend/      # Unit + integration tests
│   └── e2e/          # Playwright end-to-end tests
├── scripts/          # Utility scripts
├── data/             # Runtime data (gitignored)
│   └── zscore/       # WHO 2006 LMS Excel files (manual placement)
├── Docs/             # Reference documentation
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

---

## 4. Backend Module Map

```
backend/
  main.py               # FastAPI app — all route definitions (~30 endpoints)
  config.py             # STANDARD_SCHEMA, AUTO_MAPPING_HINTS, detection rules, birth weight categories
  db/
    models.py           # DuckDB table DDL (CREATE TABLE statements)
    init_db.py          # init_db() — idempotent table creation on startup
  cleaning/             # Source-specific rule-based cleaning pipelines
    kkm.py              # KKM school health (7-yr, 2024/2025 year-mode logic)
    kpm.py              # KPM school-age (6-8 yr, BMI thresholds)
    myvass.py           # MyVASS / NCDC infant (0-60 months, WHO z-scores)
    ncdc.py             # NCDC TASKA (wide-to-long reshape + MyVASS cleaning)
  eda/                  # Analysis pipeline
    runner.py           # Orchestrates full EDA run
    cleaning.py         # detect_data_type, shared cleaning helpers
    who_zscore.py       # Monthly LMS lookup (WHO 2006)
    who_zscore_daily.py # Daily LMS lookup (higher precision)
    indicators.py       # Nutritional indicator flags (WAZ/HAZ/BAZ)
    quality.py          # Quality scoring
    kkm_quality_rules.py
    missing.py
    completeness.py
    outliers.py
    numerical.py
    categorical.py
    bmi.py
    charts.py
    kpi.py              # RAG KPI benchmarking vs NPAN / 12th Malaysia Plan targets (#16)
  ml/
    corrections.py      # IsolationForest anomaly detection + 3×IQR correction suggestions (#12)
    risk_score.py       # Composite risk score (0-100) per child + district aggregation (#11)
  export/
    cleaned.py          # CSV/XLSX export
    tableau.py          # Tableau-ready flat aggregated export
    report.py           # PPTX (python-pptx) and PDF (reportlab) report builders (#15)
  utils/
    ic_validator.py     # IC/NRIC format check and dedup
    age.py              # Age computation (days, months, years)
    geo.py              # Geo enrichment (Kawasan Sabah, Bahagian Sarawak)
    normaliser.py       # Text normalisation helpers
```

---

## 5. Persistence Layer

Three tables live. Three more planned for Day 5. Alembic manages all schema changes from Day 2 onward.

### Migration History

| Migration | File | Changes |
|-----------|------|---------|
| 0001 | `alembic/versions/0001_initial.py` | Initial tables: `datasets`, `sessions`, `analysis_results` |
| 0002 | `alembic/versions/0002_indexes_and_jsonb.py` | FK indexes on `sessions.dataset_id`, `analysis_results.session_id`; `result_data TEXT` → `result_json JSONB` |

Migrations run automatically on container startup via `alembic upgrade head`.

### Current Tables (Day 2)

```sql
-- datasets: registry of uploaded files
CREATE TABLE datasets (
    id          VARCHAR PRIMARY KEY,
    name        VARCHAR NOT NULL,
    filename    VARCHAR NOT NULL,
    source_type VARCHAR,           -- 'myvass' | 'klinik' | 'ncdc' | 'kpm'
    row_count   INTEGER,
    created_at  TIMESTAMP NOT NULL
);

-- sessions: one analysis session per dataset
CREATE TABLE sessions (
    id         VARCHAR PRIMARY KEY,
    dataset_id VARCHAR NOT NULL REFERENCES datasets(id),
    notes      VARCHAR,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
CREATE INDEX idx_sessions_dataset_id ON sessions(dataset_id);

-- analysis_results: EDA narrative + NLQ outputs stored as JSONB
CREATE TABLE analysis_results (
    id          VARCHAR PRIMARY KEY,
    session_id  VARCHAR NOT NULL REFERENCES sessions(id),
    result_type VARCHAR NOT NULL,   -- 'narrative' | 'nlq'
    result_json JSONB   NOT NULL,
    created_at  TIMESTAMP NOT NULL
);
CREATE INDEX idx_analysis_results_session_id ON analysis_results(session_id);
```

### PostgreSQL Tuning (docker-compose.yml)

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `shared_buffers` | 512MB | Buffer pool for frequently accessed pages |
| `work_mem` | 64MB | Per-sort/hash memory |
| `maintenance_work_mem` | 256MB | VACUUM / index build memory |
| `effective_cache_size` | 2GB | Query planner cache hint |

### Planned Tables (Day 5)

| Table | Purpose |
|-------|---------|
| `zscore_archive` | Historical Z-scores per child per period — feeds Features #11 and #16 |
| `entity_linkage` | IC/NRIC-keyed index across sources — feeds Feature #14 |
| `audit_log` | Append-only change log — government traceability requirement |

---

## 6. API Surface

Four namespaces. Full per-dataset detail in [`Docs/SmartDQC_Tool_Flow.md`](SmartDQC_Tool_Flow.md).

### EDA Namespace

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/upload/preview` | POST | Single-file upload + source detection + column preview |
| `/upload/merge-preview` | POST | MyVASS multi-file merge preview |
| `/mapping/validate` | POST | Column mapping validation |
| `/transform/myvass-wide-to-long` | POST | NCDC wide-to-long reshape preview |
| `/eda/run` | POST | Full EDA pipeline (single file) |
| `/eda/run-merged` | POST | EDA on merged MyVASS multi-file |
| `/cleaned/preview` | POST | Paginated cleaned data preview |
| `/download/cleaned` | POST | Download cleaned CSV/XLSX |
| `/download/cleaned-merged` | POST | Download merged + cleaned MyVASS |
| `/export/aggregated` | POST | Tableau-ready flat table |

### Clean Namespace

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/clean/detect-type` | POST | Auto-detect source type from columns |
| `/clean/quality-check` | POST | Pre-cleaning column quality profile |
| `/clean/quality-check-multi` | POST | Multi-file pre-cleaning quality |
| `/clean/run` | POST | Cleaning pipeline + cache, returns `cache_id` |
| `/clean/run-multi` | POST | Multi-file merge + clean |
| `/clean/download` | POST | Download cleaned (re-run) |
| `/clean/download-multi` | POST | Merge + clean + download |
| `/clean/download-cached/{id}` | GET | Download from UUID cache (no re-upload) |
| `/clean/download-report/{id}` | GET | 9-tab Data Quality Report Excel |

### Join Namespace

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/join/preview` | POST | Preview join of two datasets (first 50 rows + shape + stats) |
| `/join/run` | POST | Execute full join, cache result, return `cache_id` |

**Inputs:** each side is either a raw file upload (`file_left` / `file_right`) or a `cache_id` from a prior `/clean/run`.

**Join types** (`join_type` query param):

| Value | Behaviour |
|-------|-----------|
| `inner` | Rows where key exists in both datasets |
| `left` | All left rows; NaN where no right match |
| `right` | All right rows; NaN where no left match |
| `outer` | All rows from both; NaN on unmatched sides |
| `union` | Vertical stack; optionally deduplicated (`dedup=true`) |

**Downstream:** `cache_id` from `/join/run` works directly with `/clean/download-cached/{id}` for CSV/XLSX download.

### AI Namespace

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ai/narrative` | POST | Generate bilingual EDA narrative via Ollama SLM |
| `/ai/nlq` | POST | Natural language query over cleaned dataset (two-step: code gen → bilingual answer) |

### ML Namespace

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ml/suggest` | POST | Flag anomalous rows (IsolationForest) + suggest 3×IQR corrections |

**Input:** `cache_id` query param (UUID from `/clean/run` or `/join/run`)

### Report Namespace

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/report/pptx` | POST | Generate 4-slide PPTX report — quality metrics + AI narrative |
| `/report/pdf` | POST | Generate PDF report — quality metrics + AI narrative |

**Input:** JSON body with `cache_id`, `eda_result` (from `/eda/run`), `narrative` (from `/ai/narrative`)
**Note:** No new LLM call — narrative is passed in by the caller, reusing the Day 2 `/ai/narrative` output.

### Risk Namespace

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/risk/score` | POST | Per-child risk score (0-100) + Low/Medium/High tier + district aggregation |

**Input:** `cache_id` query param
**Risk tiers:** Low 0–20 · Medium 21–50 · High 51–100

### KPI Namespace

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/kpi/dashboard` | POST | RAG traffic-light status vs Malaysian national targets |

**Input:** `cache_id` query param
**Targets (NPAN / 12th Malaysia Plan):** stunting <15% · wasting <5% · underweight <12% · overweight <10%
**RAG:** Green = at/below target · Amber = actual ≤ target × 1.20 · Red = above that ceiling

---

## 7. SLM Architecture

- **Served via:** Ollama Docker service (port 11435 on DGX)
- **Hardware target:** DGX server with NVIDIA GPU
- **Model constraint:** < 4B parameters
- **Backend integration:** HTTP to `http://ollama:11435` (Docker internal network)
- **Narrative flow:** `/ai/narrative` → Ollama → bilingual Malay/English summary stored in `analysis_results` (JSONB)
- **NLQ flow:** `/ai/nlq` → step 1: generate pandas code → step 2: execute on `_cleaned_cache` → step 3: bilingual answer

---

## 8. In-Memory Cache

`backend/main.py` holds a UUID-keyed FIFO cache (`_cleaned_cache`, max 10 entries). Used by:
- `/clean/run` and `/clean/run-multi` — store cleaned DataFrames after the cleaning pipeline
- `/join/run` — store joined DataFrames after a join operation
- `/clean/download-cached/{id}` — retrieve for download (no re-upload)
- `/clean/download-report/{id}` — retrieve for 9-tab Excel quality report

Cache is process-local — lost on container restart. 10-entry FIFO: oldest entry evicted when full.

---

*Source: `Docs/SmartDQC_Master.md` §5 + Day 1–2 implementation*
