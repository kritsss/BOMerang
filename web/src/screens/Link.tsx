import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link as RLink } from "react-router-dom";
import { Ladder } from "../components/Ladder";
import { LinksTable } from "../components/LinksTable";
import { ReadinessCard } from "../components/Readiness";
import { Dropzone, FileList } from "../components/Upload";
import { Card, EmptyState, ErrorNote, H1, Icon, NextBar, Spinner } from "../components/ui";
import { api, type Run } from "../lib/api";
import { num, plural } from "../lib/format";
import { useHealth, useInvalidateRun, useProject, useProjects, useSummary } from "../lib/hooks";
import { useUI } from "../lib/store";

export default function Link() {
  const { pid, project, loading } = useProject();
  if (loading) return <div className="text-muted">Loading…</div>;
  if (!pid || !project) return <NewProject />;
  return <LinkScreen pid={pid} />;
}

function NewProject() {
  const qc = useQueryClient();
  const setProject = useUI((s) => s.setProject);
  const projects = useProjects();
  const [name, setName] = useState("");
  const [cur, setCur] = useState("USD");
  const m = useMutation({
    mutationFn: () => api("/projects", { json: { name, display_currency: cur } }),
    onSuccess: (p: any) => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      setProject(p.id);
    },
  });
  return (
    <>
      <H1 eyebrow="Step 1 of 5">Link your BOMs to your spend.</H1>
      <p className="m-0 max-w-3xl text-[17px] leading-relaxed text-muted">
        We can't promise to match everything. We promise to show what we matched, why, and what we couldn't.
      </p>
      <EmptyState title={projects.data?.length ? "Start a new project" : "No projects yet"}>
        A project holds your uploaded files, rules and review decisions. Upload a BOM and a spend file to start. Only these two are required.
      </EmptyState>
      <Card className="flex max-w-xl flex-col gap-4">
        <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); if (name.trim()) m.mutate(); }}>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Project name
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Pumps H1" required />
          </label>
          <label className="flex flex-col gap-1 text-sm font-semibold">
            Display currency (3-letter code)
            <input className="input w-32 uppercase" value={cur} onChange={(e) => setCur(e.target.value.toUpperCase().slice(0, 3))} />
          </label>
          <ErrorNote error={m.error} />
          <div><button className="btn-primary" type="submit" disabled={m.isPending || !name.trim()}>Create project</button></div>
        </form>
      </Card>
    </>
  );
}

function LinkScreen({ pid }: { pid: number }) {
  const rd = useQuery({ queryKey: ["readiness", pid], queryFn: () => api(`/projects/${pid}/readiness`) });
  const summary = useSummary(pid);
  const health = useHealth();
  const invalidate = useInvalidateRun();
  const [runId, setRunId] = useState<number | null>(null);
  const [animate, setAnimate] = useState(false);
  const runQ = useQuery({
    queryKey: ["run", pid, runId],
    enabled: !!runId,
    queryFn: () => api<Run>(`/projects/${pid}/runs/${runId}`),
    refetchInterval: (q) => (q.state.data && ["done", "failed"].includes(q.state.data.status) ? false : 400),
  });
  const start = useMutation({
    mutationFn: () => api<Run>(`/projects/${pid}/runs`, { method: "POST" }),
    onSuccess: (r) => setRunId(r.id),
  });
  useEffect(() => {
    if (runQ.data?.status === "done") {
      setAnimate(true);
      invalidate();
      setRunId(null);
    }
  }, [runQ.data?.status]); // eslint-disable-line
  const last = summary.data?.run;
  const s = last?.summary;
  const running = start.isPending || (runId !== null && runQ.data?.status !== "failed");
  const files = rd.data?.files?.filter((f: any) => f.status !== "replaced") ?? [];
  const refusedQ = useQuery({ queryKey: ["review", pid], enabled: !!s, queryFn: () => api(`/projects/${pid}/review`) });
  const firstRefused = refusedQ.data?.refused?.[0];

  return (
    <>
      <div className="flex flex-col gap-2">
        <H1 eyebrow="Step 1 of 5">
          {s ? (
            <>
              {num(s.auto)} of {plural(s.items, "spend item")} linked automatically.
              <br />
              <span className="text-muted">
                {num(s.review)} need your eyes. {num(s.refused)} {s.refused === 1 ? "was" : "were"} refused.
              </span>
            </>
          ) : (
            "Upload, map, and watch it link."
          )}
        </H1>
      </div>

      <Dropzone pid={pid} />
      <FileList pid={pid} />
      <div className="flex flex-wrap items-start gap-6">
        <div className="min-w-[300px] flex-[1_1_340px]">{rd.data && <ReadinessCard pid={pid} rd={rd.data} />}</div>
        <section className="card flex min-w-0 flex-[999_1_560px] flex-col gap-4 p-6" aria-label="Matching ladder">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="m-0 text-base font-semibold">The matching ladder</h2>
            <span className="text-[13px] text-muted">Each step only handles what the step before could not</span>
          </div>
          {running ? (
            <div className="flex flex-col gap-3" aria-live="polite">
              <div className="text-sm font-semibold">{runQ.data?.message || "Starting"}…</div>
              <div className="h-2.5 rounded-full bg-soft">
                <div className="h-2.5 rounded-full bg-ink transition-[width] duration-200" style={{ width: `${Math.round((runQ.data?.progress ?? 0.02) * 100)}%` }} />
              </div>
            </div>
          ) : s ? (
            <Ladder key={last?.id} ladder={s.ladder} aiOn={!!health.data?.ai_on} animate={animate} onDone={() => setAnimate(false)} />
          ) : (
            <div className="text-sm text-muted">
              {files.length ? "Map every file, check the readiness card, then link." : "Upload a BOM and a spend file to start. Only these two are required."}
            </div>
          )}
          {runQ.data?.status === "failed" && <ErrorNote error={new Error(runQ.data.error)} />}
          <ErrorNote error={start.error} />
          {s && firstRefused && !running && (
            <div className="flex items-start gap-3 rounded-xl border border-cost-line bg-cost-bg px-4 py-3.5">
              <span className="mt-0.5 text-cost"><Icon name="ban" size={20} /></span>
              <div className="text-sm leading-relaxed">
                <strong>Refused {plural(s.refused, "look-alike")}.</strong> “{firstRefused.description}”: {firstRefused.reason} Different hard attribute means a different part, so it is not linked.
              </div>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className="btn-primary" disabled={!rd.data?.can_run || running} onClick={() => start.mutate()}>
              {running ? <><Spinner /> Linking…</> : s ? "Link again with everything learned" : "Link my data"}
            </button>
            {!rd.data?.can_run && rd.data?.blocking?.length > 0 && <span className="text-sm text-muted">{rd.data.blocking.join(" ")}</span>}
          </div>
        </section>
      </div>

      {s && !running && (
        <>
          <NextBar text={s.review > 0 ? `${plural(s.review, "link")} ${s.review === 1 ? "needs" : "need"} a quick decision before the numbers are final.` : "Nothing is waiting for review. See where the money went."}>
            {s.review > 0 ? (
              <RLink to="/review" className="rounded-[10px] bg-white px-5 py-3 text-[15px] font-semibold text-ink no-underline">Review {plural(s.review, "link")} →</RLink>
            ) : (
              <RLink to="/money" className="rounded-[10px] bg-white px-5 py-3 text-[15px] font-semibold text-ink no-underline">Money flow →</RLink>
            )}
          </NextBar>
          <LinksTable pid={pid} currency={s.display_currency} />
        </>
      )}
    </>
  );
}
