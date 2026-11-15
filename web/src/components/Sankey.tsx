import ReactECharts from "echarts-for-react";
import { useMemo } from "react";
import { CLASS_COLOR, C } from "../lib/colors";
import { money, pct } from "../lib/format";
import type { LedgerClass, Receipt } from "../lib/api";

export function MoneySankey({ classes, products, total, currency, onOpen, height = 520 }: { classes: LedgerClass[]; products: { product_id: string; name: string; cents: number }[]; total: number; currency: string; onOpen: (r: Receipt) => void; height?: number }) {
  const option = useMemo(() => {
    const minW = Math.abs(total) * 0.03;
    const vis = (v: number) => Math.max(Math.abs(v), minW);
    const nodes: any[] = [{ name: "All spend", itemStyle: { color: C.ink }, real: total, receipt: { kind: "total", title: "All spend" } }];
    const links: any[] = [];
    const cls = classes.filter((c) => c.cents !== 0);
    for (const c of cls) {
      nodes.push({ name: c.label, itemStyle: { color: CLASS_COLOR[c.key] ?? C.rule }, real: c.cents, receipt: { kind: "class", key: c.key, title: c.label } });
      links.push({ source: "All spend", target: c.label, value: vis(c.cents), real: c.cents, lineStyle: { color: CLASS_COLOR[c.key] ?? C.rule }, receipt: { kind: "class", key: c.key, title: c.label } });
    }
    const alloc = cls.find((c) => c.key === "allocated");
    if (alloc) {
      for (const p of products) {
        const nm = `${p.name} `;
        nodes.push({ name: nm, itemStyle: { color: C.navy }, real: p.cents, receipt: { kind: "class", key: "allocated", product: p.product_id, title: `Allocated to ${p.name}` } });
        links.push({ source: alloc.label, target: nm, value: vis(p.cents), real: p.cents, lineStyle: { color: CLASS_COLOR.allocated }, receipt: { kind: "class", key: "allocated", product: p.product_id, title: `Allocated to ${p.name}` } });
      }
    }
    return {
      animation: false,
      tooltip: {
        trigger: "item",
        formatter: (p: any) => {
          const real = p.data.real ?? 0;
          const label = p.dataType === "edge" ? `${p.data.source} → ${String(p.data.target).trim()}` : String(p.name).trim();
          return `<b>${label}</b><br/>${money(real, currency)} · ${pct(total ? real / total : 0)} of spend<br/><span style="color:#5B6270">Click for the lines</span>`;
        },
      },
      series: [
        {
          type: "sankey",
          left: 8, right: 190, top: 12, bottom: 12,
          nodeWidth: 14, nodeGap: 18, nodeAlign: "left", layoutIterations: 0, draggable: false,
          emphasis: { focus: "adjacency" },
          blur: { lineStyle: { opacity: 0.06 }, itemStyle: { opacity: 0.3 } },
          lineStyle: { curveness: 0.5, opacity: 0.32 },
          label: {
            position: "right", distance: 8,
            color: C.ink, fontFamily: "Inter", fontSize: 13,
            formatter: (p: any) => `{n|${String(p.name).trim()}}\n{v|${money(p.data.real, currency)} · ${pct(total ? p.data.real / total : 0)}}`,
            rich: { n: { fontSize: 13, color: C.ink, fontWeight: 600, lineHeight: 18 }, v: { fontSize: 12, color: C.muted, lineHeight: 16 } },
          },
          data: nodes,
          links,
        },
      ],
    };
  }, [classes, products, total, currency]);
  return (
    <ReactECharts option={option} style={{ height }} opts={{ renderer: "svg" }} notMerge
      onEvents={{ click: (p: any) => p.data?.receipt && onOpen(p.data.receipt) }} />
  );
}
