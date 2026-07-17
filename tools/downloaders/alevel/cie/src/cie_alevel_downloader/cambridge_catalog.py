from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse


CAMBRIDGE_A_LEVEL_SUBJECTS_URL = (
    "https://www.cambridgeinternational.org/programmes-and-qualifications/"
    "cambridge-advanced/cambridge-international-as-and-a-levels/subjects/"
)


@dataclass(frozen=True)
class CambridgeSubject:
    code: str
    name: str
    url: str
    qualification_notes: str
    source: str
    syllabus_pdfs: list[dict[str, object]]


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        self._href = attrs_dict.get("href")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return
        text = " ".join(part.strip() for part in self._text if part.strip())
        if text:
            self.links.append((self._href, html.unescape(text)))
        self._href = None
        self._text = []


def fetch_text(url: str, *, timeout_seconds: float = 45.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Oh-My-Exam/0.1"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_subjects(subjects_html: str, *, source_url: str = CAMBRIDGE_A_LEVEL_SUBJECTS_URL) -> list[CambridgeSubject]:
    parser = LinkParser()
    parser.feed(subjects_html)
    subjects: dict[str, CambridgeSubject] = {}
    for href, text in parser.links:
        absolute_url = urljoin(source_url, href)
        parsed = urlparse(absolute_url)
        if not (
            parsed.path.startswith("/programmes-and-qualifications/cambridge-international-as-and-a-level-")
            or parsed.path.startswith("/programmes-and-qualifications/cambridge-international-as-level-")
            or parsed.path.startswith("/programmes-and-qualifications/cambridge-international-a-level-")
        ):
            continue
        if parsed.path.rstrip("/").endswith("cambridge-international-as-and-a-levels"):
            continue
        if parsed.path.rstrip("/").endswith("cambridge-international-as-and-a-levels/subjects"):
            continue
        subject = parse_subject_link_text(text, absolute_url, source_url)
        if subject is not None:
            subjects.setdefault(subject.code, subject)
    return sorted(subjects.values(), key=lambda item: (item.name.lower(), item.code))


def parse_subject_link_text(text: str, url: str, source_url: str) -> CambridgeSubject | None:
    cleaned = re.sub(r"\s+", " ", text).strip()
    matches = list(re.finditer(r"(?<!\d)(\d{4})(?!\d)", cleaned))
    if not matches:
        return None
    match = matches[-1]
    code = match.group(1)
    trailing = cleaned[match.end() :].strip(" -()–")
    name = f"{cleaned[: match.start()]}{cleaned[match.end() :]}"
    name = re.sub(r"\((?:AS Level only|AS only|A Level only)\)", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\bNew\b", "", name)
    name = re.sub(r"\s+", " ", name).strip(" -()–")
    notes_parts = []
    if "AS Level only" in cleaned or "AS only" in cleaned:
        notes_parts.append("AS Level only")
    if "A Level only" in cleaned:
        notes_parts.append("A Level only")
    if "New" in trailing:
        notes_parts.append("New")
    return CambridgeSubject(
        code=code,
        name=name,
        url=url,
        qualification_notes=", ".join(dict.fromkeys(notes_parts)),
        source=source_url,
        syllabus_pdfs=[],
    )


def parse_syllabus_pdf_links(subject_html: str, *, page_url: str) -> list[dict[str, object]]:
    parser = LinkParser()
    parser.feed(subject_html)
    pdfs: list[dict[str, object]] = []
    for href, text in parser.links:
        if "Syllabus" not in text or ".pdf" not in href.lower():
            continue
        years = [int(value) for value in re.findall(r"20\d{2}", text)]
        pdfs.append(
            {
                "title": re.sub(r"\s+", " ", text).strip(),
                "url": urljoin(page_url, href),
                "valid_from": min(years) if years else None,
                "valid_to": max(years) if years else None,
            }
        )
    return pdfs


def build_subject_rules(subjects: list[CambridgeSubject], *, start_year: int = 2002, end_year: int = 2025) -> dict[str, object]:
    return {
        "qualification": "a_level",
        "session_range": {"start_year": start_year, "end_year": end_year, "seasons": ["m", "s", "w"]},
        "document_types": ["qp", "ms"],
        "source": CAMBRIDGE_A_LEVEL_SUBJECTS_URL,
        "subjects": [
            {
                "code": subject.code,
                "name": subject.name,
                "source_url": subject.url,
                "qualification_notes": subject.qualification_notes,
                "syllabus_pdfs": subject.syllabus_pdfs,
                "component_rules": component_rules_for_subject(subject),
            }
            for subject in subjects
        ],
    }


def component_rules_for_subject(subject: CambridgeSubject) -> list[dict[str, object]]:
    rules = default_component_rules(subject)
    syllabus_start_years = [
        int(pdf["valid_from"])
        for pdf in subject.syllabus_pdfs
        if isinstance(pdf.get("valid_from"), int)
    ]
    if "New" not in subject.qualification_notes or not syllabus_start_years:
        return rules

    first_syllabus_year = min(syllabus_start_years)
    bounded_rules: list[dict[str, object]] = []
    for rule in rules:
        bounded = dict(rule)
        valid_from = bounded.get("valid_from")
        bounded["valid_from"] = first_syllabus_year if valid_from is None else max(int(valid_from), first_syllabus_year)
        bounded_rules.append(bounded)
    return bounded_rules


def default_component_rules(subject: CambridgeSubject) -> list[dict[str, object]]:
    code = subject.code
    common_modern = ["11", "12", "13", "21", "22", "23", "31", "32", "33", "41", "42", "43"]
    science_modern = common_modern + ["51", "52", "53"]
    single_digit = ["1", "2", "3", "4", "5", "6", "7"]
    legacy_9709_double = [
        "11",
        "12",
        "13",
        "21",
        "22",
        "23",
        "31",
        "32",
        "33",
        "41",
        "42",
        "43",
        "51",
        "52",
        "53",
        "61",
        "62",
        "63",
        "71",
        "72",
        "73",
    ]

    if code == "9709":
        return [
            {
                "valid_from": 2002,
                "valid_to": 2009,
                "components": single_digit,
                "source": "Observed early Cambridge/Frank 9709 single-digit naming.",
            },
            {"valid_from": 2010, "valid_to": 2019, "components": legacy_9709_double, "source": "Legacy 9709 double-digit paper/variant candidates."},
            {"valid_from": 2020, "valid_to": None, "components": ["11", "12", "13", "31", "32", "33", "41", "42", "43", "51", "52", "53"], "source": "Modern 9709 component candidates."},
        ]
    if code in {"9700", "9701", "9702"}:
        return [{"valid_from": 2002, "valid_to": None, "components": science_modern, "source": "Science practical/written component candidates; refine per syllabus."}]
    if code == "9231":
        return [
            {"valid_from": 2002, "valid_to": 2019, "components": ["1", "2", "3", "4"], "source": "Legacy Further Mathematics candidates; refine per syllabus."},
            {"valid_from": 2020, "valid_to": None, "components": common_modern, "source": "Modern Further Mathematics candidates."},
        ]
    if "AS Level only" in subject.qualification_notes:
        return [{"valid_from": 2002, "valid_to": None, "components": ["1", "2", "11", "12", "13", "21", "22", "23"], "source": "Generic AS-only candidates; refine per syllabus."}]
    if "A Level only" in subject.qualification_notes:
        return [{"valid_from": 2002, "valid_to": None, "components": single_digit + common_modern, "source": "Generic A-only candidates; refine per syllabus."}]
    return [{"valid_from": 2002, "valid_to": None, "components": single_digit + common_modern, "source": "Generic AS/A candidates; refine per syllabus."}]


def sync_catalog(output_dir: Path, *, fetch_overview: bool = True, delay_seconds: float = 0.5) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    subjects_html = fetch_text(CAMBRIDGE_A_LEVEL_SUBJECTS_URL)
    subjects = parse_subjects(subjects_html)
    enriched: list[CambridgeSubject] = []
    for subject in subjects:
        syllabus_pdfs: list[dict[str, object]] = []
        if fetch_overview:
            try:
                syllabus_pdfs = parse_syllabus_pdf_links(fetch_text(subject.url), page_url=subject.url)
                time.sleep(delay_seconds)
            except OSError:
                syllabus_pdfs = []
        enriched.append(CambridgeSubject(**(asdict(subject) | {"syllabus_pdfs": syllabus_pdfs})))

    subjects_path = output_dir / "cie_a_level_subjects_official.json"
    rules_path = output_dir / "cie_a_level_subject_rules.json"
    subjects_path.write_text(json.dumps([asdict(subject) for subject in enriched], ensure_ascii=False, indent=2), encoding="utf-8")
    rules_path.write_text(json.dumps(build_subject_rules(enriched), ensure_ascii=False, indent=2), encoding="utf-8")
    return subjects_path, rules_path

