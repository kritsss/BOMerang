import * as Tabs from "@radix-ui/react-tabs";
import { useQuery } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChartCard, SimpleTable } from "../components/ChartCard";
import { useGate } from "../components/Gate";
import { Ledger } from "../components/Ledger";
import { Num } from "../components/Num";
import { MoneySankey } from "../components/Sankey";
import { EmptyState, H1, NextBar } from "../components/ui";
import { api } from "../lib/api";
import { CLASS_COLOR, C } from "../lib/colors";
import { amount, money, num, pct } from "../lib/format";
import { useUI } from "../lib/store";

export default function MoneyFlow() {
  const { pid, ready, gate } = useGate();
  if (!ready) return <>{gate}</>;
  return <Screen pid={pid!} />;
}

function Screen({ pid }: { pid: number }) {
  const q = useQuery({ queryKey: ["moneyflow", pid], queryFn: () => api(`/projects/${pid}/moneyflow`) });
  const open = useUI((s) => s.openReceipt);
  const [sp, setSp] = useSearchParams();
  const tab = sp.get("tab") ?? "flow";
  if (!q.data) return <div className="text-muted">Loading…</div>;
  const d = q.data;
  const s = d.summary;
  const cur = d.currency;
  const notAlloc = s.total_cents - s.allocated_cents;
  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <H1 eyebrow="Step 3 of 5 · Money flow">
          {d.has_volumes ? (
            <>
              <span className="text-navy">{pct(s.explained_share)}</span> of your spend is explained by your products.{" "}
              <span className="text-cost">
                <Num cents={notAlloc} currency={cur} receipt={{ kind: "total", title: "All spend" }} /> isn't.
              </span>{" "}
              <a href="#why" className="text-[0.6em] font-semibold text-save">See why ↓</a>
            </>
          ) : (
            <>Spend is classified, but not yet allocated to products.</>
          )}
        </H1>
      </div>
      <Tabs.Root value={tab} onValueChange={(v) => { sp.set("tab", v); setSp(sp, { replace: true }); }} className="flex flex-col gap-6">
        <Tabs.List className="flex gap-1" aria-label="Money flow views">
          <Tabs.Trigger value="flow" className="rounded-full px-4 py-2 text-sm font-semibold data-[state=active]:bg-ink data-[state=active]:text-white data-[state=inactive]:bg-white data-[state=inactive]:text-ink">Where the money goes</Tabs.Trigger>
          <Tabs.Trigger value="bom" className="rounded-full px-4 py-2 text-sm font-semibold data-[state=active]:bg-ink data-[state=active]:text-white data-[state=inactive]:bg-white data-[state=inactive]:text-ink">BOM cost per product</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="flow" className="flex flex-col gap-6 outline-none">
          {!d.has_volumes && (
            <EmptyState title="Upload production volumes to allocate spend to products">
              Allocation needs units built per product (product, period, units built). Until then, spend linked to BOM parts is shown as “Linked to a BOM part (no volumes to allocate)”. Everything else below is final and reconciles to the spend cube.
            </EmptyState>
          )}
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
            <ChartCard
              title="Follow the money · click any stream to see its lines"
              note="Small streams drawn wider so they can be clicked"
              chart={<MoneySankey classes={s.classes} products={d.products} total={s.total_cents} currency={cur} onOpen={open} />}
              table={<SimpleTable head={["Stream", "Amount", "Share"]} rows={[...s.classes.map((c: any) => [c.label, <Num cents={c.cents} currency={cur} receipt={{ kind: "class", key: c.key, title: c.label }} />, pct(s.total_cents ? c.cents / s.total_cents : 0)]), ...d.products.map((p: any) => [`  → ${p.name}`, <Num cents={p.cents} currency={cur} receipt={{ kind: "class", key: "allocated", product: p.product_id, title: `Allocated to ${p.name}` }} />, pct(p.cents / s.total_cents)])]} />}
            />
            <Ledger ledger={s} currency={cur} />
          </div>
          <div id="why" />
          <ZoomBar s={s} cur={cur} />
          <div className="grid gap-6 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <section className="card flex flex-col gap-3 p-6" aria-label="Unexplained spend">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="m-0 text-base font-semibold">Largest items not explained</h2>
                <span className="text-[13px] text-muted">Not waste by default: here is why they might exist</span>
              </div>
              {d.unexplained_top.length ? d.unexplained_top.map((u: any) => (
                <div key={u.item_id + u.class} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-b border-line pb-2 text-sm">
                  <div>
                    <span className="mr-2 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: CLASS_COLOR[u.class] }} aria-hidden />
                    <strong>{u.description}</strong> · {u.supplier}
                    <div className="text-xs text-muted">{u.label}: {u.reason}</div>
                  </div>
                  <Num cents={u.cents} currency={cur} receipt={{ kind: "item", key: u.item_id, title: u.description }} />
                </div>
              )) : <div className="text-sm text-muted">Nothing unexplained.</div>}
              <div className="flex flex-wrap gap-2 pt-1">
                {["A product outside this data?", "Wrong part ordered?", "Missing cross-reference?", "Non-production use?"].map((t) => <span key={t} className="chip bg-cost-bg text-cost">{t}</span>)}
              </div>
            </section>
            <section className="card flex flex-col gap-3 p-6">
              <h2 className="m-0 text-base font-semibold">How we count it</h2>
              <p className="m-0 text-sm leading-relaxed">Allocated = parts needed (exploded BOM quantity × units built) × weighted-average production price, never more than what was bought. Shared parts are split between products by how many each needs.</p>
              <p className="m-0 text-sm leading-relaxed">Bought beyond need = production spend on linked parts minus what was allocated. Service and warranty is shown, never split across products. Every class adds up to total spend exactly.</p>
              <p className="m-0 text-sm text-muted">Click any number for the lines behind it.</p>
            </section>
          </div>
        </Tabs.Content>
        <Tabs.Content value="bom" className="outline-none">
          <BomCost data={d.bom_cost} cur={cur} initial={sp.get("product")} hasVolumes={d.has_volumes} />
        </Tabs.Content>
      </Tabs.Root>
      <NextBar text="Pick a shared part to see who supplies it, at what price, and who uses it.">
        <Link to="/parts" className="rounded-[10px] bg-white px-5 py-3 text-[15px] font-semibold text-ink no-underline">Parts →</Link>
      </NextBar>
    </>
  );
}

