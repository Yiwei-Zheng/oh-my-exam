from __future__ import annotations

import json
import queue
import threading
import time
from pathlib import Path

from cie_alevel_downloader.cie import load_assets
from cie_alevel_downloader.frank_discovery import (
    DEFAULT_SUBJECT_AVAILABILITY_DIR,
    ensure_subject_availability,
    estimate_crawl_seconds,
    format_duration,
    load_availability_index,
    load_subject_availability_assets,
    subject_availability_path,
)
from cie_alevel_downloader.pipeline import crawl_assets, filter_assets


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "requirements.md").exists() and (parent / "tools").exists():
            return parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root()
DEFAULT_MANIFEST = Path("resources/exam_boards/cie/cie_a_level_subject_rules.json")
LEGACY_DEFAULT_MANIFEST = Path("resources/cie/cie_a_level_subject_rules.json")
FALLBACK_MANIFEST = Path("configs/cie_a_level_through_2025_manifest.json")
DEFAULT_RAW_ROOT = Path("data/raw_papers")
DEFAULT_REPORT = Path("data/reports/cie_download_status.jsonl")
FONT_FAMILY = "Segoe UI"
TEXT_SIZE = 13
TITLE_SIZE = 18
PANEL_RADIUS = 6
START_COLOR = "#15803D"
START_DISABLED_COLOR = "#6B7280"
STOP_COLOR = "#B91C1C"
SETTINGS_PATH = Path("data/gui/cie_downloader_settings.json")
THEME_VALUES = {"system", "light", "dark"}
RIGHT_PANEL_MIN_WIDTH = 920
SUBJECT_PERCENT_WIDTH = 54

TRANSLATIONS = {
    "zh": {
        "window_title": "Oh-My-Exam CIE 下载器",
        "heading": "CIE A-Level 试卷下载器",
        "language": "语言",
        "theme_mode": "主题",
        "theme_system": "跟随系统",
        "theme_light": "浅色",
        "theme_dark": "深色",
        "manifest": "Manifest 配置",
        "availability_index": "Frank 资产表目录",
        "raw_root": "原始 PDF 输出目录",
        "report": "状态报告",
        "paths": "路径",
        "filters": "筛选",
        "run": "运行",
        "output": "输出",
        "start_year": "开始年份",
        "end_year": "结束年份",
        "delay": "访问间隔秒数",
        "workers": "并发线程",
        "limit": "限制数量（空 = 全部）",
        "resume": "跳过已完成的 downloaded/missing 项",
        "use_availability": "只下载资产表中存在的试卷",
        "sniff": "嗅探",
        "subjects": "科目",
        "subject_search": "搜索科目或代码",
        "subject_count": "{shown}/{total} 个科目",
        "no_subjects": "没有匹配的科目",
        "select_all": "全选",
        "clear_all": "清空",
        "reload_subjects": "重新读取科目",
        "ready": "就绪",
        "start_download": "开始下载",
        "downloading": "下载中...",
        "stop_after_current": "当前文件完成后停止",
        "stopping": "停止中...",
        "selected": "已选择可下载试卷：{count}，预计耗时：{duration}",
        "eta": "剩余约 {duration}",
        "eta_calculating": "正在估算剩余时间",
        "invalid": "设置无效：{message}",
        "starting": "正在启动...",
        "sniffing": "正在嗅探：{subjects}，{start_year}-{end_year}",
        "sniff_done": "嗅探完成：{subjects}，失败查询：{failures}",
        "stop_requested": "已请求停止；等待当前文件完成。",
        "done": "完成：{counts}",
        "error": "错误：{message}",
        "progress": "{index}/{total} {asset} -> {status} {counts}",
        "log": "{index}/{total} {asset} {status} {message}",
        "status_downloaded": "已下载",
        "status_missing": "不存在",
        "status_failed": "失败",
        "status_rate_limited": "被限流",
        "status_skipped": "已跳过",
    },
    "en": {
        "window_title": "Oh-My-Exam CIE Downloader",
        "heading": "CIE A-Level Paper Downloader",
        "language": "Language",
        "theme_mode": "Theme",
        "theme_system": "System",
        "theme_light": "Light",
        "theme_dark": "Dark",
        "manifest": "Manifest",
        "availability_index": "Frank asset directory",
        "raw_root": "Raw PDF output",
        "report": "Status report",
        "paths": "Paths",
        "filters": "Filters",
        "run": "Run",
        "output": "Output",
        "start_year": "Start year",
        "end_year": "End year",
        "delay": "Delay seconds",
        "workers": "Workers",
        "limit": "Limit (blank = all)",
        "resume": "Resume completed downloaded/missing files",
        "use_availability": "Only download papers listed in the asset index",
        "sniff": "Sniff",
        "subjects": "Subjects",
        "subject_search": "Search subjects or codes",
        "subject_count": "{shown}/{total} subjects",
        "no_subjects": "No matching subjects",
        "select_all": "Select all",
        "clear_all": "Clear all",
        "reload_subjects": "Reload subjects",
        "ready": "Ready",
        "start_download": "Start download",
        "downloading": "Downloading...",
        "stop_after_current": "Stop after current file",
        "stopping": "Stopping...",
        "selected": "Selected downloadable papers: {count}, estimated time: {duration}",
        "eta": "ETA {duration}",
        "eta_calculating": "Estimating time remaining",
        "invalid": "Invalid settings: {message}",
        "starting": "Starting...",
        "sniffing": "Sniffing: {subjects}, {start_year}-{end_year}",
        "sniff_done": "Sniff done: {subjects}, failed queries: {failures}",
        "stop_requested": "Stop requested; waiting for current file to finish.",
        "done": "Done: {counts}",
        "error": "Error: {message}",
        "progress": "{index}/{total} {asset} -> {status} {counts}",
        "log": "{index}/{total} {asset} {status} {message}",
        "status_downloaded": "downloaded",
        "status_missing": "missing",
        "status_failed": "failed",
        "status_rate_limited": "rate limited",
        "status_skipped": "skipped",
    },
}


