"""UAT-UK admissions paper geometry splitter."""

from oh_my_exam.pipelines.adapters.uat.splitter.cutter import SplitOptions, split_asset
from oh_my_exam.pipelines.adapters.uat.splitter.pipeline import split_downloaded

__all__ = ["SplitOptions", "split_asset", "split_downloaded"]
