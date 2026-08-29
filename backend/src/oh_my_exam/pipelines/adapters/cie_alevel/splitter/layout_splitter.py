from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

from pypdf import PdfReader

from oh_my_exam.pipelines.adapters.cie_alevel.splitter.cie import build_frank_cie_url
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.content_extraction import extract_content_from_text_or_image
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.cutters.registry import get_subject_cutter
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.metadata_schema import build_question_manifest
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.models import PaperAsset
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.local_corpus import InstalledPaperSet, discover_installed_paper_sets, filter_paper_sets


ProgressCallback = Callable[[dict[str, object]], None]
StopCallback = Callable[[], bool]


@dataclass(frozen=True)
class SplitOptions:
    dpi: int = 150
    threshold: int = 215
    quality: int = 88
    crop_margin_px: int = 8
    remove_answer_lines: bool = True


@dataclass(frozen=True)
class TextLine:
    page_index: int
    x: float
    y: float
    text: str


@dataclass(frozen=True)
class PageSlicePlan:
    question_number: str
    page_index: int
    top_ratio: float
    bottom_ratio: float
    text: str


QUESTION_RE = re.compile(r"^\s*(?:Question\s*)?([0-9]{1,2})(?:\s*\(|\s+|$|[.:])", re.IGNORECASE)
MS_QUESTION_RE = re.compile(r"^\s*([0-9]{1,2})(?:\s*(?:\([a-zivx]+\))|\s{2,}|$)", re.IGNORECASE)


def split_paper_set_to_images(
    paper_set: InstalledPaperSet,
    raw_root: Path,
    processed_root: Path,
    *,
    options: SplitOptions | None = None,
) -> dict[str, object]:
    options = options or SplitOptions()
    output_dir = (
        processed_root
        / paper_set.exam_board
        / paper_set.qualification
        / paper_set.subject_code
        / str(paper_set.year)
        / paper_set.session
        / paper_set.component
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, object] = {"key": paper_set.key, "qp": None, "ms": None}
    subject_cutter = get_subject_cutter(paper_set.exam_board, paper_set.subject_code)
    if subject_cutter is not None:
        cutter_options = subject_cutter.options_type(dpi=options.dpi, quality=options.quality)
        if paper_set.qp is not None:
            result["qp"] = subject_cutter.split_asset_to_images(paper_set.qp, raw_root, output_dir / "qp", cutter_options)
        if paper_set.ms is not None:
            result["ms"] = subject_cutter.split_asset_to_images(paper_set.ms, raw_root, output_dir / "ms", cutter_options)
        result["cutter"] = subject_cutter.name
        return result
    if paper_set.qp is not None:
        result["qp"] = _split_asset_to_images(paper_set.qp, raw_root, output_dir / "qp", options)
    if paper_set.ms is not None:
        result["ms"] = _split_asset_to_images(paper_set.ms, raw_root, output_dir / "ms", options)
    return result