def project_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def load_subject_options(manifest_path: Path) -> dict[str, str]:
    raw = json.loads(project_path(manifest_path).read_text(encoding="utf-8-sig"))
    options: dict[str, str] = {}
    for subject in raw.get("subjects", []):
        if not isinstance(subject, dict):
            continue
        code = str(subject.get("code", "")).strip()
        name = str(subject.get("name", "")).strip()
        if code:
            options[code] = name or code
    return dict(sorted(options.items(), key=lambda item: (item[1].lower(), item[0])))


def default_manifest_path() -> Path:
    if project_path(DEFAULT_MANIFEST).exists():
        return DEFAULT_MANIFEST
    if project_path(LEGACY_DEFAULT_MANIFEST).exists():
        return LEGACY_DEFAULT_MANIFEST
    return FALLBACK_MANIFEST


def load_gui_settings(path: Path = SETTINGS_PATH) -> dict[str, str]:
    resolved = project_path(path)
    if not resolved.exists():
        return {}
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    theme = str(raw.get("theme_mode", "")).strip().lower()
    return {"theme_mode": theme} if theme in THEME_VALUES else {}


def save_gui_settings(settings: dict[str, str], path: Path = SETTINGS_PATH) -> None:
    resolved = project_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    safe_settings = {key: value for key, value in settings.items() if key == "theme_mode" and value in THEME_VALUES}
    resolved.write_text(json.dumps(safe_settings, ensure_ascii=False, indent=2), encoding="utf-8")


def local_pdf_relative_paths(raw_root: Path) -> set[str]:
    if not raw_root.exists():
        return set()
    paths: set[str] = set()
    for path in raw_root.rglob("*.pdf"):
        if path.is_file() and path.stat().st_size > 0:
            paths.add(path.relative_to(raw_root).as_posix().lower())
    return paths


