import pandas as pd
import io


def to_excel(records: list[dict], columns: list[str], base_filename: str) -> bytes:
    df = pd.DataFrame(records, columns=columns or None)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Cleaned_Data")
    buf.seek(0)
    return buf.read()


def to_csv(records: list[dict], columns: list[str]) -> bytes:
    df = pd.DataFrame(records, columns=columns or None)
    buf = io.StringIO()
    df.to_csv(buf, index=False, encoding="utf-8-sig")
    buf.seek(0)
    return buf.getvalue().encode("utf-8-sig")
