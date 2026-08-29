from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys

import pytest

from oh_my_exam.pipelines.adapters.cie_alevel.splitter.layout_splitter import PageSlicePlan, SplitOptions, _fallback_crop_region, _record_split_result
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.content_backfill import backfill_processed_question_content
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.cutters.registry import get_subject_cutter
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.content_extraction import ContentExtraction
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.metadata_schema import CROP_REGION_KEYS, MS_MANIFEST_KEYS, QP_MANIFEST_KEYS, validate_manifest_schema
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.models import PaperAsset
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.paths import project_relative_path


def test_project_relative_path_uses_project_root() -> None:
    root = Path(__file__).resolve().parents[5]
    path = root / "data" / "processed_questions" / "sample.json"

    assert project_relative_path(path, project_root=root) == "data/processed_questions/sample.json"


def test_registry_resolves_9709_subject_cutter() -> None:
    cutter = get_subject_cutter("cie", "9709")

    assert cutter is not None
    assert cutter.name == "cie_9709_geometry"


def test_registry_resolves_9231_subject_cutter() -> None:
    cutter = get_subject_cutter("cie", "9231")

    assert cutter is not None
    assert cutter.name == "cie_9231_geometry"


def test_ascii_integer_rejects_unicode_superscript_digits() -> None:
    module = _load_9709_cutter_module()

    assert module._is_ascii_integer("12")
    assert not module._is_ascii_integer("³")


def test_9709_safe_question_number_preserves_subquestion_identity() -> None:
    module = _load_9709_cutter_module()

    assert module._safe_question_number("2(a)") == "02_a"
    assert module._safe_question_number("11(c)(ii)") == "11_c_ii"


def test_9231_safe_question_number_preserves_subquestion_identity() -> None:
    module = _load_9231_cutter_module()

    assert module._safe_question_number("1(a)") == "01_a"
    assert module._safe_question_number("11(c)(ii)") == "11_c_ii"


def test_subject_cutters_normalize_supported_subquestion_labels() -> None:
    for module in (_load_9709_cutter_module(), _load_9231_cutter_module()):
        assert module._normalize_qp_subpart_label("(a)") == "(a)"
        assert module._normalize_qp_subpart_label("(III)") == "(iii)"
        assert module._normalize_qp_subpart_label("A") == "(a)"
        assert module._normalize_qp_subpart_label("D.") == "(d)"
        assert module._normalize_qp_subpart_label("x") is None


def test_subject_cutters_normalize_mark_scheme_subquestion_labels() -> None:
    for module in (_load_9709_cutter_module(), _load_9231_cutter_module()):
        clean_label, match = module._ms_label_match("1 A")
        assert clean_label == "1(a)"
        assert match is not None
        clean_label, match = module._ms_label_match("11(III)")
        assert clean_label == "11(iii)"
        assert match is not None
        assert module._ms_label_match("1answer")[1] is None


