from __future__ import annotations

from uat_admissions_downloader.catalog import parse_archive_html


def test_parse_archive_html_recognizes_engaa_and_nsaa() -> None:
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


def test_parse_archive_html_recognizes_all_tmua_material_types() -> None:
    html = """
    <a href="/TMUA-2023-paper-1.pdf">paper 1</a>
    <a href="/TMUA-2023-paper-1-worked-answers.pdf">paper 1 worked answers</a>
    <a href="/TMUA-2023-paper-2.pdf">paper 2</a>
    <a href="/TMUA-2023-paper-2-worked-answers.pdf">paper 2 worked answers</a>
    <a href="/TMUA-2023-answer-keys.pdf">answer keys</a>
    <a href="/TMUA-early-specimen-paper-1.pdf">specimen paper</a>
    <a href="/TMUA-early-specimen-paper-answer-keys.pdf">specimen keys</a>
    """
    assets = parse_archive_html(html, "https://example.test/archive/")
    assert [asset.stem for asset in assets] == [
        "tmua_2023_ms",
        "tmua_2023_p1_qp",
        "tmua_2023_p1_worked_answers",
        "tmua_2023_p2_qp",
        "tmua_2023_p2_worked_answers",
        "tmua_early_specimen_ms",
        "tmua_early_specimen_p1_qp",
    ]
    assert assets[-1].relative_pdf_path.as_posix() == (
        "uat/admissions/tmua/early_specimen/archive/tmua_early_specimen_p1_qp.pdf"
    )
