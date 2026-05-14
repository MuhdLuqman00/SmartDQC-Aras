"""
SmartDQC API — FastAPI application
All endpoints. Business logic lives in backend/eda/, backend/cleaning/, and backend/export/.
"""

from __future__ import annotations

import io
import json
import logging
import re
import uuid
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

import pandas as pd
import numpy as np
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
from pydantic import BaseModel
from typing import List, Optional

from .config import STANDARD_SCHEMA, auto_suggest_mapping, detect_source_type
from .ai.schema_mapper import ai_suggest_mapping, _needs_ai_assist
from .eda.runner import run_eda, json_safe
from .export.tableau import (
    build_aggregated_table,
    to_excel as tbl_excel,
    to_csv as tbl_csv,
)
from .export.cleaned import to_excel as cln_excel, to_csv as cln_csv
from .auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    TokenExpiredError,
    InvalidTokenError,
)
from .db.init_db import init_db, get_db
from .db.models import Dataset, Session as DBSession, AnalysisResult, User
from .ai.narrative import generate_narrative
from .ai.nlq import answer_query
from .ml.corrections import flag_anomalies
from .ml.risk_score import compute_risk_scores
from .ml.zscore_history import forecast_district_risk
from .export.report import build_pptx_bytes, build_pdf_bytes
from .eda.kpi import compute_kpi_dashboard, compute_trajectory_narratives

from datetime import datetime
from sqlalchemy.orm import Session as SASession


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _seed_admin()
    yield


def _seed_admin():
    from .db.init_db import SessionLocal

    db = SessionLocal()
    try:
        if not db.query(User).filter_by(username="admin").first():
            db.add(
                User(
                    username="admin",
                    password_hash=hash_password("ADMIN_SEED_PASSWORD_PLACEHOLDER"),
                    role="admin",
                )
            )
            db.commit()
    finally:
        db.close()


