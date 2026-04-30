"use client";

import * as React from "react";
import { MessageCircle, Send, X } from "lucide-react";

import { cn } from "../lib/utils";
import { Button } from "./button";
import { Textarea } from "./textarea";

/** Canonical Brain HTTP route is `POST /api/v1/brain/process` (not `/api/v1/agent/process`). */
export type BrainChatVariant = "light" | "dark";

export type BrainChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export type BrainChatProps = {
  /** Full URL for POST (e.g. `/api/brain/process` or `https://brain…/api/v1/brain/process`). */
  apiUrl: string;
  /** Sent as Brain `channel` (surface indicator). */
  productSlug: string;
  /** Optional JSON-safe context inserted as a leading system turn in `thread_context`. */
  userContext?: Record<string, unknown>;
  visualVariant?: BrainChatVariant;
  className?: string;
  /** Forwarded as Brain `persona_pin` when set. */
  personaPin?: string | null;
  /** Override Brain chain `strategy` when set. */
  strategy?: string | null;
  /** Extra fetch headers (e.g. auth); omit when calling same-origin BFF routes. */
  buildHeaders?: () => HeadersInit | Promise<HeadersInit>;
};

const VARIANT_SHELL: Record<BrainChatVariant, string> = {
  dark: "border-zinc-700 bg-zinc-950 text-zinc-100 shadow-xl shadow-black/40",
  light: "border-zinc-200 bg-white text-zinc-900 shadow-xl shadow-zinc-900/10",
};

const VARIANT_MUTED: Record<BrainChatVariant, string> = {
  dark: "text-zinc-400",
  light: "text-zinc-500",
};

const VARIANT_TEXTAREA: Record<BrainChatVariant, string> = {
  dark: "border-zinc-700 bg-zinc-900 text-zinc-100 placeholder:text-zinc-500 focus-visible:ring-zinc-500",
  light:
    "border-zinc-200 bg-white text-zinc-900 placeholder:text-zinc-400 focus-visible:ring-zinc-400",
};

const VARIANT_BUBBLE_USER: Record<BrainChatVariant, string> = {
  dark: "bg-violet-600 text-white",
  light: "bg-violet-600 text-white",
};

const VARIANT_BUBBLE_ASSISTANT: Record<BrainChatVariant, string> = {
  dark: "bg-zinc-800 text-zinc-100",
  light: "bg-zinc-100 text-zinc-900",
};

function threadStorageKey(productSlug: string) {
  return `brain-chat-thread:${productSlug}`;
}

