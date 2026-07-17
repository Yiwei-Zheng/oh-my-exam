# CIE A-Level Classifier

## Scope

CIE A-Level classifier tool boundary.

## What belongs here

- Current classifier location.
- High-level ownership.
- Known documentation gaps.

## What does not belong here

- Downloader workflow.
- Splitter crop rules.
- Global tagging product requirements.
- Future classifier schema not yet implemented.

## Related docs

- `docs/architecture.md`
- `docs/modules/exam-processing.md`
- `docs/requirements.md`

## Current Location

- GUI launcher: `tools/classifiers/alevel/cie/cie_alevel_classifier_gui.py`.
- CLI launcher: `tools/classifiers/alevel/cie/cie_alevel_classifier_cli.py`.

## Boundary

The classifier should consume processed question data and syllabus/tag resources through documented paths or public services.

It should not import downloader or splitter internals.

## Status

Detailed classifier behavior is not yet documented.

Add local docs here when tagging inputs, outputs, or schemas become stable.
