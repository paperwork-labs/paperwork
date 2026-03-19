import type { StateCode } from "../types/common";
import type { StateSources } from "../schemas/source-registry.schema";

const sourcesCache = new Map<StateCode, StateSources>();

export function loadSources(state: StateCode, sources: StateSources): void {
  sourcesCache.set(state, sources);
}

export function getStateSources(state: StateCode): StateSources | undefined {
  return sourcesCache.get(state);
}

export function getAllSourceStates(): StateCode[] {
  return Array.from(sourcesCache.keys()).sort();
}

// Test helper: clear cache for isolation
export function clearSourcesCache(): void {
  sourcesCache.clear();
}
