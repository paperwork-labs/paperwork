export interface CoverageHistoryEntry {
  ts?: string | null;
  daily_pct?: number | string | null;
  m5_pct?: number | string | null;
  stale_daily?: number | string | null;
  stale_m5?: number | string | null;
}

export interface CoverageSparkline {
  daily_pct: number[];
  m5_pct: number[];
  labels: Array<string | null | undefined>;
  stale_daily?: number[];
  stale_m5?: number[];
}

export interface CoverageKpi {
  id: string;
  label: string;
  value: number | string | null | undefined;
  unit?: string;
  help?: string;
}

export interface CoverageAction {
  label: string;
  task_name: string;
  description?: string;
  disabled?: boolean;
}

export interface CoverageBucket {
  label: string;
  count: number;
}

export interface CoverageBucketGroup {
  interval: 'daily' | 'm5';
  title: string;
  buckets: CoverageBucket[];
}

export interface CoverageHeroMeta {
  statusLabel: string;
  statusColor: string;
  summary: string;
  updatedAtIso?: string | null;
  updatedDisplay: string;
  updatedRelative: string;
  source?: string;
  snapshotAgeSeconds?: number | null;
  isSnapshotStale: boolean;
  staleCounts: { daily: number; m5: number };
  trackedCount: number;
  totalSymbols: number;
  historySamples: number;
  buckets: CoverageBucketGroup[];
  warningBanner?: {
    status: 'warning' | 'error' | 'info';
    title: string;
    description?: string;
  } | null;
  sla?: { daily_pct?: number; m5_expectation?: string };
}

const emptySparkline: CoverageSparkline = {
  daily_pct: [],
  m5_pct: [],
  labels: [],
  stale_daily: [],
  stale_m5: [],
};

const STATUS_COLOR_MAP: Record<string, string> = {
  ok: 'green',
  warning: 'yellow',
  idle: 'gray',
  degraded: 'orange',
  error: 'red',
};

const DEFAULT_COVERAGE_ACTIONS: CoverageAction[] = [
  {
    label: 'Restore Daily Coverage (Tracked)',
    task_name: 'admin_coverage_restore',
    description:
      'Guided operator flow: refresh → tracked → daily backfill → recompute → history → refresh coverage (no 5m). Endpoint: POST /api/v1/market-data/admin/coverage/restore',
  },
  {
    label: 'Backfill Daily (Stale Only)',
    task_name: 'admin_coverage_backfill_stale',
    description:
      'Backfills daily bars only for symbols currently stale in coverage snapshot. Endpoint: POST /api/v1/market-data/admin/coverage/backfill-stale',
  },
  {
    label: 'Refresh Coverage Cache',
    task_name: 'admin_coverage_refresh',
    description:
      'Recomputes and caches the coverage snapshot. Endpoint: POST /api/v1/market-data/admin/coverage/refresh',
  },
  {
    label: 'Recompute Indicators',
    task_name: 'admin_indicators_recompute_universe',
    description:
      'Builds DB snapshots for the tracked universe. Endpoint: POST /api/v1/market-data/admin/indicators/recompute-universe',
  },
  {
    label: 'Record History',
    task_name: 'admin_snapshots_history_record',
    description:
      'Writes immutable MarketSnapshotHistory rows. Endpoint: POST /api/v1/market-data/admin/snapshots/history/record',
  },
];

const BUCKET_ORDER = ['<=24h', '24-48h', '>48h', 'none'];

export const deriveSparklineSeries = (
  metaSeries?: CoverageSparkline | null,
  history?: CoverageHistoryEntry[] | null,
): CoverageSparkline => {
  if (metaSeries && Array.isArray(metaSeries.daily_pct)) {
    return {
      daily_pct: [...metaSeries.daily_pct],
      m5_pct: [...(metaSeries.m5_pct || [])],
      labels: [...(metaSeries.labels || [])],
      stale_daily: [...(metaSeries.stale_daily || [])],
      stale_m5: [...(metaSeries.stale_m5 || [])],
    };
  }

  const list = Array.isArray(history) ? history : [];
  if (list.length === 0) {
    return emptySparkline;
  }

  return {
    daily_pct: list.map((entry) => Number(entry?.daily_pct ?? 0)),
    m5_pct: list.map((entry) => Number(entry?.m5_pct ?? 0)),
    labels: list.map((entry) => entry?.ts),
    stale_daily: list.map((entry) => Number(entry?.stale_daily ?? 0)),
    stale_m5: list.map((entry) => Number(entry?.stale_m5 ?? 0)),
  };
};

export const buildCoverageKpis = (
  metaKpis?: CoverageKpi[] | null,
  snapshot?: any,
  status?: any,
): CoverageKpi[] => {
  if (Array.isArray(metaKpis) && metaKpis.length > 0) {
    return metaKpis;
  }
  const statusInfo = status || {};
  const staleM5 = Number(statusInfo.stale_m5 ?? 0);
  const totalSymbols = Number(snapshot?.symbols ?? 0);
  const dailyCount = Number(snapshot?.daily?.count ?? 0);
  const m5Count = Number(snapshot?.m5?.count ?? 0);
  const expectedDate = statusInfo.daily_expected_date ? String(statusInfo.daily_expected_date) : null;
  return [
    {
      id: 'tracked',
      label: 'Tracked Symbols',
      value: snapshot?.tracked_count ?? 0,
      help: 'Universe size',
    },
    {
      id: 'daily_pct',
      label: 'Daily Coverage %',
      value: statusInfo.daily_pct ?? 0,
      unit: '%',
      help: expectedDate
        ? `Latest trading day: ${expectedDate}`
        : `${dailyCount} / ${totalSymbols || '—'} bars`,
    },
    {
      id: 'm5_pct',
      label: '5m Coverage %',
      value: statusInfo.m5_pct ?? 0,
      unit: '%',
      help: `${m5Count} / ${totalSymbols || '—'} bars`,
    },
    {
      id: 'stale_daily',
      label: 'Stale (>48h)',
      value: statusInfo.stale_daily ?? 0,
      help: staleM5 === 0 ? 'All 5m covered' : `${staleM5} missing 5m`,
    },
  ];
};

