# AGENTS.md

Fieldnotes — a static content site for conference talks and long-form decks.

## Stack

- Astro + Markdown content, deployed to a static host.
- Build: `npm run build`. Preview: `npm run preview`.

## Map

- `content/presentations/` — long-form deck sources; these files are large, so search
  headings first and read only the section you need.
- `docs/DESIGN.md` — visual system. Read when the task touches styling.
- `docs/ARCHITECTURE.md` — build pipeline notes. Read when changing build tooling.
- `docs/TASKS.md` — current content task list.

## Verify

- `npm run build` must pass before merging.

## Content work

Work through the task list in docs/TASKS.md, one deck at a time.
Verify layout changes with screenshots before merging.
