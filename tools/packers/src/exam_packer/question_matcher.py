from __future__ import annotations

from collections import defaultdict

from exam_packer.models import MatchResult, MetadataRecord


def match_metadata_records(records: list[MetadataRecord]) -> MatchResult:
    by_question: dict[str, dict[str, list[MetadataRecord]]] = defaultdict(lambda: {"QP": [], "MS": []})
    for record in records:
        by_question[record.question_key][record.source_type].append(record)

    warnings: list[str] = []
    matched_pairs = only_qp = only_ms = duplicate_qp = duplicate_ms = ambiguous_match = 0
    selected: list[MetadataRecord] = []
    for key, group in sorted(by_question.items()):
        qp = sorted(group["QP"], key=lambda item: str(item.metadata_path))
        ms = sorted(group["MS"], key=lambda item: str(item.metadata_path))
        if len(qp) == 1 and len(ms) == 1:
            matched_pairs += 1
        elif qp and not ms:
            only_qp += 1
        elif ms and not qp:
            only_ms += 1
        if len(qp) > 1:
            duplicate_qp += 1
            warnings.append(f"{key}: duplicate QP metadata; first path retained in question source columns")
        if len(ms) > 1:
            duplicate_ms += 1
            warnings.append(f"{key}: duplicate MS metadata; first path retained in question source columns")
        if len(qp) > 1 and len(ms) > 1:
            ambiguous_match += 1
            warnings.append(f"{key}: ambiguous QP/MS match because both sides have duplicates")
        selected.extend(qp[:1])
        selected.extend(ms[:1])

    return MatchResult(
        records=selected,
        warnings=warnings,
        matched_pairs=matched_pairs,
        only_qp=only_qp,
        only_ms=only_ms,
        duplicate_qp=duplicate_qp,
        duplicate_ms=duplicate_ms,
        ambiguous_match=ambiguous_match,
    )
