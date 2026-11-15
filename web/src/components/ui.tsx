import { clsx } from "clsx";
import type { ReactNode } from "react";

export function Card({ className, children, ...rest }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLElement>) {
  return (
    <section className={clsx("card p-6", className)} {...rest}>
      {children}
    </section>
  );
}

export function H1({ children, eyebrow }: { children: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      {eyebrow && <div className="label">{eyebrow}</div>}
      <h1 className="m-0 font-display text-[32px] leading-[1.15] tracking-[-0.02em] md:text-[40px]">{children}</h1>
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-start gap-3 border-dashed p-10">
      <h2 className="m-0 text-xl font-semibold">{title}</h2>
      {children && <div className="max-w-2xl text-[15px] leading-relaxed text-muted">{children}</div>}
      {action}
    </div>
  );
}

export function NextBar({ text, children }: { text: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-card bg-ink px-6 py-5 text-white">
      <div className="text-base">{text}</div>
      {children}
    </div>
  );
}

const ICONS = {
  check: <path d="M5 12l5 5L20 7" />,
  warn: (
    <>
      <path d="M12 8v5" />
      <path d="M12 17h.01" />
      <circle cx="12" cy="12" r="9" />
    </>
  ),
  x: (
    <>
      <path d="M6 6l12 12" />
      <path d="M18 6L6 18" />
    </>
  ),
  ban: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M5.6 5.6l12.8 12.8" />
    </>
  ),
  person: (
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" />
    </>
  ),
  spark: <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />,
  rule: (
    <>
      <path d="M4 6h16" />
      <path d="M4 12h10" />
      <path d="M4 18h6" />
    </>
  ),
  minus: <path d="M6 12h12" />,
};

export function Icon({ name, size = 16, className }: { name: keyof typeof ICONS; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={clsx("flex-none", className)}>
      {ICONS[name]}
    </svg>
  );
}

export function StatusChip({ status, label }: { status: string; label?: string }) {
  const map: Record<string, [string, keyof typeof ICONS, string]> = {
    auto: ["bg-rule-bg text-ink", "rule", "Auto-linked"],
    evidence: ["bg-save-bg text-navy", "check", "Resolved by evidence"],
    human: ["bg-human-bg text-human", "person", "Linked by you"],
    review: ["bg-warn-bg text-warn", "warn", "Needs review"],
    refused: ["bg-cost-bg text-cost", "ban", "Refused"],
    nomatch: ["bg-soft text-muted", "minus", "No match"],
    notbom: ["bg-human-bg text-human", "person", "Not a BOM part"],
  };
  const [cls, icon, l] = map[status] ?? ["bg-soft text-muted", "minus", status];
  return (
    <span className={clsx("chip whitespace-nowrap", cls)}>
      <Icon name={icon} size={14} />
      {label ?? l}
    </span>
  );
}

export function AIChip({ children = "AI" }: { children?: ReactNode }) {
  return (
    <span className="chip bg-ai-bg text-ai">
      <Icon name="spark" size={14} />
      {children}
    </span>
  );
}

export function Spinner() {
  return <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" aria-hidden />;
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div role="alert" className="rounded-xl border border-cost-line bg-cost-bg px-4 py-3 text-sm text-cost">
      {(error as Error).message || String(error)}
    </div>
  );
}
