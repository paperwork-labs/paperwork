"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { SlashCommand } from "@/lib/slash-commands";
import { filterSlashCommands, tokenTriggerAtCaret } from "@/lib/slash-commands";

export type BrainPersonaOption = {
  id: string;
  label: string;
  description?: string | null;
};

type Props = {
  value: string;
  onChange: (next: string) => void;
  slashCommands: SlashCommand[];
  personas: BrainPersonaOption[];
  disabled?: boolean;
  placeholder?: string;
  /** Override for secondary composers (e.g. thread panel). */
  textareaTestId?: string;
};

export function ConversationComposer({
  value,
  onChange,
  slashCommands,
  personas,
  disabled,
  placeholder = "Reply…",
  textareaTestId = "conversation-reply-textarea",
}: Props) {
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  const [caret, setCaret] = useState(0);
  const [menuOpen, setMenuOpen] = useState<"slash" | "mention" | null>(null);
  const [tokenStart, setTokenStart] = useState(0);
  const [highlight, setHighlight] = useState(0);

  const syncCaret = useCallback(() => {
    const el = taRef.current;
    if (!el) return;
    setCaret(el.selectionStart ?? value.length);
  }, [value.length]);

  const trigger = useMemo(() => tokenTriggerAtCaret(value, caret), [value, caret]);

  useEffect(() => {
    if (!trigger) {
      setMenuOpen(null);
      return;
    }
    if (trigger.kind === "slash") {
      setMenuOpen("slash");
      setTokenStart(trigger.start);
      setHighlight(0);
      return;
    }
    setMenuOpen("mention");
    setTokenStart(trigger.start);
    setHighlight(0);
  }, [trigger]);

  const filteredSlash = useMemo(() => {
    if (menuOpen !== "slash" || !trigger || trigger.kind !== "slash") return [];
    return filterSlashCommands(slashCommands, trigger.filter);
  }, [menuOpen, slashCommands, trigger]);

  const filteredPersonas = useMemo(() => {
    if (menuOpen !== "mention" || !trigger || trigger.kind !== "mention") return [];
    const q = trigger.filter.toLowerCase();
    if (!q) return personas;
    return personas.filter(
      (p) =>
        p.id.toLowerCase().includes(q) ||
        p.label.toLowerCase().includes(q) ||
        (p.description?.toLowerCase().includes(q) ?? false),
    );
  }, [menuOpen, personas, trigger]);

  const slashLen = filteredSlash.length;
  const personaLen = filteredPersonas.length;
  const maxIdx =
    menuOpen === "slash" ? Math.max(0, slashLen - 1) : Math.max(0, personaLen - 1);

  useEffect(() => {
    setHighlight((h) => Math.min(h, maxIdx));
  }, [maxIdx, menuOpen]);

  const applyReplacement = useCallback(
    (insertFromCaret: string) => {
      const el = taRef.current;
      const end = el?.selectionStart ?? caret;
      const next = `${value.slice(0, tokenStart)}${insertFromCaret}${value.slice(end)}`;
      onChange(next);
      setMenuOpen(null);
      requestAnimationFrame(() => {
        const node = taRef.current;
        if (!node) return;
        const pos = tokenStart + insertFromCaret.length;
        node.focus();
        node.setSelectionRange(pos, pos);
        setCaret(pos);
      });
    },
    [caret, onChange, tokenStart, value],
  );

  const selectSlash = useCallback(
    (cmd: SlashCommand) => {
      applyReplacement(`/${cmd.name} `);
    },
    [applyReplacement],
  );

  const selectPersona = useCallback(
    (id: string) => {
      applyReplacement(`@${id} `);
    },
    [applyReplacement],
  );

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (menuOpen === "slash" && slashLen > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlight((h) => (h + 1) % slashLen);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlight((h) => (h - 1 + slashLen) % slashLen);
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        selectSlash(filteredSlash[highlight]!);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setMenuOpen(null);
        return;
      }
    }
    if (menuOpen === "mention" && personaLen > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setHighlight((h) => (h + 1) % personaLen);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setHighlight((h) => (h - 1 + personaLen) % personaLen);
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        selectPersona(filteredPersonas[highlight]!.id);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setMenuOpen(null);
        return;
      }
    }
  };

  const showSlashMenu = menuOpen === "slash" && filteredSlash.length > 0;
  const showMentionMenu = menuOpen === "mention" && filteredPersonas.length > 0;

  return (
    <div className="relative">
      {showSlashMenu ? (
        <div
          className="absolute bottom-full left-0 z-20 mb-2 max-h-56 w-full overflow-auto rounded-lg border border-zinc-700/80 bg-zinc-900/95 py-1 shadow-xl ring-1 ring-black/40 backdrop-blur-sm"
          data-testid="slash-command-menu"
          role="listbox"
        >
          {filteredSlash.map((cmd, i) => (
            <button
              key={cmd.name}
              type="button"
              role="option"
              aria-selected={i === highlight}
              data-testid="slash-command-option"
              data-command={cmd.name}
              className={`flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm transition ${
                i === highlight ? "bg-zinc-800 text-zinc-50" : "text-zinc-300 hover:bg-zinc-800/70"
              }`}
              onMouseEnter={() => setHighlight(i)}
              onMouseDown={(ev) => {
                ev.preventDefault();
                selectSlash(cmd);
              }}
            >
              <span className="font-mono text-xs text-sky-300">/{cmd.name}</span>
              <span className="text-xs text-zinc-400">{cmd.description}</span>
              <span className="text-[11px] text-zinc-500">{cmd.example}</span>
            </button>
          ))}
        </div>
      ) : null}

      {showMentionMenu ? (
        <div
          className="absolute bottom-full left-0 z-20 mb-2 max-h-56 w-full overflow-auto rounded-lg border border-zinc-700/80 bg-zinc-900/95 py-1 shadow-xl ring-1 ring-black/40 backdrop-blur-sm"
          data-testid="persona-mention-menu"
          role="listbox"
        >
          {filteredPersonas.map((p, i) => (
            <button
              key={p.id}
              type="button"
              role="option"
              aria-selected={i === highlight}
              data-persona-id={p.id}
              className={`flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm transition ${
                i === highlight ? "bg-zinc-800 text-zinc-50" : "text-zinc-300 hover:bg-zinc-800/70"
              }`}
              onMouseEnter={() => setHighlight(i)}
              onMouseDown={(ev) => {
                ev.preventDefault();
                selectPersona(p.id);
              }}
            >
              <span className="font-medium text-zinc-100">{p.label}</span>
              <span className="font-mono text-[11px] text-sky-300/90">@{p.id}</span>
              {p.description ? <span className="text-xs text-zinc-500">{p.description}</span> : null}
            </button>
          ))}
        </div>
      ) : null}

      <textarea
        ref={taRef}
        data-testid={textareaTestId}
        value={value}
        disabled={disabled}
        placeholder={placeholder}
        rows={3}
        onChange={(e) => {
          onChange(e.target.value);
          setCaret(e.target.selectionStart ?? e.target.value.length);
        }}
        onSelect={syncCaret}
        onClick={syncCaret}
        onKeyUp={syncCaret}
        onKeyDown={onKeyDown}
        className="w-full resize-none rounded-lg border border-zinc-800 bg-zinc-950/80 p-3 text-sm text-zinc-200 placeholder-zinc-600 outline-none ring-0 focus:border-zinc-600 focus:ring-1 focus:ring-sky-500/30 disabled:opacity-50"
      />
      <p className="mt-2 text-[11px] text-zinc-500">
        <kbd className="rounded border border-zinc-700 bg-zinc-900 px-1">/</kbd> commands ·{" "}
        <kbd className="rounded border border-zinc-700 bg-zinc-900 px-1">@</kbd> personas
      </p>
    </div>
  );
}
