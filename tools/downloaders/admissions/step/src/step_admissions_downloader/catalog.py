from __future__ import annotations

import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urljoin, urlparse, urlsplit, urlunsplit

from step_admissions_downloader.models import StepAsset


DEFAULT_ARCHIVE_URL = "https://www.physicsandmathstutor.com/admissions/step/"
PAPER_RE = re.compile(r"^(?P<year>\d{4})\s+STEP\s+(?P<paper>[123])(?:\s+-[^.]*)?\.pdf$", re.IGNORECASE)
ANSWER_RE = re.compile(r"^(?P<year>\d{4})\s+STEP\s+(?P<paper>[123])\s+.*\.pdf$", re.IGNORECASE)
BUNDLED_ANSWER_RE = re.compile(
    r"^(?P<year>\d{4})\s+(?:Hints\s+and\s+Answers|Solutions?|Mark\s+Scheme)\.pdf$",
    re.IGNORECASE,
)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None
            self._text = []


def parse_archive_html(html: str, page_url: str = DEFAULT_ARCHIVE_URL) -> list[StepAsset]:
    parser = _LinkParser()
    parser.feed(html)
    assets: dict[tuple[int, int, str], tuple[int, StepAsset]] = {}
    for href, label in parser.links:
        source_url = _browser_safe_url(urljoin(page_url, href))
        path = unquote(urlparse(source_url).path)
        filename = path.rsplit("/", 1)[-1]
        if "/STEP/Papers/" in path and "specimen" not in filename.lower():
            match = PAPER_RE.fullmatch(filename)
            document_type = "qp"
            priority = 1
        elif "/STEP/Solutions-and-Reports/" in path:
            match = ANSWER_RE.fullmatch(filename)
            combined_text = f"{filename} {label}".lower()
            priority = _answer_priority(combined_text)
            if not priority:
                continue
            document_type = "ms"
            bundled_match = BUNDLED_ANSWER_RE.fullmatch(filename)
            if not match and bundled_match:
                for paper in (1, 2, 3):
                    asset = StepAsset(
                        year=int(bundled_match.group("year")),
                        paper=paper,
                        document_type=document_type,
                        source_url=source_url,
                        contains_papers=(1, 2, 3),
                    )
                    _select_asset(assets, asset, priority)
                continue
        else:
            continue
        if not match:
            continue
        asset = StepAsset(
            year=int(match.group("year")),
            paper=int(match.group("paper")),
            document_type=document_type,
            source_url=source_url,
        )
        _select_asset(assets, asset, priority)
    return sorted(item[1] for item in assets.values())


def _answer_priority(text: str) -> int:
    if "solution" in text:
        return 3
    if "mark scheme" in text:
        return 2
    if "hints and answers" in text:
        return 1
    return 0


def _select_asset(
    assets: dict[tuple[int, int, str], tuple[int, StepAsset]],
    asset: StepAsset,
    priority: int,
) -> None:
    key = (asset.year, asset.paper, asset.document_type)
    if key not in assets or priority > assets[key][0]:
        assets[key] = (priority, asset)


def _browser_safe_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, quote(unquote(parts.path), safe="/:@"), parts.query, parts.fragment))


def discover_assets(archive_url: str = DEFAULT_ARCHIVE_URL, *, timeout_seconds: float = 30.0) -> list[StepAsset]:
    request = urllib.request.Request(archive_url, headers={"User-Agent": "Oh-My-Exam/0.1"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")
    assets = parse_archive_html(html, archive_url)
    if not assets:
        raise RuntimeError("PMT archive contained no recognized STEP PDFs")
    return assets
