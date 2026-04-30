/**
 * Conversations slash-command registry (WS-76 PR-22).
 * Extensible: add entries to `createSlashCommands`.
 */

export type SlashCommand = {
  name: string;
  description: string;
  example: string;
  handler: (args: string) => Promise<void>;
};

export class SlashCommandValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SlashCommandValidationError";
  }
}

export type SlashCommandRunOutcome =
  | { status: "not_slash_prefixed" }
  | { status: "unknown_command" }
  | { status: "completed" }
  | { status: "validation_failed"; message: string };

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function parseMoneyToCents(raw: string): number | null {
  const s = raw.replace(/^\$/, "").replace(/,/g, "").trim();
  if (!s) return null;
  if (!/^\d+(\.\d{1,2})?$/.test(s)) return null;
  const n = Number(s);
  if (!Number.isFinite(n) || n < 0) return null;
  return Math.round(n * 100);
}

function formatUsd(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(cents / 100);
}

function parseExpenseArgs(args: string): { amountCents: number; description: string } {
  const trimmed = args.trim();
  if (!trimmed) {
    throw new SlashCommandValidationError("Usage: /expense <amount> <description> — e.g. /expense $42 Snacks");
  }
  const m = trimmed.match(/^(\$?[\d.,]+)\s+(.+)$/);
  if (!m) {
    throw new SlashCommandValidationError("Usage: /expense <amount> <description> — e.g. /expense $42 Snacks");
  }
  const cents = parseMoneyToCents(m[1]);
  if (cents === null) throw new SlashCommandValidationError("Invalid expense amount.");
  const description = m[2].trim();
  if (!description) throw new SlashCommandValidationError("Expense description is required.");
  return { amountCents: cents, description };
}

async function postExpenseFromComposer(description: string, amountCents: number): Promise<void> {
  const payload = {
    vendor: description.slice(0, 200),
    amount_cents: amountCents,
    currency: "USD",
    category: "misc" as const,
    source: "manual" as const,
    occurred_at: todayIsoDate(),
    notes: "Created from Studio conversation slash command.",
    tags: ["studio-slash"],
  };
  const form = new FormData();
  form.set("body", JSON.stringify(payload));
  const res = await fetch("/api/admin/expenses", { method: "POST", body: form });
  const json = (await res.json().catch(() => ({}))) as {
    success?: boolean;
    error?: string;
    message?: string;
  };
  if (!res.ok || !json.success) {
    throw new SlashCommandValidationError(
      json.error ?? json.message ?? `Expense API failed (${res.status})`,
    );
  }
}

export type SlashCommandContext = {
  conversationId: string;
  emitMessage: (bodyMd: string) => Promise<void>;
};

export function createSlashCommands(ctx: SlashCommandContext): SlashCommand[] {
  const { emitMessage } = ctx;

  return [
    {
      name: "expense",
      description: "Creates an expense entry (posts to Brain via Studio proxy)",
      example: "/expense $42 Snacks",
      handler: async (args) => {
        const { amountCents, description } = parseExpenseArgs(args);
        await postExpenseFromComposer(description, amountCents);
        await emitMessage(`[Expense] ${formatUsd(amountCents)} — ${description}`);
      },
    },
    {
      name: "runbook",
      description: "Opens a named runbook in-context (inline link)",
      example: "/runbook deploy-checklist",
      handler: async (args) => {
        const name = args.trim();
        if (!name) {
          throw new SlashCommandValidationError("Usage: /runbook <name> — e.g. /runbook deploy-checklist");
        }
        await emitMessage(
          `[Runbook] **${name}** — [Open runbook](/admin/runbook)\n\n_In-context shortcut from slash command._`,
        );
      },
    },
    {
      name: "goal",
      description: "Link an objective or OKR in the thread",
      example: "/goal Ship WS-76 billing cutover",
      handler: async (args) => {
        const objective = args.trim();
        if (!objective) {
          throw new SlashCommandValidationError("Usage: /goal <objective> — e.g. /goal Ship WS-76 billing cutover");
        }
        await emitMessage(`[Goal / OKR] ${objective}`);
      },
    },
    {
      name: "dispatch",
      description: "Dispatch an agent for a workstream (thread note)",
      example: "/dispatch ws-76-pr-22",
      handler: async (args) => {
        const workstream = args.trim();
        if (!workstream) {
          throw new SlashCommandValidationError("Usage: /dispatch <workstream> — e.g. /dispatch ws-76-pr-22");
        }
        await emitMessage(`[Dispatch] workstream \`${workstream}\` — request logged in thread.`);
      },
    },
    {
      name: "ask-brain",
      description: "Route a question to Brain from this thread",
      example: "/ask-brain What is our current burn multiple?",
      handler: async (args) => {
        const q = args.trim();
        if (!q) {
          throw new SlashCommandValidationError("Usage: /ask-brain <question>");
        }
        await emitMessage(`[Ask Brain] ${q}`);
      },
    },
  ];
}

export async function runSlashPrefixedLine(
  line: string,
  registry: SlashCommand[],
): Promise<SlashCommandRunOutcome> {
  const trimmed = line.trim();
  if (!trimmed.startsWith("/")) return { status: "not_slash_prefixed" };
  const m = trimmed.match(/^\/([\w-]+)(?:\s+([\s\S]*))?$/);
  if (!m || !m[1]) return { status: "unknown_command" };
  const cmdName = m[1];
  const rest = typeof m[2] === "string" ? m[2].trimEnd() : "";
  const cmd = registry.find((c) => c.name === cmdName);
  if (!cmd) return { status: "unknown_command" };
  try {
    await cmd.handler(rest);
    return { status: "completed" };
  } catch (e) {
    if (e instanceof SlashCommandValidationError) {
      return { status: "validation_failed", message: e.message };
    }
    throw e;
  }
}

/** Token starting with `/` or `@` from `start` through `caret` (exclusive), if unbroken by whitespace/newline. */
export function tokenTriggerAtCaret(
  text: string,
  caret: number,
): { kind: "slash" | "mention"; start: number; filter: string } | null {
  if (caret <= 0) return null;
  let i = caret - 1;
  while (i >= 0 && !/[\s\n]/.test(text[i]!)) {
    i--;
  }
  const start = i + 1;
  const tok = text.slice(start, caret);
  if (tok.startsWith("/")) return { kind: "slash", start, filter: tok.slice(1) };
  if (tok.startsWith("@")) return { kind: "mention", start, filter: tok.slice(1) };
  return null;
}

export function filterSlashCommands(commands: SlashCommand[], filter: string): SlashCommand[] {
  const q = filter.trim().toLowerCase();
  if (!q) return commands;
  return commands.filter(
    (c) => c.name.toLowerCase().startsWith(q) || c.name.toLowerCase().includes(q),
  );
}
