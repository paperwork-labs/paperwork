import { cache } from "react";

import { BrainClient, BrainClientError } from "@/lib/brain-client";
import type { EpicHierarchyResponse } from "@/lib/brain-client";

import type { ProductPlansLoadResult } from "./product-hub-signals";

async function loadEpicHierarchyUncached(): Promise<ProductPlansLoadResult> {
  const client = BrainClient.fromEnv();
  if (!client) {
    return { hierarchy: null, configured: false, fetchError: null };
  }
  try {
    const hierarchy: EpicHierarchyResponse = await client.getEpicHierarchy();
    return { hierarchy, configured: true, fetchError: null };
  } catch (e) {
    const msg =
      e instanceof BrainClientError
        ? e.message
        : e instanceof Error
          ? e.message
          : "Brain unreachable";
    return { hierarchy: null, configured: true, fetchError: msg };
  }
}

async function loadEpicHierarchyForProductUncached(slug: string): Promise<ProductPlansLoadResult> {
  const client = BrainClient.fromEnv();
  if (!client) {
    return { hierarchy: null, configured: false, fetchError: null };
  }
  try {
    const hierarchy: EpicHierarchyResponse = await client.getEpicHierarchyForProduct(slug);
    return { hierarchy, configured: true, fetchError: null };
  } catch (e) {
    const msg =
      e instanceof BrainClientError
        ? e.message
        : e instanceof Error
          ? e.message
          : "Brain unreachable";
    return { hierarchy: null, configured: true, fetchError: msg };
  }
}

/** One Brain round-trip per request (deduped across RSC callers). */
export const loadProductPlansBrainState = cache(loadEpicHierarchyUncached);

/** Product-scoped epic tree (smaller payload than full hierarchy). */
export const loadProductPlansBrainStateForSlug = cache((slug: string) =>
  loadEpicHierarchyForProductUncached(slug),
);
