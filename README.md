# SmartDQC

Local-deployed data quality and cleaning platform for KKM (Kementerian Kesihatan Malaysia) child nutrition data. Runs fully on-premise — no data leaves the machine.

## What it does

SmartDQC ingests CSV/XLSX files from multiple KKM health data sources, cleans and standardises them against WHO 2006 z-score benchmarks, and surfaces insights through an interactive dashboard.

**Core capabilities:**
- AI-assisted schema mapping for known and unknown column layouts
- Source-specific cleaning pipelines (MyVASS, NCDC/TASKA, KPM, KKM)
- WHO 2006 z-score computation (WAZ, HAZ, BAZ) with nutrition status classification
- KPI dashboard with RAG traffic-light indicators and district-level trajectory
- Geo risk scoring and choropleth map by daerah
- AI narrative and NLQ (natural language query) powered by a local SLM
- PDF and PPTX report generation
- Cross-dataset entity linkage via IC + fuzzy name matching
- Full audit log, session history, and role-based access control

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy, Alembic, PostgreSQL |
| AI / SLM | Ollama (local, GPU) |
| Frontend | React, TypeScript, Vite, Recharts, react-simple-maps |
| Auth | JWT (python-jose) + bcrypt |
| Reports | ReportLab (PDF), python-pptx (PPTX) |
| ML | scikit-learn (IsolationForest, anomaly detection) |
| Deployment | Docker Compose |

## Data Sources

| Source | Description |
|--------|-------------|
| MyVASS | Clinic infant nutrition records (0–5 years) |
| NCDC / TASKA | Under-5 programme, multi-year wide format |
| KPM | School-age data (Tahun Satu, ~7 years) |
| KKM | School health weight/height (2024/2025) |
| Generic | Any CSV/XLSX — AI infers and maps the schema |

## Prerequisites

- Docker Desktop with GPU support (NVIDIA recommended)
- WHO 2006 z-score Excel files (6 files) — place in `data/zscore/`
- 16 GB RAM recommended; 8 GB VRAM for full GPU offload

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/MuhdLuqman00/SmartDQC.git
cd SmartDQC

# 2. Configure environment
cp .env.example .env
# Edit .env — set JWT_SECRET and ADMIN_SEED_PASSWORD before first run

# 3. Place WHO z-score files in data/zscore/
#    wfa-boys-zscore-expanded-tables.xlsx
#    wfa-girls-zscore-expanded-tables.xlsx
#    lhfa-boys-zscore-expanded-tables.xlsx
#    lhfa-girls-zscore-expanded-tables.xlsx
#    bfa-boys-zscore-expanded-tables.xlsx
#    bfa-girls-zscore-expanded-tables.xlsx

# 4. Start all services
docker compose up -d

# 5. Open the app
# Frontend: http://localhost:3000
# API docs: http://localhost:8000/docs
```

Default login: `admin` / value of `ADMIN_SEED_PASSWORD` in your `.env`

## Repository Structure

```
SmartDQC/
├── backend/
│   ├── main.py           # All API routes (FastAPI)
│   ├── config.py         # Standard schema, source detection, mapping hints
│   ├── auth.py           # JWT auth + bcrypt password hashing
│   ├── ai/               # Ollama client, schema mapper, NLQ, narrative
│   ├── cleaning/         # Source-specific cleaning (kkm, kpm, myvass, ncdc)
│   ├── db/               # SQLAlchemy models, init, session
│   ├── eda/              # WHO z-score, indicators, quality rules, KPI, runner
│   ├── export/           # PDF/PPTX reports, Tableau, data dictionary
│   ├── ml/               # Risk scoring, entity linkage, anomaly detection
│   └── utils/            # IC validator, age, geo, normaliser
├── frontend/
│   └── src/
│       ├── pages/        # Dashboard, Upload, Explorer, Quality, Geo, AI, Reports, ...
│       ├── components/   # Shared UI components
│       ├── context/      # Auth, Theme (dark/light), Language (BM/EN), Session
│       └── styles/       # Design tokens, global CSS
├── alembic/              # Database migrations
├── tests/                # Backend unit + integration tests
├── scripts/              # Utility scripts (seed data, report builder)
├── docker-compose.yml
└── .env.example
```

## Running Tests

```bash
# From project root (requires running PostgreSQL)
pytest tests/backend/ -v
```

## UI Features

- Light and dark mode
- Bilingual — Bahasa Malaysia and English toggle
- 4-step upload wizard with AI column mapping
- Inline cell editing in data explorer
- Expandable quality issue panels with fix hints
- District choropleth map with RAG indicators
- AI chat assistant with inline chart rendering
