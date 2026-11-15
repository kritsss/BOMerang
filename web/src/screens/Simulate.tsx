import * as Slider from "@radix-ui/react-slider";
import { useQuery } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChartCard, SimpleTable } from "../components/ChartCard";
import { useGate } from "../components/Gate";
import { Num, useCountTo } from "../components/Num";
import { EmptyState, ErrorNote } from "../components/ui";
import { api, download } from "../lib/api";
import { C } from "../lib/colors";
import { amount, num } from "../lib/format";
import { sensitivity, simulate, type SimRow } from "../lib/simulate";
import { useUI } from "../lib/store";

export default function Simulate() {
  const { pid, ready, gate } = useGate();
  if (!ready) return <>{gate}</>;
  return <Screen pid={pid!} />;
}

function Screen({ pid }: { pid: number }) {
  const { partId } = useParams();
  const nav = useNavigate();
  const parts = useQuery({ queryKey: ["parts", pid], queryFn: () => api<any[]>(`/projects/${pid}/parts`) });
  const choices = (parts.data ?? []).filter((p) => p.used_in > 0);
  const chosen = partId ?? choices.find((p) => p.spend_cents > 0)?.part_id ?? choices[0]?.part_id;
  return (
    <div className="grid gap-6 lg:grid-cols-[380px_minmax(0,1fr)]">
      {chosen ? <Sim key={chosen} pid={pid} partId={chosen} choices={choices} onPick={(p) => nav(`/simulate/${encodeURIComponent(p)}`)} /> : (
        <div className="lg:col-span-2"><EmptyState title="No part used in an active product">The simulator needs a part that appears in at least one active product's BOM.</EmptyState></div>
      )}
    </div>
  );
}

