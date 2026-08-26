# Domain Documentation

This repo uses a **single-context** layout for domain documentation.

## Structure

- `CONTEXT.md` at the repo root — high-level context for the entire project
- `docs/adr/` — Architecture Decision Records (ADRs)

## Consumer Rules

Agent skills that need domain context should:
1. Read `CONTEXT.md` first for project overview
2. Check `docs/adr/` for specific architectural decisions
3. Look in `docs/specs/` for feature specifications
