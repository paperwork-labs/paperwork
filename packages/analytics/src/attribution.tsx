"use client";

import { useEffect } from "react";
import { posthog } from "./posthog";

const UTM_KEYS = [
  "utm_source",
  "utm_medium",
  "utm_campaign",
  "utm_content",
  "utm_term",
] as const;

const STORAGE_KEY = "filefree_attribution";

export interface Attribution {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  utm_content?: string;
  utm_term?: string;
  referral_code?: string;
  landing_page?: string;
  captured_at?: string;
}

function captureAttribution(): void {
  if (typeof window === "undefined") return;

  const existing = sessionStorage.getItem(STORAGE_KEY);
  if (existing) return;

  const params = new URLSearchParams(window.location.search);
  const attribution: Attribution = {};
  let hasData = false;

  for (const key of UTM_KEYS) {
    const value = params.get(key);
    if (value) {
      attribution[key] = value;
      hasData = true;
    }
  }

  const ref = params.get("ref");
  if (ref) {
    attribution.referral_code = ref;
    hasData = true;
  }

  attribution.landing_page = window.location.pathname;
  attribution.captured_at = new Date().toISOString();

  if (hasData || attribution.landing_page !== "/") {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(attribution));
  }
}

export function getAttribution(): Attribution {
  if (typeof window === "undefined") return {};

  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : {};
  } catch {
    return {};
  }
}

export function AttributionProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    captureAttribution();
    const attribution = getAttribution();
    if (Object.keys(attribution).length > 0) {
      posthog.register(attribution);
    }
  }, []);

  return children;
}
