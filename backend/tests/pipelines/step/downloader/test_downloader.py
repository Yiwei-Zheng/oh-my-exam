from __future__ import annotations

from io import BytesIO
import json

from oh_my_exam.pipelines.adapters.step.downloader.catalog import parse_archive_html
from oh_my_exam.pipelines.adapters.step.downloader.download import _pdf_looks_complete, download_asset, download_assets
from oh_my_exam.pipelines.adapters.step.downloader.models import StepAsset


class _Response(BytesIO):
    headers: dict[str, str] = {}

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def test_parse_archive_html_selects_regular_papers_and_best_pairable_answers() -> None:
    html = """
    <a href="/download/Admissions/STEP/Papers/1987%20STEP%201%20-%20Maths.pdf">1987 STEP 1 - Maths</a>
    <a href="/download/Admissions/STEP/Papers/1987%20Specimen%20STEP%201%20-%20Maths.pdf">specimen</a>
    <a href="/download/Admissions/STEP/Papers/2019%20STEP%202.pdf">2019 STEP 2</a>
    <a href="/download/Admissions/STEP/Solutions-and-Reports/2019%20STEP%202%20Examiners%27%20Report.pdf">report</a>
    <a href="/download/Admissions/STEP/Solutions-and-Reports/2019%20STEP%202%20Mark%20Scheme.pdf">mark scheme</a>
    <a href="/download/Admissions/STEP/Solutions-and-Reports/2019%20STEP%202%20Solutions.pdf">solutions</a>
    <a href="/download/Admissions/STEP/Solutions-and-Reports/2017%20Solutions.pdf">year bundle</a>
    <a href="/download/Admissions/STEP/Solutions-and-Reports/2004%20Hints%20and%20Answers.pdf">old answer bundle</a>
    """
    assets = parse_archive_html(html, "https://example.test/admissions/step/")
    assert [(asset.year, asset.paper, asset.document_type) for asset in assets] == [
        (1987, 1, "qp"),
        (2004, 1, "ms"),
        (2004, 2, "ms"),
        (2004, 3, "ms"),
        (2017, 1, "ms"),
        (2017, 2, "ms"),
        (2017, 3, "ms"),
        (2019, 2, "ms"),
        (2019, 2, "qp"),
    ]
    assert assets[1].contains_papers == (1, 2, 3)
    assert assets[-2].source_url.endswith("2019%20STEP%202%20Solutions.pdf")
    assert assets[0].relative_pdf_path.as_posix() == "ocr/admissions/step/1987/archive/step_1987_s1_qp.pdf"


def test_pdf_completeness_rejects_truncated_file(tmp_path) -> None:
    complete = tmp_path / "complete.pdf"
    complete.write_bytes(b"%PDF-1.7\nbody\n%%EOF\n")
    truncated = tmp_path / "truncated.pdf"
    truncated.write_bytes(b"%PDF-1.7\nbody without trailer")

    assert _pdf_looks_complete(complete)
    assert not _pdf_looks_complete(truncated)


def test_download_metadata_separates_exam_board_from_source_provider(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *_args, **_kwargs: _Response(b"%PDF-1.7\nSTEP paper\n%%EOF\n"),
    )
    asset = StepAsset(2024, 2, "qp", "https://pmt.example/step.pdf")

    path, status = download_asset(asset, tmp_path)

    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert status == "downloaded"
    assert metadata["exam_board"] == "ocr"
    assert metadata["source_provider"] == "pmt"


def test_parallel_download_groups_reuse_shared_step_sources(tmp_path, monkeypatch) -> None:
    assets = [
        StepAsset(2017, 1, "ms", "https://pmt.example/bundle.pdf"),
        StepAsset(2017, 2, "ms", "https://pmt.example/bundle.pdf"),
        StepAsset(2024, 1, "qp", "https://pmt.example/paper.pdf"),
    ]
    reused_by_asset: dict[str, object] = {}
    progress: list[dict[str, object]] = []

    def fake_download(asset, _raw_root, *, reuse_from=None, **_kwargs):
        path = tmp_path / f"{asset.stem}.pdf"
        path.write_bytes(b"%PDF-1.7\n%%EOF\n")
        reused_by_asset[asset.stem] = reuse_from
        return path, "downloaded"

    monkeypatch.setattr(
        "oh_my_exam.pipelines.adapters.step.downloader.download.download_asset",
        fake_download,
    )

    counts = download_assets(assets, tmp_path, delay_seconds=0, workers=3, progress=progress.append)

    assert counts == {"downloaded": 3, "skipped": 0, "failed": 0}
    assert reused_by_asset["step_2017_s1_ms"] is None
    assert reused_by_asset["step_2017_s2_ms"] is not None
    assert sorted(int(item["index"]) for item in progress) == [1, 2, 3]
    assert {item["total"] for item in progress} == {3}
