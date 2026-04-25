import fs from "node:fs";
import path from "node:path";

export type CriticalDate = {
  milestone: string;
  deadline: string;
  status: string;
  notes: string;
};

export type CompanyTracker = {
  path: string;
  title: string;
  version: string | null;
  updated: string | null;
  critical_dates: CriticalDate[];
  owner: string;
};

export type Sprint = {
  slug: string;
  path: string;
  title: string;
  status: string;
  owner?: string;
  domain?: string;
  start?: string;
  end?: string;
  duration_weeks?: number;
  pr?: number | null;
  pr_url?: string | null;
  pr_state?: string;
  ships?: string[];
  personas?: string[];
};

export type Plan = {
  slug: string;
  path: string;
  title: string;
  status: string;
  owner?: string;
  doc_kind?: string;
  last_reviewed?: string;
  product: string;
};

export type Product = {
  slug: string;
  label: string;
  plans_dir: string | null;
  plans: Plan[];
};

export type TrackerIndex = {
  content_hash: string;
  company: CompanyTracker;
  sprints: Sprint[];
  products: Product[];
};

let cached: TrackerIndex | null = null;

function indexPath(): string {
  return path.resolve(process.cwd(), "src/data/tracker-index.json");
}

export function loadTrackerIndex(): TrackerIndex {
  if (cached) return cached;
  const raw = fs.readFileSync(indexPath(), "utf-8");
  cached = JSON.parse(raw) as TrackerIndex;
  return cached;
}

export function findProduct(slug: string): Product | undefined {
  return loadTrackerIndex().products.find((p) => p.slug === slug);
}

export function activeSprints(): Sprint[] {
  return loadTrackerIndex().sprints.filter((s) => s.status === "active");
}

export function shippedSprints(): Sprint[] {
  return loadTrackerIndex().sprints.filter((s) => s.status === "shipped");
}