export function BrainChat({
  apiUrl,
  productSlug,
  userContext,
  visualVariant = "dark",
  className,
  personaPin,
  strategy,
  buildHeaders,
}: BrainChatProps) {
  const [open, setOpen] = React.useState(false);
  const [threadId, setThreadId] = React.useState<string | null>(null);
  const [messages, setMessages] = React.useState<BrainChatMessage[]>([]);
  const [draft, setDraft] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const listRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const key = threadStorageKey(productSlug);
    let id = sessionStorage.getItem(key);
    if (!id) {
      id = crypto.randomUUID();
      sessionStorage.setItem(key, id);
    }
    setThreadId(id);
  }, [productSlug]);

  React.useEffect(() => {
    if (!listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, open]);

  async function handleSubmit() {
    const text = draft.trim();
    if (!text || busy || !threadId) return;

    const userMsg: BrainChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };

    const thread_context: Array<Record<string, string>> = [];

    if (userContext && Object.keys(userContext).length > 0) {
      thread_context.push({
        role: "system",
        content: `${productSlug} context: ${JSON.stringify(userContext)}`,
      });
    }

    for (const m of messages) {
      thread_context.push({ role: m.role, content: m.content });
    }

    const payload: Record<string, unknown> = {
      message: text,
      channel: productSlug,
      thread_id: threadId,
      thread_context: thread_context.length > 0 ? thread_context : undefined,
    };
    if (personaPin) payload.persona_pin = personaPin;
    if (strategy) payload.strategy = strategy;

    setDraft("");
    setError(null);
    setBusy(true);
    setMessages((prev) => [...prev, userMsg]);

    try {
      const headersInit = buildHeaders ? await buildHeaders() : undefined;
      const headers = new Headers(headersInit ?? {});
      if (!headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }

      const res = await fetch(apiUrl, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });

      const json = (await res.json()) as {
        success?: boolean;
        data?: { response?: string; error?: string };
        error?: string;
      };

      if (!res.ok || json.success === false) {
        const detail =
          (typeof json.error === "string" && json.error) ||
          json.data?.error ||
          `Request failed (${res.status})`;
        throw new Error(detail);
      }

      const reply =
        typeof json.data?.response === "string"
          ? json.data.response
          : "(Brain returned no text.)";
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", content: reply },
      ]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Brain request failed";
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  const shell = VARIANT_SHELL[visualVariant];
  const muted = VARIANT_MUTED[visualVariant];

  return (
    <div
      className={cn("pointer-events-none fixed bottom-4 right-4 z-[80] flex flex-col items-end gap-3", className)}
      data-testid="brain-chat-root"
    >
      {open ? (
        <section
          id="brain-chat-panel"
          className={cn(
            "pointer-events-auto flex h-[min(70vh,520px)] w-[min(100vw-2rem,384px)] flex-col rounded-2xl border",
            shell,
          )}
          aria-label={`${productSlug} Brain chat`}
        >
          <header className="flex shrink-0 items-center justify-between border-b border-black/10 px-4 py-3 dark:border-white/10">
            <div>
              <h2 className="text-sm font-semibold tracking-tight">Brain</h2>
              <p className={cn("text-xs", muted)}>{productSlug}</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className={visualVariant === "dark" ? "text-zinc-300 hover:bg-zinc-800" : ""}
              onClick={() => setOpen(false)}
              aria-label="Close Brain chat"
            >
              <X className="size-4" aria-hidden />
            </Button>
          </header>

          <div
            ref={listRef}
            className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3"
            role="log"
            aria-live="polite"
          >
            {messages.length === 0 ? (
              <p className={cn("text-center text-sm", muted)}>
                Ask a question — replies route through Paperwork Brain.
              </p>
            ) : null}
            {messages.map((m) => (
              <div
                key={m.id}
                className={cn(
                  "max-w-[90%] rounded-2xl px-3 py-2 text-sm leading-relaxed",
                  m.role === "user"
                    ? cn(VARIANT_BUBBLE_USER[visualVariant], "ml-auto")
                    : VARIANT_BUBBLE_ASSISTANT[visualVariant],
                )}
              >
                {m.content}
              </div>
            ))}
          </div>

          {error ? (
            <p
              className={cn(
                "shrink-0 px-4 text-xs",
                visualVariant === "dark" ? "text-red-400" : "text-red-600",
              )}
              role="alert"
            >
              {error}
            </p>
          ) : null}

          <footer className="shrink-0 border-t border-black/10 p-3 dark:border-white/10">
            <div className="flex gap-2">
              <Textarea
                value={draft}
                onChange={(ev) => setDraft(ev.target.value)}
                placeholder={threadId ? "Message Brain…" : "Initializing…"}
                disabled={busy || !threadId}
                rows={2}
                className={cn("min-h-[44px] resize-none text-sm", VARIANT_TEXTAREA[visualVariant])}
                onKeyDown={(ev) => {
                  if (ev.key === "Enter" && !ev.shiftKey) {
                    ev.preventDefault();
                    void handleSubmit();
                  }
                }}
              />
              <Button
                type="button"
                size="icon"
                className="h-auto shrink-0 self-end"
                disabled={busy || !draft.trim() || !threadId}
                onClick={() => void handleSubmit()}
                aria-label="Send message"
              >
                <Send className="size-4" aria-hidden />
              </Button>
            </div>
          </footer>
        </section>
      ) : null}

      <Button
        type="button"
        size="lg"
        className={cn(
          "pointer-events-auto size-14 rounded-full shadow-lg",
          visualVariant === "dark"
            ? "bg-violet-600 text-white hover:bg-violet-500"
            : "bg-violet-600 text-white hover:bg-violet-500",
        )}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={open ? "brain-chat-panel" : undefined}
        aria-label={open ? "Collapse Brain chat" : "Open Brain chat"}
      >
        <MessageCircle className="size-6" aria-hidden />
      </Button>
    </div>
  );
}
