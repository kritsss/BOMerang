import * as Tabs from "@radix-ui/react-tabs";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Drawer } from "../components/Drawer";
import { ErrorNote } from "../components/ui";
import { api } from "../lib/api";
import { pct } from "../lib/format";
import { useInvalidateRun, useProject } from "../lib/hooks";
import { useUI } from "../lib/store";

const TABS = [
  ["syn", "Synonyms and translations"],
  ["hard", "Hard attributes per category"],
  ["units", "Units and packs"],
  ["price", "Price band"],
  ["th", "Thresholds"],
  ["xref", "Approved and learned cross-references"],
  ["shop", "Service and shop supplies"],
  ["ver", "Versions"],
];

export function RulesDrawer() {
  const open = useUI((s) => s.rulesOpen);
  const setOpen = useUI((s) => s.setRules);
  const { pid } = useProject();
  return (
    <Drawer open={open} onClose={() => setOpen(false)} title="Matching rules" width="max-w-[980px]">
      {pid ? <RulesBody pid={pid} /> : <div className="text-muted">Create a project first.</div>}
    </Drawer>
  );
}

function RulesBody({ pid }: { pid: number }) {
  const q = useQuery({ queryKey: ["rules", pid], queryFn: () => api(`/projects/${pid}/rules`) });
  const [draft, setDraft] = useState<any>(null);
  const [why, setWhy] = useState("");
  const [who, setWho] = useState("analyst");
  const invalidate = useInvalidateRun();
  useEffect(() => { if (q.data) setDraft(structuredClone(q.data.rules)); }, [q.data]);
  const dirty = useMemo(() => draft && q.data && JSON.stringify(draft) !== JSON.stringify(q.data.rules), [draft, q.data]);
  const preview = useMutation({ mutationFn: () => api(`/projects/${pid}/rules/preview`, { json: { rules: draft, who, why } }) });
  const apply = useMutation({
    mutationFn: () => api(`/projects/${pid}/rules`, { json: { rules: draft, who, why } }),
    onSuccess: () => { preview.reset(); setWhy(""); invalidate(); setTimeout(invalidate, 1500); setTimeout(invalidate, 5000); },
  });
  if (!q.data || !draft) return <div className="text-muted">Loading…</div>;
  const set = (k: string, v: any) => setDraft({ ...draft, [k]: v });
  return (
    <div className="flex flex-col gap-5">
      <div className="text-sm text-muted">Forms and tables only. Every change is versioned (now v{q.data.version}) with who, when and why; exports state the rule version. Preview the impact before applying.</div>
      <Tabs.Root defaultValue="syn" className="flex flex-col gap-4">
        <Tabs.List className="flex flex-wrap gap-1" aria-label="Rule groups">
          {TABS.map(([k, l]) => <Tabs.Trigger key={k} value={k} className="rounded-full px-3 py-1.5 text-[13px] font-semibold data-[state=active]:bg-ink data-[state=active]:text-white data-[state=inactive]:bg-soft">{l}</Tabs.Trigger>)}
        </Tabs.List>
        <Tabs.Content value="syn"><EditTable rows={draft.synonyms} cols={[["term", "Term on invoices"], ["canonical", "Means"], ["group", "Group"]]} onChange={(v) => set("synonyms", v)} note="Applied after lowercasing, longest term first. A group named like a material-master column (e.g. 'material') adds its words to that attribute's vocabulary, so an invoice value that is not in your master can still be recognised as different." /></Tabs.Content>
        <Tabs.Content value="hard"><HardAttrs draft={draft} attrs={q.data.attribute_columns} cats={q.data.categories} onChange={(v) => set("hard_attributes", v)} /></Tabs.Content>
        <Tabs.Content value="units"><EditTable rows={draft.unit_conversions} cols={[["purchase_uom", "Purchase unit"], ["base_uom", "Base unit"], ["factor", "Factor (base units per purchase unit)"]]} onChange={(v) => set("unit_conversions", v.map((r: any) => ({ ...r, factor: r.factor === "" ? "" : Number(r.factor) })))} note="Built in: EA/PC, C = 100, M = 1000 (for count units), DZ = 12, mm/cm/m/in/ft, g/kg/lb/oz, ml/l. PK and boxes only if defined here. Learned unit rules from review appear under cross-references." /></Tabs.Content>
        <Tabs.Content value="price">
          <div className="flex flex-wrap gap-4">
            <NumIn label="Low (× expected price)" v={draft.price_band.low} onChange={(v) => set("price_band", { ...draft.price_band, low: v })} />
            <NumIn label="High (× expected price)" v={draft.price_band.high} onChange={(v) => set("price_band", { ...draft.price_band, high: v })} />
          </div>
          <p className="text-sm text-muted">A spec-rule link whose price per base unit falls outside this band goes to review as “price outside expected range”. Expected = weighted average of certain links, else standard cost. Widening the band needs a written reason.</p>
        </Tabs.Content>
        <Tabs.Content value="th">
          <div className="grid gap-4 sm:grid-cols-2">
            <NumIn label="Auto-link minimum text similarity (0–1)" v={draft.thresholds.auto_link_min_text} onChange={(v) => set("thresholds", { ...draft.thresholds, auto_link_min_text: v })} />
            <NumIn label="Quantity balance margin" v={draft.thresholds.balance_margin} onChange={(v) => set("thresholds", { ...draft.thresholds, balance_margin: v })} />
            <NumIn label="Minimum similarity for a candidate (0–1)" v={draft.thresholds.min_similarity} onChange={(v) => set("thresholds", { ...draft.thresholds, min_similarity: v })} />
            <NumIn label="Candidates compared per item" v={draft.thresholds.candidate_top_k} onChange={(v) => set("thresholds", { ...draft.thresholds, candidate_top_k: v })} />
            <NumIn label="Money-at-stake floor for review items" v={draft.thresholds.review_money_floor} onChange={(v) => set("thresholds", { ...draft.thresholds, review_money_floor: v })} />
          </div>
        </Tabs.Content>
        <Tabs.Content value="xref"><Learned pid={pid} /></Tabs.Content>
        <Tabs.Content value="shop">
          <div className="grid gap-4 sm:grid-cols-2">
            <ListIn label="Service keywords (cost center or description)" v={draft.service_keywords} onChange={(v) => set("service_keywords", v)} />
            <ListIn label="Shop-supply cost centers" v={draft.shop_supply_cost_centers} onChange={(v) => set("shop_supply_cost_centers", v)} />
            <ListIn label="Shop-supply categories (material master)" v={draft.shop_supply_categories} onChange={(v) => set("shop_supply_categories", v)} hint={q.data.categories.length ? `Categories in your master: ${q.data.categories.join(", ")}` : undefined} />
            <ListIn label="Shop-supply description keywords" v={draft.shop_supply_keywords} onChange={(v) => set("shop_supply_keywords", v)} />
          </div>
        </Tabs.Content>
        <Tabs.Content value="ver"><Versions pid={pid} /></Tabs.Content>
      </Tabs.Root>

      <div className="sticky bottom-0 flex flex-col gap-3 border-t border-line bg-white pt-4">
        {preview.data && (
          <div className="rounded-xl bg-soft p-4 text-sm" aria-live="polite">
            <strong>Impact:</strong> adds {preview.data.adds} link(s), removes {preview.data.removes}, changes {preview.data.changed}, moves {preview.data.to_review} to review ({preview.data.from_review} leave review). Spend explained {pct(preview.data.explained_before)} → <strong>{pct(preview.data.explained_after)}</strong>.
            {preview.data.wrong_before != null && <> Wrong links (answer key) {preview.data.wrong_before} → <strong>{preview.data.wrong_after}</strong>.</>}
            {preview.data.loosened?.length > 0 && <div className="mt-2 text-cost"><strong>Loosening:</strong> {preview.data.loosened.join("; ")}. A written reason is required and this is flagged in exports.</div>}
          </div>
        )}
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-sm font-semibold">Who<input className="input w-36" value={who} onChange={(e) => setWho(e.target.value)} /></label>
          <label className="flex min-w-[240px] flex-1 flex-col gap-1 text-sm font-semibold">Why (required when loosening)<input className="input" value={why} onChange={(e) => setWhy(e.target.value)} /></label>
          <button type="button" className="btn-ghost" disabled={!dirty || preview.isPending} onClick={() => preview.mutate()}>{preview.isPending ? "Re-running…" : "Preview impact"}</button>
          <button type="button" className="btn-primary" disabled={!dirty || apply.isPending} onClick={() => apply.mutate()}>Apply and re-link</button>
          {dirty && <button type="button" className="btn-ghost" onClick={() => { setDraft(structuredClone(q.data.rules)); preview.reset(); }}>Discard</button>}
        </div>
        <ErrorNote error={preview.error || apply.error} />
        {apply.isSuccess && <div className="text-sm text-human">Saved as v{(apply.data as any).version}. Re-linking in the background.</div>}
      </div>
    </div>
  );
}