def split_installed_paper_sets(
    raw_root: Path,
    processed_root: Path,
    report_path: Path,
    *,
    keys: set[str] | None = None,
    subject_codes: set[str] | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    limit: int | None = None,
    workers: int = 1,
    options: SplitOptions | None = None,
    progress: ProgressCallback | None = None,
    should_stop: StopCallback | None = None,
) -> dict[str, int]:
    paper_sets = filter_paper_sets(
        discover_installed_paper_sets(raw_root),
        keys=keys,
        subject_codes=subject_codes,
        start_year=start_year,
        end_year=end_year,
    )
    if limit is not None:
        paper_sets = paper_sets[:limit]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    counts = {"split": 0, "failed": 0, "skipped": 0}
    progress_state = {"completed": 0, "started_at": time.monotonic()}
    workers = max(1, int(workers))
    options = options or SplitOptions()

    def run_one(index: int, paper_set: InstalledPaperSet) -> dict[str, object]:
        if should_stop and should_stop():
            return {"index": index, "total": len(paper_sets), "key": paper_set.key, "status": "skipped", "message": "stopped"}
        if paper_set.qp is None and paper_set.ms is None:
            return {"index": index, "total": len(paper_sets), "key": paper_set.key, "status": "skipped"}
        split_paper_set_to_images(paper_set, raw_root, processed_root, options=options)
        return {"index": index, "total": len(paper_sets), "key": paper_set.key, "status": "split"}

    with report_path.open("a", encoding="utf-8") as report:
        if workers == 1:
            for index, paper_set in enumerate(paper_sets, start=1):
                if should_stop and should_stop():
                    break
                try:
                    record = run_one(index, paper_set)
                except Exception as exc:
                    record = {
                        "index": index,
                        "total": len(paper_sets),
                        "key": paper_set.key,
                        "status": "failed",
                        "message": str(exc),
                    }
                _record_split_result(record, report, counts, progress, progress_state)
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures: dict[Future[dict[str, object]], InstalledPaperSet] = {}
                iterator = iter(enumerate(paper_sets, start=1))
                in_flight_limit = max(workers, workers * 2)

                def submit_until_full() -> None:
                    while len(futures) < in_flight_limit:
                        if should_stop and should_stop():
                            return
                        try:
                            index, paper_set = next(iterator)
                        except StopIteration:
                            return
                        futures[executor.submit(run_one, index, paper_set)] = paper_set

                submit_until_full()
                while futures:
                    completed = next(as_completed(futures))
                    paper_set = futures.pop(completed)
                    try:
                        record = completed.result()
                    except Exception as exc:
                        record = {
                            "index": 0,
                            "total": len(paper_sets),
                            "key": paper_set.key,
                            "status": "failed",
                            "message": str(exc),
                        }
                    _record_split_result(record, report, counts, progress, progress_state)
                    submit_until_full()
    return counts


def _record_split_result(
    record: dict[str, object],
    report,
    counts: dict[str, int],
    progress: ProgressCallback | None,
    progress_state: dict[str, float],
) -> None:
    status = str(record.get("status", "failed"))
    counts[status] = counts.get(status, 0) + 1
    total = int(record.get("total") or 0)
    progress_state["completed"] = progress_state.get("completed", 0) + 1
    completed = int(progress_state["completed"])
    elapsed_seconds = max(0.0, time.monotonic() - progress_state["started_at"])
    remaining = max(0, total - completed)
    eta_seconds = (elapsed_seconds / completed * remaining) if completed and remaining else 0.0
    record["paper_index"] = record.get("index")
    record["index"] = completed
    record["elapsed_seconds"] = round(elapsed_seconds, 1)
    record["eta_seconds"] = round(eta_seconds, 1)
    record["counts"] = dict(counts)
    report.write(json.dumps(record, ensure_ascii=False) + "\n")
    report.flush()
    if progress:
        progress(record)


def _split_asset_to_images(asset: PaperAsset, raw_root: Path, output_dir: Path, options: SplitOptions) -> list[dict[str, object]]:
    pdf_path = raw_root / asset.relative_pdf_path
    output_dir.mkdir(parents=True, exist_ok=True)
    reader = PdfReader(str(pdf_path))
    lines = _extract_text_lines(reader)
    plans = _build_slice_plans(reader, lines, asset.document_type)
    rendered_pages = _render_pdf_pages(pdf_path, options.dpi)
    try:
        slices: list[dict[str, object]] = []
        totals: dict[str, int] = {}
        seen: dict[str, int] = {}
        for plan in plans:
            safe_number = _safe_number(plan.question_number)
            totals[safe_number] = totals.get(safe_number, 0) + 1
        for plan in plans:
            safe_number = _safe_number(plan.question_number)
            seen[safe_number] = seen.get(safe_number, 0) + 1
            file_id = f"q{safe_number}" if totals[safe_number] == 1 else f"q{safe_number}_p{seen[safe_number]:02d}"
            image_path, post_render_crop_px, _kept_bands_px = _export_plan_image(plan, rendered_pages[plan.page_index], output_dir, asset, options, file_id)
            manifest_path = output_dir / f"{asset.stem}_{file_id}.json"
            content = extract_content_from_text_or_image(plan.text, image_path) if asset.document_type == "qp" else None
            crop_regions = [
                _fallback_crop_region(
                    asset,
                    pdf_path,
                    reader.pages[plan.page_index],
                    plan,
                    options,
                    post_render_crop_px=post_render_crop_px,
                )
            ]
            manifest = build_question_manifest(
                asset,
                plan.question_number,
                plan.page_index + 1,
                plan.page_index + 1,
                "cie_alevel_layout_fallback",
                content=content,
                crop_regions=crop_regions,
            )
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            slices.append(manifest)
        return slices
    finally:
        _cleanup_rendered_pages(rendered_pages)


