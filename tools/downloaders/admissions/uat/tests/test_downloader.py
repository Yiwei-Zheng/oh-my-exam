from __future__ import annotations

from uat_admissions_downloader.catalog import parse_archive_html


def test_parse_archive_html_recognizes_engaa_and_nsaa_only() -> None:
    html = """
    <a href="https://cdn.test/ENGAA_2016_S1_QuestionPaper.pdf">ENGAA paper</a>
    <a href="/files/ENGAA_2016_S1_AnswerKey.pdf">ENGAA key</a>
    <a href="/files/NSAA_2023_S1_QuestionPaper.pdf">NSAA paper</a>
    <a href="/files/ESAT_Guide.pdf">Guide</a>
    """
    assets = parse_archive_html(html, "https://example.test/archive/")
    assert [(asset.exam, asset.year, asset.document_type) for asset in assets] == [
        ("engaa", 2016, "ms"),
        ("engaa", 2016, "qp"),
        ("nsaa", 2023, "qp"),
    ]
    assert assets[0].relative_pdf_path.as_posix() == "uat/admissions/engaa/2016/archive/engaa_2016_s1_ms.pdf"