def test_subject_cutters_record_crop_regions_from_pdf_source(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "sample.pdf"
    document = fitz.open()
    document.new_page(width=200, height=300)
    document.save(pdf_path)
    document.close()
    asset = PaperAsset("cie", "a_level", "9231", "Further Mathematics", "w23", "qp", "11")

    with fitz.open(pdf_path) as document:
        clip = fitz.Rect(10, 20, 180, 220)
        for module in (_load_9709_cutter_module(), _load_9231_cutter_module()):
            regions = module._build_crop_regions(asset, pdf_path, document, [(0, clip), (0, clip)], 150)

    assert len(regions) == 2
    assert regions[0]["order"] == 0
    assert regions[1]["join_gap_before_px"] == 12
    assert regions[0]["source_pdf"] == "https://cie.fraft.cn/obj/Common/Fetch/redir/9231_w23_qp_11.pdf"
    assert regions[0]["source_pdf_sha256"]
    assert regions[0]["coordinate_space"] == "pymupdf_page_points"
    assert regions[0]["rect"] == {"x0": 10.0, "y0": 20.0, "x1": 180.0, "y1": 220.0}


def test_subject_cutters_write_qp_content_sidecars(tmp_path: Path) -> None:
    asset = PaperAsset("cie", "a_level", "9709", "Mathematics", "w24", "qp", "12")

    for module in (_load_9709_cutter_module(), _load_9231_cutter_module()):
        manifest = module._write_manifest(
            asset,
            tmp_path,
            "1(a)",
            1,
            1,
            "test_cutter",
            content=ContentExtraction("Differentiate x^2.", "pdf_text"),
            crop_regions=[],
        )

        assert manifest["content"] == "Differentiate x^2."
        assert "content_source" not in manifest
        assert "mark_scheme_points" not in manifest
        assert "image_paths" not in manifest
        assert "manifest_path" not in manifest
        sidecar_text = (tmp_path / f"{asset.stem}_q01_a.json").read_text(encoding="utf-8")
        assert "mark_scheme_points" not in sidecar_text
        assert "image_paths" not in sidecar_text
        assert "manifest_path" not in sidecar_text


def test_subject_cutters_emit_unified_metadata_schema(tmp_path: Path) -> None:
    for subject_code, module in (("9709", _load_9709_cutter_module()), ("9231", _load_9231_cutter_module())):
        qp_asset = PaperAsset("cie", "a_level", subject_code, "Test Subject", "w24", "qp", "12")
        ms_asset = PaperAsset("cie", "a_level", subject_code, "Test Subject", "w24", "ms", "12")

        qp_manifest = module._write_manifest(
            qp_asset,
            tmp_path,
            "1(a)",
            1,
            1,
            "test_cutter",
            content=ContentExtraction("Differentiate x^2.", "pdf_text"),
            crop_regions=[],
        )
        ms_manifest = module._write_manifest(
            ms_asset,
            tmp_path,
            "1(a)",
            1,
            1,
            "test_cutter",
            crop_regions=[],
        )

        assert set(qp_manifest) == QP_MANIFEST_KEYS
        assert set(ms_manifest) == MS_MANIFEST_KEYS
        assert validate_manifest_schema(qp_manifest) == []
        assert validate_manifest_schema(ms_manifest) == []


def test_unified_subject_cutter_metadata_loads_in_packer(tmp_path: Path) -> None:
    from oh_my_exam.pipelines.packaging.metadata_loader import load_metadata_records

    module = _load_9231_cutter_module()
    metadata_root = tmp_path / "processed_questions"
    qp_dir = metadata_root / "cie" / "a_level" / "9231" / "2024" / "w24" / "11" / "qp"
    ms_dir = metadata_root / "cie" / "a_level" / "9231" / "2024" / "w24" / "11" / "ms"
    qp_dir.mkdir(parents=True)
    ms_dir.mkdir(parents=True)
    module._write_manifest(
        PaperAsset("cie", "a_level", "9231", "Further Mathematics", "w24", "qp", "11"),
        qp_dir,
        "1",
        1,
        1,
        "test_cutter",
        content=ContentExtraction("Find x.", "pdf_text"),
        crop_regions=[],
    )
    module._write_manifest(
        PaperAsset("cie", "a_level", "9231", "Further Mathematics", "w24", "ms", "11"),
        ms_dir,
        "1",
        1,
        1,
        "test_cutter",
        crop_regions=[],
    )

    records, warnings = load_metadata_records(
        metadata_root,
        exam_board="cie",
        qualification="a_level",
        course_code="9231",
    )

    assert warnings == []
    assert {record.source_type for record in records} == {"QP", "MS"}
    assert {record.question_key for record in records} == {"9231_w24_11_q01"}


def test_subject_cutters_omit_ms_content_sidecars(tmp_path: Path) -> None:
    asset = PaperAsset("cie", "a_level", "9709", "Mathematics", "w24", "ms", "12")

    for module in (_load_9709_cutter_module(), _load_9231_cutter_module()):
        manifest = module._write_manifest(
            asset,
            tmp_path,
            "1(a)",
            1,
            1,
            "test_cutter",
            content=ContentExtraction("Do not store this for MS.", "pdf_text"),
            crop_regions=[],
        )

        assert "content" not in manifest
        assert "content_source" not in manifest
        assert "content_warning" not in manifest


def test_backfill_processed_question_content_updates_existing_sidecar(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    project_root = tmp_path
    docs_dir = project_root / "docs"
    backend_dir = project_root / "backend"
    docs_dir.mkdir()
    backend_dir.mkdir()
    (backend_dir / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
    (docs_dir / "requirements.md").write_text("# test\n", encoding="utf-8")
    pdf_path = backend_dir / "data" / "raw_papers" / "cie" / "a_level" / "9709" / "2024" / "w24" / "9709_w24_qp_12.pdf"
    pdf_path.parent.mkdir(parents=True)
    document = fitz.open()
    page = document.new_page(width=300, height=300)
    page.insert_text((50, 80), "Find the value of x.")
    document.save(pdf_path)
    document.close()
    sidecar = backend_dir / "data" / "processed_questions" / "cie" / "a_level" / "9709" / "2024" / "w24" / "12" / "qp" / "9709_w24_qp_12_q01.json"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text(
        json.dumps(
            {
                "question_number": "1",
                "source_stem": "9709_w24_qp_12",
                "page_start": 1,
                "page_end": 1,
                "document_type": "qp",
                "cutter": "test",
                "crop_regions": [
                    {
                        "source_pdf": "https://cie.fraft.cn/obj/Common/Fetch/redir/9709_w24_qp_12.pdf",
                        "page_index": 0,
                        "coordinate_space": "pymupdf_page_points",
                        "rect": {"x0": 0, "y0": 0, "x1": 300, "y1": 160},
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    counts = backfill_processed_question_content(backend_dir / "data" / "processed_questions")
    updated = json.loads(sidecar.read_text(encoding="utf-8"))

    assert counts == {"updated": 1, "skipped": 0, "failed": 0}
    assert "Find the value of x." in updated["content"]
    assert "content_source" not in updated


def test_backfill_processed_question_content_removes_ms_content(tmp_path: Path) -> None:
    project_root = tmp_path
    (project_root / "docs").mkdir()
    (project_root / "backend").mkdir()
    (project_root / "backend" / "pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
    (project_root / "docs" / "requirements.md").write_text("# test\n", encoding="utf-8")
    sidecar = project_root / "backend" / "data" / "processed_questions" / "cie" / "a_level" / "9709" / "2024" / "w24" / "12" / "ms" / "9709_w24_ms_12_q01.json"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text(
        json.dumps(
            {
                "question_number": "1",
                "document_type": "ms",
                "content": "old",
                "content_source": "pdf_text",
                "content_warning": "old warning",
                "crop_regions": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    counts = backfill_processed_question_content(project_root / "backend" / "data" / "processed_questions")
    updated = json.loads(sidecar.read_text(encoding="utf-8"))

    assert counts == {"updated": 0, "skipped": 1, "failed": 0}
    assert "content" not in updated
    assert "content_source" not in updated
    assert "content_warning" not in updated


def test_fallback_crop_region_records_replay_transforms(tmp_path: Path) -> None:
    class FakeBox:
        width = 600
        height = 800

    class FakePage:
        mediabox = FakeBox()
        rotation = 0

    pdf_path = tmp_path / "fallback.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% synthetic test payload\n")
    asset = PaperAsset("cie", "a_level", "9999", "Sample", "w23", "qp", "11")
    plan = PageSlicePlan("1(a)", page_index=1, top_ratio=0.10, bottom_ratio=0.40, text="")

    region = _fallback_crop_region(
        asset,
        pdf_path,
        FakePage(),
        plan,
        SplitOptions(dpi=150),
        post_render_crop_px={"coordinate_space": "rendered_clip_pixels", "unit": "px", "left": 2, "top": 3, "right": 400, "bottom": 500},
    )

    assert region["source_pdf"] == "https://cie.fraft.cn/obj/Common/Fetch/redir/9999_w23_qp_11.pdf"
    assert region["rect"] == {"x0": 0.0, "y0": 480.0, "x1": 600.0, "y1": 720.0}
    assert CROP_REGION_KEYS | {"post_render_crop_px"} <= set(region)


def test_9231_removes_stale_asset_slices_after_resplitting(tmp_path: Path) -> None:
    module = _load_9231_cutter_module()
    stale = tmp_path / "9231_w23_ms_11_q01.json"
    current = tmp_path / "9231_w23_ms_11_q01_a.json"
    other = tmp_path / "9231_w23_ms_12_q01.json"
    stale.write_text("old", encoding="utf-8")
    current.write_text("old", encoding="utf-8")
    other.write_text("keep", encoding="utf-8")

    module._remove_stale_asset_slices(tmp_path, "9231_w23_ms_11", [current])

    assert not stale.exists()
    assert current.exists()
    assert other.exists()


def test_9709_modern_qp_does_not_start_from_cover_footer() -> None:
    module = _load_9709_cutter_module()
    fitz = pytest.importorskip("fitz")
    pdf_path = _project_root() / "data" / "raw_papers" / "cie" / "a_level" / "9709" / "2025" / "m25" / "9709_m25_qp_12.pdf"
    if not pdf_path.exists():
        pytest.skip("local 9709 m25 qp12 sample is not installed")

    with fitz.open(pdf_path) as document:
        starts = module._qp_question_starts(document)

    assert starts[0][0] == 1
    assert starts[0][1] < 120
    assert all(start[0] != 0 for start in starts)
    assert all(start[1] <= module._body_rect().y1 - 50.0 for start in starts)


def test_9709_qp_splits_readable_layout_to_leaf_subquestions() -> None:
    module = _load_9709_cutter_module()
    fitz = pytest.importorskip("fitz")
    pdf_path = _project_root() / "data" / "raw_papers" / "cie" / "a_level" / "9709" / "2021" / "w21" / "9709_w21_qp_12.pdf"
    if not pdf_path.exists():
        pytest.skip("local 9709 w21 qp12 sample is not installed")

    with fitz.open(pdf_path) as document:
        question_numbers = [plan.question_number for plan in module._qp_question_plans(document)]

    assert question_numbers[:5] == ["1", "2(a)", "2(b)", "3(a)", "3(b)"]
    assert "10(c)" in question_numbers
    assert question_numbers[-2:] == ["12(a)", "12(b)"]


def test_9709_modern_ms32_skips_marking_principles_pages() -> None:
    module = _load_9709_cutter_module()
    fitz = pytest.importorskip("fitz")
    pdf_path = _project_root() / "data" / "raw_papers" / "cie" / "a_level" / "9709" / "2025" / "m25" / "9709_m25_ms_32.pdf"
    if not pdf_path.exists():
        pytest.skip("local 9709 m25 ms32 sample is not installed")

    with fitz.open(pdf_path) as document:
        starts = module._ms_infer_missing_starts(document, module._ms_question_candidates(document))

    assert starts[0].number == 1
    assert starts[0].page_index == 8
    assert starts[0].display_y < 140


def test_9709_ms_splits_readable_layout_to_leaf_subquestions() -> None:
    module = _load_9709_cutter_module()
    fitz = pytest.importorskip("fitz")
    pdf_path = _project_root() / "data" / "raw_papers" / "cie" / "a_level" / "9709" / "2021" / "w21" / "9709_w21_ms_12.pdf"
    if not pdf_path.exists():
        pytest.skip("local 9709 w21 ms12 sample is not installed")

    with fitz.open(pdf_path) as document:
        starts = module._ms_split_starts(document)

    question_numbers = [start.question_number for start in starts]
    assert starts[0].page_index == 5
    assert all(start.page_index >= 5 for start in starts)
    assert question_numbers[:5] == ["1", "2(a)", "2(b)", "3(a)", "3(b)"]
    assert question_numbers[-2:] == ["12(a)", "12(b)"]


def test_9231_qp_splits_damaged_modern_layout_to_leaf_subquestions() -> None:
    module = _load_9231_cutter_module()
    fitz = pytest.importorskip("fitz")
    pdf_path = _project_root() / "data" / "raw_papers" / "cie" / "a_level" / "9231" / "2025" / "w25" / "9231_w25_qp_11.pdf"
    if not pdf_path.exists():
        pytest.skip("local 9231 w25 qp11 sample is not installed")

    with fitz.open(pdf_path) as document:
        question_numbers = [plan.question_number for plan in module._qp_question_plans(document)]

    assert question_numbers[:8] == ["1(a)", "1(b)", "1(c)", "2(a)", "2(b)", "2(c)", "2(d)", "3"]
    assert question_numbers[-5:] == ["7(a)", "7(b)", "7(c)", "7(d)", "7(e)"]


def test_9231_qp_keeps_readable_top_level_question_without_subparts() -> None:
    module = _load_9231_cutter_module()
    fitz = pytest.importorskip("fitz")
    pdf_path = _project_root() / "data" / "raw_papers" / "cie" / "a_level" / "9231" / "2021" / "w21" / "9231_w21_qp_12.pdf"
    if not pdf_path.exists():
        pytest.skip("local 9231 w21 qp12 sample is not installed")

    with fitz.open(pdf_path) as document:
        question_numbers = [plan.question_number for plan in module._qp_question_plans(document)]

    assert question_numbers[:6] == ["1(a)", "1(b)", "1(c)", "1(d)", "2", "3(a)"]


def test_9231_ms_splits_image_and_text_layout_to_leaf_subquestions() -> None:
    module = _load_9231_cutter_module()
    fitz = pytest.importorskip("fitz")
    pdf_path = _project_root() / "data" / "raw_papers" / "cie" / "a_level" / "9231" / "2025" / "w25" / "9231_w25_ms_11.pdf"
    if not pdf_path.exists():
        pytest.skip("local 9231 w25 ms11 sample is not installed")

    with fitz.open(pdf_path) as document:
        question_numbers = [start.question_number for start in module._ms_split_starts(document)]

    assert question_numbers[:8] == ["1(a)", "1(b)", "1(c)", "2(a)", "2(b)", "2(c)", "2(d)", "3"]
    assert "5(b)" in question_numbers
    assert question_numbers[-5:] == ["7(a)", "7(b)", "7(c)", "7(d)", "7(e)"]


def test_9231_w23_ms11_splits_rotated_table_to_leaf_subquestions() -> None:
    module = _load_9231_cutter_module()
    fitz = pytest.importorskip("fitz")
    pdf_path = _project_root() / "data" / "raw_papers" / "cie" / "a_level" / "9231" / "2023" / "w23" / "9231_w23_ms_11.pdf"
    if not pdf_path.exists():
        pytest.skip("local 9231 w23 ms11 sample is not installed")

    with fitz.open(pdf_path) as document:
        question_numbers = [start.question_number for start in module._ms_split_starts(document)]

    assert question_numbers[:5] == ["1(a)", "1(b)", "2", "3(a)", "3(b)"]
    assert question_numbers[-5:] == ["7(a)", "7(b)", "7(c)", "7(d)", "7(e)"]


def test_9709_ms_marking_point_parser_extracts_structured_rows() -> None:
    module = _load_9709_cutter_module()

    points = module._parse_ms_marking_points_from_rows(
        [
            {"answer": "1+5x+10x^2", "marks": "B1", "guidance": ""},
            {"answer": "", "marks": "1", "guidance": ""},
            {"answer": "1-12x+60x^2", "marks": "B2, 1, 0", "guidance": "B2 all correct, B1 for two correct components."},
            {"answer": "", "marks": "2", "guidance": ""},
            {
                "answer": "(1+5x+10x^2)(1-12x+60x^2) leading to 60-60+10",
                "marks": "M1",
                "guidance": "3 products required",
            },
            {"answer": "10", "marks": "A1", "guidance": "Allow 10x^2"},
            {"answer": "", "marks": "2", "guidance": ""},
        ]
    )

    assert [point.type for point in points] == ["B", "B", "M", "A"]
    assert [point.score for point in points] == [1, 2, 1, 1]
    assert points[0].marking_point == "1+5x+10x^2"
    assert points[1].supplement == "B2 all correct, B1 for two correct components."
    assert points[2].supplement == "3 products required"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _load_9709_cutter_module():
    cutter_path = _project_root() / "backend" / "src" / "oh_my_exam" / "pipelines" / "adapters" / "cie_alevel" / "splitter" / "subjects" / "9709.py"
    spec = spec_from_file_location("test_cie_9709_cutter", cutter_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_9231_cutter_module():
    cutter_path = _project_root() / "backend" / "src" / "oh_my_exam" / "pipelines" / "adapters" / "cie_alevel" / "splitter" / "subjects" / "9231.py"
    spec = spec_from_file_location("test_cie_9231_cutter", cutter_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_progress_uses_completed_count_not_original_paper_index(tmp_path: Path) -> None:
    report_path = tmp_path / "report.jsonl"
    counts = {"split": 0, "failed": 0, "skipped": 0}
    events = []
    progress_state = {"completed": 0, "started_at": 1.0}

    with report_path.open("w", encoding="utf-8") as report:
        _record_split_result(
            {"index": 421, "total": 834, "key": "late", "status": "split"},
            report,
            counts,
            events.append,
            progress_state,
        )
        _record_split_result(
            {"index": 108, "total": 834, "key": "early", "status": "split"},
            report,
            counts,
            events.append,
            progress_state,
        )

    assert [event["index"] for event in events] == [1, 2]
    assert [event["paper_index"] for event in events] == [421, 108]
    assert events[-1]["eta_seconds"] >= 0
