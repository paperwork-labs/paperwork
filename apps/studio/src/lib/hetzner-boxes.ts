export type HetznerBox = {
  hostname: string;
  plan: string;
  vcpus: number;
  memoryGb: number;
  diskGb: number;
  ip: string;
  role: string;
  monthlyCostEur: number;
  dockerServices: string[];
  composeFile: string;
};

export const HETZNER_BOXES: HetznerBox[] = [
  {
    hostname: "paperwork-ops",
    plan: "CX33",
    vcpus: 4,
    memoryGb: 8,
    diskGb: 80,
    ip: "204.168.147.100",
    role: "State + Social: Postgres, Redis, Postiz, Temporal",
    monthlyCostEur: 4.51,
    dockerServices: ["postgres", "redis", "postiz", "temporal", "caddy"],
    composeFile: "infra/hetzner/compose.yaml",
  },
  {
    hostname: "paperwork-builders",
    plan: "CX43",
    vcpus: 8,
    memoryGb: 16,
    diskGb: 160,
    ip: "89.167.34.68",
    role: "CI: GHA self-hosted runners, snapshot cron",
    monthlyCostEur: 7.49,
    dockerServices: ["gha-runner-1", "gha-runner-2", "gha-runner-3", "gha-runner-4", "gha-runner-5"],
    composeFile: "infra/hetzner-build/compose.yaml",
  },
  {
    hostname: "paperwork-workers",
    plan: "CX43",
    vcpus: 8,
    memoryGb: 16,
    diskGb: 160,
    ip: "204.168.165.156",
    role: "Brain background: schedulers, dispatcher, transcript ingest",
    monthlyCostEur: 7.49,
    dockerServices: [],
    composeFile: "infra/hetzner-workers/compose.yaml",
  },
];

export const HETZNER_TOTAL_MONTHLY_EUR = HETZNER_BOXES.reduce((sum, b) => sum + b.monthlyCostEur, 0);