app = FastAPI(title="SmartDQC API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── FILE READER ──────────────────────────────────────────────────────────────


def read_file(content: bytes, filename: str, sheet: str | None = None):
    fn = (filename or "").lower()
    if fn.endswith(".csv"):
        buf = io.BytesIO(content)
        if len(content) > 50_000_000:
            chunks = pd.read_csv(buf, dtype=str, chunksize=100_000)
            return pd.concat(chunks, ignore_index=True), None
        return pd.read_csv(buf, dtype=str), None
    elif fn.endswith((".xlsx", ".xls")):
        xl = pd.ExcelFile(io.BytesIO(content))
        sheets = xl.sheet_names
        target = sheet if sheet and sheet in sheets else sheets[0]
        return pd.read_excel(io.BytesIO(content), sheet_name=target, dtype=str), sheets
    raise ValueError("Hanya CSV, XLSX, XLS disokong.")


def _csv_stream(df: pd.DataFrame, chunksize: int = 10_000):
    yield df.iloc[0:0].to_csv(index=False)
    for start in range(0, len(df), chunksize):
        yield df.iloc[start : start + chunksize].to_csv(index=False, header=False)


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────


@app.get("/")
def root():
    return {"message": "SmartDQC API", "version": "1.0", "status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}


# ─── AUTH ENDPOINTS ───────────────────────────────────────────────────────────


@app.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    user = db.query(User).filter_by(username=form.username, is_active=True).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "role": user.role}


def _current_user(authorization: str = Header(...), db=Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload = decode_access_token(authorization[7:])
    except (TokenExpiredError, InvalidTokenError) as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    user = db.query(User).filter_by(username=payload["sub"], is_active=True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@app.get("/auth/me")
def me(user=Depends(_current_user)):
    return {"username": user.username, "role": user.role}


@app.post("/auth/logout")
def logout():
    return {"detail": "logged out"}


@app.get("/schema")
def get_schema():
    return {"schema": STANDARD_SCHEMA}


@app.get("/data-dictionary")
def data_dictionary():
    derived = {
        "id_cleaned": {
            "type": "identifier",
            "derived": True,
            "description": "IC/MyKid selepas dibersih (12 digit)",
        },
        "id_type": {
            "type": "categorical",
            "derived": True,
            "description": "Jenis ID: valid_ic / short_id / system_id / missing / invalid_ic",
        },
        "is_valid_ic": {
            "type": "boolean",
            "derived": True,
            "description": "True = IC 12 digit sah",
        },
        "age_months_computed": {
            "type": "numerical",
            "derived": True,
            "description": "Umur dalam bulan (dikira dari tarikh_lahir dan tarikh_ukur)",
        },
        "age_group_computed": {
            "type": "categorical",
            "derived": True,
            "description": "Kumpulan umur standard WHO",
        },
        "bulan_ukur": {
            "type": "categorical",
            "derived": True,
            "description": "Bulan pengukuran (1–12)",
        },
        "suku_tahun": {
            "type": "categorical",
            "derived": True,
            "description": "Suku tahun pengukuran (S1–S4)",
        },
        "kawasan_bahagian": {
            "type": "categorical",
            "derived": True,
            "description": "Kawasan (Sabah) / Bahagian (Sarawak)",
        },
        "flag_bawah_2": {
            "type": "boolean",
            "derived": True,
            "description": "True = bawah 2 tahun (< 24 bulan)",
        },
        "flag_bawah_5": {
            "type": "boolean",
            "derived": True,
            "description": "True = bawah 5 tahun (< 60 bulan)",
        },
        "is_missing_critical": {
            "type": "boolean",
            "derived": True,
            "description": "True = berat/tinggi/BMI hilang",
        },
        "is_missing_age": {
            "type": "boolean",
            "derived": True,
            "description": "True = umur tidak dapat dikira",
        },
        "flag_bmi_mismatch": {
            "type": "boolean",
            "derived": True,
            "description": "True = BMI tidak konsisten dengan berat/tinggi (threshold ±1.0)",
        },
        "flag_date_invalid": {
            "type": "boolean",
            "derived": True,
            "description": "True = tarikh_ukur < tarikh_lahir (tidak logik)",
        },
        "flag_date_future": {
            "type": "boolean",
            "derived": True,
            "description": "True = tarikh_ukur dalam masa hadapan",
        },
        "status_bmi_grouped": {
            "type": "categorical",
            "derived": True,
            "description": "BMI grouped: susut/normal/kurang/obes_berlebihan",
        },
        # WHO z-scores
        "waz": {
            "type": "numerical",
            "derived": True,
            "description": "WHO 2006 Weight-for-Age Z-score",
        },
        "haz": {
            "type": "numerical",
            "derived": True,
            "description": "WHO 2006 Height-for-Age Z-score",
        },
        "baz": {
            "type": "numerical",
            "derived": True,
            "description": "WHO 2006 BMI-for-Age Z-score",
        },
        "waz_class": {
            "type": "categorical",
            "derived": True,
            "description": "Klasifikasi WAZ (WHO 2006)",
        },
        "haz_class": {
            "type": "categorical",
            "derived": True,
            "description": "Klasifikasi HAZ (WHO 2006)",
        },
        "baz_class": {
            "type": "categorical",
            "derived": True,
            "description": "Klasifikasi BAZ (WHO 2006)",
        },
        # Indicator flags (z-score based)
        "ind_kurang_berat_zscore": {
            "type": "boolean",
            "derived": True,
            "description": "Kurang berat badan (WAZ < -2, WHO 2006)",
        },
        "ind_bantut_zscore": {
            "type": "boolean",
            "derived": True,
            "description": "Bantut (HAZ < -2, WHO 2006)",
        },
        "ind_susut_zscore": {
            "type": "boolean",
            "derived": True,
            "description": "Susut (BAZ < -2, WHO 2006)",
        },
        "ind_obes_zscore": {
            "type": "boolean",
            "derived": True,
            "description": "Berlebihan berat badan / obes (BAZ > +2, WHO 2006)",
        },
        # Mismatch flags
        "flag_status_berat_vs_zscore": {
            "type": "boolean",
            "derived": True,
            "description": "Label sumber status_berat tidak sepadan dengan WAZ z-skor",
        },
        "flag_status_tinggi_vs_zscore": {
            "type": "boolean",
            "derived": True,
            "description": "Label sumber status_tinggi tidak sepadan dengan HAZ z-skor",
        },
        "flag_status_bmi_vs_zscore": {
            "type": "boolean",
            "derived": True,
            "description": "Label sumber status_bmi tidak sepadan dengan BAZ z-skor",
        },
    }
    return {"source_fields": STANDARD_SCHEMA, "derived_fields": derived}


# ─── UPLOAD / PREVIEW ─────────────────────────────────────────────────────────


@app.post("/upload/preview")
async def upload_preview(
    file: UploadFile = File(...),
    source_type: str = Form("auto"),
    sheet: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
):
    content = await file.read()
    filename = file.filename or ""
    try:
        df, sheets = read_file(content, filename, sheet)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(400, f"Fail tidak dapat dibaca: {e}")

    # Detect source type and generate mapping
    detected_source_type = (
        detect_source_type(df.columns.tolist())
        if source_type == "auto"
        else source_type
    )

    auto_map = auto_suggest_mapping(df.columns.tolist(), detected_source_type)

    if _needs_ai_assist(auto_map):
        sample_values = {
            col: df[col].dropna().head(3).astype(str).tolist()
            for col in df.columns[:30]
        }
        ai_map = ai_suggest_mapping(
            df.columns.tolist(), sample_values, source_type=detected_source_type
        )
        for field, val in ai_map.items():
            if auto_map.get(field) is None and val is not None:
                auto_map[field] = val

    # Cache the uploaded DataFrame for subsequent cleaning
    cache_id = _cache_cleaned(
        df, {"filename": filename, "source_type": detected_source_type}
    )

    # Calculate unmapped columns (columns not in auto_map keys)
    unmapped = [col for col in df.columns if col not in auto_map]

    total_rows = len(df)
    start = (page - 1) * page_size
    page_data = df.iloc[start : start + page_size].copy()
    page_data = page_data.replace(r"^\s*$", np.nan, regex=True)
    page_data = page_data.where(page_data.notna(), None)

    # Build response matching frontend expectations
    mapping_with_confidence: dict = {}
    for col, standard in auto_map.items():
        # Calculate confidence based on match quality
        confidence = 0.95 if standard else 0.0
        mapping_with_confidence[col] = {"standard": standard, "confidence": confidence}

    return JSONResponse(
        content=json_safe(
            {
                "cache_id": cache_id,
                "filename": filename,
                "source_type": detected_source_type,
                "rows": total_rows,
                "columns": df.columns.tolist(),
                "sample": page_data.to_dict(orient="records"),
                "auto_mapping": mapping_with_confidence,
                "unmapped_columns": unmapped,
                "sheets": sheets or [],
                "active_sheet": sheet or (sheets[0] if sheets else None),
                "page": page,
                "page_size": page_size,
                "total_pages": max(1, (total_rows + page_size - 1) // page_size),
            }
        )
    )


# ─── MAPPING VALIDATION ───────────────────────────────────────────────────────


@app.post("/mapping/validate")
async def validate_mapping(
    file: UploadFile = File(...),
    mapping: str = "",
    sheet: Optional[str] = None,
):
    content = await file.read()
    filename = file.filename or ""
    try:
        df, _ = read_file(content, filename, sheet)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        mapping_dict = json.loads(mapping) if mapping else {}
    except Exception:
        raise HTTPException(400, "Mapping JSON tidak sah")

    available_cols = set(df.columns.tolist())
    errors, warnings, ok = [], [], []

    for std_field, raw_col in mapping_dict.items():
        if not raw_col:
            continue
        if raw_col not in available_cols:
            errors.append(
                {
                    "field": std_field,
                    "mapped_to": raw_col,
                    "issue": f"Kolum '{raw_col}' tidak wujud dalam fail",
                }
            )
        else:
            schema_type = STANDARD_SCHEMA.get(std_field, {}).get("type", "unknown")
            col_dtype = str(df[raw_col].dtype)
            ok.append({"field": std_field, "mapped_to": raw_col, "dtype": col_dtype})
            if schema_type == "numerical" and col_dtype == "object":
                pct_numeric = pd.to_numeric(df[raw_col], errors="coerce").notna().mean()
                if pct_numeric < 0.5:
                    warnings.append(
                        {
                            "field": std_field,
                            "mapped_to": raw_col,
                            "issue": f"Kolum kelihatan bukan numerik ({round(pct_numeric * 100)}% boleh ditukar)",
                        }
                    )

    from .config import CORE_FIELDS

    critical_unmapped = [
        f for f in CORE_FIELDS if f not in mapping_dict or not mapping_dict.get(f)
    ]
    if critical_unmapped:
        warnings.append(
            {
                "field": "critical_fields",
                "mapped_to": None,
                "issue": f"Medan kritikal tidak dipetakan: {critical_unmapped}",
            }
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "ok": ok,
        "total_mapped": len([v for v in mapping_dict.values() if v]),
        "available_columns": df.columns.tolist(),
    }


# ─── RUN EDA ──────────────────────────────────────────────────────────────────


@app.post("/eda/run")
async def run_eda_endpoint(
    file: UploadFile = File(...),
    mapping: str = "",
    source_type: str = "myvass",
    sheet: Optional[str] = None,
    bmi_threshold: float = Query(1.0, ge=0.1, le=10.0),
    db=Depends(get_db),
):
    content = await file.read()
    filename = file.filename or ""
    try:
        df, _ = read_file(content, filename, sheet)
    except Exception as e:
        raise HTTPException(400, str(e))

    try:
        mapping_dict = json.loads(mapping) if mapping else {}
    except Exception:
        mapping_dict = {}

    report = run_eda(df, mapping_dict, source_type, bmi_threshold=bmi_threshold)

    # Cache cleaned DF for downstream endpoints
    cleaned_df_data = report.get("_cleaned_data", [])
    import pandas as _pd

    cleaned_df = _pd.DataFrame(cleaned_df_data) if cleaned_df_data else df
    cache_id = _cache_cleaned(cleaned_df, report)

    try:
        _persist_session(
            cache_id=cache_id,
            filename=filename,
            source_type=source_type,
            row_count=len(cleaned_df),
            result=report,
            db=db,
        )
    except Exception:
        pass  # best-effort — never fail the EDA run for a DB write error

    _log_audit(action="eda.run", detail=f"cache_id={cache_id}")

    # Strip private / large keys from public response
    for key in ["_cleaned_data", "_cleaned_columns", "_aggregated_full"]:
        report.pop(key, None)

    report["cache_id"] = cache_id
    return JSONResponse(content=json_safe(report))


# ─── CLEANED DATA PREVIEW (paginated) ────────────────────────────────────────


@app.post("/cleaned/preview")
async def cleaned_preview(
    file: UploadFile = File(...),
    mapping: str = "",
    source_type: str = "myvass",
    sheet: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=5, le=200),
):
    content = await file.read()
    filename = file.filename or ""
    try:
        df, _ = read_file(content, filename, sheet)
    except Exception as e:
        raise HTTPException(400, str(e))

    mapping_dict = json.loads(mapping) if mapping else {}
    report = run_eda(df, mapping_dict, source_type)
    all_records = report.get("_cleaned_data", [])
    cols = report.get("_cleaned_columns", [])
    total_rows = len(all_records)
    start = (page - 1) * page_size

    return JSONResponse(
        content=json_safe(
            {
                "total_rows": total_rows,
                "total_pages": max(1, (total_rows + page_size - 1) // page_size),
                "page": page,
                "page_size": page_size,
                "columns": cols,
                "records": all_records[start : start + page_size],
            }
        )
    )


# ─── DOWNLOAD CLEANED DATA ────────────────────────────────────────────────────


@app.post("/download/cleaned")
async def download_cleaned(
    file: UploadFile = File(...),
    mapping: str = "",
    source_type: str = "myvass",
    sheet: Optional[str] = None,
    fmt: str = Query("csv", pattern="^(csv|xlsx)$"),
):
    content = await file.read()
    filename = file.filename or ""
    try:
        df, _ = read_file(content, filename, sheet)
    except Exception as e:
        raise HTTPException(400, str(e))

    mapping_dict = json.loads(mapping) if mapping else {}
    report = run_eda(df, mapping_dict, source_type)
    cleaned_records = report.get("_cleaned_data", [])
    cleaned_cols = report.get("_cleaned_columns", [])
    if not cleaned_records:
        raise HTTPException(500, "Tiada data dibersih.")

    base = filename.rsplit(".", 1)[0]
    if fmt == "csv":
        data = cln_csv(cleaned_records, cleaned_cols)
        return StreamingResponse(
            iter([data]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="cleaned_{base}.csv"'
            },
        )
    else:
        data = cln_excel(cleaned_records, cleaned_cols, base)
        return StreamingResponse(
            iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="cleaned_{base}.xlsx"'
            },
        )


# ─── EXPORT AGGREGATED (TABLEAU) — NO ROW CAP ────────────────────────────────


@app.post("/export/aggregated")
async def export_aggregated(
    file: UploadFile = File(...),
    mapping: str = "",
    source_type: str = "myvass",
    sheet: Optional[str] = None,
    fmt: str = Query("csv", pattern="^(csv|xlsx)$"),
):
    """
    Tableau-ready flat aggregated table — every geo × age_group × indicator row.
    NO row cap. Includes sumber_indikator column (zscore | source_label).
    """
    content = await file.read()
    filename = file.filename or ""
    try:
        df, _ = read_file(content, filename, sheet)
    except Exception as e:
        raise HTTPException(400, str(e))

    mapping_dict = json.loads(mapping) if mapping else {}
    report = run_eda(df, mapping_dict, source_type)

    # Use the full (uncapped) aggregated table from the private key
    agg_rows = report.get("_aggregated_full", build_aggregated_table(report))
    if not agg_rows:
        raise HTTPException(
            422, "Tiada data indikator — pastikan status / berat / tinggi dipetakan."
        )

    base = filename.rsplit(".", 1)[0]
    if fmt == "xlsx":
        data = tbl_excel(agg_rows, base)
        return StreamingResponse(
            iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="tableau_{base}.xlsx"'
            },
        )
    else:
        data = tbl_csv(agg_rows)
        return StreamingResponse(
            iter([data]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="tableau_{base}.csv"'
            },
        )


# ─── MYVASS WIDE-TO-LONG PREVIEW ─────────────────────────────────────────────


@app.post("/transform/myvass-wide-to-long")
async def myvass_wide_to_long_endpoint(
    file: UploadFile = File(...),
    sheet: Optional[str] = None,
):
    content = await file.read()
    filename = file.filename or ""
    try:
        df, _ = read_file(content, filename, sheet)
    except Exception as e:
        raise HTTPException(400, str(e))

    from .eda.runner import myvass_wide_to_long

    long_df = myvass_wide_to_long(df)
    return JSONResponse(
        content=json_safe(
            {
                "original_rows": len(df),
                "long_rows": len(long_df),
                "columns": long_df.columns.tolist(),
                "preview": long_df.head(10)
                .replace({np.nan: None})
                .to_dict(orient="records"),
            }
        )
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MYVASS MULTI-FILE MERGE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


def _merge_myvass_files(
    file_contents: list[tuple[str, bytes]],
    dose_date_col: str = "DOSE_DATE",
    ic_col: str = "IC_NO_PASSPORT",
) -> tuple[pd.DataFrame, dict]:
    """
    Merge multiple MyVASS files:
    1. Validate all headers match
    2. Concatenate
    3. Deduplicate by IC — keep row with latest DOSE_DATE
    4. Remove rows with any null cell
    Returns (merged_df, merge_stats).
    """
    if not file_contents:
        raise ValueError("No files provided.")

    dfs = []
    ref_cols = None
    ref_name = None

    for filename, content in file_contents:
        fn = filename.lower()
        if fn.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content), dtype=str)
        elif fn.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content), dtype=str)
        else:
            raise ValueError(f"Unsupported format: {filename}")

        if ref_cols is None:
            ref_cols = list(df.columns)
            ref_name = filename
        else:
            if list(df.columns) != ref_cols:
                missing = set(ref_cols) - set(df.columns)
                extra = set(df.columns) - set(ref_cols)
                raise ValueError(
                    f"Header mismatch in '{filename}' vs '{ref_name}'. "
                    f"Missing: {missing or 'none'}. Extra: {extra or 'none'}."
                )
        dfs.append((filename, df))

    merged = pd.concat([df for _, df in dfs], ignore_index=True)
    total_before = len(merged)
    file_counts = {fn: len(df) for fn, df in dfs}

    # Dedup by IC — keep latest DOSE_DATE
    if ic_col not in merged.columns:
        raise ValueError(
            f"Column '{ic_col}' not found. Available: {list(merged.columns)}"
        )

    dup_removed = 0
    if dose_date_col in merged.columns:
        merged["_dd_parsed"] = pd.to_datetime(
            merged[dose_date_col], dayfirst=True, errors="coerce"
        )
        merged = merged.sort_values("_dd_parsed", ascending=False, na_position="last")
        before_dedup = len(merged)
        merged = merged.drop_duplicates(subset=[ic_col], keep="first")
        dup_removed = before_dedup - len(merged)
        merged = merged.drop(columns=["_dd_parsed"]).sort_index().reset_index(drop=True)
    else:
        before_dedup = len(merged)
        merged = merged.drop_duplicates(subset=[ic_col], keep="first")
        dup_removed = before_dedup - len(merged)

    after_dedup = len(merged)

    # Remove rows with any null
    # First replace empty/whitespace strings with NaN for proper null detection
    merged = merged.replace(r"^\s*$", np.nan, regex=True)
    null_rows = int(merged.isna().any(axis=1).sum())
    merged = merged.dropna().reset_index(drop=True)
    after_null_removal = len(merged)

    stats = {
        "files_merged": len(dfs),
        "file_counts": file_counts,
        "total_rows_before": total_before,
        "duplicates_removed": dup_removed,
        "after_dedup": after_dedup,
        "null_rows_removed": null_rows,
        "final_rows": after_null_removal,
        "columns": list(merged.columns),
        "ic_column": ic_col,
        "dose_date_column": dose_date_col if dose_date_col in ref_cols else None,
    }
    return merged, stats


