# AxiomFolio ↔ Paperwork Brain integration (moved)

> This hand-written document was retired on 2026-04-23 as part of Track
> M.4. It had fallen out of sync with code (wrong tier numbers, wrong
> endpoint paths, stale "separate repos" framing).

The authoritative, auto-generated contract now lives at:

**[`docs/AXIOMFOLIO_INTEGRATION.generated.md`](AXIOMFOLIO_INTEGRATION.generated.md)**

Source of truth: [`docs/axiomfolio/brain/axiomfolio_tools.yaml`](axiomfolio/brain/axiomfolio_tools.yaml).
Regenerate with:

```bash
python scripts/generate_axiomfolio_integration_doc.py
```

CI (`.github/workflows/brain-personas-doc.yaml`) runs the `--check`
variant on every PR and fails if the YAML and doc drift. See Track M.4
in `/docs/INFRA.md` for the rationale.
