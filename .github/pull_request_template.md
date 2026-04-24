# Summary

<!-- What does this change do? Why now? -->

## Product / Scope

<!-- Which apps/apis are affected? -->

- [ ] axiomfolio (apis/axiomfolio, apps/axiomfolio)
- [ ] brain (apis/brain)
- [ ] filefree (apis/filefree, apps/filefree)
- [ ] launchfree (apis/launchfree, apps/launchfree)
- [ ] studio / distill / trinkets (apps/*)
- [ ] infra / shared packages / docs

## Checklist

- [ ] Tests pass locally for affected workspaces (`pnpm -w -F <pkg> test`, `make medallion-lint`, etc.)
- [ ] No test can touch dev/prod databases (uses `*_test` DBs only)
- [ ] DB migrations included where schema changed (alembic or prisma)
- [ ] Medallion boundaries respected — silver/gold/execution code does not import from below its layer
- [ ] Counter-based auditing preserved on any row-iterating task (`written + skipped + errors == total`)
- [ ] Append-only ledgers not mutated (`UPDATE` / `DELETE` replaced with idempotent inserts)
- [ ] Docs updated (`docs/`, per-workspace READMEs)
- [ ] No hardcoded secrets, tokens, or account identifiers

## Risk / Rollback

<!-- What breaks if this is wrong? How do we roll back? -->
