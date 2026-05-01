export type PersonaRegistryRow = {
  personaId: string;
  name: string;
  description: string | null;
  relativePath: string;
  modelAssignment: string | null;
  routingActive: boolean;
};

export type BrainDataSourceStatus =
  | { ok: true; path: string }
  | { ok: false; path: string; message: string };

/** Derived bucket for timeline badges (PR review vs cheap-agent dispatch vs escalation). */
export type ActivityActionType = "dispatch" | "review" | "escalate" | "unknown";

export type DispatchRecord = {
  dispatch_id?: string;
  dispatched_at?: string;
  agent_model?: string;
  persona_slug?: string;
  persona?: string;
  persona_pin?: string;
  pr_number?: number | null;
  workstream_id?: string;
  workstream_type?: string;
  task_summary?: string;
  outcome?: {
    ci_initial_pass?: boolean | null;
    review_pass?: boolean | null;
    merged_at?: string | null;
    reverted?: boolean | null;
    [key: string]: unknown;
  };
  [key: string]: unknown;
};

export type AgentDispatchFile = {
  dispatches?: DispatchRecord[];
};

export type PrOutcomeRecord = {
  pr_number?: number;
  merged_at?: string;
  merged_by_agent?: string;
  agent_model?: string;
  workstream_ids?: string[];
  workstream_types?: string[];
  outcomes?: unknown;
  tokens_input?: number;
  tokens_output?: number;
  [key: string]: unknown;
};

export type PrOutcomesFile = {
  outcomes?: PrOutcomeRecord[];
};

export type PersonaCostRow = {
  personaId: string;
  dispatch7d: number | null;
  dispatch30d: number | null;
  avgTokensPerDispatch: number | null;
  costNote: string;
};

export type CostTabPayload = {
  dispatchSource: BrainDataSourceStatus;
  outcomesSource: BrainDataSourceStatus;
  personaHasAttribution: boolean;
  attributionNote: string | null;
  avgTokensNote: string | null;
  rows: PersonaCostRow[];
  globalDispatch7d: number | null;
  globalDispatch30d: number | null;
};

export type EaRoutingRow = {
  tag: string;
  routingTarget: string;
};

export type ActivityFeedRow = {
  dispatchedAt: string;
  persona: string;
  personaDisplayName?: string;
  workstreamTag: string;
  successLabel: string;
  costLabel: string;
  actionType?: ActivityActionType;
  /** PR number or workstream id/type */
  targetLabel?: string;
  description?: string;
  prNumber?: number | null;
};

export type MarkdownTable = {
  title: string;
  headers: string[];
  rows: string[][];
};

export type OpenRoleRow = Pick<PersonaRegistryRow, "personaId" | "name" | "relativePath">;

/** KPI row for the People (personas) HQ dashboard. */
export type PeopleDashboardStats = {
  activePersonas: number;
  dispatchesToday: number;
  approvalRateLabel: string;
  /** Placeholder until WS-76 PR-10 ships real spend rollup. */
  dailyCostStatLabel: string;
};

export type PromotionsQueuePayload = {
  source: BrainDataSourceStatus;
  /** Normalized rows from `apis/brain/data/self_merge_promotions.json` promotions array. */
  promotions: Record<string, unknown>[];
};

export type SelfMergePromotionsFile = {
  promotions?: unknown[];
  [key: string]: unknown;
};

export type PersonasPagePayload = {
  repoRoot: string;
  dashboard: PeopleDashboardStats;
  registry: PersonaRegistryRow[];
  openRoles: OpenRoleRow[];
  promotions: PromotionsQueuePayload;
  cost: CostTabPayload;
  routing: { source: BrainDataSourceStatus; rows: EaRoutingRow[] };
  activity: {
    source: BrainDataSourceStatus;
    rows: ActivityFeedRow[];
    note: string | null;
  };
  modelRegistry: { source: BrainDataSourceStatus; tables: MarkdownTable[] };
  /**
   * Non-null when BRAIN_API_URL is configured but the request failed.
   * Pages should render an error banner. Null means no error.
   */
  brainApiError?: string | null;
};

