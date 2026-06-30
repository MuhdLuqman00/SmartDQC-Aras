# SmartDQC

Local-deployed data quality and cleaning platform for child-growth / nutrition datasets. Runs fully on-premise — no data leaves the machine.

---

## What It Does

SmartDQC ingests CSV/XLSX files from multiple health data sources, cleans and standardises them against WHO 2006 z-score benchmarks, and surfaces insights through an interactive bilingual dashboard.

**Core capabilities:**

- AI-assisted schema mapping for known and unknown column layouts
- Source-specific cleaning pipelines (MyVASS, NCDC/TASKA, KPM, KKM, Generic)
- WHO 2006 z-score computation (WAZ, HAZ, BAZ) with nutrition status classification (stunting, wasting, underweight, overweight)
- KPI dashboard with RAG traffic-light indicators (Green/Amber/Red) vs. configurable national nutrition targets (e.g. NPAN 2021–2025)
- District-level geo risk scoring and choropleth map by daerah
- AI narrative generation and NLQ (natural language query) powered by a local SLM via Ollama
- PDF and PPTX report generation with quality metrics and AI insights
- Cross-dataset entity linkage via IC + fuzzy name matching
- Full audit log, session history, and role-based access control
- Bilingual interface — Bahasa Malaysia and English

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI, SQLAlchemy, Alembic, PostgreSQL 16 |
| AI / SLM | Ollama (local, GPU-served, `gemma4:e4b-it-qat` default) |
| Frontend | React 18, TypeScript, Vite, Recharts, react-simple-maps |
| Auth | JWT (python-jose) + bcrypt, X-User header for named identity |
| Reports | ReportLab (PDF), python-pptx (PPTX) |
| ML | scikit-learn (IsolationForest, anomaly detection) |
| Deployment | Docker Compose (multi-container) or standalone all-in-one image |

---

## Data Sources Supported

| Source | Description |
|--------|-------------|
| **MyVASS** | Clinic infant nutrition records (0–5 years), wide-format multi-year records |
| **NCDC / TASKA** | Under-5 programme, multi-year wide format, auto-reshaped to long |
| **KPM** | School-age data (Tahun Satu, ~7 years) |
| **KKM** | School health weight/height (2024/2025 year-mode) |
| **Generic** | Any CSV/XLSX — AI infers and maps the schema dynamically |

---

## System Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 8 GB | 16 GB |
| VRAM (GPU) | 8 GB NVIDIA | 8 GB+ NVIDIA |
| Docker | Docker Desktop with GPU support | Docker Desktop + NVIDIA Container Toolkit |
| OS | Windows / Linux / macOS | — |

> **GPU is required** for Ollama to serve the AI model at a usable speed. CPU-only mode works but is significantly slower.

---

## Prerequisites

Before starting, ensure you have:

1. **Docker Desktop** installed with GPU support enabled
   - Windows: enable NVIDIA GPU in Docker Desktop → Settings → Resources → GPU
   - Linux: install the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

