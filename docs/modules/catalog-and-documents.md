# Catalog and Documents

## Responsibility

The catalog module owns normalized exam identity, hierarchy, question and answer
metadata, text, tags, corrections, and publication state. The documents module
owns source-paper identity, validated storage keys, and page regions.

## Hierarchy

```text
qualification
  -> provider or exam board
    -> exam or subject
      -> year
        -> session
          -> paper
            -> question
              -> subquestion
```

Knowledge points and other classifications are tags and filters. The browser
loads one level at a time and uses cursor pagination for question results.

Managed CIE knowledge-point tags use official syllabus section names. Search
can span question text, stable identity and these tags. Similar-question lists
are built offline from syllabus overlap and sparse text similarity, then stored
in the normalized catalog so API reads remain bounded.

## Documents and regions

A source-paper record uses an internal id and a storage key relative to the
protected raw-paper root. A region refers to a zero-based page and validated PDF
rectangle. Questions and answers may use multiple ordered regions.

Full-paper delivery and clipped question delivery are separate operations.
Neither operation exposes storage keys or source paths. Structured answer text
stores raw extraction and Markdown versions independently from the PDF.

## Publication

Catalog queries resolve against the active catalog plus the latest correction
revisions. A candidate replaces the active SQLite database only after automatic
validation. Corrections become active on save; revision history is retained.
