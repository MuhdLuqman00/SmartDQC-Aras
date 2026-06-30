import json
import re
from .ollama_client import generate, OllamaError

_ANTI_ECHO_RULES = """Rules (follow exactly):
- Fill EVERY field with real, specific content derived from the dataset context. Never copy the template.
- The "..." in the schema below are placeholders — replace each one. Never output a literal "..." or an empty string.
- GROUNDING: Use ONLY the figures, percentages, dates, years, places and counts that appear in the dataset context above. NEVER invent or estimate any number, date, year, quarter, month, currency amount, family/beneficiary count, district name, state name, or programme/policy name that is not explicitly present. If a specific figure is not given, describe it qualitatively rather than fabricating one.
- The total record count is EXACTLY the number stated in the dataset context. Never state a different total in any field.
- Do not confuse the indicators: stunting, wasting, underweight and overweight are distinct — describe each only with its own figure from the context.
- Never output the words "in English", "in Bahasa Malaysia", "dalam bahasa Malaysia", or any field label as a value.
- "en" must be English prose ONLY; "bm" must be Bahasa Malaysia prose ONLY — never mix languages within a single field. They must be genuine translations of each other, not the same string and not instructions about which language to use.
- Respond with valid JSON only. No markdown, no commentary outside the JSON."""

INSIGHTS_SYSTEM = f"""/no_think
You are SmartDQC, a bilingual (Bahasa Malaysia and English) data quality analyst.
You analyse child nutrition and health data and produce structured JSON insights.
{_ANTI_ECHO_RULES}"""

RECOMMENDATIONS_SYSTEM = f"""/no_think
You are SmartDQC, a bilingual (Bahasa Malaysia and English) public health advisor.
You produce actionable recommendations based on data insights.
{_ANTI_ECHO_RULES}"""


def build_context(eda_result: dict) -> str:
    """Render run_eda()'s report into LLM context.

    Reads the keys run_eda actually emits (top-level total_rows, nested
    data_quality_score / indicators, per-column outliers) — NOT the legacy
    summary/quality/by_negeri shape, which produced empty context and made
    the model reply "no dataset provided".
    """
    parts = []

    rows = eda_result.get("total_rows")
    if rows is not None:
        cols = eda_result.get("total_columns", "N/A")
        src = eda_result.get("source_type", "general")
        parts.append(f"Dataset: {rows} records, {cols} columns, source: {src}")

    dq = eda_result.get("data_quality_score") or {}
    if dq:
        line = f"Data quality score: {dq.get('score', 'N/A')}"
        if dq.get("grade"):
            line += f" (grade {dq['grade']})"
        parts.append(line)

    ic = eda_result.get("ic_validation") or {}
    if ic:
        parts.append(
            f"IC validity: {ic.get('valid', 'N/A')}/{ic.get('total', 'N/A')} "
            f"valid ({ic.get('pct_valid', 'N/A')}%)"
        )

    # KKM indicators are nested: indicators[age_group][indicator] = {label,
    # overall: {pct, n_affected, n_total}, by_negeri: {...}, ...}
    indicators = eda_result.get("indicators") or {}
    ind_lines = []
    if isinstance(indicators, dict):
        for age_key, by_ind in indicators.items():
            if not isinstance(by_ind, dict):
                continue
            for ind_key, ind in by_ind.items():
                if not isinstance(ind, dict):
                    continue
                overall = ind.get("overall") or {}
                pct = overall.get("pct")
                if pct is None:
                    continue
                label = ind.get("label", ind_key)
                ind_lines.append(
                    f"  {label} [{age_key}]: {pct}% "
                    f"({overall.get('n_affected', '?')}/{overall.get('n_total', '?')})"
                )
    if ind_lines:
        parts.append("KKM nutrition indicators:\n" + "\n".join(ind_lines[:20]))

    # run_eda stores outliers as a per-column report; summarise as a total.
    outliers = eda_result.get("outliers") or {}
    if isinstance(outliers, dict) and outliers:
        total_out = sum(
            int(v.get("combined_outliers", 0) or 0)
            for v in outliers.values()
            if isinstance(v, dict)
        )
        cols_checked = [v.get("column", k) for k, v in outliers.items()
                        if isinstance(v, dict)]
        if cols_checked:
            parts.append(
                f"Outliers: {total_out} flagged across columns "
                f"{', '.join(map(str, cols_checked))}"
            )

    bmi = eda_result.get("bmi_consistency") or {}
    if isinstance(bmi, dict):
        scal = {k: v for k, v in bmi.items()
                if isinstance(v, (int, float, str)) and not isinstance(v, bool)}
        if scal:
            parts.append(
                "BMI consistency: "
                + ", ".join(f"{k}={v}" for k, v in list(scal.items())[:4])
            )

    changes = eda_result.get("changes_applied") or []
    if changes:
        parts.append(f"Cleaning steps applied: {len(changes)}")

    return "\n".join(parts) if parts else "No structured context available."


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(raw)