function Sim({ pid, partId, choices, onPick }: { pid: number; partId: string; choices: any[]; onPick: (p: string) => void }) {
  const q = useQuery({ queryKey: ["sim", pid, partId], queryFn: () => api(`/projects/${pid}/simulate/${encodeURIComponent(partId)}`) });
  const setScenario = useUI((s) => s.setScenario);
  const open = useUI((s) => s.openReceipt);
  const [baseKey, setBaseKey] = useState<string>("");
  const [price, setPrice] = useState<number>(0);
  const [share, setShare] = useState<number>(1);
  const [vols, setVols] = useState<Record<string, string>>({});
  const [showF, setShowF] = useState(false);
  const [pinned, setPinned] = useState<any>(null);
  const [err, setErr] = useState<unknown>(null);
  const d = q.data;
  useEffect(() => {
    if (!d) return;
    const b = d.baselines[0];
    setBaseKey(b?.key ?? "");
    setPrice(b ? +(b.value * 0.9).toPrecision(4) : 0);
    setVols(Object.fromEntries(d.rows.map((r: any) => [r.product_id, r.planned_volume != null ? String(r.planned_volume) : ""])));
  }, [d]);
  const base = d?.baselines.find((b: any) => b.key === baseKey);
  const rows: SimRow[] = useMemo(() => (d?.rows ?? []).map((r: any) => ({ product_id: r.product_id, name: r.name, qty_per_unit: r.qty_per_unit, planned_volume: vols[r.product_id] === "" || vols[r.product_id] === undefined ? null : Number(vols[r.product_id]) })), [d, vols]);
  const res = useMemo(() => (base ? simulate(rows, base.value, price, share) : null), [rows, base, price, share]);
  const shown = useCountTo(res?.total ?? null);
  if (q.isLoading) return <div className="text-muted">Loading…</div>;
  if (!d) return <ErrorNote error={q.error} />;
  if (!base) return <div className="lg:col-span-2"><EmptyState title="No baseline price for this part">There is no linked production price and no standard cost. Link the part's spend lines in Review, or add standard cost to the material master.</EmptyState></div>;
  const cur = d.currency;
  const lo = Math.max(0, base.value * 0.5), hi = base.value * 1.5;
  const step = +(base.value / 200).toPrecision(2) || 0.0001;
  const total = res?.total;
  const saving = (total ?? res!.rows[0]?.change_per_unit ?? 0) <= 0;
  const period = d.period ? `period ${d.period}` : "the planned period";
  const maxAbs = Math.max(...res!.rows.map((r) => Math.abs(r.period_change ?? r.change_per_unit)), 1e-9);
  const summary = res!.perUnitOnly
    ? `Changing ${d.part_id} from ${amount(base.value, cur)} to ${amount(price, cur)} changes cost per product unit as shown. Add planned volumes to see a period total.`
    : `If ${d.part_id} costs ${amount(price, cur)} instead of ${amount(base.value, cur)} on ${num(share * 100)}% of volume, the ${res!.rows.length} product${res!.rows.length === 1 ? "" : "s"} using it would ${saving ? "save" : "cost an extra"} ${amount(Math.abs(total ?? 0), cur)} over ${period}.`;
  const exportScenario = async () => {
    const sc = { part_id: d.part_id, rows, baseline: base.value, baseline_label: `${base.label} (${base.source})`, new_price: price, share };
    setScenario(sc);
    try {
      await download(`/projects/${pid}/export`, { scenario: sc }, "BOMerang_scenario.xlsx");
    } catch (e) {
      setErr(e);
    }
  };
  return (
    <>
      <section className="card flex h-fit flex-col gap-6 p-6" aria-label="Scenario controls">
        <div>
          <div className="label">What if…</div>
          <h1 className="m-0 font-display text-[28px] leading-tight">the price of one part changed?</h1>
        </div>
        <label className="flex flex-col gap-1.5 text-sm font-semibold">
          Component
          <select className="input" value={partId} onChange={(e) => onPick(e.target.value)}>
            {choices.map((c) => <option key={c.part_id} value={c.part_id}>{c.part_id} · {c.description}</option>)}
          </select>
        </label>
        <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
          <legend className="mb-1 text-sm font-semibold">Baseline price</legend>
          {d.baselines.map((b: any) => (
            <label key={b.key} className="flex cursor-pointer items-start gap-2 rounded-lg border border-line p-2.5 text-sm has-[:checked]:border-ink">
              <input type="radio" name="base" checked={b.key === baseKey} onChange={() => { setBaseKey(b.key); setPrice(+(b.value * 0.9).toPrecision(4)); }} className="mt-1" />
              <span>
                <strong>{amount(b.value, cur)}</strong> {b.label}
                <span className="block text-xs text-muted">{b.source}</span>
              </span>
            </label>
          ))}
        </fieldset>
        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between">
            <label htmlFor="newprice" className="text-sm font-semibold">New price per {d.base_uom}</label>
            <input id="newprice" type="number" min={0} step={step} value={price} onChange={(e) => setPrice(Math.max(0, Number(e.target.value)))} className="input w-32 text-right font-display text-lg font-bold" />
          </div>
          <Slider.Root className="relative flex h-5 touch-none select-none items-center" min={lo} max={hi} step={step} value={[Math.min(hi, Math.max(lo, price))]} onValueChange={([v]) => setPrice(+v.toPrecision(4))} aria-label="New price">
            <Slider.Track className="relative h-1.5 grow rounded-full bg-line"><Slider.Range className="absolute h-full rounded-full bg-ink" /></Slider.Track>
            <Slider.Thumb className="block h-5 w-5 rounded-full border-2 border-ink bg-white" aria-label="New price" />
          </Slider.Root>
          <div className="flex justify-between text-xs text-muted"><span>{amount(lo, cur)}</span><span>baseline {amount(base.value, cur)}</span><span>{amount(hi, cur)}</span></div>
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex items-baseline justify-between">
            <span className="text-sm font-semibold" id="sharelbl">Share of volume at the new price</span>
            <span className="font-display text-lg font-bold">{num(share * 100)}%</span>
          </div>
          <Slider.Root className="relative flex h-5 touch-none select-none items-center" min={0} max={1} step={0.05} value={[share]} onValueChange={([v]) => setShare(v)} aria-labelledby="sharelbl">
            <Slider.Track className="relative h-1.5 grow rounded-full bg-line"><Slider.Range className="absolute h-full rounded-full bg-ink" /></Slider.Track>
            <Slider.Thumb className="block h-5 w-5 rounded-full border-2 border-ink bg-white" aria-label="Share of volume" />
          </Slider.Root>
          <div className="text-xs text-muted">Example: only one supplier's price changes</div>
        </div>
        <div className="flex flex-col gap-2">
          <div className="text-sm font-semibold">Planned units per product {d.period && <span className="font-normal text-muted">(prefilled from {d.period})</span>}</div>
          {d.rows.map((r: any) => (
            <label key={r.product_id} className="grid grid-cols-[1fr_120px] items-center gap-2 text-sm">
              <span className="truncate">{r.name}</span>
              <input className="input text-right" inputMode="numeric" value={vols[r.product_id] ?? ""} placeholder="units" onChange={(e) => setVols({ ...vols, [r.product_id]: e.target.value.replace(/[^\d.]/g, "") })} />
            </label>
          ))}
        </div>
        <ul className="m-0 flex list-disc flex-col gap-1 rounded-xl bg-soft py-3 pl-8 pr-4 text-[13px] leading-relaxed text-muted">
          {d.assumptions.map((a: string) => <li key={a}>{a}</li>)}
        </ul>
      </section>

      <section className="flex min-w-0 flex-col gap-6" aria-label="Results">
        <div className="flex flex-col gap-3 rounded-card bg-ink p-7 text-white" aria-live="polite">
          <div className="text-sm text-[#D1D5DB]">{res!.perUnitOnly ? "Change per product unit (no volumes)" : `${saving ? "Potential saving" : "Extra cost"} over ${period}`}</div>
          <div className={`font-display text-[52px] font-bold leading-none tabnum ${saving ? "text-[#93C5FD]" : "text-[#FDBA74]"}`}>
            {res!.perUnitOnly ? amount(res!.rows[0]?.change_per_unit ?? 0, cur, { sign: true }) : amount(shown ?? 0, cur, { sign: true, decimals: 0 })}
          </div>
          <div className="max-w-2xl text-[15px] leading-relaxed text-[#E5E7EB]">{summary}</div>
          <div className="flex flex-wrap gap-2 pt-1">
            <button type="button" className="rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-ink" onClick={() => setPinned({ price, share, total, base: base.value, label: `${amount(price, cur)} on ${num(share * 100)}%` })}>Pin to compare</button>
            {pinned && <button type="button" className="rounded-lg border border-white/40 px-3 py-1.5 text-sm" onClick={() => setPinned(null)}>Clear pin</button>}
          </div>
        </div>
        {pinned && (
          <div className="grid gap-4 sm:grid-cols-2">
            {[["Pinned", pinned], ["Current", { price, share, total, label: `${amount(price, cur)} on ${num(share * 100)}%` }]].map(([l, s]: any) => (
              <div key={l} className="card p-5">
                <div className="label">{l} · {s.label}</div>
                <div className={`font-display text-2xl font-bold ${(s.total ?? 0) <= 0 ? "text-save" : "text-cost"}`}>{s.total == null ? "per unit only" : amount(s.total, cur, { sign: true, decimals: 0 })}</div>
              </div>
            ))}
          </div>
        )}
        <section className="card flex flex-col gap-4 p-6" aria-label="Every product that uses it">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="m-0 text-base font-semibold">Every product that uses it</h2>
            <button type="button" className="text-[13px] font-semibold text-save" onClick={() => setShowF((v) => !v)} aria-pressed={showF}>{showF ? "Hide formulas" : "Show all formulas"}</button>
          </div>
          {res!.rows.map((r) => {
            const v = r.period_change ?? r.change_per_unit;
            const now = r.planned_volume != null ? r.cost_per_unit_now * r.planned_volume * share : r.cost_per_unit_now;
            return (
              <div key={r.product_id} className="flex flex-col gap-2 border-b border-line pb-4 last:border-0">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm md:grid-cols-[1.4fr_0.8fr_1.4fr_1fr_1.2fr]">
                  <strong>{r.name}</strong>
                  <span><span className="block text-xs text-muted">Qty per unit</span>{num(r.qty_per_unit, 4)}</span>
                  <span><span className="block text-xs text-muted">Now → new, per unit</span>{amount(r.cost_per_unit_now, cur)} → {amount(r.cost_per_unit_new, cur)}</span>
                  <span><span className="block text-xs text-muted">Units planned</span>{r.planned_volume != null ? num(r.planned_volume) : "–"}</span>
                  <span className="text-right">
                    <span className="block text-xs text-muted">{r.period_change != null ? "Period change" : "Change per unit"}</span>
                    <Num receipt={{ kind: "formula", title: `${r.name}: how the change is computed`, ...({ formula: `change = qty per unit × (new price − baseline) × planned units × share = ${r.formula} = ${amount(v, cur, { sign: true })}`, inputs: [["Qty per product unit (exploded BOM)", num(r.qty_per_unit, 4)], ["Baseline", `${amount(base.value, cur)} · ${base.label} (${base.source})`], ["New price", amount(price, cur)], ["Planned units", r.planned_volume != null ? num(r.planned_volume) : "not set"], ["Share of volume", `${num(share * 100)}%`]] } as any) } as any}
                      className={`font-semibold ${v <= 0 ? "text-save" : "text-cost"}`}>{amount(v, cur, { sign: true })}</Num>
                  </span>
                </div>
                <div className="relative h-3 rounded bg-soft" aria-hidden>
                  <div className="absolute h-3 rounded bg-[#E5E7EB]" style={{ width: `${Math.min(100, (Math.abs(now) / (Math.max(maxAbs, Math.abs(now)) || 1)) * 100)}%` }} title="cost now (faint)" />
                  <div className="absolute h-3 rounded" style={{ width: `${(Math.abs(v) / Math.max(maxAbs, Math.abs(now))) * 100}%`, background: v <= 0 ? C.save : C.cost }} />
                </div>
                {showF && <div className="font-mono text-xs text-muted">{r.formula} = {amount(v, cur, { sign: true })}</div>}
              </div>
            );
          })}
          <div className="text-xs text-muted">Grey bar behind = what this part costs now in that product over the period; colored bar = the change. Negative = saving, positive = extra cost.</div>
        </section>
        {!res!.perUnitOnly && <Sensitivity rows={rows} base={base.value} share={share} price={price} lo={lo} hi={hi} cur={cur} onPrice={(p) => setPrice(+p.toPrecision(4))} />}
        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-ghost" onClick={() => setShowF(true)}>Show all formulas</button>
          <button type="button" className="btn-primary" onClick={exportScenario}>Export scenario to Excel</button>
        </div>
        <ErrorNote error={err} />
      </section>
    </>
  );
}