2. **WHO 2006 z-score Excel files** — 6 files that must be placed in `data/zscore/` at the project root:

   ```
   data/zscore/
   ├── wfa-boys-zscore-expanded-tables.xlsx
   ├── wfa-girls-zscore-expanded-tables.xlsx
   ├── lhfa-boys-zscore-expanded-tables.xlsx
   ├── lhfa-girls-zscore-expanded-tables.xlsx
   ├── bfa-boys-zscore-expanded-tables.xlsx
   └── bfa-girls-zscore-expanded-tables.xlsx
   ```

   These files are available from the [WHO Child Growth Standards](https://www.who.int/tools/child-growth-standards/software) page. Create the `data/zscore/` folder manually if it does not exist.

---

## Deployment Options

| Option | Best For | Effort |
|--------|----------|--------|
| [A — Docker Hub (multi-container)](#option-a--docker-hub-multi-container) | Standard production setup | Low |
| [B — Docker Hub (standalone)](#option-b--docker-hub-standalone-all-in-one) | Single-machine quick demo | Lowest |
| [C — Local development (from source)](#option-c--local-development-from-source) | Contributing to the code | High |

---

## Option A — Docker Hub (Multi-Container)

Pulls pre-built images from Docker Hub and runs five services via Docker Compose. This is the standard setup. The bundled Ollama can be swapped for an LLM running on a separate GPU host — see [Split deployment](#split-deployment--llm-on-a-separate-gpu-host) below.

| Service | Purpose | Host Port |
|---------|---------|-----------|
| `postgres` | PostgreSQL 16 database | internal |
| `api` | FastAPI backend | `8000` |
| `frontend` | React SPA (Nginx) | `3000` |
| `ollama` | Local SLM inference server | `11435` |
| `ollama-init` | Pulls the AI model on first run | — |

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/MuhdLuqman00/SmartDQC.git
cd SmartDQC

# 2. Copy and configure the environment file
cp .env.example .env
```

All values in `.env` have sensible defaults for a local setup. No changes are required to get started.

> **Auth model:** SmartDQC uses name-based sessions — users identify themselves by typing a name, which the frontend sends as an `X-User` header. There is no password login. `JWT_SECRET` and `ADMIN_SEED_PASSWORD` are legacy variables retained for backwards compatibility and do not affect day-to-day operation.

```bash
# 3. Start all services
docker compose up -d

# 4. On first run, the AI model is downloaded from the Ollama registry (~3 GB).
# This takes several minutes depending on your connection. Watch progress with:
docker compose logs -f ollama-init
# You will see "Model ready." when the download is complete
```

> **No z-score file setup needed.** The api image already includes the WHO 2006 z-score tables baked in at build time, so there is nothing to copy onto the host. (Placing files in `data/zscore/` is only needed when *building* the image from source or running Option C.)

### Access

| URL | Description |
|-----|-------------|
| `http://localhost:3000` | Frontend (main app) |
| `http://localhost:8000/docs` | Backend API docs (Swagger UI) |

**To access:** open the app, type any name when prompted, and the system will create a session scoped to that name.

### Split deployment — LLM on a separate GPU host

By default all five services run on one machine. If your GPU lives on a separate host (e.g. a DGX) while the rest of the app runs on a CPU-only VM, point SmartDQC at that remote Ollama instead of the bundled one. Only the AI calls cross to the GPU host — the frontend, backend, and database still run together on the app VM.

1. **On the GPU host** — run Ollama so it is reachable over the network, and pull the model:

   ```bash
   # Bind to all interfaces, not just localhost, so the app VM can reach it
   OLLAMA_HOST=0.0.0.0:11434 ollama serve
   ollama pull gemma4:e4b-it-qat
   ```

   Open the Ollama port (default `11434`) in the GPU host's firewall for the app VM.

2. **On the app VM** — set the Ollama URL in `.env`:

   ```bash
   OLLAMA_BASE_URL=http://<gpu-host-ip>:11434
   ```

3. **On the app VM** — start only the non-LLM services. This skips the bundled `ollama` and `ollama-init`, so the VM needs no GPU:

   ```bash
   docker compose up -d postgres api frontend
   ```

> Leave `OLLAMA_BASE_URL` unset (or `http://ollama:11434`) to go back to the bundled single-host setup with `docker compose up -d`.

---

## Option B — Docker Hub (Standalone All-in-One)

A single container that bundles Ollama, PostgreSQL, the FastAPI backend, and the Nginx frontend via Supervisord. Best for a quick demo on a single machine.

```bash
# 1. Clone the repository
git clone https://github.com/MuhdLuqman00/SmartDQC.git
cd SmartDQC

# 2. Copy and configure the standalone environment file
cp .env.standalone.example .env
```

No changes to `.env` are required to get started — all values have sensible defaults.

> **Auth model:** SmartDQC uses name-based sessions via the `X-User` header. There is no password login. `JWT_SECRET` and `ADMIN_SEED_PASSWORD` in the `.env` are legacy variables and do not affect operation.

```bash
# 3. Start the standalone container
docker compose -f docker-compose.standalone.yml up -d
```

> **No z-score file setup needed.** The standalone image already includes the WHO 2006 z-score tables baked in at build time.

### Access

| URL | Description |
|-----|-------------|
| `http://localhost:8080` | Frontend (main app) |
| `http://localhost:8000` | Backend API |

**To access:** open the app, type any name when prompted, and the system will create a session scoped to that name.

> First startup takes a few minutes while the model initialises inside the container.

> **Image tag note:** The published image is `luqmanzulkefli/smartdqc-standalone:v3.11`. The tag name does not determine the AI model — the model is pulled at runtime by Ollama according to `OLLAMA_MODEL` in your `.env` (default: `gemma4:e4b-it-qat`).

---

## Option C — Local Development (From Source)

Run the backend and frontend directly on your machine for active development.

### Additional Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16 running locally (or start just the Postgres container: `docker compose up -d postgres`)
- Ollama installed and running locally (`ollama pull gemma4:e4b-it-qat`)

### Backend

```bash
# 1. Create and activate a virtual environment
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Set environment variables (in your shell or a .env file)
# Windows PowerShell
$env:DATABASE_URL = "postgresql://smartdqc:smartdqc@localhost:5432/smartdqc"
$env:WHO_ZSCORE_DIR = "C:\absolute\path\to\data\zscore"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "gemma4:e4b-it-qat"
$env:JWT_SECRET = "your-secret-here"
$env:ADMIN_SEED_PASSWORD = "your-password-here"

# macOS / Linux
export DATABASE_URL=postgresql://smartdqc:smartdqc@localhost:5432/smartdqc
export WHO_ZSCORE_DIR=/absolute/path/to/data/zscore
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_MODEL=gemma4:e4b-it-qat
export JWT_SECRET=your-secret-here
export ADMIN_SEED_PASSWORD=your-password-here

# 4. Run database migrations (creates all tables)
cd ..
alembic upgrade head

# 5. Start the backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

API is now at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Frontend

```bash
# In a new terminal, from the project root
cd frontend

# 1. Install dependencies
npm install

# 2. Start the Vite dev server
npm run dev
```

Frontend is now at `http://localhost:3000`. It calls the backend directly at `http://localhost:8000` (the default in `frontend/src/api/client.ts`; override with the `VITE_API_BASE_URL` env var), and the backend allows cross-origin requests, so no proxy is needed.

### AI model (Ollama)

```bash
# Install Ollama from https://ollama.com, then pull the model
ollama pull gemma4:e4b-it-qat
```

The AI features (narrative generation, NLQ chat) require Ollama to be running with a compatible model loaded.

---

## Environment Variables Reference

### Multi-Container (`.env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `WHO_ZSCORE_DIR` | `/app/data/zscore` | Path to WHO z-score Excel files inside the container |
| `POSTGRES_USER` | `smartdqc` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `smartdqc` | PostgreSQL password |
| `POSTGRES_DB` | `smartdqc` | PostgreSQL database name |
| `DATABASE_URL` | *(auto-constructed)* | Override only when connecting to an external Postgres |
| `OLLAMA_MODEL` | `gemma4:e4b-it-qat` | Ollama model tag — any tag from [ollama.com/library](https://ollama.com/library) |
| `OLLAMA_THINK` | `false` | Set `true` only for reasoning models (not needed for Gemma 4) |
| `OLLAMA_KEEP_ALIVE` | `-1` | `-1` = keep model in VRAM forever; use `30m` on a shared GPU |
| `OLLAMA_CONTEXT_LENGTH` | `8192` | Context window size — keeps KV cache within 8 GB VRAM |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | URL of the Ollama server. Defaults to the bundled `ollama` service. For a [split deployment](#split-deployment--llm-on-a-separate-gpu-host), point this at an external GPU host, e.g. `http://10.0.0.5:11434` |
| `JWT_SECRET` | `JWT_SECRET_PLACEHOLDER` | Legacy JWT signing secret. Not used by the current X-User auth model. |
| `ADMIN_SEED_PASSWORD` | `ADMIN_SEED_PASSWORD_PLACEHOLDER` | Legacy admin seed password. Not used by the current X-User auth model. |

### Standalone (`.env.standalone.example`)

Same as above except `POSTGRES_*`, `DATABASE_URL`, and `OLLAMA_BASE_URL` are not needed — they are managed internally by the container.

---

## Repository Structure

```
SmartDQC/
├── backend/
│   ├── main.py                   # All API routes (50+ endpoints, FastAPI)
│   ├── config.py                 # Standard schema, source detection, mapping hints
│   ├── auth.py                   # JWT auth + bcrypt, X-User named identity
│   ├── clinical_ranges.py        # Machine-readable clinical range registry
│   ├── ai/                       # Ollama client, schema mapper, NLQ, narrative
│   ├── cleaning/                 # Source-specific cleaning (kkm, kpm, myvass, ncdc)
│   ├── db/                       # SQLAlchemy models (14 tables), DB init
│   ├── eda/                      # WHO z-score, indicators, quality rules, KPI, runner
│   ├── export/                   # PDF/PPTX reports, Tableau export, data dictionary
│   ├── ml/                       # Risk scoring, entity linkage, anomaly detection
│   └── utils/                    # IC validator, age computation, geo, normaliser
├── frontend/
│   └── src/
│       ├── pages/                # 14 pages (Dashboard, Upload, Explorer, AI, Reports, ...)
│       ├── components/           # Shared UI components (choropleth, RAG badges, charts)
│       ├── context/              # Auth, Theme (dark/light), Language (BM/EN), Session
│       ├── api/client.ts         # Axios HTTP client
│       └── styles/               # Design tokens, global CSS
├── alembic/                      # Database migrations
├── tests/                        # Backend unit + integration tests
├── scripts/                      # Utility scripts (seed data, report builder)
├── data/
│   └── zscore/                   # WHO 2006 z-score Excel files (place here — gitignored)
├── Docs/                         # Architecture, clinical ranges, ADRs, UI spec
├── docker-compose.yml            # Multi-container (Postgres + API + Frontend + Ollama)
├── docker-compose.standalone.yml # All-in-one single container
├── Dockerfile                    # Backend API image
├── frontend/Dockerfile           # Frontend Nginx image
├── Dockerfile.standalone         # All-in-one image (Ollama + Postgres + API + Nginx)
├── .env.example                  # Environment template (multi-container)
└── .env.standalone.example       # Environment template (standalone)
```

---

## Running Tests

```bash
# Backend unit and integration tests (requires PostgreSQL running)
pytest tests/backend/ -v

# Frontend component tests (Vitest)
cd frontend
npm test
```

---

## Pages & Features

| Page | Description |
|------|-------------|
| **Dashboard** | KPI summary with RAG indicators, district choropleth, breakdown by state / gender / age |
| **Upload** | 4-step wizard — file upload, AI column mapping, quality preview, issue review |
| **Explorer** | Paginated data table with inline cell editing, column filters, and CSV/XLSX export |
| **Cleaning** | Rule-based cleaning (14 rule families) with preview-impact before applying |
| **Quality** | Completeness, classification accuracy, outlier summary, and cell-level flags |
| **Geo** | District risk scoring with choropleth and trend lines by daerah |
| **AI** | Bilingual NLQ chat (type a question, get a chart or table back) + EDA narrative |
| **Reports** | Generate PPTX (7 slides) or PDF with quality metrics and AI insights |
| **Linkage** | Cross-dataset entity matching by IC + fuzzy name, with confidence scores |
| **Settings** | Override KPI targets and clinical ranges (admin only) |
| **Audit** | Read-only government traceability log of all user actions |
| **History** | Session history per dataset with rollback |
| **Dataset Library** | Saved datasets, owner-scoped visibility, cleanup |

---

## Documentation

Extended reference material is in the `Docs/` folder:

| File | Contents |
|------|---------|
| `Docs/architecture.md` | System design, API namespace reference, persistence layer |
| `Docs/clinical_ranges_provenance.md` | Evidence tier and rationale for all numeric bounds |
| `Docs/known_issues.md` | Risk register and open items |
| `Docs/workflows.md` | User workflows per data source |
| `Docs/SmartDQC_UI_Spec.md` | Component and layout specifications |
| `Docs/SmartDQC_Master.md` | High-level feature specs and business logic |

---

## Troubleshooting

**AI features not working / narrative returns nothing**

The model is still being pulled on first run. Check progress:
```bash
docker compose logs -f ollama-init
```
Once complete, the log shows `Model ready.`

**Z-score computation fails or returns empty results**

Ensure all 6 WHO Excel files are present in `data/zscore/` on the host machine. This folder is mounted into the container — missing files silently produce empty z-score outputs.

**Frontend shows "Network Error" or blank dashboard**

Check that all services are running:
```bash
docker compose ps
```
All services should show `running`. The `ollama-init` service exits after the model pull — that is expected behaviour.

**API crashes on startup / Postgres not ready**

On first run, Postgres can take a few seconds to initialise. The API service waits for the Postgres health check before starting. If it keeps failing, check Postgres logs:
```bash
docker compose logs postgres
```

**Changing the AI model**

Edit `OLLAMA_MODEL` in your `.env` to any valid tag from [ollama.com/library](https://ollama.com/library), then restart:
```bash
docker compose down
docker compose up -d
```
The `ollama-init` service will pull the new model automatically.

---

## Building & Publishing the Images (Maintainers Only)

This section is for maintainers who need to rebuild and push updated images to Docker Hub. Publishing requires Docker Hub credentials for the `luqmanzulkefli` account — cloning the repo alone does not grant push access.

### Prerequisites

```bash
docker login
# Enter luqmanzulkefli credentials when prompted
```

### Build and push the API image

```bash
docker build -t luqmanzulkefli/smartdqc-api:latest .
docker push luqmanzulkefli/smartdqc-api:latest
```

### Build and push the frontend image

```bash
docker build -t luqmanzulkefli/smartdqc-frontend:latest ./frontend
docker push luqmanzulkefli/smartdqc-frontend:latest
```

### Build and push the standalone image

The standalone image embeds the frontend build, backend, Postgres, and Nginx in one container. Tag it with the version number — do not add a `latest` tag.

```bash
docker build -f Dockerfile.standalone -t luqmanzulkefli/smartdqc-standalone:v3.11 .
docker push luqmanzulkefli/smartdqc-standalone:v3.11
```

> The AI model is **not** baked into the standalone image. Ollama pulls `OLLAMA_MODEL` from the Ollama registry on first container boot and caches it in the `ollama_models` volume. The deploy host needs internet access on first run only.

### After publishing

Update the image tag in `docker-compose.standalone.yml` to match the new version before committing.