def _extract_text_lines(reader: PdfReader) -> list[TextLine]:
    lines: list[TextLine] = []
    for page_index, page in enumerate(reader.pages):
        def visitor(text: str, _cm, tm, _font, _size) -> None:
            value = (text or "").strip()
            if value:
                lines.append(TextLine(page_index=page_index, x=float(tm[4]), y=float(tm[5]), text=value))

        try:
            page.extract_text(visitor_text=visitor)
        except Exception:
            continue
    return lines


def _build_slice_plans(reader: PdfReader, lines: list[TextLine], document_type: str) -> list[PageSlicePlan]:
    page_count = len(reader.pages)
    plans: list[PageSlicePlan] = []
    next_number = 1
    seen_mark_scheme_question = False
    for page_index in range(page_count):
        page_lines = sorted((line for line in lines if line.page_index == page_index), key=lambda item: -item.y)
        markers = _detect_question_markers(page_lines, document_type, float(reader.pages[page_index].mediabox.height or 842))
        if not markers:
            text = "\n".join(line.text for line in page_lines)
            if _looks_like_front_matter(text, document_type) or (document_type == "ms" and not seen_mark_scheme_question):
                continue
            if plans:
                markers = [(plans[-1].question_number, 0.06)]
            else:
                continue
        elif document_type == "ms":
            seen_mark_scheme_question = True
        markers = _dedupe_markers(markers)
        for marker_index, (question_number, top_ratio) in enumerate(markers):
            if not question_number:
                question_number = str(next_number)
            bottom_ratio = markers[marker_index + 1][1] if marker_index + 1 < len(markers) else 0.94
            if bottom_ratio - top_ratio < 0.025:
                continue
            text = "\n".join(line.text for line in _lines_between(page_lines, top_ratio, bottom_ratio, reader.pages[page_index]))
            plans.append(PageSlicePlan(question_number=question_number, page_index=page_index, top_ratio=top_ratio, bottom_ratio=bottom_ratio, text=text))
            if question_number.isdigit():
                next_number = max(next_number, int(question_number) + 1)
    if document_type == "ms" and not plans and page_count:
        start_page = 3 if page_count > 3 else 0
        for page_index in range(start_page, page_count):
            plans.append(
                PageSlicePlan(
                    question_number=str(page_index - start_page + 1),
                    page_index=page_index,
                    top_ratio=0.06,
                    bottom_ratio=0.94,
                    text="",
                )
            )
    return plans


def _detect_question_markers(lines: list[TextLine], document_type: str, page_height: float) -> list[tuple[str, float]]:
    markers: list[tuple[str, float]] = []
    seen_y: set[int] = set()
    seen_garbled_marker = False
    for line in lines:
        if line.y < 45 or line.y > 760:
            continue
        if line.x > 130:
            continue
        pattern = MS_QUESTION_RE if document_type == "ms" else QUESTION_RE
        match = pattern.match(line.text)
        if match:
            y_bucket = round(line.y / 4)
            if y_bucket in seen_y:
                continue
            seen_y.add(y_bucket)
            markers.append((match.group(1), _pdf_y_to_top_ratio(line.y, page_height)))
            continue
        if document_type == "qp" and not seen_garbled_marker and 45 <= line.x <= 85 and _is_probable_garbled_question_marker(line.text):
            y_bucket = round(line.y / 12)
            if y_bucket not in seen_y:
                seen_y.add(y_bucket)
                seen_garbled_marker = True
                markers.append(("", _pdf_y_to_top_ratio(line.y, page_height)))
    return markers


