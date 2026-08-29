# Engineering Principles

## Product truth before implementation convenience

Requirements constrain architecture. Architecture constrains module contracts.
Implementation details must not silently redefine product behavior.

## One authority per fact

The identity database owns accounts and job state. The active catalog database
owns published question data. Original PDFs own document fidelity. Generated
caches and portable inputs are never treated as published authorities.

## Explicit boundaries

The frontend communicates only through the versioned API. Pipeline core runs
without Web or GUI dependencies. Infrastructure is replaceable where a real
replacement is planned, especially object storage, queue transport, and model
providers. Avoid ceremonial abstractions elsewhere.

## Reproducible processing

Every run records configuration, inputs, outputs, code-visible adapter identity,
and failure state. Steps are idempotent. Published releases and corrections are
versioned. Original documents remain immutable.

## Clean breaks with evidence

Do not maintain compatibility code after the new path passes its acceptance
gate. Before deleting legacy assets, reconcile counts, verify checksums, render
representative documents, test the supported workflows, and retain a migration
manifest. Git history is the archive for tracked code.

## Accessible, bilingual interfaces

Chinese and English are first-class. Interfaces remain keyboard and touch
operable, responsive, contrast-safe, and usable with reduced motion. Visual
style never overrides legibility or document fidelity.

## Small, reviewable changes

Keep commits scoped to one migration or capability. Inspect diffs before every
commit. Do not combine unrelated refactors, generated files, secrets, caches, or
runtime data with source changes.
