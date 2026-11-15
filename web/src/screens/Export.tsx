import { useState } from "react";
import { useGate } from "../components/Gate";
import { ErrorNote, H1 } from "../components/ui";
import { download } from "../lib/api";
import { useUI } from "../lib/store";

const SHEETS = ["Links (with evidence, status, overrides flagged)", "Allocation by product", "Spend explainer (8 classes, difference to the spend cube)", "Explainer lines", "BOM cost per product", "Scenario with formula", "Review decisions with timestamps and reasons", "Learned rules", "Rule version (loosened rules flagged)", "Data readiness"];

export default function Export() {
  const { pid, ready, gate, run } = useGate();
  const scenario = useUI((s) => s.scenario);
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  if (!ready) return <>{gate}</>;
  const go = async (fn: () => Promise<void>) => {
    setBusy(true);
    setErr(null);
    try { await fn(); } catch (e) { setErr(e); } finally { setBusy(false); }
  };
  return (
    <>
      <H1 eyebrow="Export">Everything, with an audit trail.</H1>
      <section className="card flex flex-col gap-4 p-6">
        <h2 className="m-0 text-base font-semibold">One Excel workbook</h2>
        <ul className="m-0 grid gap-1 pl-5 text-sm sm:grid-cols-2">{SHEETS.map((s) => <li key={s}>{s}</li>)}</ul>
        <div className="text-sm text-muted">Run {run?.id} · rule version {run?.rule_version}. {scenario ? `Includes your last scenario for ${scenario.part_id}.` : "No scenario yet: export one from Simulate to include it."}</div>
        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-primary" disabled={busy} onClick={() => go(() => download(`/projects/${pid}/export`, { scenario }, "BOMerang.xlsx"))}>Download Excel workbook</button>
          <button type="button" className="btn-ghost" disabled={busy} onClick={() => go(() => download(`/projects/${pid}/export/links.csv`, undefined, "links.csv"))}>Link table as CSV</button>
        </div>
        <ErrorNote error={err} />
      </section>
    </>
  );
}
