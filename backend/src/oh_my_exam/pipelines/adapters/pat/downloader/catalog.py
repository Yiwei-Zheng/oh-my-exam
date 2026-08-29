from __future__ import annotations

import re
import time
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urljoin, urlparse, urlsplit, urlunsplit

from oh_my_exam.pipelines.adapters.pat.downloader.models import PatAsset


DEFAULT_ARCHIVE_URL = "https://www.physicsandmathstutor.com/admissions/pat/"
PAPER_RE = re.compile(r"^PAT\s+(?P<year>\d{4})(?P<specimen>\s+Specimen)?\.pdf$", re.IGNORECASE)
SOLUTION_PAGE_RE = re.compile(r"^/admissions/pat/solutions-(?P<year>\d{4})(?P<specimen>-specimen)?/?$", re.IGNORECASE)


@dataclass(frozen=True, order=True)
class SolutionPage:
    year: int
    variant: str
    page_url: str


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.frames: list[str] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag.lower() == "a":
            self._href = values.get("href")
            self._text = []
        elif tag.lower() in {"iframe", "embed"} and values.get("src"):
            self.frames.append(str(values["src"]))

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None
            self._text = []


def parse_archive_html(html: str, page_url: str = DEFAULT_ARCHIVE_URL) -> tuple[list[PatAsset], list[SolutionPage]]:
    parser = _LinkParser()
    parser.feed(html)
    papers: dict[tuple[int, str], PatAsset] = {}
    solution_pages: dict[tuple[int, str], SolutionPage] = {}
    for href, _label in parser.links:
        absolute_url = _browser_safe_url(urljoin(page_url, href))
        path = unquote(urlparse(absolute_url).path)
        filename = path.rsplit("/", 1)[-1]
        paper_match = PAPER_RE.fullmatch(filename) if "/Admissions/PAT/Papers/" in path else None
        if paper_match:
            variant = "specimen" if paper_match.group("specimen") else "regular"
            asset = PatAsset(int(paper_match.group("year")), variant, "qp", absolute_url)
            papers[(asset.year, asset.variant)] = asset
            continue
        solution_match = SOLUTION_PAGE_RE.fullmatch(urlparse(absolute_url).path)
        if solution_match:
            variant = "specimen" if solution_match.group("specimen") else "regular"
            item = SolutionPage(int(solution_match.group("year")), variant, absolute_url)
            solution_pages[(item.year, item.variant)] = item
    return sorted(papers.values()), sorted(solution_pages.values())


def parse_solution_html(html: str, page: SolutionPage) -> PatAsset:
    parser = _LinkParser()
    parser.feed(html)
    candidates = parser.frames + [href for href, _label in parser.links]
    for candidate in candidates:
        source_url = _browser_safe_url(urljoin(page.page_url, candidate))
        path = unquote(urlparse(source_url).path)
        if "/Admissions/PAT/Solutions/" in path and path.lower().endswith(".pdf"):
            return PatAsset(page.year, page.variant, "ms", source_url)
    raise RuntimeError(f"PAT solution page contained no solution PDF: {page.page_url}")


def discover_assets(archive_url: str = DEFAULT_ARCHIVE_URL, *, timeout_seconds: float = 30.0) -> list[PatAsset]:
    html = _fetch_html(archive_url, timeout_seconds)
    papers, solution_pages = parse_archive_html(html, archive_url)
    solutions = [parse_solution_html(_fetch_html(page.page_url, timeout_seconds), page) for page in solution_pages]
    assets = sorted(papers + solutions)
    if not papers or not solutions:
        raise RuntimeError("PMT archive contained no recognized PAT papers or solutions")
    return assets


def _fetch_html(url: str, timeout_seconds: float) -> str:
    last_error: Exception | None = None
    for attempt in range(3):
        request = urllib.request.Request(url, headers={"User-Agent": "Oh-My-Exam/0.1"})
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def _browser_safe_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, quote(unquote(parts.path), safe="/:@"), parts.query, parts.fragment))
