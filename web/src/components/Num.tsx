import { clsx } from "clsx";
import { useEffect, useRef, useState } from "react";
import type { Receipt } from "../lib/api";
import { money } from "../lib/format";
import { useUI } from "../lib/store";

/** A number that opens its receipts. Every number on Money flow, Parts and Simulate goes through this. */
export function Num({ cents, currency, receipt, className, children, sign }: { cents?: number | null; currency?: string; receipt: Receipt; className?: string; children?: React.ReactNode; sign?: boolean }) {
  const open = useUI((s) => s.openReceipt);
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        open(receipt);
      }}
      className={clsx("tabnum cursor-pointer rounded underline decoration-dotted decoration-1 underline-offset-4 hover:decoration-solid", className)}
      title="Show the lines behind this number"
      aria-label={`${children ?? money(cents ?? 0, currency)}: show receipts`}
    >
      {children ?? money(cents ?? 0, currency, { sign })}
    </button>
  );
}

/** Counts smoothly to a new value (150-250 ms), respecting reduced motion. */
export function useCountTo(target: number | null, ms = 220) {
  const [v, setV] = useState(target);
  const from = useRef(target);
  useEffect(() => {
    if (target === null) {
      setV(null);
      return;
    }
    const reduce = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const start = from.current ?? target;
    if (reduce || start === target) {
      setV(target);
      from.current = target;
      return;
    }
    let raf = 0;
    const t0 = performance.now();
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / ms);
      const e = 1 - Math.pow(1 - k, 3);
      setV(start + (target - start) * e);
      if (k < 1) raf = requestAnimationFrame(step);
      else from.current = target;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return v;
}
