/**
 * Historical display metadata for legacy n8n shadow job ids. Brain retired the
 * mirror module (`chore/brain-delete-legacy-owns-flags`); the admin API returns
 * `retired: true` with an empty `per_job` list.
 */
export type N8nMirrorSpecMeta = {
  n8n_workflow_name: string;
  schedule: string;
  trigger_type: "cron" | "interval";
};

/** Legacy: job ids that once had a `BRAIN_OWNS_*` cutover path (mirror removed). */
export const N8N_MIRROR_CUTOVER_JOB_IDS = new Set([
  "n8n_shadow_brain_daily",
  "n8n_shadow_infra_heartbeat",
  "n8n_shadow_weekly_strategy",
  "n8n_shadow_infra_health",
]);

export const N8N_MIRROR_SPEC_META: Record<string, N8nMirrorSpecMeta> = {
  n8n_shadow_brain_daily: {
    n8n_workflow_name: "Brain Daily Trigger",
    schedule: "0 7 * * *",
    trigger_type: "cron",
  },
  n8n_shadow_brain_weekly: {
    n8n_workflow_name: "Brain Weekly Trigger",
    schedule: "0 18 * * 0",
    trigger_type: "cron",
  },
  n8n_shadow_sprint_kickoff: {
    n8n_workflow_name: "Sprint Kickoff",
    schedule: "0 7 * * 1",
    trigger_type: "cron",
  },
  n8n_shadow_sprint_close: {
    n8n_workflow_name: "Sprint Close",
    schedule: "0 21 * * 5",
    trigger_type: "cron",
  },
  n8n_shadow_weekly_strategy: {
    n8n_workflow_name: "Weekly Strategy Check-in",
    schedule: "0 9 * * 1",
    trigger_type: "cron",
  },
  n8n_shadow_infra_heartbeat: {
    n8n_workflow_name: "Infra Heartbeat",
    schedule: "0 8 * * *",
    trigger_type: "cron",
  },
  n8n_shadow_data_source_monitor: {
    n8n_workflow_name: "Data Source Monitor (P2.8)",
    schedule: "0 6 * * 1",
    trigger_type: "cron",
  },
  n8n_shadow_data_deep_validator: {
    n8n_workflow_name: "Data Deep Validator (P2.9)",
    schedule: "0 3 1 * *",
    trigger_type: "cron",
  },
  n8n_shadow_annual_data: {
    n8n_workflow_name: "Annual Data Update Trigger (P2.10)",
    schedule: "0 9 1 10 *",
    trigger_type: "cron",
  },
  n8n_shadow_infra_health: {
    n8n_workflow_name: "Infra Health Check",
    schedule: "30m",
    trigger_type: "interval",
  },
  n8n_shadow_credential_expiry: {
    n8n_workflow_name: "Credential Expiry Check",
    schedule: "0 8 * * *",
    trigger_type: "cron",
  },
};
