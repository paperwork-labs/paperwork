---
last_reviewed: 2026-05-01
owner: strategy
doc_kind: reference
domain: docs
tags: [docs, obsidian]
---

# Navigate `docs/` (Obsidian vault)

This folder stays **markdown-first** for GitHub, CI, and agents. You can also open **`docs/` as an Obsidian vault** for graph view, backlinks, and quick switching—without changing how anyone else uses the repo.

**Setup (one time):** Install [Obsidian](https://obsidian.md), choose **Open folder as vault**, select the `docs/` directory in this monorepo. Copy `docs/.obsidian-recommended/*.json` into `docs/.obsidian/` (create `.obsidian` if needed). Restart Obsidian if it was already open.

**Hard rule:** Do **not** use `[[wikilinks]]`. Keep using normal Markdown links like [`INFRA.md`](INFRA.md) so GitHub and our doc checks keep working. Obsidian still resolves **backlinks** from Markdown links.

**Useful features:** Graph (**Cmd+G**), Backlinks (right sidebar), Command palette (**Cmd+P**), Quick switcher (**Cmd+O**), Tags pane. **Bookmarks:** if the Bookmarks core plugin does not show the seeded list after first launch, Obsidian may rewrite `bookmarks.json` — open the docs hub at [INFRA.md](INFRA.md) or [axiomfolio/PRODUCTION.md](axiomfolio/PRODUCTION.md) and use the Quick switcher (Cmd+O) to jump anywhere from there.

**Daily notes** use **`journal/YYYY-MM-DD.md`** (same as the template in `.obsidian-recommended`). Put scratch and personal notes there so tooling can read paths predictably; they are intentionally omitted from the generated docs hub index.
