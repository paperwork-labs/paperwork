import { describe, expect, it } from "vitest";
import { parseWorkspaceSnapshotFromMarketDataResponse } from "../src/types/workspaceSnapshot";

describe("lab + market/workspace (batch F follow-up)", () => {
  it("normalizes market snapshot response shapes", () => {
    const nested = { data: { data: { snapshot: { rsi: 55, beta: 1.1 } } } } as const;
    const snap = parseWorkspaceSnapshotFromMarketDataResponse(nested);
    expect(snap).toEqual({ rsi: 55, beta: 1.1 });
    const dSnap = { data: { snapshot: { stage_label: "2" } } } as const;
    expect(parseWorkspaceSnapshotFromMarketDataResponse(dSnap)).toEqual({ stage_label: "2" });
    const flat = { data: { rsi: 30 } } as const;
    expect(parseWorkspaceSnapshotFromMarketDataResponse(flat)).toEqual({ rsi: 30 });
    expect(parseWorkspaceSnapshotFromMarketDataResponse(null)).toBeNull();
  });

  it("resolves app route module defaults", async () => {
    const lab = await import("../src/app/lab/page");
    const workspace = await import("../src/app/market/workspace/page");
    const monte = await import("../src/app/lab/monte-carlo/page");
    expect(lab.default).toBeTypeOf("function");
    expect(workspace.default).toBeTypeOf("function");
    expect(monte.default).toBeTypeOf("function");
  });
});
