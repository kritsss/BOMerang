import { useMutation, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import { NavLink } from "react-router-dom";
import { api } from "../lib/api";
import { useHealth, useProject, useProjects, useSummary } from "../lib/hooks";
import { useUI } from "../lib/store";
import { Icon } from "./ui";

const STEPS = [
  ["/", "1 Link"],
  ["/review", "2 Review"],
  ["/money", "3 Money flow"],
  ["/parts", "4 Parts"],
  ["/simulate", "5 Simulate"],
] as const;

const CURRENCIES = ["USD", "EUR", "GBP", "CHF", "JPY", "CNY", "INR", "CAD", "AUD", "SEK", "PLN", "CZK", "MXN", "BRL", "KRW", "SGD"];

export function Header() {
  const health = useHealth();
  const projects = useProjects();
  const { pid, project } = useProject();
  const setProject = useUI((s) => s.setProject);
  const setPalette = useUI((s) => s.setPalette);
  const setRules = useUI((s) => s.setRules);
  const summary = useSummary(pid);
  const qc = useQueryClient();
  const hasRun = !!summary.data?.has_run;
  const cur = useMutation({
    mutationFn: (c: string) => api(`/projects/${pid}`, { method: "PATCH", json: { display_currency: c } }),
    onSuccess: () => qc.invalidateQueries(),
  });
  const ranCur = summary.data?.run?.summary?.display_currency;
  return (
    <header className="sticky top-0 z-30 flex flex-wrap items-center gap-x-6 gap-y-3 bg-ink px-4 py-3 text-white md:px-8">
      <NavLink to="/" className="font-display text-xl font-bold tracking-[-0.01em] text-white no-underline">
        BOMerang
      </NavLink>
      <nav aria-label="Steps" className="flex flex-1 flex-wrap items-center gap-0.5">
        {STEPS.map(([to, l], i) => (
          <NavLink key={to} to={to} end={to === "/"}
            className={({ isActive }) => clsx("whitespace-nowrap rounded-full px-3 py-1.5 text-sm no-underline", isActive ? "bg-white font-semibold text-ink" : "text-[#D1D5DB] hover:text-white", !hasRun && i > 0 && "opacity-70")}>
            {l}
          </NavLink>
        ))}
        <span className="mx-1 h-5 w-px bg-[#374151]" aria-hidden />
        {[["/export", "Export"]].map(([to, l]) => (
          <NavLink key={to} to={to} className={({ isActive }) => clsx("whitespace-nowrap rounded-full px-3 py-1.5 text-sm no-underline", isActive ? "bg-white font-semibold text-ink" : "text-[#D1D5DB] hover:text-white")}>
            {l}
          </NavLink>
        ))}
      </nav>
      <div className="flex flex-wrap items-center gap-2">
        <span className={clsx("chip", health.data?.ai_on ? "bg-ai text-white" : "bg-[#2a2f3a] text-[#D1D5DB]")} title={health.data?.model ?? "Set ANTHROPIC_API_KEY to turn AI suggestions on"}>
          <Icon name="spark" size={14} />
          {health.data?.ai_on ? "AI suggestions on" : "AI suggestions off"}
        </span>
        {project && (
          <label className="flex items-center gap-1 text-sm text-[#D1D5DB]">
            <span className="sr-only">Display currency</span>
            <select value={project.display_currency} onChange={(e) => cur.mutate(e.target.value)} className="rounded-lg border border-[#4B5563] bg-ink px-2 py-1.5 text-white" aria-label="Display currency">
              {Array.from(new Set([project.display_currency, ...CURRENCIES])).map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
            {hasRun && ranCur && ranCur !== project.display_currency && <span className="text-xs text-[#FDBA74]">re-run to apply</span>}
          </label>
        )}
        <label className="flex items-center text-sm">
          <span className="sr-only">Project</span>
          <select aria-label="Project" value={pid ?? ""} onChange={(e) => setProject(e.target.value === "new" ? null : Number(e.target.value) || null)}
            className="max-w-[150px] rounded-lg border border-[#4B5563] bg-ink px-2 py-1.5 text-white">
            {!pid && <option value="">No project</option>}
            {projects.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
            <option value="new">+ New project</option>
          </select>
        </label>
        <button type="button" onClick={() => setRules(true)} className="rounded-lg border border-[#4B5563] px-3 py-1.5 text-sm font-medium hover:bg-[#2a2f3a]">
          Rules
        </button>
        <button type="button" onClick={() => setPalette(true)} className="rounded-lg border border-[#4B5563] px-3 py-1.5 text-sm text-[#D1D5DB] hover:bg-[#2a2f3a]" aria-label="Open command palette">
          ⌘K
        </button>
      </div>
    </header>
  );
}
