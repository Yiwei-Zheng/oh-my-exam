from __future__ import annotations

import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from uat_admissions_downloader.models import ArchiveAsset


DEFAULT_ARCHIVE_URL = "https://esat-tmua.ac.uk/esat-preparation-materials/"
ASSET_RE = re.compile(
    r"(?P<exam>ENGAA|NSAA)_(?P<year>20\d{2})_S1_(?P<kind>QuestionPaper|AnswerKey)\.pdf(?:[?#].*)?$",
    re.IGNORECASE,
)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def parse_archive_html(html: str, page_url: str = DEFAULT_ARCHIVE_URL) -> list[ArchiveAsset]:
    parser = _LinkParser()
    parser.feed(html)
    assets: dict[tuple[str, int, str], ArchiveAsset] = {}
    for href in parser.links:
        absolute_url = urljoin(page_url, href)
        filename = urlparse(absolute_url).path.rsplit("/", 1)[-1]
        match = ASSET_RE.fullmatch(filename)
        if not match:
            continue
        document_type = "qp" if match.group("kind").lower() == "questionpaper" else "ms"
        asset = ArchiveAsset(
            exam=match.group("exam").lower(),
            year=int(match.group("year")),
            document_type=document_type,
            source_url=absolute_url,
        )
        assets[(asset.exam, asset.year, asset.document_type)] = asset
    return sorted(assets.values())


def discover_assets(
    archive_url: str = DEFAULT_ARCHIVE_URL,
    *,
    timeout_seconds: float = 30.0,
) -> list[ArchiveAsset]:
    request = urllib.request.Request(archive_url, headers={"User-Agent": "Oh-My-Exam/0.1"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")
    assets = parse_archive_html(html, archive_url)
    if not assets:
        raise RuntimeError("official archive contained no recognized ENGAA/NSAA PDF links")
    return assets
