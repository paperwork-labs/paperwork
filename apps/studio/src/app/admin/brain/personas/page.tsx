import fs from "node:fs";
import path from "node:path";
import { Suspense } from "react";

import matter from "gray-matter";
import { headers } from "next/headers";

import { getStudioPublicOrigin } from "@/lib/studio-public-url";

import { PersonasPageClient } from "./personas-client";
import type {
  ActivityPayload,
  CostWindowPayload,
  PersonaRow,
  PersonasPageInitial,
  RoutingPayload,
} from "./personas-types";

export const dynamic = "force-dynamic";

async function resolveBaseUrl(): Promise<string> {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host");
  if (!host) {
    return getStudioPublicOrigin();
  }
  const proto =
    h.get("x-forwarded-proto") ??
    (host.startsWith("localhost") || host.startsWith("127.") ? "http" : "https");
  return `${proto}://${host}`;
}

async function fetchPersonasEnvelope<T>(pathSegment: string, search = ""): Promise<T | null> {
  const base = await resolveBaseUrl();
  const res = await fetch(`${base}/api/admin/personas/${pathSegment}${search}`, { cache: "no-store" });
  if (!res.ok) return null;
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    return null;
  }
  if (!body || typeof body !== "object") return null;
  const rec = body as { success?: boolean; data?: unknown };
  if (!rec.success || rec.data == null) return null;
  return rec.data as T;
}

function loadModelRegistryFromRepo(): { markdown: string; lastReviewed: string | null } {
  const root = path.resolve(process.cwd(), "../..");
  const fp = path.join(root, "docs", "AI_MODEL_REGISTRY.md");
  try {
    const raw = fs.readFileSync(fp, "utf-8");
    const { content, data } = matter(raw);
    const lr = (data as { last_reviewed?: unknown }).last_reviewed;
    return {
      markdown: content.trim() || "",
      lastReviewed: typeof lr === "string" ? lr : null,
    };
  } catch {
    return { markdown: "", lastReviewed: null };
  }
}

export default async function BrainPersonasPage() {
  const brainConfigured = Boolean(
    process.env.BRAIN_API_URL?.trim() && process.env.BRAIN_API_SECRET?.trim(),
  );

  const listEnvelope = brainConfigured
    ? await fetchPersonasEnvelope<{ personas?: PersonaRow[] }>("list")
    : null;
  const personas = listEnvelope?.personas ?? (brainConfigured ? null : []);

  const cost7d = brainConfigured
    ? await fetchPersonasEnvelope<CostWindowPayload>("cost", "?window=7d")
    : null;
  const cost30d = brainConfigured
    ? await fetchPersonasEnvelope<CostWindowPayload>("cost", "?window=30d")
    : null;
  const routing = brainConfigured ? await fetchPersonasEnvelope<RoutingPayload>("routing") : null;
  const activity = brainConfigured
    ? await fetchPersonasEnvelope<ActivityPayload>("activity", "?limit=50")
    : null;

  const doc = loadModelRegistryFromRepo();

  const initial: PersonasPageInitial = {
    brainConfigured,
    personas,
    cost7d,
    cost30d,
    routing,
    activity,
    modelRegistryMarkdown: doc.markdown,
    modelRegistryLastReviewed: doc.lastReviewed,
  };

  return (
    <Suspense fallback={<div className="p-6 text-sm text-zinc-400">Loading personas…</div>}>
      <PersonasPageClient initial={initial} />
    </Suspense>
  );
}
