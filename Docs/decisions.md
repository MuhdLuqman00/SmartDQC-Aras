# SmartDQC — Architecture Decision Records

> Decisions locked during the 2026-05-09 planning session and 2026-05-12 Day 1 implementation.
> Do not revisit without strong justification. Add new ADRs here for future locked decisions.

---

## ADR-001: DuckDB over SQLite / PostgreSQL

**Date:** 2026-05-12
**Status:** Accepted

**Decision:** Use DuckDB as the persistence backend.

**Why:**
- SQLite's row-store is not optimised for analytical queries (aggregations, pivots) that SmartDQC runs frequently
- PostgreSQL requires a separate Docker service, connection pooling, and PGDATA volume management — too heavyweight for a local single-client deployment
- DuckDB is embedded (no server process), analytical-first (columnar), supports full SQL, and produces a single portable `.duckdb` file

**Implications:**
- DB file lives at `SMARTDQC_DB_PATH` (default: `/app/data/smartdqc.duckdb` in container)
- All migrations handled by `init_db()` running `CREATE TABLE IF NOT EXISTS` on startup
- File is gitignored — never commit `data/smartdqc.duckdb`

---

## ADR-002: Standalone SmartDQC git repo

**Date:** 2026-05-09
**Status:** Accepted

**Decision:** SmartDQC is a new standalone git repository — not a submodule of `data-cleaning-tool`.

**Why:**
- Clean slate for the new stack (DuckDB, Ollama, fresh UI)
- The legacy repo (`data-cleaning-tool-new`) is a migration reference only, not a dependency

---

## ADR-003: UI built from scratch

**Date:** 2026-05-09
**Status:** Accepted

**Decision:** React frontend built from scratch — not adapted from `data-cleaning-tool` frontend.

**Why:**
- Legacy `kkm-eda-dashboard` v3.2.0 has no light/dark mode, no chatbot, no dataset library — adapting it costs more than a fresh start
- SmartDQC requires KKM branding, bilingual UI, chatbot wired to NLQ (Feature #13), session history, and multi-dataset workflow

**Implications:**
- No frontend container until Day 6; interact via API during Days 1-5
- `frontend/` directory scaffolded in repo now; populated on Day 5 afternoon / Day 6

---

## ADR-004: Features #9 + #10 — two sequential LLM calls, not one

**Date:** 2026-05-12 (revised from 2026-05-09 draft)
**Status:** Accepted

**Decision:** AI Insight Generation (#9) and Smart Recommendations (#10) use two sequential focused LLM calls — Insights first, Recommendations second (with Insights as context).

**Why the original single-call approach was revised:**
- A `<4B` parameter model asked to produce executive summary + 6-part 5W1H x bilingual + recommendations + per-record explainability in one shot degrades significantly — format failures, hallucinations, and truncation are common
- Two focused calls allow independent quality tuning: fix the recommendation prompt without touching insights
- A failed single call requires full regeneration; two calls allow partial retry

**How it works:**

```
EDA pipeline completes
       |
Call 1 — Insights (Feature #9)
  Input:  dataset summary, indicator distributions, outlier counts, historical comparison
  Output:
    {
      "executive_summary": { "bm": "...", "en": "..." },
      "insights_5w1h": {
        "who":   { "bm": "...", "en": "..." },
        "what":  { "bm": "...", "en": "..." },
        "when":  { "bm": "...", "en": "..." },
        "where": { "bm": "...", "en": "..." },
        "why":   { "bm": "...", "en": "..." },
        "how":   { "bm": "...", "en": "..." }
      },
      "explainability": {
        "flags": [{ "record_id": "...", "reason_bm": "...", "reason_en": "..." }]
      }
    }
       |
Call 2 — Recommendations (Feature #10)
  Input:  Call 1 output + same dataset context
  Output:
    {
      "recommendations": [
        { "action": "...", "priority": "high|medium|low", "bm": "...", "en": "...", "reasoning": "..." }
      ]
    }
       |
Merge both -> stored as one analysis_results record (result_type="narrative")
```

---

## ADR-005: Report generation (#15) renders structured data, not shared prose

**Date:** 2026-05-12 (revised from 2026-05-09 draft)
**Status:** Accepted

**Decision:** Feature #15 (Automated Report Generation) makes no new LLM calls. It reads the structured JSON from `analysis_results` and renders it through format-specific templates per output container.

**Why the original "reuse narrative text" approach was revised:**
- In-app display requires conversational, present-tense prose for a data analyst
- A government ministry PDF/PPTX requires formal language, past tense, and structured section formatting
- Rendering the same string into both containers produces one output wrong in tone or format
- The correct abstraction: LLM produces structured data; rendering layer formats per container

**How it works:**

```
Day 2: LLM produces structured JSON -> stored in analysis_results

Day 3: Report renderer reads stored JSON by session_id
       |
       |-- Render A: React component — casual, present tense, interactive
       +-- Render B: PDF/PPTX template — formal BM/EN, ministry section structure
```

No second LLM call. Rendering difference is in the template layer only.

**Implications for Day 3:**
- Build two rendering outputs: React layout + reportlab/python-pptx template
- MOH report template (Open Item #7) must be received before building the PDF template
- Generic fallback template if MOH template not received in time

---

## ADR-006: Smart Correction Suggestions (#12) extends the existing cleaning pipeline

**Date:** 2026-05-09
**Status:** Accepted

**Decision:** Feature #12 is a downstream ML extension of `outliers.py` / `cleaning/` — not a separate system.

**Why:**
- Cleaning pipeline already produces the signals #12 needs (`flag_status_berat_vs_zscore`, outlier flags)
- #12 adds classification on top: detect decimal shifts, digit transpositions, column swaps; surface reasoning per suggestion
- Row-level editing (accept / reject / override) is a UI concern that does not couple backend modules

**Approach (decide before Day 3):**
- Rule-based heuristics — recommended default, no training data required
- ML classifier — requires labelled corrections data, may not be available

All accepted edits appended to `audit_log` — government traceability requirement.

---

## ADR-007: Explainability is a cross-cutting requirement, not a feature

**Date:** 2026-05-09
**Status:** Accepted

**Decision:** Explainability is not a feature number — it is a requirement baked into every AI module from Day 2 onwards.

**Rule:** Every AI module must surface `reason_bm` and `reason_en` for each decision. A reusable explainability interface is designed before Day 2 starts, and all AI modules (Days 2-5) plug into it.

---

## ADR-008: Schema mapping AI is always-on, not fallback-only

**Date:** 2026-05-09
**Status:** Accepted

**Decision:** AI validates all uploads across all 3 scenarios — not just unknown schemas.

**Scenarios:**
1. **Exact match** — auto-map via `thefuzz`; AI confirms
2. **Unknown schema** — AI generates compatible schema dynamically
3. **Schema drift** — AI maps new columns, infers renames, warns on missing, flags type changes

**Current state:** Only Scenario 1 implemented (Day 1). Scenarios 2 and 3 are Day 5 scope.

---

## ADR-009: Session history and multi-dataset management are architecture, not features

**Date:** 2026-05-09
**Status:** Accepted

| Item | Where |
|------|-------|
| Session & Analysis History | `sessions` + `analysis_results` tables (Day 1) + history panel UI (Day 6) |
| Multi-Dataset Management | `datasets` table (Day 1) + dataset library UI (Day 5) |

---

*Last updated: 2026-05-12*
