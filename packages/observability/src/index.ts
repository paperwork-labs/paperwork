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
}

type BrainEnv = "production" | "preview";
type Severity = "error" | "warning";

type ObservabilityConfig = {
  product: string;
  brainUrl: string;
  brainToken: string;
  env: BrainEnv;
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
    const response = await fetch(`${active.brainUrl}/v1/errors/ingest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${active.brainToken}`,
      },
      body: JSON.stringify(payload),
      keepalive: true,
    });
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
