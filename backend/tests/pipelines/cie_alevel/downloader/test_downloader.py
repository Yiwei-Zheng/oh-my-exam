import json
import os
from pathlib import Path

from oh_my_exam.pipelines.adapters.cie_alevel.downloader.models import PaperAsset
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.download import DownloadOutcome, download_asset
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.cambridge_catalog import CambridgeSubject, component_rules_for_subject, parse_subject_link_text, parse_subjects
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.cie import build_frank_cie_url, is_supported_frank_asset, load_assets
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.frank_discovery import (
    availability_covers_request,
    estimate_crawl_seconds,
    filter_to_available_assets,
    format_duration,
    load_availability_index,
    load_subject_availability_assets,
    save_availability_index,
    subject_availability_path,
    subjects_missing_availability,
)
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.admin_support import (
    default_manifest_path,
    load_subject_options,
    local_pdf_relative_paths,
    project_path,
    subject_download_percentage,
)
from oh_my_exam.pipelines.adapters.cie_alevel.downloader import pipeline
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.pipeline import filter_assets, migrate_raw_layout


def test_build_frank_cie_url() -> None:
    asset = PaperAsset("cie", "a_level", "9701", "Chemistry", "w24", "qp", "31")
    assert build_frank_cie_url(asset) == "https://cie.fraft.cn/obj/Common/Fetch/redir/9701_w24_qp_31.pdf"


def test_componentless_frank_asset_stem_and_url() -> None:
    asset = PaperAsset("cie", "a_level", "9709", "Mathematics", "s03", "ms", "")

    assert asset.stem == "9709_s03_ms"
    assert build_frank_cie_url(asset).endswith("/9709_s03_ms.pdf")
    assert asset.relative_pdf_path == Path("cie/a_level/9709/2003/s03/9709_s03_ms.pdf")


def test_asset_paths_include_year_above_session() -> None:
    asset = PaperAsset("cie", "a_level", "9709", "Mathematics", "s24", "qp", "11")

    assert asset.relative_pdf_path == Path("cie/a_level/9709/2024/s24/9709_s24_qp_11.pdf")
    assert asset.legacy_relative_pdf_path == Path("cie/a_level/9709/s24/9709_s24_qp_11.pdf")


def test_through_2025_manifest_expands_full_candidate_space() -> None:
    manifest = Path(__file__).parents[4] / "config" / "exams" / "cie_a_level_through_2025_manifest.json"
    assets = load_assets(manifest)
    assert assets[0].stem == "9709_m02_qp_1"
    assert assets[-1].stem == "9608_w25_ms_43"
    assert len(assets) == 15408


def test_filter_assets_by_subject_doc_and_year() -> None:
    assets = [
        PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "11"),
        PaperAsset("cie", "a_level", "9701", "Chemistry", "w25", "ms", "21"),
    ]
    filtered = filter_assets(assets, subject_codes={"9709"}, document_types={"qp"}, start_year=2024, end_year=2024)
    assert [asset.stem for asset in filtered] == ["9709_s24_qp_11"]


def test_crawl_assets_continues_after_rate_limit(monkeypatch, tmp_path: Path) -> None:
    assets = [
        PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "11"),
        PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "12"),
    ]

    def fake_try_download_asset(asset: PaperAsset, output_root: Path, *, min_delay_seconds: float = 2.0) -> DownloadOutcome:
        if asset.component == "11":
            return DownloadOutcome(asset=asset, status="rate_limited", path=None, message="HTTP 429")
        return DownloadOutcome(asset=asset, status="downloaded", path=tmp_path / "paper.pdf", message="")

    monkeypatch.setattr(pipeline, "try_download_asset", fake_try_download_asset)

    counts = pipeline.crawl_assets(assets, tmp_path, tmp_path / "report.jsonl", delay_seconds=0, max_workers=1)

    assert counts["rate_limited"] == 1
    assert counts["downloaded"] == 1


def test_crawl_assets_throttles_skipped_progress(tmp_path: Path) -> None:
    assets = [
        PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "11"),
        PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "12"),
        PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "13"),
    ]
    report = tmp_path / "report.jsonl"
    report.write_text(
        "\n".join(json.dumps({"stem": asset.stem, "status": "downloaded"}) for asset in assets),
        encoding="utf-8",
    )
    events: list[dict[str, object]] = []

    counts = pipeline.crawl_assets(
        assets,
        tmp_path,
        report,
        delay_seconds=0,
        max_workers=4,
        progress=events.append,
        skipped_progress_interval=2,
    )

    assert counts["skipped"] == 3
    assert [event["counts"]["skipped"] for event in events] == [2, 3]


def test_availability_index_filters_candidates(tmp_path: Path) -> None:
    available = [PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "11")]
    candidates = [
        PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "11"),
        PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "12"),
    ]
    index_path = tmp_path / "frank_available_assets.json"

    save_availability_index(index_path, available)

    assert [asset.stem for asset in load_availability_index(index_path)] == ["9709_s24_qp_11"]
    assert [asset.stem for asset in filter_to_available_assets(candidates, index_path)] == ["9709_s24_qp_11"]


