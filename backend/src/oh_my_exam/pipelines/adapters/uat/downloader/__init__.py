"""UAT-UK admissions archive downloader."""

from oh_my_exam.pipelines.adapters.uat.downloader.catalog import DEFAULT_ARCHIVE_URL, discover_assets
from oh_my_exam.pipelines.adapters.uat.downloader.download import download_assets
from oh_my_exam.pipelines.adapters.uat.downloader.models import ArchiveAsset

__all__ = ["ArchiveAsset", "DEFAULT_ARCHIVE_URL", "discover_assets", "download_assets"]
