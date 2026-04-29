export type BrainEnvelope<T> = { success?: boolean; data?: T; error?: string };

export async function fetchSelfImprovementJson<T>(path: string): Promise<BrainEnvelope<T>> {
  const url = `/api/admin/brain/self-improvement/${path.replace(/^\/+/, "")}`;
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-store" });
  } catch {
    return { success: false, error: "Network error calling Brain proxy." };
  }
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    return { success: false, error: `Non-JSON response (HTTP ${res.status}).` };
  }
  if (!res.ok) {
    const err =
      typeof body === "object" && body !== null && "error" in body
        ? String((body as { error?: unknown }).error)
        : `HTTP ${res.status}`;
    return { success: false, error: err };
  }
  return body as BrainEnvelope<T>;
}
