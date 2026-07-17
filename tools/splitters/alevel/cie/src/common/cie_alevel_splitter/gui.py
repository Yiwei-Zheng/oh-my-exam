from __future__ import annotations

import queue
import threading
import os
from pathlib import Path

from cie_alevel_splitter.layout_splitter import SplitOptions, split_installed_paper_sets
from cie_alevel_splitter.local_corpus import InstalledPaperSet, discover_installed_paper_sets, filter_paper_sets


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "requirements.md").exists() and (parent / "tools").exists():
            return parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root()
DEFAULT_RAW_ROOT = Path("data/raw_papers")
DEFAULT_PROCESSED_ROOT = Path("data/processed_questions")
DEFAULT_REPORT = Path("data/reports/cie_image_split_status.jsonl")
FONT_FAMILY = "Segoe UI"
TEXT_SIZE = 13
TITLE_SIZE = 18
PANEL_RADIUS = 6
START_COLOR = "#166534"
STOP_COLOR = "#991b1b"
RIGHT_PANEL_MIN_WIDTH = 920
LEFT_PANEL_WIDTH = 360
PAPER_LIST_MIN_WIDTH = 310
EXPAND_BUTTON_WIDTH = 32
CHECKBOX_WIDTH = 34
LIST_ROW_HEIGHT = 34
LIST_ROW_GAP = 4
SUBJECT_TEXT_WIDTH = PAPER_LIST_MIN_WIDTH - CHECKBOX_WIDTH - EXPAND_BUTTON_WIDTH - (LIST_ROW_GAP * 2) - 12
PAPER_TEXT_WIDTH = PAPER_LIST_MIN_WIDTH - CHECKBOX_WIDTH - 28 - LIST_ROW_GAP - 12

TRANSLATIONS = {
    "zh": {
        "window_title": "Oh-My-Exam 切题工具",
        "heading": "本地试卷切题与 9709/9231 几何小问导出",
        "language": "语言",
        "theme_mode": "主题",
        "theme_system": "跟随系统",
        "theme_light": "浅色",
        "theme_dark": "深色",
        "paths": "路径",
        "filters": "筛选",
        "papers": "本地科目",
        "run": "运行",
        "output": "输出",
        "raw_root": "原始 PDF 目录",
        "processed_root": "切题输出目录",
        "report": "状态报告",
        "paper_search": "搜索科目、年份、session、component",
        "paper_count": "{shown}/{total} 个科目",
        "no_papers": "没有匹配的本地科目",
        "scanning": "正在扫描本地试卷...",
        "reload": "重新扫描",
        "select_all": "全选",
        "clear_all": "清空",
        "start_year": "开始年份",
        "end_year": "结束年份",
        "workers": "并发线程",
        "dpi": "DPI",
        "threshold": "黑白阈值",
        "quality": "JPEG 质量",
        "limit": "限制数量（空 = 全部）",
        "remove_answer_lines": "移除明显空白作答线",
        "selected": "将处理：{count} 套试卷",
        "ready": "就绪",
        "invalid": "设置无效：{message}",
        "start": "开始切题",
        "stop": "结束",
        "starting": "正在启动...",
        "stopping": "正在结束...",
        "done": "完成：{counts}",
        "error": "错误：{message}",
        "progress": "{index}/{total} {key} -> {status} {counts} | 预计剩余 {eta}",
        "status_split": "已切题",
        "status_failed": "失败",
        "status_skipped": "已跳过",
    },
    "en": {
        "window_title": "Oh-My-Exam Splitter",
        "heading": "Local Paper Splitting with 9709/9231 Geometry Subquestions",
        "language": "Language",
        "theme_mode": "Theme",
        "theme_system": "System",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "paths": "Paths",
        "filters": "Filters",
        "papers": "Installed subjects",
        "run": "Run",
        "output": "Output",
        "raw_root": "Raw PDF directory",
        "processed_root": "Split output directory",
        "report": "Status report",
        "paper_search": "Search subject, year, session, component",
        "paper_count": "{shown}/{total} subjects",
        "no_papers": "No matching local subjects",
        "scanning": "Scanning local papers...",
        "reload": "Rescan",
        "select_all": "Select all",
        "clear_all": "Clear",
        "start_year": "Start year",
        "end_year": "End year",
        "workers": "Workers",
        "dpi": "DPI",
        "threshold": "B/W threshold",
        "quality": "JPEG quality",
        "limit": "Limit (blank = all)",
        "remove_answer_lines": "Remove obvious blank answer lines",
        "selected": "Will process: {count} paper sets",
        "ready": "Ready",
        "invalid": "Invalid settings: {message}",
        "start": "Start splitting",
        "stop": "Stop",
        "starting": "Starting...",
        "stopping": "Stopping...",
        "done": "Done: {counts}",
        "error": "Error: {message}",
        "progress": "{index}/{total} {key} -> {status} {counts} | ETA {eta}",
        "status_split": "split",
        "status_failed": "failed",
        "status_skipped": "skipped",
    },
}


