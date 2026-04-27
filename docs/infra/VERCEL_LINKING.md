# Vercel linking (monorepo)

Every app deployed on Vercel needs a local **link** so the CLI knows which team and project to use. That state lives in `apps/<name>/.vercel/project.json`, which is **gitignored** (it contains IDs that differ per developer and must never be committed).

Without a link, commands like `vercel env ls`, `vercel env pull`, and `vercel deploy` fail or prompt with “codebase isn’t linked,” and automation reports “skipped because not linked.”

## One-shot setup

From the repo root:

```bash
pnpm vercel:link
```

Prerequisites:

- [Vercel CLI](https://vercel.com/docs/cli) installed (`vercel` on your `PATH`)
- Logged in: `vercel login`

The script reads the canonical mapping in [`scripts/vercel-projects.json`](../../scripts/vercel-projects.json) and runs non-interactive `vercel link` for each app that exists under `apps/` and is not already linked. It is safe to run repeatedly; already-linked apps are skipped.

Linking resolves the `team` field (slug or team id) to a Vercel team id via `vercel teams list --format json`, because some CLI versions mis-handle `--scope <slug>` and treat it as a personal account.

## Verify (read-only)

```bash
pnpm vercel:link:check
```

No network required; this only checks for `.vercel/project.json` per app.

## List env vars across linked apps

```bash
pnpm vercel:envs
```

Requires login. Emits a Markdown table (app, variable name, scopes) for secrets propagation and audits. Unlinked apps are skipped with a short message on stderr.

## Postinstall hint

After `pnpm install`, if any apps are still unlinked **and** `vercel whoami` succeeds, you may see a short reminder to run `pnpm vercel:link`. This never fails the install.

- Disable the hint: `VERCEL_LINK_SKIP=1`
- CI: the hint is skipped when `CI=true`

## Mapping file (source of truth)

Edit [`scripts/vercel-projects.json`](../../scripts/vercel-projects.json):

- `team`: Vercel team slug passed as `--scope` (e.g. `paperwork-labs`)
- `apps[]`: `dir` (folder under `apps/`), `project` (Vercel project name), optional `"deploys": false` to exclude from linking

The JSON schema is [`scripts/vercel-projects.schema.json`](../../scripts/vercel-projects.schema.json).

When you add a new Vercel app:

1. Create `apps/<dir>/` and ensure the project exists in the Vercel team.
2. Add an entry to `vercel-projects.json`.
3. Run `pnpm vercel:link`.

Entries for directories that do not exist yet (e.g. a future `apps/paperworklabs/`) are ignored until the folder is present.

## Common errors

| Symptom | What to do |
|--------|------------|
| `not logged in to Vercel` | Run `vercel login` |
| `Project not found` / wrong scope | Confirm the `project` name in `vercel-projects.json` matches the Vercel dashboard; confirm your account has access to team `team` |
| Wrong team | Update `team` in `vercel-projects.json` to your team slug (Dashboard → Team Settings) |
| Link succeeds but `vercel env ls` fails | Re-run from the app directory or use `--cwd apps/<dir>`; confirm `project.json` exists |

## Related docs

- Agent / human onboarding: [AGENTS.md](../../AGENTS.md)
- Secrets and env matrix: [docs/SECRETS.md](../SECRETS.md) and the **Secrets & Environment** Cursor rule (`secrets-ops.mdc`)
