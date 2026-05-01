export interface CaptureContext {
  product: string;
  env?: "production" | "preview" | "development";
  user?: { id?: string; email?: string };
  context?: Record<string, unknown>;
}

export interface ObservabilityOptions {
  product: string;
  brainUrl: string;
  brainToken: string;
  env?: string;
  memoryReportPath?: string;
}

type BrainEnv = "production" | "preview";
type Severity = "error" | "warning";

type ObservabilityConfig = {
  product: string;
  brainUrl: string;
  brainToken: string;
  env: BrainEnv;
  memoryReportPath?: string;
};

type ErrorPayload = {
  product: string;
  env: BrainEnv;
  message: string;
  stack?: string;
  url?: string;
  user_agent?: string;
  severity: Severity;
  context?: Record<string, unknown>;
};

let config: ObservabilityConfig | null = null;
let handlersInstalled = false;

function toBrainEnv(env: string | undefined): BrainEnv {
  return env === "production" ? "production" : "preview";
}

function normalizeBrainUrl(brainUrl: string): string {
  return brainUrl.trim().replace(/\/+$/, "");
}

function errorParts(err: Error | string): { message: string; stack?: string } {
  if (err instanceof Error) {
    return { message: err.message || err.name, stack: err.stack };
  }
  return { message: err };
}

function browserContext(extra?: Record<string, unknown>): Record<string, unknown> {
  const ctx: Record<string, unknown> = { ...(extra ?? {}) };
  if (typeof window !== "undefined") {
    ctx.location = window.location.href;
  }
  return ctx;
}

function currentUrl(): string | undefined {
  if (typeof window === "undefined") return undefined;
  return window.location.href;
}

function currentUserAgent(): string | undefined {
  if (typeof navigator === "undefined") return undefined;
  return navigator.userAgent;
}

function fingerprintForMemoryReport(p: ErrorPayload): string {
  const raw = `${p.product}|${p.message}|${p.stack ?? ""}|${p.url ?? ""}`;
  let h = 0;
  for (let i = 0; i < raw.length; i++) h = (Math.imul(31, h) + raw.charCodeAt(i)) | 0;
  const unsigned = h >>> 0;
  const hex = unsigned.toString(16);
  return `fp:${p.product}:${hex}`.slice(0, 200);
}

async function postMemoryEpisodeFromPayload(payload: ErrorPayload): Promise<void> {
  const active = config;
  const path = active?.memoryReportPath?.trim();
  if (!path || typeof window === "undefined") {
    return;
  }
  try {
    const envLabel = payload.env === "production" ? "production" : "preview";
    const body = {
      source: payload.product,
      summary: payload.message.slice(0, 500),
      fingerprint: fingerprintForMemoryReport(payload),
      environment: envLabel,
      severity: payload.severity === "warning" ? "warning" : "error",
      url: payload.url,
      user_agent: payload.user_agent,
      stack: payload.stack?.slice(0, 4000),
      metadata: payload.context,
    };
    const response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive: true,
    });
    if (!response.ok) {
      console.error(
        `@paperwork/observability memory report responded ${response.status} ${response.statusText}`,
      );
    }
  } catch (err) {
    console.error("@paperwork/observability memory report failed.", err);
  }
}

async function postError(payload: ErrorPayload): Promise<void> {
  const active = config;
  if (!active) {
    console.error("@paperwork/observability is not initialized; dropping captured error.");
    return;
  }
  if (!active.brainUrl || !active.brainToken) {
    console.error(
      "@paperwork/observability missing brainUrl or brainToken; dropping captured error.",
    );
    return;
  }
  if (typeof fetch !== "function") {
    console.error("@paperwork/observability requires fetch; dropping captured error.");
    return;
  }

  try {
    const memoryOp = postMemoryEpisodeFromPayload(payload);
    const response = await fetch(`${active.brainUrl}/v1/errors/ingest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${active.brainToken}`,
      },
      body: JSON.stringify(payload),
      keepalive: true,
    });
    await memoryOp;
    if (!response.ok) {
      console.error(
        `@paperwork/observability failed to capture error: ${response.status} ${response.statusText}`,
      );
    }
  } catch (err) {
    console.error("@paperwork/observability failed to capture error.", err);
  }
}

function installBrowserHandlers(): void {
  if (handlersInstalled || typeof window === "undefined") return;
  handlersInstalled = true;

  window.addEventListener("error", (event) => {
    const err = event.error instanceof Error ? event.error : String(event.message);
    captureError(err, {
      context: browserContext({
        source: event.filename,
        lineno: event.lineno,
        colno: event.colno,
      }),
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason instanceof Error ? event.reason : String(event.reason);
    captureError(reason, {
      context: browserContext({ type: "unhandledrejection" }),
    });
  });
}

export function initObservability(opts: ObservabilityOptions): void {
  config = {
    product: opts.product,
    brainUrl: normalizeBrainUrl(opts.brainUrl),
    brainToken: opts.brainToken.trim(),
    env: toBrainEnv(opts.env),
    memoryReportPath: opts.memoryReportPath?.trim() || undefined,
  };

  if (!config.brainUrl || !config.brainToken) {
    console.error(
      "@paperwork/observability initialized without brainUrl or brainToken; captures will be dropped.",
    );
  }

  installBrowserHandlers();
}

export function captureError(err: Error | string, ctx?: Partial<CaptureContext>): void {
  try {
    const active = config;
    const parts = errorParts(err);
    const product = ctx?.product ?? active?.product;
    if (!product) {
      console.error("@paperwork/observability capture missing product; dropping captured error.");
      return;
    }

    const context: Record<string, unknown> = {
      ...(ctx?.context ?? {}),
    };
    if (ctx?.user) {
      context.user = ctx.user;
    }

    void postError({
      product,
      env: toBrainEnv(ctx?.env ?? active?.env),
      message: parts.message,
      stack: parts.stack,
      url: currentUrl(),
      user_agent: currentUserAgent(),
      severity: "error",
      context: Object.keys(context).length > 0 ? context : undefined,
    });
  } catch (captureFailure) {
    console.error("@paperwork/observability captureError failed.", captureFailure);
  }
}
