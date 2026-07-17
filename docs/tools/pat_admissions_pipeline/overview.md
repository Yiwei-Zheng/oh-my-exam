# PAT Admissions Archive Downloader And Splitter

## Scope

Oxford Physics Aptitude Test (PAT) papers and model solutions linked from
Physics & Maths Tutor (PMT), including the separately identified specimen
papers.

## Source And Identity

- Exam-board key: `pearson_vue` (Pearson VUE). This is the stable project
  grouping for PAT; it is independent from the archive used to obtain PDFs.
- Operator reference: Oxford's 2025 PAT booking guidance used Pearson VUE's
  booking system and test-centre network.
- Archive page: `https://www.physicsandmathstutor.com/admissions/pat/`.
- The downloader parses the current paper links and follows each solution page
  to its embedded PDF. Final PDF URLs are not hard-coded.
- Regular papers use component `s1`; specimen papers use `s2`, so the 2009,
  2015, and 2017 pairs do not overwrite the regular paper from the same year.
- The 2024 specimen is retained because it is the available example of the new
  online multiple-choice format.

PMT is a third-party archive, not the exam board. Raw metadata records
`source_provider: pmt`; raw metadata and every crop region retain the exact PMT
PDF URL and SHA-256 checksum.

## Commands

```powershell
tools\.venv\Scripts\python tools\downloaders\admissions\pat\pat_admissions_downloader_cli.py
tools\.venv\Scripts\python tools\splitters\admissions\pat\pat_admissions_splitter_cli.py
tools\.venv\Scripts\python tools\packers\packer_cli.py --metadata-root data\processed_questions --output-dir data\databases\admissions\pearson_vue --exam-board pearson_vue --qualification admissions --course-code pat
```

Both PAT commands support `--variant regular|specimen`, `--document-type
qp|ms`, year bounds, and `--limit`. The downloader also supports `--list-only`.
The splitter prefers CUDA OCR when ONNX Runtime exposes a working CUDA provider
and falls back to CPU. `--cpu-only` disables GPU initialization.

## Layout

```text
data/raw_papers/pearson_vue/admissions/pat/{year}/{regular|specimen}/pat_{year}_s{1|2}_{qp|ms}.pdf
data/processed_questions/pearson_vue/admissions/pat/{year}/{regular|specimen}/s{1|2}/{qp|ms}/
data/databases/admissions/pearson_vue/pearson_vue_admissions_pat.sqlite
```

## Cutting Rules

- Searchable papers use printed top-level question headings and PDF geometry.
- Scanned solutions and the 2021 browser-print paper use RapidOCR geometry.
- The 2024 specimen has one question per page after its cover and is split by
  that stable layout; OCR supplies searchable QP content.
- The 2006-2007 format contains separate Physics and Mathematics sections whose
  printed numbering restarts at 1. The splitter preserves source order and uses
  one canonical ordinal sequence so QP and solution crops remain uniquely
  pairable.
- Blank working pages are excluded, multi-page questions retain ordered crop
  regions, and an untrusted sequence fails instead of reporting partial output.

Review `data/reports/pat_admissions_download.jsonl` and
`data/reports/pat_admissions_split.jsonl`. Before distribution, compare QP/MS
counts for every paper and visually inspect both legacy sections, a scanned
solution, 2021, and the 2024 online-format specimen.
