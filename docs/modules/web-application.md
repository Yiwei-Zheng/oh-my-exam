# Web Application

## Responsibility

The Vue application provides role-aware catalog browsing, document viewing,
administration, corrections, and pipeline control. It contains presentation and
browser adaptation only. It never imports processing or persistence internals.

## Information architecture

Desktop uses navigation, question tree, and document workspace columns. Tablet
collapses navigation. Phone uses route-based drill-down. The selected catalog
path and document state are deep-linkable.

The document rail contains question PDF, answer PDF, structured text, and source
paper views. Full paper and clipped views embed authorized backend PDF
responses. Large trees and lists load lazily.

## Visual system

The interface uses an Apple-inspired document-workspace language: system fonts,
neutral semantic surfaces, one system-blue accent, restrained materials, and
precise spacing. Blur is limited to chrome and overlays. Document surfaces are
opaque. Apple logos, screenshots, and font files are not included.

Element Plus is isolated behind `shared/ui` wrappers. Pinia owns client state;
TanStack Vue Query owns server state. User-visible strings are translated in
Chinese and English.

## Quality gates

Verify 320, 375, 768, 1024, and 1440px widths; portrait and landscape; keyboard
operation; route focus; screen-reader labels; 44px targets; WCAG AA contrast;
light and dark modes; reduced motion; and PDF loading, error, and empty states.
