import pandas as pd
from ..config import SABAH_KAWASAN_MAP, SARAWAK_BAHAGIAN_MAP


def get_kawasan_bahagian(negeri_val, daerah_val) -> str | None:
    if pd.isna(negeri_val) or pd.isna(daerah_val):
        return None
    n = str(negeri_val).strip().lower()
    d = str(daerah_val).strip().lower()
    if n == "sabah":
        return SABAH_KAWASAN_MAP.get(d)
    elif n == "sarawak":
        return SARAWAK_BAHAGIAN_MAP.get(d)
    return None


def add_geo_columns(df: pd.DataFrame, changes: list) -> pd.DataFrame:
    """Add kawasan_bahagian column for Sabah and Sarawak records."""
    if "negeri" not in df.columns or "daerah" not in df.columns:
        return df

    df["kawasan_bahagian"] = df.apply(
        lambda r: get_kawasan_bahagian(r.get("negeri"), r.get("daerah")), axis=1
    )
    n_geo = int(df["kawasan_bahagian"].notna().sum())
    changes.append({
        "action": "kawasan_bahagian_mapped",
        "description": f"Kawasan/Bahagian Sabah & Sarawak dipetakan — {n_geo} rekod",
        "column": "kawasan_bahagian",
        "before": {}, "after": {"n_mapped": n_geo},
        "impact_pct": round(n_geo / len(df) * 100, 1) if len(df) else 0,
        "rows_affected": n_geo,
    })
    return df