export const getCoverageStatusColor = (label?: string | null): string => {
  if (!label) return 'orange';
  return STATUS_COLOR_MAP[label.toLowerCase()] || 'orange';
};

export const buildCoverageActions = (metaActions?: CoverageAction[] | null): CoverageAction[] => {
  const result: CoverageAction[] = [];
  const seen = new Set<string>();

  const pushUnique = (action?: CoverageAction | null) => {
    if (!action || !action.task_name) return;
    if (seen.has(action.task_name)) return;
    seen.add(action.task_name);
    result.push(action);
  };

  (metaActions || []).forEach(pushUnique);
  DEFAULT_COVERAGE_ACTIONS.forEach(pushUnique);
  return result;
};

const buildBuckets = (interval: 'daily' | 'm5', freshness?: Record<string, number>): CoverageBucketGroup => {
  const safe = freshness || {};
  return {
    interval,
    title: interval === 'daily' ? 'Daily Freshness' : '5m Freshness',
    buckets: BUCKET_ORDER.map((label) => ({
      label,
      count: typeof safe[label] === 'number' ? safe[label] : 0,
    })),
  };
};

const formatRelativeAge = (seconds?: number | null): string => {
  if (seconds === undefined || seconds === null) return 'unknown age';
  if (seconds < 60) return `${Math.round(seconds)}s ago`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m ago`;
  const hours = seconds / 3600;
  if (hours < 24) return `${hours.toFixed(1)}h ago`;
  const days = hours / 24;
  return `${days.toFixed(1)}d ago`;
};

export const formatCoverageHero = (snapshot?: any, staleThresholdSeconds = 1800): CoverageHeroMeta => {
  const status = snapshot?.status || {};
  const label = (status.label || 'unknown').toString().toUpperCase();
  const staleDaily = Number(status.stale_daily ?? 0);
  const staleM5 = Number(status.stale_m5 ?? 0);
  const summary =
    status.summary ||
    (staleDaily > 0
      ? `${staleDaily} symbols missing the latest daily bar.`
      : staleM5 > 0
        ? `${staleM5} symbols missing 5m data.`
        : 'Coverage healthy across daily + 5m intervals.');
  const color = getCoverageStatusColor(status.label);
  const updatedAtIso = snapshot?.meta?.updated_at || snapshot?.generated_at;
  const updatedDisplay = updatedAtIso ? new Date(updatedAtIso).toLocaleString() : '—';
  const providedAgeSeconds = snapshot?.meta?.snapshot_age_seconds;
  const fallbackAgeSeconds =
    updatedAtIso && typeof Date !== 'undefined'
      ? Math.max(0, (Date.now() - new Date(updatedAtIso).getTime()) / 1000)
      : null;
  const snapshotAgeSeconds =
    typeof providedAgeSeconds === 'number' ? providedAgeSeconds : fallbackAgeSeconds;
  const updatedRelative = updatedAtIso ? formatRelativeAge(snapshotAgeSeconds) : 'unknown age';
  const staleCounts = {
    daily: Number(status.stale_daily ?? 0),
    m5: Number(status.stale_m5 ?? 0),
  };
  const trackedCount = Number(snapshot?.tracked_count ?? 0);
  const totalSymbols = Number(snapshot?.symbols ?? 0);
  const historySamples = Array.isArray(snapshot?.history)
    ? snapshot.history.length
    : Array.isArray(snapshot?.meta?.history)
      ? snapshot.meta.history.length
      : 0;
  const isSnapshotStale = typeof snapshotAgeSeconds === 'number' && snapshotAgeSeconds > staleThresholdSeconds;
  const buckets = [
    buildBuckets('daily', snapshot?.daily?.freshness),
    buildBuckets('m5', snapshot?.m5?.freshness),
  ];

  const bannerBase =
    status.label === 'degraded'
      ? { status: 'error' as const, title: 'Coverage degraded', description: summary }
      : status.label === 'warning'
        ? { status: 'warning' as const, title: 'Coverage warning', description: summary }
        : null;

  const warningBanner = isSnapshotStale
    ? {
      status: 'warning' as const,
      title: 'Snapshot is stale',
      description: `Last refreshed ${updatedDisplay} (${updatedRelative}).`,
    }
    : bannerBase;

  return {
    statusLabel: label,
    statusColor: color,
    summary,
    updatedAtIso,
    updatedDisplay,
    updatedRelative,
    source: snapshot?.meta?.source || 'db',
    snapshotAgeSeconds,
    isSnapshotStale,
    staleCounts,
    trackedCount,
    totalSymbols,
    historySamples,
    buckets,
    warningBanner,
    sla: snapshot?.meta?.sla,
  };
};

