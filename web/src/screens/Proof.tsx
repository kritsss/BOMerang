import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { useGate } from "../components/Gate";
import { EmptyState, ErrorNote, H1 } from "../components/ui";
import { api } from "../lib/api";
import { money, num, pct } from "../lib/format";

export default function Proof() {
  const { pid, ready, gate, summary } = useGate();
  const q = useQuery({ queryKey: ["proof", pid], enabled: ready, queryFn: () => api(`/projects/${pid}/proof`), staleTime: 60_000 });
  if (!ready) return <>{gate}</>;
  const cur = summary?.display_currency ?? "USD";
  return (
    <>
      <H1 eyebrow="Proof">How well does the matching hold against your answer key?</H1>
      {q.isLoading ? (
        <div className="text-muted">Running the three modes on your data… this re-runs matching three times.</div>
      ) : q.error ? (
        <ErrorNote error={q.error} />
      ) : !q.data?.available ? (
        <EmptyState title="Upload an answer key to see the proof">
          An answer key has columns <code>line_id</code>, <code>true_part_id</code> (or <code>NONE</code>) and optionally <code>class</code>. It is used only here and is never shown to the matcher.
        </EmptyState>
      ) : (
        q.data.datasets.map((ds: any) => (
          <section key={ds.spend_file} className="card overflow-auto p-6">
            <h2 className="m-0 mb-1 text-base font-semibold">Spend file: {ds.spend_file}</h2>
            <p className="m-0 mb-4 text-sm text-muted">Only numbers this run produced. Precision = correct automatic links ÷ all automatic links, by item.</p>
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted">
                  {["Mode", "Spend linked automatically", "Precision", "Wrong links", "Wrong-link money", "Look-alikes wrongly linked", "Sent to review", "Review suggestion right"].map((h) => <th key={h} className="py-2 pr-4">{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {ds.rows.map((r: any, i: number) => (
                  <tr key={r.mode} className={clsx("border-b border-line", i === ds.rows.length - 1 && "bg-save-bg font-semibold")}>
                    <td className="py-2.5 pr-4">{r.mode}</td>
                    <td className="py-2.5 pr-4 tabnum">{pct(r.auto_share_spend)}</td>
                    <td className="py-2.5 pr-4 tabnum">{r.precision == null ? "–" : pct(r.precision)}</td>
                    <td className="py-2.5 pr-4 tabnum">{num(r.wrong_links)}</td>
                    <td className="py-2.5 pr-4 tabnum">{money(r.wrong_money_cents, cur)}</td>
                    <td className={clsx("py-2.5 pr-4 tabnum", r.lookalikes_wrongly_linked > 0 && "text-cost")}>{num(r.lookalikes_wrongly_linked)}</td>
                    <td className="py-2.5 pr-4 tabnum">{num(r.sent_to_review)}</td>
                    <td className="py-2.5 pr-4 tabnum">{r.review_suggestion_right == null ? "–" : pct(r.review_suggestion_right)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="m-0 mt-3 text-xs text-muted">Text similarity only = link to the most similar description when similarity ≥ 0.5. Rules only = exact IDs, cross-references and spec rules, without quantity or price evidence. Full = everything (your review decisions excluded). Items: {ds.rows[0]?.items}.</p>
          </section>
        ))
      )}
    </>
  );
}
