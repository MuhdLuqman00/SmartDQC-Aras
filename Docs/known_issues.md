# SmartDQC — Known Issues, Open Items & Risk Register

> Living document. Update as items are resolved or new issues are discovered.
> Last updated: 2026-05-12 (Day 1 complete)

---

## 1. Open Items

| # | Item | Blocking | Status |
|---|------|---------|--------|
| 1 | SLM model selection — confirm VRAM fit on RTX 5060 | Day 2 | Open |
| 2 | Client predefined business rules (full list — only 9 of N known) | Feature #5 | Open |
| 3 | Schema structure for Admin Data (1) and (2) | Post-v1 | Deferred |
| 4 | KKM design assets and branding files | Day 6 | Open — define fallback if not received |
| 5 | Feature count confirmation (16 in doc vs 18 stated verbally) | Product spec | Open |
| 6 | ~~Database choice~~ | ~~Day 1~~ | Resolved — DuckDB (ADR-001) |
| 7 | MOH quarterly report template from client | Day 3 Feature #15 | Open |
| 8 | Traffic-light KPI threshold definitions (On Track / At Risk / Off Track %) | Day 4 Feature #16 | Open |
| 9 | Risk score model architecture — rule-based vs ML vs LLM | Day 4 Feature #11 | Open |
| 10 | 5W1H output schema — exact JSON structure | Day 2 before coding | Draft in ADR-004 — confirm before Day 2 |
| 11 | NLQ sandboxing strategy for pandas exec | Day 2 Feature #13 | Open |
| 12 | Bilingual infrastructure — local transformer vs API + BM domain glossary | Day 2 BM output | Open |
| 13 | KKM staff acceptance test workflow (1-page user journey) | Day 6 final test | Open |
| 14 | Docker Compose networking spec — frontend container hostname | Day 6 | Partial — api + ollama wired; frontend TBD |
| 15 | Remote maintenance mechanism — SSH tunnel vs webhook vs reverse tunnel | Day 6 | Open |

---

## 2. Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|-----------|
| SLM fails VRAM budget on SE's RTX 5060 | Blocks Days 2-5 | Medium | Hard gate on Day 1 — swap model before proceeding |
| Feature #14 complexity overruns Day 5 | May consume full day | High | MVP only: IC + DOB exact/fuzzy; probabilistic matching is post-v1 |
| Client business rules incomplete | Feature #5 rule count may change | Medium | 9 rules hardcoded; architecture is extensible |
| Only 4 of 10 sources schema-mapped | v1 fully covers 4 sources only | Accepted | Remaining 6 are post-v1 |
| AI narrative quality in BM | BM output may need prompt tuning | Medium | Budget 1h Day 2 afternoon for BM iteration |
| No audit trail | Government health data requires traceability | High | `audit_log` table planned for Day 5 |
| UI from scratch underestimated | Day 6 scope risk | High | Begin Day 5 afternoon if integration finishes early |
| Feature #12 no labelled training data | ML classifier blocked | Medium | Rule-based heuristics are safe default |
| MOH report template not received | Cannot build PDF scaffold | Medium | Request immediately; generic fallback template |
| Synthetic historical data not generated | Blocks Days 4-5 | High | Generate 12-month Z-score rollback for 500 synthetic children across 5 districts before Day 4 |

---

## 3. Audit Findings (from 2026-05-09 full audit)

### Cross-Cutting Issues

| Issue | Severity | Status |
|-------|----------|--------|
| ~~Persistence layer under-scoped — no schema, no DB choice~~ | Critical | Resolved — DuckDB, 3 tables live, 3 more planned Day 5 |
| SLM model not selected | Critical | Open |
| Time budget underestimated ~30-50% per day | High | Mitigated — stub persistence if needed; begin UI Day 5 |
| KKM design assets not received — no fallback plan | High | Open — define fallback now |
| Synthetic historical dataset not generated | High | Open |

### Per-Day Critical Gaps

**Day 1 (complete):**
- DuckDB chosen and implemented
- Backend migrated, all ~20 endpoints verified
- Docker api + ollama running
- `zscore_archive`, `entity_linkage`, `audit_log` deferred to Day 5
- SLM model selection still pending

**Day 2 (upcoming):**
- SLM must be a real Docker service wired via HTTP — not loaded in-process
- 5W1H schema must be finalised before writing any LLM code
- Explainability module interface must be designed first (reused Days 3-5)
- NLQ pandas exec must be sandboxed

**Day 3:** Feature #12 architecture (rule-based vs ML) must be decided before coding; MOH template must be in hand; auto-chart selection logic undefined.

**Day 4:** Synthetic data must exist; risk score model spec must be pre-decided; traffic-light thresholds confirmed; blocked if Day 1 persistence or Day 2 LLM incomplete.

**Day 5:** Multi-dataset workflow is greenfield; `entity_linkage` table needed; requires persistence to be complete.

**Day 6:** Define UI fallback now; UI from scratch takes 8-11h — must start Day 5 afternoon; remote maintenance not spec'd.

---

## 4. Post-v1 Scope (do not implement in v1)

- 6 of 10 sources have no schema mappings (NHMS, JKN, Parliament, DDSM, Admin Data 1 and 2)
- Full probabilistic entity matching (Fellegi-Sunter)
- Chatbot multi-turn conversation state and memory
- Complete predefined business rules from client
- Feature count discrepancy (16 documented, 18 verbal) — 2 unconfirmed features
- KKM standalone desktop script (`clean_kkm_data.py`) not integrated into FastAPI backend

---

*Source: `Docs/SmartDQC_Master.md` §9-12*