function EditTable({ rows, cols, onChange, note }: { rows: any[]; cols: [string, string][]; onChange: (v: any[]) => void; note?: string }) {
  const [filter, setFilter] = useState("");
  const shown = rows.map((r, i) => [r, i] as const).filter(([r]) => !filter || JSON.stringify(r).toLowerCase().includes(filter.toLowerCase()));
  return (
    <div className="flex flex-col gap-3">
      {note && <p className="m-0 text-sm text-muted">{note}</p>}
      <div className="flex gap-2">
        <input className="input max-w-xs" placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter rows" />
        <button type="button" className="btn-ghost" onClick={() => onChange([Object.fromEntries(cols.map(([k]) => [k, ""])), ...rows])}>Add row</button>
      </div>
      <div className="max-h-[45vh] overflow-auto rounded-xl border border-line">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-soft"><tr>{cols.map(([, l]) => <th key={l} className="px-2 py-2 text-left text-xs font-semibold text-muted">{l}</th>)}<th /></tr></thead>
          <tbody>
            {shown.map(([r, i]) => (
              <tr key={i} className="border-t border-line">
                {cols.map(([k, l]) => (
                  <td key={k} className="px-1 py-1"><input className="input py-1" aria-label={l} value={r[k] ?? ""} onChange={(e) => onChange(rows.map((x, j) => (j === i ? { ...x, [k]: e.target.value } : x)))} /></td>
                ))}
                <td className="px-1"><button type="button" className="text-xs font-semibold text-cost" onClick={() => onChange(rows.filter((_, j) => j !== i))} aria-label="Remove row">Remove</button></td>
              </tr>
            ))}
            {!shown.length && <tr><td colSpan={cols.length + 1} className="px-3 py-4 text-muted">No rows.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function HardAttrs({ draft, attrs, cats, onChange }: { draft: any; attrs: string[]; cats: string[]; onChange: (v: any) => void }) {
  const ha = draft.hard_attributes ?? { "*": [] };
  if (!attrs.length) return <p className="text-sm text-muted">No attribute columns yet. Upload a material master and tick its attribute columns during mapping.</p>;
  const rows = ["*", ...cats];
  const toggle = (cat: string, a: string) => {
    const curList: string[] = cat in ha ? ha[cat] : [...(ha["*"] ?? [])];
    const next = curList.includes(a) ? curList.filter((x) => x !== a) : [...curList, a];
    onChange({ ...ha, [cat]: next });
  };
  return (
    <div className="flex flex-col gap-3">
      <p className="m-0 text-sm text-muted">A difference on a hard attribute refuses the link. “All categories” applies where a category has no row of its own. A hard attribute only applies to categories where the master fills it. Un-ticking (loosening) needs a written reason.</p>
      <div className="overflow-auto rounded-xl border border-line">
        <table className="w-full text-sm">
          <thead className="bg-soft"><tr><th className="px-3 py-2 text-left text-xs text-muted">Category</th>{attrs.map((a) => <th key={a} className="px-3 py-2 text-xs text-muted">{a}</th>)}<th /></tr></thead>
          <tbody>
            {rows.map((c) => {
              const own = c in ha;
              const list: string[] = own ? ha[c] : ha["*"] ?? [];
              return (
                <tr key={c} className="border-t border-line">
                  <td className="px-3 py-2">{c === "*" ? <strong>All categories</strong> : c}{c !== "*" && !own && <span className="text-xs text-muted"> (uses all)</span>}</td>
                  {attrs.map((a) => <td key={a} className="px-3 py-2 text-center"><input type="checkbox" aria-label={`${a} hard for ${c === "*" ? "all categories" : c}`} checked={list.includes(a)} onChange={() => toggle(c, a)} /></td>)}
                  <td className="px-2">{c !== "*" && own && <button type="button" className="text-xs text-save" onClick={() => { const n = { ...ha }; delete n[c]; onChange(n); }}>Reset</button>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function NumIn({ label, v, onChange }: { label: string; v: number; onChange: (v: number) => void }) {
  return <label className="flex flex-col gap-1 text-sm font-semibold">{label}<input className="input w-40" type="number" step="any" value={v} onChange={(e) => onChange(Number(e.target.value))} /></label>;
}

function ListIn({ label, v, onChange, hint }: { label: string; v: string[]; onChange: (v: string[]) => void; hint?: string }) {
  const [t, setT] = useState((v ?? []).join(", "));
  useEffect(() => setT((v ?? []).join(", ")), [v]);
  return (
    <label className="flex flex-col gap-1 text-sm font-semibold">
      {label}
      <textarea className="input min-h-[70px]" value={t} onChange={(e) => setT(e.target.value)} onBlur={() => onChange(t.split(",").map((s) => s.trim()).filter(Boolean))} />
      <span className="text-xs font-normal text-muted">Comma separated.{hint ? ` ${hint}` : ""}</span>
    </label>
  );
}

function Learned({ pid }: { pid: number }) {
  const q = useQuery({ queryKey: ["learned", pid], queryFn: () => api<any[]>(`/projects/${pid}/learned`) });
  const invalidate = useInvalidateRun();
  const rm = useMutation({ mutationFn: (id: number) => api(`/projects/${pid}/learned/${id}`, { method: "DELETE" }), onSuccess: () => { invalidate(); setTimeout(invalidate, 2000); } });
  const rows = q.data ?? [];
  return (
    <div className="flex flex-col gap-2">
      <p className="m-0 text-sm text-muted">Approved cross-references come from your uploaded file. Learned rules come from review decisions and apply on every later run. Removing one re-links.</p>
      {!rows.length && <div className="text-sm text-muted">No learned rules yet.</div>}
      {rows.map((r) => (
        <div key={r.id} className={`flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line px-3 py-2 text-sm ${r.active ? "" : "opacity-50"}`}>
          <div><span className="chip mr-2 bg-human-bg text-human">{r.kind}</span><strong>{r.text}</strong><div className="text-xs text-muted">{r.who} · {r.created_at} · {r.why}</div></div>
          {r.active ? <button type="button" className="btn-ghost px-3 py-1" onClick={() => rm.mutate(r.id)}>Remove</button> : <span className="text-xs">removed</span>}
        </div>
      ))}
    </div>
  );
}

function Versions({ pid }: { pid: number }) {
  const q = useQuery({ queryKey: ["rules", "versions", pid], queryFn: () => api<any[]>(`/projects/${pid}/rules/versions`) });
  return (
    <div className="flex flex-col gap-2">
      {!q.data?.length && <div className="text-sm text-muted">Default rules (v0). No changes yet.</div>}
      {q.data?.map((v) => (
        <div key={v.version} className="rounded-lg border border-line px-3 py-2 text-sm">
          <strong>v{v.version}</strong> · {v.who} · {v.created_at} · {v.why || "no reason given"}
          {v.loosened?.length > 0 && <div className="text-cost">Loosened: {v.loosened.join("; ")}</div>}
        </div>
      ))}
    </div>
  );
}
