# SmartDQC — UI Specification
### Internal Reference Document

---

## 1. Design Direction

| Attribute | Direction |
|-----------|-----------|
| Colour Scheme | KKM-inspired — modernised navy and blue, not a direct copy of their portal |
| Feel | Clean, simple, aesthetically pleasing — dashboard-quality, not government-portal |
| Modes | Light and Dark mode |
| Target Users | KKM staff — non-technical to semi-technical |
| Language | Bahasa Malaysia and English |

### Colour Palette

The palette is anchored in KKM's official website colours (dark navy, medium blue, light steel blue) but modernised for a clean, professional data platform aesthetic. The navy gives it identity and authority; the brighter accent blue drives interactivity; light steel blue is used sparingly for depth without clutter.

#### Core
| Role | Name | Light Mode | Dark Mode |
|------|------|------------|-----------|
| Brand / Primary | KKM Navy | `#1B2A4A` | `#1B2A4A` |
| Interactive / Accent | Bright Blue | `#1D6FE8` | `#3B8BF5` |
| Subtle Highlight | Steel Blue | `#B8CCE4` | `#2A3F5F` |

#### Surfaces & Backgrounds
| Role | Light Mode | Dark Mode |
|------|------------|-----------|
| Page Background | `#F4F6F9` | `#0F1923` |
| Surface (cards, panels) | `#FFFFFF` | `#1A2633` |
| Surface Elevated | `#EEF2F7` | `#233043` |
| Border / Divider | `#D6E0ED` | `#2E3F55` |

#### Typography
| Role | Light Mode | Dark Mode |
|------|------------|-----------|
| Primary Text | `#1B2A4A` | `#E8EDF2` |
| Secondary Text | `#5A6E8C` | `#8DA4BF` |
| Muted / Placeholder | `#9EB3CC` | `#4A6080` |

#### Status Colours
| Role | Colour |
|------|--------|
| Success | `#22C55E` |
| Warning | `#F59E0B` |
| Danger / Critical | `#EF4444` |
| Info | `#3B82F6` |
| Neutral | `#94A3B8` |

#### Usage Notes
- **Navy `#1B2A4A`** — sidebar background, top nav, section headers, primary buttons
- **Bright Blue `#1D6FE8`** — CTA buttons, links, active nav states, chart primary series, progress indicators
- **Steel Blue `#B8CCE4`** — badge backgrounds, hover states, subtle card accents, secondary chart series
- **Dark mode** — flip surfaces to dark navy/charcoal; keep bright blue accent slightly lighter (`#3B8BF5`) for contrast on dark backgrounds
- **Red is logo-only** — do not use as a UI brand colour; reserved strictly for Danger/Critical status indicators

---

## 2. Pages & Layout

---

### 2.1 Landing / Login Page
**Purpose:** Entry point into the platform.

**Layout:**
- Full screen split — left panel with KKM branding/logo, right panel with login form
- Subtle animated background (soft gradient using Navy `#1B2A4A` → Bright Blue `#1D6FE8`, or a low-opacity particle effect)
- Light/Dark mode toggle visible on landing

**Elements:**
- KKM logo + SmartDQC platform name
- Username / Password fields
- Login button
- Language toggle (BM / EN)
- Light/Dark toggle

---

### 2.2 Dashboard (Home)
**Purpose:** High-level overview after login. First thing the user sees.

**Layout:**
- Top navigation bar (persistent across all pages)
- Left sidebar navigation
- Main content area with KPI cards + charts

**Elements:**
- **KPI Cards (top row):**
  - Total Records Uploaded
  - Overall Data Quality Score (%)
  - Total Flagged Issues
  - Active Alerts / Threshold Breaches
- **Recent Activity Feed** — last uploads, last quality checks run, recent cleaning actions
- **Quick Action Buttons** — Upload Dataset, Run Quality Check, Generate Report
- **Summary Chart** — Quality score trend over time (line chart)
- **Alert Banner** — if any threshold is breached, show prominently at top

---

### 2.3 Data Upload
**Purpose:** Entry point for all dataset ingestion.

**Layout:**
- Guided step-by-step wizard (Step 1 of N format)
- Progress indicator at top

**Steps / Flow:**
1. **Select Data Source** — dropdown to select which source:
   myVASS, CCMS, KPM, NCDC, NHMS, JKN, Parliament, DDSM, Admin Data (1), Admin Data (2)
   *v1 has full schema mappings for 4 sources only (myVASS, CCMS, KPM, NCDC). Remaining 6 are post-v1.*
