import { Link } from "react-router-dom";
import { useProject, useSummary } from "../lib/hooks";
import { EmptyState } from "./ui";

/** Shows an empty state that teaches until there is a project and a finished run. */
export function useGate() {
  const { pid, project, loading } = useProject();
  const s = useSummary(pid);
  const ready = !!pid && !!s.data?.has_run;
  let gate: React.ReactNode = null;
  if (loading || (pid && s.isLoading)) gate = <div className="text-muted">Loading…</div>;
  else if (!pid)
    gate = (
      <EmptyState title="No project yet" action={<Link to="/" className="btn-primary no-underline">Start on step 1 →</Link>}>
        Create a project and upload a BOM and a spend file to start. Only these two are required.
      </EmptyState>
    );
  else if (!ready)
    gate = (
      <EmptyState title="Nothing linked yet" action={<Link to="/" className="btn-primary no-underline">Go to 1 Link →</Link>}>
        Upload a BOM and a spend file and press “Link my data”. Every number on this screen will come from your files.
      </EmptyState>
    );
  return { pid, project, ready, gate, summary: s.data?.run?.summary, run: s.data?.run };
}
