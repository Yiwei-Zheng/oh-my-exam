# CIE A-Level Downloader Source

This `src/` folder contains the standalone `cie_alevel_downloader` package.

The downloader does not import the splitter or the removed `tools/exam_pipeline` package. It owns CIE manifest parsing, Cambridge catalog sync, Frank availability discovery, polite PDF downloading, raw layout migration, and downloader GUI/CLI code.