2. **Upload File** — drag and drop zone, supports CSV / XLSX / XLS
   - **MyVASS multi-file upload:** if myVASS is selected, allow uploading multiple files at once. Backend automatically merges them (concatenate → deduplicate by IC keeping latest DOSE_DATE → remove rows with any null cell) before processing. Show a merge summary before proceeding: files merged, duplicates removed, null rows removed, final record count.
3. **Schema Detection** — AI always-on validation layer runs against every upload:
   - ✅ Scenario 1 — Exact match: schema recognised, auto-mapped to known source
   - ⚠️ Scenario 2 — Unknown schema: AI dynamically generates a compatible schema proposal
   - 🔄 Scenario 3 — Schema drift (most common real-world case): known schema but columns added/renamed/type-changed; AI contextually maps new columns, infers renames by content/type similarity, warns on missing expected columns, flags type changes
   User reviews and confirms all three scenarios before proceeding.
4. **Column Mapping Review** — table showing detected columns vs expected schema fields, drag-drop reassignment, warnings for unmapped critical fields
5. **Confirm & Upload** — summary of what will be ingested, confirm button

---

### 2.4 Data Explorer
**Purpose:** View, browse, and edit uploaded datasets at row level.

**Layout:**
- Full-width data table
- Filter/search bar above the table
- Side panel for row detail view

**Elements:**
- Paginated data table with sortable columns
- Colour-coded rows — flagged rows highlighted (`#F59E0B` background = warning, `#EF4444` background = critical)
- Inline row editing capability — click any cell to edit value directly in the table; changes saved on blur/Enter
- Row-level action menu (Edit, Flag, Delete, View AI Analysis)
- All manual edits logged to audit history (who changed what, from/to values, timestamp)
- Column filter chips
- Search by any field
- Export current view button

---

### 2.5 Data Quality Check
**Purpose:** Run and view results of quality checks against business and DQ rules.

**Layout:**
- Left: Rule set selector and configuration
- Right: Results panel

**Elements:**
- Toggle between viewing **Business Rules** vs **DQ Rules** vs **Combined**
- **Run Quality Check** button
- **Quality Scorecard** — overall score (0–100), grade (A–D), breakdown by dimension. *For KPM data, scorecard displays BMI category distribution (Kurus/Normal/Berlebihan/Obes) rather than WHO z-score indicators.*
- **Rule Results Table** — each rule, pass/fail status, number of records affected, severity
- **Drill Down** — click any failed rule to see the affected records
- **Export quality report** — two formats:
  - **PDF / in-app** — standard quality scorecard
  - **Excel (9-tab)** — auto-generated structured report: Executive Summary, Cleaning Rules Applied, Records Dropped, plus WAZ/HAZ/BAZ pivot tables broken down by Negeri and Daerah (detailed count + %, combined count + %). Available after cleaning is run. (*Note: KPM data exports BMI category breakdown instead of z-score pivots — see §2.6.*)

---

### 2.6 Data Cleaning
**Purpose:** Apply cleaning operations to the dataset.

**Layout:**
- Left panel: Cleaning operations menu
- Right panel: Preview of changes before applying

**Elements:**
- **Operation Types:**
  - Imputation (select column, select strategy — mean/median/mode/custom)
  - Remove Records (filter-based removal)
  - Add / Edit Records (manual additions)
  - Row Level Editing (bulk or individual) — inline cell editing per row, multi-row bulk select + apply, changes previewed before commit, all edits logged to audit history
  - Calculations / Computations (derived field creation)
- **Preview Panel** — shows before/after for selected operation
- **Apply** / **Discard** buttons
- **Cleaning History Log** — list of all operations applied in this session with undo capability

> **Source-type note:** Cleaning output varies by data source. MyVASS and NCDC produce WHO z-score outputs (WAZ/HAZ/BAZ with Malay-language status labels). KPM data is school-age (6–8 years) and produces BMI-based classification instead: Kurus / Normal / Berlebihan Berat Badan / Obes — not WHO z-scores. The cleaning result display and quality metrics must adapt terminology accordingly per source.

