from oh_my_exam.pipelines.adapters.cie_alevel.splitter.cleaning import detect_question_number, normalize_text, parse_mark_points
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.content_extraction import text_looks_unreliable


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  A   B\r\n\r\n\r\nC  ") == "A B\n\nC"


def test_detect_question_number() -> None:
    assert detect_question_number("  12 (a) Explain the result") == "12"


def test_parse_mark_points() -> None:
    points = parse_mark_points("M1 for method\nA1 correct answer\nIgnore unrelated")
    assert [point.marker for point in points] == ["M1", "A1"]


def test_rejects_symbol_font_mojibake_but_keeps_math_unicode() -> None:
    assert text_looks_unreliable("Find x when \x98 = 2")
    assert text_looks_unreliable("Use င to calculate the answer")
    assert text_looks_unreliable("I□ = ⅓mr²")
    assert not text_looks_unreliable("Integrate ∫ x² dx and show that θ = π/2")