@app.post("/upload/merge-preview")
async def merge_preview(
    files: List[UploadFile] = File(...),
    ic_col: str = Query("IC_NO_PASSPORT"),
    dose_date_col: str = Query("DOSE_DATE"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=5, le=100),
):
    """
    Upload multiple MyVASS files, merge + dedup + remove nulls,
    and return a preview of the merged data.
    """
    file_contents = []
    for f in files:
        content = await f.read()
        file_contents.append((f.filename or "unknown", content))

    try:
        merged, stats = _merge_myvass_files(file_contents, dose_date_col, ic_col)
    except ValueError as e:
        raise HTTPException(400, str(e))

    source_type = detect_source_type(merged.columns.tolist())
    auto_map = auto_suggest_mapping(merged.columns.tolist(), source_type)

    if _needs_ai_assist(auto_map):
        sample_values = {
            col: merged[col].dropna().head(3).astype(str).tolist()
            for col in merged.columns[:30]
        }
        ai_map = ai_suggest_mapping(
            merged.columns.tolist(), sample_values, source_type=source_type
        )
        for field, val in ai_map.items():
            if auto_map.get(field) is None and val is not None:
                auto_map[field] = val

    total_rows = len(merged)
    start = (page - 1) * page_size
    page_data = merged.iloc[start : start + page_size].copy()
    page_data = page_data.where(page_data.notna(), None)

    # Save merged data in memory as CSV for subsequent EDA call
    merged_buf = io.BytesIO()
    merged.to_csv(merged_buf, index=False, encoding="utf-8-sig")
    merged_bytes = merged_buf.getvalue()

    _log_audit(action="upload.preview", detail=",".join(f[0] for f in file_contents))
    return JSONResponse(
        content=json_safe(
            {
                "merge_stats": stats,
                "source_type": source_type,
                "total_rows": total_rows,
                "total_columns": len(merged.columns),
                "columns": merged.columns.tolist(),
                "preview": page_data.to_dict(orient="records"),
                "page": page,
                "page_size": page_size,
                "total_pages": max(1, (total_rows + page_size - 1) // page_size),
                "auto_mapping": auto_map,
            }
        )
    )


@app.post("/eda/run-merged")
async def run_eda_merged(
    files: List[UploadFile] = File(...),
    mapping: str = "",
    source_type: str = "myvass",
    ic_col: str = Query("IC_NO_PASSPORT"),
    dose_date_col: str = Query("DOSE_DATE"),
    bmi_threshold: float = Query(1.0, ge=0.1, le=10.0),
):
    """
    Upload multiple MyVASS files → merge + dedup + remove nulls → run full EDA.
    """
    file_contents = []
    for f in files:
        content = await f.read()
        file_contents.append((f.filename or "unknown", content))

    try:
        merged, merge_stats = _merge_myvass_files(file_contents, dose_date_col, ic_col)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        mapping_dict = json.loads(mapping) if mapping else {}
    except Exception:
        mapping_dict = {}

    # Convert merged DataFrame to string-typed (same as read_file does)
    merged = merged.astype(str).replace("nan", np.nan)

    report = run_eda(merged, mapping_dict, source_type, bmi_threshold=bmi_threshold)
    report["merge_stats"] = merge_stats
    report["changes_applied"].insert(
        0,
        f"Merged {merge_stats['files_merged']} files: "
        f"{merge_stats['total_rows_before']} total rows → "
        f"{merge_stats['duplicates_removed']} duplicates removed → "
        f"{merge_stats['null_rows_removed']} null rows removed → "
        f"{merge_stats['final_rows']} final rows",
    )

    for key in ["_cleaned_data", "_cleaned_columns", "_aggregated_full"]:
        report.pop(key, None)

    return JSONResponse(content=json_safe(report))


@app.post("/download/cleaned-merged")
async def download_cleaned_merged(
    files: List[UploadFile] = File(...),
    mapping: str = "",
    source_type: str = "myvass",
    ic_col: str = Query("IC_NO_PASSPORT"),
    dose_date_col: str = Query("DOSE_DATE"),
    fmt: str = Query("csv", pattern="^(csv|xlsx)$"),
):
    """Download cleaned data from merged multi-file upload."""
    file_contents = []
    for f in files:
        content = await f.read()
        file_contents.append((f.filename or "unknown", content))

    try:
        merged, _ = _merge_myvass_files(file_contents, dose_date_col, ic_col)
    except ValueError as e:
        raise HTTPException(400, str(e))

    mapping_dict = json.loads(mapping) if mapping else {}
    merged = merged.astype(str).replace("nan", np.nan)
    report = run_eda(merged, mapping_dict, source_type)
    cleaned_records = report.get("_cleaned_data", [])
    cleaned_cols = report.get("_cleaned_columns", [])
    if not cleaned_records:
        raise HTTPException(500, "Tiada data dibersih.")

    if fmt == "csv":
        data = cln_csv(cleaned_records, cleaned_cols)
        return StreamingResponse(
            iter([data]),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="cleaned_merged_myvass.csv"'
            },
        )
    else:
        data = cln_excel(cleaned_records, cleaned_cols, "merged_myvass")
        return StreamingResponse(
            iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": 'attachment; filename="cleaned_merged_myvass.xlsx"'
            },
        )


# ═══════════════════════════════════════════════════════════════════════════════
# KKM DATA CLEANING TOOL ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

import uuid as _uuid

from .eda.cleaning import clean_data, detect_data_type

# ── In-memory cache for cleaned DataFrames (avoids re-upload for download) ────
_cleaned_cache: dict[str, dict] = {}  # key -> {"df": DataFrame, "stats": dict}
_CACHE_MAX = 10  # keep at most 10 entries


def _cache_cleaned(df: pd.DataFrame, stats: dict | None = None) -> str:
    """Store cleaned DF + stats in cache, return a UUID key."""
    key = str(_uuid.uuid4())
    if len(_cleaned_cache) >= _CACHE_MAX:
        oldest = next(iter(_cleaned_cache))
        _cleaned_cache.pop(oldest, None)
    _cleaned_cache[key] = {"df": df, "stats": stats or {}}
    return key


def _persist_session(
    cache_id: str,
    filename: str,
    source_type: str,
    row_count: int,
    result: dict,
    db,
) -> None:
    """Upsert Dataset + Session + AnalysisResult so session data survives server restart."""
    from .db.models import Dataset, Session as _Session, AnalysisResult
    from datetime import datetime as _dt

    now = _dt.utcnow()

    ds = db.query(Dataset).filter_by(id=cache_id).first()
    if ds is None:
        ds = Dataset(
            id=cache_id,
            name=filename,
            filename=filename,
            source_type=source_type,
            row_count=row_count,
            quality_score=result.get("quality_score"),
            created_at=now,
        )
        db.add(ds)
        db.flush()
    else:
        ds.quality_score = result.get("quality_score", ds.quality_score)

    sess_id = str(_uuid.uuid4())
    sess = _Session(
        id=sess_id,
        dataset_id=cache_id,
        created_at=now,
        updated_at=now,
    )
    db.add(sess)
    db.flush()

    db.add(
        AnalysisResult(
            id=str(_uuid.uuid4()),
            session_id=sess_id,
            result_type="quality",
            result_json={
                "quality_score": result.get("quality_score"),
                "issues": result.get("issues", []),
            },
            created_at=now,
        )
    )
    db.commit()


