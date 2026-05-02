/**
 * Client-side calls → Studio `/api/admin/epics/*` → Brain `/api/v1/admin/*`.
 */

export async function epicHierarchyBrainFetch(
  pathSegments: string[],
  init: RequestInit,
): Promise<Response> {
  const path = pathSegments.map(encodeURIComponent).join("/");
  return fetch(`/api/admin/epics/${path}`, init);
}

export function messageFromBrainJson(body: unknown, status: number, fallback?: string): string {
  if (fallback && fallback.trim()) return fallback;
  if (typeof body !== "object" || body === null) {
    return `Request failed (HTTP ${status})`;
  }
  const obj = body as Record<string, unknown>;
  const err = obj.error ?? obj.detail ?? obj.message;
  if (typeof err === "string" && err.trim()) return err;
  if (
    typeof obj.detail === "object" &&
    obj.detail !== null &&
    "msg" in (obj.detail as object)
  ) {
    const m = (obj.detail as Record<string, unknown>).msg;
    if (typeof m === "string") return m;
  }
  return `Request failed (HTTP ${status})`;
}

export async function parseBrainProxyResponse(res: Response): Promise<unknown> {
  const text = await res.text().catch(() => "");
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

export async function epicHierarchyMutateJson(
  pathSegments: string[],
  method: string,
  jsonBody?: unknown,
): Promise<{ ok: boolean; status: number; body: unknown; errorMessage?: string }> {
  const init: RequestInit = { method, cache: "no-store" };
  if (jsonBody !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(jsonBody);
  }
  const res = await epicHierarchyBrainFetch(pathSegments, init);
  const body = await parseBrainProxyResponse(res);
  if (!res.ok) {
    return {
      ok: false,
      status: res.status,
      body,
      errorMessage: messageFromBrainJson(body, res.status),
    };
  }
  if (
    typeof body === "object" &&
    body !== null &&
    "success" in body &&
    (body as { success: boolean }).success === false
  ) {
    return {
      ok: false,
      status: res.status,
      body,
      errorMessage: messageFromBrainJson(body, res.status, (body as { error?: string }).error),
    };
  }
  return { ok: true, status: res.status, body };
}
