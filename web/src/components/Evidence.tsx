import ReactECharts from "echarts-for-react";
import { clsx } from "clsx";
import { amount, num, pct } from "../lib/format";
import { C } from "../lib/colors";
import { AIChip, Icon } from "./ui";

type Attr = { attr: string; hard: boolean; result: "agree" | "missing" | "differ"; item_val: string | null; part_val: string | null; why: string; source?: string };

export function AttributeChips({ attrs }: { attrs: Attr[] }) {
  if (!attrs?.length) return <div className="text-sm text-muted">No attribute columns in the material master.</div>;
  const sorted = [...attrs].sort((a, b) => Number(b.hard) - Number(a.hard));
  return (
    <div className="flex flex-wrap gap-2" role="list" aria-label="Attribute check">
      {sorted.map((a) => {
        const cls = a.result === "agree" ? "bg-ok-bg text-ok" : a.result === "missing" ? "bg-warn-bg text-warn" : "bg-cost-bg text-cost";
        const icon = a.result === "agree" ? "check" : a.result === "missing" ? "warn" : "x";
        const word = a.result === "agree" ? "agrees" : a.result === "missing" ? "missing" : "differs";
        let text = `${a.attr} ${a.part_val ?? ""}`;
        if (a.result === "differ") text = `${a.attr}: invoice ${a.item_val} vs part ${a.part_val}`;
        if (a.result === "missing") text = `${a.attr}: ${a.part_val ? `${a.part_val} · ` : ""}${a.why}`;
        return (
          <span key={a.attr} role="listitem" className={clsx("chip", cls, a.source === "ai" && "ring-2 ring-ai-line")} title={`${a.attr} ${word}${a.hard ? " (hard attribute)" : ""}${a.source === "ai" ? " · read by AI" : ""}`}>
            <Icon name={icon as any} size={14} />
            {text}
            {a.hard && <span className="text-[11px] font-bold uppercase opacity-70">hard</span>}
            {a.source === "ai" && <span className="text-[11px] font-bold text-ai">AI-read</span>}
            <span className="sr-only">{word}</span>
          </span>
        );
      })}
    </div>
  );
}

const MARK = { pass: ["Pass", "bg-ok-bg text-ok", "check"], not_decisive: ["Not decisive", "bg-soft text-muted", "minus"], fail: ["Fail", "bg-cost-bg text-cost", "x"] } as const;

export function CheckHead({ title, result }: { title: string; result?: keyof typeof MARK }) {
  const m = MARK[result ?? "not_decisive"];
  return (
    <div className="flex items-center justify-between gap-2">
      <div className="text-sm font-semibold">{title}</div>
      <span className={clsx("chip", m[1])}>
        <Icon name={m[2] as any} size={14} />
        {m[0]}
      </span>
    </div>
  );
}

export function PriceGauge({ price, currency }: { price: any; currency: string }) {
  if (!price || price.ratio == null)
    return <div className="text-sm text-muted">{price?.sentence ?? "No price to compare."}</div>;
  const max = Math.max(2.2, price.high * 1.3, price.ratio * 1.1);
  const x = (r: number) => `${(Math.min(r, max) / max) * 100}%`;
  return (
    <div className="flex flex-col gap-2">
      <div className="relative h-7 rounded-full bg-soft" role="img" aria-label={`Price is ${price.ratio.toFixed(2)} times expected; band ${price.low} to ${price.high}`}>
        <div className="absolute top-0 h-7 rounded-full bg-ok-bg" style={{ left: x(price.low), width: `calc(${x(price.high)} - ${x(price.low)})` }} />
        <div className="absolute top-0 h-7 w-px bg-muted" style={{ left: x(1) }} />
        <div className={clsx("absolute -top-1 h-9 w-[6px] -translate-x-1/2 rounded", price.result === "fail" ? "bg-cost" : "bg-ink")} style={{ left: x(price.ratio) }} />
      </div>
      <div className="flex justify-between text-xs text-muted">
        <span>0×</span>
        <span>band {price.low}× – {price.high}×</span>
        <span>{max.toFixed(1)}×</span>
      </div>
      <div className="text-sm">
        Paid <strong className="tabnum">{amount(price.price, currency)}</strong> per base unit vs expected <strong className="tabnum">{amount(price.expected, currency)}</strong>
        <span className="text-muted"> ({price.expected_source})</span>. {price.sentence}
      </div>
    </div>
  );
}

export function BalanceBars({ balance, coverage }: { balance?: any; coverage?: any }) {
  if (balance?.coverage && Object.keys(balance.coverage).length) {
    const rows = Object.entries(balance.coverage) as [string, any][];
    const max = Math.max(1.5, ...rows.map(([, c]) => c.coverage_if_linked ?? 0)) * 1.05;
    return (
      <div className="flex flex-col gap-3">
        {rows.map(([p, c]) => (
          <div key={p} className="grid grid-cols-[110px_1fr_64px] items-center gap-3 text-sm">
            <div className={clsx("truncate font-semibold", p === balance.best && "text-navy")}>{p}</div>
            <div className="relative h-4 rounded bg-soft">
              <div className="absolute h-4 rounded-l bg-[#C7D2FE]" style={{ width: `${(Math.min(c.coverage_without ?? 0, max) / max) * 100}%` }} />
              <div className="absolute h-4 rounded" style={{ width: `${(Math.min(c.coverage_if_linked ?? 0, max) / max) * 100}%`, background: p === balance.best ? C.navy : "#94A3B8", opacity: 0.85 }} />
              <div className="absolute -top-1 h-6 w-[2px] bg-ink" style={{ left: `${(1 / max) * 100}%` }} title="100% = exactly what production needed" />
            </div>
            <div className="text-right tabnum">{c.coverage_if_linked != null ? pct(c.coverage_if_linked, 0) : "–"}</div>
          </div>
        ))}
        <div className="text-xs text-muted">Bar = bought vs needed if this item is linked there (light part = already covered by certain links). Black line = 100%.</div>
        <div className="text-sm">{balance.sentence}{balance.margin != null && isFinite(balance.margin) ? ` Margin ${balance.margin.toFixed(2)}.` : ""}</div>
      </div>
    );
  }
  if (coverage) return <div className="text-sm">{coverage.sentence}</div>;
  return <div className="text-sm text-muted">No production volumes: the quantity check is off.</div>;
}

