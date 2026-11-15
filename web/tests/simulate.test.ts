import { describe, expect, it } from "vitest";
import { simulate, sensitivity } from "../src/lib/simulate";
import { money } from "../src/lib/format";

describe("simulator", () => {
  const rows = [{ product_id: "X", qty_per_unit: 4, planned_volume: 10000 }];
  it("qty 4, 0.50 -> 0.40, 10,000 units = -4,000", () => {
    expect(simulate(rows, 0.5, 0.4, 1).total).toBeCloseTo(-4000, 6);
  });
  it("an increase is positive", () => {
    expect(simulate(rows, 0.5, 0.6, 1).total!).toBeGreaterThan(0);
  });
  it("50% share halves it", () => {
    expect(simulate(rows, 0.5, 0.4, 0.5).total).toBeCloseTo(-2000, 6);
  });
  it("no volumes: per-unit only", () => {
    const r = simulate([{ product_id: "X", qty_per_unit: 4, planned_volume: null }], 0.5, 0.4, 1);
    expect(r.perUnitOnly).toBe(true);
    expect(r.rows[0].change_per_unit).toBeCloseTo(-0.4, 9);
  });
  it("sensitivity passes through zero at the baseline", () => {
    const pts = sensitivity(rows, 0.5, 1, 0.25, 0.75, 2);
    expect(pts[1][1]).toBeCloseTo(0, 9);
  });
});

describe("format", () => {
  it("formats negative money with a real minus", () => {
    expect(money(-400000, "USD")).toContain("−");
  });
});
