"use server";

import { revalidatePath } from "next/cache";

import {
  type CreateGoalInput,
  type UpdateGoalInput,
  archiveGoal,
  createGoal,
  updateGoal,
  updateKRProgress,
} from "@/lib/brain-client";

export type ActionResult = { ok: true } | { ok: false; error: string };

export async function createGoalAction(input: CreateGoalInput): Promise<ActionResult> {
  try {
    await createGoal(input);
    revalidatePath("/admin/goals");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Unknown error" };
  }
}

export async function updateGoalAction(
  goalId: string,
  input: UpdateGoalInput,
): Promise<ActionResult> {
  try {
    await updateGoal(goalId, input);
    revalidatePath("/admin/goals");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Unknown error" };
  }
}

export async function archiveGoalAction(goalId: string): Promise<ActionResult> {
  try {
    await archiveGoal(goalId);
    revalidatePath("/admin/goals");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Unknown error" };
  }
}

export async function updateKRProgressAction(
  goalId: string,
  krId: string,
  currentValue: number,
  note?: string | null,
): Promise<ActionResult> {
  try {
    await updateKRProgress(goalId, krId, currentValue, note);
    revalidatePath("/admin/goals");
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "Unknown error" };
  }
}
