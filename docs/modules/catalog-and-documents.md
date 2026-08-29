# Catalog and Documents

## Responsibility

The catalog module owns normalized exam identity, hierarchy, question and answer
metadata, text, tags, corrections, and published releases. The documents module
owns immutable source document identity, object versions, and page regions.

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

## Documents and regions

A document version records its checksum, size, MIME type, storage key, and
provenance. A region refers to a zero-based page and validated PDF rectangle.
Questions and answers may use multiple ordered regions.

Full-paper delivery and clipped question delivery are separate operations.
Neither operation exposes storage keys or source paths. Structured answer text
stores raw extraction and Markdown versions independently from the PDF.

## Publication

Catalog queries resolve only against the active release plus active correction
revisions. Releases are immutable. Corrections become active on save and remain
reversible.
