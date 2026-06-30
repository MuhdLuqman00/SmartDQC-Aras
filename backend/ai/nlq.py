import base64
import io
import json
import math
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .ollama_client import generate
from .sandbox import safe_exec

_NLQ_TEAL = "#00697A"
_NLQ_NAVY = "#1A3A5C"


def _result_to_chart(result) -> str | None:
    """Convert NLQ result to base64 PNG bar chart. Returns None if not chartable."""
    if result is None or isinstance(result, (str, int, float, bool)):
        return None

    if isinstance(result, dict):
        if not all(isinstance(v, (int, float)) for v in result.values()):
            return None
        labels = list(result.keys())[:15]
        values = [result[k] for k in labels]
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.barh(labels, values, color=_NLQ_TEAL)
        ax.set_facecolor("#FAFCFC")
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()

    if isinstance(result, list):
        if not result:
            return None
        try:
            df = pd.DataFrame(result)
        except Exception:
            return None
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if not num_cols:
            return None
        str_cols = [c for c in df.columns if c not in num_cols]
        label_col = str_cols[0] if str_cols else None
        value_col = num_cols[0]
        labels = df[label_col].astype(str).tolist()[:15] if label_col else [str(i) for i in df.index[:15]]
        values = df[value_col].tolist()[:15]
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.barh(labels, values, color=_NLQ_TEAL)
        ax.set_xlabel(value_col, color=_NLQ_NAVY, fontsize=9)
        ax.set_facecolor("#FAFCFC")
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()

    return None

CODE_SYSTEM = """You are a Python/pandas code generator for health data analysis.
Given a user question and a DataFrame schema, write pandas code to answer it.
Rules:
- There is exactly ONE DataFrame, available as `df`. There are NOT multiple
  datasets — phrases like "each dataset" mean grouping within this one `df`.
- EVERY column is stored as a string. Before any numeric comparison, sum, mean,
  min/max, or sorting, convert with `pd.to_numeric(df[col], errors="coerce")`
  so non-numeric/blank cells become NaN instead of crashing.
- Store the final answer in a variable called `result`.
- `result` must be JSON-friendly: a scalar (int/float/str/bool), a flat list, a
  flat dict {label: number}, or a small DataFrame (max 20 rows). When you build
  a dict/Series of counts, call `.to_dict()` so the value is plain — never leave
  `result` as a GroupBy, ndarray, or numpy scalar method call.
- For "how many X per/by/for each Y" use `df.groupby(Y).size()` (or `[X].nunique()`)
  then `.to_dict()`.
- `pd` (pandas) and `np` (numpy) are already available — prefer them directly.
- If you must import, only these are allowed: pandas, numpy, math, datetime, re, statistics, json, collections, itertools, functools, decimal
- Standard builtins (len, sum, round, sorted, min, max, etc.) are available.
- No file or OS access (no open, os, sys, subprocess) — it will be rejected.
- Match column names to the schema EXACTLY (they are case- and spelling-sensitive).
- Return only the code block, no explanation."""

ANSWER_SYSTEM = """You are SmartDQC, a bilingual (Bahasa Malaysia and English) data analyst.
Your readers are non-technical health staff. Given a user question and the
computed result, reply with:
  - "answer": the result stated plainly in both languages.
  - "reasoning": one short plain-language sentence (no code, no column jargon
    where avoidable) explaining HOW the number was obtained — e.g. "counted the
    distinct values in the state column". This is shown to non-technical users
    so they can trust the figure.
Never invent numbers that are not in the computed result. Always respond with
valid JSON only."""


def _schema_context(df: pd.DataFrame) -> str:
    lines = [f"DataFrame shape: {df.shape[0]} rows × {df.shape[1]} columns"]
    lines.append("Columns and sample values:")
    for col in df.columns[:30]:
        sample = df[col].dropna().head(3).tolist()
        lines.append(f"  {col}: {sample}")
    return "\n".join(lines)


