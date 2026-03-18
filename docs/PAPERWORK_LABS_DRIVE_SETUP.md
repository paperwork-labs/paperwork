# Paperwork Labs — Google Drive Setup

**Purpose**: Central hub for agent outputs (briefings, trinket one-pagers, competitive intel). Cursor can read via GDrive MCP. Create this structure in Drive to prove connection + organize outputs.

**Last updated**: 2026-03-17

---

## Quick Proof It Works

1. Go to [drive.google.com](https://drive.google.com)
2. Create a **folder**: `Paperwork Labs HQ`
3. Inside it, create a **Google Doc** named: `MCP Connected — 2026-03-17`
4. Add one line: *"GDrive MCP is reading this. Paperwork Labs HQ is live."*
5. In Cursor, ask the agent: *"Search my Drive for 'MCP Connected'"* — you should see the doc.

---

## Folder Structure (Create Manually)

Create these folders under `Paperwork Labs HQ/`:

```
Paperwork Labs HQ/
├── Operations/
│   ├── Daily Briefings/
│   ├── Weekly Plans/
│   └── Analytics/
├── Trinkets/
│   ├── One-Pagers/
│   └── PRDs/
└── Intelligence/
```

**Where to create**: In Google Drive, click **New** → **Folder** → `Paperwork Labs HQ`. Open it, then create the subfolders.

**EA agent outputs** (from n8n workflows) will write here once the GDrive output nodes are configured. Cursor can search and read these files via MCP.

---

## GDrive MCP: Read-Write (google-drive-mcp)

We use **google-drive-mcp** (domdomegg) — supports `folder_create`, `file_upload`, and full file management. The official `@modelcontextprotocol/server-gdrive` is read-only.

### One-Time GCP Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services** → **Credentials**
2. Open your OAuth 2.0 Client ID
3. Under **Authorized redirect URIs**, add: `http://localhost:3100/callback`
4. Save

### Start the Server (Required Before Using in Cursor)

The server runs on HTTP and must be running before Cursor can use it:

```bash
./scripts/start-gdrive-mcp.sh
```

Keep that terminal open. Cursor connects to `http://localhost:3100/mcp`.

### mcp.json

The project `.cursor/mcp.json` is configured to use `gdrive-writable` when the server is running. Restart Cursor or reload MCP after starting the server.
