from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from cie_alevel_splitter.cie import build_frank_cie_url
from cie_alevel_splitter.content_extraction import ContentExtraction, extract_content_from_fitz_clips
from cie_alevel_splitter.metadata_schema import build_question_manifest
from cie_alevel_splitter.models import PaperAsset

if TYPE_CHECKING:
    import fitz
    from PIL import Image as PILImage

Image = None
ImageDraw = None


BODY_RECT_VALUES = (55.0, 42.0, 555.0, 740.0)
VERTICAL_CLUSTER_GAP = 52.0
TOP_RANGE_SAFETY_POINTS = 20.0
END_RANGE_SAFETY_POINTS = 6.0
HORIZONTAL_PADDING_POINTS = 10.0
TOP_PADDING_POINTS = 16.0
BOTTOM_PADDING_POINTS = 10.0
JOIN_GAP_PIXELS = 12
RASTER_LAYOUT_SCALE = 2.0
RASTER_INK_THRESHOLD = 200
MS_TOP_PADDING_POINTS = 8.0
MS_BOTTOM_PADDING_POINTS = 3.0
MS_NEXT_QUESTION_GAP_POINTS = 34.0
MS_LEGACY_NEXT_QUESTION_GAP_POINTS = 6.0
MS_INK_THRESHOLD = 235
QUESTION_LABEL_PATTERN = re.compile(r"^(?P<number>[0-9]{1,2})(?:\([a-zivxlcdm]+\))*\.?$", re.I)
LABEL_TOKEN_PATTERN = re.compile(r"^(?:[a-z]|[ivxlcdm]{1,6})$", re.I)
BARE_OPTION_LABEL_PATTERN = re.compile(r"^[A-D]$")
QP_FRONT_MATTER_PATTERNS = (
    "INSTRUCTIONS TO CANDIDATES",
    "INFORMATION FOR CANDIDATES",
    "READ THESE INSTRUCTIONS",
    "ANSWER ALL QUESTIONS",
)
MS_FRONT_MATTER_PATTERNS = (
    "MARK SCHEME",
    "MAXIMUM MARK",
    "SYLLABUS",
    "GENERAL MARKING",
    "UNIVERSITY OF CAMBRIDGE",
)
MS_PRE_ANSWER_PATTERNS = (
    "GENERIC MARKING PRINCIPLES",
    "MATHEMATICS SPECIFIC MARKING PRINCIPLES",
    "MARK SCHEME NOTES",
    "ABBREVIATIONS",
)
MS_ANSWER_TABLE_PATTERN = "QUESTION ANSWER MARKS GUIDANCE"
CUTTER_NAME = "cie_9231_geometry"


@dataclass(frozen=True)
class CutterOptions:
    dpi: int = 160
    quality: int = 88
    overwrite: bool = True


@dataclass(frozen=True)
class QuestionStart:
    number: int
    page_index: int
    display_y: float
    inferred: bool = False
    label: str = ""

    @property
    def question_number(self) -> str:
        return self.label or str(self.number)


@dataclass(frozen=True)
class QuestionClipPlan:
    question_number: str
    ranges: tuple[tuple[tuple[int, float], tuple[int, float]], ...]


@dataclass(frozen=True)
class QpPartBoundary:
    label: str
    depth: int
    page_index: int
    display_y: float
    x0: float
    path: tuple[str, ...] = ()


@dataclass(frozen=True)
class MarkSchemePoint:
    score: int
    type: str
    marking_point: str
    supplement: str


@dataclass(frozen=True)
class RenderedSegment:
    page_index: int
    image: "PILImage.Image"
    clip: "fitz.Rect"
    post_render_crop_px: dict[str, object]


def split_asset_to_images(asset: PaperAsset, raw_root: Path, output_dir: Path, options: CutterOptions) -> list[dict[str, object]]:
    pdf_path = raw_root / asset.relative_pdf_path
    output_dir.mkdir(parents=True, exist_ok=True)
    fitz_module = _load_fitz()
    _load_pillow()
    try:
        with fitz_module.open(pdf_path) as document:
            if asset.document_type == "qp":
                return _split_qp(document, asset, output_dir, options, pdf_path)
            if asset.document_type == "ms":
                return _split_ms(document, asset, output_dir, options, pdf_path)
        raise ValueError(f"unsupported 9231 document type: {asset.document_type}")
    finally:
        _clear_runtime_caches()


def _load_fitz():
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "High-quality CIE 9231 splitting requires PyMuPDF. "
            "Install it in the project venv with: python -m pip install PyMuPDF Pillow"
        ) from exc
    return fitz


def _load_pillow():
    global Image, ImageDraw
    if Image is None or ImageDraw is None:
        try:
            from PIL import Image as PILImage
            from PIL import ImageDraw as PILImageDraw
        except ImportError as exc:
            raise RuntimeError(
                "High-quality image splitting requires Pillow. "
                "Install it in the project venv with: python -m pip install PyMuPDF Pillow"
            ) from exc
        Image = PILImage
        ImageDraw = PILImageDraw
    return Image, ImageDraw


def _body_rect() -> "fitz.Rect":
    return _load_fitz().Rect(*BODY_RECT_VALUES)


@lru_cache(maxsize=4096)
def _page_text(page: "fitz.Page") -> str:
    return page.get_text()


@lru_cache(maxsize=4096)
def _page_words(page: "fitz.Page") -> tuple[tuple, ...]:
    return tuple(page.get_text("words"))


@lru_cache(maxsize=1024)
def _page_rawdict(page: "fitz.Page") -> dict:
    return page.get_text("rawdict")


@lru_cache(maxsize=1024)
def _page_drawings(page: "fitz.Page") -> tuple[dict, ...]:
    return tuple(page.get_drawings())


@lru_cache(maxsize=1024)
def _page_image_info(page: "fitz.Page") -> tuple[dict, ...]:
    return tuple(page.get_image_info())


def _clear_runtime_caches() -> None:
    _page_text.cache_clear()
    _page_words.cache_clear()
    _page_rawdict.cache_clear()
    _page_drawings.cache_clear()
    _page_image_info.cache_clear()
    _raster_page_image.cache_clear()
    _is_raster_only_page.cache_clear()


def _split_qp(document: "fitz.Document", asset: PaperAsset, output_dir: Path, options: CutterOptions, source_pdf_path: Path) -> list[dict[str, object]]:
    plans = _qp_question_plans(document)
    output: list[dict[str, object]] = []
    written_paths: list[Path] = []
    for plan in plans:
        clips: list[tuple[int, "fitz.Rect"]] = []
        for question_range in plan.ranges:
            range_clips = _qp_question_clips(document, question_range)
            if not range_clips:
                continue
            _audit_qp_question_coverage(document, question_range, range_clips)
            clips.extend(range_clips)
        if not clips:
            continue
        images = [_render_qp_clip(document, page_index, clip, options.dpi) for page_index, clip in clips]
        question_image = _join_images(images)
        _validate_rendered_question(asset, plan.question_number, question_image, options.dpi)
        destination = output_dir / f"{asset.stem}_q{_safe_question_number(plan.question_number)}.jpg"
        if options.overwrite or not destination.exists():
            question_image.save(
                destination,
                format="JPEG",
                quality=options.quality,
                optimize=False,
                progressive=False,
                dpi=(options.dpi, options.dpi),
            )
        manifest_path = output_dir / f"{asset.stem}_q{_safe_question_number(plan.question_number)}.json"
        crop_regions = _build_crop_regions(asset, source_pdf_path, document, clips, options.dpi)
        content = extract_content_from_fitz_clips(document, clips, question_image)
        manifest = _write_manifest(
            asset,
            output_dir,
            plan.question_number,
            clips[0][0] + 1,
            clips[-1][0] + 1,
            "cie_9231_qp_geometry",
            content=content,
            crop_regions=crop_regions,
        )
        written_paths.extend([destination, manifest_path])
        output.append(manifest)
    _remove_stale_asset_slices(output_dir, asset.stem, written_paths)
    return output


def _split_ms(document: "fitz.Document", asset: PaperAsset, output_dir: Path, options: CutterOptions, source_pdf_path: Path) -> list[dict[str, object]]:
    starts = _ms_split_starts(document)
    output: list[dict[str, object]] = []
    written_paths: list[Path] = []
    for index, start in enumerate(starts):
        following = starts[index + 1] if index + 1 < len(starts) else None
        segments = _ms_question_segments(document, start, following, options.dpi)
        if not segments:
            raise ValueError(f"{asset.stem}: mark scheme question {start.question_number} has no rendered content")
        images = [segment.image for segment in segments]
        question_image = _join_images(images)
        _validate_rendered_question(asset, start.question_number, question_image, options.dpi)
        destination = output_dir / f"{asset.stem}_q{_safe_question_number(start.question_number)}.jpg"
        if options.overwrite or not destination.exists():
            question_image.save(
                destination,
                format="JPEG",
                quality=options.quality,
                optimize=False,
                progressive=False,
                dpi=(options.dpi, options.dpi),
            )
        page_end = (
            following.page_index + 1
            if following and following.page_index == start.page_index
            else (following.page_index if following else document.page_count)
        )
        crop_regions = [
            _crop_region(
                asset,
                source_pdf_path,
                document,
                segment.page_index,
                segment.clip,
                order,
                options.dpi,
                post_render_crop_px=segment.post_render_crop_px,
            )
            for order, segment in enumerate(segments)
        ]
        manifest = _write_manifest(
            asset,
            output_dir,
            start.question_number,
            start.page_index + 1,
            page_end,
            "cie_9231_ms_geometry",
            crop_regions=crop_regions,
        )
        manifest_path = output_dir / f"{asset.stem}_q{_safe_question_number(start.question_number)}.json"
        written_paths.extend([destination, manifest_path])
        output.append(manifest)
    _remove_stale_asset_slices(output_dir, asset.stem, written_paths)
    return output


def _remove_stale_asset_slices(output_dir: Path, stem: str, keep_paths: list[Path]) -> None:
    keep = {path.resolve() for path in keep_paths}
    for path in output_dir.glob(f"{stem}_q*"):
        if path.is_file() and path.resolve() not in keep:
            try:
                path.unlink()
            except OSError:
                continue


