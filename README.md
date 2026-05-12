# SmartDQC

Local-deployed data quality and cleaning platform for KKM health nutrition data.
Runs fully on-premise — no internet required after initial setup.

## Quick Start

### Prerequisites
- Docker Desktop with GPU support (NVIDIA, RTX 5060)
- WHO 2006 z-score Excel files (6 files) placed in `data/zscore/`

### Setup

```bash
# 1. Copy environment config
cp .env.example .env

# 2. Place WHO z-score Excel files in data/zscore/
#    Required files:
#      wfa-boys-zscore-expanded-tables.xlsx
#      wfa-girls-zscore-expanded-tables.xlsx
#      lhfa-boys-zscore-expanded-tables.xlsx
#      lhfa-girls-zscore-expanded-tables.xlsx
#      bfa-boys-zscore-expanded-tables.xlsx
#      bfa-girls-zscore-expanded-tables.xlsx

# 3. Start all services
docker compose up --build

# 4. Verify
curl http://localhost:8000/health
curl http://localhost:11434/api/tags
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| api | 8000 | FastAPI backend (data cleaning, EDA, AI features) |
| ollama | 11434 | Local SLM runtime (GPU) |
| ollama-init | — | One-shot model pull on first startup |

## Data Sources Supported

- **MyVASS** — Clinic infant nutrition (0-5 years)
- **NCDC (TASKA)** — Under-5 program, multi-year wide format
- **KPM** — School-age (Tahun Satu, 7-year-olds)
- **KKM** — School health weight/height (2024/2025)
- **Other** — Generic CSV/XLSX with schema inference

## Architecture

```
backend/
  config.py         # STANDARD_SCHEMA, detection, auto-mapping
  main.py           # FastAPI app (30+ endpoints)
  db/               # SQLite persistence (datasets, sessions, results)
  cleaning/         # Source-specific cleaning (ncdc, kpm, myvass, kkm)
  eda/              # Analysis pipeline (who_zscore, indicators, quality, ...)
  export/           # CSV/XLSX/Tableau export
  utils/            # IC validator, age, geo, normaliser
data/
  zscore/           # WHO 2006 LMS tables (required)
  smartdqc.db       # SQLite DB (auto-created on first run)
```
