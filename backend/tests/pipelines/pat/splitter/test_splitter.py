from __future__ import annotations

import fitz

from oh_my_exam.pipelines.adapters.pat.splitter.cutter import Anchor, _select_anchors
from oh_my_exam.pipelines.adapters.pat.splitter.pipeline import discover_downloaded


def _anchor(number: int, page: int, x: float = 40.0) -> Anchor:
    return Anchor(number, page, fitz.Rect(x, 50, x + 12, 62), "test")


def test_modern_pat_selects_one_contiguous_sequence() -> None:
    candidates = [_anchor(1, 1), _anchor(2, 2), _anchor(3, 3), _anchor(1, 0, 250), _anchor(2, 0, 280)]
    assert [item.number for item in _select_anchors(candidates, 2020)] == [1, 2, 3]


def test_legacy_pat_flattens_two_numbered_sections() -> None:
    candidates = [_anchor(1, 1), _anchor(2, 2), _anchor(3, 3), _anchor(1, 5), _anchor(2, 6)]
    anchors = _select_anchors(candidates, 2007)
    assert [(item.number, item.page_index) for item in anchors] == [(1, 1), (2, 2), (3, 3), (1, 5), (2, 6)]


def test_2008_pat_uses_one_contiguous_sequence() -> None:
    candidates = [_anchor(number, number) for number in range(1, 6)]
    assert [item.number for item in _select_anchors(candidates, 2008)] == [1, 2, 3, 4, 5]


def test_discover_downloaded_uses_pearson_vue_board_path(tmp_path) -> None:
    pdf_path = tmp_path / "pearson_vue/admissions/pat/2024/regular/pat_2024_s1_qp.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.touch()

    assert discover_downloaded(tmp_path) == [pdf_path]
