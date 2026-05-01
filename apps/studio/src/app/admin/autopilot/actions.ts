"use server";

import { revalidatePath } from "next/cache";

import { getBrainAdminFetchOptions } from "@/lib/brain-admin-proxy";

export async function approveDispatch(taskId: string): Promise<{ ok: boolean; error?: string }> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return { ok: false, error: "Brain API not configured" };

  try {
    const res = await fetch(`${auth.root}/admin/dispatch/${taskId}/approve`, {
      method: "POST",
      headers: {
        "X-Brain-Secret": auth.secret,
        "Content-Type": "application/json",
      },
    });

    if (!res.ok) {
      const body = await res.text();
      return { ok: false, error: `Brain API returned ${res.status}: ${body}` };
    }

    revalidatePath("/admin/autopilot");
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Unknown error" };
  }
}

export async function vetoDispatch(
  taskId: string,
  reason: string,
): Promise<{ ok: boolean; error?: string }> {
  const auth = getBrainAdminFetchOptions();
  if (!auth.ok) return { ok: false, error: "Brain API not configured" };

  try {
    const res = await fetch(`${auth.root}/admin/dispatch/${taskId}/veto`, {
      method: "POST",
      headers: {
        "X-Brain-Secret": auth.secret,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ reason }),
    });

    if (!res.ok) {
      const body = await res.text();
      return { ok: false, error: `Brain API returned ${res.status}: ${body}` };
    }

    revalidatePath("/admin/autopilot");
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Unknown error" };
  }
}
