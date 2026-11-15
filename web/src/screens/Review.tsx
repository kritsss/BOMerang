import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { AINote, AttributeChips, EvidencePanel } from "../components/Evidence";
import { useGate } from "../components/Gate";
import { AIChip, ErrorNote, H1, Icon, NextBar } from "../components/ui";
import { api } from "../lib/api";
import { money, num, plural } from "../lib/format";
import { useInvalidateRun } from "../lib/hooks";

export default function Review() {
  const { pid, ready, gate } = useGate();
  if (!ready) return <>{gate}</>;
  return <ReviewScreen pid={pid!} />;
}

function ReviewScreen({ pid }: { pid: number }) {
  const q = useQuery({ queryKey: ["review", pid], queryFn: () => api(`/projects/${pid}/review`) });
  const [idx, setIdx] = useState(0);
  const [banner, setBanner] = useState<{ kind: "approve" | "reject" | "undo"; text: string } | null>(null);
  const invalidate = useInvalidateRun();
  const qc = useQueryClient();
  const queue: any[] = q.data?.queue ?? [];
  const cur = queue[Math.min(idx, Math.max(0, queue.length - 1))];
  const currency = q.data?.currency ?? "USD";
  const detail = useQuery({ queryKey: ["item", pid, cur?.item_id], enabled: !!cur, queryFn: () => api(`/projects/${pid}/items/${cur.item_id}`) });
  const [part, setPart] = useState<string>("");
  const [factor, setFactor] = useState<string>("");
  const [reason, setReason] = useState("");
  useEffect(() => {
    setPart(cur?.suggestion_part_id ?? "");
    setFactor(detail.data?.item?.evidence?.unit?.factor ? String(detail.data.item.evidence.unit.factor) : "");
    setReason("");
  }, [cur?.item_id, detail.data?.item?.item_id]); // eslint-disable-line

  const decide = useMutation({
    mutationFn: (body: any) => api(`/projects/${pid}/review/${body.item_id}`, { json: body }),
    onSuccess: (r: any, body: any) => {
      if (body.action === "approve") setBanner({ kind: "approve", text: `Linked. Saved as a rule: ${r.saved_rules.join(" · ")}` });
      else setBanner({ kind: "reject", text: `Not linked. ${money(cur?.spend_cents, currency)} moves to “No match found”, with your reason recorded in the export.` });
      invalidate();
    },
  });
  const undo = useMutation({
    mutationFn: () => api(`/projects/${pid}/review/undo`, { method: "POST" }),
    onSuccess: () => {
      setBanner({ kind: "undo", text: "Undone. The item is back in the queue." });
      invalidate();
    },
  });
  const approve = () => cur && part && decide.mutate({ item_id: cur.item_id, action: "approve", part_id: part, unit_factor: factor ? Number(factor) : null, reason });
  const reject = () => cur && decide.mutate({ item_id: cur.item_id, action: "reject", reason });

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && ["INPUT", "SELECT", "TEXTAREA"].includes(t.tagName)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === "a") approve();
      else if (k === "r") reject();
      else if (k === "u") undo.mutate();
      else if (k === "j") setIdx((i) => Math.min(queue.length - 1, i + 1));
      else if (k === "k") setIdx((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  if (!q.data) return <div className="text-muted">Loading the queue…</div>;
  const k80 = q.data.k80 ?? queue.length;
  const unitUnknown = detail.data?.unit_unknown;
  const it = detail.data?.item;
  const cand = it?.evidence?.candidates?.find((c: any) => c.part_id === part) ?? it?.evidence?.candidates?.[0];
  const partCard = detail.data?.candidates?.find((c: any) => c?.part_id === part) ?? detail.data?.main_part;

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <H1 eyebrow={queue.length ? `Review · card ${Math.min(idx, queue.length - 1) + 1} of ${queue.length}` : "Review"}>
          {queue.length ? (
            <>
              {num(k80)} of {plural(queue.length, "review")} settle 80% of the money waiting.
            </>
          ) : (
            "Nothing is waiting for review."
          )}
        </H1>
        {queue.length > 0 && <CumCurve values={q.data.cumulative} k80={k80} />}
      </div>
      <div className="text-sm text-muted">
        Shortcuts: <kbd>A</kbd> approve · <kbd>R</kbd> not a BOM part · <kbd>U</kbd> undo · <kbd>J</kbd>/<kbd>K</kbd> next / previous · queue ordered by money at stake ({money(q.data.stake_total_cents, currency)} in total)
      </div>

      <AnimatePresence>
        {banner && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
            className={banner.kind === "approve" ? "flex flex-wrap items-center justify-between gap-3 rounded-card bg-human px-5 py-4 text-white" : "flex flex-wrap items-center justify-between gap-3 rounded-card border border-line bg-white px-5 py-4"}>
            <div className="text-sm"><strong>{banner.text}</strong></div>
            <div className="flex gap-2">
              {banner.kind !== "undo" && <button type="button" className={banner.kind === "approve" ? "rounded-lg bg-white px-3 py-1.5 text-sm font-semibold text-human" : "btn-ghost px-3 py-1.5"} onClick={() => undo.mutate()}>Undo</button>}
              <button type="button" className={banner.kind === "approve" ? "rounded-lg border border-white/50 px-3 py-1.5 text-sm" : "btn-ghost px-3 py-1.5"} onClick={() => setBanner(null)} aria-label="Dismiss">Dismiss</button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <ErrorNote error={decide.error || undo.error} />

      {cur && it ? (
        <section className="card flex flex-col gap-6 p-6 md:p-7" aria-label="Link to review">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-1.5 rounded-xl bg-soft p-5">
              <div className="label">Purchased · {plural(it.n_lines, "spend line")}</div>
              <div className="font-display text-xl font-semibold">{it.description}</div>
              <div className="text-sm text-muted">{it.supplier_name}{it.supplier_pn ? ` · ${it.supplier_pn}` : ""}</div>
              <div className="text-sm">
                {it.base_qty != null ? `${num(it.base_qty)} base units` : `qty in ${it.purchase_uom ?? "?"}`}
                {it.price_per_base != null && <> at {money(it.price_per_base * 100, currency)}</>} · <strong>{money(it.spend_cents, currency)}</strong>
              </div>
            </div>
            <div className="flex flex-col gap-1.5 rounded-xl border-2 border-human-line p-5">
              <div className="label flex items-center gap-2">Suggested part in your BOMs {cur.ai_proposed && <AIChip>AI suggested</AIChip>}</div>
              {partCard ? (
                <>
                  <div className="font-display text-xl font-semibold">{partCard.part_id} · {partCard.description}</div>
                  <div className="text-sm text-muted">
                    {partCard.used_in?.length ? "Used in " + partCard.used_in.map((u: any) => `${u.name} (${num(u.qty_per_unit, 3)} per unit)`).join(", ") : "Not in any BOM"}
                  </div>
                  <div className="text-sm">{partCard.required != null ? <>Needed: {num(partCard.required)} {partCard.base_uom} over the period</> : "No volumes: demand unknown"}</div>
                </>
              ) : (
                <div className="text-sm text-muted">No suggestion. Pick a part below or mark as not a BOM part.</div>
              )}
            </div>
          </div>
          <div className="text-sm"><strong>Why it is here: </strong>{it.reason}</div>
          {cand && (
            <div className="flex flex-col gap-2">
              <div className="label">Attribute check</div>
              <AttributeChips attrs={cand.attrs} />
            </div>
          )}
          <AINote ai={it.evidence?.ai} />
          <EvidencePanel item={{ ...it, suggestion_part_id: part || it.suggestion_part_id }} currency={currency} />
          <details className="rounded-xl border border-line p-4">
            <summary className="cursor-pointer text-sm font-semibold">Lines behind this item ({detail.data.lines.length})</summary>
            <table className="mt-3 w-full text-sm">
              <tbody>
                {detail.data.lines.map((l: any) => (
                  <tr key={l.line_id} className="border-t border-line">
                    <td className="py-1.5 pr-3">{l.line_id}</td>
                    <td className="py-1.5 pr-3">{l.description}</td>
                    <td className="py-1.5 pr-3 text-right tabnum">{num(l.qty, 2)} {l.purchase_uom}</td>
                    <td className="py-1.5 pr-3 text-right tabnum">{l.unit_price != null ? num(l.unit_price, 4) : ""} {l.currency}</td>
                    <td className="py-1.5 pr-3">{l.month}</td>
                    <td className="py-1.5 text-right tabnum">{money(l.cents, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
          <div className="flex flex-wrap items-end gap-3 border-t border-line pt-5">
            <label className="flex flex-col gap-1 text-sm font-semibold">
              Link to part
              <PartPicker value={part} onChange={setPart} options={detail.data.part_options} candidates={(it.evidence?.candidates ?? []).filter((c: any) => c.verdict !== "refused").map((c: any) => c.part_id)} />
            </label>
            {unitUnknown && (
              <label className="flex flex-col gap-1 text-sm font-semibold">
                1 {it.purchase_uom ?? "unit"} = how many {partCard?.base_uom ?? "base units"}?
                <input className="input w-28" inputMode="decimal" value={factor} onChange={(e) => setFactor(e.target.value)} required />
              </label>
            )}
            <label className="flex min-w-[220px] flex-1 flex-col gap-1 text-sm font-semibold">
              Note (optional, goes to the export)
              <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} />
            </label>
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="button" className="btn-human px-6 py-3 text-[15px]" onClick={approve} disabled={!part || decide.isPending || (unitUnknown && !factor)}>
              Approve link <kbd className="border-white/40 bg-white/20 text-white">A</kbd>
            </button>
            <button type="button" className="btn-cost px-6 py-3 text-[15px]" onClick={reject} disabled={decide.isPending}>
              Not a BOM part <kbd>R</kbd>
            </button>
            <button type="button" className="btn-ghost px-6 py-3 text-[15px]" onClick={() => undo.mutate()} disabled={!q.data.decided_count}>
              Undo <kbd>U</kbd>
            </button>
            <div className="ml-auto flex gap-2">
              <button type="button" className="btn-ghost" onClick={() => setIdx((i) => Math.max(0, i - 1))} aria-label="Previous (K)">← K</button>
              <button type="button" className="btn-ghost" onClick={() => setIdx((i) => Math.min(queue.length - 1, i + 1))} aria-label="Next (J)">J →</button>
            </div>
          </div>
        </section>
      ) : cur ? (
        <div className="text-muted">Loading the card…</div>
      ) : (
        <NextBar text="Every uncertain link has been decided. The numbers are final.">
          <Link to="/money" className="rounded-[10px] bg-white px-5 py-3 text-[15px] font-semibold text-ink no-underline">Money flow →</Link>
        </NextBar>
      )}

      {queue.length > 1 && <QueueList queue={queue} idx={idx} setIdx={setIdx} currency={currency} />}
      <RefusedList pid={pid} refused={q.data.refused} currency={currency} onDone={(t) => { setBanner({ kind: "approve", text: t }); invalidate(); qc.invalidateQueries(); }} />
      {queue.length > 0 && (
        <NextBar text="Done for now? Unreviewed items stay in “Pending review” in the money flow.">
          <Link to="/money" className="rounded-[10px] bg-white px-5 py-3 text-[15px] font-semibold text-ink no-underline">Money flow →</Link>
        </NextBar>
      )}
    </>
  );
}

function PartPicker({ value, onChange, options, candidates }: { value: string; onChange: (v: string) => void; options: any[]; candidates: string[] }) {
  const [q, setQ] = useState("");
  const list = useMemo(() => {
    const s = q.toLowerCase();
    const cand = options.filter((o) => candidates.includes(o.part_id));
    const rest = options.filter((o) => !candidates.includes(o.part_id) && (!s || `${o.part_id} ${o.description}`.toLowerCase().includes(s))).slice(0, 200);
    return { cand, rest };
  }, [q, options, candidates]);
  return (
    <div className="flex gap-2">
      <input className="input w-40" placeholder="Filter parts…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter parts" />
      <select className="input w-[320px]" value={value} onChange={(e) => onChange(e.target.value)} aria-label="Part to link to">
        <option value="">— choose a part —</option>
        {list.cand.length > 0 && (
          <optgroup label="Candidates">
            {list.cand.map((o) => <option key={o.part_id} value={o.part_id}>{o.part_id} · {o.description}</option>)}
          </optgroup>
        )}
        <optgroup label="All parts">
          {list.rest.map((o) => <option key={o.part_id} value={o.part_id}>{o.part_id} · {o.description}</option>)}
        </optgroup>
      </select>
    </div>
  );
}

function CumCurve({ values, k80 }: { values: number[]; k80: number }) {
  const w = 220, h = 64;
  const n = values.length;
  const pts = [[0, h], ...values.map((v, i) => [((i + 1) / n) * w, h - v * h])];
  return (
    <figure className="m-0 flex flex-col items-end gap-1">
      <svg width={w} height={h + 4} role="img" aria-label={`Cumulative share of money at stake: ${k80} of ${n} reviews reach 80%`}>
        <line x1={0} x2={w} y1={h - 0.8 * h} y2={h - 0.8 * h} stroke="#E5E7EB" strokeDasharray="3 3" />
        <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke="#0F766E" strokeWidth={2} />
        <circle cx={(k80 / n) * w} cy={h - (values[k80 - 1] ?? 1) * h} r={4} fill="#fff" stroke="#0F766E" strokeWidth={2} />
      </svg>
      <figcaption className="text-xs text-muted">money settled as you review, dashed = 80%</figcaption>
    </figure>
  );
}

function QueueList({ queue, idx, setIdx, currency }: { queue: any[]; idx: number; setIdx: (i: number) => void; currency: string }) {
  return (
    <section className="card p-6" aria-label="Review queue">
      <h2 className="m-0 mb-3 text-base font-semibold">Queue · by money at stake</h2>
      <ol className="m-0 flex list-none flex-col p-0">
        {queue.slice(0, 50).map((r, i) => (
          <li key={r.item_id}>
            <button type="button" onClick={() => setIdx(i)} className={`grid w-full grid-cols-[28px_1fr_auto] gap-3 rounded-lg px-2 py-2 text-left text-sm ${i === idx ? "bg-soft font-semibold" : "hover:bg-soft"}`}>
              <span className="text-muted">{i + 1}</span>
              <span className="truncate">{r.description} <span className="font-normal text-muted">· {r.supplier_name} → {r.suggestion_part_id ?? "?"}</span> {r.ai_proposed && <span className="text-ai">· AI</span>}</span>
              <span className="tabnum">{money(r.money_at_stake_cents, currency)}</span>
            </button>
          </li>
        ))}
      </ol>
    </section>
  );
}

function RefusedList({ pid, refused, currency, onDone }: { pid: number; refused: any[]; currency: string; onDone: (t: string) => void }) {
  const [open, setOpen] = useState<string | null>(null);
  const [why, setWhy] = useState("");
  const m = useMutation({
    mutationFn: (r: any) => api(`/projects/${pid}/review/${r.item_id}`, { json: { action: "approve", part_id: r.suggestion_part_id, override_reason: why } }),
    onSuccess: (r: any) => { setOpen(null); setWhy(""); onDone(`Override saved with your reason. Flagged in the export. ${r.saved_rules.join(" · ")}`); },
  });
  if (!refused.length) return null;
  return (
    <details className="card p-6">
      <summary className="cursor-pointer text-base font-semibold">Refused automatically · {refused.length} (no review needed)</summary>
      <ul className="m-0 mt-4 flex list-none flex-col gap-3 p-0">
        {refused.map((r) => (
          <li key={r.item_id} className="flex flex-col gap-2 rounded-xl border border-cost-line bg-cost-bg px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="text-sm">
                <strong>{r.description}</strong> · {r.supplier_name} · {money(r.spend_cents, currency)}
                <div className="text-cost">{r.reason}</div>
              </div>
              <span className="chip bg-white text-cost"><Icon name="ban" size={14} />Hard attribute differs</span>
            </div>
            {r.suggestion_part_id && (open === r.item_id ? (
              <div className="flex flex-wrap items-end gap-2">
                <label className="flex flex-1 flex-col gap-1 text-sm font-semibold">
                  Written reason to override (required, flagged in the export)
                  <input className="input" value={why} onChange={(e) => setWhy(e.target.value)} />
                </label>
                <button type="button" className="btn-human" disabled={!why.trim() || m.isPending} onClick={() => m.mutate(r)}>Link to {r.suggestion_part_id} anyway</button>
                <button type="button" className="btn-ghost" onClick={() => setOpen(null)}>Cancel</button>
              </div>
            ) : (
              <button type="button" className="self-start text-[13px] font-semibold text-cost underline" onClick={() => setOpen(r.item_id)}>Override with a reason…</button>
            ))}
          </li>
        ))}
      </ul>
      <ErrorNote error={m.error} />
    </details>
  );
}