_EMPTY_KEYS = ["who", "what", "when", "where", "why", "how"]

# Placeholder / scaffold values a weak model echoes instead of real content.
# Covers the "..." scaffold (current prompt), blanks, and the older descriptive
# scaffold strings that may still sit in cached narratives — all lower-cased.
_PLACEHOLDER_VALUES = {
    "", "...",
    "short action title in english",
    "tajuk tindakan ringkas dalam bahasa malaysia",
    "detailed recommendation in english",
    "detailed recommendation in bahasa malaysia",
    "cadangan terperinci dalam bahasa malaysia",
    "why this is recommended based on the data",
}


def _is_placeholder(value) -> bool:
    """True if a field holds scaffold/placeholder text rather than real content."""
    return (value or "").strip().lower() in _PLACEHOLDER_VALUES


def _is_echoed(rec: dict) -> bool:
    """A recommendation is junk when its body is placeholder in BOTH languages —
    the body is the substance; without it the card says nothing."""
    return _is_placeholder(rec.get("en")) and _is_placeholder(rec.get("bm"))


def _scrub_bilingual(field) -> dict:
    """Blank out any bm/en value that is scaffold/placeholder text.

    The recommendation guards only cover the recommendation list; a templated
    `executive_summary` or `insights_5w1h` field (e.g. a leaked "...") would
    otherwise render raw. Returns a {bm, en} dict with placeholders cleared."""
    if not isinstance(field, dict):
        return {"bm": "", "en": ""}
    out = dict(field)
    for k in ("bm", "en"):
        if _is_placeholder(out.get(k)):
            out[k] = ""
    return out


def _scrub_insights(parsed: dict) -> dict:
    """Clear placeholder/scaffold text from the summary + 5W1H fields so a model
    slip (or a stale cached narrative built by the old prompt) never renders as
    content. Mirrors the recommendation guard for the narrative body."""
    if not isinstance(parsed, dict):
        return parsed
    if isinstance(parsed.get("executive_summary"), dict):
        parsed["executive_summary"] = _scrub_bilingual(parsed["executive_summary"])
    w5h1 = parsed.get("insights_5w1h")
    if isinstance(w5h1, dict):
        parsed["insights_5w1h"] = {
            k: _scrub_bilingual(v) for k, v in w5h1.items()
        }
    return parsed


def _insights_fallback(message_en: str, message_bm: str, flag: str) -> dict:
    """A clearly-flagged, non-blank insights payload.

    A silent empty narrative renders as 'No narrative produced.' with no
    explanation; this surfaces a visible reason + an explainability flag so
    the user knows to retry rather than seeing a blank panel.
    """
    return {
        "executive_summary": {"bm": message_bm, "en": message_en},
        "insights_5w1h": {d: {"bm": "", "en": ""} for d in _EMPTY_KEYS},
        "explainability": {"flags": [flag]},
    }


