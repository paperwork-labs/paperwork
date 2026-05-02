/** Brain `/api/v1/admin/stats` + `/attention` payload shapes (Studio Overview). */

export type BrainAdminStats = {
  products: { total: number; active: number };
  employees: { total: number; ai: number; human: number };
  epics: { total: number; in_progress: number; completed: number; blocked: number };
  sprints: { total: number; active: number };
  conversations: { total: number; today: number };
  dispatches_today: number;
  last_dispatch_at: string | null;
};

export type BrainAdminAttention = {
  blocked_epics: { id: string; title: string; goal_objective: string }[];
  stale_sprints: {
    id: string;
    title: string;
    epic_title: string;
    last_activity_at: string | null;
  }[];
  unreplied_conversations: { id: string; title: string; updated_at: string }[];
  failed_dispatches: {
    dispatched_at?: string | null;
    persona_slug?: string | null;
    task_summary?: string | null;
    pr_number?: number | null;
  }[];
};