export function TimingChart({ timing }: { timing: any }) {
  if (!timing?.series) return <div className="text-sm text-muted">Needs monthly purchase dates and monthly volumes.</div>;
  const [p, s] = Object.entries(timing.series)[0] as [string, any];
  const opt = {
    animation: false,
    grid: { left: 40, right: 16, top: 24, bottom: 28 },
    tooltip: { trigger: "axis", valueFormatter: (v: number) => pct(v, 0) },
    legend: { top: 0, right: 0, textStyle: { color: C.muted, fontSize: 12 } },
    xAxis: { type: "category", data: s.chunks, axisLabel: { color: C.muted, fontSize: 11 }, axisLine: { lineStyle: { color: C.line } } },
    yAxis: { type: "value", axisLabel: { formatter: (v: number) => pct(v, 0), color: C.muted }, splitLine: { lineStyle: { color: C.grid } } },
    series: [
      { name: "Purchases (shifted 1 month)", type: "line", data: s.purchase, symbolSize: 8, lineStyle: { width: 2, color: C.ink }, itemStyle: { color: C.ink } },
      { name: `Demand for ${p}`, type: "line", data: s.demand, symbolSize: 8, lineStyle: { width: 2, color: C.navy, type: "dashed" }, itemStyle: { color: C.navy } },
    ],
  };
  return (
    <div>
      <ReactECharts option={opt} style={{ height: 160 }} opts={{ renderer: "svg" }} />
      <div className="text-sm">Timing fit <strong>{pct(s.fit, 0)}</strong> for {p}.</div>
    </div>
  );
}

export function EvidencePanel({ item, currency }: { item: any; currency: string }) {
  const ev = item.evidence || {};
  const cand = (ev.candidates || []).find((c: any) => c.part_id === (item.part_id || item.suggestion_part_id)) || (ev.candidates || [])[0];
  const balResult = ev.balance?.result ?? ev.coverage?.result;
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="flex flex-col gap-3 rounded-xl border border-line p-4">
        <CheckHead title="What the invoice says" result={cand ? (cand.attrs.some((a: Attr) => a.hard && a.result === "differ") ? "fail" : cand.attrs.some((a: Attr) => a.hard && a.result === "missing") ? "not_decisive" : cand.attrs.some((a: Attr) => a.hard) ? "pass" : "not_decisive") : "not_decisive"} />
        {cand ? (
          <table className="text-sm">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th className="py-1 pr-3">Attribute</th>
                <th className="py-1 pr-3">Invoice</th>
                <th className="py-1 pr-3">Part {cand.part_id}</th>
              </tr>
            </thead>
            <tbody>
              {cand.attrs.map((a: Attr) => (
                <tr key={a.attr} className="border-t border-line">
                  <td className="py-1.5 pr-3">{a.attr}{a.hard && <span className="ml-1 text-[11px] font-bold uppercase text-muted">hard</span>}</td>
                  <td className={clsx("py-1.5 pr-3", a.result === "differ" && "font-semibold text-cost")}>{a.item_val ?? <span className="text-warn">not stated</span>}{a.source === "ai" && <span className="ml-1 text-[11px] font-bold text-ai">AI-read</span>}</td>
                  <td className="py-1.5 pr-3">{a.part_val ?? <span className="text-warn">not stated</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="text-sm text-muted">No candidate part.</div>
        )}
        {cand && <div className="text-xs text-muted">Description similarity {pct(cand.text_sim, 0)}{cand.type_ok ? "" : " · part type word not found on the invoice"}</div>}
      </div>
      <div className="flex flex-col gap-3 rounded-xl border border-line p-4">
        <CheckHead title="Is the price plausible?" result={ev.price?.result} />
        <PriceGauge price={ev.price} currency={currency} />
      </div>
      <div className="flex flex-col gap-3 rounded-xl border border-line p-4">
        <CheckHead title="Do the quantities add up?" result={balResult} />
        <BalanceBars balance={ev.balance} coverage={ev.coverage} />
        {ev.unit && (
          <div className="rounded-lg bg-warn-bg px-3 py-2 text-sm text-warn">
            <strong>Unit unknown.</strong> {ev.unit.sentence}
          </div>
        )}
      </div>
      <div className="flex flex-col gap-3 rounded-xl border border-line p-4">
        <CheckHead title="Does the timing fit?" result={ev.timing ? ((Object.values(ev.timing.fit)[0] as number) >= 0.7 ? "pass" : "not_decisive") : "not_decisive"} />
        <TimingChart timing={ev.timing} />
      </div>
    </div>
  );
}

export function AINote({ ai }: { ai: any }) {
  if (!ai || !ai.note) return null;
  return (
    <div className="flex gap-3 rounded-xl border border-ai-line bg-[#F5F3FF] px-4 py-3">
      <AIChip />
      <div className="text-sm leading-relaxed">
        {ai.note}{" "}
        <span className="font-semibold text-ai">{ai.rejected_by_rules ? "Rules re-checked this suggestion and refused it (hard attribute conflict)." : "Rules re-checked this suggestion."}</span>
      </div>
    </div>
  );
}

export { num };