def generate_insights(eda_result: dict) -> dict:
    context = build_context(eda_result)
    prompt = f"""Based on this health dataset analysis, produce a JSON response with executive summary and 5W1H insights.

Dataset context:
{context}

Example of the REQUIRED shape, filled with real content (use the actual numbers from the context above, not these):
{{
  "executive_summary": {{
    "en": "The dataset of 1,240 records scored 82 (grade B); stunting affects 11.3% of children aged 0-59 months, concentrated in Kelantan.",
    "bm": "Set data 1,240 rekod mencatat skor 82 (gred B); kekerdilan menjejaskan 11.3% kanak-kanak berumur 0-59 bulan, tertumpu di Kelantan."
  }},
  "insights_5w1h": {{
    "who": {{"en": "Children aged 0-59 months in the surveyed districts.", "bm": "Kanak-kanak berumur 0-59 bulan di daerah yang dikaji."}}
  }}
}}

Now produce the response for THIS dataset using this exact JSON structure (replace every "..." with real content):
{{
  "executive_summary": {{"bm": "...", "en": "..."}},
  "insights_5w1h": {{
    "who":   {{"bm": "...", "en": "..."}},
    "what":  {{"bm": "...", "en": "..."}},
    "when":  {{"bm": "...", "en": "..."}},
    "where": {{"bm": "...", "en": "..."}},
    "why":   {{"bm": "...", "en": "..."}},
    "how":   {{"bm": "...", "en": "..."}}
  }},
  "explainability": {{
    "flags": []
  }}
}}"""

    raw = generate(prompt, system=INSIGHTS_SYSTEM, json_mode=True)
    if not raw or not raw.strip():
        return _insights_fallback(
            "AI insight generation returned no output — the model may be "
            "loading or offline. Please retry in a moment.",
            "Penjanaan wawasan AI tidak menghasilkan output — model mungkin "
            "sedang dimuatkan atau luar talian. Sila cuba semula sebentar lagi.",
            "empty_response",
        )
    try:
        return _scrub_insights(_extract_json(raw))
    except Exception:
        return _insights_fallback(
            "AI insight could not be parsed (model returned non-JSON output). "
            "Please retry.",
            "Wawasan AI tidak dapat dihuraikan (model memberi output bukan JSON). "
            "Sila cuba semula.",
            "parse_error",
        )


def raw_ok(insights: dict) -> bool:
    """True if insights is a real model result (not a flagged fallback)."""
    flags = (insights.get("explainability") or {}).get("flags") or []
    return not any(f in ("empty_response", "parse_error") for f in flags)


def generate_recommendations(eda_result: dict, insights: dict) -> dict:
    context = build_context(eda_result)
    summary_bm = insights.get("executive_summary", {}).get("bm", "")

    prompt = f"""Based on this KKM dataset analysis and insights, produce actionable recommendations in JSON.

Dataset context:
{context}

Key insight: {summary_bm}

Example of ONE filled recommendation (real content — yours must be derived from the context above, not copied):
{{
  "action_en": "Prioritise stunting screening in Kelantan",
  "action_bm": "Utamakan saringan kekerdilan di Kelantan",
  "priority": "high",
  "en": "Deploy mobile screening teams to the 3 districts with stunting above 15% within the next quarter.",
  "bm": "Hantar pasukan saringan bergerak ke 3 daerah dengan kekerdilan melebihi 15% dalam suku tahun berikutnya.",
  "reasoning": "Stunting is the highest indicator at 11.3% and is geographically concentrated."
}}

Now respond with this exact JSON structure (replace every "..." with real content):
{{
  "recommendations": [
    {{
      "action_en": "...",
      "action_bm": "...",
      "priority": "high",
      "bm": "...",
      "en": "...",
      "reasoning_en": "...",
      "reasoning_bm": "..."
    }}
  ]
}}

action_en/en/reasoning_en must be English and action_bm/bm/reasoning_bm must be Bahasa Malaysia — never leave either blank, never reuse the same string for both, never write the word "English" or "Malaysia" as the value. Provide 3-5 recommendations ordered by priority (high/medium/low)."""

    if not raw_ok(insights):
        # Insights failed; don't waste a second model call or imply success.
        return {"recommendations": [], "_rec_flag": "skipped_insights_failed"}

    raw = generate(prompt, system=RECOMMENDATIONS_SYSTEM, json_mode=True)
    if not raw or not raw.strip():
        return {"recommendations": [], "_rec_flag": "empty_response"}
    try:
        parsed = _extract_json(raw)
        recs = parsed.get("recommendations", []) or []
        clean = []
        for r in recs:
            if not isinstance(r, dict) or _is_echoed(r):
                continue
            # Scrub any residual scaffold bits so a surviving rec renders nothing junk.
            for k in ("en", "bm", "action_en", "action_bm", "reasoning_en", "reasoning_bm", "reasoning"):
                if _is_placeholder(r.get(k)):
                    r[k] = ""
            clean.append(r)
        if recs and not clean:
            return {"recommendations": [], "_rec_flag": "placeholder_echo"}
        parsed["recommendations"] = clean
        return parsed
    except Exception:
        return {"recommendations": [], "_rec_flag": "parse_error"}


def generate_narrative(eda_result: dict) -> dict:
    insights = generate_insights(eda_result)
    recommendations = generate_recommendations(eda_result, insights)
    return {**insights, **recommendations}
