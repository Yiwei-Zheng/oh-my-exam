from __future__ import annotations

import re
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from oh_my_exam.pipelines.adapters.uat.downloader.models import ArchiveAsset


DEFAULT_ARCHIVE_URLS = (
    "https://esat-tmua.ac.uk/esat-preparation-materials/",
    "https://esat-tmua.ac.uk/tmua-preparation-materials/",
)
DEFAULT_ARCHIVE_URL = DEFAULT_ARCHIVE_URLS[0]
ESAT_ASSET_RE = re.compile(
    r"(?P<exam>ENGAA|NSAA)_(?P<year>20\d{2})_S1_(?P<kind>QuestionPaper|AnswerKey)\.pdf(?:[?#].*)?$",
    re.IGNORECASE,
)
TMUA_ASSET_RE = re.compile(
    r"TMUA-(?P<period>20\d{2}|early-specimen)-"
    r"(?:(?:paper-(?P<paper>[12])(?P<worked>-worked-answers)?)|(?P<keys>answer-keys|paper-answer-keys))"
    r"\.pdf(?:[?#].*)?$",
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
    assets: dict[tuple[str, int | None, str, str], ArchiveAsset] = {}
    for href in parser.links:
        absolute_url = urljoin(page_url, href)
        filename = urlparse(absolute_url).path.rsplit("/", 1)[-1]
        esat_match = ESAT_ASSET_RE.fullmatch(filename)
        if esat_match:
            document_type = "qp" if esat_match.group("kind").lower() == "questionpaper" else "ms"
            asset = ArchiveAsset(
                exam=esat_match.group("exam").lower(),
                year=int(esat_match.group("year")),
                document_type=document_type,
                source_url=absolute_url,
            )
            assets[(asset.exam, asset.year, asset.component, asset.document_type)] = asset
            continue

        tmua_match = TMUA_ASSET_RE.fullmatch(filename)
        if not tmua_match:
            continue
        period = tmua_match.group("period").lower()
        paper = tmua_match.group("paper")
        asset = ArchiveAsset(
            exam="tmua",
            year=int(period) if period.isdigit() else None,
            document_type="ms" if tmua_match.group("keys") else ("worked_answers" if tmua_match.group("worked") else "qp"),
            source_url=absolute_url,
            component=f"p{paper}" if paper else "",
            edition="early_specimen" if period == "early-specimen" else "archive",
        )
        assets[(asset.exam, asset.year, asset.component, asset.document_type)] = asset
    return sorted(
        assets.values(),
        key=lambda asset: (asset.exam, asset.year is None, asset.year or 0, asset.component, asset.document_type),
    )


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
