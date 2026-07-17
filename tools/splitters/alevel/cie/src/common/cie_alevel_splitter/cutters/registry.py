from __future__ import annotations

from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from typing import Callable

from cie_alevel_splitter.models import PaperAsset


@dataclass(frozen=True)
class SubjectCutter:
    name: str
    split_asset_to_images: Callable[[PaperAsset, Path, Path, object], list[dict[str, object]]]
    options_type: type


def get_subject_cutter(exam_board: str, subject_code: str) -> SubjectCutter | None:
    if exam_board != "cie":
        return None
    splitter_root = Path(__file__).resolve().parents[3]
    cutter_path = splitter_root / subject_code / "cutter.py"
    if not cutter_path.exists():
        return None
    spec = spec_from_file_location(f"cie_alevel_subject_{subject_code}_cutter", cutter_path)
    if spec is None or spec.loader is None:
        return None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return SubjectCutter(
        name=str(module.CUTTER_NAME),
        split_asset_to_images=module.split_asset_to_images,
        options_type=module.CutterOptions,
    )