def _log_audit(
    action: str,
    dataset_id: int | None = None,
    detail: str | None = None,
    user_id: int | None = None,
) -> None:
    """Best-effort audit write — never raises."""
    try:
        from .db.session import SessionLocal
        from .db.models import AuditLog

        db = SessionLocal()
        try:
            db.add(
                AuditLog(
                    action=action, dataset_id=dataset_id, detail=detail, user_id=user_id
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def _resolve_source(
    file: bytes | None, filename: str | None, cache_id: str | None
) -> "pd.DataFrame":
    """Resolve a join source to a DataFrame from either a raw upload or the cleaned cache."""
    if cache_id is not None:
        entry = _cleaned_cache.get(cache_id)
        if entry is None:
            raise HTTPException(
                400, f"Cache ID '{cache_id}' not found — re-run cleaning first."
            )
        return entry["df"].copy()
    if file is not None:
        df, _ = read_file(file, filename or "upload.csv")
        return df
    raise HTTPException(
        400, "Provide either a file upload or a cache_id for each side of the join."
    )


def _perform_join(
    df_left: "pd.DataFrame",
    df_right: "pd.DataFrame",
    join_type: str,
    key_cols: list[str] | None,
    dedup: bool,
) -> "tuple[pd.DataFrame, dict]":
    """Execute a join/union and return (result_df, stats_dict)."""
    if join_type == "union":
        result = pd.concat([df_left, df_right], ignore_index=True)
        if dedup:
            before = len(result)
            result = result.drop_duplicates()
            dupes_removed = before - len(result)
        else:
            dupes_removed = 0
        stats = {
            "left_rows": len(df_left),
            "right_rows": len(df_right),
            "result_rows": len(result),
            "duplicates_removed": dupes_removed,
        }
        return result, stats

    # Horizontal join (inner / left / right / outer)
    if not key_cols:
        raise HTTPException(
            400, "key_cols is required for inner/left/right/outer joins."
        )
    missing_left = [c for c in key_cols if c not in df_left.columns]
    missing_right = [c for c in key_cols if c not in df_right.columns]
    if missing_left:
        raise HTTPException(
            400, f"Key column(s) {missing_left} not found in left dataset."
        )
    if missing_right:
        raise HTTPException(
            400, f"Key column(s) {missing_right} not found in right dataset."
        )

    # Match stats based on first key column
    key = key_cols[0]
    left_keys = set(df_left[key].dropna().astype(str))
    right_keys = set(df_right[key].dropna().astype(str))
    stats = {
        "matched_keys": len(left_keys & right_keys),
        "left_only_keys": len(left_keys - right_keys),
        "right_only_keys": len(right_keys - left_keys),
        "result_rows": 0,  # filled after merge
    }

    result = pd.merge(df_left, df_right, on=key_cols, how=join_type)
    stats["result_rows"] = len(result)
    return result, stats


def _profile_columns(df: pd.DataFrame) -> list[dict]:
    """Return column-level profile of a DataFrame."""
    cols = []
    for c in df.columns:
        non_null = int(df[c].notna().sum())
        missing = len(df) - non_null
        missing_pct = round(missing / len(df) * 100, 1) if len(df) > 0 else 0
        unique = int(df[c].nunique())
        # infer type
        s = pd.to_numeric(df[c], errors="coerce")
        dtype = "Numeric" if s.notna().sum() > 0.5 * non_null else "Text"
        cols.append(
            {
                "name": c,
                "non_null": non_null,
                "missing": missing,
                "missing_pct": missing_pct,
                "unique": unique,
                "dtype": dtype,
            }
        )
    return cols


@app.post("/clean/detect-type")
async def detect_type_endpoint(
    file: UploadFile = File(...),
    sheet: Optional[str] = None,
):
    """Detect data type from file columns."""
    content = await file.read()
    filename = file.filename or ""
    try:
        df, sheets = read_file(content, filename, sheet)
    except Exception as e:
        raise HTTPException(400, str(e))

    data_type = detect_data_type(df.columns.tolist(), filename)

    return JSONResponse(
        content=json_safe(
            {
                "filename": filename,
                "detected_type": data_type,
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "columns": df.columns.tolist(),
                "sheets": sheets or [],
            }
        )
    )


@app.post("/clean/quality-check")
async def quality_check_endpoint(
    file: UploadFile = File(...),
    data_type: str = "myvass",
    sheet: Optional[str] = None,
):
    """Get raw data quality analysis before cleaning."""
    content = await file.read()
    filename = file.filename or ""
    try:
        df, _ = read_file(content, filename, sheet)
    except Exception as e:
        raise HTTPException(400, str(e))

    # Basic quality stats
    quality = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "columns": [],
    }

    for col in df.columns:
        col_data = df[col]
        non_null = col_data.notna().sum()
        null_count = len(df) - non_null
        unique_count = col_data.nunique()

        # Check if numeric
        numeric_vals = pd.to_numeric(col_data, errors="coerce")
        is_numeric = numeric_vals.notna().sum() > non_null * 0.8

        col_info = {
            "name": col,
            "non_null": int(non_null),
            "null_count": int(null_count),
            "null_percent": round((null_count / len(df)) * 100, 1)
            if len(df) > 0
            else 0,
            "unique_count": int(unique_count),
            "is_numeric": is_numeric,
        }

        if is_numeric and non_null > 0:
            col_info["min"] = (
                float(numeric_vals.min()) if numeric_vals.notna().any() else None
            )
            col_info["max"] = (
                float(numeric_vals.max()) if numeric_vals.notna().any() else None
            )
            col_info["mean"] = (
                round(float(numeric_vals.mean()), 2)
                if numeric_vals.notna().any()
                else None
            )
        else:
            sample = col_data.dropna().head(5).tolist()
            col_info["sample_values"] = [str(v)[:50] for v in sample]

        quality["columns"].append(col_info)

    # Overall completeness
    total_cells = len(df) * len(df.columns)
    filled_cells = sum(c["non_null"] for c in quality["columns"])
    quality["overall_completeness"] = (
        round((filled_cells / total_cells) * 100, 1) if total_cells > 0 else 0
    )

    return JSONResponse(content=json_safe(quality))


@app.post("/clean/run")
async def clean_run_endpoint(
    file: UploadFile = File(default=None),
    cache_id: str = Form(default=None),
    data_type: str = Form("myvass"),
    sheet: Optional[str] = Form(None),
    db=Depends(get_db),
):
    """Run the cleaning process and return cleaned data with statistics.

    Accepts either:
    1. A file upload directly (file parameter)
    2. A cache_id referencing previously uploaded data
    """
    df = None
    filename = ""

    # Try to get DataFrame from cache_id first
    if cache_id:
        entry = _cleaned_cache.get(cache_id)
        if entry:
            df = entry["df"]
            filename = entry.get("stats", {}).get("filename", "cached_data")

    # If no cache_id or not found, try file upload
    if df is None and file:
        content = await file.read()
        filename = file.filename or ""
        try:
            df, _ = read_file(content, filename, sheet)
        except Exception as e:
            raise HTTPException(400, str(e))

    if df is None:
        raise HTTPException(400, "Provide either a file or a valid cache_id")

    try:
        cleaned_df, stats = clean_data(df, data_type)
    except Exception as e:
        raise HTTPException(500, f"Cleaning error: {str(e)}")

    # Convert cleaned data to records
    cleaned_records = cleaned_df.replace({np.nan: None}).to_dict(orient="records")

    # Cache cleaned DF so download doesn't need re-upload
    new_cache_id = _cache_cleaned(cleaned_df, stats)

    try:
        _persist_session(
            cache_id=new_cache_id,
            filename=filename,
            source_type=data_type,
            row_count=len(cleaned_df),
            result=stats or {},
            db=db,
        )
    except Exception:
        pass  # best-effort — never fail the clean run for a DB write error

    _log_audit(action="clean.run", detail=f"cache_id={new_cache_id}")
    return JSONResponse(
        content=json_safe(
            {
                "success": True,
                "data_type": data_type,
                "stats": stats,
                "cleaned_columns": cleaned_df.columns.tolist(),
                "cleaned_column_profile": _profile_columns(cleaned_df),
                "cleaned_count": len(cleaned_df),
                "preview": cleaned_records[:100],  # First 100 rows for preview
                "cache_id": new_cache_id,
                "rows_before": len(df),
                "rows_after": len(cleaned_df),
            }
        )
    )


@app.post("/clean/download")
async def clean_download_endpoint(
    file: UploadFile = File(...),
    data_type: str = "myvass",
    sheet: Optional[str] = None,
    fmt: str = Query("xlsx", pattern="^(csv|xlsx)$"),
):
    """Download cleaned data as CSV or Excel."""
    content = await file.read()
    filename = file.filename or ""
    try:
        df, _ = read_file(content, filename, sheet)
    except Exception as e:
        raise HTTPException(400, str(e))

    try:
        cleaned_df, stats = clean_data(df, data_type)
    except Exception as e:
        raise HTTPException(500, f"Cleaning error: {str(e)}")

    if len(cleaned_df) == 0:
        raise HTTPException(422, "No data after cleaning")

    base = filename.rsplit(".", 1)[0]
    timestamp = pd.Timestamp.now().strftime("%Y%m%d")

    if fmt == "xlsx":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            # Cleaned data sheet
            cleaned_df.to_excel(writer, sheet_name="Cleaned Data", index=False)

            # Stats sheet
            stats_df = pd.DataFrame(
                [
                    {"Metric": k, "Value": v}
                    for k, v in stats.items()
                    if not isinstance(v, dict)
                ]
            )
            stats_df.to_excel(writer, sheet_name="Cleaning Stats", index=False)

        output.seek(0)
        return StreamingResponse(
            iter([output.read()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{data_type.upper()}_Cleaned_{timestamp}.xlsx"'
            },
        )
    else:
        return StreamingResponse(
            _csv_stream(cleaned_df),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{data_type.upper()}_Cleaned_{timestamp}.csv"'
            },
        )


# ── Multi-file quality check ──────────────────────────────────────────────────
@app.post("/clean/quality-check-multi")
async def quality_check_multi_endpoint(
    files: List[UploadFile] = File(...),
    data_type: str = "myvass",
    ic_col: str = Query("IC_NO_PASSPORT"),
    dose_date_col: str = Query("DOSE_DATE"),
):
    """Merge multiple files, then return quality stats on the merged data."""
    file_contents = []
    for f in files:
        content = await f.read()
        file_contents.append((f.filename or "unknown", content))

    try:
        merged, merge_stats = _merge_myvass_files(file_contents, dose_date_col, ic_col)
    except ValueError as e:
        raise HTTPException(400, str(e))

    df = merged
    quality = {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "merge_stats": merge_stats,
        "columns": [],
    }

    for col in df.columns:
        col_data = df[col]
        non_null = col_data.notna().sum()
        null_count = len(df) - non_null
        unique_count = col_data.nunique()
        numeric_vals = pd.to_numeric(col_data, errors="coerce")
        is_numeric = numeric_vals.notna().sum() > non_null * 0.8

        col_info = {
            "name": col,
            "non_null": int(non_null),
            "null_count": int(null_count),
            "null_percent": round((null_count / len(df)) * 100, 1)
            if len(df) > 0
            else 0,
            "unique_count": int(unique_count),
            "is_numeric": is_numeric,
        }
        if is_numeric and non_null > 0:
            col_info["min"] = (
                float(numeric_vals.min()) if numeric_vals.notna().any() else None
            )
            col_info["max"] = (
                float(numeric_vals.max()) if numeric_vals.notna().any() else None
            )
            col_info["mean"] = (
                round(float(numeric_vals.mean()), 2)
                if numeric_vals.notna().any()
                else None
            )
        else:
            sample = col_data.dropna().head(5).tolist()
            col_info["sample_values"] = [str(v)[:50] for v in sample]
        quality["columns"].append(col_info)

    total_cells = len(df) * len(df.columns)
    filled_cells = sum(c["non_null"] for c in quality["columns"])
    quality["overall_completeness"] = (
        round((filled_cells / total_cells) * 100, 1) if total_cells > 0 else 0
    )

    return JSONResponse(content=json_safe(quality))


# ── Multi-file cleaning ───────────────────────────────────────────────────────
@app.post("/clean/run-multi")
async def clean_run_multi_endpoint(
    files: List[UploadFile] = File(...),
    data_type: str = "myvass",
    ic_col: str = Query("IC_NO_PASSPORT"),
    dose_date_col: str = Query("DOSE_DATE"),
):
    """Merge multiple files, then run cleaning on the merged data."""
    file_contents = []
    for f in files:
        content = await f.read()
        file_contents.append((f.filename or "unknown", content))

    try:
        merged, merge_stats = _merge_myvass_files(file_contents, dose_date_col, ic_col)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        cleaned_df, stats = clean_data(merged, data_type)
    except Exception as e:
        raise HTTPException(500, f"Cleaning error: {str(e)}")

    stats["merge_stats"] = merge_stats
    cleaned_records = cleaned_df.replace({np.nan: None}).to_dict(orient="records")

    # Cache cleaned DF so download doesn't need re-upload
    cache_id = _cache_cleaned(cleaned_df, stats)

    return JSONResponse(
        content=json_safe(
            {
                "success": True,
                "data_type": data_type,
                "stats": stats,
                "cleaned_columns": cleaned_df.columns.tolist(),
                "cleaned_column_profile": _profile_columns(cleaned_df),
                "cleaned_count": len(cleaned_df),
                "preview": cleaned_records[:100],
                "cache_id": cache_id,
            }
        )
    )


# ── Multi-file download ───────────────────────────────────────────────────────
@app.post("/clean/download-multi")
async def clean_download_multi_endpoint(
    files: List[UploadFile] = File(...),
    data_type: str = "myvass",
    ic_col: str = Query("IC_NO_PASSPORT"),
    dose_date_col: str = Query("DOSE_DATE"),
    fmt: str = Query("xlsx", pattern="^(csv|xlsx)$"),
):
    """Merge multiple files, clean, and download."""
    file_contents = []
    for f in files:
        content = await f.read()
        file_contents.append((f.filename or "unknown", content))

    try:
        merged, merge_stats = _merge_myvass_files(file_contents, dose_date_col, ic_col)
    except ValueError as e:
        raise HTTPException(400, str(e))

    try:
        cleaned_df, stats = clean_data(merged, data_type)
    except Exception as e:
        raise HTTPException(500, f"Cleaning error: {str(e)}")

    if len(cleaned_df) == 0:
        raise HTTPException(422, "No data after cleaning")

    timestamp = pd.Timestamp.now().strftime("%Y%m%d")

    if fmt == "xlsx":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            cleaned_df.to_excel(writer, sheet_name="Cleaned Data", index=False)
            stats_rows = [
                {"Metric": k, "Value": v}
                for k, v in stats.items()
                if not isinstance(v, dict)
            ]
            merge_rows = [
                {"Metric": f"merge_{k}", "Value": v}
                for k, v in merge_stats.items()
                if not isinstance(v, (dict, list))
            ]
            pd.DataFrame(stats_rows + merge_rows).to_excel(
                writer, sheet_name="Cleaning Stats", index=False
            )
        output.seek(0)
        return StreamingResponse(
            iter([output.read()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{data_type.upper()}_Merged_Cleaned_{timestamp}.xlsx"'
            },
        )
    else:
        return StreamingResponse(
            _csv_stream(cleaned_df),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{data_type.upper()}_Merged_Cleaned_{timestamp}.csv"'
            },
        )


# ── Cached download (instant — no re-upload) ─────────────────────────────────
@app.get("/clean/download-cached/{cache_id}")
async def download_cached_endpoint(
    cache_id: str,
    fmt: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    data_type: str = Query("myvass"),
):
    """Download previously cleaned data from cache — no file re-upload needed."""
    entry = _cleaned_cache.get(cache_id)
    if entry is None:
        raise HTTPException(404, "Cached data not found — please re-run cleaning.")
    cleaned_df = entry["df"]

    timestamp = pd.Timestamp.now().strftime("%Y%m%d")

    if fmt == "xlsx":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            cleaned_df.to_excel(writer, sheet_name="Cleaned Data", index=False)
        output.seek(0)
        return StreamingResponse(
            iter([output.read()]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{data_type.upper()}_Cleaned_{timestamp}.xlsx"'
            },
        )
    else:
        return StreamingResponse(
            _csv_stream(cleaned_df),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{data_type.upper()}_Cleaned_{timestamp}.csv"'
            },
        )


