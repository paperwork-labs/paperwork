"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { KeyRound, Loader2, ShieldCheck } from "lucide-react";

type Phase = "idle" | "submitting" | "success" | "error";

function formatRemaining(ms: number): string {
  if (ms <= 0) return "0:00";
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function IntakeClient({
  token,
  secretName,
  service,
  description,
  expectedPrefix,
  expiresAt,
}: {
  token: string;
  secretName: string;
  service: string;
  description: string | null;
  expectedPrefix: string | null;
  expiresAt: string;
}) {
  const [value, setValue] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  const expiresMs = useMemo(() => new Date(expiresAt).getTime(), [expiresAt]);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (phase !== "success") return;
    const t = setTimeout(() => {
      window.location.href = "/admin/secrets";
    }, 5000);
    return () => clearTimeout(t);
  }, [phase]);

  const remaining = expiresMs - now;
  const expired = remaining <= 0;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (expired) {
      setError("This intake has expired.");
      setPhase("error");
      return;
    }
    setPhase("submitting");
    setError(null);
    try {
      const res = await fetch(`/api/secrets/intake/${encodeURIComponent(token)}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      });
      const json = (await res.json()) as { success?: boolean; error?: string };
      if (!res.ok || !json.success) {
        const msg = json.error ?? "Something went wrong";
        setError(msg);
        setPhase("error");
        return;
      }
      setPhase("success");
    } catch {
      setError("Network error — try again.");
      setPhase("error");
    }
  }

  if (phase === "success") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="space-y-6"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/15">
            <ShieldCheck className="h-5 w-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
              Secret received
            </h1>
            <p className="text-sm text-zinc-400">The agent can continue securely.</p>
          </div>
        </div>
        <div className="rounded-xl border border-emerald-800/40 bg-emerald-950/20 p-6">
          <p className="text-emerald-200">
            ✓ Secret received, agent notified
          </p>
          <p className="mt-2 text-sm text-zinc-500">
            Redirecting to Secrets in 5 seconds…
          </p>
          <Link
            href="/admin/secrets"
            className="mt-4 inline-block text-sm text-zinc-300 underline decoration-zinc-600 underline-offset-4 hover:text-white"
          >
            Go now
          </Link>
        </div>
      </motion.div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Secret intake
        </h1>
        <p className="mt-1 text-sm text-zinc-400">
          Paste the value once. It is encrypted and stored in the vault — nothing is echoed back.
        </p>
      </div>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-6">
        <div className="mb-4 flex flex-wrap items-center gap-3 text-sm">
          <KeyRound className="h-4 w-4 text-zinc-500" />
          <span className="font-mono font-medium text-zinc-100">{secretName}</span>
          <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">{service}</span>
        </div>
        {description ? (
          <p className="mb-4 text-sm text-zinc-500">{description}</p>
        ) : null}
        {expectedPrefix ? (
          <p className="mb-4 text-xs text-zinc-500">
            Expected prefix:{" "}
            <code className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-zinc-300">
              {expectedPrefix}
            </code>
          </p>
        ) : null}
        <p
          className={`mb-4 text-xs tabular-nums ${expired ? "text-rose-400" : "text-amber-300"}`}
        >
          {expired ? "Expired" : `Expires in ${formatRemaining(remaining)}`}
        </p>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label htmlFor="secret-value" className="mb-1.5 block text-xs font-medium text-zinc-400">
              Secret value
            </label>
            <input
              id="secret-value"
              name="secret-value"
              type="password"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              disabled={phase === "submitting" || expired}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950/80 py-2.5 px-3 font-mono text-sm text-zinc-100 outline-none transition focus:border-zinc-600 focus:ring-1 focus:ring-zinc-600 disabled:opacity-50"
              placeholder="Paste secret once"
            />
          </div>
          {error ? (
            <p className="text-sm text-rose-400" role="alert">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={phase === "submitting" || expired || !value.trim()}
            className="inline-flex items-center gap-2 rounded-lg bg-zinc-100 px-4 py-2.5 text-sm font-medium text-zinc-900 transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {phase === "submitting" ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Submitting…
              </>
            ) : (
              "Submit securely"
            )}
          </button>
        </form>
      </section>

      <p className="text-xs text-zinc-600">
        <Link href="/admin/secrets" className="underline decoration-zinc-700 underline-offset-2 hover:text-zinc-400">
          Cancel and return to Secrets
        </Link>
      </p>
    </div>
  );
}