function ZoomBar({ s, cur }: { s: any; cur: string }) {
  const rest = s.classes.filter((c: any) => c.key !== "allocated" && c.cents !== 0);
  const tot = rest.reduce((a: number, c: any) => a + Math.abs(c.cents), 0);
  if (!tot) return null;
  return (
    <section className="card flex flex-col gap-3 p-6" aria-label="Spend not allocated to products">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="m-0 text-base font-semibold">Zoom: the {money(s.total_cents - s.allocated_cents, cur)} not allocated to products</h2>
        <span className="text-[13px] text-muted">Click a segment for its lines</span>
      </div>
      <div className="flex h-9 w-full gap-[2px] overflow-hidden rounded-lg" role="img" aria-label="Breakdown of spend not allocated to products">
        {rest.map((c: any) => (
          <ZoomSeg key={c.key} c={c} w={Math.abs(c.cents) / tot} />
        ))}
      </div>
      <ul className="m-0 flex list-none flex-wrap gap-x-6 gap-y-2 p-0 text-sm">
        {rest.map((c: any) => (
          <li key={c.key} className="flex items-center gap-2">
            <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: CLASS_COLOR[c.key] }} aria-hidden />
            {c.label} <Num cents={c.cents} currency={cur} receipt={{ kind: "class", key: c.key, title: c.label }} /> <span className="text-muted">{pct(Math.abs(c.cents) / tot, 0)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ZoomSeg({ c, w }: { c: any; w: number }) {
  const open = useUI((s) => s.openReceipt);
  return (
    <button type="button" aria-label={`${c.label}`} title={c.label} onClick={() => open({ kind: "class", key: c.key, title: c.label })}
      className="h-9 min-w-[4px] hover:opacity-80" style={{ width: `${w * 100}%`, background: CLASS_COLOR[c.key] }} />
  );
}

function BomCost({ data, cur, initial, hasVolumes }: { data: any[]; cur: string; initial: string | null; hasVolumes: boolean }) {
  const [pidx, setP] = useState<string>(initial && data.some((d) => d.product_id === initial) ? initial : data[0]?.product_id);
  const prod = data.find((d) => d.product_id === pidx);
  const leaves = useMemo(() => (prod?.rows ?? []).filter((r: any) => r.is_leaf && r.actual_ext != null).sort((a: any, b: any) => b.actual_ext - a.actual_ext).slice(0, 20), [prod]);
  const open = useUI((s) => s.openReceipt);
  if (!data.length) return <EmptyState title="No products found">The BOM has no top-level products.</EmptyState>;
  const opt = {
    animation: false,
    grid: { left: 140, right: 70, top: 8, bottom: 24 },
    tooltip: { trigger: "item", valueFormatter: (v: number) => amount(v, cur) },
    xAxis: { type: "value", axisLabel: { color: C.muted, formatter: (v: number) => amount(v, cur, { decimals: 2 }) }, splitLine: { lineStyle: { color: C.grid } } },
    yAxis: { type: "category", inverse: true, data: leaves.map((r: any) => r.part_id), axisLabel: { color: C.ink, width: 130, overflow: "truncate" }, axisTick: { show: false }, axisLine: { lineStyle: { color: C.line } } },
    series: [{ type: "bar", barMaxWidth: 16, data: leaves.map((r: any) => r.actual_ext), itemStyle: { color: C.navy, borderRadius: [0, 4, 4, 0] }, label: { show: true, position: "right", color: C.muted, formatter: (p: any) => amount(p.value, cur) } }],
  };
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm font-semibold" htmlFor="prod">Product</label>
        <select id="prod" className="input max-w-sm" value={pidx} onChange={(e) => setP(e.target.value)}>
          {data.map((d) => <option key={d.product_id} value={d.product_id}>{d.name}{d.status === "discontinued" ? " (discontinued)" : ""}</option>)}
        </select>
      </div>
      {prod && (
        <>
          <div className="grid gap-4 sm:grid-cols-4">
            <Stat label="Standard cost per unit" v={amount(prod.std_cost_per_unit, cur)} />
            <Stat label="Actual-price cost per unit" v={amount(prod.actual_cost_per_unit, cur)} sub={`${prod.actual_known_lines} of ${prod.leaf_lines} lines priced`} />
            <Stat label="Spend allocated" v={<Num cents={prod.allocated_cents} currency={cur} receipt={{ kind: "class", key: "allocated", product: prod.product_id, title: `Allocated to ${prod.name}` }} />} sub={hasVolumes ? "" : "needs volumes"} />
            <div className="card flex flex-col gap-2 p-5">
              <div className="label">Coverage</div>
              <div className="font-display text-2xl font-bold">{pct(prod.coverage, 0)}</div>
              <div className="h-2 rounded-full bg-soft" role="meter" aria-valuenow={Math.round(prod.coverage * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Share of BOM lines with a confirmed link">
                <div className="h-2 rounded-full bg-human" style={{ width: `${prod.coverage * 100}%` }} />
              </div>
              <div className="text-xs text-muted">BOM lines with a confirmed link</div>
            </div>
          </div>
          <ChartCard title="BOM cost by line · actual price × quantity per unit" note="Top 20 lines"
            chart={leaves.length ? <ReactECharts option={opt} style={{ height: Math.max(160, leaves.length * 28 + 40) }} opts={{ renderer: "svg" }} onEvents={{ click: (p: any) => open({ kind: "part", key: p.name, title: `Lines linked to ${p.name}` }) }} /> : <div className="text-sm text-muted">No linked prices yet for this product.</div>}
            table={<SimpleTable head={["Part", "Actual × qty"]} rows={leaves.map((r: any) => [r.part_id, amount(r.actual_ext, cur)])} />} />
          <section className="card overflow-auto p-6" aria-label="Indented BOM">
            <h2 className="m-0 mb-3 text-base font-semibold">Indented BOM</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted">
                  <th className="py-2 pr-3">Part</th><th className="py-2 pr-3">Description</th><th className="py-2 pr-3 text-right">Qty / parent</th><th className="py-2 pr-3 text-right">Qty / unit</th>
                  <th className="py-2 pr-3 text-right">Standard cost</th><th className="py-2 pr-3 text-right">Actual price</th><th className="py-2 pr-3 text-right">Actual × qty</th><th className="py-2 pr-3 text-right">Spend allocated</th><th className="py-2">Link</th>
                </tr>
              </thead>
              <tbody>
                {prod.rows.map((r: any, i: number) => (
                  <tr key={i} className="border-b border-line">
                    <td className="py-1.5 pr-3" style={{ paddingLeft: (r.level - 1) * 18 }}>{r.is_leaf ? <Link to={`/parts/${encodeURIComponent(r.part_id)}`}>{r.part_id}</Link> : <strong>{r.part_id}</strong>}</td>
                    <td className="py-1.5 pr-3">{r.description}</td>
                    <td className="py-1.5 pr-3 text-right tabnum">{num(r.qty_per_parent, 3)}</td>
                    <td className="py-1.5 pr-3 text-right tabnum">{num(r.ext_qty, 3)}</td>
                    <td className="py-1.5 pr-3 text-right tabnum">{amount(r.standard_cost, cur)}</td>
                    <td className="py-1.5 pr-3 text-right tabnum">{amount(r.actual_price, cur)}</td>
                    <td className="py-1.5 pr-3 text-right tabnum">{amount(r.actual_ext, cur)}</td>
                    <td className="py-1.5 pr-3 text-right">{r.is_leaf && r.allocated_cents ? <Num cents={r.allocated_cents} currency={cur} receipt={{ kind: "class", key: "allocated", product: prod.product_id, title: `Allocated to ${prod.name}` }} /> : ""}</td>
                    <td className="py-1.5">{r.is_leaf ? <LinkDot s={r.link} /> : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}

function LinkDot({ s }: { s: string }) {
  const m: Record<string, [string, string]> = { linked: ["bg-human", "linked"], pending: ["bg-warn", "pending review"], none: ["bg-line", "no link"] };
  const [c, l] = m[s] ?? m.none;
  return <span className="inline-flex items-center gap-1.5 text-xs"><span className={`h-2.5 w-2.5 rounded-full ${c}`} aria-hidden />{l}</span>;
}

function Stat({ label, v, sub }: { label: string; v: React.ReactNode; sub?: string }) {
  return (
    <div className="card flex flex-col gap-1 p-5">
      <div className="label">{label}</div>
      <div className="font-display text-2xl font-bold">{v}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  );
}
