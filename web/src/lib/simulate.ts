// Deterministic simulator arithmetic (mirrors api/engine/simulator.py).
export type SimRow = { product_id: string; name?: string; qty_per_unit: number; planned_volume: number | null };
export type SimOut = SimRow & { cost_per_unit_now: number; cost_per_unit_new: number; change_per_unit: number; period_change: number | null; formula: string };

export function simulate(rows: SimRow[], baseline: number, newPrice: number, share: number) {
  let total = 0;
  let hasVol = true;
  const out: SimOut[] = rows.map((r) => {
    const perUnit = r.qty_per_unit * (newPrice - baseline);
    let period: number | null = null;
    if (r.planned_volume === null || r.planned_volume === undefined || Number.isNaN(r.planned_volume)) hasVol = false;
    else {
      period = perUnit * r.planned_volume * share;
      total += period;
    }
    return {
      ...r,
      cost_per_unit_now: r.qty_per_unit * baseline,
      cost_per_unit_new: r.qty_per_unit * newPrice,
      change_per_unit: perUnit,
      period_change: period,
      formula: `${fmt(r.qty_per_unit)} × (${fmt(newPrice)} − ${fmt(baseline)}) × ${r.planned_volume ?? "?"} × ${fmt(share * 100)}%`,
    };
  });
  return { rows: out, total: hasVol ? total : null, perUnitOnly: !hasVol };
}

export function sensitivity(rows: SimRow[], baseline: number, share: number, lo: number, hi: number, steps = 40) {
  const pts: [number, number][] = [];
  for (let i = 0; i <= steps; i++) {
    const p = lo + ((hi - lo) * i) / steps;
    pts.push([p, simulate(rows, baseline, p, share).total ?? 0]);
  }
  return pts;
}

function fmt(x: number) {
  return Number.isInteger(x) ? String(x) : String(+x.toPrecision(6));
}
