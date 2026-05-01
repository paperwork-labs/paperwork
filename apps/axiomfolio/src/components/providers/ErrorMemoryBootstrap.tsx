"use client";

import * as React from "react";

import { errorFingerprint, reportError } from "@/lib/error-reporter";

function captureEnv(): string {
  if (process.env.NODE_ENV !== "production") return "dev";
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host === "localhost" || host.endsWith(".vercel.app")) return "preview";
  }
  return "production";
}

export function ErrorMemoryBootstrap(): null {
  React.useEffect(() => {
    const environment = captureEnv();

    const onWindowError = (event: ErrorEvent) => {
      const err = event.error;
      const message =
        err instanceof Error ? err.message || err.name : String(event.message ?? "window.error");
      const stack = err instanceof Error ? err.stack : undefined;
      void reportError({
        source: "axiomfolio",
        summary: message.slice(0, 500),
        fingerprint: errorFingerprint({
          source: "axiomfolio",
          message,
          stack,
          url: window.location.href,
        }),
        environment,
        severity: "error",
        url: window.location.href,
        user_agent: navigator.userAgent,
        stack: stack?.slice(0, 4000) ?? null,
        metadata: {
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno,
        },
      });
    };

    const onUnhandled = (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      const message =
        reason instanceof Error ? reason.message || reason.name : String(reason ?? "rejection");
      const stack = reason instanceof Error ? reason.stack : undefined;
      void reportError({
        source: "axiomfolio",
        summary: message.slice(0, 500),
        fingerprint: errorFingerprint({
          source: "axiomfolio",
          message,
          stack,
          url: window.location.href,
        }),
        environment,
        severity: "error",
        url: window.location.href,
        user_agent: navigator.userAgent,
        stack: stack?.slice(0, 4000) ?? null,
        metadata: { type: "unhandledrejection" },
      });
    };

    window.addEventListener("error", onWindowError);
    window.addEventListener("unhandledrejection", onUnhandled);
    return () => {
      window.removeEventListener("error", onWindowError);
      window.removeEventListener("unhandledrejection", onUnhandled);
    };
  }, []);

  return null;
}
