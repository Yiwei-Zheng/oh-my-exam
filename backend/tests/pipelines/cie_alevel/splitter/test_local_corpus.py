from __future__ import annotations

import json
from pathlib import Path

from oh_my_exam.pipelines.adapters.cie_alevel.splitter.local_corpus import (
    discover_installed_paper_sets,
)


def test_discovery_ignores_other_exam_metadata(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw_papers"
    cie_dir = raw_root / "cie" / "a_level" / "9709" / "2025" / "s25"
    cie_dir.mkdir(parents=True)
    metadata = {
        "exam_board": "cie",
        "qualification": "a_level",
        "subject_code": "9709",
        "subject_name": "Mathematics",
        "session": "s25",
        "document_type": "qp",
        "component": "11",
    }
    (cie_dir / "9709_s25_qp_11.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    (cie_dir / "9709_s25_qp_11.pdf").write_bytes(b"pdf")

    other_dir = raw_root / "ocr" / "admissions" / "step" / "2025" / "archive"
    other_dir.mkdir(parents=True)
    (other_dir / "step_2025_s1_qp.json").write_text(
        json.dumps(metadata | {
            "exam_board": "ocr",
            "qualification": "admissions",
            "subject_code": "step",
            "session": "archive",
        }),
        encoding="utf-8",
    )

    paper_sets = discover_installed_paper_sets(raw_root)

    assert len(paper_sets) == 1
    assert paper_sets[0].key == "cie/a_level/9709/2025/s25/11"
