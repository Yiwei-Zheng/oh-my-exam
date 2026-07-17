from __future__ import annotations

import json
from pathlib import Path

from ome_cie_sources.frank import FRANK_CIE_REDIR_BASE, build_frank_cie_url_from_stem

from cie_alevel_splitter.models import PaperAsset


def build_frank_cie_url(asset: PaperAsset) -> str:
    return build_frank_cie_url_from_stem(asset.stem)


def is_supported_frank_asset(asset: PaperAsset) -> bool:
    # Frank may list combined mark schemes such as ms_1+2+3+4+5+6+7.
    # We intentionally skip those and only download normal per-component QP/MS files.
    if asset.document_type == "ms" and "+" in asset.component:
        return False
    return True


def load_assets(manifest_path: Path) -> list[PaperAsset]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    sessions = _load_sessions(raw)
    assets: list[PaperAsset] = []
    for subject in raw["subjects"]:
        for session in sessions:
            for component in _load_subject_components(subject, session):
                for document_type in raw["document_types"]:
                    asset = PaperAsset(
                        exam_board="cie",
                        qualification=raw["qualification"],
                        subject_code=subject["code"],
                        subject_name=subject["name"],
                        session=session,
                        document_type=document_type,
                        component=component,
                    )
                    if is_supported_frank_asset(asset):
                        assets.append(asset)
    return assets


def _load_subject_components(subject: dict[str, object], session: str) -> list[str]:
    if "components" in subject:
        return [str(component) for component in subject["components"]]

    component_rules = subject.get("component_rules")
    if not isinstance(component_rules, list):
        raise ValueError(f"subject {subject.get('code')} must contain components or component_rules")

    year = _session_year(session)
    components: list[str] = []
    seen: set[str] = set()
    for rule in component_rules:
        if not isinstance(rule, dict):
            continue
        valid_from = rule.get("valid_from")
        valid_to = rule.get("valid_to")
        if valid_from is not None and year < int(valid_from):
            continue
        if valid_to is not None and year > int(valid_to):
            continue
        for component in rule.get("components", []):
            value = str(component)
            if value not in seen:
                seen.add(value)
                components.append(value)
    return components


def _session_year(session: str) -> int:
    match = session[1:]
    if len(match) != 2 or not match.isdigit():
        raise ValueError(f"invalid CIE session: {session}")
    suffix = int(match)
    return 2000 + suffix


def _load_sessions(raw: dict[str, object]) -> list[str]:
    if "sessions" in raw:
        return [str(session) for session in raw["sessions"]]

    session_range = raw.get("session_range")
    if not isinstance(session_range, dict):
        raise ValueError("manifest must contain either sessions or session_range")

    start_year = int(session_range["start_year"])
    end_year = int(session_range["end_year"])
    seasons = [str(season) for season in session_range.get("seasons", ["m", "s", "w"])]
    sessions: list[str] = []
    for year in range(start_year, end_year + 1):
        suffix = f"{year % 100:02d}"
        sessions.extend(f"{season}{suffix}" for season in seasons)
    return sessions

