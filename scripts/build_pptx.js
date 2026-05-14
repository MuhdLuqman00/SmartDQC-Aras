/**
 * SmartDQC Progress Report — Day 1 & Day 2
 * Palette: Navy #1A3A5C | Teal #0891B2 | Light #F0F7FA | White #FFFFFF
 */
const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "SmartDQC — Development Progress";

// ── PALETTE ──────────────────────────────────────────────
const NAVY   = "1A3A5C";
const TEAL   = "0891B2";
const TEAL2  = "0DAFCE";
const LIGHT  = "F0F7FA";
const WHITE  = "FFFFFF";
const GRAY   = "64748B";
const DARK   = "1E293B";
const GREEN  = "059669";
const AMBER  = "D97706";

const makeShadow = () => ({ type: "outer", blur: 8, offset: 3, angle: 135, color: "000000", opacity: 0.12 });

// ── HELPERS ───────────────────────────────────────────────
function addNavySlide() {
  const s = pres.addSlide();
  s.background = { color: NAVY };
  return s;
}

function addLightSlide() {
  const s = pres.addSlide();
  s.background = { color: LIGHT };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.07, fill: { color: TEAL }, line: { color: TEAL } });
  return s;
}

function card(slide, x, y, w, h, title, body, iconEmoji) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: WHITE },
    line: { color: "E2EEF4", width: 1 },
    shadow: makeShadow(),
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 0.06, h,
    fill: { color: TEAL }, line: { color: TEAL },
  });
  let ty = y + 0.14;
  if (iconEmoji) {
    slide.addText(iconEmoji, { x: x + 0.15, y: ty, w: 0.45, h: 0.35, fontSize: 16, margin: 0 });
    slide.addText(title, { x: x + 0.6, y: ty, w: w - 0.7, h: 0.35, fontSize: 11, bold: true, color: NAVY, margin: 0 });
  } else {
    slide.addText(title, { x: x + 0.15, y: ty, w: w - 0.25, h: 0.35, fontSize: 11, bold: true, color: NAVY, margin: 0 });
  }
  slide.addText(body, { x: x + 0.15, y: y + 0.54, w: w - 0.25, h: h - 0.65, fontSize: 9.5, color: GRAY, margin: 0 });
}

