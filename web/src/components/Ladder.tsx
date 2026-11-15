import { clsx } from "clsx";
import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";
import { num } from "../lib/format";

type Rung = { n: number; label: string; hint?: string; count: number; tone: "rule" | "ai" | "evidence" | "human"; suffix?: string };

const TONE = {
  rule: ["bg-rule-bg text-[#374151]", "#6B7280", "text-ink"],
  ai: ["bg-ai-bg text-ai", "#6D28D9", "text-ai"],
  evidence: ["bg-save-bg text-navy", "#1E3A8A", "text-navy"],
  human: ["bg-human-bg text-human", "#0F766E", "text-human"],
} as const;

export function Ladder({ ladder, aiOn, animate, onDone }: { ladder: Record<string, number>; aiOn: boolean; animate: boolean; onDone?: () => void }) {
  const reduce = useReducedMotion();
  const rungs: Rung[] = [
    { n: 1, label: "Exact part IDs", count: ladder.exact, tone: "rule" },
    { n: 2, label: "Cross-references", hint: "approved and learned", count: ladder.xref, tone: "rule" },
    { n: 3, label: "Spec rules", hint: "material, size, units, translations", count: ladder.spec, tone: "rule" },
    { n: 4, label: "AI shortlist", hint: aiOn ? "suggests, never decides" : "off: no API key", count: ladder.ai, tone: "ai", suffix: "suggested" },
    { n: 5, label: "Independent checks", hint: "quantities add up, price plausible", count: ladder.evidence, tone: "evidence", suffix: "resolved" },
    { n: 6, label: "Your review", count: ladder.review, tone: "human", suffix: ladder.human ? `waiting · ${num(ladder.human)} decided` : "waiting" },
  ];
  const total = Math.max(1, ladder.items);
  const [step, setStep] = useState(animate && !reduce ? 0 : rungs.length);
  useEffect(() => {
    if (step >= rungs.length) {
      onDone?.();
      return;
    }
    const t = setTimeout(() => setStep((s) => s + 1), 420);
    return () => clearTimeout(t);
  }, [step]); // eslint-disable-line
  return (
    <div className="flex flex-col gap-4">
      {rungs.map((r, i) => {
        const lit = i < step;
        const [badge, bar, txt] = TONE[r.tone];
        return (
          <div key={r.n} className="grid grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3.5">
            <div className={clsx("flex h-9 w-9 items-center justify-center rounded-[10px] font-bold transition-opacity", badge, !lit && "opacity-40")}>{r.n}</div>
            <div className="flex flex-col gap-1.5">
              <div className="font-semibold">
                {r.label} {r.hint && <span className="text-[13px] font-normal text-muted">· {r.hint}</span>}
              </div>
              <div className="h-2.5 rounded-full bg-soft">
                <motion.div className="h-2.5 rounded-full" style={{ background: bar }} initial={false} animate={{ width: lit ? `${Math.max(r.count ? 1.5 : 0, (r.count / total) * 100)}%` : "0%" }} transition={{ duration: reduce ? 0 : 0.25 }} />
              </div>
            </div>
            <div className={clsx("min-w-[72px] text-right font-display text-xl font-bold tabnum", txt)}>
              {lit ? <Counter to={r.count} /> : 0}
              {r.suffix && <span className="ml-1 text-xs font-medium text-muted">{r.suffix}</span>}
            </div>
          </div>
        );
      })}
      {step < rungs.length && (
        <button type="button" className="self-end text-[13px] font-semibold text-save" onClick={() => setStep(rungs.length)}>
          Skip animation
        </button>
      )}
    </div>
  );
}

function Counter({ to }: { to: number }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    let raf = 0;
    const t0 = performance.now();
    const f = (t: number) => {
      const k = Math.min(1, (t - t0) / 250);
      setV(Math.round(to * k));
      if (k < 1) raf = requestAnimationFrame(f);
    };
    raf = requestAnimationFrame(f);
    return () => cancelAnimationFrame(raf);
  }, [to]);
  return <>{num(v)}</>;
}