def _is_probable_garbled_question_marker(text: str) -> bool:
    if len(text) > 35:
        return False
    if any(ch.isdigit() for ch in text):
        return False
    return sum(1 for ch in text if ord(ch) > 126 or ord(ch) < 32) >= 1


def _dedupe_markers(markers: list[tuple[str, float]]) -> list[tuple[str, float]]:
    deduped: list[tuple[str, float]] = []
    for number, ratio in sorted(markers, key=lambda item: item[1]):
        if deduped and abs(deduped[-1][1] - ratio) < 0.025:
            continue
        deduped.append((number, ratio))
    return deduped


def _looks_like_front_matter(text: str, document_type: str) -> bool:
    lowered = text.lower()
    if document_type == "ms":
        return any(token in lowered for token in ["mark scheme", "generic marking", "published"])
    return any(token in lowered for token in ["instructions", "answer all questions", "read these instructions"])


def _lines_between(lines: list[TextLine], top_ratio: float, bottom_ratio: float, page) -> list[TextLine]:
    height = float(page.mediabox.height or 842)
    top_y = height * (1 - top_ratio)
    bottom_y = height * (1 - bottom_ratio)
    return [line for line in lines if bottom_y <= line.y <= top_y]


def _pdf_y_to_top_ratio(y: float, page_height: float = 842.0) -> float:
    return max(0.0, min(1.0, 1 - (y / page_height) - 0.015))


