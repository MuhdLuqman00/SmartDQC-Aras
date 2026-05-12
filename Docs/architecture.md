# SmartDQC — Architecture Reference

> **Status:** Day 1 complete. Frontend container is Day 6 scope.
> Last updated: 2026-05-12

---

## 1. System Components

| Component | Technology | Status | Notes |
|-----------|-----------|--------|-------|
| Backend API | Python 3.12, FastAPI | ✅ Running | Dual namespace: `/eda/*` + `/clean/*` |
| Database | DuckDB 1.x | ✅ Running | File-backed; auto-created at `SMARTDQC_DB_PATH` |
| SLM Model Server | Ollama | ✅ Running | GPU-served; model pulled on first start |
| Frontend | React (from scratch) | 🔜 Day 6 | KKM branding, light/dark mode, chatbot |

---

## 2. Docker Services

```yaml
# docker-compose.yml services
api:         # FastAPI backend — port 8000
ollama:      # Ollama SLM server — port 11434 (GPU)
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
  export/
    cleaned.py          # CSV/XLSX export
    tableau.py          # Tableau-ready flat aggregated export
  utils/
    ic_validator.py     # IC/NRIC format check and dedup
    age.py              # Age computation (days, months, years)
    geo.py              # Geo enrichment (Kawasan Sabah, Bahagian Sarawak)
    normaliser.py       # Text normalisation helpers
```

---

## 5. Persistence Layer

Three tables live after Day 1. Three more planned for Day 5.

### Current Tables (Day 1)

```sql
CREATE TABLE IF NOT EXISTS datasets (
    id VARCHAR PRIMARY KEY,
    filename VARCHAR NOT NULL,
    source_type VARCHAR,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    row_count INTEGER,
    column_count INTEGER,
    metadata VARCHAR
);

CREATE TABLE IF NOT EXISTS sessions (
    id VARCHAR PRIMARY KEY,
    dataset_id VARCHAR REFERENCES datasets(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    config VARCHAR,
    status VARCHAR DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR REFERENCES sessions(id),
    result_type VARCHAR NOT NULL,
    result_data VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Planned Tables (Day 5)

| Table | Purpose |
|-------|---------|
| `zscore_archive` | Historical Z-scores per child per period — feeds Features #11 and #16 |
| `entity_linkage` | IC/NRIC-keyed index across sources — feeds Feature #14 |
| `audit_log` | Append-only change log — government traceability requirement |

---

## 6. API Surface

Two namespaces. Full per-dataset detail in [`Docs/SmartDQC_Tool_Flow.md`](SmartDQC_Tool_Flow.md).

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

---

## 7. SLM Architecture

- **Served via:** Ollama Docker service (port 11434)
- **Hardware target:** NVIDIA RTX 5060, 8GB VRAM
- **Model constraint:** < 4B parameters (candidates: Qwen2.5-3B, Phi-3.5-mini, Mistral-3B)
- **Backend integration:** HTTP to `http://ollama:11434` (Docker internal network)
- **Day 1 gate:** If model exceeds VRAM budget on SE's laptop, swap before Day 2

---

## 8. In-Memory Cache

`backend/main.py` holds a UUID-keyed LRU cache (`_cleaned_cache`, max 10 entries). Enables `/clean/download-cached/{id}` without re-upload. Cache is process-local — lost on container restart.

---

*Source: `Docs/SmartDQC_Master.md` §5 + Day 1 implementation*
