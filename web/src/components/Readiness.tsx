import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../lib/api";
import { Icon } from "./ui";

export function ReadinessCard({ pid, rd }: { pid: number; rd: any }) {
  const qc = useQueryClient();
  const [fx, setFx] = useState<Record<string, string>>({});
  const save = useMutation({
    mutationFn: () => api(`/projects/${pid}`, { method: "PATCH", json: { fx_overrides: Object.fromEntries(Object.entries(fx).filter(([, v]) => v)) } }),
    onSuccess: () => qc.invalidateQueries(),
  });
  return (
    <section className="card flex flex-col gap-4 p-6" aria-label="Data readiness">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="m-0 text-base font-semibold">Data readiness</h2>
        <span className="text-[13px] text-muted">What your files switch on</span>
      </div>
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {rd.features.map((f: any) => (
          <li key={f.key} className="grid grid-cols-[22px_1fr] gap-2 text-sm">
            <span className={f.on ? "text-human" : "text-muted"}><Icon name={f.on ? "check" : "minus"} size={18} /></span>
            <div>
              <span className="font-semibold">{f.label}</span> <span className={f.on ? "text-human" : "text-muted"}>· {f.on ? "on" : "off"}</span>
              <div className="text-muted">{f.why}{!f.on && f.how && <> <span className="text-ink">How to turn it on:</span> {f.how}</>}</div>
            </div>
          </li>
        ))}
      </ul>
      {rd.unknown_units?.length > 0 && (
        <div className="rounded-xl bg-warn-bg px-4 py-3 text-sm text-warn">
          <strong>Unknown purchase units: {rd.unknown_units.join(", ")}.</strong> They are not guessed. Items using them go to review with a suggested factor, or add the conversion in Rules → Units and packs.
        </div>
      )}
      {rd.missing_fx?.length > 0 && (
        <div className="flex flex-col gap-3 rounded-xl border border-cost-line bg-cost-bg p-4">
          <div className="text-sm font-semibold text-cost">Exchange rates needed to convert to {rd.display_currency}</div>
          <div className="flex flex-wrap gap-3">
            {rd.missing_fx.map((c: string) => (
              <label key={c} className="flex items-center gap-2 text-sm">
                1 {c} =
                <input className="input w-28" inputMode="decimal" value={fx[c] ?? ""} onChange={(e) => setFx({ ...fx, [c]: e.target.value })} aria-label={`Rate from ${c} to ${rd.display_currency}`} />
                {rd.display_currency}
              </label>
            ))}
          </div>
          <div><button type="button" className="btn-primary" onClick={() => save.mutate()}>Save rates</button></div>
        </div>
      )}
    </section>
  );
}