function sectionTag(slide, label) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 0.18, w: 1.5, h: 0.28,
    fill: { color: TEAL }, line: { color: TEAL },
  });
  slide.addText(label, { x: 0.5, y: 0.18, w: 1.5, h: 0.28, fontSize: 8.5, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
}

// ════════════════════════════════════════════════════════
// SLIDE 1 — TITLE
// ════════════════════════════════════════════════════════
{
  const s = addNavySlide();

  s.addShape(pres.shapes.OVAL, { x: 6.5, y: -1.5, w: 6, h: 6, fill: { color: TEAL, transparency: 88 }, line: { color: TEAL, transparency: 88 } });
  s.addShape(pres.shapes.OVAL, { x: 7.5, y: 2.5, w: 3.5, h: 3.5, fill: { color: TEAL2, transparency: 92 }, line: { color: TEAL2, transparency: 92 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.1, w: 10, h: 0.525, fill: { color: TEAL }, line: { color: TEAL } });

  s.addText("SmartDQC", { x: 0.6, y: 0.55, w: 5, h: 0.5, fontSize: 14, bold: true, color: TEAL2, margin: 0 });
  s.addText("Development Progress", { x: 0.6, y: 1.1, w: 7, h: 0.75, fontSize: 36, bold: true, color: WHITE, margin: 0 });
  s.addText("Day 1 & Day 2 Summary", { x: 0.6, y: 1.85, w: 7, h: 0.55, fontSize: 22, color: "A8C8D8", margin: 0 });
  s.addShape(pres.shapes.LINE, { x: 0.6, y: 2.55, w: 3.5, h: 0, line: { color: TEAL, width: 2 } });
  s.addText("KKM Smart Data Quality Check & Cleaning Tool", { x: 0.6, y: 2.75, w: 7.5, h: 0.35, fontSize: 13, color: "8BAFC2", margin: 0 });
  s.addText("Fully Dockerised  ·  On-Premise  ·  Bilingual AI (BM + EN)", { x: 0.6, y: 3.1, w: 7.5, h: 0.35, fontSize: 11, color: "6A8EA0", margin: 0 });
  s.addText("M Telecommunication Sdn Bhd  ·  2026", { x: 0.6, y: 5.15, w: 8, h: 0.4, fontSize: 10, color: WHITE, valign: "middle", margin: 0 });
}

// ════════════════════════════════════════════════════════
// SLIDE 2 — WHAT IS SMARTDQC
// ════════════════════════════════════════════════════════
{
  const s = addLightSlide();
  sectionTag(s, "OVERVIEW");

  s.addText("What is SmartDQC?", { x: 0.5, y: 0.55, w: 9, h: 0.55, fontSize: 26, bold: true, color: NAVY, margin: 0 });
  s.addText("A data quality and cleaning platform built for KKM — runs entirely on a laptop, no internet needed.", {
    x: 0.5, y: 1.12, w: 9, h: 0.4, fontSize: 12, color: GRAY, margin: 0,
  });

  const items = [
    ["📂", "10 Data Sources", "Handles MyVASS, NCDC, KPM, KKM and more — each with source-specific cleaning rules"],
    ["🔒", "Fully Private", "Runs on-premise on client's laptop (RTX 5060). No data leaves the building"],
    ["🐳", "One-Command Deploy", "Docker image on Docker Hub — client runs docker compose up and it's ready"],
    ["🤖", "AI-Powered", "Built-in small language model (Gemma 3 4B) for bilingual insights and Q&A"],
    ["🌐", "Bilingual", "All outputs in Bahasa Malaysia and English — from the data all the way to the AI narrative"],
    ["📊", "Full Analytics", "Cleaning, quality scoring, z-scores, indicators, charts, and export in one tool"],
  ];

  const cw = 2.9, ch = 1.1, gap = 0.12;
  const startX = 0.5, startY = 1.65;
  items.forEach(([icon, title, desc], i) => {
    const col = i % 3;
    const row = Math.floor(i / 3);
    card(s, startX + col * (cw + gap), startY + row * (ch + gap), cw, ch, title, desc, icon);
  });
}

// ════════════════════════════════════════════════════════
// SLIDE 3 — DAY 1 OVERVIEW
// ════════════════════════════════════════════════════════
{
  const s = addNavySlide();
  s.addShape(pres.shapes.OVAL, { x: 7, y: -0.5, w: 5, h: 5, fill: { color: TEAL, transparency: 90 }, line: { color: TEAL, transparency: 90 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.35, h: 5.625, fill: { color: TEAL }, line: { color: TEAL } });

  s.addText("DAY 1", { x: 0.6, y: 0.5, w: 3, h: 0.45, fontSize: 13, bold: true, color: TEAL2, charSpacing: 4, margin: 0 });
  s.addText("Building the\nFoundation", { x: 0.6, y: 0.95, w: 6, h: 1.3, fontSize: 34, bold: true, color: WHITE, margin: 0 });
  s.addText("Goal: New repo running, backend migrated, Docker stack live,\npersistence layer ready, existing features intact.", {
    x: 0.6, y: 2.35, w: 7, h: 0.7, fontSize: 12.5, color: "8BAFC2", margin: 0,
  });

  const stats = [["25+", "API Endpoints\nMigrated"], ["4", "Data Source\nModules"], ["3", "DB Tables\nReady"], ["1", "Docker Image\nPublished"]];
  stats.forEach(([num, label], i) => {
    const x = 0.6 + i * 2.3;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 3.25, w: 2.1, h: 1.7, fill: { color: "FFFFFF", transparency: 92 }, line: { color: TEAL, width: 1 } });
    s.addText(num, { x, y: 3.35, w: 2.1, h: 0.65, fontSize: 30, bold: true, color: TEAL2, align: "center", margin: 0 });
    s.addText(label, { x, y: 4.0, w: 2.1, h: 0.75, fontSize: 9.5, color: "A8C8D8", align: "center", margin: 0 });
  });
}

// ════════════════════════════════════════════════════════
// SLIDE 4 — DAY 1 DETAIL
// ════════════════════════════════════════════════════════
{
  const s = addLightSlide();
  sectionTag(s, "DAY 1");

  s.addText("What Was Built", { x: 0.5, y: 0.55, w: 9, h: 0.5, fontSize: 24, bold: true, color: NAVY, margin: 0 });

  const items = [
    ["🗂️", "Backend Migration", "All 21 Python modules moved from the old data-cleaning-tool into the new SmartDQC repo and restructured into clean namespaces (eda/, cleaning/, export/, db/, utils/)"],
    ["🧹", "Source-Specific Cleaners", "4 dedicated modules: ncdc.py (WIDE→LONG reshape), kpm.py (school-age only), myvass.py (Bahagian derivation, IC gender fallback), kkm.py (7yo BMI thresholds, 2024 date-forcing)"],
    ["🗄️", "DuckDB Persistence", "3 tables auto-created on startup: datasets, sessions, analysis_results. Chosen over PostgreSQL (too heavy) and SQLite (not analytical-first)"],
    ["🐳", "Docker Stack", "3 containers: api + ollama + ollama-init. Model auto-pulled on first run. WHO z-score Excel files baked into image — client never needs to manage them manually"],
    ["☁️", "Published to Docker Hub", "Image luqmanzulkefli/smartdqc-api:latest pushed. Client only needs docker-compose.yml to run the full app. Source code never exposed"],
    ["✅", "All Features Verified", "Smoke test passed: /health, /schema, DB tables confirmed. All 25+ existing endpoints responding correctly"],
  ];

  const cw = 4.55, ch = 1.05, gap = 0.12;
  items.forEach(([icon, title, desc], i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    card(s, 0.5 + col * (cw + gap), 1.2 + row * (ch + gap), cw, ch, title, desc, icon);
  });
}

// ════════════════════════════════════════════════════════
// SLIDE 5 — DAY 2 OVERVIEW
// ════════════════════════════════════════════════════════
{
  const s = addNavySlide();
  s.addShape(pres.shapes.OVAL, { x: 7, y: -0.5, w: 5, h: 5, fill: { color: TEAL, transparency: 90 }, line: { color: TEAL, transparency: 90 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.35, h: 5.625, fill: { color: TEAL }, line: { color: TEAL } });

  s.addText("DAY 2", { x: 0.6, y: 0.5, w: 3, h: 0.45, fontSize: 13, bold: true, color: TEAL2, charSpacing: 4, margin: 0 });
  s.addText("Adding Artificial\nIntelligence", { x: 0.6, y: 0.95, w: 6.5, h: 1.3, fontSize: 34, bold: true, color: WHITE, margin: 0 });
  s.addText("Goal: LLM wired into the pipeline, bilingual BM/English output,\nNLQ working end-to-end.", {
    x: 0.6, y: 2.35, w: 7, h: 0.7, fontSize: 12.5, color: "8BAFC2", margin: 0,
  });

  const features = [["#9", "AI Insight\nGeneration"], ["#10", "Smart\nRecommendations"], ["#13", "Natural Language\nQuerying"]];
  features.forEach(([num, label], i) => {
    const x = 0.6 + i * 3.05;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 3.2, w: 2.8, h: 1.85, fill: { color: "FFFFFF", transparency: 90 }, line: { color: TEAL, width: 1 } });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 3.2, w: 2.8, h: 0.42, fill: { color: TEAL, transparency: 20 }, line: { color: TEAL } });
    s.addText(`Feature ${num}`, { x, y: 3.2, w: 2.8, h: 0.42, fontSize: 9, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(label, { x, y: 3.65, w: 2.8, h: 1.3, fontSize: 16, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
  });
}

// ════════════════════════════════════════════════════════
// SLIDE 6 — AI NARRATIVE (5W1H)
// ════════════════════════════════════════════════════════
{
  const s = addLightSlide();
  sectionTag(s, "DAY 2 · FEATURES #9 + #10");

  s.addText("AI Narrative: Insights & Recommendations", { x: 0.5, y: 0.55, w: 9, h: 0.5, fontSize: 22, bold: true, color: NAVY, margin: 0 });
  s.addText("After every data analysis, SmartDQC automatically generates a structured report in Bahasa Malaysia and English.", {
    x: 0.5, y: 1.08, w: 9, h: 0.35, fontSize: 11, color: GRAY, margin: 0,
  });

  const wh = [
    ["WHO", "Which children, districts, or states are most affected"],
    ["WHAT", "Key findings — stunting rates, quality scores, outlier counts"],
    ["WHEN", "Time period of the data and any trends observed"],
    ["WHERE", "Geographic breakdown by negeri and daerah"],
    ["WHY", "Root causes inferred from the data patterns"],
    ["HOW", "Methodology — WHO standards, indicators used"],
  ];

  const bw = 1.48, bh = 1.5, gap = 0.1;
  wh.forEach(([label, desc], i) => {
    const x = 0.5 + i * (bw + gap);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.55, w: bw, h: bh, fill: { color: WHITE }, line: { color: "D0E8F0", width: 1 }, shadow: makeShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.55, w: bw, h: 0.42, fill: { color: NAVY }, line: { color: NAVY } });
    s.addText(label, { x, y: 1.55, w: bw, h: 0.42, fontSize: 15, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(desc, { x: x + 0.08, y: 2.02, w: bw - 0.16, h: 1.0, fontSize: 8.5, color: GRAY, margin: 0 });
  });

  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 3.18, w: 4.2, h: 0.85, fill: { color: NAVY }, line: { color: NAVY }, shadow: makeShadow() });
  s.addText("Call 1 — Insights (Feature #9)", { x: 0.5, y: 3.18, w: 4.2, h: 0.35, fontSize: 10, bold: true, color: TEAL2, align: "center", valign: "middle", margin: 0 });
  s.addText("Executive summary · 5W1H · Explainability flags", { x: 0.5, y: 3.53, w: 4.2, h: 0.4, fontSize: 9, color: "A8C8D8", align: "center", margin: 0 });

  s.addText("→", { x: 4.77, y: 3.38, w: 0.5, h: 0.4, fontSize: 18, bold: true, color: TEAL, align: "center", margin: 0 });

  s.addShape(pres.shapes.RECTANGLE, { x: 5.3, y: 3.18, w: 4.2, h: 0.85, fill: { color: NAVY }, line: { color: NAVY }, shadow: makeShadow() });
  s.addText("Call 2 — Recommendations (Feature #10)", { x: 5.3, y: 3.18, w: 4.2, h: 0.35, fontSize: 10, bold: true, color: TEAL2, align: "center", valign: "middle", margin: 0 });
  s.addText("High / Medium / Low priority · Reasoning included", { x: 5.3, y: 3.53, w: 4.2, h: 0.4, fontSize: 9, color: "A8C8D8", align: "center", margin: 0 });

  s.addText("Two focused LLM calls — better quality than one large call for small models", { x: 0.5, y: 4.15, w: 9, h: 0.3, fontSize: 9.5, color: GRAY, align: "center", italic: true, margin: 0 });
}