def _write_manifest(
    asset: PaperAsset,
    output_dir: Path,
    question_number: str,
    page_start: int,
    page_end: int,
    cutter: str,
    *,
    content: ContentExtraction | None = None,
    crop_regions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    safe_number = _safe_question_number(question_number)
    manifest_path = output_dir / f"{asset.stem}_q{safe_number}.json"
    manifest = build_question_manifest(
        asset,
        question_number,
        page_start,
        page_end,
        cutter,
        content=content,
        crop_regions=crop_regions,
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _build_crop_regions(
    asset: PaperAsset,
    source_pdf_path: Path,
    document: "fitz.Document",
    clips: list[tuple[int, "fitz.Rect"]],
    dpi: int,
) -> list[dict[str, object]]:
    return [
        _crop_region(asset, source_pdf_path, document, page_index, clip, order, dpi)
        for order, (page_index, clip) in enumerate(clips)
    ]


def _crop_region(
    asset: PaperAsset,
    source_pdf_path: Path,
    document: "fitz.Document",
    page_index: int,
    clip: "fitz.Rect",
    order: int,
    dpi: int,
    *,
    post_render_crop_px: dict[str, object] | None = None,
) -> dict[str, object]:
    page = document[page_index]
    region: dict[str, object] = {
        "order": order,
        "source_pdf": build_frank_cie_url(asset),
        "source_pdf_sha256": _file_sha256(str(source_pdf_path.resolve())),
        "source_stem": asset.stem,
        "document_type": asset.document_type,
        "page_index": page_index,
        "page_number": page_index + 1,
        "page_width": _round_float(page.rect.width),
        "page_height": _round_float(page.rect.height),
        "page_rotation": int(page.rotation),
        "coordinate_space": "pymupdf_page_points",
        "unit": "pt",
        "rect": _rect_payload(clip),
        "render_dpi": dpi,
        "join_gap_before_px": 0 if order == 0 else JOIN_GAP_PIXELS,
    }
    if post_render_crop_px is not None:
        region["post_render_crop_px"] = post_render_crop_px
    return region


def _rect_payload(rect: "fitz.Rect") -> dict[str, float]:
    return {
        "x0": _round_float(rect.x0),
        "y0": _round_float(rect.y0),
        "x1": _round_float(rect.x1),
        "y1": _round_float(rect.y1),
    }


def _round_float(value: float) -> float:
    return round(float(value), 3)


@lru_cache(maxsize=2048)
def _file_sha256(path_text: str) -> str:
    digest = hashlib.sha256()
    with Path(path_text).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_question_number(question_number: str) -> str:
    parts = re.findall(r"[0-9]+|[A-Za-z]+", question_number)
    if not parts:
        return re.sub(r"[^A-Za-z0-9_-]+", "_", question_number).strip("_") or "unknown"
    if parts[0].isdigit():
        parts[0] = parts[0].zfill(2)
    return "_".join(part.lower() for part in parts)


def _validate_rendered_question(asset: PaperAsset, question_number: str, image: "PILImage.Image", dpi: int) -> None:
    min_height = max(18, round(dpi * 0.12)) if asset.document_type == "ms" else max(28, round(dpi * 0.20))
    min_width = max(120, round(dpi * 0.75))
    if image.height < min_height or image.width < min_width:
        raise ValueError(
            f"{asset.stem}: question {question_number} rendered too small "
            f"({image.width}x{image.height}); boundary detection is unreliable"
        )


def _block_text(block: dict) -> str:
    return "".join(character["c"] for line in block.get("lines", []) for span in line.get("spans", []) for character in span.get("chars", []))


def _is_repeated_answer_line(block: dict) -> bool:
    text = _block_text(block)
    if len(text) < 25:
        return False
    non_space = text.replace(" ", "")
    if not non_space:
        return False
    most_common = max(non_space.count(character) for character in set(non_space))
    return len(set(non_space)) <= 2 or most_common / len(non_space) >= 0.9


def _is_page_number_rect(rect: "fitz.Rect", page_rect: "fitz.Rect") -> bool:
    center_offset = abs((rect.x0 + rect.x1) / 2 - page_rect.width / 2)
    return center_offset < 35 and ((rect.width < 30 and (rect.y0 < 70 or rect.y1 > 690)) or (rect.width < 8 and rect.height < 8))


@lru_cache(maxsize=512)
def _raster_page_image(page: "fitz.Page") -> Image.Image:
    _load_pillow()
    fitz_module = _load_fitz()
    pixmap = page.get_pixmap(matrix=fitz_module.Matrix(RASTER_LAYOUT_SCALE, RASTER_LAYOUT_SCALE), colorspace=fitz_module.csGRAY, alpha=False)
    return Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)


@lru_cache(maxsize=2048)
def _is_raster_only_page(page: "fitz.Page") -> bool:
    if _page_words(page):
        return False
    return any(_load_fitz().Rect(image["bbox"]).width > page.rect.width * 0.8 and _load_fitz().Rect(image["bbox"]).height > page.rect.height * 0.8 for image in _page_image_info(page))


def _qp_raster_question_starts(document: "fitz.Document") -> list[tuple[int, float]]:
    starts: list[tuple[int, float]] = []
    body = _body_rect()
    scale = RASTER_LAYOUT_SCALE
    for page_index in range(1, document.page_count):
        image = _raster_page_image(document[page_index])
        pixels = image.load()
        x0, x1 = int(57.5 * scale), int(85 * scale)
        y0 = int(body.y0 * scale)
        y1 = min(image.height, int(body.y1 * scale))
        seen: set[tuple[int, int]] = set()
        components: list[tuple[int, int, int, int, int]] = []
        for y in range(y0, y1):
            for x in range(x0, x1):
                if pixels[x, y] >= RASTER_INK_THRESHOLD or (x, y) in seen:
                    continue
                stack = [(x, y)]
                seen.add((x, y))
                xs: list[int] = []
                ys: list[int] = []
                while stack:
                    current_x, current_y = stack.pop()
                    xs.append(current_x)
                    ys.append(current_y)
                    for neighbor in ((current_x - 1, current_y), (current_x + 1, current_y), (current_x, current_y - 1), (current_x, current_y + 1)):
                        if x0 <= neighbor[0] < x1 and y0 <= neighbor[1] < y1 and pixels[neighbor[0], neighbor[1]] < RASTER_INK_THRESHOLD and neighbor not in seen:
                            seen.add(neighbor)
                            stack.append(neighbor)
                width = max(xs) - min(xs) + 1
                height = max(ys) - min(ys) + 1
                if 3 <= width <= 16 and 9 <= height <= 22 and len(xs) >= 25:
                    components.append((min(xs), min(ys), width, height, len(xs)))
        row_starts: list[int] = []
        for component in sorted(components, key=lambda item: item[1]):
            if not row_starts or component[1] - row_starts[-1] > 4:
                row_starts.append(component[1])
        starts.extend((page_index, y / scale) for y in row_starts if y / scale < 650)
    if not starts:
        raise ValueError("no question starts detected from raster layout")
    return starts


def _qp_question_starts(document: "fitz.Document") -> list[tuple[int, float]]:
    starts: list[tuple[int, float]] = []
    body = _body_rect()
    if document.page_count < 2:
        raise ValueError(f"unexpected page count: {document.page_count}")
    first_content_page = 1
    for page_index in range(first_content_page, document.page_count):
        page = document[page_index]
        if _is_qp_front_matter_page(page):
            continue
        page_text_starts = _qp_text_question_starts(page, body)
        starts.extend(page_text_starts)
        if page_text_starts:
            continue
        if _is_raster_only_page(page):
            continue
        for block in _page_rawdict(page)["blocks"]:
            if block["type"] != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    rect = _load_fitz().Rect(span["bbox"])
                    label = _block_text({"lines": [{"spans": [span]}]}).strip()
                    if (
                        70.0 <= rect.x0 <= 74.0
                        and 5.0 <= rect.width <= 16.0
                        and 9.0 <= rect.height <= 36.0
                        and ("Bold" in span["font"] or span["font"].startswith("AllAndNone"))
                        and (_is_ascii_integer(label) or not label or span["font"].startswith("AllAndNone") or (len(label) <= 3 and any(ord(character) < 32 for character in label)))
                        and body.y0 <= rect.y0 <= body.y1 - 50.0
                    ):
                        starts.append((page_index, rect.y0))
    return sorted(set(starts)) if starts else _qp_raster_question_starts(document)


def _qp_first_content_page(document: "fitz.Document") -> int:
    for page_index in range(1, document.page_count):
        page = document[page_index]
        if _is_qp_front_matter_page(page):
            continue
        if _qp_text_question_starts(page, _body_rect()) or _is_raster_only_page(page):
            return page_index
    return 1 if document.page_count > 1 else 0


def _is_qp_front_matter_page(page: "fitz.Page") -> bool:
    normalized_text = re.sub(r"\s+", " ", _page_text(page).upper())
    return any(pattern in normalized_text for pattern in QP_FRONT_MATTER_PATTERNS)


def _qp_text_question_starts(page: "fitz.Page", body: "fitz.Rect") -> list[tuple[int, float]]:
    fitz_module = _load_fitz()
    starts: list[tuple[int, float]] = []
    words = sorted(_page_words(page), key=lambda item: (item[1], item[0]))
    for word in words:
        label = str(word[4]).strip()
        if not _is_ascii_integer(label):
            continue
        number = int(label)
        if not 1 <= number <= 30:
            continue
        rect = fitz_module.Rect(word[:4])
        if not (52.0 <= rect.x0 <= 82.0 and body.y0 <= rect.y0 <= body.y1 - 50.0 and rect.width <= 22.0 and rect.height <= 18.0):
            continue
        if starts and abs(starts[-1][1] - rect.y0) < 8:
            continue
        starts.append((page.number, rect.y0))
    return starts


def _is_ascii_integer(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9]+", value))


def _qp_question_ranges(document: "fitz.Document") -> list[tuple[tuple[int, float], tuple[int, float]]]:
    body = _body_rect()
    starts = _qp_question_starts(document)
    ranges = []
    for index, start in enumerate(starts):
        start_page, start_y = start
        safe_start = (start_page, max(body.y0, start_y - TOP_RANGE_SAFETY_POINTS))
        if index + 1 < len(starts):
            next_page, next_y = starts[index + 1]
            end = (next_page, body.y0) if next_page > start_page else (next_page, max(body.y0, next_y - END_RANGE_SAFETY_POINTS))
        else:
            end = (document.page_count - 1, body.y1)
        ranges.append((safe_start, end))
    return ranges


def _qp_question_plans(document: "fitz.Document") -> list[QuestionClipPlan]:
    plans: list[QuestionClipPlan] = []
    for top_level_number, question_range in enumerate(_qp_question_ranges(document), start=1):
        plans.extend(_qp_subquestion_plans(document, top_level_number, question_range))
    return plans


def _qp_subquestion_plans(
    document: "fitz.Document",
    top_level_number: int,
    question_range: tuple[tuple[int, float], tuple[int, float]],
) -> list[QuestionClipPlan]:
    boundaries = _qp_subpart_boundaries(document, question_range)
    if not boundaries:
        return [QuestionClipPlan(str(top_level_number), (question_range,))]

    first_boundary = boundaries[0]
    top_preamble = _bounded_range(question_range[0], _end_before_boundary(first_boundary), question_range)
    parent_preambles = _qp_parent_preamble_ranges(boundaries, question_range)
    plans: list[QuestionClipPlan] = []
    for index, boundary in enumerate(boundaries):
        next_boundary = boundaries[index + 1] if index + 1 < len(boundaries) else None
        if next_boundary and next_boundary.depth > boundary.depth:
            continue
        segment_end = _end_before_boundary(next_boundary) if next_boundary else question_range[1]
        segment_range = _bounded_range(_start_at_boundary(boundary), segment_end, question_range)
        ranges = []
        if top_preamble is not None:
            ranges.append(top_preamble)
        if boundary.depth > 1:
            parent_preamble = parent_preambles.get(boundary.path[:-1])
            if parent_preamble is not None:
                ranges.append(parent_preamble)
        if segment_range is not None:
            ranges.append(segment_range)
        if ranges:
            plans.append(QuestionClipPlan(f"{top_level_number}{''.join(boundary.path)}", tuple(ranges)))
    return plans or [QuestionClipPlan(str(top_level_number), (question_range,))]


def _qp_subpart_boundaries(
    document: "fitz.Document",
    question_range: tuple[tuple[int, float], tuple[int, float]],
) -> list[QpPartBoundary]:
    fitz_module = _load_fitz()
    (start_page, start_y), (end_page, end_y) = question_range
    boundaries: list[QpPartBoundary] = []
    for page_index in range(start_page, min(end_page + 1, document.page_count)):
        page = document[page_index]
        page_y0 = start_y if page_index == start_page else _body_rect().y0
        page_y1 = end_y if page_index == end_page else _body_rect().y1
        for word in _page_words(page):
            raw_label = str(word[4])
            label = _normalize_qp_subpart_label(raw_label)
            if label is None:
                continue
            rect = fitz_module.Rect(word[:4])
            if not _is_qp_subpart_label_rect(rect, page_y0, page_y1):
                continue
            if _is_bare_option_label(raw_label) and rect.x0 >= 112.0:
                continue
            depth = 2 if rect.x0 >= 112.0 else 1
            boundaries.append(QpPartBoundary(label=label, depth=depth, page_index=page_index, display_y=rect.y0, x0=rect.x0))
    if not boundaries and not _qp_range_has_readable_text(document, question_range):
        boundaries = _qp_raster_subpart_boundaries(document, question_range)
    return _qp_assign_subpart_paths(_dedupe_qp_part_boundaries(boundaries))


def _qp_range_has_readable_text(
    document: "fitz.Document",
    question_range: tuple[tuple[int, float], tuple[int, float]],
) -> bool:
    (start_page, _start_y), (end_page, _end_y) = question_range
    parts: list[str] = []
    for page_index in range(start_page, min(end_page + 1, document.page_count)):
        parts.append(_page_text(document[page_index]))
    text = "\n".join(parts)
    visible = [character for character in text if not character.isspace()]
    if len(visible) < 20:
        return False
    c1_controls = sum(1 for character in visible if "\x80" <= character <= "\x9f")
    if c1_controls / len(visible) > 0.005:
        return False
    ascii_letters = sum(1 for character in visible if ("A" <= character <= "Z") or ("a" <= character <= "z"))
    has_exam_words = bool(re.search(r"\b(deduce|determine|find|given|give|hence|let|prove|show|use|where)\b", text, re.I))
    return has_exam_words or ascii_letters / len(visible) >= 0.02


def _qp_raster_subpart_boundaries(
    document: "fitz.Document",
    question_range: tuple[tuple[int, float], tuple[int, float]],
) -> list[QpPartBoundary]:
    (start_page, start_y), (end_page, end_y) = question_range
    last_page = end_page if end_y > _body_rect().y0 else end_page - 1
    rows: list[tuple[int, float]] = []
    for page_index in range(start_page, min(last_page + 1, document.page_count)):
        if page_index > start_page and _is_qp_auxiliary_page(document[page_index]):
            continue
        page_y0 = start_y if page_index == start_page else _body_rect().y0
        page_y1 = end_y if page_index == end_page else _body_rect().y1
        rows.extend((page_index, row_y) for row_y in _qp_raster_subpart_rows(document[page_index], page_y0, page_y1))
    rows = _prune_qp_raster_subpart_rows(rows, question_range)
    if not rows:
        return []
    return [
        QpPartBoundary(
            label=f"({chr(ord('a') + index)})",
            depth=1,
            page_index=page_index,
            display_y=row_y,
            x0=92.0,
        )
        for index, (page_index, row_y) in enumerate(rows)
        if index < 26
    ]


def _prune_qp_raster_subpart_rows(
    rows: list[tuple[int, float]],
    question_range: tuple[tuple[int, float], tuple[int, float]],
) -> list[tuple[int, float]]:
    if not rows:
        return rows
    (start_page, start_y), _end = question_range
    first_page, first_y = rows[0]
    if first_page != start_page or first_y - start_y > 28.0:
        return rows
    following_same_page = rows[1] if len(rows) > 1 and rows[1][0] == first_page else None
    if len(rows) == 1 or (following_same_page is not None and following_same_page[1] - first_y < 120.0):
        return rows[1:]
    return rows


def _qp_raster_subpart_rows(page: "fitz.Page", y0_points: float, y1_points: float) -> list[float]:
    scale = RASTER_LAYOUT_SCALE
    image = _raster_page_image(page)
    pixels = image.load()
    x0, x1 = int(88.0 * scale), int(132.0 * scale)
    y0 = int(max(58.0, y0_points) * scale)
    y1 = min(image.height, int(min(_body_rect().y1, y1_points) * scale))
    seen: set[tuple[int, int]] = set()
    components: list[tuple[float, float, float, float, int]] = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if pixels[x, y] >= RASTER_INK_THRESHOLD or (x, y) in seen:
                continue
            stack = [(x, y)]
            seen.add((x, y))
            xs: list[int] = []
            ys: list[int] = []
            while stack:
                current_x, current_y = stack.pop()
                xs.append(current_x)
                ys.append(current_y)
                for neighbor in ((current_x - 1, current_y), (current_x + 1, current_y), (current_x, current_y - 1), (current_x, current_y + 1)):
                    if x0 <= neighbor[0] < x1 and y0 <= neighbor[1] < y1 and pixels[neighbor[0], neighbor[1]] < RASTER_INK_THRESHOLD and neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
            width = (max(xs) - min(xs) + 1) / scale
            height = (max(ys) - min(ys) + 1) / scale
            ink = len(xs)
            if 1.0 <= width <= 30.0 and 4.0 <= height <= 18.0 and ink >= 10:
                components.append((min(xs) / scale, min(ys) / scale, width, height, ink))

    row_groups: list[list[tuple[float, float, float, float, int]]] = []
    for component in sorted(components, key=lambda item: item[1]):
        if not row_groups or component[1] - row_groups[-1][0][1] > 36.0:
            row_groups.append([component])
        else:
            row_groups[-1].append(component)
    rows: list[float] = []
    for group in row_groups:
        left = min(component[0] for component in group)
        right = max(component[0] + component[2] for component in group)
        if len(group) >= 5 and right - left >= 30.0:
            rows.append(min(component[1] for component in group))
    return rows


def _normalize_qp_subpart_label(value: str) -> str | None:
    clean = value.strip().rstrip(".").replace(" ", "")
    if BARE_OPTION_LABEL_PATTERN.fullmatch(clean):
        return f"({clean.lower()})"
    if not (clean.startswith("(") and clean.endswith(")")):
        return None
    token = clean[1:-1].strip()
    if not LABEL_TOKEN_PATTERN.fullmatch(token):
        return None
    return f"({token.lower()})"


def _is_bare_option_label(value: str) -> bool:
    return bool(BARE_OPTION_LABEL_PATTERN.fullmatch(value.strip().rstrip(".").replace(" ", "")))


def _is_qp_subpart_label_rect(rect: "fitz.Rect", page_y0: float, page_y1: float) -> bool:
    return (
        88.0 <= rect.x0 <= 132.0
        and page_y0 <= rect.y0 <= page_y1 - 8.0
        and 7.0 <= rect.width <= 25.0
        and 7.0 <= rect.height <= 18.0
    )


def _dedupe_qp_part_boundaries(boundaries: list[QpPartBoundary]) -> list[QpPartBoundary]:
    output: list[QpPartBoundary] = []
    for boundary in sorted(boundaries, key=lambda item: (item.page_index, item.display_y, item.x0)):
        if output and boundary.page_index == output[-1].page_index and abs(boundary.display_y - output[-1].display_y) < 4 and boundary.label == output[-1].label:
            continue
        output.append(boundary)
    return output


def _qp_assign_subpart_paths(boundaries: list[QpPartBoundary]) -> list[QpPartBoundary]:
    output: list[QpPartBoundary] = []
    current_parent: QpPartBoundary | None = None
    for boundary in boundaries:
        if boundary.depth <= 1:
            current_parent = boundary
            output.append(
                QpPartBoundary(
                    label=boundary.label,
                    depth=1,
                    page_index=boundary.page_index,
                    display_y=boundary.display_y,
                    x0=boundary.x0,
                    path=(boundary.label,),
                )
            )
            continue
        path = (current_parent.label, boundary.label) if current_parent is not None else (boundary.label,)
        output.append(
            QpPartBoundary(
                label=boundary.label,
                depth=boundary.depth,
                page_index=boundary.page_index,
                display_y=boundary.display_y,
                x0=boundary.x0,
                path=path,
            )
        )
    return output


def _qp_parent_preamble_ranges(
    boundaries: list[QpPartBoundary],
    question_range: tuple[tuple[int, float], tuple[int, float]],
) -> dict[tuple[str, ...], tuple[tuple[int, float], tuple[int, float]]]:
    preambles: dict[tuple[str, ...], tuple[tuple[int, float], tuple[int, float]]] = {}
    for index, boundary in enumerate(boundaries):
        next_boundary = boundaries[index + 1] if index + 1 < len(boundaries) else None
        if not next_boundary or next_boundary.depth <= boundary.depth:
            continue
        preamble = _bounded_range(_start_at_boundary(boundary), _end_before_boundary(next_boundary), question_range)
        if preamble is not None:
            preambles[boundary.path] = preamble
    return preambles


def _start_at_boundary(boundary: QpPartBoundary) -> tuple[int, float]:
    body = _body_rect()
    return (boundary.page_index, max(body.y0, boundary.display_y - TOP_RANGE_SAFETY_POINTS))


def _end_before_boundary(boundary: QpPartBoundary | None) -> tuple[int, float]:
    body = _body_rect()
    if boundary is None:
        return (0, body.y1)
    return (boundary.page_index, max(body.y0, boundary.display_y - END_RANGE_SAFETY_POINTS))


def _bounded_range(
    start: tuple[int, float],
    end: tuple[int, float],
    bounds: tuple[tuple[int, float], tuple[int, float]],
) -> tuple[tuple[int, float], tuple[int, float]] | None:
    (bounds_start_page, bounds_start_y), (bounds_end_page, bounds_end_y) = bounds
    start_page, start_y = start
    end_page, end_y = end
    if start_page < bounds_start_page or (start_page == bounds_start_page and start_y < bounds_start_y):
        start_page, start_y = bounds_start_page, bounds_start_y
    if end_page > bounds_end_page or (end_page == bounds_end_page and end_y > bounds_end_y):
        end_page, end_y = bounds_end_page, bounds_end_y
    if (end_page, end_y) <= (start_page, start_y):
        return None
    return ((start_page, start_y), (end_page, end_y))


def _qp_content_rects(page: "fitz.Page", y0: float, y1: float) -> list["fitz.Rect"]:
    fitz_module = _load_fitz()
    body = _body_rect()
    rects: list[fitz.Rect] = []
    allowed = fitz_module.Rect(body.x0, max(body.y0, y0), body.x1, min(body.y1, y1))
    if allowed.is_empty:
        return rects
    if _is_raster_only_page(page):
        return _qp_raster_content_rects(page, allowed)
    for block in _page_rawdict(page)["blocks"]:
        if block["type"] != 0 or _is_repeated_answer_line(block):
            continue
        rect = fitz_module.Rect(block["bbox"])
        if _is_page_number_rect(rect, page.rect) or _is_qp_header_barcode_rect(rect) or (rect.y0 > 700 and rect.width > 350) or (rect.width > 100 and rect.height < 3):
            continue
        if rect.intersects(allowed):
            clipped = rect & allowed
            if not (rect.y0 < allowed.y0 and clipped.height < 3):
                rects.append(clipped)
    for drawing in _page_drawings(page):
        rect = fitz_module.Rect(drawing["rect"])
        if not _is_page_number_rect(rect, page.rect) and not _is_qp_header_barcode_rect(rect) and not (rect.width > 100 and rect.height < 3) and rect.intersects(allowed):
            clipped = rect & allowed
            if not (rect.y0 < allowed.y0 and clipped.height < 3):
                rects.append(clipped)
    for image in _page_image_info(page):
        rect = fitz_module.Rect(image["bbox"])
        if not _is_page_number_rect(rect, page.rect) and not _is_qp_header_barcode_rect(rect) and not (rect.width > 100 and rect.height < 3) and rect.intersects(allowed):
            clipped = rect & allowed
            if not (rect.y0 < allowed.y0 and clipped.height < 3):
                rects.append(clipped)
    return [rect for rect in rects if not rect.is_empty]


def _is_qp_header_barcode_rect(rect: "fitz.Rect") -> bool:
    return rect.y0 < 70.0 and rect.width > 80.0 and rect.height < 8.0


def _qp_raster_content_rects(page: "fitz.Page", allowed: "fitz.Rect") -> list["fitz.Rect"]:
    fitz_module = _load_fitz()
    scale = RASTER_LAYOUT_SCALE
    image = _raster_page_image(page)
    crop = image.crop((int(allowed.x0 * scale), int(allowed.y0 * scale), int(allowed.x1 * scale), int(allowed.y1 * scale))).point(lambda value: 255 if value < RASTER_INK_THRESHOLD else 0, mode="1")
    active_rows = [y for y in range(crop.height) if crop.crop((0, y, crop.width, y + 1)).getbbox()]
    if not active_rows:
        return []
    bands: list[tuple[int, int]] = []
    start = previous = active_rows[0]
    for y in active_rows[1:]:
        if y - previous > 3:
            bands.append((start, previous + 1))
            start = y
        previous = y
    bands.append((start, previous + 1))
    rects = []
    for band_y0, band_y1 in bands:
        bbox = crop.crop((0, band_y0, crop.width, band_y1)).getbbox()
        if bbox is None or band_y1 - band_y0 < 2:
            continue
        rect = fitz_module.Rect(allowed.x0 + bbox[0] / scale, allowed.y0 + band_y0 / scale, allowed.x0 + bbox[2] / scale, allowed.y0 + band_y1 / scale)
        if not _is_page_number_rect(rect, page.rect):
            rects.append(rect)
    return rects


def _is_qp_auxiliary_page(page: "fitz.Page") -> bool:
    body = _body_rect()
    if _is_raster_only_page(page):
        image = _raster_page_image(page)
        scale = RASTER_LAYOUT_SCALE
        body_image = image.crop((int(body.x0 * scale), int(body.y0 * scale), int(body.x1 * scale), int(body.y1 * scale)))
        return sum(body_image.histogram()[:RASTER_INK_THRESHOLD]) < 5000
    normalized_text = re.sub(r"[^A-Z]", "", _page_text(page).upper())
    if "BLANKPAGE" in normalized_text or "ADDITIONALPAGE" in normalized_text:
        return True
    raw_blocks = _page_rawdict(page)["blocks"]
    repeated_count = sum(block["type"] == 0 and _load_fitz().Rect(block["bbox"]).intersects(body) and _is_repeated_answer_line(block) for block in raw_blocks)
    meaningful_rects = []
    has_body_indent_span = False
    for block in raw_blocks:
        if block["type"] != 0 or _is_repeated_answer_line(block):
            continue
        rect = _load_fitz().Rect(block["bbox"])
        if rect.y0 > 700 and rect.width > 350:
            continue
        if rect.intersects(body):
            meaningful_rects.append(rect & body)
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_rect = _load_fitz().Rect(span["bbox"])
                if 88 <= span_rect.x0 <= 105 and body.y0 <= span_rect.y0 <= body.y1:
                    has_body_indent_span = True
    has_graphics = any(_load_fitz().Rect(drawing["rect"]).intersects(body) for drawing in _page_drawings(page)) or any(_load_fitz().Rect(image["bbox"]).intersects(body) for image in _page_image_info(page))
    if meaningful_rects and min(rect.y0 for rect in meaningful_rects) > 650:
        return True
    if has_body_indent_span or has_graphics:
        return False
    has_middle_content = any(120 < rect.y0 < 650 for rect in meaningful_rects)
    if has_middle_content:
        return False
    has_centered_template_heading = any(200 < rect.x0 < 320 and rect.x1 < 420 and 55 < rect.y0 < 120 for rect in meaningful_rects)
    return repeated_count >= 5 or has_centered_template_heading or not meaningful_rects


def _cluster_content(rects: list["fitz.Rect"], bounds: "fitz.Rect") -> list["fitz.Rect"]:
    if not rects:
        return []
    ordered = sorted(rects, key=lambda rect: (rect.y0, rect.x0))
    clusters: list[list[fitz.Rect]] = [[ordered[0]]]
    cluster_bottom = ordered[0].y1
    for rect in ordered[1:]:
        if rect.y0 - cluster_bottom > VERTICAL_CLUSTER_GAP:
            clusters.append([rect])
        else:
            clusters[-1].append(rect)
        cluster_bottom = max(cluster_bottom, rect.y1)
    output = []
    for cluster in clusters:
        united = _load_fitz().Rect(cluster[0])
        for rect in cluster[1:]:
            united |= rect
        united.x0 = max(bounds.x0, united.x0 - HORIZONTAL_PADDING_POINTS)
        united.y0 = max(bounds.y0, united.y0 - TOP_PADDING_POINTS)
        united.x1 = min(bounds.x1, united.x1 + HORIZONTAL_PADDING_POINTS)
        united.y1 = min(bounds.y1, united.y1 + BOTTOM_PADDING_POINTS)
        if united.width > 10 and united.height > 5:
            output.append(united)
    return output


def _qp_question_clips(document: "fitz.Document", question_range: tuple[tuple[int, float], tuple[int, float]]) -> list[tuple[int, "fitz.Rect"]]:
    body = _body_rect()
    clips: list[tuple[int, fitz.Rect]] = []
    (start_page, start_y), (end_page, end_y) = question_range
    last_page = end_page if end_y > body.y0 else end_page - 1
    for page_index in range(start_page, min(last_page + 1, document.page_count)):
        page = document[page_index]
        if page_index > start_page and _is_qp_auxiliary_page(page):
            continue
        page_y0 = start_y if page_index == start_page else body.y0
        page_y1 = end_y if page_index == end_page else body.y1
        bounds = _load_fitz().Rect(body.x0, page_y0, body.x1, page_y1)
        clips.extend((page_index, rect) for rect in _cluster_content(_qp_content_rects(page, page_y0, page_y1), bounds))
    return clips


def _audit_qp_question_coverage(document: "fitz.Document", question_range: tuple[tuple[int, float], tuple[int, float]], clips: list[tuple[int, "fitz.Rect"]]) -> None:
    body = _body_rect()
    (start_page, start_y), (end_page, end_y) = question_range
    last_page = end_page if end_y > body.y0 else end_page - 1
    clips_by_page: dict[int, list[fitz.Rect]] = {}
    for page_index, clip in clips:
        clips_by_page.setdefault(page_index, []).append(clip)
    missed = []
    for page_index in range(start_page, min(last_page + 1, document.page_count)):
        if page_index > start_page and _is_qp_auxiliary_page(document[page_index]):
            continue
        page_y0 = start_y if page_index == start_page else body.y0
        page_y1 = end_y if page_index == end_page else body.y1
        for rect in _qp_content_rects(document[page_index], page_y0, page_y1):
            if not any(clip.contains(rect) for clip in clips_by_page.get(page_index, [])):
                missed.append((page_index + 1, tuple(round(value, 2) for value in rect)))
    if missed:
        raise ValueError(f"question content coverage audit failed: {missed[:5]}")


def _render_qp_clip(document: "fitz.Document", page_index: int, clip: "fitz.Rect", dpi: int) -> Image.Image:
    fitz_module = _load_fitz()
    page = document.load_page(page_index)
    pixmap = page.get_pixmap(dpi=dpi, colorspace=fitz_module.csGRAY, alpha=False, clip=clip)
    image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
    draw = ImageDraw.Draw(image)
    scale = dpi / 72.0
    _mask_qp_header_templates(draw, image, clip, scale)
    for block in _page_rawdict(page)["blocks"]:
        if block["type"] != 0 or not _is_repeated_answer_line(block):
            continue
        rect = fitz_module.Rect(block["bbox"])
        if not rect.intersects(clip):
            continue
        masked = rect & clip
        draw.rectangle(
            (
                max(0, int((masked.x0 - clip.x0) * scale) - 2),
                max(0, int((masked.y0 - clip.y0) * scale) - 2),
                min(image.width, int((masked.x1 - clip.x0) * scale) + 2),
                min(image.height, int((masked.y1 - clip.y0) * scale) + 2),
            ),
            fill=255,
        )
    return image


def _mask_qp_header_templates(draw, image: "PILImage.Image", clip: "fitz.Rect", scale: float) -> None:
    fitz_module = _load_fitz()
    for rect in (fitz_module.Rect(80.0, 42.0, 280.0, 66.0),):
        if not rect.intersects(clip):
            continue
        masked = rect & clip
        draw.rectangle(
            (
                max(0, int((masked.x0 - clip.x0) * scale) - 2),
                max(0, int((masked.y0 - clip.y0) * scale) - 2),
                min(image.width, int((masked.x1 - clip.x0) * scale) + 2),
                min(image.height, int((masked.y1 - clip.y0) * scale) + 2),
            ),
            fill=255,
        )


def _ms_display_rect(page: "fitz.Page", rect: "fitz.Rect") -> "fitz.Rect":
    return rect * page.rotation_matrix


def _ms_is_full_page_image(page: "fitz.Page") -> bool:
    if _page_words(page):
        return False
    fitz_module = _load_fitz()
    return any(_ms_display_rect(page, fitz_module.Rect(info["bbox"])).width > page.rect.width * 0.75 and _ms_display_rect(page, fitz_module.Rect(info["bbox"])).height > page.rect.height * 0.75 for info in _page_image_info(page))


def _ms_is_answer_table_page(page: "fitz.Page") -> bool:
    labels = {word[4].strip().lower() for word in _page_words(page)}
    return {"question", "answer", "marks"}.issubset(labels) and "guidance" in labels


def _ms_has_answer_section_evidence(page: "fitz.Page") -> bool:
    if _ms_is_answer_table_page(page):
        return True
    normalized_text = re.sub(r"\s+", " ", _page_text(page).upper())
    return bool(re.search(r"\b[BMAD]M?\d\b|\b[BMA]\d\b", normalized_text)) and "MARKING PRINCIPLE" not in normalized_text


def _ms_is_text_front_matter_page(page: "fitz.Page") -> bool:
    normalized_text = re.sub(r"\s+", " ", _page_text(page).upper())
    return any(pattern in normalized_text for pattern in MS_FRONT_MATTER_PATTERNS)


def _ms_is_pre_answer_notes_page(page: "fitz.Page") -> bool:
    normalized_text = re.sub(r"\s+", " ", _page_text(page).upper())
    if MS_ANSWER_TABLE_PATTERN in normalized_text:
        return False
    return any(pattern in normalized_text for pattern in MS_PRE_ANSWER_PATTERNS)


def _ms_label_match(value: str) -> tuple[str, re.Match[str] | None]:
    clean_label = _normalize_ms_question_label(value.replace(" ", "").rstrip("."))
    return clean_label, QUESTION_LABEL_PATTERN.fullmatch(clean_label)


def _normalize_ms_question_label(value: str) -> str:
    clean = value.strip().rstrip(".").replace(" ", "")
    match = re.fullmatch(r"(?P<number>[0-9]{1,2})(?P<parts>(?:\([A-Za-zivxlcdmIVXLCDM]{1,6}\)|[A-D])*)", clean)
    if not match:
        return clean
    parts: list[str] = []
    for token in re.findall(r"\([A-Za-zivxlcdmIVXLCDM]{1,6}\)|[A-D]", match.group("parts")):
        if token.startswith("("):
            value_token = token[1:-1]
        else:
            value_token = token
        if not LABEL_TOKEN_PATTERN.fullmatch(value_token):
            return clean
        parts.append(f"({value_token.lower()})")
    return f"{match.group('number')}{''.join(parts)}"


def _ms_plain_integer_label(clean_label: str, match: re.Match[str] | None) -> bool:
    return bool(match and clean_label == match.group("number") and _is_ascii_integer(clean_label))


def _ms_find_text_question_column(document: "fitz.Document", answer_start_page: int) -> float | None:
    from statistics import median

    fitz_module = _load_fitz()
    clusters: list[list[tuple[int, int, float]]] = []
    for page_index in range(answer_start_page, document.page_count):
        page = document[page_index]
        for word in _page_words(page):
            clean_label, match = _ms_label_match(str(word[4]))
            if not _ms_plain_integer_label(clean_label, match):
                continue
            number = int(match.group("number"))
            rect = _ms_display_rect(page, fitz_module.Rect(word[:4]))
            if not (1 <= number <= 30 and 50 <= rect.x0 <= 125 and 55 <= rect.y0 <= page.rect.height - 45 and rect.width <= 20):
                continue
            for cluster in clusters:
                if abs(rect.x0 - median(item[2] for item in cluster)) <= 4:
                    cluster.append((number, page_index, rect.x0))
                    break
            else:
                clusters.append([(number, page_index, rect.x0)])
    candidates = []
    for cluster in clusters:
        numbers = {item[0] for item in cluster}
        if 1 not in numbers and len(numbers) < 2:
            continue
        column_x = median(item[2] for item in cluster)
        left_column_bonus = 2 if column_x < 90 else 0
        sequence_bonus = sum(1 for number in range(1, max(numbers) + 1) if number in numbers)
        first_page = min(item[1] for item in cluster)
        candidates.append((left_column_bonus + sequence_bonus + len(numbers), first_page, column_x))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    return candidates[0][2]


def _ms_find_answer_start_page(document: "fitz.Document") -> int:
    fitz_module = _load_fitz()
    if any(page.rotation for page in document):
        first_text_table = None
        for page_index, page in enumerate(document):
            if _ms_is_pre_answer_notes_page(page):
                continue
            for word in _page_words(page):
                label, match = _ms_label_match(str(word[4]))
                rect = _ms_display_rect(page, fitz_module.Rect(word[:4]))
                if match and "(" in label and 48 <= rect.x0 <= 115:
                    first_text_table = page_index
                    break
            if first_text_table is not None:
                break
        if first_text_table is None:
            for page_index, page in enumerate(document):
                if _ms_is_pre_answer_notes_page(page):
                    continue
                if not _ms_has_answer_section_evidence(page):
                    continue
                labels = []
                for word in _page_words(page):
                    label, match = _ms_label_match(str(word[4]))
                    rect = _ms_display_rect(page, fitz_module.Rect(word[:4]))
                    if match and _is_ascii_integer(label) and int(match.group("number")) in (1, 2) and 25 <= rect.x0 <= 100 and 55 <= rect.y0 <= page.rect.height - 45:
                        labels.append((int(match.group("number")), rect.x0))
                if any(number == 1 for number, _ in labels) and any(number == 2 and abs(x2 - x1) <= 8 for number, x2 in labels for first, x1 in labels if first == 1):
                    return page_index
            raise ValueError("cannot find mark-scheme answer table")
        answer_start = first_text_table
        while answer_start > 0 and (
            _ms_is_full_page_image(document[answer_start - 1])
            or _ms_is_answer_table_page(document[answer_start - 1])
        ):
            if _ms_is_pre_answer_notes_page(document[answer_start - 1]):
                break
            answer_start -= 1
        return answer_start
    for page_index, page in enumerate(document):
        if _ms_is_pre_answer_notes_page(page):
            continue
        if not _ms_has_answer_section_evidence(page):
            continue
        labels: list[tuple[int, float]] = []
        for word in _page_words(page):
            clean_label, match = _ms_label_match(str(word[4]))
            rect = _ms_display_rect(page, fitz_module.Rect(word[:4]))
            if match and clean_label == match.group("number") and 50 <= rect.x0 <= 95 and rect.y0 > 55 and rect.width <= 20:
                labels.append((int(match.group("number")), rect.x0))
        numbers = {number for number, _ in labels}
        if 1 in numbers or len(numbers) >= 2:
            return page_index
    raise ValueError("cannot find mark-scheme answer section")


def _ms_text_question_candidates(document: "fitz.Document") -> dict[int, QuestionStart]:
    from statistics import median

    fitz_module = _load_fitz()
    answer_start_page = _ms_find_answer_start_page(document)
    modern_question_x: float | None = None
    rotated_legacy = False
    if document[answer_start_page].rotation:
        part_label_x: list[float] = []
        for page_index in range(answer_start_page, document.page_count):
            page = document[page_index]
            for word in _page_words(page):
                label, match = _ms_label_match(str(word[4]))
                rect = _ms_display_rect(page, fitz_module.Rect(word[:4]))
                if match and "(" in label and 48 <= rect.x0 <= 115:
                    part_label_x.append(rect.x0)
        rotated_legacy = not part_label_x
        if part_label_x:
            modern_question_x = median(part_label_x)
        if modern_question_x is not None:
            for page_index in range(answer_start_page):
                page = document[page_index]
                if _ms_is_pre_answer_notes_page(page):
                    continue
                if any(
                    _ms_label_match(str(word[4]))[0] == "1"
                    and abs(_ms_display_rect(page, fitz_module.Rect(word[:4])).x0 - modern_question_x) <= 20
                    and 55 <= _ms_display_rect(page, fitz_module.Rect(word[:4])).y0 <= page.rect.height - 45
                    for word in _page_words(page)
                ):
                    answer_start_page = page_index
                    break
        while modern_question_x is not None and answer_start_page > 0:
            previous_page = document[answer_start_page - 1]
            if _ms_is_pre_answer_notes_page(previous_page):
                break
            has_question_label = False
            for word in _page_words(previous_page):
                clean_label, match = _ms_label_match(str(word[4]))
                rect = _ms_display_rect(previous_page, fitz_module.Rect(word[:4]))
                if match and 1 <= int(match.group("number")) <= 30 and abs(rect.x0 - modern_question_x) <= 20 and 55 <= rect.y0 <= previous_page.rect.height - 45:
                    has_question_label = True
                    break
            if not has_question_label and not _ms_is_full_page_image(previous_page):
                break
            answer_start_page -= 1
    candidates: dict[int, QuestionStart] = {}
    text_question_column = None if document[answer_start_page].rotation else _ms_find_text_question_column(document, answer_start_page)
    for page_index in range(answer_start_page, document.page_count):
        page = document[page_index]
        if _ms_is_pre_answer_notes_page(page):
            continue
        for word in _page_words(page):
            label, match = _ms_label_match(str(word[4]))
            if not match:
                continue
            rect = _ms_display_rect(page, fitz_module.Rect(word[:4]))
            if page.rotation:
                is_top_level = (rotated_legacy and _is_ascii_integer(label) and 25 <= rect.x0 <= 100 and rect.width <= 18) or (
                    not rotated_legacy and ((_is_ascii_integer(label) and modern_question_x is not None and abs(rect.x0 - modern_question_x) <= 12) or ("(" in label and 48 <= rect.x0 <= 115))
                )
            else:
                is_top_level = (
                    text_question_column is not None
                    and abs(rect.x0 - text_question_column) <= 8
                    and rect.width <= 24
                ) or (text_question_column is None and 70 <= rect.x0 <= 110 and rect.width <= 38)
            if not is_top_level or not (55 <= rect.y0 <= page.rect.height - 45):
                continue
            number = int(match.group("number"))
            if not 1 <= number <= 30:
                continue
            start = QuestionStart(number, page_index, rect.y0)
            previous = candidates.get(number)
            if previous is None or (page_index, rect.y0) < (previous.page_index, previous.display_y):
                candidates[number] = start
    return candidates


def _ms_raster_question_candidates(document: "fitz.Document") -> dict[int, QuestionStart]:
    def answer_start_page() -> int:
        try:
            return _ms_find_answer_start_page(document)
        except ValueError:
            pass
        last_notes_page: int | None = None
        for page_index, page in enumerate(document):
            if _ms_is_pre_answer_notes_page(page):
                last_notes_page = page_index
        return (last_notes_page + 1) if last_notes_page is not None else 0

    def page_rows(page: "fitz.Page", x0_points: float, x1_points: float) -> list[float]:
        scale = RASTER_LAYOUT_SCALE
        image = _raster_page_image(page)
        pixels = image.load()
        x0, x1 = int(x0_points * scale), int(x1_points * scale)
        content_top = 98.0 if page.rotation else 62.0
        content_bottom = page.rect.height - (76.0 if page.rotation else 65.0)
        y0 = int(content_top * scale)
        y1 = min(image.height, int(content_bottom * scale))
        seen: set[tuple[int, int]] = set()
        components: list[tuple[float, float, float, float, int]] = []
        for y in range(y0, y1):
            for x in range(x0, x1):
                if pixels[x, y] >= RASTER_INK_THRESHOLD or (x, y) in seen:
                    continue
                stack = [(x, y)]
                seen.add((x, y))
                xs: list[int] = []
                ys: list[int] = []
                while stack:
                    current_x, current_y = stack.pop()
                    xs.append(current_x)
                    ys.append(current_y)
                    for neighbor in ((current_x - 1, current_y), (current_x + 1, current_y), (current_x, current_y - 1), (current_x, current_y + 1)):
                        if x0 <= neighbor[0] < x1 and y0 <= neighbor[1] < y1 and pixels[neighbor[0], neighbor[1]] < RASTER_INK_THRESHOLD and neighbor not in seen:
                            seen.add(neighbor)
                            stack.append(neighbor)
                width = (max(xs) - min(xs) + 1) / scale
                height = (max(ys) - min(ys) + 1) / scale
                ink = len(xs)
                if 1.0 <= width <= 12.0 and 4.0 <= height <= 16.0 and ink >= 12:
                    components.append((min(xs) / scale, min(ys) / scale, width, height, ink))
        rows: list[float] = []
        for component in sorted(components, key=lambda item: item[1]):
            if not rows or component[1] - rows[-1] > 8:
                rows.append(component[1])
        return rows

    starts: list[QuestionStart] = []
    start_page = answer_start_page()
    for page_index in range(start_page, document.page_count):
        page = document[page_index]
        if _ms_is_pre_answer_notes_page(page):
            continue
        rows = []
        for x0_points, x1_points in ((55, 85), (85, 115), (65, 105)):
            rows = page_rows(page, x0_points, x1_points)
            if rows:
                break
        if page_index == 0 and len(rows) <= 1 and document.page_count > 1:
            continue
        for row_y in rows:
            starts.append(QuestionStart(len(starts) + 1, page_index, row_y, inferred=True))
    if not starts:
        raise ValueError("no question labels detected in mark scheme")
    filtered: list[QuestionStart] = []
    for start in starts:
        if len(filtered) >= 14:
            break
        if filtered and start.page_index == filtered[-1].page_index and start.display_y - filtered[-1].display_y < 45:
            continue
        filtered.append(QuestionStart(len(filtered) + 1, start.page_index, start.display_y, inferred=True))
    return {start.number: start for start in filtered}


def _ms_question_candidates(document: "fitz.Document") -> dict[int, QuestionStart]:
    try:
        candidates = _ms_text_question_candidates(document)
    except ValueError as exc:
        if "cannot find mark-scheme answer" not in str(exc) and "no question labels" not in str(exc):
            raise
        return _ms_raster_question_candidates(document)
    candidates = _ms_prune_question_candidates(candidates)
    if not candidates:
        return _ms_raster_question_candidates(document)
    if min(candidates) != 1:
        first = candidates[min(candidates)]
        has_leading_answer_image = any(_ms_is_full_page_image(document[page_index]) for page_index in range(first.page_index))
        if min(candidates) != 2 or not has_leading_answer_image:
            return _ms_raster_question_candidates(document)
    return candidates


def _ms_split_starts(document: "fitz.Document") -> list[QuestionStart]:
    top_level_starts = _ms_infer_missing_starts(document, _ms_question_candidates(document))
    explicit_subparts = _ms_explicit_subquestion_candidates(document)
    subparts_by_number: dict[int, list[QuestionStart]] = {}
    for start in explicit_subparts:
        subparts_by_number.setdefault(start.number, []).append(start)

    output: list[QuestionStart] = []
    seen_numbers = {start.number for start in top_level_starts}
    for top_level_start in top_level_starts:
        subparts = subparts_by_number.get(top_level_start.number)
        if subparts:
            output.extend(subparts)
        else:
            output.append(
                QuestionStart(
                    top_level_start.number,
                    top_level_start.page_index,
                    top_level_start.display_y,
                    top_level_start.inferred,
                    str(top_level_start.number),
                )
            )
    for number in sorted(set(subparts_by_number) - seen_numbers):
        output.extend(subparts_by_number[number])
    return _ms_prune_split_starts(sorted(output, key=lambda item: (item.page_index, item.display_y, item.question_number)))


def _ms_explicit_subquestion_candidates(document: "fitz.Document") -> list[QuestionStart]:
    fitz_module = _load_fitz()
    try:
        answer_start_page = _ms_find_answer_start_page(document)
    except ValueError:
        return []
    candidates: dict[str, QuestionStart] = {}
    for page_index in range(answer_start_page, document.page_count):
        page = document[page_index]
        if _ms_is_pre_answer_notes_page(page):
            continue
        if not _ms_has_answer_section_evidence(page):
            continue
        for word in _page_words(page):
            clean_label, match = _ms_label_match(str(word[4]))
            if not match or "(" not in clean_label:
                continue
            rect = _ms_display_rect(page, fitz_module.Rect(word[:4]))
            if not _ms_is_subquestion_label_rect(page, rect):
                continue
            number = int(match.group("number"))
            if not 1 <= number <= 30:
                continue
            label = clean_label.lower()
            candidate = QuestionStart(number, page_index, rect.y0, False, label)
            previous = candidates.get(label)
            if previous is None or (page_index, rect.y0) < (previous.page_index, previous.display_y):
                candidates[label] = candidate
    for candidate in _ms_raster_subquestion_candidates(document, candidates, answer_start_page):
        previous = candidates.get(candidate.question_number)
        if previous is None or (candidate.page_index, candidate.display_y) < (previous.page_index, previous.display_y):
            candidates[candidate.question_number] = candidate
    return sorted(candidates.values(), key=lambda item: (item.page_index, item.display_y, item.question_number))


def _ms_raster_subquestion_candidates(
    document: "fitz.Document",
    text_candidates: dict[str, QuestionStart],
    answer_start_page: int,
) -> list[QuestionStart]:
    ordered_text = sorted(text_candidates.values(), key=lambda item: (item.page_index, item.display_y, item.question_number))
    if not ordered_text:
        return []
    output: list[QuestionStart] = []
    previous_text: QuestionStart | None = None
    for next_text in ordered_text:
        rows = _ms_raster_rows_between(document, previous_text, next_text, answer_start_page)
        if rows:
            labels = _ms_infer_labels_between(previous_text.question_number if previous_text else None, next_text.question_number, len(rows))
            if len(labels) == len(rows):
                output.extend(
                    QuestionStart(number, page_index, row_y, True, label)
                    for (page_index, row_y), (number, label) in zip(rows, labels)
                )
        previous_text = next_text
    if previous_text is not None:
        rows = _ms_raster_rows_after(document, previous_text)
        if rows:
            previous_number, previous_path = _ms_parse_label_path(previous_text.question_number)
            labels = _ms_labels_after_path(previous_number, previous_path, len(rows)) if previous_number is not None else []
            if len(labels) == len(rows):
                output.extend(
                    QuestionStart(number, page_index, row_y, True, label)
                    for (page_index, row_y), (number, label) in zip(rows, labels)
                )
    return output


def _ms_raster_rows_between(
    document: "fitz.Document",
    previous: QuestionStart | None,
    following: QuestionStart,
    answer_start_page: int,
) -> list[tuple[int, float]]:
    start_page = previous.page_index if previous is not None else answer_start_page
    rows: list[tuple[int, float]] = []
    for page_index in range(start_page, min(following.page_index + 1, document.page_count)):
        page = document[page_index]
        if not _ms_is_full_page_image(page):
            continue
        page_rows = _ms_raster_label_rows(page)
        if previous is not None and page_index == previous.page_index:
            page_rows = [row for row in page_rows if row > previous.display_y + 8.0]
        if page_index == following.page_index:
            page_rows = [row for row in page_rows if row < following.display_y - 8.0]
        rows.extend((page_index, row) for row in page_rows)
    return rows


def _ms_raster_rows_after(document: "fitz.Document", previous: QuestionStart) -> list[tuple[int, float]]:
    rows: list[tuple[int, float]] = []
    for page_index in range(previous.page_index, document.page_count):
        page = document[page_index]
        if not _ms_is_full_page_image(page):
            continue
        page_rows = _ms_raster_label_rows(page)
        if page_index == previous.page_index:
            page_rows = [row for row in page_rows if row > previous.display_y + 8.0]
        rows.extend((page_index, row) for row in page_rows)
    return rows


def _ms_raster_label_rows(page: "fitz.Page") -> list[float]:
    scale = RASTER_LAYOUT_SCALE
    image = _raster_page_image(page)
    pixels = image.load()
    x0, x1 = int(55.0 * scale), int(90.0 * scale)
    content_top = 98.0 if page.rotation else 62.0
    content_bottom = page.rect.height - (76.0 if page.rotation else 65.0)
    y0 = int(content_top * scale)
    y1 = min(image.height, int(content_bottom * scale))
    seen: set[tuple[int, int]] = set()
    components: list[tuple[float, float, float, float, int]] = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if pixels[x, y] >= RASTER_INK_THRESHOLD or (x, y) in seen:
                continue
            stack = [(x, y)]
            seen.add((x, y))
            xs: list[int] = []
            ys: list[int] = []
            while stack:
                current_x, current_y = stack.pop()
                xs.append(current_x)
                ys.append(current_y)
                for neighbor in ((current_x - 1, current_y), (current_x + 1, current_y), (current_x, current_y - 1), (current_x, current_y + 1)):
                    if x0 <= neighbor[0] < x1 and y0 <= neighbor[1] < y1 and pixels[neighbor[0], neighbor[1]] < RASTER_INK_THRESHOLD and neighbor not in seen:
                        seen.add(neighbor)
                        stack.append(neighbor)
            width = (max(xs) - min(xs) + 1) / scale
            height = (max(ys) - min(ys) + 1) / scale
            ink = len(xs)
            if 1.0 <= width <= 30.0 and 4.0 <= height <= 18.0 and ink >= 10:
                components.append((min(xs) / scale, min(ys) / scale, width, height, ink))

    rows: list[float] = []
    for component in sorted(components, key=lambda item: item[1]):
        if not rows or component[1] - rows[-1] > 36.0:
            rows.append(component[1])
    return rows


def _ms_parse_label_path(label: str) -> tuple[int | None, tuple[str, ...]]:
    normalized = _normalize_ms_question_label(label)
    match = re.fullmatch(r"(?P<number>[0-9]{1,2})(?P<parts>(?:\([a-zivxlcdm]+\))*)", normalized)
    if not match:
        return None, ()
    return int(match.group("number")), tuple(part.strip("()") for part in re.findall(r"\([a-zivxlcdm]+\)", match.group("parts")))


def _ms_infer_labels_between(previous_label: str | None, next_label: str, count: int) -> list[tuple[int, str]]:
    next_number, next_path = _ms_parse_label_path(next_label)
    if next_number is None or not next_path:
        return []
    if previous_label is None:
        return _ms_infer_labels_before(next_number, next_path, count)
    previous_number, previous_path = _ms_parse_label_path(previous_label)
    if previous_number is None:
        return []
    if previous_number == next_number:
        labels = _ms_labels_after_path(previous_number, previous_path, count)
        labels = [item for item in labels if item[1] not in {next_label}]
        return labels[:count]
    if next_number == previous_number + 1 and next_path == ("a",):
        return _ms_labels_after_path(previous_number, previous_path, count)[:count]
    if next_number == previous_number + 2 and next_path == ("a",):
        return _ms_labels_from_first_alpha(previous_number + 1, count)
    return []


def _ms_infer_labels_before(next_number: int, next_path: tuple[str, ...], count: int) -> list[tuple[int, str]]:
    if count <= 0:
        return []
    labels: list[tuple[int, str]] = []
    same_question = _ms_labels_before_path(next_number, next_path)
    take_same = min(len(same_question), count)
    if take_same:
        labels.extend((next_number, label) for label in same_question[-take_same:])
    remaining = count - take_same
    if remaining:
        previous_number = next_number - 1
        if previous_number < 1:
            return []
        previous_labels = [f"{previous_number}({chr(ord('a') + index)})" for index in range(remaining)]
        labels = [(previous_number, label) for label in previous_labels] + labels
    return labels


def _ms_labels_before_path(number: int, path: tuple[str, ...]) -> list[str]:
    if not path:
        return []
    first = path[0]
    if len(path) == 1 and len(first) == 1 and "a" <= first <= "z":
        return [f"{number}({chr(code)})" for code in range(ord("a"), ord(first))]
    if len(path) == 2:
        roman_order = ("i", "ii", "iii", "iv", "v", "vi")
        if path[1] in roman_order:
            return [f"{number}({first})({roman})" for roman in roman_order[: roman_order.index(path[1])]]
    return []


def _ms_labels_after_path(number: int, path: tuple[str, ...], count: int) -> list[tuple[int, str]]:
    if count <= 0 or not path:
        return []
    first = path[0]
    if len(path) == 1 and len(first) == 1 and "a" <= first <= "z":
        start = ord(first) + 1
        return [(number, f"{number}({chr(code)})") for code in range(start, min(ord("z") + 1, start + count))]
    if len(path) == 2:
        roman_order = ("i", "ii", "iii", "iv", "v", "vi")
        if path[1] in roman_order:
            start = roman_order.index(path[1]) + 1
            return [(number, f"{number}({first})({roman})") for roman in roman_order[start : start + count]]
    return []


def _ms_labels_from_first_alpha(number: int, count: int) -> list[tuple[int, str]]:
    if count <= 0:
        return []
    return [(number, f"{number}({chr(code)})") for code in range(ord("a"), min(ord("z") + 1, ord("a") + count))]


def _ms_is_subquestion_label_rect(page: "fitz.Page", rect: "fitz.Rect") -> bool:
    if page.rotation:
        return 48.0 <= rect.x0 <= 115.0 and 55.0 <= rect.y0 <= page.rect.height - 45.0 and rect.width <= 36.0
    return 50.0 <= rect.x0 <= 120.0 and 55.0 <= rect.y0 <= page.rect.height - 45.0 and rect.width <= 42.0


def _ms_prune_split_starts(starts: list[QuestionStart]) -> list[QuestionStart]:
    output: list[QuestionStart] = []
    for start in starts:
        if output and (start.page_index, start.display_y) <= (output[-1].page_index, output[-1].display_y):
            continue
        if output and start.question_number == output[-1].question_number:
            continue
        if output and start.page_index == output[-1].page_index and start.display_y - output[-1].display_y < 18:
            continue
        output.append(start)
    if not output:
        raise ValueError("no question labels detected in mark scheme")
    return output


def _ms_prune_question_candidates(candidates: dict[int, QuestionStart]) -> dict[int, QuestionStart]:
    output: dict[int, QuestionStart] = {}
    previous: QuestionStart | None = None
    for number in sorted(candidates):
        current = candidates[number]
        if previous is not None:
            if (current.page_index, current.display_y) <= (previous.page_index, previous.display_y):
                continue
            if current.page_index == previous.page_index and current.display_y - previous.display_y < 45:
                continue
        output[number] = current
        previous = current
    return output


def _ms_infer_missing_starts(document: "fitz.Document", candidates: dict[int, QuestionStart]) -> list[QuestionStart]:
    if not candidates:
        raise ValueError("no question labels detected in mark scheme")
    maximum = max(candidates)
    starts = dict(candidates)
    for number in range(1, maximum + 1):
        if number in starts:
            continue
        previous = starts.get(number - 1)
        following = next((starts[value] for value in range(number + 1, maximum + 1) if value in starts), None)
        lower_page = previous.page_index if previous else 0
        upper_page = following.page_index if following else document.page_count
        image_pages = [page_index for page_index in range(lower_page, upper_page) if _ms_is_full_page_image(document[page_index]) and (previous is None or page_index > previous.page_index)]
        if image_pages:
            starts[number] = QuestionStart(number, image_pages[-1] if previous is None else image_pages[0], 88.0, inferred=True)
        elif previous is None and following is not None:
            starts[number] = QuestionStart(number, following.page_index, 98.0, inferred=True)
        elif previous is not None and following is not None and following.page_index > previous.page_index:
            starts[number] = QuestionStart(number, min(previous.page_index + 1, following.page_index), 98.0, inferred=True)
        elif previous is not None and following is not None and following.page_index == previous.page_index and following.display_y - previous.display_y > 36:
            starts[number] = QuestionStart(number, previous.page_index, (previous.display_y + following.display_y) / 2, inferred=True)
        else:
            raise ValueError(f"cannot infer start of question {number}")
    ordered = [starts[number] for number in range(1, maximum + 1)]
    if any((current.page_index, current.display_y) >= (following.page_index, following.display_y) for current, following in zip(ordered, ordered[1:])):
        raise ValueError("question starts are not in increasing page order")
    return ordered


def _ms_render_page_segment(page: "fitz.Page", y0: float, y1: float, dpi: int, *, bottom_padding: float = MS_BOTTOM_PADDING_POINTS) -> tuple[Image.Image, "fitz.Rect", dict[str, object]] | None:
    fitz_module = _load_fitz()
    content_top = 98.0 if page.rotation else 62.0
    safe_y0 = max(content_top, y0 - MS_TOP_PADDING_POINTS)
    content_bottom = page.rect.height - (76.0 if page.rotation else 65.0)
    safe_y1 = min(content_bottom, y1 + bottom_padding)
    if safe_y1 <= safe_y0:
        return None
    display_clip = fitz_module.Rect(42.0, safe_y0, page.rect.width - 42.0, safe_y1)
    pixmap = page.get_pixmap(dpi=dpi, colorspace=fitz_module.csGRAY, alpha=False, clip=display_clip)
    image = Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples)
    mask = image.point(lambda value: 255 if value < MS_INK_THRESHOLD else 0, mode="1")
    bbox = mask.getbbox()
    if bbox is None:
        return None
    padding = max(8, round(dpi / 12))
    crop_box = (
        max(0, bbox[0] - padding),
        max(0, bbox[1] - padding),
        min(image.width, bbox[2] + padding),
        min(image.height, bbox[3] + padding),
    )
    post_render_crop_px = {
        "coordinate_space": "rendered_clip_pixels",
        "unit": "px",
        "left": crop_box[0],
        "top": crop_box[1],
        "right": crop_box[2],
        "bottom": crop_box[3],
    }
    return image.crop(crop_box), display_clip, post_render_crop_px


