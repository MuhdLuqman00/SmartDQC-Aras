# SmartDQC — Master Reference Document

> **This is the single source of truth for SmartDQC development.**
> Use this file to generate `architecture.md`, `decisions.md`, `known_issues.md`, and `workflows.md` as needed.
> All session decisions, architectural constraints, feature statuses, and open items are captured here.

---

## 1. Project Overview

**Platform:** SmartDQC — Smart Data Quality Check & Cleaning Tool
**Client:** KKM (Kementerian Kesihatan Malaysia)
**Deployment:** Local — accessible via IP address on client's laptop
**Hardware:** RTX 5060, 8GB VRAM
**Packaging:** Fully Dockerised — single image (frontend + backend + SLM + database). Client never sees source code.
**Maintenance:** Remote updates via versioned image tags. Remote access mechanism for dev team (no physical access needed).
**Languages:** Bahasa Malaysia and English throughout — all AI outputs, UI, reports.

---

## 2. Data Sources (10 Total)

| # | Source |
|---|--------|
| 1 | myVASS |
| 2 | CCMS |
| 3 | KPM |
| 4 | NCDC |
| 5 | NHMS |
| 6 | JKN |
| 7 | Parliament |
| 8 | DDSM |
| 9 | Admin Data (1) |
| 10 | Admin Data (2) |

**v1 scope:** Only 4 of 10 data sources have schema mappings. Remaining 6 are post-v1 schema work.

---

## 3. Feature List & Status

### 3.1 Data Portion — All Done (migrated from `data-cleaning-tool-new`)

> **Reference codebase:** `data-cleaning-tool-new/` — this is the current source of truth. The old `data-cleaning-tool/` is obsolete.

| # | Feature | Status | Key Files |
|---|---------|--------|-----------|
| 1 | Data Input & Detection | ✅ Done | `backend/config.py`, `backend/eda/runner.py`, `backend/eda/cleaning.py` (detect_data_type) |
| 2 | Column Mapping | ⚠️ Partial | `backend/config.py` (AUTO_MAPPING_HINTS for `myvass` + `klinik`), `frontend/src/components/cleaning/` — fuzzy match only, AI scenarios 2 & 3 missing |
| 3 | Data Cleaning | ✅ Done | `backend/eda/cleaning.py` (dedicated: clean_myvass, clean_ncdc, clean_kpm), `backend/utils/ic_validator.py`, `normaliser.py`, `outliers.py` |
| 4 | Derived Field Computation | ✅ Done | `backend/utils/age.py`, `geo.py`, `backend/eda/who_zscore.py`, `who_zscore_daily.py`, `indicators.py` |
| 5 | Data Quality Assessment | ✅ Done | `backend/eda/quality.py`, `kkm_quality_rules.py`, `missing.py`, `completeness.py`, 9-tab Excel quality report in `backend/main.py` |
| 6 | Statistical Analysis | ✅ Done | `backend/eda/numerical.py`, `categorical.py`, `indicators.py` |
| 7 | Visualization | ✅ Done | `backend/eda/charts.py`, `frontend/src/components/tabs/` (KKMDuplicatesTab, KKMQualityTab, KKMVisualizationTab, MyvassQualityTab, MyvassDashboardTab, ZscoreTab, TableauPrepTab, and others) |
| 8 | Export & Integration | ✅ Done | `backend/export/cleaned.py`, `tableau.py`, `backend/main.py` — includes 9-tab Excel quality report, in-memory clean cache, cached download endpoints |

**New capabilities present in `data-cleaning-tool-new` (not in original plan):**