# ── Dataset Join (horizontal / vertical union) ───────────────────────────────

_JOIN_TYPES = {"inner", "left", "right", "outer", "union"}


@app.post("/join/preview")
async def join_preview_endpoint(
    file_left: UploadFile | None = File(None),
    file_right: UploadFile | None = File(None),
    cache_id_left: str | None = Query(None),
    cache_id_right: str | None = Query(None),
    join_type: str = Query(..., pattern="^(inner|left|right|outer|union)$"),
    key_cols: str | None = Query(
        None, description="Comma-separated key column names (horizontal joins)"
    ),
    dedup: bool = Query(False, description="Remove duplicate rows after union"),
):
    """Preview a join of two datasets. Returns first 50 rows plus shape and stats."""
    left_bytes = (await file_left.read()) if file_left else None
    right_bytes = (await file_right.read()) if file_right else None

    df_left = _resolve_source(
        left_bytes, file_left.filename if file_left else None, cache_id_left
    )
    df_right = _resolve_source(
        right_bytes, file_right.filename if file_right else None, cache_id_right
    )

    parsed_keys = [c.strip() for c in key_cols.split(",")] if key_cols else None
    result, stats = _perform_join(df_left, df_right, join_type, parsed_keys, dedup)

    return {
        "preview": result.head(50).to_dict(orient="records"),
        "columns": list(result.columns),
        "left_columns": list(df_left.columns),
        "right_columns": list(df_right.columns),
        "shape": {"rows": len(result), "cols": len(result.columns)},
        "left_shape": {"rows": len(df_left), "cols": len(df_left.columns)},
        "right_shape": {"rows": len(df_right), "cols": len(df_right.columns)},
        "join_stats": stats,
    }


@app.post("/join/run")
async def join_run_endpoint(
    file_left: UploadFile | None = File(None),
    file_right: UploadFile | None = File(None),
    cache_id_left: str | None = Query(None),
    cache_id_right: str | None = Query(None),
    join_type: str = Query(..., pattern="^(inner|left|right|outer|union)$"),
    key_cols: str | None = Query(
        None, description="Comma-separated key column names (horizontal joins)"
    ),
    dedup: bool = Query(False, description="Remove duplicate rows after union"),
):
    """Execute a full join and cache the result. Returns cache_id for download or EDA."""
    left_bytes = (await file_left.read()) if file_left else None
    right_bytes = (await file_right.read()) if file_right else None

    df_left = _resolve_source(
        left_bytes, file_left.filename if file_left else None, cache_id_left
    )
    df_right = _resolve_source(
        right_bytes, file_right.filename if file_right else None, cache_id_right
    )

    parsed_keys = [c.strip() for c in key_cols.split(",")] if key_cols else None
    result, stats = _perform_join(df_left, df_right, join_type, parsed_keys, dedup)

    cache_id = _cache_cleaned(result)
    return {
        "cache_id": cache_id,
        "shape": {"rows": len(result), "cols": len(result.columns)},
        "join_stats": stats,
    }


# --- ML NAMESPACE ---------------------------------------------------------------


@app.post("/ml/suggest")
async def ml_suggest_endpoint(
    cache_id: str = Query(..., description="UUID from /clean/run or /join/run"),
):
    """Flag anomalous rows and suggest corrections using IsolationForest."""
    entry = _cleaned_cache.get(cache_id)
    if entry is None:
        raise HTTPException(
            404, "cache_id not found — run /clean/run first or check the UUID"
        )
    result = flag_anomalies(entry["df"])
    return JSONResponse(content=json_safe(result))


# --- REPORT NAMESPACE -----------------------------------------------------------


@app.post("/report/pptx")
async def report_pptx_endpoint(req: ReportRequest):
    """Generate a PPTX report from EDA results and AI narrative."""
    if _cleaned_cache.get(req.cache_id) is None:
        raise HTTPException(404, "cache_id not found — run /clean/run first")
    data = build_pptx_bytes(req.eda_result, req.narrative, kpi_result=req.kpi_result)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": 'attachment; filename="SmartDQC_Report.pptx"'},
    )


@app.post("/report/pdf")
async def report_pdf_endpoint(req: ReportRequest):
    """Generate a PDF report from EDA results and AI narrative."""
    if _cleaned_cache.get(req.cache_id) is None:
        raise HTTPException(404, "cache_id not found — run /clean/run first")
    data = build_pdf_bytes(req.eda_result, req.narrative, kpi_result=req.kpi_result)
    _log_audit(action="report.pdf", detail=f"cache_id={req.cache_id}")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="SmartDQC_Report.pdf"'},
    )


# --- RISK NAMESPACE -------------------------------------------------------------


@app.post("/risk/score")
async def risk_score_endpoint(
    cache_id: str = Query(..., description="UUID from /clean/run or /join/run"),
):
    """Compute per-child composite risk score (0-100) and district aggregation."""
    entry = _cleaned_cache.get(cache_id)
    if entry is None:
        raise HTTPException(
            404, "cache_id not found — run /clean/run first or check the UUID"
        )
    result = compute_risk_scores(entry["df"])
    return JSONResponse(content=json_safe(result))


class ForecastRequest(BaseModel):
    records: list[dict]


@app.post("/risk/forecast")
async def risk_forecast(req: ForecastRequest):
    """Compute next-quarter district risk forecast from historical zscore_archive records."""
    return forecast_district_risk(req.records)


# --- KPI NAMESPACE --------------------------------------------------------------


@app.post("/kpi/dashboard")
async def kpi_dashboard_endpoint(
    cache_id: str = Query(..., description="UUID from /clean/run or /join/run"),
):
    """Return RAG traffic-light KPI status benchmarked against Malaysian national targets."""
    entry = _cleaned_cache.get(cache_id)
    if entry is None:
        raise HTTPException(
            404, "cache_id not found — run /clean/run first or check the UUID"
        )
    result = compute_kpi_dashboard(entry["df"])
    return JSONResponse(content=json_safe(result))


class TrajectoryRequest(BaseModel):
    historical_snapshots: list[dict]
    current_breakdown: list[dict] = []


@app.post("/kpi/trajectory")
async def kpi_trajectory(req: TrajectoryRequest):
    """Compute per-district trajectory narratives and 2027 target forecast from indicator snapshots."""
    return compute_trajectory_narratives(
        req.historical_snapshots, req.current_breakdown
    )


# ── Data Quality Report (5-tab Excel) ────────────────────────────────────────


