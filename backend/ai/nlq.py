import base64
import io
import json
import re
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

CODE_SYSTEM = """You are a Python/pandas code generator for KKM health data analysis.
Given a user question and a DataFrame schema, write pandas code to answer it.
Rules:
- The DataFrame is available as `df` (all columns are strings unless stated otherwise)
- Store your final answer in a variable called `result`
- result must be a scalar, list, dict, or small DataFrame (max 20 rows)
- Use only pd, np, and df — no imports, no file I/O
- Return only the code block, no explanation"""

ANSWER_SYSTEM = """You are SmartDQC, a bilingual (Bahasa Malaysia and English) data analyst for KKM.
Given a user question and the computed result, write a clear answer in both languages.
Always respond with valid JSON only."""


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


def _result_to_json_safe(result) -> object:
    if isinstance(result, pd.DataFrame):
        return result.head(20).to_dict(orient="records")
    if isinstance(result, pd.Series):
        return result.head(20).to_dict()
    if hasattr(result, "item"):
        return result.item()
    return result


def answer_query(query: str, df: pd.DataFrame) -> dict:
    schema = _schema_context(df)

    code_prompt = f"""User question: {query}

{schema}

Write pandas code to answer this question. Store the answer in `result`."""

    raw_code = generate(code_prompt, system=CODE_SYSTEM)
    code = _extract_code(raw_code)

    result, error = safe_exec(code, df)

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
  "answer": {{"bm": "answer in Bahasa Malaysia", "en": "answer in English"}}
}}"""

    raw_answer = generate(answer_prompt, system=ANSWER_SYSTEM, json_mode=True)

    try:
        raw_answer = raw_answer.strip()
        match = re.search(r"\{.*\}", raw_answer, re.DOTALL)
        answer_json = json.loads(match.group() if match else raw_answer)
    except Exception:
        answer_json = {"answer": {"bm": raw_answer[:300], "en": raw_answer[:300]}}

    chart_b64 = _result_to_chart(result_safe)

    return {
        "answer":    answer_json.get("answer", {"bm": "", "en": ""}),
        "result":    result_safe,
        "code_used": code,
        "chart_b64": chart_b64,
    }