// ════════════════════════════════════════════════════════
// SLIDE 7 — NLQ
// ════════════════════════════════════════════════════════
{
  const s = addLightSlide();
  sectionTag(s, "DAY 2 · FEATURE #13");

  s.addText("Natural Language Querying (NLQ)", { x: 0.5, y: 0.55, w: 9, h: 0.5, fontSize: 22, bold: true, color: NAVY, margin: 0 });
  s.addText("Ask questions about the data in plain BM or English — SmartDQC answers automatically.", {
    x: 0.5, y: 1.08, w: 9, h: 0.35, fontSize: 11, color: GRAY, margin: 0,
  });

  const steps = [
    [NAVY, WHITE, "1", "User types a\nquestion", "(BM or English)"],
    [TEAL, WHITE, "2", "LLM generates\npandas code", "to query the data"],
    [NAVY, WHITE, "3", "Secure sandbox\nexecutes code", "No file access allowed"],
    [TEAL, WHITE, "4", "LLM writes a\nplain answer", "in BM + English"],
  ];

  steps.forEach(([bg, fg, num, title, sub], i) => {
    const x = 0.5 + i * 2.3;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.55, w: 2.1, h: 1.75, fill: { color: bg }, line: { color: bg }, shadow: makeShadow() });
    s.addText(num, { x, y: 1.65, w: 2.1, h: 0.5, fontSize: 22, bold: true, color: fg, align: "center", margin: 0 });
    s.addText(title, { x, y: 2.15, w: 2.1, h: 0.65, fontSize: 11, bold: true, color: fg, align: "center", margin: 0 });
    s.addText(sub, { x, y: 2.8, w: 2.1, h: 0.4, fontSize: 8.5, color: i % 2 === 0 ? TEAL2 : "CDEEF5", align: "center", margin: 0 });
    if (i < steps.length - 1) {
      s.addText("→", { x: x + 2.1, y: 2.2, w: 0.2, h: 0.35, fontSize: 16, bold: true, color: TEAL, align: "center", margin: 0 });
    }
  });

  s.addText("Sample Questions", { x: 0.5, y: 3.45, w: 9, h: 0.32, fontSize: 11, bold: true, color: NAVY, margin: 0 });

  const queries = [
    ["BM", "Berapa peratus kanak-kanak yang kekurangan zat makanan?"],
    ["EN", "Which district has the highest stunting rate?"],
    ["BM", "Senaraikan 5 daerah teratas dengan kadar WAZ terendah"],
    ["EN", "How many records have missing IC numbers?"],
  ];

  queries.forEach(([lang, q], i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    const x = 0.5 + col * 4.75;
    const y = 3.85 + row * 0.45;
    const tagColor = lang === "BM" ? TEAL : GREEN;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.42, h: 0.3, fill: { color: tagColor }, line: { color: tagColor } });
    s.addText(lang, { x, y, w: 0.42, h: 0.3, fontSize: 8, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addText(q, { x: x + 0.48, y, w: 4.15, h: 0.3, fontSize: 9.5, color: DARK, valign: "middle", margin: 0 });
  });
}