def _build_quality_report(df: pd.DataFrame, stats: dict, data_type: str) -> io.BytesIO:
    """Build a multi-tab Excel data quality report from cleaned data + cleaning stats."""
    from datetime import datetime
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    raw = stats.get("raw_count", 0)
    final = stats.get("final_count", len(df))

    def pct(n, base):
        return f"{n / base * 100:.2f}%" if base else "0%"

    def _style_sheet(ws, header_row=1, freeze_row=2):
        hdr_font = Font(bold=True, color="FFFFFF", size=11)
        hdr_fill = PatternFill(
            start_color="2F5496", end_color="2F5496", fill_type="solid"
        )
        thin_border = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin"),
        )
        for cell in ws[header_row]:
            cell.font = hdr_font
            cell.fill = hdr_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border
        for row in ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row):
            for cell in row:
                cell.border = thin_border
        for col_idx in range(1, ws.max_column + 1):
            letter = get_column_letter(col_idx)
            max_len = 0
            for cell in ws[letter]:
                try:
                    max_len = max(max_len, len(str(cell.value or "")))
                except Exception:
                    pass
            ws.column_dimensions[letter].width = min(max_len + 4, 45)
        ws.freeze_panes = ws.cell(row=freeze_row, column=1)

    # Rule-level stats
    dropped_gender = stats.get("dropped_invalid_gender", 0)
    dropped_dob = stats.get("dropped_date_before_dob", 0)
    dropped_age = stats.get("dropped_age_over5", stats.get("dropped_age_invalid", 0))
    dropped_outlier = stats.get("dropped_measurement_outlier", 0)
    dropped_bmi = stats.get("dropped_bmi_outlier", 0)
    dropped_no_meas = stats.get("dropped_no_measurement", 0)
    dropped_zscore = stats.get("dropped_null_zscore", 0)

    rules_ordered = [
        ("Rule 1", "Jantina 'Others'", dropped_gender),
        ("Rule 4", "Assessment before DOB", dropped_dob),
        ("Rule 3", "Age > 5 years", dropped_age),
        ("Rule 2", "Measurement outliers", dropped_outlier),
        ("Rule 5", "Implausible BMI > 40", dropped_bmi),
        ("Rule 6", "No measurement (both null)", dropped_no_meas),
        ("Rule 7", "Null z-score(s)", dropped_zscore),
    ]

    # TAB 1 — Executive Summary
    exec_rows = [
        [f"{data_type.upper()} \u2014 DATA QUALITY REPORT", "", "", ""],
        [f"Generated: {datetime.now().strftime('%d %B %Y  %H:%M')}", "", "", ""],
        [],
        ["Metric", "Count", "% of Raw", "Notes"],
        ["Raw records (before cleaning)", raw, "100%", "Source CSV"],
    ]
    for rule_id, label, count in rules_ordered:
        exec_rows.append([f"Dropped \u2014 {label}", count, pct(count, raw), rule_id])
    exec_rows.append(
        ["Final cleaned records", final, pct(final, raw), "After all rules"]
    )
    exec_rows.append([])

    # WAZ distribution
    exec_rows.append(["WAZ \u2014 Weight-for-Age", "Count", "% of Cleaned", ""])
    if "WAZ_Status" in df.columns:
        waz_vc = df["WAZ_Status"].value_counts()
        for code, label in [
            ("berat_badan_normal", "Berat Badan Normal"),
            ("risiko_kurang_berat_badan", "Risiko Kurang Berat Badan"),
            ("kurang_berat_badan", "Kurang Berat Badan"),
            ("kurang_berat_badan_teruk", "Kurang Berat Badan Teruk"),
            ("mungkin_masalah_pertumbuhan", "Mungkin Masalah Pertumbuhan"),
        ]:
            cnt = int(waz_vc.get(code, 0))
            exec_rows.append([label, cnt, pct(cnt, final), ""])
    exec_rows.append([])

    # HAZ distribution
    exec_rows.append(["HAZ \u2014 Height-for-Age", "Count", "% of Cleaned", ""])
    if "HAZ_Status" in df.columns:
        haz_vc = df["HAZ_Status"].value_counts()
        for code, label in [
            ("normal", "Panjang/Tinggi Normal"),
            ("risiko_bantut", "Risiko Bantut"),
            ("bantut", "Bantut"),
            ("bantut_teruk", "Bantut Teruk"),
            ("mungkin_masalah_endokrin", "Mungkin Masalah Endokrin"),
        ]:
            cnt = int(haz_vc.get(code, 0))
            exec_rows.append([label, cnt, pct(cnt, final), ""])
    exec_rows.append([])

    # BAZ distribution
    exec_rows.append(["BAZ \u2014 BMI-for-Age", "Count", "% of Cleaned", ""])
    if "BAZ_Status" in df.columns:
        baz_vc = df["BAZ_Status"].value_counts()
        for code, label in [
            ("normal", "Berat Badan Normal"),
            ("berisiko_susut", "Berisiko Susut"),
            ("susut", "Susut"),
            ("susut_teruk", "Susut Teruk"),
            ("risiko_lebih_berat_badan", "Risiko Lebih Berat Badan"),
            ("berlebihan_berat_badan", "Berlebihan Berat Badan"),
            ("obes", "Obes"),
        ]:
            cnt = int(baz_vc.get(code, 0))
            exec_rows.append([label, cnt, pct(cnt, final), ""])
    exec_rows.append([])
    if "Kategori_Umur" in df.columns:
        bawah2 = int((df["Kategori_Umur"] == "Bawah 2 Tahun").sum())
        bawah5 = int((df["Kategori_Umur"] == "Bawah 5 Tahun").sum())
    elif "Age_Months" in df.columns:
        age_m = pd.to_numeric(df["Age_Months"], errors="coerce")
        bawah2 = int((age_m < 24).sum())
        bawah5 = int(((age_m >= 24) & (age_m < 60)).sum())
    else:
        bawah2, bawah5 = 0, final
    exec_rows.append(["Age Group", "Count", "% of Cleaned", "Definition"])
    exec_rows.append(["Bawah 2 Tahun", bawah2, pct(bawah2, final), "0 \u2013 23 bulan"])
    exec_rows.append(
        ["Bawah 5 Tahun", bawah5, pct(bawah5, final), "24 \u2013 59 bulan"]
    )

    # TAB 2 — Cleaning Rules
    rules_detail = [
        ["CLEANING RULES APPLIED", "", "", "", "", ""],
        [],
        ["Rule", "Column(s)", "Condition", "Action", "Rows Affected", "% of Raw"],
        [
            "Rule 1",
            "Jantina",
            "Jantina = 'Others'",
            "Drop row",
            dropped_gender,
            pct(dropped_gender, raw),
        ],
        [
            "Rule 2",
            "Berat / Panjang",
            "Berat \u2264 0.5 or > 35.0 kg | Panjang \u2264 30.0 or > 130.0 cm",
            "Drop row",
            dropped_outlier,
            pct(dropped_outlier, raw),
        ],
        [
            "Rule 3",
            "Tarikh Lahir / Tarikh Antropometri",
            "Age at assessment \u2265 60 months (> 5 years)",
            "Drop row",
            dropped_age,
            pct(dropped_age, raw),
        ],
        [
            "Rule 4",
            "Tarikh Lahir / Tarikh Antropometri",
            "Tarikh Antropometri < Tarikh Lahir",
            "Drop row",
            dropped_dob,
            pct(dropped_dob, raw),
        ],
        [
            "Rule 5",
            "Berat + Panjang",
            "BMI > 40.0 (implausible weight/height combination)",
            "Drop row",
            dropped_bmi,
            pct(dropped_bmi, raw),
        ],
        [
            "Rule 6",
            "Berat + Panjang",
            "Both weight AND height are NULL",
            "Drop row",
            dropped_no_meas,
            pct(dropped_no_meas, raw),
        ],
        [
            "Rule 7",
            "WAZ / HAZ / BAZ",
            "Any z-score is NULL after computation",
            "Drop row",
            dropped_zscore,
            pct(dropped_zscore, raw),
        ],
    ]

    # TAB 3 — Records Dropped
    dropped_rows = [
        ["RECORDS DROPPED \u2014 Summary by Rule", "", ""],
        [],
        ["Rule", "Records Dropped", "Cumulative Remaining"],
    ]
    cumulative = raw
    for rule_id, label, count in rules_ordered:
        if count > 0:
            cumulative -= count
            dropped_rows.append([f"{rule_id} \u2014 {label}", count, cumulative])

    # ── Find geographic columns ────────────────────────────────────────────────
    state_col = None
    for c in df.columns:
        if c.lower() in ("state", "negeri"):
            state_col = c
            break
    if state_col is None:
        for c in df.columns:
            if "negeri" in c.lower() or "state" in c.lower():
                state_col = c
                break

    district_col = None
    for c in df.columns:
        if c.lower() in ("district", "daerah"):
            district_col = c
            break
    if district_col is None:
        for c in df.columns:
            if "daerah" in c.lower() or "district" in c.lower():
                district_col = c
                break

    # ── Helper: build pivot table (4 sections) for one z-score indicator ──────
    age_cats = ["Bawah 2 Tahun", "Bawah 5 Tahun"]

    def _build_pivot_tab(
        geo_col, geo_label, status_col, detail_labels, combine_map, combine_order, title
    ):
        """
        Build rows for one pivot tab.
        detail_labels: ordered list of classification codes
        combine_map: dict mapping combined_label -> list of codes to merge
        combine_order: ordered list of combined labels
        """
        rows_out = []
        if geo_col is None or geo_col not in df.columns or status_col not in df.columns:
            rows_out.append([f"(No {geo_label} or {status_col} column found)"])
            return rows_out

        # Ensure Kategori_Umur exists
        if "Kategori_Umur" not in df.columns:
            return [[f"(No Kategori_Umur column found)"]]

        # --- SECTION 1: Detailed Count ---
        hdr1 = [f"Count of {status_col}", "Column Labels"]
        for lbl in detail_labels:
            hdr1.extend(["", "", ""])
        rows_out.append(hdr1)

        sub_hdr1_1 = [f"", ""]
        for lbl in detail_labels:
            sub_hdr1_1.extend([lbl, "", f"{lbl} Total"])
        rows_out.append(sub_hdr1_1)

        sub_hdr1_2 = ["Row Labels", ""]
        for lbl in detail_labels:
            sub_hdr1_2.extend(["Bawah 2 Tahun", "Bawah 5 Tahun", ""])
        rows_out.append(sub_hdr1_2)

        # Group data
        grouped = (
            df.groupby([geo_col, "Kategori_Umur", status_col])
            .size()
            .reset_index(name="count")
        )
        geo_totals = df.groupby(geo_col).size()

        detail_data = []
        for geo_name in sorted(df[geo_col].dropna().unique()):
            row = [str(geo_name), int(geo_totals.get(geo_name, 0))]
            grp = grouped[grouped[geo_col] == geo_name]
            for lbl in detail_labels:
                for age_cat in age_cats:
                    mask = (grp["Kategori_Umur"] == age_cat) & (grp[status_col] == lbl)
                    val = int(grp.loc[mask, "count"].sum())
                    row.append(val)
                # Total for this classification
                mask_all = grp[status_col] == lbl
                row.append(int(grp.loc[mask_all, "count"].sum()))
            detail_data.append(row)

        # Sort by total descending
        detail_data.sort(key=lambda x: x[1], reverse=True)
        for row in detail_data:
            rows_out.append(row)

        # Grand Total row
        grand = ["Grand Total", len(df)]
        for lbl in detail_labels:
            for age_cat in age_cats:
                mask = (grouped["Kategori_Umur"] == age_cat) & (
                    grouped[status_col] == lbl
                )
                grand.append(int(grouped.loc[mask, "count"].sum()))
            mask_all = grouped[status_col] == lbl
            grand.append(int(grouped.loc[mask_all, "count"].sum()))
        rows_out.append(grand)
        rows_out.append([])

        # --- SECTION 2: Detailed Percentage ---
        rows_out.append([f"Count of {status_col}", "Column Labels"])
        rows_out.append(sub_hdr1_1)
        sub_pct = ["Row Labels", ""]
        for lbl in detail_labels:
            sub_pct.extend(["Bawah 2 Tahun", "Bawah 5 Tahun", ""])
        rows_out.append(sub_pct)

        for row in detail_data:
            geo_name = row[0]
            total = row[1]
            pct_row = [geo_name, ""]
            idx = 2
            for lbl in detail_labels:
                for _ in age_cats:
                    pct_row.append(f"{row[idx] / total * 100:.2f}%" if total else "0%")
                    idx += 1
                pct_row.append(f"{row[idx] / total * 100:.2f}%" if total else "0%")
                idx += 1
            rows_out.append(pct_row)

        # Grand total pct
        g_total = grand[1]
        gpct = ["Grand Total", ""]
        idx = 2
        for lbl in detail_labels:
            for _ in age_cats:
                gpct.append(f"{grand[idx] / g_total * 100:.2f}%" if g_total else "0%")
                idx += 1
            gpct.append(f"{grand[idx] / g_total * 100:.2f}%" if g_total else "0%")
            idx += 1
        rows_out.append(gpct)
        rows_out.append([])

        # --- SECTION 3: Combined Count ---
        rows_out.append(
            [f"Count of {status_col.replace('_Status', '_COMBINE')}", "Column Labels"]
        )
        sub_c1 = ["", ""]
        for clbl in combine_order:
            sub_c1.extend([clbl, "", f"{clbl} Total"])
        sub_c1.append("Grand Total")
        rows_out.append(sub_c1)

        sub_c2 = ["Row Labels", ""]
        for clbl in combine_order:
            sub_c2.extend(["Bawah 2 Tahun", "Bawah 5 Tahun", ""])
        sub_c2.append("")
        rows_out.append(sub_c2)

        combine_data = []
        for row in detail_data:
            geo_name = row[0]
            total = row[1]
            crow = [geo_name, ""]
            for clbl in combine_order:
                codes = combine_map[clbl]
                for age_cat in age_cats:
                    s = 0
                    idx_base = 2
                    for i, lbl in enumerate(detail_labels):
                        if lbl in codes:
                            age_idx = age_cats.index(age_cat)
                            s += row[idx_base + i * (len(age_cats) + 1) + age_idx]
                    crow.append(s)
                # Total
                s_total = 0
                idx_base = 2
                for i, lbl in enumerate(detail_labels):
                    if lbl in codes:
                        s_total += row[
                            idx_base + i * (len(age_cats) + 1) + len(age_cats)
                        ]
                crow.append(s_total)
            crow.append(total)
            combine_data.append(crow)

        for crow in combine_data:
            rows_out.append(crow)

        # Grand total combined
        gcrow = ["Grand Total", ""]
        g_total = grand[1]
        for clbl in combine_order:
            codes = combine_map[clbl]
            for age_cat in age_cats:
                s = 0
                idx_base = 2
                for i, lbl in enumerate(detail_labels):
                    if lbl in codes:
                        age_idx = age_cats.index(age_cat)
                        s += grand[idx_base + i * (len(age_cats) + 1) + age_idx]
                gcrow.append(s)
            s_total = 0
            idx_base = 2
            for i, lbl in enumerate(detail_labels):
                if lbl in codes:
                    s_total += grand[idx_base + i * (len(age_cats) + 1) + len(age_cats)]
            gcrow.append(s_total)
        gcrow.append(g_total)
        rows_out.append(gcrow)
        rows_out.append([])

        # --- SECTION 4: Combined Percentage ---
        rows_out.append(
            [f"Count of {status_col.replace('_Status', '_COMBINE')}", "Column Labels"]
        )
        rows_out.append(sub_c1)
        rows_out.append(sub_c2)

        for crow in combine_data:
            geo_name = crow[0]
            total = crow[-1]
            cpct = [geo_name, ""]
            idx = 2
            for clbl in combine_order:
                for _ in age_cats:
                    cpct.append(f"{crow[idx] / total * 100:.2f}%" if total else "0%")
                    idx += 1
                cpct.append(f"{crow[idx] / total * 100:.2f}%" if total else "0%")
                idx += 1
            cpct.append("100.00%")
            rows_out.append(cpct)

        gcpct = ["Grand Total", ""]
        idx = 2
        for clbl in combine_order:
            for _ in age_cats:
                gcpct.append(f"{gcrow[idx] / g_total * 100:.2f}%" if g_total else "0%")
                idx += 1
            gcpct.append(f"{gcrow[idx] / g_total * 100:.2f}%" if g_total else "0%")
            idx += 1
        gcpct.append("100.00%")
        rows_out.append(gcpct)

        return rows_out

    # ── WAZ config ─────────────────────────────────────────────────────────────
    waz_detail = [
        "kurang_berat_badan_teruk",
        "kurang_berat_badan",
        "risiko_kurang_berat_badan",
        "berat_badan_normal",
        "mungkin_masalah_pertumbuhan",
    ]
    waz_combine = {
        "Kurang Berat Badan": ["kurang_berat_badan_teruk", "kurang_berat_badan"],
        "risiko_kurang_berat_badan": ["risiko_kurang_berat_badan"],
        "berat_badan_normal": ["berat_badan_normal"],
        "mungkin_masalah_pertumbuhan": ["mungkin_masalah_pertumbuhan"],
    }
    waz_combine_order = [
        "Kurang Berat Badan",
        "risiko_kurang_berat_badan",
        "berat_badan_normal",
        "mungkin_masalah_pertumbuhan",
    ]

    # ── HAZ config ─────────────────────────────────────────────────────────────
    haz_detail = [
        "bantut_teruk",
        "bantut",
        "risiko_bantut",
        "normal",
        "mungkin_masalah_endokrin",
    ]
    haz_combine = {
        "Bantut": ["bantut_teruk", "bantut"],
        "risiko_bantut": ["risiko_bantut"],
        "normal": ["normal"],
        "mungkin_masalah_endokrin": ["mungkin_masalah_endokrin"],
    }
    haz_combine_order = [
        "Bantut",
        "risiko_bantut",
        "normal",
        "mungkin_masalah_endokrin",
    ]

    # ── BAZ config ─────────────────────────────────────────────────────────────
    baz_detail = [
        "susut_teruk",
        "susut",
        "berisiko_susut",
        "normal",
        "risiko_lebih_berat_badan",
        "berlebihan_berat_badan",
        "obes",
    ]
    baz_combine = {
        "Susut": ["susut_teruk", "susut"],
        "berisiko_susut": ["berisiko_susut"],
        "normal": ["normal"],
        "risiko_lebih_berat_badan": ["risiko_lebih_berat_badan"],
        "Berlebihan Berat Badan": ["berlebihan_berat_badan", "obes"],
    }
    baz_combine_order = [
        "Susut",
        "berisiko_susut",
        "normal",
        "risiko_lebih_berat_badan",
        "Berlebihan Berat Badan",
    ]

    # Build pivot tabs
    waz_negeri = _build_pivot_tab(
        state_col,
        "Negeri",
        "WAZ_Status",
        waz_detail,
        waz_combine,
        waz_combine_order,
        "WAZ Negeri",
    )
    waz_daerah = _build_pivot_tab(
        district_col,
        "Daerah",
        "WAZ_Status",
        waz_detail,
        waz_combine,
        waz_combine_order,
        "WAZ Daerah",
    )
    haz_negeri = _build_pivot_tab(
        state_col,
        "Negeri",
        "HAZ_Status",
        haz_detail,
        haz_combine,
        haz_combine_order,
        "HAZ Negeri",
    )
    haz_daerah = _build_pivot_tab(
        district_col,
        "Daerah",
        "HAZ_Status",
        haz_detail,
        haz_combine,
        haz_combine_order,
        "HAZ Daerah",
    )
    baz_negeri = _build_pivot_tab(
        state_col,
        "Negeri",
        "BAZ_Status",
        baz_detail,
        baz_combine,
        baz_combine_order,
        "BAZ Negeri",
    )
    baz_daerah = _build_pivot_tab(
        district_col,
        "Daerah",
        "BAZ_Status",
        baz_detail,
        baz_combine,
        baz_combine_order,
        "BAZ Daerah",
    )

    # Write workbook
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(exec_rows).to_excel(
            writer, sheet_name="Executive Summary", index=False, header=False
        )
        _style_sheet(writer.sheets["Executive Summary"], header_row=4, freeze_row=5)

        pd.DataFrame(rules_detail).to_excel(
            writer, sheet_name="Cleaning Rules", index=False, header=False
        )
        _style_sheet(writer.sheets["Cleaning Rules"], header_row=3, freeze_row=4)

        pd.DataFrame(dropped_rows).to_excel(
            writer, sheet_name="Records Dropped", index=False, header=False
        )
        _style_sheet(writer.sheets["Records Dropped"], header_row=3, freeze_row=4)

        # 6 pivot tabs
        pivot_tabs = [
            ("WAZ Negeri", waz_negeri),
            ("WAZ Daerah", waz_daerah),
            ("HAZ Negeri", haz_negeri),
            ("HAZ Daerah", haz_daerah),
            ("BAZ Negeri", baz_negeri),
            ("BAZ Daerah", baz_daerah),
        ]
        for sheet_name, rows_data in pivot_tabs:
            pd.DataFrame(rows_data).to_excel(
                writer, sheet_name=sheet_name, index=False, header=False
            )
            ws = writer.sheets[sheet_name]
            # Style header rows and section dividers
            for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
                val = str(row[0].value or "")
                if val.startswith("Count of"):
                    for cell in row:
                        cell.font = Font(bold=True, size=12, color="1F3864")
                if val in ("Row Labels", ""):
                    first_val = str(row[1].value or "") if len(row) > 1 else ""
                    if first_val in ("Column Labels", ""):
                        pass
                if val == "Row Labels":
                    for cell in row:
                        cell.font = Font(bold=True, color="FFFFFF", size=10)
                        cell.fill = PatternFill(
                            start_color="2F5496", end_color="2F5496", fill_type="solid"
                        )
                        cell.alignment = Alignment(horizontal="center")
                if val == "Grand Total":
                    for cell in row:
                        cell.font = Font(bold=True)

        title_font = Font(bold=True, size=14, color="1F3864")
        for ws in writer.sheets.values():
            if ws.cell(1, 1).value:
                ws.cell(1, 1).font = title_font

    output.seek(0)
    return output


