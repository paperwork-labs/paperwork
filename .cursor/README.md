# Cursor config

- **Rules / personas**: `.cursor/rules/*.mdc` — see repo root `.cursorrules` for the list.
- **MCP**: Copy `mcp.json.example` to `mcp.json` and fill in tokens (or use env). `mcp.json` is gitignored so credentials are never committed.

## Vercel (Cursor)

The official **Cursor Vercel plugin** is enabled in [`settings.json`](settings.json) via `plugins.vercel.enabled`. That only affects the IDE: React/Next.js performance guidance (skill) and deploy helpers such as the `/vercel-deploy` command. It does **not** change Vercel project settings, builds, or runtime behavior in production.
