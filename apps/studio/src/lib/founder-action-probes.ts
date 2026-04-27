/**
 * Live HTTP probes for founder-action verification URLs (Studio server only).
 * Keeps the Founder Actions page honest vs stale markdown.
 */

const URL_RE = /https:\/\/[^\s\)`'"<>]+/g;

export type ProbeResult = {
  url: string;
  ok: boolean;
  status: number;
  error?: string;
};

export function extractVerificationUrls(text: string): string[] {
  const m = text.match(URL_RE);
  if (!m?.length) return [];
  return [...new Set(m.map((u) => u.replace(/[.,;]+$/, "")))];
}

export async function probeHead(url: string, ms = 6000): Promise<ProbeResult> {
  const run = async (method: "HEAD" | "GET") => {
    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), ms);
    try {
      const res = await fetch(url, {
        method,
        signal: ac.signal,
        redirect: "follow",
        cache: "no-store",
      });
      clearTimeout(t);
      return res;
    } catch (e) {
      clearTimeout(t);
      throw e;
    }
  };
  try {
    let res = await run("HEAD");
    if (res.status === 405 || res.status === 501) {
      res = await run("GET");
    }
    return { url, ok: res.ok, status: res.status };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { url, ok: false, status: 0, error: msg };
  }
}

/** Dedupe URLs across items, probe once each, return map url → result */
export async function probeAllUrls(urls: string[]): Promise<Map<string, ProbeResult>> {
  const unique = [...new Set(urls)];
  const results = await Promise.all(unique.map((u) => probeHead(u)));
  return new Map(results.map((r) => [r.url, r]));
}