def _ms_mark_scheme_points(document: "fitz.Document", start: QuestionStart, following: QuestionStart | None) -> list[MarkSchemePoint]:
    rows: list[dict[str, str]] = []
    end_page = following.page_index if following and following.page_index == start.page_index else (following.page_index - 1 if following else document.page_count - 1)
    for page_index in range(start.page_index, end_page + 1):
        page = document[page_index]
        page_y0 = start.display_y if page_index == start.page_index else 0.0
        same_page_next = following is not None and page_index == following.page_index
        same_page_gap = MS_NEXT_QUESTION_GAP_POINTS if _ms_is_answer_table_page(page) else MS_LEGACY_NEXT_QUESTION_GAP_POINTS
        page_y1 = following.display_y - same_page_gap if same_page_next else page.rect.height
        rows.extend(_ms_extract_marking_rows(page, page_y0, page_y1))
    return _parse_ms_marking_points_from_rows(rows)


def _ms_extract_marking_rows(page: "fitz.Page", y0: float, y1: float) -> list[dict[str, str]]:
    fitz_module = _load_fitz()
    answer_left, marks_left, guidance_left, right = _ms_table_column_edges(page)
    content_top = 98.0 if page.rotation else 62.0
    content_bottom = page.rect.height - (76.0 if page.rotation else 65.0)
    safe_y0 = max(content_top, y0 - MS_TOP_PADDING_POINTS)
    safe_y1 = min(content_bottom, y1 + MS_BOTTOM_PADDING_POINTS)
    word_rows: list[list[tuple[float, float, str]]] = []
    for word in _page_words(page):
        text = str(word[4]).strip()
        if not text:
            continue
        rect = _ms_display_rect(page, fitz_module.Rect(word[:4]))
        if rect.y1 < safe_y0 or rect.y0 > safe_y1 or rect.x1 < answer_left or rect.x0 > right:
            continue
        row_y = (rect.y0 + rect.y1) / 2
        for row in word_rows:
            if abs(row[0][0] - row_y) <= 3.5:
                row.append((row_y, rect.x0, text))
                break
        else:
            word_rows.append([(row_y, rect.x0, text)])

    output: list[dict[str, str]] = []
    for row in sorted(word_rows, key=lambda item: item[0][0]):
        answer_words: list[tuple[float, str]] = []
        mark_words: list[tuple[float, str]] = []
        guidance_words: list[tuple[float, str]] = []
        for _, x, text in row:
            if marks_left <= x < guidance_left:
                mark_words.append((x, text))
            elif x >= guidance_left:
                guidance_words.append((x, text))
            elif x >= answer_left:
                answer_words.append((x, text))
        answer = _ms_join_words(answer_words)
        marks = _ms_join_words(mark_words)
        guidance = _ms_join_words(guidance_words)
        if not answer and not marks and not guidance:
            continue
        if {answer.lower(), marks.lower(), guidance.lower()} & {"answer", "marks", "guidance"}:
            continue
        output.append({"answer": answer, "marks": marks, "guidance": guidance})
    return output


