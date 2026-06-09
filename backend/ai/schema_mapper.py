"""AI-powered column mapping for Feature #2 — scenarios 2 (unknown schema)
and 3 (schema drift). Called only when keyword matching leaves too many fields
unmapped. Falls back gracefully if LLM is unavailable."""
from __future__ import annotations

import json
import re

from backend.config import STANDARD_SCHEMA
from backend.ai.ollama_client import generate

_SCHEMA_SYSTEM = """You are a data schema mapper for Malaysian health data.
Given a list of raw column names and sample values, map each raw column to a
standard field name from the provided schema. Respond ONLY with valid JSON:
{"standard_field_name": "raw_column_name_or_null", ...}
Every standard field must appear as a key. Use null if no column matches."""


# Schema mapping is best-effort and sits on the synchronous /upload/preview
# path. Bound it well under the nginx gateway timeout so a cold/slow model
# fails fast to the heuristic fallback instead of hanging the upload (504).
_SCHEMA_MAP_TIMEOUT = 20.0


def _needs_ai_assist(auto_map: dict, unmapped_threshold: int = 3) -> bool:
    """Return True if enough fields are unmapped to justify an LLM call."""
    unmapped = sum(1 for v in auto_map.values() if v is None)
    return unmapped >= unmapped_threshold


def ai_suggest_mapping(
    columns: list[str],
    sample_values: dict[str, list],
    source_type: str = "general",
) -> dict[str, str | None]:
    """Return {standard_field: raw_column} using LLM. Falls back to empty map on error."""
    schema_desc = "\n".join(
        f"  {k}: {v['description']}" for k, v in STANDARD_SCHEMA.items()
    )
    sample_lines = "\n".join(
        f"  {col}: {vals[:3]}" for col, vals in list(sample_values.items())[:25]
    )
    prompt = (
        f"Source type hint: {source_type}\n\n"
        f"Raw columns with sample values:\n{sample_lines}\n\n"
        f"Standard schema fields:\n{schema_desc}\n\n"
        "Map each standard field to the best matching raw column, or null."
    )

    try:
        raw = generate(
            prompt,
            system=_SCHEMA_SYSTEM,
            json_mode=True,
            timeout=_SCHEMA_MAP_TIMEOUT,
        )
        raw = raw.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(match.group() if match else raw)
    except Exception:
        return {k: None for k in STANDARD_SCHEMA}

    col_set = set(columns)
    return {
        k: (result[k] if result.get(k) in col_set else None)
        for k in STANDARD_SCHEMA
    }