function Sensitivity({ rows, base, share, price, lo, hi, cur, onPrice }: { rows: SimRow[]; base: number; share: number; price: number; lo: number; hi: number; cur: string; onPrice: (p: number) => void }) {
  const ref = useRef<any>(null);
  const pts = sensitivity(rows, base, share, lo, hi, 40);
  const cur_t = simulate(rows, base, price, share).total ?? 0;
  const option = {
    animation: false,
    grid: { left: 80, right: 24, top: 20, bottom: 36 },
    tooltip: { trigger: "axis", formatter: (p: any) => `price ${amount(p[0].value[0], cur)}<br/>change ${amount(p[0].value[1], cur, { sign: true, decimals: 0 })}` },
    xAxis: { type: "value", min: lo, max: hi, name: "price", nameLocation: "middle", nameGap: 24, axisLabel: { color: C.muted, formatter: (v: number) => amount(v, cur) }, splitLine: { show: false } },
    yAxis: { type: "value", axisLabel: { color: C.muted, formatter: (v: number) => amount(v, cur, { decimals: 0 }) }, splitLine: { lineStyle: { color: C.grid } } },
    series: [
      { type: "line", data: pts, showSymbol: false, lineStyle: { width: 2, color: C.ink },
        markLine: { silent: true, symbol: "none", lineStyle: { color: "#D1D5DB", type: "dashed" }, label: { show: false }, data: [{ xAxis: base, label: { show: true, color: C.muted, formatter: "baseline", position: "end" } }, { yAxis: 0 }] } },
      { type: "scatter", data: [[price, cur_t]], symbolSize: 16, itemStyle: { color: "#fff", borderColor: C.ink, borderWidth: 3 }, z: 5 },
    ],
  };
  return (
    <ChartCard title="Whole range at a glance" note="Total change against price · dot = your scenario · click the chart to move it"
      chart={<ReactECharts ref={ref} option={option} style={{ height: 240 }} opts={{ renderer: "svg" }}
        onChartReady={(chart: any) => {
          chart.getZr().on("click", (e: any) => {
            const p = chart.convertFromPixel({ seriesIndex: 0 }, [e.offsetX, e.offsetY]);
            if (p && p[0] >= lo && p[0] <= hi) onPrice(p[0]);
          });
        }} />}
      table={<SimpleTable head={["Price", "Total change"]} rows={pts.filter((_, i) => i % 4 === 0).map(([p, t]) => [amount(p, cur), amount(t, cur, { sign: true, decimals: 0 })])} />} />
  );
}