def _ms_table_column_edges(page: "fitz.Page") -> tuple[float, float, float, float]:
    fitz_module = _load_fitz()
    headers: dict[str, float] = {}
    for word in _page_words(page):
        label = str(word[4]).strip().lower()
        if label not in {"answer", "marks", "guidance"}:
            continue
        rect = _ms_display_rect(page, fitz_module.Rect(word[:4]))
        headers[label] = rect.x0
    if {"answer", "marks", "guidance"}.issubset(headers):
        return (
            max(42.0, headers["answer"] - 12.0),
            max(headers["answer"] + 35.0, headers["marks"] - 14.0),
            max(headers["marks"] + 20.0, headers["guidance"] - 14.0),
            page.rect.width - 42.0,
        )
    return (page.rect.width * 0.16, page.rect.width * 0.59, page.rect.width * 0.67, page.rect.width - 42.0)


def _ms_join_words(words: list[tuple[float, str]]) -> str:
    text = " ".join(word for _, word in sorted(words, key=lambda item: item[0]))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:)])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    text = re.sub(r"\s*([+=])\s*", r"\1", text)
    return text


def _parse_ms_marking_points_from_rows(rows: list[dict[str, str]]) -> list[MarkSchemePoint]:
    parsed: list[dict[str, object]] = []
    marker_pattern = re.compile(r"(?<![A-Za-z])([BMA])\s*(\d+)(?!\d)")
    for row in rows:
        marks = row.get("marks", "")
        matches = list(marker_pattern.finditer(marks))
        if not matches:
            if parsed and not _ms_is_total_mark_row(row):
                if row.get("answer"):
                    parsed[-1]["marking_point"] = _combine_ms_text(str(parsed[-1]["marking_point"]), row["answer"])
                if row.get("guidance"):
                    parsed[-1]["supplement"] = _combine_ms_text(str(parsed[-1]["supplement"]), row["guidance"])
            continue
        for match in matches:
            parsed.append(
                {
                    "score": int(match.group(2)),
                    "type": match.group(1),
                    "marking_point": row.get("answer", ""),
                    "supplement": row.get("guidance", ""),
                }
            )
    return [
        MarkSchemePoint(
            score=int(point["score"]),
            type=str(point["type"]),
            marking_point=str(point["marking_point"]).strip(),
            supplement=str(point["supplement"]).strip(),
        )
        for point in parsed
    ]


