import { MessageSquare } from "lucide-react";

export const dynamic = "force-dynamic";

// PR E populates this page with a full conversation browser, thread viewer,
// and needs-action filter (the ?filter=needs-action route redirected from
// /admin/founder-actions lands here).

export default function BrainConversationsPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Brain — Conversations
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Full conversation history across Brain personas, with filtering by status, persona,
          and action-required flag. Founder-escalation conversations are surfaced via
          the <code className="rounded bg-zinc-800 px-1 font-mono text-xs">?filter=needs-action</code> query.
        </p>
      </header>
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-700 bg-zinc-900/40 py-20 text-center">
        <MessageSquare className="mb-4 h-10 w-10 text-zinc-600" />
        <h2 className="text-base font-semibold text-zinc-300">Conversations — coming soon</h2>
        <p className="mt-2 max-w-md text-sm text-zinc-500">
          Full conversation browser with thread viewer, persona filter, date range, and
          escalation queue. The shell is ready; PR E wires the Brain API connection and
          renders the conversation list.
        </p>
        <span className="mt-4 rounded-full border border-zinc-700 bg-zinc-800 px-3 py-1 text-xs font-medium text-zinc-400">
          PR E populates
        </span>
      </div>
    </div>
  );
}