// ════════════════════════════════════════════════════════
// SLIDE 8 — ARCHITECTURE
// ════════════════════════════════════════════════════════
{
  const s = addLightSlide();
  sectionTag(s, "ARCHITECTURE");

  s.addText("How It All Fits Together", { x: 0.5, y: 0.55, w: 9, h: 0.5, fontSize: 24, bold: true, color: NAVY, margin: 0 });

  const layers = [
    [NAVY, WHITE, "Frontend (Day 6)", "React · KKM Branding · Light/Dark Mode · Chatbot · Dataset Library"],
    [TEAL, WHITE, "FastAPI Backend", "25+ Endpoints · EDA Pipeline · Cleaning Pipeline · AI Module (backend/ai/)"],
    [DARK, WHITE, "AI Layer (Day 2)", "ollama_client.py · narrative.py · nlq.py · sandbox.py"],
    ["2C5F7E", WHITE, "Ollama + Gemma 3 4B", "Runs on GPU · Auto-pulled on first start · Swap model via env var only"],
    ["1E3A52", "A8C8D8", "DuckDB Persistence", "datasets · sessions · analysis_results — single portable .duckdb file"],
  ];

  layers.forEach(([bg, fg, title, desc], i) => {
    const y = 1.2 + i * 0.82;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y, w: 9, h: 0.72, fill: { color: bg }, line: { color: bg }, shadow: makeShadow() });
    s.addText(title, { x: 0.65, y, w: 2.8, h: 0.72, fontSize: 11, bold: true, color: fg, valign: "middle", margin: 0 });
    s.addShape(pres.shapes.LINE, { x: 3.4, y: y + 0.1, w: 0, h: 0.52, line: { color: fg, width: 1, transparency: 60 } });
    s.addText(desc, { x: 3.55, y, w: 5.8, h: 0.72, fontSize: 10, color: fg, valign: "middle", margin: 0 });
  });
}

