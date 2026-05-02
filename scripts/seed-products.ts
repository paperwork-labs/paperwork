#!/usr/bin/env node
/**
 * Seed Brain ``products`` table for Studio admin (WS-82).
 *
 * Env: ``BRAIN_API_URL``, ``BRAIN_API_SECRET`` (same as other Brain seed scripts).
 *
 * Idempotency: POST then PUT on HTTP 409.
 *
 * Run: ``pnpm seed:products`` or ``pnpm exec tsx scripts/seed-products.ts``
 */

type BrainEnvelope<T> = {
  success: boolean;
  data?: T;
  error?: string | null;
};

type ProductCreateBody = {
  id: string;
  name: string;
  tagline?: string | null;
  status?: string;
  domain?: string | null;
  repo_path?: string | null;
  vercel_project?: string | null;
  render_services?: unknown[];
  tech_stack?: unknown[];
  metadata?: Record<string, unknown>;
};

function sanitizeEnv(val: string | undefined): string {
  if (!val) return "";
  return val.trim().replace(/\\n$/, "").replace(/\/+$/, "");
}

function brainApiV1Root(): string | null {
  const raw = sanitizeEnv(process.env.BRAIN_API_URL);
  if (!raw) return null;
  return raw.endsWith("/api/v1") ? raw : `${raw}/api/v1`;
}

function die(msg: string): never {
  console.error(msg);
  process.exit(1);
}

async function brainFetch(
  root: string,
  secret: string,
  method: string,
  path: string,
  body?: unknown,
): Promise<Response> {
  const url = `${root}${path}`;
  const headers: Record<string, string> = { "X-Brain-Secret": secret };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  return fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
}

async function parseEnvelope<T>(label: string, res: Response): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`${label}: HTTP ${res.status} ${text.slice(0, 600)}`);
  }
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error(`${label}: response is not JSON`);
  }
  const env = json as BrainEnvelope<T>;
  if (typeof env === "object" && env !== null && "success" in env) {
    if (!env.success) {
      throw new Error(`${label}: ${env.error ?? "success=false"}`);
    }
    if (env.data !== undefined) return env.data as T;
  }
  return json as T;
}

function omitId(body: ProductCreateBody): Omit<ProductCreateBody, "id"> {
  const { id: _id, ...rest } = body;
  return rest;
}

async function postOrPutProduct(
  root: string,
  secret: string,
  body: ProductCreateBody,
): Promise<void> {
  const postRes = await brainFetch(root, secret, "POST", "/admin/products", body);
  if (postRes.status === 409) {
    const putRes = await brainFetch(
      root,
      secret,
      "PUT",
      `/admin/products/${encodeURIComponent(body.id)}`,
      omitId(body),
    );
    await parseEnvelope<unknown>(`product ${body.id} (put)`, putRes);
    return;
  }
  await parseEnvelope<unknown>(`product ${body.id} (post)`, postRes);
}

const SEED_PRODUCTS: ProductCreateBody[] = [
  {
    id: "axiomfolio",
    name: "AxiomFolio",
    tagline: "AI-powered portfolio management",
    status: "beta",
    domain: "axiomfolio.com",
    repo_path: "apps/axiomfolio",
    vercel_project: "axiomfolio",
    metadata: {
      color_accent: "#6366f1",
      mrr: 0,
      active_users: 0,
      owner_persona: "cfo",
      url: "https://axiomfolio.com",
      admin_url: "/admin/products/axiomfolio",
      pricing_tiers: [
        {
          id: "starter",
          name: "Starter",
          price_monthly_usd: 0,
          blurb: "Paper trading and core portfolio views",
        },
        {
          id: "pro",
          name: "Pro",
          price_monthly_usd: 49,
          blurb: "Live accounts, automation, and advanced risk",
        },
        {
          id: "enterprise",
          name: "Enterprise",
          price_monthly_usd: null,
          blurb: "SSO, dedicated support, and custom workflows",
        },
      ],
    },
  },
  {
    id: "distill",
    name: "Distill Tax",
    tagline: "Knowledge distillation",
    status: "alpha",
    domain: "distill.tax",
    repo_path: "apps/distill",
    vercel_project: "distill",
    metadata: {
      color_accent: "#8b5cf6",
      mrr: 0,
      active_users: 0,
      owner_persona: "brain",
      admin_url: "/admin/products/distill",
      pricing_tiers: [],
    },
  },
  {
    id: "filefree",
    name: "FileFree",
    tagline: "Smart document management",
    status: "alpha",
    domain: "filefree.app",
    repo_path: "apps/filefree",
    vercel_project: "filefree",
    metadata: {
      color_accent: "#06b6d4",
      mrr: 0,
      active_users: 0,
      owner_persona: "founder",
      url: "https://filefree.com",
      admin_url: "/admin/products/filefree",
      pricing_tiers: [],
    },
  },
  {
    id: "launchfree",
    name: "LaunchFree",
    tagline: "Launch your business fast",
    status: "alpha",
    domain: null,
    repo_path: "apps/launchfree",
    vercel_project: "launchfree",
    metadata: {
      color_accent: "#f59e0b",
      mrr: 0,
      active_users: 0,
      owner_persona: "founder",
      url: "https://launchfree.com",
      admin_url: "/admin/products/launchfree",
      pricing_tiers: [],
    },
  },
  {
    id: "studio",
    name: "Studio (HQ)",
    tagline: "Company HQ",
    status: "beta",
    domain: "paperworklabs.com",
    repo_path: "apps/studio",
    vercel_project: "studio",
    metadata: {
      color_accent: "#10b981",
      mrr: 0,
      active_users: 1,
      owner_persona: "founder",
      url: "https://paperworklabs.com",
      admin_url: "/admin",
      pricing_tiers: [
        {
          id: "internal",
          name: "Internal",
          price_monthly_usd: 0,
          blurb: "Operator workspace — not customer-priced",
        },
      ],
    },
  },
  {
    id: "trinkets",
    name: "Trinkets",
    tagline: "Digital collectibles",
    status: "concept",
    domain: null,
    repo_path: "apps/trinkets",
    vercel_project: "trinkets",
    metadata: {
      color_accent: "#ec4899",
      mrr: 0,
      active_users: 0,
      owner_persona: "founder",
      admin_url: "/admin/products/trinkets",
      pricing_tiers: [],
    },
  },
];

async function main(): Promise<void> {
  const root = brainApiV1Root();
  const secret = sanitizeEnv(process.env.BRAIN_API_SECRET);
  if (!root) die("error: BRAIN_API_URL is not set (or is empty).");
  if (!secret) die("error: BRAIN_API_SECRET is not set (or is empty).");

  for (const row of SEED_PRODUCTS) {
    try {
      await postOrPutProduct(root, secret, row);
      console.log(`product ${row.id}: ok`);
    } catch (e) {
      die(
        `error: Brain rejected ${row.id} — ${e instanceof Error ? e.message : String(e)}`,
      );
    }
  }
  console.log("seed-products: complete");
}

main().catch((e) => {
  die(`error: ${e instanceof Error ? e.message : String(e)}`);
});
