"use client";

import { useState } from "react";
import { FadeIn } from "@/components/animated/fade-in";
import { GlowCard } from "@/components/animated/glow-card";
import { TypingDots } from "@/components/animated/typing-dots";

export default function AdvisoryPlaygroundPage() {
  const [prompt, setPrompt] = useState(
    "I just got a W-2 and one 1099-INT. What should I prepare before filing?"
  );
  const [answer, setAnswer] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(false);

  async function runAdvisory() {
    setLoading(true);
    setError("");
    setAnswer("");

    try {
      const res = await fetch("/api/advisory", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      const data = (await res.json()) as {
        success: boolean;
        data?: { text: string };
        error?: string;
      };

      if (!res.ok || !data.success) {
        setError(data.error || "Advisory request failed.");
        return;
      }

      setAnswer(data.data?.text || "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10">
      <FadeIn>
        <h1 className="text-2xl font-semibold tracking-tight">Advisory Playground</h1>
        <p className="mt-1 text-sm text-zinc-400">
          AI SDK-backed advisory endpoint plus reusable animation primitives.
        </p>
      </FadeIn>

      <FadeIn delay={0.05}>
        <GlowCard>
          <label htmlFor="advisory-prompt" className="mb-2 block text-sm font-medium text-zinc-200">
            Ask a tax prep question
          </label>
          <textarea
            id="advisory-prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            className="min-h-28 w-full rounded-md border border-zinc-700 bg-zinc-950/80 p-3 text-sm text-zinc-100 outline-none focus:border-violet-500"
          />
          <button
            type="button"
            onClick={runAdvisory}
            disabled={loading}
            className="mt-3 inline-flex items-center rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? (
              <>
                Thinking <span className="ml-2"><TypingDots /></span>
              </>
            ) : (
              "Get advisory guidance"
            )}
          </button>
        </GlowCard>
      </FadeIn>

      {error ? (
        <FadeIn delay={0.1}>
          <GlowCard className="border-red-800/60">
            <p className="text-sm text-red-300">{error}</p>
          </GlowCard>
        </FadeIn>
      ) : null}

      {answer ? (
        <FadeIn delay={0.12}>
          <GlowCard>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-zinc-400">Response</h2>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-100">{answer}</p>
          </GlowCard>
        </FadeIn>
      ) : null}
    </main>
  );
}