| Capability | Where | Notes |
|-----------|-------|-------|
| Dedicated cleaning pipeline | `backend/eda/cleaning.py` | Separate from EDA pipeline — handles KPM, MyVASS, NCDC with source-specific rules |
| KPM source type | `cleaning.py:clean_kpm()` | School-age (6–8 yrs), BMI-based classification (not z-score) — Kurus/Normal/Berlebihan/Obes |
| MyVASS multi-file merge | `backend/main.py` | Endpoints: `/upload/merge-preview`, `/eda/run-merged`, `/download/cleaned-merged` — merge N files, dedup by IC (keep latest DOSE_DATE), remove null rows, then run EDA |
| 9-tab Excel quality report | `backend/main.py:_build_quality_report()` | Tabs: Executive Summary, Cleaning Rules, Records Dropped + WAZ/HAZ/BAZ × Negeri/Daerah pivot tables |
| In-memory clean cache | `backend/main.py:_cleaned_cache` | UUID-keyed cache (max 10 entries); enables instant download without re-upload |
| Birth weight classification | `backend/config.py:BIRTH_WEIGHT_CATEGORIES` | WHO-standard 5 categories for klinik data (ELBW/VLBW/LBW/Normal/Macrosomia) |
| WHO daily LMS z-scores | `backend/eda/who_zscore_daily.py` | Higher-precision daily age lookup vs. monthly interpolation |
| Dual-namespace API | `backend/main.py` | `/eda/*` (EDA pipeline) + `/clean/*` (dedicated cleaning) — ~20 endpoints total, not 10 |

### 3.2 AI Portion — Not Started

| # | Feature | Day | Notes |
|---|---------|-----|-------|
| 9 | AI Insight Generation | Day 2 | Merged with #10 — single LLM call |
| 10 | Smart Recommendations | Day 2 | Merged with #9 — do not build separate pipeline |
| 11 | Predictive Risk Scoring | Day 4 | Child-level + district-level |
| 12 | Smart Data Correction Suggestions | Day 3 | ML layer on top of existing `outliers.py` |
| 13 | Natural Language Querying | Day 2 | BM/English → pandas → answer + chart |
| 14 | Cross-Dataset Entity Resolution | Day 5 | MVP only: IC + DOB exact/fuzzy match |
| 15 | Automated Report Generation | Day 3 | Reuses narratives from #9/#10 — no duplicate LLM calls |
| 16 | Benchmarking & Target Tracking | Day 4 | Traffic-light dashboard vs national KPIs + WHO |

---

## 4. Session Decisions

These decisions were locked during the 2026-05-09 planning session. Do not revisit without strong reason.

### 4.1 Feature Consolidations

- **#9 + #10 merged:** AI Insight Generation and Smart Recommendations are one LLM call with one unified output. Do not build separate pipelines.
- **#9 + #15 share narrative logic:** Report Generation reuses the same AI narratives as Insight Generation. The difference is only the output container (in-app UI vs PDF/PPTX). Build narrative generation once, render twice.
- **#3 + #12 relationship:** Data Cleaning (#3) is done (rule-based). Smart Data Correction Suggestions (#12) is the ML layer on top. Build #12 as an extension of the existing cleaning pipeline — not a separate system. Row-level editing is the human-in-the-loop UI layer — users can accept, reject, or manually override individual ML suggestions before finalising. All edits are logged to `audit_log`.
- **#6 + #7 already done:** Statistical Analysis and Visualization are cross-cutting capabilities already built. No new work needed.

### 4.2 What Is a Feature vs What Is Architecture

| Item | Classification | Where It Lives |
|------|---------------|----------------|
| Session & Analysis History | Architecture | Persistence layer (Day 1) + interface history panel |
| Multi-Dataset Management | Architecture | Persistence layer (Day 1) + dataset library UI (Day 5) |
| Explainability | Cross-cutting requirement | Built into every AI module from Day 2 onwards |
| Schema Mapping (all 3 scenarios) | Part of Feature #2 | Day 5 upgrade |

### 4.3 Explainability Requirement

Not a feature — a requirement. Every AI decision must surface its reasoning in plain language:
- Why a record was flagged
- Why a correction was suggested
- Why a risk score is high

Design a reusable explainability module interface on Day 1. All AI modules (Days 2–5) plug into it. Non-negotiable.

### 4.4 Schema Mapping — 3-Scenario Flow

The AI in column mapping must be an **always-on validation layer**, not a fallback that only triggers for unknown schemas. Three scenarios must all be handled:

1. **Known schema, exact match** → auto-map (already works via `thefuzz`)
2. **Unknown schema entirely** → AI generates a new compatible schema dynamically (currently missing)
3. **Known schema + schema drift** (extra columns, renamed columns, type changes) → AI contextually maps new columns, infers renames by content/type similarity, warns on missing expected columns, detects type changes (currently missing)

**Critical:** Scenario 3 (schema drift) is the most common real-world case. Data sources evolve. This is Day 5 work.

### 4.5 Repo & UI Decisions

- **New standalone SmartDQC git repo** — clean slate, no dependency on or connection to `data-cleaning-tool`
- **UI built from scratch** — not adapted from `data-cleaning-tool` frontend. KKM branding, light/dark mode, chatbot interface.
- **Backend migrated** — copy and restructure backend logic from `data-cleaning-tool` into new repo on Day 1. Not a submodule.

### 4.6 Multi-Dataset Analysis Workflow

A user-facing workflow (Day 5) that enables:
- Dataset library UI — browse all past uploads with metadata (source, version, timestamp)
- Select 2+ datasets from different sessions
- Trigger combined/comparative analysis
- Results: side-by-side comparison, trend deltas, cross-dataset quality differences

This is what makes the persistence layer worthwhile. Without it, past uploads are just storage.

---

## 5. Architecture

### 5.1 System Components

| Component | Technology | Notes |
|-----------|-----------|-------|
| Frontend | React (from scratch) | KKM branding, light/dark mode, chatbot |
| Backend | Python (FastAPI) | Migrated from `data-cleaning-tool-new` — dual pipeline: `/eda/*` (EDA) + `/clean/*` (dedicated cleaning) |
| SLM Model Server | TBD (Ollama or llama.cpp) | <4B params, runs on RTX 5060 |
| Database | TBD (PostgreSQL or SQLite) | See Open Item #6 |
| Docker | docker-compose | All 4 containers in one image |

### 5.2 Persistence Layer (Design Before Day 1 Starts)

Six tables required:

| Table | Purpose |
|-------|---------|
| `dataset_library` | Store uploaded datasets — tags, source type, version, upload timestamp, file reference |
| `session_history` | Log each analysis run — quality score, key metrics, config used, timestamp, who ran it |
| `zscore_archive` | Historical Z-scores per child per period — structured for time-series queries |
| `indicator_snapshots` | Periodic indicator values per district/state — feeds Features #11 and #16 |
| `entity_linkage` | IC/NRIC-keyed index across uploaded sources — feeds Feature #14 |
| `audit_log` | Append-only log: who ran what, what was changed (including row-level edits and correction overrides), when — government traceability requirement |

**Re-run capability:** Store enough state to replay any past session identically.

### 5.3 SLM Architecture

- Model: <4B parameters (candidates: Qwen2.5-3B, Phi-3.5-mini, Mistral-3B)
- Must run on RTX 5060 8GB VRAM under sustained load
- Served as a Docker service (not just loaded in-process)
- Backend calls model via HTTP (Ollama API or compatible)
- Day 1 is a hard decision gate: if SLM fails VRAM budget on SE's laptop, swap model before Day 2

### 5.4 5W1H Framework

Structures all AI narrative output. Apply at both per-record and dataset level:

| Dimension | Per-Record Example | Dataset-Level Example |
|-----------|-------------------|----------------------|
| **Who** | Patient IC 123456 | Children aged 6–24 months in Selangor |
| **What** | WAZ = -3.2 (severely underweight) | 12.4% severe undernutrition rate |
| **When** | Measured March 2025 | Q1 2025 vs Q1 2024 |
| **Where** | Klinik Kesihatan Petaling | Districts: Klang, Petaling, Gombak |
| **Why** | Z-score below -3 SD triggers severe classification | Rate exceeds national benchmark by 4.1pp |
| **How** | WHO 2006 Growth Standards applied | Trend analysis across 4 quarters |

