# Global Question Catalog

## Scope

The normalized local SQLite catalog built at
`data/databases/global_exam_catalog.sqlite`. It is the local source of truth for
server-owned papers, questions, answers, matching features, and similarity data.

## Build

```powershell
.venv\Scripts\python tools\packers\global_catalog_cli.py --overwrite --strip-legacy-urls --extract-answer-text
```

The command imports every per-subject SQLite database under `data/databases/`,
resolves its paper stems against PDFs under `data/raw_papers/`, validates foreign
keys and SQLite integrity, and atomically replaces the global catalog. It does
not call an AI model.

## Identity And Documents

- Integer primary keys are local relational identifiers.
- `papers.stable_key` and `questions.stable_key` remain deterministic across
  rebuilds.
- `paper_documents.storage_key` is a path relative to `data/raw_papers/`.
- Catalog databases do not store a remote URL, absolute filesystem path,
  checksum, copyright record, or source-audit record.
- Existing question and paper API routes resolve internal ids to storage keys;
  clients never supply or receive a storage key.

## Normalized Tables

Catalog hierarchy:

- `exam_boards`
- `qualifications`
- `exam_programs`
- `papers`
- `paper_documents`

Question and answer content:

- `questions`
- `question_relations`
- `question_texts`
- `question_regions`
- `answers`
- `answer_regions`
- `answer_versions`
- `marking_points`

Cross-exam matching:

- `features`
- `feature_labels`
- `question_features`
- `syllabuses`
- `syllabus_topics`
- `syllabus_topic_features`
- `embedding_models`
- `question_embeddings`
- `similarity_algorithms`
- `question_similarities`

`answers` created from legacy answer crops start as `source_only`. A later
extractor may add Markdown in `answer_versions` and normalized rubric rows in
`marking_points`; it must not invent missing answer content.

## Runtime Boundary

The backend opens the global catalog read-only. `FileSystemPaperStore` resolves
storage keys beneath `OME_PAPER_ROOT`; a production object-store adapter may use
the same keys. The existing API remains:

```text
GET /api/v1/exams/{exam_id}/questions/{question_id}/question.pdf
GET /api/v1/exams/{exam_id}/questions/{question_id}/answer.pdf
GET /api/v1/exams/{exam_id}/papers/{paper_id}/{question|answer}
```
