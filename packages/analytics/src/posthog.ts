"use client";

import posthog from "posthog-js";

const POSTHOG_KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY;
const POSTHOG_HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com";

const PII_PATTERNS = [
  /\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b/g,
  /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,
];

function scrubPII(value: unknown): unknown {
  if (typeof value === "string") {
    let scrubbed = value;
    for (const pattern of PII_PATTERNS) {
      scrubbed = scrubbed.replace(pattern, "[REDACTED]");
    }
    return scrubbed;
  }

  if (Array.isArray(value)) {
    return value.map(scrubPII);
  }

  if (value && typeof value === "object") {
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value)) {
      const lk = k.toLowerCase();
      if (lk.includes("ssn") || lk.includes("password") || lk.includes("token")) {
        result[k] = "[REDACTED]";
      } else {
        result[k] = scrubPII(v);
      }
    }
    return result;
  }

  return value;
}

let initialized = false;

export function initPostHog(): void {
  if (initialized || !POSTHOG_KEY || typeof window === "undefined") return;

  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    capture_pageview: true,
    capture_pageleave: true,
    persistence: "localStorage+cookie",
    sanitize_properties: (properties) =>
      scrubPII(properties) as Record<string, unknown>,
  });

  initialized = true;
}

export { posthog };