def test_subject_availability_coverage_tracks_requested_years(tmp_path: Path) -> None:
    path = subject_availability_path("9709", availability_dir=tmp_path)
    save_availability_index(
        path,
        [PaperAsset("cie", "a_level", "9709", "Math", "s16", "qp", "11")],
        coverage=[{"subject_code": "9709", "start_year": 2010, "end_year": 2019, "seasons": ["Mar", "Jun", "Nov"]}],
    )

    assert availability_covers_request(path, subject_code="9709", start_year=2016, end_year=2019)
    assert not availability_covers_request(path, subject_code="9709", start_year=2002, end_year=2009)
    assert subjects_missing_availability({"9709", "9701"}, start_year=2016, end_year=2019, availability_dir=tmp_path) == {"9701"}
    assert [asset.stem for asset in load_subject_availability_assets({"9709"}, availability_dir=tmp_path)] == ["9709_s16_qp_11"]


def test_crawl_estimate_uses_delay_and_workers() -> None:
    assert estimate_crawl_seconds(120, delay_seconds=1.5, workers=6) == 30
    assert format_duration(3661) == "1h 1m"


def test_combined_mark_scheme_assets_are_skipped(tmp_path: Path) -> None:
    manifest = {
        "qualification": "a_level",
        "sessions": ["s03"],
        "document_types": ["ms"],
        "subjects": [{"code": "9709", "name": "Mathematics", "components": ["1", "1+2+3+4+5+6+7"]}],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assets = load_assets(manifest_path)

    assert [asset.stem for asset in assets] == ["9709_s03_ms_1"]
    assert not is_supported_frank_asset(PaperAsset("cie", "a_level", "9709", "Mathematics", "s03", "ms", "1+2"))


def test_component_rules_are_selected_by_session_year(tmp_path: Path) -> None:
    manifest = {
        "qualification": "a_level",
        "sessions": ["s19", "s20"],
        "document_types": ["qp"],
        "subjects": [
            {
                "code": "9709",
                "name": "Mathematics",
                "component_rules": [
                    {"valid_from": 2002, "valid_to": 2019, "components": ["1", "2"]},
                    {"valid_from": 2020, "valid_to": None, "components": ["11", "12"]},
                ],
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assets = load_assets(manifest_path)

    assert [asset.stem for asset in assets] == [
        "9709_s19_qp_1",
        "9709_s19_qp_2",
        "9709_s20_qp_11",
        "9709_s20_qp_12",
    ]


def test_download_migrates_legacy_raw_layout(tmp_path: Path) -> None:
    asset = PaperAsset("cie", "a_level", "9709", "Mathematics", "s24", "qp", "11")
    legacy_pdf = tmp_path / asset.legacy_relative_pdf_path
    legacy_pdf.parent.mkdir(parents=True)
    legacy_pdf.write_bytes(b"%PDF")
    legacy_pdf.with_suffix(".json").write_text(json.dumps({"stem": asset.stem}), encoding="utf-8")

    target = download_asset(asset, tmp_path)

    assert target == tmp_path / asset.relative_pdf_path
    assert target.exists()
    assert target.with_suffix(".json").exists()
    assert not legacy_pdf.exists()


def test_migrate_raw_layout_moves_existing_metadata_pairs(tmp_path: Path) -> None:
    asset = PaperAsset("cie", "a_level", "9709", "Mathematics", "s24", "qp", "11")
    legacy_pdf = tmp_path / asset.legacy_relative_pdf_path
    legacy_pdf.parent.mkdir(parents=True)
    legacy_pdf.write_bytes(b"%PDF")
    legacy_pdf.with_suffix(".json").write_text(json.dumps(asset.__dict__), encoding="utf-8")

    counts = migrate_raw_layout(tmp_path)

    assert counts["migrated"] == 1
    assert (tmp_path / asset.relative_pdf_path).exists()


def test_migrate_raw_layout_moves_legacy_part_files(tmp_path: Path) -> None:
    asset = PaperAsset("cie", "a_level", "9709", "Mathematics", "w24", "qp", "11")
    legacy_part = tmp_path / asset.legacy_relative_pdf_path.with_suffix(".pdf.part")
    legacy_part.parent.mkdir(parents=True)
    legacy_part.write_bytes(b"partial")

    counts = migrate_raw_layout(tmp_path)

    assert counts["migrated_part"] == 1
    assert (tmp_path / asset.relative_pdf_path.with_suffix(".pdf.part")).exists()
    assert not legacy_part.exists()


def test_cambridge_subject_link_parser_extracts_code_and_notes() -> None:
    subject = parse_subject_link_text(
        "English General Paper 8021 (AS Level only)",
        "https://www.cambridgeinternational.org/example/",
        "https://www.cambridgeinternational.org/subjects/",
    )

    assert subject is not None
    assert subject.code == "8021"
    assert subject.name == "English General Paper"
    assert subject.qualification_notes == "AS Level only"

    new_subject = parse_subject_link_text(
        "Chinese Language & Literature (A Level only) (9868) New",
        "https://www.cambridgeinternational.org/example/",
        "https://www.cambridgeinternational.org/subjects/",
    )
    assert new_subject is not None
    assert new_subject.code == "9868"
    assert new_subject.name == "Chinese Language & Literature"
    assert new_subject.qualification_notes == "A Level only, New"

    history_subject = parse_subject_link_text(
        "US History since 1877 - 8102 New",
        "https://www.cambridgeinternational.org/example/",
        "https://www.cambridgeinternational.org/subjects/",
    )
    assert history_subject is not None
    assert history_subject.code == "8102"
    assert history_subject.name == "US History since 1877"


def test_cambridge_subjects_parser_keeps_subject_links_only() -> None:
    html = """
    <a href="/programmes-and-qualifications/cambridge-international-as-and-a-level-mathematics-9709/">
      Mathematics 9709
    </a>
    <a href="/programmes-and-qualifications/cambridge-international-as-and-a-levels/subjects/">Subjects</a>
    <a href="/programmes-and-qualifications/cambridge-igcse-chemistry-0620/">Chemistry 0620</a>
    """

    subjects = parse_subjects(html)

    assert [(subject.code, subject.name) for subject in subjects] == [("9709", "Mathematics")]


def test_subject_options_are_loaded_from_manifest(tmp_path: Path) -> None:
    manifest = {
        "qualification": "a_level",
        "sessions": ["s24"],
        "document_types": ["qp"],
        "subjects": [
            {"code": "9709", "name": "Mathematics", "components": ["11"]},
            {"code": "9701", "name": "Chemistry", "components": ["11"]},
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert load_subject_options(manifest_path) == {"9701": "Chemistry", "9709": "Mathematics"}


def test_default_manifest_is_resolved_outside_project_root(tmp_path: Path) -> None:
    previous = Path.cwd()
    try:
        os.chdir(tmp_path)
        manifest = default_manifest_path()
        assert project_path(manifest).exists()
        assert load_subject_options(manifest)
    finally:
        os.chdir(previous)


def test_subject_download_percentage_uses_available_assets_and_local_pdfs(tmp_path: Path) -> None:
    availability_dir = tmp_path / "available"
    raw_root = tmp_path / "raw"
    asset_a = PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "11")
    asset_b = PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "12")
    save_availability_index(subject_availability_path("9709", availability_dir=availability_dir), [asset_a, asset_b])
    downloaded = raw_root / asset_a.relative_pdf_path
    downloaded.parent.mkdir(parents=True)
    downloaded.write_bytes(b"%PDF")

    assert subject_download_percentage(
        "9709",
        raw_root=raw_root,
        availability_dir=availability_dir,
        start_year=2024,
        end_year=2024,
        document_types={"qp"},
    ) == 50


def test_subject_download_percentage_can_reuse_local_pdf_index(tmp_path: Path) -> None:
    availability_dir = tmp_path / "available"
    raw_root = tmp_path / "raw"
    asset_a = PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "11")
    asset_b = PaperAsset("cie", "a_level", "9709", "Math", "s24", "qp", "12")
    save_availability_index(subject_availability_path("9709", availability_dir=availability_dir), [asset_a, asset_b])
    downloaded = raw_root / asset_b.legacy_relative_pdf_path
    downloaded.parent.mkdir(parents=True)
    downloaded.write_bytes(b"%PDF")

    local_pdfs = local_pdf_relative_paths(raw_root)

    assert subject_download_percentage(
        "9709",
        raw_root=raw_root,
        availability_dir=availability_dir,
        start_year=2024,
        end_year=2024,
        document_types={"qp"},
        local_pdfs=local_pdfs,
    ) == 50


def test_new_cambridge_subject_rules_start_at_first_syllabus_year() -> None:
    subject = CambridgeSubject(
        code="8102",
        name="US History since 1877",
        url="https://www.cambridgeinternational.org/example/",
        qualification_notes="New",
        source="https://www.cambridgeinternational.org/subjects/",
        syllabus_pdfs=[{"title": "2027 - 2029 Syllabus", "url": "https://example.test/syllabus.pdf", "valid_from": 2027, "valid_to": 2029}],
    )

    assert component_rules_for_subject(subject)[0]["valid_from"] == 2027


def test_9709_rules_split_single_and_double_digit_eras() -> None:
    subject = CambridgeSubject(
        code="9709",
        name="Mathematics",
        url="https://www.cambridgeinternational.org/example/",
        qualification_notes="",
        source="https://www.cambridgeinternational.org/subjects/",
        syllabus_pdfs=[],
    )

    rules = component_rules_for_subject(subject)

    assert rules[0]["valid_to"] == 2009
    assert rules[0]["components"] == ["1", "2", "3", "4", "5", "6", "7"]
    assert rules[1]["valid_from"] == 2010
    assert "1" not in rules[1]["components"]
    assert {"11", "21", "61", "71"}.issubset(set(rules[1]["components"]))

