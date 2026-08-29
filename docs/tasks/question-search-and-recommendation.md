# Question search and recommendation

## Asset inventory

The active catalog contains 30,168 questions across six programs. Extracted
search text is available for 22,881 questions (75.8%). CIE Mathematics 9709 and
Further Mathematics 9231 account for 27,233 questions. The normalized schema
already contained syllabus, feature, embedding, and similarity tables, but all
of them were empty before this task.

Maintained syllabus PDFs exist for 9231, 9618, and 9702. The matching topic
catalog covers the two subjects currently present in the question database:
9709 and 9231. It records the official 2026-2027 Cambridge syllabus URLs and
uses their section names as canonical tags.

## Matching design

`ome-match-questions` rebuilds managed syllabus tags and the top similar
questions for each question. Component numbers constrain candidate syllabus
sections; extracted question text then selects detailed topics. Similarity is a
sparse TF-IDF cosine score (75%) plus shared-topic Jaccard score (25%). Matches
from the same paper are excluded to avoid recommending adjacent subparts.
Historical Mathematics Paper 7 is mapped to the current Paper 6 Statistics 2
content domain; zero-padded component identifiers are normalized.

Word2Vec is not used. The available corpus is small for training stable domain
word vectors, and OCR-heavy mathematical notation produces noisy tokens. The
chosen approach is deterministic, explainable, has no model download, and can
later be replaced or complemented through the existing embedding tables.

## API

- `GET /api/v1/questions/search?query=...&exam_id=...&topic=...`
- `GET /api/v1/topics?exam_id=...`
- `GET /api/v1/exams/{exam_id}/questions/{question_id}/similar`

The release pipeline rebuilds tags and similarities before activating a new
catalog. Questions without extracted text retain broad component-level tags but
may have no text-based recommendations. Admissions tests currently use text
matching only and do not receive syllabus tags until maintained specifications
are added.