// ════════════════════════════════════════════════════════
// SLIDE 9 — WHAT'S NEXT
// ════════════════════════════════════════════════════════
{
  const s = addLightSlide();
  sectionTag(s, "ROADMAP");

  s.addText("What's Next", { x: 0.5, y: 0.55, w: 9, h: 0.5, fontSize: 24, bold: true, color: NAVY, margin: 0 });

  const days = [
    ["Day 3", "Data Correction + Reports", GREEN, ["ML-based correction suggestions on top of existing outlier detection", "One-click PDF/PPTX report export (reuses Day 2 AI narratives — no new LLM calls)"]],
    ["Day 4", "Risk Scoring + KPI Dashboard", AMBER, ["Predictive risk scoring per child and per district", "Traffic-light dashboard vs national KPIs and WHO benchmarks"]],
    ["Day 5", "Entity Matching + Schema AI", TEAL, ["Cross-dataset entity resolution using IC/NRIC matching", "AI-powered column mapping for unknown and drifted schemas"]],
    ["Day 6", "Full UI + Final Testing", NAVY, ["React frontend: KKM branding, dark/light mode, chatbot wired to NLQ", "End-to-end test on SE's laptop — full user journey verified"]],
  ];

  days.forEach(([day, title, color, bullets], i) => {
    const y = 1.18 + i * 1.05;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y, w: 0.85, h: 0.9, fill: { color }, line: { color }, shadow: makeShadow() });
    s.addText(day, { x: 0.5, y, w: 0.85, h: 0.9, fontSize: 11, bold: true, color: WHITE, align: "center", valign: "middle", margin: 0 });
    s.addShape(pres.shapes.RECTANGLE, { x: 1.45, y, w: 8.05, h: 0.9, fill: { color: WHITE }, line: { color: "E2EEF4", width: 1 }, shadow: makeShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x: 1.45, y, w: 0.06, h: 0.9, fill: { color }, line: { color } });
    s.addText(title, { x: 1.62, y: y + 0.06, w: 7.7, h: 0.32, fontSize: 11, bold: true, color: NAVY, margin: 0 });
    s.addText(bullets.join("    ·    "), { x: 1.62, y: y + 0.42, w: 7.7, h: 0.38, fontSize: 9, color: GRAY, margin: 0 });
  });
}

