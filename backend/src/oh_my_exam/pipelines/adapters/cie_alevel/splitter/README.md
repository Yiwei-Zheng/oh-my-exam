# CIE A-Level Splitter Source

This `src/` folder contains the standalone `cie_alevel_splitter` package.

The splitter does not import the downloader or the removed `tools/exam_pipeline` package. It owns local raw corpus discovery, PDF splitting, subject-specific cutters, SQLite ingestion, and splitter GUI/CLI code.
