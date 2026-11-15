import { useState, type ReactNode } from "react";

/** Every chart has a text alternative: a table view toggle. */
export function ChartCard({ title, note, chart, table, className = "", actions }: { title: ReactNode; note?: ReactNode; chart: ReactNode; table: ReactNode; className?: string; actions?: ReactNode }) {
  const [asTable, setAsTable] = useState(false);
  return (
    <section className={`card flex flex-col gap-4 p-6 ${className}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 className="m-0 text-base font-semibold">{title}</h2>
        <div className="flex items-center gap-3">
          {note && <span className="text-[13px] text-muted">{note}</span>}
          {actions}
          <button type="button" className="text-[13px] font-semibold text-save underline-offset-4 hover:underline" aria-pressed={asTable} onClick={() => setAsTable((v) => !v)}>
            {asTable ? "Chart view" : "Table view"}
          </button>
        </div>
      </div>
      {asTable ? <div className="overflow-auto">{table}</div> : chart}
    </section>
  );
}

export function SimpleTable({ head, rows }: { head: string[]; rows: ReactNode[][] }) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-line text-left text-xs text-muted">
          {head.map((h) => (
            <th key={h} className="py-2 pr-4 font-semibold">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} className="border-b border-line">
            {r.map((c, j) => (
              <td key={j} className="py-2 pr-4 tabnum">
                {c}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
