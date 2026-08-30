# Web Application

## Responsibility

The Next.js application provides role-aware catalog browsing, document viewing,
administration, corrections, and pipeline control. It contains presentation and
browser adaptation only. It never imports processing or persistence internals.

## Information architecture

Administrators use a question tree, question list, and document workspace. The
same header exposes the complete update pipeline, question search, and access
control. Access control groups existing accounts and invitation management
without mixing these identity tasks into the catalog browser.

Students and teachers land on `/questions`, where they search extracted text,
filter by exam, preview the original clipped question, and follow indexed
similar-question matches. On desktop the search result list and document view
remain side by side. Tablet moves secondary match content below the document;
phone stacks every task vertically without horizontal workspace scrolling.

The document rail contains question JPG, answer JPG, structured text, and source
paper views. Full papers use authorized PDF responses; question-level crops use
authorized pre-rendered JPG responses. Large trees and lists load lazily.

## Visual system

The interface uses a restrained technical-workspace language: graphite text,
paper-white surfaces, cool neutral dividers, one electric-blue action color,
and monospace labels for paper identifiers and operational metadata. A faint
coordinate grid and mathematical notation identify the STEM search surface;
status colors remain semantic rather than decorative. Document surfaces are
opaque and motion respects the reduced-motion preference.

Repository-owned shadcn components use preset `b27I38wi`, Figtree and
Hugeicons. Product-specific rules live in `docs/ui-design-guidelines.md`.
User-visible strings are translated in Chinese and English.

## Quality gates

Verify 320, 375, 768, 1024, and 1440px widths; portrait and landscape; keyboard
operation; route focus; screen-reader labels; 44px targets; WCAG AA contrast;
light and dark modes; reduced motion; and document loading, error, and empty states.
