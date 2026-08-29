from __future__ import annotations

from io import BytesIO
import json

from oh_my_exam.pipelines.adapters.pat.downloader.catalog import SolutionPage, parse_archive_html, parse_solution_html
from oh_my_exam.pipelines.adapters.pat.downloader.download import download_asset
from oh_my_exam.pipelines.adapters.pat.downloader.models import PatAsset


class _Response(BytesIO):
    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def test_parse_archive_html_keeps_regular_and_specimen_papers() -> None:
    html = """
    <a href="https://pmt.example/download/Admissions/PAT/Papers/PAT%202009.pdf">PAT 2009</a>
    <a href="https://pmt.example/download/Admissions/PAT/Papers/PAT%202009%20Specimen.pdf">PAT 2009 Specimen</a>
    <a href="/admissions/pat/solutions-2009/">2009 Solutions</a>
    <a href="/admissions/pat/solutions-2009-specimen/">2009 Specimen Solutions</a>
    <a href="https://pmt.example/download/Admissions/PAT/Reports/PAT%202009.pdf">report</a>
    """
    papers, pages = parse_archive_html(html, "https://www.example.test/admissions/pat/")
    assert [(asset.year, asset.variant, asset.document_type) for asset in papers] == [
        (2009, "regular", "qp"),
        (2009, "specimen", "qp"),
    ]
    assert [(page.year, page.variant) for page in pages] == [(2009, "regular"), (2009, "specimen")]
    assert papers[0].relative_pdf_path.as_posix() == "pearson_vue/admissions/pat/2009/regular/pat_2009_s1_qp.pdf"
    assert papers[1].component == "s2"


def test_parse_solution_html_extracts_embedded_pdf() -> None:
    page = SolutionPage(2024, "specimen", "https://www.example.test/admissions/pat/solutions-2024-specimen/")
    html = '<iframe src="https://pmt.example/download/Admissions/PAT/Solutions/PAT-2024-Specimen-Solutions.pdf"></iframe>'
    asset = parse_solution_html(html, page)
    assert (asset.year, asset.variant, asset.document_type) == (2024, "specimen", "ms")
    assert asset.source_url.endswith("PAT-2024-Specimen-Solutions.pdf")


def test_download_metadata_separates_exam_board_from_source_provider(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response(b"%PDF-1.7\nPAT paper\n%%EOF\n"),
    )
    asset = PatAsset(2024, "regular", "qp", "https://pmt.example/pat.pdf")

    path, status = download_asset(asset, tmp_path)

    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert status == "downloaded"
    assert metadata["exam_board"] == "pearson_vue"
    assert metadata["source_provider"] == "pmt"
