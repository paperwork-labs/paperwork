"use client";

import { useState, useMemo } from "react";
import {
  Eye,
  EyeOff,
  Copy,
  Check,
  Search,
  AlertTriangle,
  Shield,
  KeyRound,
  RefreshCw,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

type SecretMeta = {
  id: string;
  name: string;
  service: string;
  location: string;
  description: string | null;
  expires_at: string | null;
  last_rotated_at: string | null;
  created_at: string;
  updated_at: string;
};

type RevealedSecret = {
  value: string;
  loading: boolean;
  error: string | null;
};

function formatDatePT(dateStr: string | null): string {
  if (!dateStr) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "America/Los_Angeles",
    }).format(new Date(dateStr));
  } catch {
    return "—";
  }
}

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  try {
    const diff = new Date(dateStr).getTime() - Date.now();
    return Math.floor(diff / (1000 * 60 * 60 * 24));
  } catch {
    return null;
  }
}

function previewSnippet(value: string): string {
  if (value.length <= 12) return value;
  return `${value.slice(0, 6)}...${value.slice(-4)}`;
}

function statusDot(expiresAt: string | null) {
  const days = daysUntil(expiresAt);
  if (days === null) return { color: "bg-emerald-400", label: "Active" };
  if (days <= 0) return { color: "bg-rose-400", label: "Expired" };
  if (days <= 30) return { color: "bg-rose-400", label: `${days}d left` };
  if (days <= 60) return { color: "bg-amber-400", label: `${days}d left` };
  return { color: "bg-emerald-400", label: `${days}d left` };
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};
const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

