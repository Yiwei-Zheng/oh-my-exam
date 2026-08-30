# 0008: Apple-inspired adaptive document workspace

## Status

Accepted on 2026-08-29.

## Context

The web application must support a deep question hierarchy, full-paper PDF
viewing, question and answer comparison, structured answer text, pipeline
operations, phones, tablets, desktops, Chinese, and English. A generic dashboard
or decorative glassmorphism would reduce information density and readability.

## Decision

Use an Apple-inspired document workspace rather than copying Apple assets or
marketing pages. The primary reference is the interaction language of Finder,
Preview, and system settings: restrained hierarchy, adaptive split views,
semantic materials, precise spacing, and predictable sheets and popovers.

Desktop uses navigation, lazy question tree, and document workspace columns.
Tablet uses a collapsible tree and preview. Phone uses drill-down navigation.
The signature interaction is a document rail switching among question JPG,
answer JPG, structured text, and source paper while retaining context.

Use semantic light and dark tokens. Default to the operating-system theme. Use
the system font stack rather than distributing SF Pro. Blur is limited to
navigation chrome, popovers, and sheets. PDF and text surfaces remain opaque.
All visible text uses i18n resources.

Use repository-owned shadcn primitives configured by preset `b27I38wi` and
Hugeicons. Feature components call the FastAPI boundary through the shared API
adapter and do not introduce a second UI framework.

Required quality gates include 320px layouts, portrait and landscape, keyboard
navigation, visible focus, 44px touch targets, WCAG AA contrast, screen-reader
labels, reduced motion, and route-level deep links.

## Consequences

- The interface is content-dense without becoming a generic enterprise theme.
- Light and dark themes are independently designed and tested.
- Apple logos, screenshots, SF font files, and unmodified platform assets are
  not bundled.

## References

- Apple Human Interface Guidelines foundations:
  https://developer.apple.com/design/human-interface-guidelines/foundations
- Apple materials guidance:
  https://developer.apple.com/design/human-interface-guidelines/materials
- Apple font licensing entry point:
  https://developer.apple.com/fonts/
- Vue testing recommendations:
  https://vuejs.org/guide/scaling-up/testing.html
