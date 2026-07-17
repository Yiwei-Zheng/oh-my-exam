from __future__ import annotations

import queue
import threading
from pathlib import Path

from exam_packer.models import MetadataCourse, PackOptions
from exam_packer.packer import discover_metadata_courses, pack_subject_database


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "requirements.md").exists() and (parent / "tools").exists():
            return parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root()
DEFAULT_METADATA_ROOT = Path("data/processed_questions")
DEFAULT_OUTPUT_BASE = Path("data/databases")
FONT_FAMILY = "Segoe UI"
TEXT_SIZE = 13
TITLE_SIZE = 18
PANEL_RADIUS = 6
RIGHT_PANEL_MIN_WIDTH = 760
QUALIFICATION_LABELS = {
    "a_level": "A-level",
    "igcse": "IGCSE",
    "admissions": "Admissions Tests",
}

TRANSLATIONS = {
    "zh": {
        "window_title": "Oh-My-Exam Metadata Packer",
        "heading": "Metadata 打包为单科 SQLite",
        "language": "语言",
        "metadata_root": "Metadata 根目录",
        "output_dir": "输出目录",
        "qualification": "Qualification",
        "exam_board": "考试局",
        "course_code": "科目代码",
        "overwrite": "覆盖已有数据库",
        "dry_run": "Dry run",
        "scan": "扫描",
        "start": "开始打包",
        "ready": "就绪",
        "scanning": "正在扫描...",
        "scan_done": "已发现 {courses} 个可打包科目，共 {metadata} 份 metadata",
        "no_courses": "未发现 JSON metadata",
        "no_exam_boards": "当前 Qualification 下未找到本地考试局",
        "select_exam_board": "请选择考试局",
        "select_course_code": "请选择科目代码",
        "no_course_codes": "当前 Qualification + 考试局下未找到本地科目代码，请检查 Metadata 根目录或点击扫描",
        "done": "完成",
        "warning": "警告：{message}",
        "error": "错误：{message}",
    },
    "en": {
        "window_title": "Oh-My-Exam Metadata Packer",
        "heading": "Package Metadata into Subject SQLite",
        "language": "Language",
        "metadata_root": "Metadata root",
        "output_dir": "Output directory",
        "qualification": "Qualification",
        "exam_board": "Exam board",
        "course_code": "Course code",
        "overwrite": "Overwrite existing database",
        "dry_run": "Dry run",
        "scan": "Scan",
        "start": "Start packing",
        "ready": "Ready",
        "scanning": "Scanning...",
        "scan_done": "Found {courses} packable courses with {metadata} metadata files",
        "no_courses": "No JSON metadata found",
        "no_exam_boards": "No local exam boards found for the selected qualification",
        "select_exam_board": "Select an exam board",
        "select_course_code": "Select a course code",
        "no_course_codes": "No local course codes found for this qualification + exam board. Check the metadata root or scan again.",
        "done": "Done",
        "warning": "Warning: {message}",
        "error": "Error: {message}",
    },
}


def _qualification_label(qualification: str) -> str:
    return QUALIFICATION_LABELS.get(qualification, qualification.replace("_", " ").title())


def _bind_dropdown_handler(dropdown: object, handler: object) -> None:
    """Bind both current and legacy Flet dropdown selection events."""
    if hasattr(dropdown, "on_select"):
        setattr(dropdown, "on_select", handler)
    else:
        setattr(dropdown, "on_change", handler)


