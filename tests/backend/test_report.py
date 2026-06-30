import pytest
from backend.export.report import build_pptx_bytes, build_pdf_bytes

SAMPLE_EDA = {
    "summary": {"total_rows": 1500, "source_type": "wide_multiyear"},
    "quality": {"overall_score": 0.78, "missing_rate": 0.12, "overall_completeness": 88.5},
    "indicators": {"stunting_rate": 0.24, "wasting_rate": 0.11, "underweight_rate": 0.18},
    "outliers": {"total_flagged": 43},
}

SAMPLE_NARRATIVE = {
    "executive_summary": {
        "bm": "Kadar stunting keseluruhan adalah 24% melebihi sasaran kebangsaan.",
        "en": "Overall stunting rate is 24%, exceeding the national target.",
    },
    "insights_5w1h": {
        "who":   {"bm": "Kanak-kanak berumur 0-5 tahun.", "en": "Children aged 0-5 years."},
        "what":  {"bm": "Kadar stunting tinggi.", "en": "High stunting rate."},
        "when":  {"bm": "Data 2024.", "en": "2024 data."},
        "where": {"bm": "Sabah dan Kelantan.", "en": "Sabah and Kelantan."},
        "why":   {"bm": "Kekurangan zat makanan.", "en": "Nutritional deficiency."},
        "how":   {"bm": "Standard WHO.", "en": "WHO standards."},
    },
    "recommendations": [
        {
            "action": "Increase supplementation",
            "priority": "high",
            "bm": "Tingkatkan program suplemen zat besi.",
            "en": "Increase iron supplementation programme.",
            "reasoning": "Iron deficiency is a primary driver.",
        }
    ],
}

def test_build_pptx_returns_bytes():
    data = build_pptx_bytes(SAMPLE_EDA, SAMPLE_NARRATIVE)
    assert isinstance(data, bytes)
    assert len(data) > 1000

def test_pptx_starts_with_pk_magic():
    data = build_pptx_bytes(SAMPLE_EDA, SAMPLE_NARRATIVE)
    assert data[:2] == b"PK"  # PPTX is a ZIP

def test_build_pdf_returns_bytes():
    data = build_pdf_bytes(SAMPLE_EDA, SAMPLE_NARRATIVE)
    assert isinstance(data, bytes)
    assert len(data) > 100

def test_pdf_starts_with_pdf_magic():
    data = build_pdf_bytes(SAMPLE_EDA, SAMPLE_NARRATIVE)
    assert data[:4] == b"%PDF"

def test_build_pptx_with_empty_narrative():
    data = build_pptx_bytes(SAMPLE_EDA, {})
    assert isinstance(data, bytes)

def test_build_pdf_with_empty_narrative():
    data = build_pdf_bytes(SAMPLE_EDA, {})
    assert isinstance(data, bytes)
