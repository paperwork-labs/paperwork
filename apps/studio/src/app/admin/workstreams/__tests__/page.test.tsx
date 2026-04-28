import { describe, expect, it } from "vitest";

import workstreamsJson from "@/data/workstreams.json";
import {
  WorkstreamsFileSchema,
  computeKpis,
} from "@/lib/workstreams/schema";

import AdminWorkstreamsPage from "../page";

describe("/admin/workstreams page module", () => {
  it("parses seeded workstreams.json without error", () => {
    const file = WorkstreamsFileSchema.parse(workstreamsJson);
    const kpis = computeKpis(file);
    expect(kpis.total).toBeGreaterThan(0);
  });

  it("default export resolves to rendered markup", async () => {
    const tree = await AdminWorkstreamsPage();
    expect(tree).toBeTruthy();
  });
});