Output schema: JSON with both `bm` and `en` keys. Define exact structure before Day 2 starts (Open Item #10).

### 5.5 Docker & Deployment

- Four containers: `frontend`, `backend`, `slm`, `database`
- Single image distributed to client
- Client pulls image and runs locally — no source code exposed
- Remote maintenance: push new versioned image tags; client re-pulls and redeploys
- Remote access mechanism (SSH tunnel, webhook, or reverse tunnel) — spec before Day 6

---

## 6. Key Workflows

### 6.1 Schema Mapping (3-Scenario)

```
Upload CSV/Excel
       ↓
Extract column headers + sample data
       ↓
AI: Compare against known source schemas
       ↓
    ┌──────────────────────────────┐
    │                              │
Exact match         Schema drift         Unknown schema
    │                    │                     │
Auto-map           AI contextual         AI generates new
(existing)         mapping:              compatible schema
                   - map new cols        dynamically
                   - infer renames
                   - warn on missing
                   - flag type changes
    │                    │                     │
    └──────────────────────────────┘
                   ↓
         User reviews + confirms
                   ↓
         Pipeline proceeds
```

### 6.2 Data Cleaning Pipeline

```
Upload → Schema Mapping → Column Mapping
       → Derived Fields (age, geo, WHO Z-score, indicators)
       → Data Quality Assessment (predefined rules + DQ rules)
       → Data Cleaning (normalise, validate IC, impute, remove outliers)
       → [Day 3] ML Correction Suggestions (smart layer on top)
       → [Day 3] Row-Level Editing (accept/reject/manual override per suggestion; changes logged to audit_log)
       → Export (CSV, Excel, Tableau)
       → [Day 2] AI Narrative Generation (5W1H, BM + English)
       → [Day 3] Report Generation (PDF/PPTX — reuses narratives)
```

### 6.3 AI Narrative Generation

```
EDA pipeline completes
       ↓
Single LLM call with full analysis context:
  - Dataset summary
  - Quality scores
  - Indicator values
  - Outlier flags
  - Historical comparison (if available)
       ↓
Output: {
  executive_summary: { bm: "...", en: "..." },
  insights_5w1h: { who, what, when, where, why, how } × { bm, en },
  recommendations: [{ action, priority, bm, en, reasoning }],
  explainability: { flags: [{ record_id, reason_bm, reason_en }] }
}
       ↓
Render 1: In-app UI display (Feature #9/#10)
Render 2: PDF/PPTX export (Feature #15) — same data, different container
```

### 6.4 Multi-Dataset Analysis

```
User opens Dataset Library
       ↓
Browse past uploads (source, date, quality score)
       ↓
Select 2+ datasets
       ↓
Trigger combined analysis:
  - Side-by-side quality comparison
  - Trend deltas (if same source, different periods)
  - Cross-source entity matching (Feature #14)
  - AI narrative for the comparison (BM + English)
       ↓
Export comparative report
```

---

## 7. Pre-Work Checklist (Must Complete BEFORE Day 1)

These items block the first hour of development if unresolved:

- [ ] **SLM model selection** — choose from: Qwen2.5-3B, Phi-3.5-mini, Mistral-3B; confirm runs on RTX 5060 8GB; download weights
- [ ] **Database choice** — PostgreSQL (Docker service) or SQLite (embedded); decision affects Day 1 schema and all queries
- [ ] **Design persistence schema** — define all 6 tables: `dataset_library`, `session_history`, `zscore_archive`, `indicator_snapshots`, `entity_linkage`, `audit_log`
- [ ] **Design 5W1H output schema** — exact JSON structure (per-record vs dataset-level fields, BM + English keys)
- [ ] **Define explainability module interface** — reusable pattern all AI modules plug into; design once, apply Days 2–5
- [ ] **Request MOH report template** — get actual KKM quarterly report PDF/PPTX from client as reference for Feature #15
- [ ] **Define traffic-light thresholds** — confirm KPI targets with client (what % malnutrition = On Track / At Risk / Off Track)
- [ ] **Decide Feature #12 approach** — rule-based heuristics (fast, no training data needed) or ML classifier (needs labelled data); document the decision
- [ ] **Request KKM branding assets** — if not received by Day 5, approve fallback (neutral clean UI, KKM colour codes, placeholder logo)
- [ ] **Generate synthetic historical dataset** — 12-month rollback of Z-scores for 500 synthetic children across 5 districts; needed before Day 4
- [ ] **Define SE acceptance test workflow** — write 1-page KKM staff user journey (what they upload, what they do, what outputs they verify)

---

## 8. 6-Day Development Timeline

> Daily testing runs on the **SE's laptop** (RTX 5060, 8GB VRAM) — the production environment. Build on your machine, test on theirs.

### Day 1 — Foundation & Architecture (6h)
**Goal:** New repo running, SLM confirmed on SE hardware, existing features intact, persistence layer stubbed.

**Morning (3h):**
- Init new standalone SmartDQC git repo
- Migrate backend from `data-cleaning-tool` (copy + restructure)
- Docker skeleton — define 4 containers: frontend, backend, slm, database
- Select + pull SLM model; test basic inference call on RTX 5060
- Generate `Docs/architecture.md`, `Docs/decisions.md`, `Docs/known_issues.md`, `Docs/workflows.md` from this master file

**Afternoon (3h):**
- Wire migrated backend — verify all ~20 endpoints still respond (EDA namespace: `/upload/preview`, `/mapping/validate`, `/eda/run`, `/cleaned/preview`, `/download/cleaned`, `/export/aggregated`, `/transform/myvass-wide-to-long`, `/upload/merge-preview`, `/eda/run-merged`, `/download/cleaned-merged`; Clean namespace: `/clean/detect-type`, `/clean/quality-check`, `/clean/run`, `/clean/download`, `/clean/quality-check-multi`, `/clean/run-multi`, `/clean/download-multi`, `/clean/download-cached/{id}`, `/clean/download-report/{id}`)
- Implement persistence layer (stubs if time-constrained; complete Day 2 morning if needed)
- Verify SLM under sustained load within 8GB VRAM budget
- **SE laptop test:** Upload KKM file → full EDA → Features #1–8 pass → dataset persisted in history → SLM loads within VRAM

**Decision gate:** If SLM fails on SE's laptop, swap model before Day 2. Do not proceed.

### Day 2 — AI Core: Insights + Recommendations + NLQ (6h)
**Goal:** LLM wired into pipeline, BM/English output, NLQ working end-to-end.

**Morning (3h):**
- AI narrative module — single LLM call: executive summary + 5W1H insights + recommendations (Features #9 + #10)
- Explainability wired into every narrative output (WHY, not just WHAT)
- Output in BM and English

**Afternoon (3h):**
- Feature #13: NLQ — user query (BM/English) → LLM → pandas exec → answer + auto chart
- Sandbox pandas execution (security: no arbitrary file system access)
- **SE laptop test:** Narrative quality, BM accuracy, NLQ on 5 sample queries, response time acceptable

### Day 3 — Data Correction + Report Generation (6h)
**Goal:** ML correction suggestions live. One-click PDF/PPTX export.

**Morning (3h):**
- Feature #12: ML correction suggestions on top of `outliers.py` — detect decimal shifts, digit transpositions, column swaps; classify outlier type; surface reasoning per suggestion. Row-level editing UI: users can accept, reject, or manually override each suggestion inline; all edits logged to `audit_log`.

**Afternoon (3h):**
- Feature #15: Report generation — reuse Day 2 narratives (no new LLM calls); render into MOH-style PDF + PPTX with tables, auto-selected charts, recommendations, methodology appendix
- **SE laptop test:** Corrections visible in report; BM/English correct in PDF/PPTX; no duplicate LLM calls; opens cleanly on SE machine

### Day 4 — Predictive Analytics + Benchmarking (6h)
**Goal:** Risk scoring per child and district. Benchmarking dashboard live.

**Morning (3h):**
- Feature #11: Predictive risk scoring — child-level malnutrition risk using historical Z-scores + demographics; district-level early warning for KKM threshold breaches next quarter; output risk score column + "Senarai Kanak-kanak Berisiko"; explain each score

**Afternoon (3h):**
- Feature #16: Benchmarking — district/state vs national KPIs + WHO targets + historical self; traffic-light dashboard (On Track / At Risk / Off Track); AI trajectory narrative per district/state
- **SE laptop test:** Threshold logic, alert generation, narrative accuracy; full pipeline with synthetic historical data

### Day 5 — Entity Resolution, Multi-Dataset & Schema AI (6h)
**Goal:** MVP entity resolution. Multi-dataset workflow live. Column mapping upgraded to all 3 AI scenarios.

**Morning (3h):**
- Feature #14 (MVP): IC + DOB exact/fuzzy match across MyVASS + NCDC + KKM; detect contradictions; output unified longitudinal profile per child
- Multi-Dataset Analysis Workflow: dataset library UI; select 2+ datasets; combined/comparative analysis; side-by-side results with trend deltas

**Afternoon (3h):**
- Feature #2 upgrade: Replace `thefuzz`-only mapping with AI-powered schema validation — all 3 scenarios; AI always-on, not fallback-only
- **SE laptop test:** Upload 2 datasets in separate sessions → library → select both → combined analysis verified. Full end-to-end integration test all 16 features.

> **Note:** If Day 4 or earlier finishes ahead of schedule, begin UI work (Day 6 afternoon) on Day 5 afternoon.

### Day 6 — Docker + UI + Final Testing (6h)
**Goal:** Shippable Docker image. KKM-branded UI. Full clean end-to-end pass.

**Morning (3h):**
- Full Docker containerisation — package all 4 containers into single image
- Verify image runs clean with no source code exposed
- Remote maintenance mechanism (versioned tags + remote access)

**Afternoon (3h):**
- UI from scratch: KKM branding, light/dark mode, chatbot wired to NLQ (Feature #13)
- **SE laptop final test:** Pull Docker image as clean deployment (simulates client). SE runs full KKM staff workflow. Bug fixes only — no new features. Tag v1.0.

---

## 9. Audit Findings

Full audit conducted 2026-05-09 across all 6 days.

### Cross-Cutting Issues

| Issue | Affects | Severity |
|-------|---------|----------|
| Persistence layer under-scoped — no schema, no DB choice made | Days 1, 4, 5 | Critical |
| SLM model not selected — blocks all AI work | Days 2–6 | Critical |
| Time budget underestimated ~30–50% per day | All days | High |
| KKM design assets not received — no fallback plan | Day 6 | High |
| Synthetic historical data not generated | Days 4, 5 | High |

### Per-Day Critical Gaps

**Day 1:** DB choice + schema must be decided before coding starts. SLM evaluation needs defined acceptance criteria (latency, VRAM peak vs sustained). Docker Compose networking not spec'd. 6h may not be enough — stub persistence, complete Day 2 morning.

**Day 2:** SLM must be a real Docker service wired to backend. 5W1H output schema and explainability module must be designed before coding starts. NLQ pandas exec needs sandboxing. Bilingual infrastructure unspecified. Chatbot conversation state not scoped.

**Day 3:** Feature #12 model architecture undefined (rule-based vs ML vs LLM). MOH report template must be in hand before PDF scaffold. Auto-chart selection logic undefined. Corrections visible in report implies frontend work not in current Day 3 scope.

**Day 4:** Synthetic historical data must exist before Day 4. Risk score model spec must be pre-decided (input features, algorithm, output format). Traffic-light thresholds must be confirmed. Blocked if Day 1 persistence and Day 2 LLM are not complete.

**Day 5:** Multi-dataset workflow entirely greenfield — no backend, no UI scaffold yet. Feature #14 requires cross-dataset linkage table from Day 1. Feature #2 AI upgrade requires SLM. Testing 2 datasets across sessions requires persistence to exist.

**Day 6:** Dockerfile does not exist yet. KKM assets not received — need fallback now. NLQ and chatbot depend entirely on Day 2. Remote maintenance not spec'd. UI from scratch realistically takes 8–11h, not 3h — must start Day 5 afternoon at latest.

---

## 10. Risk Register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| SLM fails VRAM budget on Day 1 | Blocks Days 2–5 | Day 1 is hard decision gate — swap model before proceeding |
| Feature #14 complexity overruns | May eat all of Day 5 | Scoped to MVP: IC + DOB only; probabilistic matching is post-v1 |
| Client business rules not provided | Feature #5 rule count may change | 9 known rules hardcoded; extensible for client additions |
| Only 4 of 10 sources schema-mapped | Features #1–#5 only fully cover 4 sources | v1 targets 4 known sources; remaining 6 are post-v1 |
| KKM-specific logic embedded in generic features | Extending to other 6 sources requires refactor | Note in architecture; isolate cleaning/derived logic into source-specific modules post-v1 |
| AI narrative quality in BM | May need prompt tuning | Budget 1h on Day 2 afternoon for BM iteration |
| No audit trail specified | Government health data requires traceability | Append-only audit log per session — build into persistence Day 1 |
| UI from scratch underestimated | Half a day is not enough | Begin Day 5 afternoon if integration finishes early |
| Feature #12 no training data | ML classifier approach blocked if no labelled corrections data | Decide rule-based vs ML before Day 1; rule-based is safer default |
| MOH report template not received | Can't build PDF scaffold without it | Request immediately; build generic template as fallback |

---

## 11. Open Items

| # | Item | Blocking |
|---|------|---------|
| 1 | SLM model selection | Day 1 — must decide before Day 1 |
| 2 | Client predefined business rules (full list) | Feature #5 |
| 3 | Schema structure for Admin Data (1) and (2) | Post-v1 |
| 4 | KKM design assets and branding files | Day 6 — need fallback if not received |
| 5 | Feature count confirmation (16 doc vs 18 verbal) | Product spec |
| 6 | Database choice — PostgreSQL vs SQLite vs DuckDB | Day 1 persistence layer |
| 7 | MOH quarterly report template/example from client | Day 3 Feature #15 |
| 8 | Traffic-light KPI threshold definitions | Day 4 Feature #16 |
| 9 | Risk score model architecture — rules vs ML vs LLM | Day 4 Feature #11 |
| 10 | 5W1H output schema — exact JSON structure | Day 2 before coding |
| 11 | NLQ sandboxing strategy for pandas exec | Day 2 Feature #13 |
| 12 | Bilingual infrastructure — local transformer vs API, BM domain glossary | Day 2 BM output |
| 13 | Full KKM staff workflow definition for SE acceptance test | Day 6 final test |
| 14 | Docker Compose networking spec | Day 1 Docker skeleton |
| 15 | Remote maintenance mechanism — SSH tunnel vs webhook vs reverse tunnel | Day 6 |

---

## 12. Known Scope Gaps (Post-v1)

- 6 of 10 data sources have no schema mappings (NHMS, JKN, Parliament, DDSM, Admin Data 1 & 2)
- KKM-specific nutrition logic (Features #3 and #4) is tightly coupled — needs isolation before extending to other 6 sources
- Full probabilistic entity matching for Feature #14 (Fellegi-Sunter or similar)
- Chatbot conversation state and multi-turn memory
- Complete predefined business rules from client — only 9 known rules currently hardcoded
- Feature count discrepancy (16 documented, 18 verbal) — 2 unconfirmed features

---

*Generated 2026-05-09. Based on verbal briefing, feature review session, codebase audit, and 6-day planning session.*
*Updated 2026-05-11: Section 3.1, 5.1, and Day 1 timeline updated to reflect `data-cleaning-tool-new` as the current reference codebase.*
*Source files: `SmartDQC_Brief_Summary.md`, `SmartDQC_BP_KKM_Proposed Features.docx`, `data-cleaning-tool-new` codebase audit.*
