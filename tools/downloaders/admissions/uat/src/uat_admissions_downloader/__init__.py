"""UAT-UK admissions archive downloader."""

from uat_admissions_downloader.catalog import DEFAULT_ARCHIVE_URL, discover_assets
from uat_admissions_downloader.download import download_assets
from uat_admissions_downloader.models import ArchiveAsset

__all__ = ["ArchiveAsset", "DEFAULT_ARCHIVE_URL", "discover_assets", "download_assets"]
