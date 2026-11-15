import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { num } from "../lib/format";
import { ErrorNote, Icon } from "./ui";

export function Dropzone({ pid }: { pid: number }) {
  const qc = useQueryClient();
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const up = useMutation({
    mutationFn: async (files: FileList | File[]) => {
      const fd = new FormData();
      Array.from(files).forEach((f) => fd.append("files", f));
      return api(`/projects/${pid}/uploads`, { method: "POST", body: fd });
    },
    onSuccess: (added: any) => {
      qc.setQueryData(["uploads", pid], (old: any[] | undefined) => [...(old ?? []).filter((o) => !added.some((a: any) => a.id === o.id)), ...added]);
      qc.invalidateQueries({ queryKey: ["uploads"] });
      qc.invalidateQueries({ queryKey: ["readiness"] });
    },
  });
  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); if (e.dataTransfer.files.length) up.mutate(e.dataTransfer.files); }}
        className={clsx("flex flex-col items-center justify-center gap-3 rounded-card border-2 border-dashed px-6 py-10 text-center transition-colors", drag ? "border-save bg-save-bg" : "border-line bg-white")}
      >
        <div className="font-display text-xl font-semibold">Drop CSV or Excel files here</div>
        <div className="max-w-xl text-sm text-muted">
          Required: a <strong>BOM</strong> and a <strong>spend</strong> file. Optional files unlock more: material master, production volumes, products, suppliers, unit conversions, FX rates, approved cross-references, an answer key. An Excel workbook can hold several tabs.
        </div>
        <button type="button" className="btn-primary" onClick={() => input.current?.click()} disabled={up.isPending}>
          {up.isPending ? "Reading files…" : "Choose files"}
        </button>
        <input ref={input} type="file" multiple accept=".csv,.txt,.xlsx,.xlsm,.xls" className="sr-only" aria-label="Choose files to upload" onChange={(e) => e.target.files && up.mutate(e.target.files)} />
      </div>
      <ErrorNote error={up.error} />
    </div>
  );
}

export function FileList({ pid }: { pid: number }) {
  const uploads = useQuery({ queryKey: ["uploads", pid], queryFn: () => api<any[]>(`/projects/${pid}/uploads`) });
  const schema = useQuery({ queryKey: ["schema"], queryFn: () => api("/schema"), staleTime: Infinity });
  const [open, setOpen] = useState<number | null>(null);
  const qc = useQueryClient();
  const del = useMutation({
    mutationFn: (id: number) => api(`/projects/${pid}/uploads/${id}`, { method: "DELETE" }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["uploads"] }); qc.invalidateQueries({ queryKey: ["readiness"] }); },
  });
  const list = (uploads.data ?? []).filter((u) => u.status !== "replaced");
  useEffect(() => {
    if (open === null) {
      const first = list.find((u) => u.status === "needs_mapping");
      if (first) setOpen(first.id);
    }
  }, [uploads.data]); // eslint-disable-line
  if (!list.length) return null;
  const labels: Record<string, string> = Object.fromEntries((schema.data?.types ?? []).map((t: any) => [t.key, t.label]));
  return (
    <section className="card flex flex-col gap-3 p-6" aria-label="Your files">
      <h2 className="m-0 text-base font-semibold">Your files</h2>
      {list.map((u) => (
        <div key={u.id} className="rounded-xl border border-line">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">{u.filename}{u.sheet ? ` · ${u.sheet}` : ""}</div>
              <div className="text-xs text-muted">{num(u.n_rows)} rows · {u.columns.length} columns</div>
            </div>
            <div className="flex items-center gap-2">
              {u.status === "mapped" ? (
                <span className="chip bg-human-bg text-human"><Icon name="check" size={14} />{labels[u.file_type] ?? u.file_type} · mapped</span>
              ) : (
                <span className="chip bg-warn-bg text-warn"><Icon name="warn" size={14} />Needs column mapping</span>
              )}
              <button type="button" className="btn-ghost px-3 py-1.5" onClick={() => setOpen(open === u.id ? null : u.id)} aria-expanded={open === u.id}>
                {open === u.id ? "Close" : u.status === "mapped" ? "Edit mapping" : "Map columns"}
              </button>
              <button type="button" className="btn-ghost px-3 py-1.5" onClick={() => del.mutate(u.id)} aria-label={`Remove ${u.filename}`}>Remove</button>
            </div>
          </div>
          {open === u.id && schema.data && <MappingPanel pid={pid} upload={u} schema={schema.data} onDone={() => setOpen(list.find((x) => x.status === "needs_mapping" && x.id !== u.id)?.id ?? null)} />}
        </div>
      ))}
    </section>
  );
}

