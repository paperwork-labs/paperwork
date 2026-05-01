"use client";

import { useEffect, useRef, useState } from "react";
import { Paperclip, X } from "lucide-react";
import type {
  Attachment,
  Conversation,
  ConversationParticipant,
  ConversationSpace,
  UrgencyLevel,
} from "@/types/conversations";
import type { ComposePersonaOption } from "@/lib/compose-persona-options";
import { CONVERSATION_SPACES, inferSpaceFromTopic } from "@/lib/conversation-spaces";

/** Optional seed when opening compose from product cockpit support (WS-76 PR-24a). */
export type ComposeModalPrefill = {
  title?: string;
  bodyMd?: string;
  space?: ConversationSpace;
  tags?: string;
  /** Sent as `product_slug` on create. */
  productSlug?: string | null;
};

const URGENCY_OPTIONS: { value: UrgencyLevel; label: string }[] = [
  { value: "info", label: "Info" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

const ALLOWED_MIMES = ["image/png", "image/jpeg", "image/webp", "application/pdf"];
const MAX_BYTES = 10 * 1024 * 1024;

const FOUNDER: ConversationParticipant = {
  id: "founder",
  kind: "founder",
  display_name: "Founder",
};

interface Props {
  onClose: () => void;
  onSuccess: (conv: Conversation) => void;
  personaOptions: ComposePersonaOption[];
  prefill?: ComposeModalPrefill | null;
  /** Deep-link / query-param: pre-check this persona id (slug) in Participants. */
  initialPersonaSlug?: string | null;
}

export function ComposeModal({
  onClose,
  onSuccess,
  personaOptions,
  prefill,
  initialPersonaSlug = null,
}: Props) {
  const [title, setTitle] = useState("");
  const [bodyMd, setBodyMd] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [urgency, setUrgency] = useState<UrgencyLevel>("normal");
  const [space, setSpace] = useState<ConversationSpace>("paperwork-labs");
  const [personaIds, setPersonaIds] = useState<Set<string>>(new Set());
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [previews, setPreviews] = useState<Map<string, string>>(new Map());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const spaceManualRef = useRef(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const dropRef = useRef<HTMLDivElement>(null);
  const appliedPersonaSeedRef = useRef(false);

  useEffect(() => {
    if (appliedPersonaSeedRef.current) return;
    const slug = initialPersonaSlug?.trim();
    if (!slug) return;
    if (!personaOptions.some((p) => p.id === slug)) return;
    setPersonaIds(new Set([slug]));
    appliedPersonaSeedRef.current = true;
  }, [initialPersonaSlug, personaOptions]);

  useEffect(() => {
    if (spaceManualRef.current) return;
    setSpace(inferSpaceFromTopic(title));
  }, [title]);

  useEffect(() => {
    if (!prefill) return;
    if (prefill.title !== undefined) setTitle(prefill.title);
    if (prefill.bodyMd !== undefined) setBodyMd(prefill.bodyMd);
    if (prefill.tags !== undefined) setTagsInput(prefill.tags);
    if (prefill.space) {
      spaceManualRef.current = true;
      setSpace(prefill.space);
    }
  }, [prefill]);

  const togglePersona = (id: string) => {
    setPersonaIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleFiles = (files: FileList | null) => {
    if (!files) return;
    Array.from(files).forEach((file) => {
      if (!ALLOWED_MIMES.includes(file.type)) {
        setError(`File type ${file.type} is not allowed.`);
        return;
      }
      if (file.size > MAX_BYTES) {
        setError(`${file.name} exceeds the 10 MB limit.`);
        return;
      }
      const id = crypto.randomUUID();
      const objectUrl = URL.createObjectURL(file);
      const att: Attachment = {
        id,
        kind: file.type.startsWith("image/") ? "image" : "file",
        url: objectUrl,
        mime: file.type,
        size_bytes: file.size,
        thumbnail_url: file.type.startsWith("image/") ? objectUrl : null,
      };
      setAttachments((prev) => [...prev, att]);
      if (file.type.startsWith("image/")) {
        setPreviews((prev) => new Map(prev).set(id, objectUrl));
      }
    });
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    handleFiles(e.dataTransfer.files);
  };

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
    setPreviews((prev) => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const tags = tagsInput
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const personaParticipants: ConversationParticipant[] = [];
      for (const id of personaIds) {
        const opt = personaOptions.find((p) => p.id === id);
        personaParticipants.push({
          id,
          kind: "persona",
          display_name: opt?.label ?? id,
        });
      }
      const participants: ConversationParticipant[] = [FOUNDER, ...personaParticipants];
      const primaryPersona =
        personaParticipants.length > 0 ? personaParticipants[0]!.id : null;

      const body: Record<string, unknown> = {
        title: title.trim(),
        body_md: bodyMd,
        tags,
        urgency,
        space,
        persona: primaryPersona,
        participants,
        attachments,
      };
      const ps = prefill?.productSlug?.trim();
      if (ps) body.product_slug = ps;
      const res = await fetch("/api/admin/conversations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const json = await res.json();
      if (!json.success) {
        setError(json.error ?? "Failed to create conversation.");
        return;
      }
      onSuccess(json.data as Conversation);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      data-testid="compose-modal"
      className="fixed inset-0 z-50 overflow-y-auto bg-black/60 p-4"
    >
      <div className="flex min-h-full items-center justify-center py-8">
        <div className="w-full max-w-lg rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl">
          <div className="flex items-center justify-between border-b border-zinc-800 px-5 py-4">
          <h2 className="text-sm font-semibold text-zinc-100">New conversation</h2>
          <button type="button" onClick={onClose} className="text-zinc-500 transition hover:text-zinc-300">
            <X className="h-4 w-4" />
          </button>
          </div>
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 p-5">
          {error && (
            <p className="rounded-lg bg-red-900/30 p-3 text-sm text-red-300">{error}</p>
          )}

          <div>
            <label htmlFor="compose-title-input" className="mb-1 block text-xs font-medium text-zinc-400">
              Title *
            </label>
            <input
              id="compose-title-input"
              data-testid="compose-title-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Conversation title…"
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-sky-500/50"
            />
          </div>

          <div>
            <label htmlFor="compose-body-textarea" className="mb-1 block text-xs font-medium text-zinc-400">
              Body (markdown)
            </label>
            <textarea
              id="compose-body-textarea"
              data-testid="compose-body-textarea"
              value={bodyMd}
              onChange={(e) => setBodyMd(e.target.value)}
              placeholder="Write the opening message… (markdown supported)"
              rows={4}
              className="w-full resize-none rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-sky-500/50"
            />
          </div>

          <div>
            <label htmlFor="compose-space-select" className="mb-1 block text-xs font-medium text-zinc-400">
              Space / channel
            </label>
            <select
              id="compose-space-select"
              data-testid="compose-space-select"
              value={space}
              onChange={(e) => {
                spaceManualRef.current = true;
                setSpace(e.target.value as ConversationSpace);
              }}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none"
            >
              {CONVERSATION_SPACES.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <p className="mb-2 text-xs font-medium text-zinc-400">Participants</p>
            <div className="space-y-2 rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-3">
              <label className="flex cursor-default items-center gap-2 text-sm text-zinc-300">
                <input type="checkbox" checked disabled data-testid="compose-persona-founder" className="rounded" />
                Founder (always included)
              </label>
              {personaOptions.length === 0 ? (
                <p className="text-xs text-zinc-500">No personas loaded — check Brain configuration.</p>
              ) : (
                personaOptions.map((opt) => (
                  <label
                    key={opt.id}
                    className="flex cursor-pointer items-center gap-2 text-sm text-zinc-300"
                  >
                    <input
                      type="checkbox"
                      checked={personaIds.has(opt.id)}
                      onChange={() => togglePersona(opt.id)}
                      data-testid={`compose-persona-${opt.id}`}
                      className="rounded"
                    />
                    {opt.label}
                  </label>
                ))
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="compose-urgency" className="mb-1 block text-xs font-medium text-zinc-400">
                Urgency
              </label>
              <select
                id="compose-urgency"
                value={urgency}
                onChange={(e) => setUrgency(e.target.value as UrgencyLevel)}
                className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none"
              >
                {URGENCY_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="compose-tags" className="mb-1 block text-xs font-medium text-zinc-400">
              Tags (comma-separated)
            </label>
            <input
              id="compose-tags"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="e.g. infra, billing, urgent"
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-sky-500/50"
            />
          </div>

          <div>
            <span className="mb-1 block text-xs font-medium text-zinc-400">Attachments</span>
            <div
              ref={dropRef}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") fileRef.current?.click();
              }}
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
              className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-zinc-700 bg-zinc-900/50 p-4 text-center transition hover:border-sky-500/40"
            >
              <Paperclip className="h-5 w-5 text-zinc-600" />
              <p className="text-xs text-zinc-500">
                Drag & drop or click to upload (PNG, JPEG, WebP, PDF — max 10 MB)
              </p>
              <input
                ref={fileRef}
                type="file"
                multiple
                accept=".png,.jpg,.jpeg,.webp,.pdf"
                className="hidden"
                onChange={(e) => handleFiles(e.target.files)}
              />
            </div>
            {attachments.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {attachments.map((att) => (
                  <div key={att.id} className="group relative">
                    {previews.has(att.id) ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={previews.get(att.id)}
                        alt="preview"
                        className="h-14 w-14 rounded object-cover"
                      />
                    ) : (
                      <div className="flex h-14 w-14 items-center justify-center rounded bg-zinc-800 text-xs text-zinc-400">
                        {att.mime?.split("/")[1] ?? "file"}
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() => removeAttachment(att.id)}
                      className="absolute -right-1 -top-1 hidden rounded-full bg-red-600 p-0.5 group-hover:block"
                    >
                      <X className="h-2.5 w-2.5 text-white" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 border-t border-zinc-800 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm text-zinc-400 transition hover:text-zinc-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              data-testid="compose-submit"
              disabled={submitting}
              className="rounded-lg bg-sky-500/20 px-4 py-2 text-sm font-medium text-sky-300 ring-1 ring-sky-500/30 transition hover:bg-sky-500/30 disabled:opacity-40"
            >
              {submitting ? "Creating…" : "Create conversation"}
            </button>
          </div>
        </form>
        </div>
      </div>
    </div>
  );
}
