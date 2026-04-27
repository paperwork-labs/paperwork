import type { Sprint } from "./tracker";

const PR_REF_RE = /(?:#|PR\s*#|pull\/)(\d{2,5})/i;
const SHIPPED_DATE_RE = /(?:^shipped\s+|\bshipped\s+)(\d{4}-\d{2}-\d{2})/i;
const SCROLLED_PREFIX_RE = /^(?:✅|✓|✔|⏳|⏰|⏱|🟢|🟡)\s*/u;
const STATUS_TOKEN_RE = /^(?:shipped|pending|active|paused|abandoned|deferred|dropped|planned|in_progress)\b\s*[:—-]?\s*/i;

export type TrackerItemStatus = "shipped" | "pending" | "deferred" | "dropped";

export type TrackerItem = {
  status: TrackerItemStatus;
  text: string;
  date?: string;
  pr?: number;
};

function readInlineStatus(
  line: string
): { next: string; itemStatus: TrackerItemStatus } | null {
  const m = line.match(
    /^(shipped|pending|active|paused|abandoned|deferred|dropped|planned|in_progress)\b/i
  );
  if (!m) return null;
  const t = m[1].toLowerCase();
  let itemStatus: TrackerItemStatus;
  if (t === "shipped") itemStatus = "shipped";
  else if (t === "dropped" || t === "abandoned") itemStatus = "dropped";
  else if (t === "deferred") itemStatus = "deferred";
  else itemStatus = "pending";
  const next = line.replace(STATUS_TOKEN_RE, "").trim();
  return { next, itemStatus };
}

export function classifyItem(
  raw: string,
  defaultStatus: TrackerItemStatus,
  sprintShipped: boolean
): TrackerItem {
  let text = raw.replace(SCROLLED_PREFIX_RE, "").trim();
  let status: TrackerItemStatus = defaultStatus;

  const inline = readInlineStatus(text);
  if (inline) {
    text = inline.next;
    status = inline.itemStatus;
  }

  const dateMatch = text.match(SHIPPED_DATE_RE);
  let date: string | undefined;
  if (dateMatch) {
    date = dateMatch[1];
    text = text.replace(SHIPPED_DATE_RE, "").replace(/^[\s—:–-]+/, "").trim();
  }

  let pr: number | undefined;
  const prMatch = text.match(PR_REF_RE);
  if (prMatch) {
    pr = Number(prMatch[1]);
  }

  if (sprintShipped && status === "pending") {
    status = "deferred";
  }

  return { status, text, date, pr };
}

export function buildTracker(sprint: Sprint): TrackerItem[] {
  const sprintShipped =
    sprint.status === "shipped" || sprint.effective_status === "shipped";
  const shipped = (sprint.outcome_bullets ?? []).map((line) =>
    classifyItem(line, "shipped", sprintShipped)
  );
  const pendingDefault: TrackerItemStatus = sprintShipped ? "deferred" : "pending";
  const pending = (sprint.followups ?? []).map((line) =>
    classifyItem(line, pendingDefault, sprintShipped)
  );
  const items = [...shipped, ...pending];
  const rank = (s: TrackerItem["status"]) => {
    if (s === "shipped") return 0;
    if (s === "pending") return 1;
    if (s === "deferred") return 2;
    return 3;
  };
  return items.sort((a, b) => {
    if (a.status !== b.status) return rank(a.status) - rank(b.status);
    if (a.status === "shipped") {
      const ad = a.date ?? "";
      const bd = b.date ?? "";
      if (ad && bd) return bd.localeCompare(ad);
      if (ad) return -1;
      if (bd) return 1;
    }
    return 0;
  });
}
