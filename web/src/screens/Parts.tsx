import { useQuery } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ChartCard, SimpleTable } from "../components/ChartCard";
import { useGate } from "../components/Gate";
import { Num } from "../components/Num";
import { EmptyState, H1, Icon } from "../components/ui";
import { api } from "../lib/api";
import { C } from "../lib/colors";
import { amount, money, num, pct, plural } from "../lib/format";
import { useUI } from "../lib/store";

export default function Parts() {
  const { pid, ready, gate } = useGate();
  if (!ready) return <>{gate}</>;
  return <Screen pid={pid!} />;
}

function Screen({ pid }: { pid: number }) {
  const { partId } = useParams();
  const nav = useNavigate();
  const list = useQuery({ queryKey: ["parts", pid], queryFn: () => api<any[]>(`/projects/${pid}/parts`) });
  const [q, setQ] = useState("");
  const shown = useMemo(() => (list.data ?? []).filter((p) => !q || `${p.part_id} ${p.description}`.toLowerCase().includes(q.toLowerCase())).slice(0, 60), [list.data, q]);
  return (
    <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
      <aside className="card flex h-fit flex-col gap-3 p-4 lg:sticky lg:top-24" aria-label="Pick a part">
        <div className="label">Step 4 of 5 · Parts</div>
        <input className="input" placeholder="Search parts (or ⌘K)…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search parts" />
        <ul className="m-0 flex max-h-[60vh] list-none flex-col overflow-auto p-0">
          {shown.map((p) => (
            <li key={p.part_id}>
              <button type="button" onClick={() => nav(`/parts/${encodeURIComponent(p.part_id)}`)} className={`flex w-full flex-col rounded-lg px-3 py-2 text-left text-sm ${p.part_id === partId ? "bg-soft" : "hover:bg-soft"}`}>
                <span className="font-semibold">{p.part_id}</span>
                <span className="truncate text-xs text-muted">{p.description} · {p.spend_cents ? money(p.spend_cents) : "no linked spend"} · in {p.used_in}</span>
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <div className="flex min-w-0 flex-col gap-6">
        {partId ? <PartDetail pid={pid} partId={partId} /> : (
          <EmptyState title="Pick a part">Search on the left or press ⌘K. Parts are sorted by linked spend, so shared, expensive parts come first.</EmptyState>
        )}
      </div>
    </div>
  );
}

function PartDetail({ pid, partId }: { pid: number; partId: string }) {
  const q = useQuery({ queryKey: ["part", pid, partId], queryFn: () => api(`/projects/${pid}/parts/${encodeURIComponent(partId)}`) });
  const open = useUI((s) => s.openReceipt);
  const [supplier, setSupplier] = useState<string | null>(null);
  if (q.isLoading) return <div className="text-muted">Loading…</div>;
  if (q.error) return <EmptyState title="Part not found" />;
  const d = q.data;
  const cur = d.currency;
  const prodSup = d.suppliers.filter((s: any) => s.kind === "production");
  const nSup = new Set(prodSup.map((s: any) => s.supplier)).size;
  const nPrice = new Set(prodSup.filter((s: any) => s.price).map((s: any) => s.price.toFixed(4))).size;
  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <H1 eyebrow={`${d.used_in > 1 ? "Shared part" : "Part"} · ${d.part_id}`}>
          {d.description}: one part, {plural(nSup, "supplier")}, {plural(nPrice, "price")}.
        </H1>
        <Link to={`/simulate/${encodeURIComponent(d.part_id)}`} className="btn-primary no-underline">Simulate a price change →</Link>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Spend on this part" v={<Num cents={d.spend_cents} currency={cur} receipt={{ kind: "part", key: d.part_id, title: `Lines linked to ${d.part_id}` }} />} />
        <Kpi label="Used in" v={plural(d.used_in, "product")} />
        <Kpi label="Production price gap" v={d.price_gap ? <Num receipt={{ kind: "part", key: d.part_id, title: `Prices paid for ${d.part_id}` }}>{amount(d.price_gap, cur)} · {pct(d.price_gap_pct, 0)}</Num> : "–"} sub="highest minus lowest supplier price" />
        <Kpi label="Look-alikes refused" v={num(d.refused_count)} tone={d.refused_count ? "text-cost" : undefined} />
      </div>
      <Network d={d} cur={cur} onSupplier={(s) => { setSupplier(s); open({ kind: "part", key: d.part_id, supplier: s, title: `${d.part_id} from ${s}` }); }} onProduct={(p) => open({ kind: "class", key: "allocated", product: p, title: `${d.part_id}: allocated lines` })} />
      <div className="grid gap-6 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <PriceBars d={d} cur={cur} highlight={supplier} />
        <section className="card flex flex-col gap-3 border-cost-line p-6" aria-label="Refused look-alikes">
          <h2 className="m-0 flex items-center gap-2 text-base font-semibold text-cost"><Icon name="ban" size={18} /> Not this part</h2>
          {d.refused.length ? d.refused.map((r: any) => (
            <div key={r.item_id} className="text-sm leading-relaxed">
              <strong>{r.description}</strong> · {r.supplier} · <Num cents={r.spend_cents} currency={cur} receipt={{ kind: "item", key: r.item_id, title: r.description }} />
              <div className="text-muted">{r.reason} It was refused, so it never changes this part's price.</div>
            </div>
          )) : <div className="text-sm text-muted">No look-alikes were refused for this part.</div>}
        </section>
      </div>
      {d.price_by_month?.length > 0 && <PriceOverTime d={d} cur={cur} />}
    </>
  );
}

function Kpi({ label, v, sub, tone }: { label: string; v: React.ReactNode; sub?: string; tone?: string }) {
  return (
    <div className="card flex flex-col gap-1 p-5">
      <div className="label">{label}</div>
      <div className={`font-display text-[26px] font-bold ${tone ?? ""}`}>{v}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  );
}

function Network({ d, cur, onSupplier, onProduct }: { d: any; cur: string; onSupplier: (s: string) => void; onProduct: (p: string) => void }) {
  const bySup: Record<string, number> = {};
  for (const s of d.suppliers) bySup[s.supplier] = (bySup[s.supplier] ?? 0) + s.cents;
  const nodes: any[] = [{ name: d.part_id, itemStyle: { color: C.ink }, real: d.spend_cents, kind: "part" }];
  const links: any[] = [];
  const supTot = Object.values(bySup).reduce((a, b) => a + Math.abs(b), 0) || 1;
  const minW = supTot * 0.02;
  for (const [s, c] of Object.entries(bySup)) {
    nodes.push({ name: `${s} `, itemStyle: { color: C.rule }, real: c, kind: "supplier", key: s });
    links.push({ source: `${s} `, target: d.part_id, value: Math.max(Math.abs(c), minW), real: c, lineStyle: { color: C.rule } });
  }
  for (const p of d.products) {
    const nm = `${p.name}  `;
    nodes.push({ name: nm, itemStyle: { color: p.status === "discontinued" ? C.rule : C.navy }, real: p.allocated_cents, kind: "product", key: p.product_id });
    links.push({ source: d.part_id, target: nm, value: Math.max(Math.abs(p.allocated_cents), minW), real: p.allocated_cents, lineStyle: { color: C.navy } });
  }
  const option = {
    animation: false,
    tooltip: { formatter: (p: any) => `${String(p.name).trim()}<br/>${money(p.data.real ?? 0, cur)}` },
    series: [{
      type: "sankey", left: 8, right: 170, top: 8, bottom: 8, nodeWidth: 14, nodeGap: 16, layoutIterations: 0, draggable: false,
      emphasis: { focus: "adjacency" }, lineStyle: { curveness: 0.5, opacity: 0.35 },
      label: { formatter: (p: any) => `{n|${String(p.name).trim()}}\n{v|${money(p.data.real ?? 0, cur)}}`, rich: { n: { fontWeight: 600, color: C.ink, fontSize: 13 }, v: { color: C.muted, fontSize: 12 } } },
      data: nodes, links,
    }],
  };
  return (
    <ChartCard title="Who supplies it → who uses it" note="line thickness = spend · click a supplier or product"
      chart={<ReactECharts option={option} style={{ height: Math.max(220, 60 * Math.max(Object.keys(bySup).length, d.products.length)) }} opts={{ renderer: "svg" }}
        onEvents={{ click: (p: any) => { if (p.data?.kind === "supplier") onSupplier(p.data.key); if (p.data?.kind === "product") onProduct(p.data.key); } }} />}
      table={<SimpleTable head={["From", "To", "Amount"]} rows={[...Object.entries(bySup).map(([s, c]) => [s, d.part_id, money(c, cur)]), ...d.products.map((p: any) => [d.part_id, `${p.name} (${num(p.qty_per_unit, 3)} per unit${p.units_built != null ? `, ${num(p.units_built)} built` : ""})`, money(p.allocated_cents, cur)])]} />} />
  );
}

function PriceBars({ d, cur, highlight }: { d: any; cur: string; highlight: string | null }) {
  const rows = [...d.suppliers].filter((s: any) => s.price != null).sort((a: any, b: any) => (a.kind === b.kind ? a.price - b.price : a.kind === "production" ? -1 : 1));
  const max = Math.max(...rows.map((r: any) => r.price), 0) * 1.1 || 1;
  return (
    <ChartCard title={`Price per ${d.base_uom}`} note={d.wavg_price ? `weighted average ${amount(d.wavg_price, cur)}` : undefined}
      chart={
        <div className="flex flex-col gap-3">
          {rows.map((r: any) => {
            const prod = r.kind === "production";
            return (
              <div key={r.supplier + r.kind} className={`grid grid-cols-[minmax(0,180px)_1fr_90px] items-center gap-3 text-sm ${prod ? "" : "text-muted"}`}>
                <span className={`truncate ${highlight === r.supplier ? "font-bold" : ""}`}>{r.supplier} · {prod ? "production" : "spare / warranty"}</span>
                <div className="h-3 rounded bg-soft"><div className="h-3 rounded" style={{ width: `${(r.price / max) * 100}%`, background: prod ? C.navy : "#D1D5DB" }} /></div>
                <Num receipt={{ kind: "part", key: d.part_id, supplier: r.supplier, title: `${d.part_id} from ${r.supplier}` }} className={`text-right ${prod ? "font-semibold" : ""}`}>{amount(r.price, cur)}</Num>
              </div>
            );
          })}
          {!rows.length && <div className="text-sm text-muted">No priced lines (unknown units or no links yet).</div>}
          <div className="text-xs text-muted">Spare and warranty prices are shown greyed and kept out of the production comparison.</div>
        </div>
      }
      table={<SimpleTable head={["Supplier", "Kind", "Lines", "Quantity", "Price"]} rows={rows.map((r: any) => [r.supplier, r.kind, r.lines, num(r.qty), amount(r.price, cur)])} />} />
  );
}

function PriceOverTime({ d, cur }: { d: any; cur: string }) {
  const months = Array.from(new Set(d.price_by_month.map((r: any) => r.month))).sort() as string[];
  const sups = Array.from(new Set(d.price_by_month.map((r: any) => r.supplier))) as string[];
  const palette = [C.navy, "#1BA3C9", "#8C8A2E", "#D9541E"];
  const option = {
    animation: false,
    grid: { left: 60, right: 20, top: 30, bottom: 30 },
    tooltip: { trigger: "axis", valueFormatter: (v: number) => amount(v, cur) },
    legend: sups.length > 1 ? { top: 0, textStyle: { color: C.muted } } : undefined,
    xAxis: { type: "category", data: months, axisLabel: { color: C.muted } },
    yAxis: { type: "value", axisLabel: { color: C.muted, formatter: (v: number) => amount(v, cur) }, splitLine: { lineStyle: { color: C.grid } } },
    series: sups.slice(0, 4).map((s, i) => ({ name: s, type: "line", symbolSize: 8, lineStyle: { width: 2 }, color: palette[i], connectNulls: true, data: months.map((m) => d.price_by_month.find((r: any) => r.month === m && r.supplier === s)?.price ?? null) })),
  };
  return (
    <ChartCard title="Production price over time" note={sups.length > 4 ? "4 largest suppliers shown" : undefined}
      chart={<ReactECharts option={option} style={{ height: 240 }} opts={{ renderer: "svg" }} />}
      table={<SimpleTable head={["Month", "Supplier", "Price"]} rows={d.price_by_month.map((r: any) => [r.month, r.supplier, amount(r.price, cur)])} />} />
  );
}
