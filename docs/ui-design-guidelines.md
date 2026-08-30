# UI Design Guidelines

## Permanent baseline

All maintained Web UI uses the shadcn preset `b27I38wi` with the Next.js
template. The equivalent bootstrap command is:

```bash
npx shadcn@latest init --preset b27I38wi --template next
```

This repository is already initialized. Do not rerun the command over the
existing frontend. The persistent sources of truth are:

- `frontend/components.json`: Rhea style, neutral base, Hugeicons, RSC and TSX.
- `frontend/app/globals.css`: semantic light/dark tokens and motion tokens.
- `frontend/components/ui/`: repository-owned shadcn primitives.
- This document: product-specific layout, motion and accessibility rules.

Future AI-generated designs must extend this system. They must not introduce a
second component library, icon family, font system or unrelated visual theme.

## Visual language

- Use Figtree for interface text and Geist Mono for identifiers, metrics and
  tabular numbers. Chinese falls back to PingFang SC or Microsoft YaHei.
- Use semantic shadcn color tokens. Do not hardcode page-specific light/dark
  colors when an existing token expresses the role.
- Use Hugeicons consistently. Do not use emoji as structural icons.
- Keep the interface document-first and information-dense. Cards group related
  work; they are not decoration. Blur is limited to navigation, sheets and
  popovers.
- The signature layout is an adaptive exam workspace: hierarchy on the left,
  inventory or selection context immediately to its right, and document content
  in the largest remaining region.

## Responsive behavior

- Support 320 px through wide desktop without page-level horizontal overflow.
- Desktop may use split panes. Tablet stacks secondary context below the tree.
  Phone uses a single-column drill-down flow.
- Tables may scroll inside their own bounded region, but primary page controls
  remain visible and usable.
- Interactive targets are at least 44 px. Text wraps before it is truncated
  unless truncation preserves a dense identifier column and the full value is
  otherwise available.

## Motion language

- Motion communicates entry, hierarchy, selection and progress. Avoid ambient
  decorative movement.
- Use the shared tokens `--motion-swift`, `--motion-smooth` and
  `--motion-spring`. Normal interaction is 180-320 ms; page entry may use up to
  480 ms.
- Animate transform and opacity. State changes remain interactive and may be
  redirected from their current visual state; never wait for an old animation
  to finish before accepting input.
- Press feedback follows the pointer immediately with a subtle scale response.
  Expanding trees retains spatial continuity between the disclosure indicator
  and its child content.
- Initial loading uses reserved skeleton geometry followed by a short,
  staggered content entrance. It must not cause layout shift.
- `prefers-reduced-motion` reduces all nonessential motion to an effectively
  immediate state change.

## Quality gates

- All visible copy is present in both Chinese and English translation maps.
- Keyboard focus is visible and follows visual order.
- Normal text meets WCAG AA contrast. Data meaning is never communicated by
  color alone.
- Verify 320/375 px phone, 768 px tablet, 1024 px desktop and a wide desktop.
- Run frontend lint, typecheck and build before delivery.
