export interface ServiceCheck {
  name: string;
  url: string;
  dashboardUrl: string;
  accessHint: string;
  status: "healthy" | "degraded" | "down" | "unknown";
  latencyMs: number | null;
  details?: Record<string, unknown>;
  checkedAt: string;
  category: "core" | "ops" | "analytics" | "ci";
}

export interface N8nWorkflow {
  id: string;
  name: string;
  active: boolean;
  updatedAt: string;
}

export interface CIRun {
  name: string;
  conclusion: string | null;
  status: string;
  updatedAt: string;
  url: string;
}

export interface OpsData {
  services: ServiceCheck[];
  workflows: N8nWorkflow[];
  ciRuns: CIRun[];
  checkedAt: string;
}
