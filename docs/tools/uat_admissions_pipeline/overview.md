# UAT Admissions Archive Downloader And Splitter

## Scope

Official historic ENGAA and NSAA Section 1 papers linked from the UAT-UK ESAT
preparation page.

## Source

- Archive page: `https://esat-tmua.ac.uk/esat-preparation-materials/`
- The downloader parses the current archive page and follows recognized
  `ENGAA_*_S1_QuestionPaper.pdf`, `ENGAA_*_S1_AnswerKey.pdf`,
  `NSAA_*_S1_QuestionPaper.pdf`, and `NSAA_*_S1_AnswerKey.pdf` links.
- Upstream PDF URLs are not hard-coded, so a moved S3 object is picked up from
  the official page on the next run.

## Tool Boundaries

- Downloader: `tools/downloaders/admissions/uat/`.
- Splitter: `tools/splitters/admissions/uat/`.
- The downloader writes raw PDFs and adjacent source metadata only.
- The splitter consumes those public files and does not import downloader code.

## Commands

```powershell
.venv\Scripts\python tools\downloaders\admissions\uat\uat_admissions_downloader_cli.py
.venv\Scripts\python tools\splitters\admissions\uat\uat_admissions_splitter_cli.py
```

Use repeatable `--exam engaa` or `--exam nsaa`, plus `--start-year` and
`--end-year`, to limit either command. `--list-only` lets the downloader audit
the current official catalog without downloading PDFs.

## Raw Layout

```text
data/raw_papers/uat/admissions/{engaa|nsaa}/{year}/archive/{exam}_{year}_s1_{qp|ms}.pdf
```

Each PDF has an adjacent JSON file containing the official source URL and
SHA-256 checksum.

## Processed Layout

```text
data/processed_questions/uat/admissions/{engaa|nsaa}/{year}/archive/s1/{qp|ms}/
```

Each leaf output contains a grayscale JPEG and JSON sidecar. Sidecar fields
match the stable splitter format documented for CIE A-Level:

- QP: `question_number`, `content`, `source_stem`, `page_start`, `page_end`,
  `document_type`, `cutter`, `content_source`, and `crop_regions`, with optional
  `content_warning`.
- MS/answer key: the same identity, page, cutter, and crop fields, without the
  QP-only content fields.
- Every crop region records the official source URL, source checksum, page
  geometry, PyMuPDF coordinates, render DPI, and join gap.

## Cutting Rules

- QP boundaries come from the stable printed question-number column, not OCR.
- The complete detected sequence must begin at 1 and be contiguous; an
  untrusted paper fails instead of producing partial output.
- Blank pages and part-divider templates between questions are excluded.
- Multi-page questions retain ordered crop regions and can be replayed from the
  original PDF.
- Answer keys are split from explicit numeric or `Q`-prefixed row labels paired
  with A-H answer cells. The row sequence must also be complete.
- QP searchable content uses PDF text first and optional OCR fallback when the
  text is empty or visibly damaged.

## Validation

- Compare QP and answer-key counts for the same exam and year.
- Check contiguous question identities and exact QP/MS sidecar field sets.
- Visually inspect old and current layouts, formulas, diagrams, two-question
  pages, section transitions, and two-column answer keys.
- Review `data/reports/uat_admissions_download.jsonl` and
  `data/reports/uat_admissions_split.jsonl`; failures never count as success.