- **AI Correction Suggestions (Feature #12)** — ML layer on top of outlier detection:
  - Detects: decimal shifts (e.g. 123.4 → 12.34), digit transpositions, column swaps
  - Each card shows: affected field, current value, suggested correction, confidence score, reason (BM/EN)
  - Inline explainability: why this record was flagged
  - Accept / Reject / Modify — accepted corrections logged in cleaning history

---

### 2.7 AI — Smart Analysis
**Purpose:** Run and view AI-powered row-level analysis using 5W1H framework.

**Layout:**
- Top: Run analysis controls (select dataset, select scope — full / filtered rows)
- Below: Results as cards or expandable rows

**Elements:**
- **Run Analysis** button
- **Analysis Results** — per record or per group, structured as:
  - Who / What / When / Where / Why / How breakdown
  - Confidence score per analysis
- **Filter by dimension** — e.g. show only records where "Why" is flagged
- **Export Analysis** button
- Language toggle for output (BM / EN)

---

### 2.8 AI — Predictive Analytics
**Purpose:** View trends, risk mappings, and threshold alerts.

**Layout:**
- Tab-based: Trends | Geo Mapping | Alerts | Benchmarking

**Trends Tab:**
- Line/bar charts per indicator over time
- Filter by state / district / demographic
- AI narrative below each chart explaining the trend

**Geo Mapping Tab:**
- Interactive map of Malaysia
- Colour-coded by risk level per district/state
- Click district to see detail panel

**Alerts Tab:**
- List of active threshold alerts
- Each alert shows: indicator, location, current value, threshold value, severity
- Mark as reviewed / snooze functionality
- Alert history

**Benchmarking Tab:**
- District/state performance vs national KPIs + WHO targets + historical self
- Traffic-light per metric: 🟢 On Track / 🟡 At Risk / 🔴 Off Track
- AI trajectory narrative per district/state (BM + English)
- KPI thresholds configurable via Settings > Threshold Configuration
- **Senarai Kanak-kanak Berisiko** — exportable high-risk child list per district

---

### 2.9 AI — Explainability Panel (Cross-Cutting Component)
**Purpose:** Surface plain-language reasoning for any AI decision across the platform.

**Scope:** Explainability is a cross-cutting requirement — every AI module surfaces inline reasoning without requiring navigation here. This dedicated panel provides the deep-dive view with full factor breakdown. Inline explainability notes appear directly in §2.6 (Cleaning Suggestions), §2.7 (Smart Analysis), and §2.8 (Predictive Analytics) without opening this panel.

**Layout:**
- NOT a standalone nav item — linked from any AI output (quality check, smart analysis, predictive)
- Opens as a side panel or modal

**Elements:**
- Plain-language explanation of why the AI made a specific decision
- Confidence score
- Factors that influenced the decision (listed by weight)
- "What if" toggle — e.g. what would change if this value was corrected
- Language toggle (BM / EN)

---

### 2.10 Reports
**Purpose:** Generate and download formal reports.

**Layout:**
- Report type selector
- Configuration options
- Preview pane
- Download button

**Elements:**
- Select report type: Quality Report / Analysis Report / Predictive Report / Full Report
- Select scope: date range, data source, state/district filter
- **Generate Preview** button — renders report in-app
- AI-written executive summary section (editable before export)
- Export format: PDF / PPTX / Excel
  - **Excel (9-tab quality report)** — available for myVASS and NCDC sources after cleaning; contains Executive Summary, Cleaning Rules, Records Dropped, and WAZ/HAZ/BAZ × Negeri/Daerah pivot tables. For KPM, contains BMI category breakdown instead of z-score tabs.
- Report follows KKM quarterly reporting format

---

### 2.11 Chatbot
**Purpose:** Conversational interface to query the data and AI models.

**Layout:**
- Right-side slide-in panel or dedicated full page
- Chat bubble UI

**Backend:** Feature #13 — Natural Language Querying: user input (BM/English) → LLM → sandboxed pandas execution → answer + auto-generated chart where relevant. (Sandboxed: no arbitrary file system access from NLQ queries.)

**Elements:**
- Chat input field (BM / EN)
- Message history
- Auto-suggested queries:
  - "Berapa % stunted di Sabah Q1?"
  - "Tunjukkan trend wasting 2023 vs 2024 bagi Selangor"
  - "Senaraikan daerah yang melebihi ambang underweight nasional"
- Responses include text + auto-generated charts where relevant
- Context-aware — knows which dataset is currently loaded
- Clear conversation button
- Copy response button

---

### 2.12 History
**Purpose:** Full log of all past sessions, uploads, analyses, and cleaning operations.

**Layout:**
- Timeline or table view
- Filter by type and date

**Elements:**
- Session entries: date, user, action type, dataset, status
- Click to replay or view results of any past session
- Filter by: Upload / Quality Check / Cleaning / Row Edit / Analysis / Report
- Search by dataset name or date
- Delete history entry option

---

### 2.13 Dataset Library
**Purpose:** Browse all past uploads and launch multi-dataset comparative analysis.

**Layout:**
- Card grid or table of all uploaded datasets
- Filter/sort by source, date, quality score

**Elements:**
- Each dataset card shows: source name, upload date, record count, overall quality score, status badge
- **Select mode** — checkbox multi-select to pick 2+ datasets
- **Compare Selected** button — triggers combined analysis workflow
- Combined analysis results:
  - Side-by-side quality comparison
  - Trend deltas (same source, different periods)
  - Cross-source entity match summary (Feature #14)
  - AI comparative narrative (BM + English)
- **Export Comparative Report** button
- Link to full session detail (→ History log entry)

---

### 2.14 Settings
**Purpose:** Platform configuration and administration.

**Sections:**
- **User Management** — add/edit/remove users, assign roles (Admin / Analyst / Viewer)
- **Business Rules Editor** — view, add, edit, disable client-provided business rules
- **DQ Rules Editor** — view, add, edit, disable development-defined quality rules
- **Threshold Configuration** — set and adjust alert thresholds per indicator
- **Model Settings** — select active SLM, view model info, toggle explainability on/off
- **Appearance** — Light / Dark mode toggle, language preference
- **About** — platform version, build info

---

## 3. Navigation Structure

```
SmartDQC
├── Dashboard
├── Data
│   ├── Upload Dataset
│   ├── Data Explorer
│   ├── Data Quality Check
│   └── Data Cleaning
├── AI
│   ├── Smart Analysis (5W1H)
│   └── Predictive Analytics
│       ├── Trends
│       ├── Geo Mapping
│       ├── Alerts
│       └── Benchmarking
├── Reports
├── Dataset Library
├── History
├── Chatbot (persistent panel)
└── Settings
```

> Explainability is not a nav destination — it opens as a side panel from any AI output across the platform.

---

## 4. Persistent UI Elements

These elements appear across all pages:

- **Top Navigation Bar** — Logo, page title, notifications bell, user avatar, light/dark toggle
- **Left Sidebar** — Main navigation links, collapsible
- **Notification / Alert Banner** — Appears at top when threshold is breached
- **Chatbot Toggle Button** — Floating button (bottom-right) to open chatbot panel at any time

---

## 5. User Flow — Primary Journey

**Primary Journey (single dataset):**
```
Login
  └── Dashboard
        └── Upload Dataset (wizard)
              └── Schema Mapping Review
                    └── Data Explorer
                          └── Data Quality Check
                                └── Data Cleaning
                                      └── Smart Analysis (5W1H)
                                            └── Predictive Analytics
                                                  └── Generate Report
                                                        └── Export / Download
```

**Multi-Dataset Journey:**
```
Dataset Library
  └── Select 2+ Datasets
        └── Compare Selected
              ├── Side-by-side Quality Comparison
              ├── Trend Deltas (same source, different periods)
              ├── Entity Resolution Summary (Feature #14)
              └── Export Comparative Report
```

---

## 6. Open Items

| # | Item | Blocking |
|---|------|---------|
| 1 | Obtain official KKM logo assets — fallback approved: KKM colours + placeholder logo | Day 6 UI |
| 2 | Confirm language default (BM or EN) and switching behaviour | All pages |
| 3 | Decide on chatbot placement — floating panel vs dedicated page | §2.11 |
| 4 | Confirm user roles and permission matrix with client | §2.14 Settings |
| 5 | Wireframes to be designed separately based on this spec | Design phase |
| 6 | Traffic-light KPI threshold definitions (On Track / At Risk / Off Track values) | §2.8 Benchmarking |
| 7 | MOH quarterly report template from client | §2.10 Reports |
| 8 | Full KKM staff workflow definition for SE acceptance test | Day 6 final test |
| 9 | Feature count confirmation — 16 documented vs 18 verbal | Product spec |

---

*Internal reference only. UI spec based on project briefing. Subject to change during design phase.*