def subject_download_percentage(
    subject_code: str,
    *,
    raw_root: Path,
    availability_dir: Path,
    start_year: int,
    end_year: int,
    document_types: set[str],
    qualification: str = "a_level",
    local_pdfs: set[str] | None = None,
) -> int:
    path = subject_availability_path(subject_code, qualification=qualification, availability_dir=availability_dir)
    if not path.exists():
        return 0
    assets = filter_assets(
        load_availability_index(path),
        subject_codes={subject_code},
        document_types=document_types,
        start_year=start_year,
        end_year=end_year,
    )
    if not assets:
        return 0
    local_pdfs = local_pdfs if local_pdfs is not None else local_pdf_relative_paths(raw_root)
    downloaded = 0
    for asset in assets:
        current = asset.relative_pdf_path.as_posix().lower()
        legacy = asset.legacy_relative_pdf_path.as_posix().lower()
        if current in local_pdfs or legacy in local_pdfs:
            downloaded += 1
    return round(downloaded * 100 / len(assets))


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
        gui_settings = load_gui_settings()

        def t(key: str, **kwargs: object) -> str:
            template = TRANSLATIONS[locale["value"]][key]
            return template.format(**kwargs) if kwargs else template

        def status_label(status: object) -> str:
            return TRANSLATIONS[locale["value"]].get(f"status_{status}", str(status))

        page.title = t("window_title")
        page.window_min_width = 1080
        page.window_min_height = 760
        page.padding = 16
        page.spacing = 0
        page.theme_mode = {
            "light": ft.ThemeMode.LIGHT,
            "dark": ft.ThemeMode.DARK,
        }.get(gui_settings.get("theme_mode"), ft.ThemeMode.SYSTEM)
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

        def section_title(key: str) -> object:
            return ft.Text(t(key), size=TEXT_SIZE, weight=ft.FontWeight.W_500, font_family=FONT_FAMILY)

        def command_button_style(color: str) -> object:
            return ft.ButtonStyle(bgcolor=color, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=PANEL_RADIUS))

        title = ft.Text(t("heading"), size=TITLE_SIZE, weight=ft.FontWeight.W_500, font_family=FONT_FAMILY)
        language = ft.Dropdown(
            label=t("language"),
            value="zh",
            width=180,
            text_size=TEXT_SIZE,
            options=[
                ft.DropdownOption(key="zh", text="中文"),
                ft.DropdownOption(key="en", text="English"),
            ],
        )
        theme_mode = ft.Dropdown(
            label=t("theme_mode"),
            value=gui_settings.get("theme_mode", "system"),
            width=160,
            text_size=TEXT_SIZE,
            options=[
                ft.DropdownOption(key="system", text=t("theme_system")),
                ft.DropdownOption(key="light", text=t("theme_light")),
                ft.DropdownOption(key="dark", text=t("theme_dark")),
            ],
        )
        manifest_path = ft.TextField(label=t("manifest"), value=str(default_manifest_path()), expand=True, text_size=TEXT_SIZE)
        availability_path = ft.TextField(label=t("availability_index"), value=str(DEFAULT_SUBJECT_AVAILABILITY_DIR), expand=True, text_size=TEXT_SIZE)
        raw_root = ft.TextField(label=t("raw_root"), value=str(DEFAULT_RAW_ROOT), expand=True, text_size=TEXT_SIZE)
        report_path = ft.TextField(label=t("report"), value=str(DEFAULT_REPORT), expand=True, text_size=TEXT_SIZE)
        start_year = ft.TextField(label=t("start_year"), value="2002", width=120, text_size=TEXT_SIZE)
        end_year = ft.TextField(label=t("end_year"), value="2025", width=120, text_size=TEXT_SIZE)
        delay = ft.TextField(label=t("delay"), value="1.5", width=140, text_size=TEXT_SIZE)
        workers = ft.TextField(label=t("workers"), value="4", width=120, text_size=TEXT_SIZE)
        limit = ft.TextField(label=t("limit"), value="", width=190, text_size=TEXT_SIZE)

        subject_checks: dict[str, ft.Checkbox] = {}
        qp_check = ft.Checkbox(label="QP", value=True)
        ms_check = ft.Checkbox(label="MS", value=True)
        resume_check = ft.Checkbox(label=t("resume"), value=True)
        availability_check = ft.Checkbox(label=t("use_availability"), value=True)
        sniff_check = ft.Checkbox(label=t("sniff"), value=False)

        progress = ft.ProgressBar(value=0)
        summary = ft.Text(t("ready"), size=TEXT_SIZE, selectable=True, font_family=FONT_FAMILY)
        asset_count = ft.Text("", size=TEXT_SIZE, font_family=FONT_FAMILY)
        paths_title = section_title("paths")
        filters_title = section_title("filters")
        run_title = section_title("run")
        output_title = section_title("output")
        subjects_title = section_title("subjects")
        subject_search = ft.TextField(label=t("subject_search"), value="", text_size=TEXT_SIZE)
        subject_count = ft.Text("", size=TEXT_SIZE, font_family=FONT_FAMILY)
        subject_list = ft.ListView(expand=True, spacing=2)
        select_all_button = ft.TextButton(t("select_all"))
        clear_all_button = ft.TextButton(t("clear_all"))
        reload_subjects_button = ft.TextButton(t("reload_subjects"))
        log_view = ft.ListView(expand=True, spacing=4, auto_scroll=True)
        start_button = ft.ElevatedButton(
            t("start_download"),
            tooltip=t("start_download"),
            style=command_button_style(START_COLOR),
        )
        stop_button = ft.ElevatedButton(
            t("stop_after_current"),
            tooltip=t("stop_after_current"),
            disabled=True,
            style=command_button_style(STOP_COLOR),
        )

        events: queue.Queue[dict[str, object]] = queue.Queue()
        stop_requested = threading.Event()
        worker: threading.Thread | None = None
        download_started_at: dict[str, float | None] = {"value": None}
        percentage_cache: dict[str, object] = {"signature": None, "values": {}}
        local_pdf_cache: dict[str, object] = {"root": None, "paths": set()}
        subject_asset_cache: dict[tuple[str, str], list] = {}
        selected_asset_cache: dict[str, object] = {"signature": None, "assets": []}

        def cached_local_pdf_paths(raw_dir: Path, *, force: bool = False) -> set[str]:
            root = str(raw_dir)
            if force or local_pdf_cache["root"] != root:
                local_pdf_cache["root"] = root
                local_pdf_cache["paths"] = local_pdf_relative_paths(raw_dir)
            paths = local_pdf_cache["paths"]
            return paths if isinstance(paths, set) else set()

        def cached_subject_assets(subjects: set[str], availability_dir: Path) -> list:
            assets = []
            base = str(availability_dir)
            for code in sorted(subjects):
                key = (base, code)
                if key not in subject_asset_cache:
                    path = subject_availability_path(code, availability_dir=availability_dir)
                    subject_asset_cache[key] = load_availability_index(path) if path.exists() else []
                assets.extend(subject_asset_cache[key])
            return sorted(assets, key=lambda asset: (asset.subject_code, asset.session, asset.document_type, asset.component))

        def invalidate_asset_caches() -> None:
            subject_asset_cache.clear()
            selected_asset_cache["signature"] = None
            selected_asset_cache["assets"] = []

        def subject_percentage_signature() -> tuple[str, str, int, int, tuple[str, ...]]:
            start, end = selected_year_range()
            return (
                str(project_path(raw_root.value)),
                str(project_path(availability_path.value)),
                start,
                end,
                tuple(sorted(selected_document_types())),
            )

        def refresh_percentage_cache(*, force: bool = False, subject_codes: set[str] | None = None) -> None:
            try:
                signature = subject_percentage_signature()
            except Exception:
                percentage_cache["signature"] = None
                percentage_cache["values"] = {}
                return
            if signature != percentage_cache["signature"]:
                percentage_cache["signature"] = signature
                percentage_cache["values"] = {}
            values = percentage_cache["values"]
            if not isinstance(values, dict):
                values = {}
                percentage_cache["values"] = values
            raw_dir = Path(signature[0])
            availability_dir = Path(signature[1])
            start = int(signature[2])
            end = int(signature[3])
            docs = set(signature[4])
            local_pdfs = cached_local_pdf_paths(raw_dir, force=force)
            targets = set(subject_codes or subject_checks.keys())
            for code in targets:
                if not force and code in values:
                    continue
                values[code] = (
                    subject_download_percentage(
                        code,
                        raw_root=raw_dir,
                        availability_dir=availability_dir,
                        start_year=start,
                        end_year=end,
                        document_types=docs,
                        local_pdfs=local_pdfs,
                    )
                    if docs
                    else 0
                )

        def invalidate_percentage_cache() -> None:
            percentage_cache["signature"] = None
            percentage_cache["values"] = {}
            local_pdf_cache["root"] = None
            local_pdf_cache["paths"] = set()

        def refresh_subject_filter(_: object | None = None) -> None:
            needle = (subject_search.value or "").strip().lower()
            shown: list[object] = []
            if page.controls:
                refresh_percentage_cache()
            percentages = percentage_cache["values"]
            if not isinstance(percentages, dict):
                percentages = {}
            for code, check in subject_checks.items():
                label = str(check.label or "")
                if needle and needle not in code.lower() and needle not in label.lower():
                    continue
                percentage = int(percentages.get(code, 0) or 0)
                shown.append(
                    ft.Container(
                        ft.Row(
                            [
                                check,
                                ft.Text(
                                    f"{percentage}%",
                                    width=SUBJECT_PERCENT_WIDTH,
                                    text_align=ft.TextAlign.RIGHT,
                                    size=TEXT_SIZE,
                                    font_family=FONT_FAMILY,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.Padding(4, 2, 4, 2),
                        border_radius=4,
                    )
                )
            if shown:
                subject_list.controls = shown
            else:
                subject_list.controls = [ft.Text(t("no_subjects"), size=TEXT_SIZE, font_family=FONT_FAMILY)]
            subject_count.value = t("subject_count", shown=len(shown), total=len(subject_checks))
            if page.controls:
                page.update()

        def rebuild_subject_checks(*, keep_selection: bool = True) -> None:
            previous = {code: bool(check.value) for code, check in subject_checks.items()}
            subject_checks.clear()
            options = load_subject_options(Path(manifest_path.value))
            for code, name in options.items():
                selected = previous.get(code, True) if keep_selection else True
                subject_checks[code] = ft.Checkbox(label=f"{code} - {name}", value=selected, on_change=refresh_count)
            invalidate_percentage_cache()
            refresh_subject_filter()

        def selected_subject_codes() -> set[str]:
            return {code for code, check in subject_checks.items() if check.value}

        def selected_year_range() -> tuple[int, int]:
            return int(start_year.value), int(end_year.value)

        def selected_document_types() -> set[str]:
            docs = set()
            if qp_check.value:
                docs.add("qp")
            if ms_check.value:
                docs.add("ms")
            return docs

        def selected_assets() -> list:
            subjects = selected_subject_codes()
            signature = (
                bool(availability_check.value),
                str(project_path(availability_path.value)),
                str(project_path(manifest_path.value)),
                tuple(sorted(subjects)),
                tuple(sorted(selected_document_types())),
                int(start_year.value),
                int(end_year.value),
                limit.value.strip(),
            )
            if signature == selected_asset_cache["signature"]:
                cached = selected_asset_cache["assets"]
                return list(cached) if isinstance(cached, list) else []
            if availability_check.value:
                assets = cached_subject_assets(subjects, project_path(availability_path.value))
            else:
                assets = load_assets(project_path(manifest_path.value))
            docs = selected_document_types()
            chosen = filter_assets(
                assets,
                subject_codes=subjects,
                document_types=docs,
                start_year=int(start_year.value),
                end_year=int(end_year.value),
            )
            if limit.value.strip():
                chosen = chosen[: int(limit.value)]
            selected_asset_cache["signature"] = signature
            selected_asset_cache["assets"] = list(chosen)
            return chosen

        def refresh_count(_: object | None = None) -> None:
            try:
                count = len(selected_assets())
                seconds = estimate_crawl_seconds(count, delay_seconds=float(delay.value), workers=int(workers.value))
                asset_count.value = t("selected", count=count, duration=format_duration(seconds))
            except Exception as exc:
                asset_count.value = t("invalid", message=exc)
            page.update()

        def refresh_download_scope(_: object | None = None) -> None:
            invalidate_percentage_cache()
            selected_asset_cache["signature"] = None
            selected_asset_cache["assets"] = []
            refresh_subject_filter()
            refresh_count()

        def reload_subjects(_: object | None = None) -> None:
            try:
                rebuild_subject_checks()
                refresh_count()
            except Exception as exc:
                asset_count.value = t("invalid", message=exc)
                page.update()

        def set_all_subjects(value: bool) -> None:
            for check in subject_checks.values():
                check.value = value
            selected_asset_cache["signature"] = None
            selected_asset_cache["assets"] = []
            refresh_count()

        def append_log(text: str) -> None:
            log_view.controls.append(ft.Text(text, size=TEXT_SIZE, selectable=True, font_family=FONT_FAMILY))
            if len(log_view.controls) > 500:
                del log_view.controls[:100]

        def set_download_running(is_running: bool) -> None:
            start_button.text = t("downloading") if is_running else t("start_download")
            stop_button.text = t("stop_after_current")
            start_button.disabled = is_running
            start_button.style = command_button_style(START_DISABLED_COLOR if is_running else START_COLOR)
            stop_button.disabled = not is_running

        def format_eta(counts: object, total: int) -> str:
            if not isinstance(counts, dict):
                return t("eta_calculating")
            completed = sum(int(counts.get(key, 0) or 0) for key in ["downloaded", "missing", "failed", "rate_limited", "skipped"])
            started_at = download_started_at["value"]
            if not started_at or completed <= 0:
                return t("eta_calculating")
            elapsed = max(0.1, time.monotonic() - started_at)
            remaining = max(0, total - completed)
            seconds = remaining / max(0.001, completed / elapsed)
            return t("eta", duration=format_duration(seconds))

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
                    index = int(event["index"])
                    total = int(event["total"])
                    progress.value = index / total if total else 0
                    counts = event.get("counts", {})
                    status = status_label(event.get("status"))
                    summary.value = f"{t('progress', index=index, total=total, asset=event.get('asset'), status=status, counts=counts)} · {format_eta(counts, total)}"
                    message = event.get("message") or ""
                    append_log(t("log", index=index, total=total, asset=event.get("asset"), status=status, message=message))
                    if event.get("status") == "downloaded":
                        subject_code = str(event.get("asset", "")).split("_", 1)[0]
                        if subject_code:
                            refresh_percentage_cache(force=True, subject_codes={subject_code})
                            refresh_subject_filter()
                elif kind == "sniff":
                    invalidate_asset_caches()
                    invalidate_percentage_cache()
                    summary.value = str(event.get("message"))
                    append_log(str(event.get("message")))
                elif kind == "done":
                    invalidate_percentage_cache()
                    refresh_subject_filter()
                    summary.value = t("done", counts=event.get("counts"))
                    download_started_at["value"] = None
                    set_download_running(False)
                    worker = None
                elif kind == "error":
                    summary.value = t("error", message=event.get("message"))
                    append_log(str(event.get("message")))
                    download_started_at["value"] = None
                    set_download_running(False)
                    worker = None
            if changed:
                page.update()
            if worker is not None:
                page.run_task(_sleep_and_poll)

        async def _sleep_and_poll() -> None:
            import asyncio

            await asyncio.sleep(0.3)
            poll_events()

        async def _deferred_initial_refresh() -> None:
            import asyncio

            await asyncio.sleep(0.1)
            refresh_download_scope()

        def run_download() -> None:
            try:
                subjects = selected_subject_codes()
                start, end = selected_year_range()
                if availability_check.value and sniff_check.value:
                    sniff_subjects = subjects
                    events.put({"kind": "sniff", "message": t("sniffing", subjects=", ".join(sorted(sniff_subjects)), start_year=start, end_year=end)})
                    result = ensure_subject_availability(
                        sniff_subjects,
                        start_year=start,
                        end_year=end,
                        availability_dir=project_path(availability_path.value),
                        force=bool(sniff_check.value),
                        delay_seconds=float(delay.value),
                        workers=max(1, int(workers.value)),
                    )
                    events.put(
                        {
                            "kind": "sniff",
                            "message": t(
                                "sniff_done",
                                subjects=", ".join(result.get("sniffed_subjects", [])),
                                failures=result.get("failed_queries", 0),
                            ),
                        }
                    )
                    invalidate_asset_caches()
                    invalidate_percentage_cache()
                assets = selected_assets()

                def progress_callback(event: dict[str, object]) -> None:
                    if event.get("status") == "skipped":
                        counts = event.get("counts", {})
                        skipped = int(counts.get("skipped", 0) or 0) if isinstance(counts, dict) else 0
                        if int(event.get("index", 0) or 0) != int(event.get("total", 0) or 0) and skipped % 100 != 0:
                            return
                    events.put({"kind": "progress", **event})

                counts = crawl_assets(
                    assets,
                    project_path(raw_root.value),
                    project_path(report_path.value),
                    delay_seconds=float(delay.value),
                    resume=bool(resume_check.value),
                    max_workers=int(workers.value),
                    progress=progress_callback,
                    should_stop=stop_requested.is_set,
                    skipped_progress_interval=100,
                )
                events.put({"kind": "done", "counts": counts})
            except Exception as exc:
                events.put({"kind": "error", "message": str(exc)})

        def start_download(_: object) -> None:
            nonlocal worker
            if worker is not None:
                return
            stop_requested.clear()
            log_view.controls.clear()
            download_started_at["value"] = time.monotonic()
            set_download_running(True)
            progress.value = 0
            summary.value = t("starting")
            worker = threading.Thread(target=run_download, daemon=True)
            worker.start()
            page.update()
            poll_events()

        def stop_download(_: object) -> None:
            stop_requested.set()
            stop_button.disabled = True
            stop_button.text = t("stopping")
            summary.value = t("stop_requested")
            page.update()

        def apply_theme(_: object | None = None) -> None:
            value = theme_mode.value or "system"
            page.theme_mode = {
                "light": ft.ThemeMode.LIGHT,
                "dark": ft.ThemeMode.DARK,
            }.get(value, ft.ThemeMode.SYSTEM)
            save_gui_settings({"theme_mode": value})
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
            manifest_path.label = t("manifest")
            availability_path.label = t("availability_index")
            raw_root.label = t("raw_root")
            report_path.label = t("report")
            start_year.label = t("start_year")
            end_year.label = t("end_year")
            delay.label = t("delay")
            workers.label = t("workers")
            limit.label = t("limit")
            resume_check.label = t("resume")
            availability_check.label = t("use_availability")
            sniff_check.label = t("sniff")
            paths_title.value = t("paths")
            filters_title.value = t("filters")
            run_title.value = t("run")
            output_title.value = t("output")
            subjects_title.value = t("subjects")
            subject_search.label = t("subject_search")
            select_all_button.text = t("select_all")
            clear_all_button.text = t("clear_all")
            reload_subjects_button.text = t("reload_subjects")
            start_button.text = t("downloading") if worker is not None else t("start_download")
            start_button.tooltip = t("start_download")
            stop_button.text = t("stopping") if stop_requested.is_set() else t("stop_after_current")
            stop_button.tooltip = t("stop_after_current")
            if worker is None and progress.value == 0:
                summary.value = t("ready")
            refresh_subject_filter()
            refresh_count()

        start_button.on_click = start_download
        stop_button.on_click = stop_download
        language.on_select = apply_language
        theme_mode.on_change = apply_theme
        select_all_button.on_click = lambda _: set_all_subjects(True)
        clear_all_button.on_click = lambda _: set_all_subjects(False)
        reload_subjects_button.on_click = reload_subjects
        subject_search.on_change = refresh_subject_filter
        for control in [
            delay,
            workers,
            limit,
            availability_check,
            sniff_check,
        ]:
            control.on_change = refresh_count
        for control in [availability_path, raw_root, start_year, end_year, qp_check, ms_check]:
            control.on_change = refresh_download_scope

        rebuild_subject_checks(keep_selection=False)
        page.add(
            ft.Column(
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
                                    ft.Row(
                                        [subjects_title, subject_count],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    subject_search,
                                    ft.Row([select_all_button, clear_all_button, reload_subjects_button], spacing=4),
                                    ft.Container(
                                        subject_list,
                                        expand=True,
                                        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                                        border_radius=PANEL_RADIUS,
                                        padding=6,
                                    ),
                                ],
                                width=360,
                                expand=False,
                            ),
                            scrollable_panel(
                                [
                                    paths_title,
                                    ft.Row([manifest_path], spacing=12),
                                    ft.Row([availability_path], spacing=12),
                                    ft.Row([raw_root, report_path], spacing=12),
                                    ft.Divider(height=1),
                                    filters_title,
                                    ft.Row([start_year, end_year, delay, workers, limit], spacing=12, wrap=True),
                                    ft.Row([qp_check, ms_check, resume_check, availability_check, sniff_check], spacing=12, wrap=True),
                                    ft.Divider(height=1),
                                    run_title,
                                    ft.Row(
                                        [start_button, stop_button, asset_count],
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
                    panel(
                        [
                            output_title,
                            progress,
                            summary,
                            ft.Container(
                                log_view,
                                expand=True,
                                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                                border_radius=PANEL_RADIUS,
                                padding=8,
                            ),
                        ],
                        height=250,
                    ),
                ],
                expand=True,
                spacing=12,
            )
        )
        page.run_task(_deferred_initial_refresh)

    ft.app(target=app)


if __name__ == "__main__":
    main()