def _ms_is_total_mark_row(row: dict[str, str]) -> bool:
    return bool(re.fullmatch(r"\d+", row.get("marks", "").strip())) and not row.get("answer", "").strip() and not row.get("guidance", "").strip()


def _combine_ms_text(first: str, second: str) -> str:
    if not first:
        return second
    if not second:
        return first
    return f"{first} {second}"


def _ms_question_segments(document: "fitz.Document", start: QuestionStart, following: QuestionStart | None, dpi: int) -> list[RenderedSegment]:
    end_page = following.page_index if following and following.page_index == start.page_index else (following.page_index - 1 if following else document.page_count - 1)
    segments: list[RenderedSegment] = []
    for page_index in range(start.page_index, end_page + 1):
        page = document[page_index]
        page_y0 = start.display_y if page_index == start.page_index else 0.0
        same_page_next = following is not None and page_index == following.page_index
        same_page_gap = MS_NEXT_QUESTION_GAP_POINTS if _ms_is_answer_table_page(page) else MS_LEGACY_NEXT_QUESTION_GAP_POINTS
        page_y1 = following.display_y - same_page_gap if same_page_next else page.rect.height
        rendered = _ms_render_page_segment(page, page_y0, page_y1, dpi, bottom_padding=0.0 if same_page_next else MS_BOTTOM_PADDING_POINTS)
        if rendered is not None:
            image, clip, post_render_crop_px = rendered
            segments.append(RenderedSegment(page_index=page_index, image=image, clip=clip, post_render_crop_px=post_render_crop_px))
    return segments


def _ms_question_images(document: "fitz.Document", start: QuestionStart, following: QuestionStart | None, dpi: int) -> list[Image.Image]:
    return [segment.image for segment in _ms_question_segments(document, start, following, dpi)]


def _join_images(images: list[Image.Image]) -> Image.Image:
    width = max(image.width for image in images)
    height = sum(image.height for image in images) + JOIN_GAP_PIXELS * (len(images) - 1)
    output = Image.new("L", (width, height), 255)
    y = 0
    for image in images:
        output.paste(image, (0, y))
        y += image.height + JOIN_GAP_PIXELS
    return output

