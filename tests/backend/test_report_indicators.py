from io import BytesIO

from pptx import Presentation

from backend.export.report import (
    _add_indicator_table_slide,
    _add_methodology_slide,
    build_pptx_bytes,
    build_pdf_bytes,
)


def _sample_kpi_result() -> dict:
    return {
        "kpis": [{"kpi": "stunting_rate", "actual": 18.5, "target": 15.0,
                  "who_target": 20.0, "status": "Amber", "who_status": "Green"}],
        "overall_status": "Amber",
        "district_breakdown": [
            {"district": "Petaling", "n_records": 100,
             "stunting_rate_rate": 18.5, "wasting_rate_rate": 3.2,
             "underweight_rate_rate": 9.1, "overweight_rate_rate": 8.0},
            {"district": "Klang", "n_records": 80,
             "stunting_rate_rate": 22.1, "wasting_rate_rate": 6.0,
             "underweight_rate_rate": 11.0, "overweight_rate_rate": 9.5},
        ],
    }


def test_add_indicator_table_slide_adds_one_slide():
    prs = Presentation()
    blank = prs.slide_layouts[6]
    _add_indicator_table_slide(prs, blank, _sample_kpi_result())
    assert len(prs.slides) == 1


def test_add_methodology_slide_adds_one_slide():
    prs = Presentation()
    blank = prs.slide_layouts[6]
    _add_methodology_slide(prs, blank)
    assert len(prs.slides) == 1


def test_build_pptx_with_kpi_result_has_six_slides():
    eda  = {"summary": {"source_type": "myvass", "total_rows": 100},
            "quality": {}, "indicators": {}, "outliers": {}}
    narr = {"executive_summary": {"bm": "ujian", "en": "test"}, "recommendations": []}
    data = build_pptx_bytes(eda, narr, kpi_result=_sample_kpi_result())
    prs  = Presentation(BytesIO(data))
    # 4 original slides + indicator table + methodology = 6
    assert len(prs.slides) == 6


def test_build_pdf_with_kpi_result_is_valid_pdf():
    eda  = {"summary": {"source_type": "myvass", "total_rows": 100},
            "quality": {}, "indicators": {}, "outliers": {}}
    narr = {"executive_summary": {"bm": "ujian", "en": "test"}, "recommendations": []}
    data = build_pdf_bytes(eda, narr, kpi_result=_sample_kpi_result())
    assert data[:4] == b"%PDF"