// ════════════════════════════════════════════════════════
// SLIDE 10 — CLOSING
// ════════════════════════════════════════════════════════
{
  const s = addNavySlide();
  s.addShape(pres.shapes.OVAL, { x: 6, y: -1, w: 6, h: 6, fill: { color: TEAL, transparency: 88 }, line: { color: TEAL, transparency: 88 } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.1, w: 10, h: 0.525, fill: { color: TEAL }, line: { color: TEAL } });
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.35, h: 5.625, fill: { color: TEAL }, line: { color: TEAL } });

  s.addText("SmartDQC", { x: 0.6, y: 0.9, w: 5, h: 0.45, fontSize: 14, bold: true, color: TEAL2, margin: 0 });
  s.addText("Day 1 ✓  Day 2 ✓", { x: 0.6, y: 1.4, w: 7, h: 0.65, fontSize: 30, bold: true, color: WHITE, margin: 0 });
  s.addShape(pres.shapes.LINE, { x: 0.6, y: 2.15, w: 3, h: 0, line: { color: TEAL, width: 2 } });

  const done = [
    "Backend migrated — all 25+ endpoints live",
    "Docker image published to Docker Hub",
    "AI narrative live — bilingual 5W1H + recommendations",
    "NLQ endpoint live — BM/English questions answered",
    "Gemma 3 4B confirmed on target GPU hardware",
  ];

  done.forEach((item, i) => {
    s.addShape(pres.shapes.OVAL, { x: 0.6, y: 2.35 + i * 0.45, w: 0.22, h: 0.22, fill: { color: TEAL }, line: { color: TEAL } });
    s.addText(item, { x: 0.95, y: 2.3 + i * 0.45, w: 7.5, h: 0.35, fontSize: 11, color: "A8C8D8", valign: "middle", margin: 0 });
  });

  s.addText("M Telecommunication Sdn Bhd  ·  2026", { x: 0.6, y: 5.15, w: 8, h: 0.4, fontSize: 10, color: WHITE, valign: "middle", margin: 0 });
}

// ── WRITE FILE ────────────────────────────────────────────
const outPath = "SmartDQC_Progress_Day1_Day2.pptx";
pres.writeFile({ fileName: outPath }).then(() => {
  console.log(`Created: ${outPath}`);
});