def main() -> None:
    try:
        import flet as ft
    except ImportError as exc:
        raise SystemExit("Flet is required for the GUI. Install it with: python -m pip install flet") from exc

    def app(page: ft.Page) -> None:
        locale = {"value": "zh"}
        events: queue.Queue[dict[str, object]] = queue.Queue()
        worker: threading.Thread | None = None

        def t(key: str, **kwargs: object) -> str:
            template = TRANSLATIONS[locale["value"]][key]
            return template.format(**kwargs) if kwargs else template

        def resolved_path(value: str | None) -> Path:
            path = Path((value or "").strip())
            return path if path.is_absolute() else PROJECT_ROOT / path

        courses: list[MetadataCourse] = []

        page.title = t("window_title")
        page.window_min_width = 980
        page.window_min_height = 680
        page.padding = 16
        page.spacing = 0
        page.bgcolor = ft.Colors.SURFACE_CONTAINER_LOW

        def panel(
            controls: list,
            *,
            expand: bool | int = False,
            width: int | None = None,
            height: int | None = None,
        ) -> object:
            return ft.Container(
                ft.Column(controls, spacing=10, expand=True),
                expand=expand,
                width=width,
                height=height,
                padding=14,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=PANEL_RADIUS,
            )

        def scrollable_panel(
            controls: list,
            *,
            expand: bool | int = False,
            width: int | None = None,
            height: int | None = None,
            min_content_width: int = RIGHT_PANEL_MIN_WIDTH,
        ) -> object:
            content = ft.Container(ft.Column(controls, spacing=10), width=min_content_width)
            return ft.Container(
                ft.Column(
                    [ft.Row([content], scroll=ft.ScrollMode.AUTO, expand=True)],
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
                expand=expand,
                width=width,
                height=height,
                padding=14,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=PANEL_RADIUS,
            )

        title = ft.Text(t("heading"), size=TITLE_SIZE, weight=ft.FontWeight.W_500, font_family=FONT_FAMILY)
        language = ft.Dropdown(
            label=t("language"),
            value="zh",
            width=150,
            text_size=TEXT_SIZE,
            options=[ft.DropdownOption(key="zh", text="中文"), ft.DropdownOption(key="en", text="English")],
        )
        metadata_root = ft.TextField(label=t("metadata_root"), value=str(DEFAULT_METADATA_ROOT), expand=True, text_size=TEXT_SIZE)
        qualification = ft.Dropdown(label=t("qualification"), width=180, text_size=TEXT_SIZE)
        exam_board = ft.Dropdown(label=t("exam_board"), width=160, text_size=TEXT_SIZE)
        course_dropdown = ft.Dropdown(label=t("course_code"), width=180, text_size=TEXT_SIZE)
        output_dir = ft.TextField(
            label=t("output_dir"),
            value=str(DEFAULT_OUTPUT_BASE / "a_level" / "cie"),
            expand=True,
            text_size=TEXT_SIZE,
            read_only=True,
        )
        overwrite = ft.Checkbox(label=t("overwrite"), value=False)
        dry_run = ft.Checkbox(label=t("dry_run"), value=False)
        scan_button = ft.TextButton(t("scan"))
        start_button = ft.ElevatedButton(t("start"))
        status = ft.Text(t("ready"), selectable=True, size=TEXT_SIZE, font_family=FONT_FAMILY)
        log_view = ft.ListView(expand=True, spacing=4, auto_scroll=True)

        def append_log(text: str) -> None:
            log_view.controls.append(ft.Text(text, size=TEXT_SIZE, selectable=True, no_wrap=True))
            if len(log_view.controls) > 500:
                del log_view.controls[:100]

        def update_output_dir() -> None:
            if qualification.value and exam_board.value:
                output_dir.value = str(DEFAULT_OUTPUT_BASE / qualification.value / exam_board.value)
            else:
                output_dir.value = ""

        def available_qualifications() -> list[str]:
            found = {course.qualification for course in courses}
            preferred = [key for key in QUALIFICATION_LABELS if key in found]
            return [*preferred, *sorted(found.difference(preferred))]

        def courses_for_selection() -> list[MetadataCourse]:
            return [
                course
                for course in courses
                if course.qualification == qualification.value and course.exam_board == exam_board.value
            ]

        def update_start_button() -> None:
            start_button.disabled = worker is not None or not (
                qualification.value and exam_board.value and course_dropdown.value
            )

        def refresh_qualification_options() -> None:
            options = available_qualifications()
            qualification.options = [
                ft.DropdownOption(key=value, text=_qualification_label(value)) for value in options
            ]
            if qualification.value not in options:
                qualification.value = "a_level" if "a_level" in options else (options[0] if options else None)
            qualification.disabled = not bool(options)

        def refresh_exam_board_options(*, reset: bool) -> None:
            boards = sorted({course.exam_board for course in courses if course.qualification == qualification.value})
            exam_board.options = [ft.DropdownOption(key=board, text=board.upper()) for board in boards]
            if reset or exam_board.value not in boards:
                exam_board.value = None
            exam_board.disabled = not bool(boards)

        def refresh_course_options(*, reset: bool) -> None:
            selected_courses = courses_for_selection() if exam_board.value else []
            course_dropdown.options = [
                ft.DropdownOption(
                    key=course.course_code,
                    text=(
                        f"{course.course_code.upper()} ({course.metadata_count})"
                        if course.metadata_count
                        else course.course_code.upper()
                    ),
                )
                for course in selected_courses
            ]
            course_codes = {course.course_code for course in selected_courses}
            if reset or course_dropdown.value not in course_codes:
                course_dropdown.value = None
            course_dropdown.disabled = not (qualification.value and exam_board.value and selected_courses)

        def update_selection_status() -> None:
            if not courses:
                status.value = t("no_courses")
            elif not exam_board.options:
                status.value = t("no_exam_boards")
            elif not exam_board.value:
                status.value = t("select_exam_board")
            elif not course_dropdown.options:
                status.value = t("no_course_codes")
            elif not course_dropdown.value:
                status.value = t("select_course_code")
            else:
                status.value = t("ready")

        def refresh_selection(*, reset_exam_board: bool = False, reset_course: bool = False) -> None:
            refresh_qualification_options()
            refresh_exam_board_options(reset=reset_exam_board)
            refresh_course_options(reset=reset_course or reset_exam_board)
            update_output_dir()
            update_selection_status()
            update_start_button()

        def run_scan() -> None:
            try:
                found = discover_metadata_courses(resolved_path(metadata_root.value))
                events.put({"kind": "scan_done", "courses": found})
            except Exception as exc:
                events.put({"kind": "error", "message": str(exc)})

        def scan_courses(_: object | None = None) -> None:
            nonlocal worker
            if worker is not None:
                return
            log_view.controls.clear()
            scan_button.disabled = True
            start_button.disabled = True
            status.value = t("scanning")
            page.update()
            worker = threading.Thread(target=run_scan, daemon=True)
            worker.start()
            poll_events()

        def finish_operation() -> None:
            nonlocal worker
            worker = None
            scan_button.disabled = False
            update_start_button()

        def set_courses(found: object) -> None:
            nonlocal courses
            courses = list(found) if isinstance(found, list) else []
            refresh_selection()
            status.value = (
                t(
                    "scan_done",
                    courses=len(courses),
                    metadata=sum(course.metadata_count for course in courses),
                )
                if courses
                else t("no_courses")
            )

        def select_qualification(_: object) -> None:
            refresh_selection(reset_exam_board=True, reset_course=True)
            page.update()

        def select_exam_board(_: object) -> None:
            refresh_selection(reset_course=True)
            page.update()

        def select_course(_: object) -> None:
            update_selection_status()
            update_start_button()
            page.update()

        def run_pack() -> None:
            try:
                summary = pack_subject_database(
                    PackOptions(
                        metadata_root=resolved_path(metadata_root.value),
                        output_dir=resolved_path(output_dir.value),
                        qualification=qualification.value or "",
                        exam_board=exam_board.value or "",
                        course_code=course_dropdown.value or "",
                        overwrite=bool(overwrite.value),
                        dry_run=bool(dry_run.value),
                    )
                )
                events.put({"kind": "done", "summary": summary})
            except Exception as exc:
                events.put({"kind": "error", "message": str(exc)})

        def poll_events() -> None:
            changed = False
            while True:
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    break
                changed = True
                if event.get("kind") == "scan_done":
                    set_courses(event.get("courses"))
                    finish_operation()
                elif event.get("kind") == "done":
                    summary = event["summary"]
                    status.value = t("done")
                    for warning in summary.warnings:
                        append_log(t("warning", message=warning))
                    for line in summary.as_lines():
                        append_log(line)
                    finish_operation()
                elif event.get("kind") == "error":
                    status.value = t("error", message=event.get("message"))
                    append_log(status.value)
                    finish_operation()
            if changed:
                page.update()
            if worker is not None:
                page.run_task(_sleep_and_poll)

        async def _sleep_and_poll() -> None:
            import asyncio

            await asyncio.sleep(0.3)
            poll_events()

        def start_pack(_: object) -> None:
            nonlocal worker
            if worker is not None:
                return
            log_view.controls.clear()
            scan_button.disabled = True
            start_button.disabled = True
            status.value = t("ready")
            worker = threading.Thread(target=run_pack, daemon=True)
            worker.start()
            page.update()
            poll_events()

        def apply_language(_: object | None = None) -> None:
            locale["value"] = language.value or "zh"
            page.title = t("window_title")
            title.value = t("heading")
            language.label = t("language")
            metadata_root.label = t("metadata_root")
            output_dir.label = t("output_dir")
            qualification.label = t("qualification")
            exam_board.label = t("exam_board")
            course_dropdown.label = t("course_code")
            overwrite.label = t("overwrite")
            dry_run.label = t("dry_run")
            scan_button.text = t("scan")
            start_button.text = t("start")
            update_selection_status()
            page.update()

        scan_button.on_click = scan_courses
        start_button.on_click = start_pack
        _bind_dropdown_handler(language, apply_language)
        _bind_dropdown_handler(qualification, select_qualification)
        _bind_dropdown_handler(exam_board, select_exam_board)
        _bind_dropdown_handler(course_dropdown, select_course)
        refresh_selection(reset_exam_board=True, reset_course=True)

        page.add(
            ft.Column(
                [
                    ft.Row(
                        [title, language],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                    ),
                    scrollable_panel(
                        [
                            ft.Row([metadata_root, scan_button], spacing=12),
                            ft.Row([qualification, exam_board, course_dropdown], spacing=12, wrap=True),
                            ft.Row([output_dir], spacing=12),
                            ft.Row(
                                [overwrite, dry_run, start_button, status],
                                spacing=12,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                wrap=True,
                            ),
                        ],
                        height=250,
                    ),
                    panel(
                        [
                            ft.Container(
                                log_view,
                                expand=True,
                                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                                border_radius=PANEL_RADIUS,
                                padding=8,
                            ),
                        ],
                        expand=True,
                    ),
                ],
                expand=True,
                spacing=12,
            )
        )
        scan_courses()

    ft.app(target=app)


if __name__ == "__main__":
    main()
