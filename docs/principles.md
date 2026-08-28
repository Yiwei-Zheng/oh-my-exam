# Principles

## Scope

Global engineering rules for agents working in this repository.

## What belongs here

- Stable development principles.
- Cross-cutting architecture rules.
- Rules that apply to every tool.

## What does not belong here

- Tool-specific workflows.
- Exam-board details.
- Data schemas owned by one tool.
- Completed task history.

## Related docs

- `AGENTS.md`
- `docs/architecture.md`
- `docs/requirements.md`

## Change Discipline

- Prefer small, reviewable changes.
- Avoid unrelated refactors.
- Do not delete working behavior unless the task asks for it.
- Keep names clear and consistent with nearby code.
- Add comments only for non-obvious design reasons.

## Documentation Discipline

- Read `docs/requirements.md`, `docs/architecture.md`, relevant `docs/tasks/`, and nearby code before changing code.
- Use UTF-8 when reading Chinese or mixed-language docs.
- Update documentation when behavior, startup flow, architecture, or APIs change.
- Keep global docs short and stable.
- Put local details in the owning module or tool docs.

## Source And Runtime Hygiene

- `temp/` is scratch input only.
- Move useful `temp/` files into the proper source/resource location before depending on them.
- Use only the repository-root `.venv/` for Python dependencies. Do not place
  scripts, source, docs, or project files inside it.
- Configuration belongs outside code.
- Do not commit secrets, API keys, tokens, private local data, or irrelevant generated files.

## Architecture Rules

- Core business logic and presentation layers must be separate.
- Core code must not depend on GUI frameworks.
- GUI and CLI must call public core services.
- Frontend and backend must communicate through APIs.
- Do not duplicate business logic across frontend and backend.
- If a change affects system boundaries, update `docs/architecture.md`.
- Record important long-term technical decisions under `docs/decisions/`.

## GUI Rules

- GUI must support Chinese and English.
- User-visible text belongs in i18n resources.
- Resizable windows, panels, and long content must remain usable with horizontal and vertical scrolling.
- Long list items must not hide critical actions.
- Removing GUI code must not break core and CLI functionality.