export default function SecretsClient({
  secrets,
  apiKey,
}: {
  secrets: SecretMeta[];
  apiKey: string;
}) {
  const [search, setSearch] = useState("");
  const [revealed, setRevealed] = useState<Record<string, RevealedSecret>>({});
  const [copied, setCopied] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return secrets;
    return secrets.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.service.toLowerCase().includes(q) ||
        (s.description && s.description.toLowerCase().includes(q))
    );
  }, [secrets, search]);

  const grouped = useMemo(() => {
    const map = new Map<string, SecretMeta[]>();
    for (const s of filtered) {
      const list = map.get(s.service) ?? [];
      list.push(s);
      map.set(s.service, list);
    }
    return map;
  }, [filtered]);

  const expiringSoon = useMemo(() => {
    const now = Date.now();
    const sixtyDays = 60 * 24 * 60 * 60 * 1000;
    return secrets.filter((s) => {
      if (!s.expires_at) return false;
      const exp = new Date(s.expires_at).getTime();
      return exp - now <= sixtyDays && exp > now;
    });
  }, [secrets]);

  const expiredCount = useMemo(() => {
    const now = Date.now();
    return secrets.filter((s) => {
      if (!s.expires_at) return false;
      return new Date(s.expires_at).getTime() <= now;
    }).length;
  }, [secrets]);

  const servicesCount = useMemo(
    () => new Set(secrets.map((s) => s.service)).size,
    [secrets]
  );

  async function revealSecret(id: string) {
    if (revealed[id]?.value) {
      setRevealed((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      return;
    }

    setRevealed((prev) => ({
      ...prev,
      [id]: { value: "", loading: true, error: null },
    }));

    try {
      const res = await fetch(`/api/secrets/${id}`, {
        headers: { Authorization: `Bearer ${apiKey}` },
      });
      const json = await res.json();
      if (!res.ok || !json.success) {
        throw new Error(json.error || "Failed to decrypt");
      }
      setRevealed((prev) => ({
        ...prev,
        [id]: { value: json.data.value, loading: false, error: null },
      }));
    } catch (err) {
      setRevealed((prev) => ({
        ...prev,
        [id]: {
          value: "",
          loading: false,
          error: err instanceof Error ? err.message : "Unknown error",
        },
      }));
    }
  }

  async function copyValue(id: string, value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(id);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      // clipboard not available
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Secrets Vault
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          AES-256-GCM encrypted secrets across all services. Stored in Neon
          PostgreSQL.
        </p>
      </div>

      {/* Stats */}
      <motion.section
        className="grid gap-4 md:grid-cols-4"
        variants={stagger}
        initial="hidden"
        animate="show"
      >
        <motion.div
          variants={fadeUp}
          className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5"
        >
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-zinc-500" />
            <p className="text-xs uppercase tracking-wide text-zinc-400">
              Total secrets
            </p>
          </div>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-zinc-100">
            {secrets.length}
          </p>
        </motion.div>
        <motion.div
          variants={fadeUp}
          className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5"
        >
          <div className="flex items-center gap-2">
            <KeyRound className="h-4 w-4 text-zinc-500" />
            <p className="text-xs uppercase tracking-wide text-zinc-400">
              Services
            </p>
          </div>
          <p className="mt-2 text-2xl font-semibold tabular-nums text-zinc-100">
            {servicesCount}
          </p>
        </motion.div>
        <motion.div
          variants={fadeUp}
          className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-400" />
            <p className="text-xs uppercase tracking-wide text-zinc-400">
              Expiring soon
            </p>
          </div>
          <p
            className={`mt-2 text-2xl font-semibold tabular-nums ${expiringSoon.length > 0 ? "text-amber-300" : "text-emerald-300"}`}
          >
            {expiringSoon.length}
          </p>
          <p className="text-xs text-zinc-500">within 60 days</p>
        </motion.div>
        <motion.div
          variants={fadeUp}
          className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5"
        >
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-rose-400" />
            <p className="text-xs uppercase tracking-wide text-zinc-400">
              Expired
            </p>
          </div>
          <p
            className={`mt-2 text-2xl font-semibold tabular-nums ${expiredCount > 0 ? "text-rose-300" : "text-emerald-300"}`}
          >
            {expiredCount}
          </p>
        </motion.div>
      </motion.section>

      {/* Expiry alerts */}
      {expiringSoon.length > 0 && (
        <section className="rounded-xl border border-amber-800/40 bg-amber-950/20 p-4">
          <p className="mb-2 text-sm font-medium text-amber-300">
            Rotation needed
          </p>
          <div className="space-y-1.5">
            {expiringSoon.map((s) => {
              const days = daysUntil(s.expires_at);
              const critical = days !== null && days < 30;
              return (
                <div
                  key={s.id}
                  className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm ${critical ? "text-rose-300" : "text-amber-300"}`}
                >
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${critical ? "bg-rose-400" : "bg-amber-400"}`}
                  />
                  <span className="font-medium">{s.name}</span>
                  <span className="text-zinc-500">{s.service}</span>
                  <span className="ml-auto text-xs">
                    {days !== null
                      ? days <= 0
                        ? "expired"
                        : `${days}d`
                      : "—"}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          type="text"
          placeholder="Search secrets..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-lg border border-zinc-800 bg-zinc-900/60 py-2.5 pl-10 pr-4 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition focus:border-zinc-600 focus:ring-1 focus:ring-zinc-600"
        />
      </div>

      {/* Secrets by service */}
      {filtered.length === 0 ? (
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-8 text-center">
          <p className="text-sm text-zinc-400">
            {search ? "No secrets match your search." : "No secrets in the vault yet."}
          </p>
        </section>
      ) : (
        <motion.section
          className="space-y-5"
          variants={stagger}
          initial="hidden"
          animate="show"
        >
          {Array.from(grouped.entries()).map(([service, serviceSecrets]) => (
            <motion.div
              key={service}
              variants={fadeUp}
              className="rounded-xl border border-zinc-800 bg-zinc-900/60"
            >
              <div className="border-b border-zinc-800/60 px-5 py-3">
                <p className="text-sm font-medium text-zinc-200">
                  {service}{" "}
                  <span className="text-zinc-500">
                    ({serviceSecrets.length})
                  </span>
                </p>
              </div>
              <div className="divide-y divide-zinc-800/40">
                {serviceSecrets.map((s) => {
                  const rev = revealed[s.id];
                  const status = statusDot(s.expires_at);
                  return (
                    <div key={s.id} className="px-5 py-3.5">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2.5">
                            <span
                              className={`inline-block h-2 w-2 shrink-0 rounded-full ${status.color}`}
                              title={status.label}
                            />
                            <span className="font-mono text-sm font-medium text-zinc-100">
                              {s.name}
                            </span>
                            {s.location && (
                              <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-500">
                                {s.location}
                              </span>
                            )}
                          </div>
                          {s.description && (
                            <p className="mt-1 pl-[18px] text-xs text-zinc-500">
                              {s.description}
                            </p>
                          )}

                          {/* Value display */}
                          <div className="mt-2 pl-[18px]">
                            <AnimatePresence mode="wait">
                              {rev?.loading ? (
                                <motion.div
                                  key="loading"
                                  initial={{ opacity: 0 }}
                                  animate={{ opacity: 1 }}
                                  exit={{ opacity: 0 }}
                                  className="flex items-center gap-2"
                                >
                                  <RefreshCw className="h-3 w-3 animate-spin text-zinc-500" />
                                  <span className="text-xs text-zinc-500">
                                    Decrypting...
                                  </span>
                                </motion.div>
                              ) : rev?.error ? (
                                <motion.p
                                  key="error"
                                  initial={{ opacity: 0 }}
                                  animate={{ opacity: 1 }}
                                  exit={{ opacity: 0 }}
                                  className="text-xs text-rose-400"
                                >
                                  {rev.error}
                                </motion.p>
                              ) : rev?.value ? (
                                <motion.div
                                  key="value"
                                  initial={{ opacity: 0, y: 4 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  exit={{ opacity: 0, y: -4 }}
                                  className="flex items-center gap-2"
                                >
                                  <code className="rounded bg-zinc-800 px-2 py-1 font-mono text-xs text-emerald-300">
                                    {previewSnippet(rev.value)}
                                  </code>
                                  <button
                                    onClick={() =>
                                      copyValue(s.id, rev.value)
                                    }
                                    className="rounded p-1 text-zinc-500 transition hover:bg-zinc-800 hover:text-zinc-300"
                                    title="Copy full value"
                                  >
                                    {copied === s.id ? (
                                      <Check className="h-3.5 w-3.5 text-emerald-400" />
                                    ) : (
                                      <Copy className="h-3.5 w-3.5" />
                                    )}
                                  </button>
                                </motion.div>
                              ) : (
                                <motion.span
                                  key="hidden"
                                  initial={{ opacity: 0 }}
                                  animate={{ opacity: 1 }}
                                  exit={{ opacity: 0 }}
                                  className="font-mono text-xs text-zinc-600"
                                >
                                  ••••••••••••••••
                                </motion.span>
                              )}
                            </AnimatePresence>
                          </div>
                        </div>

                        <div className="flex shrink-0 items-center gap-1">
                          <button
                            onClick={() => revealSecret(s.id)}
                            className="rounded-md p-2 text-zinc-500 transition hover:bg-zinc-800 hover:text-zinc-300"
                            title={rev?.value ? "Hide value" : "Reveal value"}
                          >
                            {rev?.value ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Metadata row */}
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 pl-[18px] text-[11px] text-zinc-600">
                        {s.expires_at && (
                          <span>
                            expires: {formatDatePT(s.expires_at)} PT
                          </span>
                        )}
                        {s.last_rotated_at && (
                          <span>
                            rotated: {formatDatePT(s.last_rotated_at)} PT
                          </span>
                        )}
                        <span>updated: {formatDatePT(s.updated_at)} PT</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          ))}
        </motion.section>
      )}

      {/* API reference */}
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="mb-3 text-sm font-medium text-zinc-200">
          Secrets API
        </p>
        <p className="mb-3 text-xs text-zinc-500">
          Auth via{" "}
          <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-zinc-400">
            Authorization: Bearer &lt;SECRETS_API_KEY&gt;
          </code>
        </p>
        <div className="grid gap-2 md:grid-cols-2">
          {[
            { method: "GET", path: "/api/secrets", desc: "List all (metadata only)" },
            { method: "POST", path: "/api/secrets", desc: "Create or update secret" },
            { method: "GET", path: "/api/secrets/:id", desc: "Get decrypted value" },
            { method: "GET", path: "/api/secrets/export", desc: "Export as .env" },
          ].map((ep) => (
            <div
              key={ep.path + ep.method}
              className="rounded-md bg-zinc-800/40 px-3 py-2 text-xs"
            >
              <span className="font-mono font-medium text-zinc-300">
                {ep.method}
              </span>{" "}
              <span className="font-mono text-zinc-400">{ep.path}</span>
              <p className="mt-0.5 text-zinc-500">{ep.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