def _render_pdf_pages(pdf_path: Path, dpi: int) -> list[Path]:
    try:
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Image splitting requires Pillow. Install with: python -m pip install Pillow") from exc
    pdftoppm = _find_pdftoppm()
    if pdftoppm is None:
        raise RuntimeError("Image splitting requires Poppler pdftoppm on PATH.")
    render_root = Path.cwd() / "tmp" / "pdf_render"
    render_root.mkdir(parents=True, exist_ok=True)
    temp_dir = render_root / f"ome_pdf_render_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=False)
    prefix = temp_dir / "page"
    try:
        subprocess.run(
            [pdftoppm, "-r", str(dpi), "-mono", str(pdf_path), str(prefix)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"pdftoppm failed for {pdf_path}: {message}") from exc
    return sorted(temp_dir.glob("page-*.pbm"))


def _find_pdftoppm() -> str | None:
    candidate = shutil.which("pdftoppm")
    candidates: list[Path] = []
    if candidate:
        candidates.append(Path(candidate))
        if candidate.lower().endswith(".cmd"):
            candidates.insert(0, Path(candidate).parent.parent / "native" / "poppler" / "Library" / "bin" / "pdftoppm.exe")
    candidates.append(Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "native" / "poppler" / "Library" / "bin" / "pdftoppm.exe")
    for path in candidates:
        if path.exists():
            return str(path)
    return candidate


def _cleanup_rendered_pages(rendered_pages: list[Path]) -> None:
    if not rendered_pages:
        return
    shutil.rmtree(rendered_pages[0].parent, ignore_errors=True)


def _fallback_crop_region(
    asset: PaperAsset,
    source_pdf_path: Path,
    page,
    plan: PageSlicePlan,
    options: SplitOptions,
    *,
    post_render_crop_px: dict[str, object] | None,
) -> dict[str, object]:
    width = float(page.mediabox.width or 0)
    height = float(page.mediabox.height or 0)
    top_y = height * (1.0 - plan.top_ratio)
    bottom_y = height * (1.0 - plan.bottom_ratio)
    region: dict[str, object] = {
        "order": 0,
        "source_pdf": build_frank_cie_url(asset),
        "source_pdf_sha256": _file_sha256(str(source_pdf_path.resolve())),
        "source_stem": asset.stem,
        "document_type": asset.document_type,
        "page_index": plan.page_index,
        "page_number": plan.page_index + 1,
        "page_width": _round_float(width),
        "page_height": _round_float(height),
        "page_rotation": int(getattr(page, "rotation", 0) or 0),
        "coordinate_space": "pypdf_mediabox_points_bottom_left",
        "unit": "pt",
        "rect": {
            "x0": 0.0,
            "y0": _round_float(bottom_y),
            "x1": _round_float(width),
            "y1": _round_float(top_y),
        },
        "render_dpi": options.dpi,
        "join_gap_before_px": 0,
    }
    if post_render_crop_px is not None:
        region["post_render_crop_px"] = post_render_crop_px
    return region


def _round_float(value: float) -> float:
    return round(float(value), 3)


@lru_cache(maxsize=2048)
def _file_sha256(path_text: str) -> str:
    digest = hashlib.sha256()
    with Path(path_text).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _export_plan_image(
    plan: PageSlicePlan,
    page_image: Path,
    output_dir: Path,
    asset: PaperAsset,
    options: SplitOptions,
    file_id: str,
) -> tuple[Path, dict[str, object] | None, list[dict[str, int]] | None]:
    from PIL import Image, ImageChops

    image = Image.open(page_image).convert("L")
    width, height = image.size
    top = int(max(0, min(height - 1, plan.top_ratio * height)))
    bottom = int(max(top + 8, min(height, plan.bottom_ratio * height)))
    crop = image.crop((0, top, width, bottom))
    bw = crop.point(lambda pixel: 0 if pixel < options.threshold else 255, "1")
    bbox = ImageChops.invert(bw.convert("L")).getbbox()
    post_render_crop_px = None
    if bbox:
        left = max(0, bbox[0] - options.crop_margin_px)
        upper = max(0, bbox[1] - options.crop_margin_px)
        right = min(bw.width, bbox[2] + options.crop_margin_px)
        lower = min(bw.height, bbox[3] + options.crop_margin_px)
        bw = bw.crop((left, upper, right, lower))
        post_render_crop_px = {
            "coordinate_space": "rendered_clip_pixels",
            "unit": "px",
            "left": left,
            "top": upper,
            "right": right,
            "bottom": lower,
        }
    kept_bands_px = None
    if options.remove_answer_lines and asset.document_type == "qp":
        bw, kept_bands = _remove_answer_line_bands(bw)
        if kept_bands:
            kept_bands_px = [{"top": top, "bottom": bottom} for top, bottom in kept_bands]
    out_path = output_dir / f"{asset.stem}_{file_id}.png"
    bw.save(out_path, optimize=True)
    return out_path, post_render_crop_px, kept_bands_px


def _remove_answer_line_bands(image):
    from PIL import Image

    source = image.convert("L")
    width, height = source.size
    pixels = source.load()
    keep_rows: list[tuple[int, int]] = []
    in_band = False
    start = 0
    for y in range(height):
        black_count = 0
        longest_run = 0
        current_run = 0
        for x in range(width):
            if pixels[x, y] < 128:
                black_count += 1
                current_run += 1
                longest_run = max(longest_run, current_run)
            else:
                current_run = 0
        is_answer_line = longest_run > width * 0.45 and black_count < width * 0.75
        if is_answer_line and not in_band:
            if y > start:
                keep_rows.append((start, y))
            in_band = True
        elif not is_answer_line and in_band:
            start = y + 2
            in_band = False
    if not in_band and start < height:
        keep_rows.append((start, height))
    keep_rows = [(top, bottom) for top, bottom in keep_rows if bottom - top > 4]
    if not keep_rows or keep_rows == [(0, height)]:
        return image, []
    new_height = sum(bottom - top for top, bottom in keep_rows)
    compact = Image.new("1", (width, max(new_height, 1)), 1)
    cursor = 0
    for top, bottom in keep_rows:
        segment = image.crop((0, top, width, bottom))
        compact.paste(segment, (0, cursor))
        cursor += bottom - top
    return compact, keep_rows


def _safe_number(question_number: str) -> str:
    return question_number.zfill(2) if question_number.isdigit() else re.sub(r"[^A-Za-z0-9_-]+", "_", question_number)