function MappingPanel({ pid, upload, schema, onDone }: { pid: number; upload: any; schema: any; onDone: () => void }) {
  const qc = useQueryClient();
  const [type, setType] = useState<string>(upload.file_type ?? upload.suggested_type);
  const [mapping, setMapping] = useState<Record<string, string | null>>(upload.mapping);
  const [attrs, setAttrs] = useState<string[]>(upload.attribute_columns ?? []);
  const [hard, setHard] = useState<string[]>(upload.hard_suggestion ?? []);
  const [touchedType, setTouchedType] = useState(false);
  useEffect(() => {
    if (!touchedType) return;
    api(`/projects/${pid}/uploads/${upload.id}/suggest?file_type=${type}`).then((r: any) => {
      setMapping(r.mapping);
      setAttrs(r.attribute_candidates);
      setHard(r.hard_suggestion);
    });
  }, [type]); // eslint-disable-line
  const save = useMutation({
    mutationFn: () => api(`/projects/${pid}/uploads/${upload.id}/mapping`, { json: { file_type: type, mapping, attribute_columns: type === "master" ? attrs : [], hard_attributes: type === "master" ? hard : null } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["uploads"] });
      qc.invalidateQueries({ queryKey: ["readiness"] });
      qc.invalidateQueries({ queryKey: ["rules"] });
      onDone();
    },
  });
  const t = schema.types.find((x: any) => x.key === type);
  const used = new Set(Object.values(mapping).filter(Boolean));
  const attrCands = upload.columns.filter((c: string) => !used.has(c));
  return (
    <div className="flex flex-col gap-4 border-t border-line px-4 py-4">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm font-semibold" htmlFor={`ft-${upload.id}`}>This file is</label>
        <select id={`ft-${upload.id}`} className="input max-w-[280px]" value={type} onChange={(e) => { setTouchedType(true); setType(e.target.value); }}>
          {schema.types.map((x: any) => <option key={x.key} value={x.key}>{x.label}</option>)}
        </select>
        {upload.saved_mapping && !upload.file_type && <span className="chip bg-human-bg text-human">Saved mapping found: one click</span>}
      </div>
      <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {t.fields.map((f: any) => (
          <label key={f.name} className="grid grid-cols-[170px_1fr] items-center gap-2 text-sm">
            <span>
              {f.name}
              {f.required && <span className="text-cost"> *</span>}
            </span>
            <select className="input" value={mapping[f.name] ?? ""} onChange={(e) => setMapping({ ...mapping, [f.name]: e.target.value || null })}>
              <option value="">— not in this file —</option>
              {upload.columns.map((c: string) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
        ))}
      </div>
      {type === "master" && (
        <div className="flex flex-col gap-2 rounded-xl bg-soft p-4">
          <div className="text-sm font-semibold">Attribute columns</div>
          <div className="text-xs text-muted">Tick the columns that describe the part (material, size, hardness…). Mark which are <strong>hard</strong>: a difference on a hard attribute refuses a link. Suggested from the column names; please confirm. You can set hard attributes per category later in Rules.</div>
          <div className="flex flex-wrap gap-2">
            {attrCands.map((c: string) => {
              const on = attrs.includes(c);
              return (
                <span key={c} className={clsx("flex items-center gap-2 rounded-lg border px-2 py-1 text-sm", on ? "border-save bg-white" : "border-line")}>
                  <label className="flex items-center gap-1">
                    <input type="checkbox" checked={on} onChange={() => setAttrs(on ? attrs.filter((a) => a !== c) : [...attrs, c])} />
                    {c}
                  </label>
                  {on && (
                    <label className="flex items-center gap-1 text-xs text-cost">
                      <input type="checkbox" checked={hard.includes(c)} onChange={() => setHard(hard.includes(c) ? hard.filter((a) => a !== c) : [...hard, c])} />
                      hard
                    </label>
                  )}
                </span>
              );
            })}
          </div>
        </div>
      )}
      <div className="overflow-auto rounded-xl border border-line">
        <table className="w-full text-xs">
          <caption className="px-3 py-2 text-left text-xs text-muted">Preview: first 5 rows</caption>
          <thead>
            <tr className="bg-soft">
              {upload.columns.map((c: string) => <th key={c} className="whitespace-nowrap px-3 py-2 text-left font-semibold">{c}{used.has(c) && <span className="ml-1 text-human">✓</span>}</th>)}
            </tr>
          </thead>
          <tbody>
            {upload.preview.map((r: any, i: number) => (
              <tr key={i} className="border-t border-line">
                {upload.columns.map((c: string) => <td key={c} className="whitespace-nowrap px-3 py-1.5">{r[c] ?? ""}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ErrorNote error={save.error} />
      <div><button type="button" className="btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>{save.isPending ? "Saving…" : "Save mapping"}</button></div>
    </div>
  );
}