def _extract_code(raw: str) -> str:
    match = re.search(r"```(?:python)?\n(.*?)```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw.strip()


def _to_json_native(obj) -> object:
    """Recursively coerce a value into JSON-native Python types.

    The NLQ result is generated by an LLM-written pandas snippet, so it can be
    anything: a numpy scalar, a nested dict whose values are np.int64, a Series,
    a DataFrame, NaN/Inf, etc. FastAPI's encoder and the JSONB column both reject
    those — that was the root of both the 500 ("'numpy.int64' object is not
    iterable") and "Object of type DataFrame is not JSON serializable". Walking
    the structure once here guarantees everything downstream is serialisable.
    """
    # None / native scalars (filter non-finite floats → null, like JSON wants).
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None

    # numpy scalars / 0-d arrays expose .item() → a native Python scalar.
    if isinstance(obj, np.generic):
        return _to_json_native(obj.item())
    if isinstance(obj, np.ndarray):
        return [_to_json_native(v) for v in obj.tolist()]

    # pandas containers — cap rows so a runaway result can't bloat the payload.
    if isinstance(obj, pd.DataFrame):
        return [_to_json_native(r) for r in obj.head(20).to_dict(orient="records")]
    if isinstance(obj, pd.Series):
        return {str(k): _to_json_native(v) for k, v in obj.head(20).to_dict().items()}
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()

    if isinstance(obj, dict):
        return {str(k): _to_json_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_json_native(v) for v in obj]

    # Last-resort generic .item() (e.g. decimal/other scalar wrappers).
    if hasattr(obj, "item"):
        try:
            return _to_json_native(obj.item())
        except Exception:
            pass
    return str(obj)


def _result_to_json_safe(result) -> object:
    return _to_json_native(result)


def _ensure_answer(ans, error: str | None) -> dict:
    """Guarantee a non-empty bilingual {bm,en} answer.

    A blank answer is what makes the frontend fall back to String(r.data)
    and render '[object Object]'. So the model/sandbox failing must still
    yield a readable message, never an empty string.
    """
    bm = en = ""
    if isinstance(ans, dict):
        bm = str(ans.get("bm") or "").strip()
        en = str(ans.get("en") or "").strip()
    elif isinstance(ans, str):
        bm = en = ans.strip()

    if not bm and not en:
        if error:
            snippet = str(error).strip().splitlines()[-1][:200]
            en = f"Could not compute an answer for that question ({snippet})."
            bm = f"Tidak dapat mengira jawapan untuk soalan itu ({snippet})."
        else:
            en = "No answer could be produced — please rephrase the question."
            bm = "Tiada jawapan dapat dihasilkan — sila ubah soalan."

    # Never leave one side blank.
    bm = bm or en
    en = en or bm
    return {"bm": bm, "en": en}


def _reasoning_or_none(reasoning, error: str | None) -> dict | None:
    """Plain-language 'how this was computed' shown to non-technical users.

    Unlike the answer it is optional: if the model omits it, or the code failed
    (so there's nothing to explain), return None and the UI simply hides the
    explanation rather than showing an empty line."""
    if error:
        return None
    bm = en = ""
    if isinstance(reasoning, dict):
        bm = str(reasoning.get("bm") or "").strip()
        en = str(reasoning.get("en") or "").strip()
    elif isinstance(reasoning, str):
        bm = en = reasoning.strip()
    if not bm and not en:
        return None
    return {"bm": bm or en, "en": en or bm}


def _generate_code(query: str, schema: str, prior_error: str | None = None) -> str:
    """Ask the model for a pandas snippet. On a retry, feed back the traceback
    from the failed first attempt so it can correct itself (a wrong column name,
    a numeric op on a string column, etc.)."""
    code_prompt = f"""User question: {query}

{schema}

Write pandas code to answer this question. Store the answer in `result`."""
    if prior_error:
        snippet = str(prior_error).strip().splitlines()[-1][:300]
        code_prompt += (
            f"\n\nYour previous attempt failed with this error:\n{snippet}\n"
            "Fix the code — check the exact column names against the schema and "
            "coerce string columns with pd.to_numeric(..., errors=\"coerce\") "
            "before any numeric operation."
        )
    return _extract_code(generate(code_prompt, system=CODE_SYSTEM))


def answer_query(query: str, df: pd.DataFrame) -> dict:
    schema = _schema_context(df)

    # First pass; on failure, retry once with the traceback fed back so the
    # model can self-correct instead of us surfacing a raw "code failed" answer.
    code = _generate_code(query, schema)
    result, error = safe_exec(code, df)
    if error:
        retry_code = _generate_code(query, schema, prior_error=error)
        retry_result, retry_error = safe_exec(retry_code, df)
        if not retry_error:
            code, result, error = retry_code, retry_result, None
        else:
            code, error = retry_code, retry_error

    if error:
        answer_context = f"The code failed with error: {error}"
        result_safe = None
    else:
        result_safe = _result_to_json_safe(result)
        answer_context = f"Computed result: {str(result_safe)[:500]}"

    answer_prompt = f"""User question: {query}

{answer_context}

Respond with this exact JSON:
{{
  "answer": {{"bm": "answer in Bahasa Malaysia", "en": "answer in English"}},
  "reasoning": {{"bm": "how it was computed, in Bahasa Malaysia", "en": "how it was computed, in English"}}
}}"""

    raw_answer = generate(answer_prompt, system=ANSWER_SYSTEM, json_mode=True)

    try:
        raw_answer = raw_answer.strip()
        match = re.search(r"\{.*\}", raw_answer, re.DOTALL)
        answer_json = json.loads(match.group() if match else raw_answer)
    except Exception:
        answer_json = {"answer": {"bm": raw_answer[:300], "en": raw_answer[:300]}}

    if not isinstance(answer_json, dict):
        answer_json = {}

    chart_b64 = _result_to_chart(result_safe)

    return {
        "answer":    _ensure_answer(answer_json.get("answer"), error),
        "reasoning": _reasoning_or_none(answer_json.get("reasoning"), error),
        "result":    result_safe,
        "code_used": code,
        "chart_b64": chart_b64,
    }
