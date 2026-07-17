# STEP Admissions Archive Downloader And Splitter

## Scope

STEP 1, STEP 2, and STEP 3 historic papers linked from Physics & Maths Tutor
(PMT), plus solution or mark-scheme PDFs that can be assigned to one paper
without guessing.

## Source And Catalog Rules

- Exam-board key: `ocr` (Oxford, Cambridge and RSA). OCR has run STEP since the
  June 2024 series; the project uses the current operator as the stable subject
  grouping for the historic archive.
- Operator reference: `https://www.ocr.org.uk/students/step-mathematics/`.
- Archive page: `https://www.physicsandmathstutor.com/admissions/step/`.
- The catalog is parsed on every run; PDF URLs are not hard-coded.
- Downloads must match the HTTP content length and contain a complete PDF
  trailer. Truncated files are discarded and retried instead of being cached.
- Regular papers from both the current and old-format sections are included.
- Specimen papers are excluded because they collide with the same year/paper
  identity as the live paper.
- A worked solution is preferred over a mark scheme or hints-and-answers file.
  Examiner reports without a solution or mark scheme are excluded.
- Older answer bundles that combine STEP 1/2/3 are cataloged once per paper.
  The downloader reuses the first local copy, and the splitter selects the
  matching internal STEP I/II/III question sequence and stops at the next one.

PMT is a third-party archive, not the exam board. Raw metadata records
`source_provider: pmt`; every raw asset and crop region retains its exact PMT
URL and SHA-256 checksum for audit and later replacement by an official source.

## Commands

```powershell
tools\.venv\Scripts\python tools\downloaders\admissions\step\step_admissions_downloader_cli.py
tools\.venv\Scripts\python tools\splitters\admissions\step\step_admissions_splitter_cli.py
tools\.venv\Scripts\python tools\packers\packer_cli.py --metadata-root data\processed_questions --output-dir data\databases\admissions\ocr --exam-board ocr --qualification admissions --course-code step
```

Both STEP commands support repeatable `--paper 1`, `--paper 2`, or `--paper 3`,
`--document-type qp|ms`, year bounds, and `--limit`. The downloader also
supports `--list-only` for a catalog audit without downloading PDFs.

## Layout

```text
data/raw_papers/ocr/admissions/step/{year}/archive/step_{year}_s{paper}_{qp|ms}.pdf
data/processed_questions/ocr/admissions/step/{year}/archive/s{paper}/{qp|ms}/
data/databases/admissions/ocr/ocr_admissions_step.sqlite
```

Processed JPEG and JSON names use
`step_{year}_s{paper}_{qp|ms}_q{number}`. This is compatible with the existing
admissions metadata contract and produces `ocr_admissions_step.sqlite` through
the metadata packer.

## Cutting And Validation

- Searchable PDFs use printed question headings and their PDF geometry.
- Scanned historic PDFs use RapidOCR with ONNX Runtime for heading geometry and
  question text. Both are Python dependencies installed inside the project
  virtual environment; no system OCR program or PATH change is required.
- When ONNX Runtime exposes `CUDAExecutionProvider`, the splitter uses it before
  `CPUExecutionProvider`; a missing or unusable CUDA runtime automatically falls
  back to CPU. The default dependency is CPU-only. A local GPU environment may
  replace `onnxruntime` with `onnxruntime-gpu[cuda,cudnn]` without installing a
  system-wide CUDA Toolkit.
- The accepted question sequence must start at 1 and remain contiguous.
- When the front page declares a question count, the detected count must match.
- Multi-page questions retain ordered crop regions; blank pages are skipped.
- QP sidecars contain searchable content. MS sidecars deliberately do not copy
  solution text into the question content field.
- Untrusted papers fail and are recorded in
  `data/reports/step_admissions_split.jsonl`; partial output is never reported as
  success.

Before a bulk import, visually inspect at least one scanned old-format paper,
one searchable pre-2020 paper, one remote-delivery 2020 paper, one worked
solution, and one combined examiner-report/mark-scheme document.
