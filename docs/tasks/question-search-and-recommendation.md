# Question search and recommendation

## Asset inventory

The active catalog contains 30,528 questions across seven programs. Extracted
search text is available for 23,241 questions (76.1%). CIE Mathematics 9709 and
Further Mathematics 9231 account for 27,233 questions, and TMUA contributes 360
paired questions and answers. The normalized schema
already contained syllabus, feature, embedding, and similarity tables, but all
of them were empty before this task.

Maintained syllabus PDFs exist for 9231, 9618, and 9702. The matching topic
catalog covers 9709, 9231, and TMUA. It records the official 2026-2027 Cambridge
syllabus URLs and the UAT-UK TMUA content specification, using their section
names as canonical tags.

## Matching design

`ome-match-questions` rebuilds managed syllabus tags and the top similar
questions for each question. Component numbers constrain candidate syllabus
sections; extracted question text then selects detailed topics. Similarity is a
sparse TF-IDF cosine score (75%) plus shared-topic Jaccard score (25%). Matches
from the same paper are excluded to avoid recommending adjacent subparts.
Historical Mathematics Paper 7 is mapped to the current Paper 6 Statistics 2
content domain; zero-padded component identifiers are normalized. TMUA Paper 1
and Paper 2 receive their broad paper tags plus detailed content tags before
similarities are ranked.

Word2Vec is not used. The available corpus is small for training stable domain
word vectors, and OCR-heavy mathematical notation produces noisy tokens. The
chosen approach is deterministic, explainable, has no model download, and can
later be replaced or complemented through the existing embedding tables.

## API

- `GET /api/v1/questions/search?query=...&exam_id=...&topic=...`
- `GET /api/v1/topics?exam_id=...`
- `GET /api/v1/exams/{exam_id}/questions/{question_id}/similar`
- `POST /api/v1/questions/image-search` returns at most the top five matches.

The release pipeline rebuilds tags and similarities before activating a new
catalog. Questions without extracted text retain broad component-level tags but
may have no text-based recommendations. Admissions tests without a maintained
specification continue to use text matching only.

Photo search ranks every token-matching candidate by cosine similarity against
the complete OCR output before applying the result limit. This prevents older
TMUA questions from being discarded by the catalog's default recency ordering.
The search interface does not display OCR or stored question text in match
lists; it shows identity and topic tags, then loads the pre-rendered question
image when the user selects a match.

Knowledge-point search uses the syllabus parent hierarchy and includes all
descendant topics when a branch is selected. A question may carry multiple
topic tags. From the preview, users can switch to the matching source-paper or
source-answer page; the server renders the recorded page and marks every region
for that question on the page.