@app.get("/clean/download-report/{cache_id}")
async def download_report_endpoint(
    cache_id: str,
    data_type: str = Query("myvass"),
):
    """Download Data Quality Report (5-tab Excel) from cached cleaning results."""
    entry = _cleaned_cache.get(cache_id)
    if entry is None:
        raise HTTPException(404, "Cached data not found \u2014 please re-run cleaning.")

    cleaned_df = entry["df"]
    stats = entry["stats"]
    timestamp = pd.Timestamp.now().strftime("%Y%m%d")
    report_buf = _build_quality_report(cleaned_df, stats, data_type)

    return StreamingResponse(
        iter([report_buf.read()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{data_type.upper()}_Data_Quality_Report_{timestamp}.xlsx"'
        },
    )


# ─── AI ENDPOINTS ─────────────────────────────────────────────────────────────


class ReportRequest(BaseModel):
    cache_id: str
    eda_result: dict
    narrative: dict = {}
    kpi_result: dict | None = None


class NarrativeRequest(BaseModel):
    session_id: str
    eda_result: dict


class NLQRequest(BaseModel):
    session_id: str
    query: str


@app.post("/ai/narrative")
async def ai_narrative(req: NarrativeRequest, db: SASession = Depends(get_db)):
    """Generate AI narrative (insights + recommendations) from EDA results."""
    try:
        narrative = generate_narrative(req.eda_result)
    except Exception as e:
        raise HTTPException(500, f"Narrative generation failed: {e}")

    now = datetime.utcnow()
    PLACEHOLDER_DATASET_ID = "00000000-0000-0000-0000-000000000000"
    try:
        if not db.get(Dataset, PLACEHOLDER_DATASET_ID):
            db.add(
                Dataset(
                    id=PLACEHOLDER_DATASET_ID,
                    name="__placeholder__",
                    filename="__placeholder__",
                    created_at=now,
                )
            )
        if not db.get(DBSession, req.session_id):
            db.add(
                DBSession(
                    id=req.session_id,
                    dataset_id=PLACEHOLDER_DATASET_ID,
                    notes=None,
                    created_at=now,
                    updated_at=now,
                )
            )
        db.add(
            AnalysisResult(
                id=str(uuid.uuid4()),
                session_id=req.session_id,
                result_type="narrative",
                result_json=narrative,
                created_at=now,
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to persist analysis_result: %s", exc)

    return narrative


@app.post("/ai/nlq")
async def ai_nlq(req: NLQRequest):
    """Answer a natural language query against the cleaned dataset for a session."""
    entry = _cleaned_cache.get(req.session_id)
    if entry is None:
        raise HTTPException(
            404, "Session not found in cache — please re-run cleaning first."
        )

    df = entry["df"]
    try:
        result = answer_query(req.query, df)
    except Exception as e:
        raise HTTPException(500, f"NLQ failed: {e}")

    return result


# ── Multi-Dataset Comparison ─────────────────────────────────────────────────

from backend.eda.compare import compare_datasets, _INDICATOR_KEYS


@app.get("/datasets")
async def list_datasets():
    """List all datasets in the library."""
    from backend.db.models import Dataset
    from backend.db.init_db import SessionLocal

    with SessionLocal() as db:
        datasets = db.query(Dataset).order_by(Dataset.created_at.desc()).all()
        return [
            {
                "id": ds.id,
                "name": ds.name,
                "filename": ds.filename,
                "source_type": ds.source_type,
                "row_count": ds.row_count,
                "created_at": ds.created_at.isoformat(),
            }
            for ds in datasets
        ]


class DatasetCompareRequest(BaseModel):
    dataset_ids: list[str]


@app.post("/datasets/compare")
async def datasets_compare(req: DatasetCompareRequest):
    """Compare 2+ datasets side-by-side. Returns quality and indicator deltas."""
    from backend.db.models import Dataset, AnalysisResult
    from backend.db.init_db import SessionLocal

    if len(req.dataset_ids) < 2:
        raise HTTPException(400, "Provide at least 2 dataset_ids.")

    summaries = []
    with SessionLocal() as db:
        for ds_id in req.dataset_ids:
            ds = db.get(Dataset, ds_id)
            if ds is None:
                continue
            ar = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.dataset_id == ds_id)
                .order_by(AnalysisResult.created_at.desc())
                .first()
            )
            quality_score = None
            indicators = {}
            if ar and ar.result_json:
                rj = ar.result_json
                quality_score = rj.get("quality", {}).get("overall_score")
                ind = rj.get("indicators", {})
                for k in _INDICATOR_KEYS:
                    if k in ind:
                        indicators[k] = ind[k]
            summaries.append(
                {
                    "dataset_id": ds_id,
                    "source_type": ds.source_type or "unknown",
                    "quality_score": quality_score,
                    "indicators": indicators,
                    "name": ds.name,
                    "created_at": ds.created_at.isoformat(),
                }
            )

    return compare_datasets(summaries)


# ── Entity Resolution ────────────────────────────────────────────────────────

from backend.ml.entity import link_records, persist_linkage


class EntityLinkRequest(BaseModel):
    dataset_ids: list[str]


@app.post("/entity/link")
async def entity_link(req: EntityLinkRequest):
    """Link child records across 2+ datasets by IC. Writes to entity_linkage table."""
    from backend.db.models import Dataset, AnalysisResult
    from backend.db.init_db import SessionLocal

    if len(req.dataset_ids) < 2:
        raise HTTPException(400, "Provide at least 2 dataset_ids to link.")

    records = []
    with SessionLocal() as db:
        for ds_id in req.dataset_ids:
            ds = db.get(Dataset, ds_id)
            if ds is None:
                continue
            ar = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.dataset_id == ds_id)
                .order_by(AnalysisResult.created_at.desc())
                .first()
            )
            if ar is None or not ar.result_json:
                continue
            summary = ar.result_json.get("summary", {})
            records.append(
                {
                    "ic": summary.get("ic", ""),
                    "source_type": ds.source_type or "unknown",
                    "dataset_id": ds_id,
                    "name": summary.get("name", ""),
                    "dob": summary.get("dob", ""),
                }
            )

        groups = link_records(records)
        rows_written = persist_linkage(groups, db)

    linked = [g for g in groups if len(g["sources"]) > 1]
    unlinked = [g for g in groups if len(g["sources"]) == 1]
    return {
        "total_groups": len(groups),
        "linked_groups": len(linked),
        "unlinked": len(unlinked),
        "rows_written": rows_written,
        "profiles": linked[:50],
    }


