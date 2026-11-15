import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Project, type Run } from "./api";
import { useUI } from "./store";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: () => api<{ ai_on: boolean; model: string | null }>("/health"), staleTime: 60_000 });
}

export function useProjects() {
  return useQuery({ queryKey: ["projects"], queryFn: () => api<Project[]>("/projects") });
}

export function useProject() {
  const pid = useUI((s) => s.projectId);
  const projects = useProjects();
  const project = projects.data?.find((p) => p.id === pid) ?? null;
  return { pid: project ? pid : null, project, loading: projects.isLoading };
}

export function useSummary(pid: number | null) {
  return useQuery({
    queryKey: ["summary", pid],
    enabled: !!pid,
    queryFn: () => api<{ has_run: boolean; run?: Run }>(`/projects/${pid}/summary`),
  });
}

export function usePQ<T = any>(pid: number | null, path: string, key: unknown[], enabled = true) {
  return useQuery({ queryKey: [...key, pid], enabled: !!pid && enabled, queryFn: () => api<T>(`/projects/${pid}${path}`), retry: (n, e: any) => e?.status !== 409 && n < 2 });
}

export function useInvalidateRun() {
  const qc = useQueryClient();
  return () => {
    for (const k of ["summary", "review", "moneyflow", "links", "parts", "part", "sim", "readiness", "learned", "proof", "rules", "item", "search", "projects"]) {
      qc.invalidateQueries({ queryKey: [k] });
    }
  };
}