def main() -> None:
    try:
        import flet as ft
    except ImportError as exc:
        raise SystemExit(
            "Flet is required for the GUI. Install it inside the project venv with: "
            "python -m pip install flet Pillow PyMuPDF pypdf"
        ) from exc

    def app(page: ft.Page) -> None:
        locale = {"value": "zh"}
        installed: list[InstalledPaperSet] = []
        subject_groups: dict[str, list[InstalledPaperSet]] = {}
        selected_keys: set[str] = set()
        paper_checks: dict[str, ft.Checkbox] = {}
        subject_checks: dict[str, ft.Checkbox] = {}
        expanded_subjects: set[str] = set()
        events: queue.Queue[dict[str, object]] = queue.Queue()
        stop_requested = threading.Event()
        worker: threading.Thread | None = None

        def t(message_key: str, **kwargs: object) -> str:
            template = TRANSLATIONS[locale["value"]][message_key]
            return template.format(**kwargs) if kwargs else template

        def status_label(status: object) -> str:
            return TRANSLATIONS[locale["value"]].get(f"status_{status}", str(status))

        def format_duration(seconds: object) -> str:
            try:
                value = max(0, int(float(seconds)))
            except (TypeError, ValueError):
                value = 0
            minutes, second = divmod(value, 60)
            hours, minute = divmod(minutes, 60)
            if hours:
                return f"{hours}h {minute:02d}m"
            if minutes:
                return f"{minutes}m {second:02d}s"
            return f"{second}s"

        def resolved_path(value: str | None) -> Path:
            path = Path((value or "").strip())
            if path.is_absolute():
                return path
            return PROJECT_ROOT / path

        page.title = t("window_title")
        page.window_min_width = 1120
        page.window_min_height = 760
        page.padding = 16
        page.spacing = 0
        page.theme_mode = ft.ThemeMode.SYSTEM
        page.bgcolor = ft.Colors.SURFACE_CONTAINER_LOW

        def panel(
            controls: list,
            *,
            expand: bool | int = False,
            width: int | None = None,
            height: int | None = None,
        ):
            inner = ft.Column(
                controls,
                spacing=10,
                expand=True,
                scroll=ft.ScrollMode.ALWAYS,
            )
            return ft.Container(
                inner,
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
        ):
            content = ft.Container(
                ft.Column(controls, spacing=10),
                width=min_content_width,
            )
            return ft.Container(
                ft.Column(
                    [
                        ft.Row(
                            [content],
                            scroll=ft.ScrollMode.AUTO,
                            expand=True,
                        )
                    ],
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

        def horizontal_area(control, *, expand: bool | int = True, width: int | None = None):
            return ft.Container(
                ft.Row([control], scroll=ft.ScrollMode.ALWAYS, expand=True),
                expand=expand,
                width=width,
            )

        def output_panel():
            return ft.Container(
                ft.Column(
                    [
                        output_title,
                        progress,
                        summary,
                        ft.Container(
                            ft.Row([log_view], scroll=ft.ScrollMode.ALWAYS, expand=True),
                            expand=True,
                            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                            border_radius=PANEL_RADIUS,
                            padding=8,
                        ),
                    ],
                    spacing=10,
                    expand=True,
                    scroll=None,
                ),
                height=250,
                padding=14,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=PANEL_RADIUS,
            )

        def subject_list_area():
            return ft.Row(
                [ft.Container(paper_list, width=PAPER_LIST_MIN_WIDTH, expand=False)],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            )

        def section_title(key: str):
            return ft.Text(t(key), size=TEXT_SIZE, weight=ft.FontWeight.W_500, font_family=FONT_FAMILY)

        title = ft.Text(t("heading"), size=TITLE_SIZE, weight=ft.FontWeight.W_500, font_family=FONT_FAMILY)
        language = ft.Dropdown(
            label=t("language"),
            value="zh",
            width=150,
            text_size=TEXT_SIZE,
            options=[ft.DropdownOption(key="zh", text="中文"), ft.DropdownOption(key="en", text="English")],
        )
        theme_mode = ft.Dropdown(
            label=t("theme_mode"),
            value="system",
            width=150,
            text_size=TEXT_SIZE,
            options=[
                ft.DropdownOption(key="system", text=t("theme_system")),
                ft.DropdownOption(key="light", text=t("theme_light")),
                ft.DropdownOption(key="dark", text=t("theme_dark")),
            ],
        )
        raw_root = ft.TextField(label=t("raw_root"), value=str(DEFAULT_RAW_ROOT), expand=True, text_size=TEXT_SIZE)
        processed_root = ft.TextField(label=t("processed_root"), value=str(DEFAULT_PROCESSED_ROOT), expand=True, text_size=TEXT_SIZE)
        report_path = ft.TextField(label=t("report"), value=str(DEFAULT_REPORT), expand=True, text_size=TEXT_SIZE)
        start_year = ft.TextField(label=t("start_year"), value="", width=120, text_size=TEXT_SIZE)
        end_year = ft.TextField(label=t("end_year"), value="", width=120, text_size=TEXT_SIZE)
        workers = ft.TextField(label=t("workers"), value=str(min(8, max(1, os.cpu_count() or 4))), width=110, text_size=TEXT_SIZE)
        dpi = ft.TextField(label=t("dpi"), value="150", width=100, text_size=TEXT_SIZE)
        threshold = ft.TextField(label=t("threshold"), value="215", width=120, text_size=TEXT_SIZE)
        quality = ft.TextField(label=t("quality"), value="88", width=120, text_size=TEXT_SIZE)
        limit = ft.TextField(label=t("limit"), value="", width=180, text_size=TEXT_SIZE)
        remove_answer_lines = ft.Checkbox(label=t("remove_answer_lines"), value=True)

        paths_title = section_title("paths")
        filters_title = section_title("filters")
        papers_title = section_title("papers")
        run_title = section_title("run")
        output_title = section_title("output")
        paper_search = ft.TextField(label=t("paper_search"), value="", text_size=TEXT_SIZE)
        paper_count = ft.Text("", size=TEXT_SIZE, font_family=FONT_FAMILY)
        paper_list = ft.ListView(expand=True, spacing=2)
        reload_button = ft.TextButton(t("reload"))
        select_all_button = ft.TextButton(t("select_all"))
        clear_all_button = ft.TextButton(t("clear_all"))
        progress = ft.ProgressBar(value=0)
        summary = ft.Text(t("ready"), size=TEXT_SIZE, selectable=True, font_family=FONT_FAMILY)
        selected_summary = ft.Text("", size=TEXT_SIZE, selectable=True, font_family=FONT_FAMILY)
        log_view = ft.ListView(expand=True, spacing=4, auto_scroll=True)
        start_button = ft.ElevatedButton(
            t("start"),
            style=ft.ButtonStyle(bgcolor=START_COLOR, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=PANEL_RADIUS)),
        )
        stop_button = ft.ElevatedButton(
            t("stop"),
            disabled=True,
            style=ft.ButtonStyle(bgcolor=STOP_COLOR, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=PANEL_RADIUS)),
        )

        def parse_int(value: str, field: str) -> int | None:
            value = value.strip()
            if not value:
                return None
            try:
                return int(value)
            except ValueError as exc:
                raise ValueError(f"{field}: {value}") from exc

        def selected_sets() -> list[InstalledPaperSet]:
            chosen = filter_paper_sets(
                installed,
                keys=selected_keys,
                start_year=parse_int(start_year.value or "", "start_year"),
                end_year=parse_int(end_year.value or "", "end_year"),
            )
            if limit.value.strip():
                chosen = chosen[: int(limit.value)]
            return chosen

        def refresh_selection(_: object | None = None) -> None:
            try:
                selected_summary.value = t("selected", count=len(selected_sets()))
            except Exception as exc:
                selected_summary.value = t("invalid", message=exc)
            if page.controls:
                page.update()

        def subject_key(paper_set: InstalledPaperSet) -> str:
            return f"{paper_set.exam_board}/{paper_set.qualification}/{paper_set.subject_code}"

        def subject_label(paper_set: InstalledPaperSet, papers: list[InstalledPaperSet]) -> str:
            docs = set()
            for item in papers:
                if item.qp:
                    docs.add("QP")
                if item.ms:
                    docs.add("MS")
            years = sorted({item.year for item in papers})
            year_text = str(years[0]) if len(years) == 1 else f"{years[0]}-{years[-1]}"
            return f"{paper_set.subject_code} - {paper_set.subject_name} | {len(papers)} 套 | {year_text} | {'+'.join(sorted(docs))}"

        def subject_display_label(paper_set: InstalledPaperSet) -> str:
            return f"{paper_set.subject_code} - {paper_set.subject_name}"

        def compact_checkbox(value: bool, on_change):
            return ft.Checkbox(
                value=value,
                width=CHECKBOX_WIDTH,
                height=LIST_ROW_HEIGHT,
                scale=0.75,
                visual_density=ft.VisualDensity.COMPACT,
                on_change=on_change,
            )

        def grouped_by_subject() -> dict[str, list[InstalledPaperSet]]:
            return subject_groups

        def update_subject_check(subject: str) -> None:
            check = subject_checks.get(subject)
            if check is None:
                return
            subject_papers = subject_groups.get(subject, [])
            values = [item.key in selected_keys for item in subject_papers]
            check.value = bool(values) and all(values)

        def set_subject(subject: str, value: bool) -> None:
            for paper_set in subject_groups.get(subject, []):
                if value:
                    selected_keys.add(paper_set.key)
                else:
                    selected_keys.discard(paper_set.key)
                if paper_set.key in paper_checks:
                    paper_checks[paper_set.key].value = value
            update_subject_check(subject)
            refresh_selection()

        def set_paper(paper_set: InstalledPaperSet, value: bool) -> None:
            if value:
                selected_keys.add(paper_set.key)
            else:
                selected_keys.discard(paper_set.key)
            update_subject_check(subject_key(paper_set))
            refresh_selection()

        def paper_checkbox(paper_set: InstalledPaperSet):
            check = paper_checks.get(paper_set.key)
            if check is None:
                paper_checks[paper_set.key] = compact_checkbox(
                    value=paper_set.key in selected_keys,
                    on_change=lambda event, item=paper_set: set_paper(item, bool(event.control.value)),
                )
                check = paper_checks[paper_set.key]
            else:
                check.value = paper_set.key in selected_keys
            return check

        def paper_label(paper_set: InstalledPaperSet) -> str:
            docs = "QP+MS" if paper_set.qp and paper_set.ms else ("QP" if paper_set.qp else "MS")
            return f"{paper_set.subject_code} - {paper_set.subject_name} | {paper_set.year} {paper_set.session} {paper_set.component} | {docs}"

        def toggle_subject(subject: str) -> None:
            if subject in expanded_subjects:
                expanded_subjects.remove(subject)
            else:
                expanded_subjects.add(subject)
            refresh_paper_filter()

        def refresh_paper_filter(_: object | None = None) -> None:
            needle = (paper_search.value or "").strip().lower()
            shown = []
            shown_subjects = 0
            groups = grouped_by_subject()
            for subject, subject_papers in groups.items():
                first = subject_papers[0]
                label = subject_label(first, subject_papers)
                haystack = " ".join([subject, label, *(paper_set.key for paper_set in subject_papers)]).lower()
                paper_matches = [
                    paper_set
                    for paper_set in subject_papers
                    if not needle or needle in f"{paper_set.key} {paper_set.year} {paper_set.session} {paper_set.component}".lower()
                ]
                if needle and needle not in haystack and not paper_matches:
                    continue
                shown_subjects += 1
                subject_check = subject_checks[subject]
                subject_text = subject_display_label(first)
                subject_detail = subject_label(first, subject_papers)
                expand_button = ft.IconButton(
                    icon=ft.Icons.KEYBOARD_ARROW_DOWN if subject in expanded_subjects else ft.Icons.KEYBOARD_ARROW_RIGHT,
                    icon_size=18,
                    width=EXPAND_BUTTON_WIDTH,
                    height=LIST_ROW_HEIGHT,
                    tooltip=subject_detail,
                    on_click=lambda _, item=subject: toggle_subject(item),
                )
                shown.append(
                    ft.Container(
                        ft.Row(
                            [
                                subject_check,
                                ft.Text(
                                    subject_text,
                                    width=SUBJECT_TEXT_WIDTH,
                                    size=TEXT_SIZE,
                                    weight=ft.FontWeight.W_500,
                                    font_family=FONT_FAMILY,
                                    no_wrap=True,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                expand_button,
                            ],
                            spacing=LIST_ROW_GAP,
                            height=LIST_ROW_HEIGHT,
                            width=PAPER_LIST_MIN_WIDTH,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.START,
                        ),
                        padding=ft.Padding(4, 2, 4, 2),
                        border_radius=4,
                        tooltip=subject_detail,
                    )
                )
                if subject in expanded_subjects:
                    visible_papers = paper_matches if needle and paper_matches else subject_papers
                    for paper_set in visible_papers:
                        check = paper_checkbox(paper_set)
                        label = paper_label(paper_set)
                        shown.append(
                            ft.Container(
                                ft.Row(
                                    [
                                        check,
                                        ft.Text(
                                            label,
                                            width=PAPER_TEXT_WIDTH,
                                            size=TEXT_SIZE,
                                            font_family=FONT_FAMILY,
                                            no_wrap=True,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                    ],
                                    spacing=LIST_ROW_GAP,
                                    height=LIST_ROW_HEIGHT,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    alignment=ft.MainAxisAlignment.START,
                                ),
                                padding=ft.Padding(28, 0, 4, 0),
                                border_radius=4,
                                tooltip=label,
                            )
                        )
            paper_list.controls = shown or [ft.Text(t("no_papers"), size=TEXT_SIZE, font_family=FONT_FAMILY)]
            paper_count.value = t("paper_count", shown=shown_subjects, total=len(groups))
            refresh_selection()

        def rebuild_papers(_: object | None = None) -> None:
            nonlocal installed, subject_groups, selected_keys
            previous_keys = set(selected_keys)
            previous_subjects = {key: bool(check.value) for key, check in subject_checks.items()}
            installed = discover_installed_paper_sets(resolved_path(raw_root.value))
            groups: dict[str, list[InstalledPaperSet]] = {}
            for paper_set in installed:
                groups.setdefault(subject_key(paper_set), []).append(paper_set)
            subject_groups = dict(sorted(groups.items(), key=lambda item: (item[1][0].subject_code, item[1][0].subject_name)))
            selected_keys = {paper_set.key for paper_set in installed if not previous_keys or paper_set.key in previous_keys}
            paper_checks.clear()
            subject_checks.clear()
            for subject, subject_papers in subject_groups.items():
                if subject in previous_subjects and previous_subjects[subject] is False:
                    for paper_set in subject_papers:
                        selected_keys.discard(paper_set.key)
                subject_checks[subject] = compact_checkbox(
                    value=True,
                    on_change=lambda event, item=subject: set_subject(item, bool(event.control.value)),
                )
                update_subject_check(subject)
            refresh_paper_filter()

        def set_all(value: bool) -> None:
            if value:
                selected_keys.update(paper_set.key for paper_set in installed)
            else:
                selected_keys.clear()
            for check in paper_checks.values():
                check.value = value
            for check in subject_checks.values():
                check.value = value
            refresh_selection()
            refresh_paper_filter()

        def append_log(text: str) -> None:
            log_view.controls.append(
                horizontal_area(
                    ft.Text(text, size=TEXT_SIZE, selectable=True, no_wrap=True, font_family=FONT_FAMILY)
                )
            )
            if len(log_view.controls) > 500:
                del log_view.controls[:100]

        def poll_events() -> None:
            nonlocal worker
            changed = False
            while True:
                try:
                    event = events.get_nowait()
                except queue.Empty:
                    break
                changed = True
                kind = event.get("kind")
                if kind == "progress":
                    index = int(event.get("index") or 0)
                    total = int(event.get("total") or 0)
                    progress.value = index / total if index and total else progress.value
                    status = status_label(event.get("status"))
                    summary.value = t(
                        "progress",
                        index=index,
                        total=total,
                        key=event.get("key"),
                        status=status,
                        counts=event.get("counts"),
                        eta=format_duration(event.get("eta_seconds")),
                    )
                    append_log(summary.value)
                elif kind == "done":
                    summary.value = t("done", counts=event.get("counts"))
                    start_button.disabled = False
                    stop_button.disabled = True
                    worker = None
                elif kind == "error":
                    summary.value = t("error", message=event.get("message"))
                    append_log(summary.value)
                    start_button.disabled = False
                    stop_button.disabled = True
                    worker = None
            if changed:
                page.update()
            if worker is not None:
                page.run_task(_sleep_and_poll)

        async def _sleep_and_poll() -> None:
            import asyncio

            await asyncio.sleep(0.3)
            poll_events()

        async def _deferred_initial_scan() -> None:
            import asyncio

            await asyncio.sleep(0.05)
            rebuild_papers()

        def run_split() -> None:
            try:
                keys = {paper_set.key for paper_set in selected_sets()}

                def report_progress(event: dict[str, object]) -> None:
                    if stop_requested.is_set():
                        return
                    events.put({"kind": "progress", **event})

                counts = split_installed_paper_sets(
                    resolved_path(raw_root.value),
                    resolved_path(processed_root.value),
                    resolved_path(report_path.value),
                    keys=keys,
                    workers=int(workers.value),
                    options=SplitOptions(
                        dpi=int(dpi.value),
                        threshold=int(threshold.value),
                        quality=int(quality.value),
                        remove_answer_lines=bool(remove_answer_lines.value),
                    ),
                    progress=report_progress,
                    should_stop=stop_requested.is_set,
                )
                events.put({"kind": "done", "counts": counts})
            except Exception as exc:
                events.put({"kind": "error", "message": str(exc)})

        def start_split(_: object) -> None:
            nonlocal worker
            if worker is not None:
                return
            log_view.controls.clear()
            stop_requested.clear()
            start_button.disabled = True
            stop_button.disabled = False
            progress.value = 0
            summary.value = t("starting")
            worker = threading.Thread(target=run_split, daemon=True)
            worker.start()
            page.update()
            poll_events()

        def stop_split(_: object) -> None:
            if worker is None:
                return
            stop_requested.set()
            stop_button.disabled = True
            summary.value = t("stopping")
            page.update()

        def apply_theme(_: object | None = None) -> None:
            page.theme_mode = {"light": ft.ThemeMode.LIGHT, "dark": ft.ThemeMode.DARK}.get(theme_mode.value or "system", ft.ThemeMode.SYSTEM)
            page.update()

        def apply_language(_: object | None = None) -> None:
            locale["value"] = language.value or "zh"
            page.title = t("window_title")
            title.value = t("heading")
            language.label = t("language")
            theme_mode.label = t("theme_mode")
            theme_mode.options = [
                ft.DropdownOption(key="system", text=t("theme_system")),
                ft.DropdownOption(key="light", text=t("theme_light")),
                ft.DropdownOption(key="dark", text=t("theme_dark")),
            ]
            raw_root.label = t("raw_root")
            processed_root.label = t("processed_root")
            report_path.label = t("report")
            start_year.label = t("start_year")
            end_year.label = t("end_year")
            workers.label = t("workers")
            dpi.label = t("dpi")
            threshold.label = t("threshold")
            quality.label = t("quality")
            limit.label = t("limit")
            remove_answer_lines.label = t("remove_answer_lines")
            paths_title.value = t("paths")
            filters_title.value = t("filters")
            papers_title.value = t("papers")
            run_title.value = t("run")
            output_title.value = t("output")
            paper_search.label = t("paper_search")
            reload_button.text = t("reload")
            select_all_button.text = t("select_all")
            clear_all_button.text = t("clear_all")
            start_button.text = t("start")
            stop_button.text = t("stop")
            if worker is None and progress.value == 0:
                summary.value = t("ready")
            refresh_paper_filter()

        start_button.on_click = start_split
        stop_button.on_click = stop_split
        reload_button.on_click = rebuild_papers
        select_all_button.on_click = lambda _: set_all(True)
        clear_all_button.on_click = lambda _: set_all(False)
        paper_search.on_change = refresh_paper_filter
        language.on_select = apply_language
        theme_mode.on_select = apply_theme
        for control in [raw_root, start_year, end_year, limit]:
            control.on_change = refresh_selection

        paper_list.controls = [ft.Text(t("scanning"), size=TEXT_SIZE, font_family=FONT_FAMILY)]
        paper_count.value = t("paper_count", shown=0, total=0)
        main_view = ft.Column(
                [
                    ft.Row(
                        [title, ft.Row([theme_mode, language], spacing=12)],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                    ),
                    ft.Row(
                        [
                            panel(
                                [
                                    ft.Row([papers_title, paper_count], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    paper_search,
                                    ft.Row([select_all_button, clear_all_button, reload_button], spacing=4),
                                    ft.Container(
                                        subject_list_area(),
                                        expand=True,
                                        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                                        border_radius=PANEL_RADIUS,
                                        padding=6,
                                    ),
                                ],
                                width=LEFT_PANEL_WIDTH,
                                expand=False,
                            ),
                            scrollable_panel(
                                [
                                    paths_title,
                                    ft.Row([raw_root], spacing=12),
                                    ft.Row([processed_root, report_path], spacing=12),
                                    ft.Divider(height=1),
                                    filters_title,
                                    ft.Row([start_year, end_year, workers, dpi, threshold, quality, limit], spacing=12, wrap=True),
                                    ft.Row([remove_answer_lines], spacing=12, wrap=True),
                                    ft.Divider(height=1),
                                    run_title,
                                    ft.Row(
                                        [start_button, stop_button, selected_summary],
                                        spacing=12,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        wrap=True,
                                    ),
                                ],
                                expand=True,
                            ),
                        ],
                        expand=True,
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                    output_panel(),
                ],
                expand=True,
                spacing=12,
            )
        page.add(main_view)
        refresh_selection()
        page.run_task(_deferred_initial_scan)

    ft.app(target=app)


if __name__ == "__main__":
    main()