@app.get("/sessions")
def list_sessions(db=Depends(get_db)):
    """List the 100 most recent cleaned sessions persisted to the database."""
    from .db.models import Dataset

    rows = db.query(Dataset).order_by(Dataset.created_at.desc()).limit(100).all()
    return [
        {
            "cache_id": r.id,
            "filename": r.filename,
            "source_type": r.source_type,
            "row_count": r.row_count or 0,
            "quality_score": r.quality_score or 0,
        }
        for r in rows
    ]


@app.get("/audit/log")
def get_audit_log(dataset_id: int | None = None, limit: int = 100, db=Depends(get_db)):
    from .db.models import AuditLog

    q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if dataset_id is not None:
        q = q.filter(AuditLog.dataset_id == dataset_id)
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id,
            "action": r.action,
            "dataset_id": r.dataset_id,
            "detail": r.detail,
            "user_id": r.user_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ── Settings API ──────────────────────────────────────────────────────────────

import json as _json

_DEFAULT_THRESHOLDS = {
    "missing_rate_warn": 0.05,
    "missing_rate_fail": 0.15,
    "duplicate_rate_warn": 0.02,
    "duplicate_rate_fail": 0.10,
    "outlier_zscore_threshold": 3.0,
}

_DEFAULT_RULES: dict = {
    k: {"enabled": True}
    for k in [
        "duplicate_check",
        "missing_value_check",
        "ic_format_check",
        "age_range_check",
        "height_range_check",
        "weight_range_check",
        "bmi_range_check",
        "date_format_check",
        "gender_value_check",
    ]
}


def _get_setting(key: str, default, db) -> dict:
    from .db.models import AppSetting

    row = db.query(AppSetting).filter_by(key=key).first()
    if row:
        return _json.loads(row.value)
    return default


def _set_setting(key: str, value, db) -> None:
    from .db.models import AppSetting

    existing = db.query(AppSetting).filter_by(key=key).first()
    if existing:
        existing.value = _json.dumps(value)
    else:
        db.add(AppSetting(key=key, value=_json.dumps(value)))
    db.commit()


@app.get("/settings/thresholds")
def get_thresholds(db=Depends(get_db)):
    return _get_setting("threshold.all", _DEFAULT_THRESHOLDS, db)


@app.post("/settings/thresholds")
def post_thresholds(updates: dict, db=Depends(get_db)):
    current = _get_setting("threshold.all", _DEFAULT_THRESHOLDS, db)
    current.update(updates)
    _set_setting("threshold.all", current, db)
    return current


@app.get("/settings/rules")
def get_rules(db=Depends(get_db)):
    return _get_setting("rules.all", _DEFAULT_RULES, db)


@app.post("/settings/rules/toggle")
def toggle_rule(body: dict, db=Depends(get_db)):
    rule = body.get("rule")
    enabled = body.get("enabled", True)
    current = _get_setting("rules.all", _DEFAULT_RULES, db)
    if rule not in current:
        raise HTTPException(status_code=404, detail=f"Rule '{rule}' not found")
    current[rule]["enabled"] = enabled
    _set_setting("rules.all", current, db)
    return current
