import json
import re
from .ollama_client import generate, OllamaError

INSIGHTS_SYSTEM = """You are SmartDQC, a bilingual (Bahasa Malaysia and English) data quality analyst for KKM (Kementerian Kesihatan Malaysia).
You analyse child nutrition and health data and produce structured JSON insights.
Always respond with valid JSON only. No markdown, no explanation outside the JSON."""

RECOMMENDATIONS_SYSTEM = """You are SmartDQC, a bilingual (Bahasa Malaysia and English) public health advisor for KKM.
You produce actionable recommendations based on data insights.
Always respond with valid JSON only. No markdown, no explanation outside the JSON."""


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
        src = eda_result.get("source_type", "unknown")
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
    prompt = f"""Based on this KKM health dataset analysis, produce a JSON response with executive summary and 5W1H insights.

Dataset context:
{context}

Respond with this exact JSON structure:
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
        return _extract_json(raw)
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

Respond with this exact JSON structure:
{{
  "recommendations": [
    {{
      "action": "short action title",
      "priority": "high",
      "bm": "detailed recommendation in Bahasa Malaysia",
      "en": "detailed recommendation in English",
      "reasoning": "why this is recommended based on the data"
    }}
  ]
}}

Provide 3-5 recommendations ordered by priority (high/medium/low)."""

    if not raw_ok(insights):
        # Insights failed; don't waste a second model call or imply success.
        return {"recommendations": [], "_rec_flag": "skipped_insights_failed"}

    raw = generate(prompt, system=RECOMMENDATIONS_SYSTEM, json_mode=True)
    if not raw or not raw.strip():
        return {"recommendations": [], "_rec_flag": "empty_response"}
    try:
        return _extract_json(raw)
    except Exception:
        return {"recommendations": [], "_rec_flag": "parse_error"}


def generate_narrative(eda_result: dict) -> dict:
    insights = generate_insights(eda_result)
    recommendations = generate_recommendations(eda_result, insights)
    return {**insights, **recommendations}
