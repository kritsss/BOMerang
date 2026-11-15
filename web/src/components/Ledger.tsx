import { clsx } from "clsx";
import { CLASS_COLOR, GROUP_LABEL } from "../lib/colors";
import { money } from "../lib/format";
import type { Summary } from "../lib/api";
import { Num } from "./Num";
import { Icon } from "./ui";

export function Ledger({ ledger, currency }: { ledger: Summary["ledger"]; currency: string }) {
  const groups = ["explained", "waiting", "not_explained"];
  const diff = ledger.difference_cents;
  return (
    <section className="card flex flex-col gap-3 p-6" aria-label="Ledger">
      <h2 className="m-0 text-base font-semibold">The ledger · every line counted once</h2>
      <table className="w-full text-sm">
        <tbody>
          {groups.map((g) => {
            const rows = ledger.classes.filter((c) => c.group === g);
            if (!rows.length) return null;
            return [
              ...rows.map((c) => (
                <tr key={c.key} className="border-b border-line">
                  <td className="py-2 pr-3">
                    <span className="mr-2 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: CLASS_COLOR[c.key] }} aria-hidden />
                    {c.label}
                  </td>
                  <td className="py-2 text-right"><Num cents={c.cents} currency={currency} receipt={{ kind: "class", key: c.key, title: c.label }} /></td>
                </tr>
              )),
              <tr key={g} className="border-b border-line bg-soft font-semibold">
                <td className="py-2 pl-2 pr-3">{GROUP_LABEL[g]}</td>
                <td className="py-2 pr-1 text-right"><Num cents={ledger.groups[g] ?? 0} currency={currency} receipt={{ kind: "group", key: g, title: GROUP_LABEL[g] }} /></td>
              </tr>,
            ];
          })}
          <tr className="border-b-[3px] border-double border-ink font-display text-base font-bold">
            <td className="pb-2 pt-3">Total</td>
            <td className="pb-2 pt-3 text-right"><Num cents={ledger.ledger_cents} currency={currency} receipt={{ kind: "total", title: "All spend" }} /></td>
          </tr>
          <tr>
            <td className="pt-3 text-muted">Spend cube total</td>
            <td className="pt-3 text-right tabnum text-muted">{money(ledger.total_cents, currency)}</td>
          </tr>
          <tr>
            <td className={clsx("pt-1 font-semibold", diff !== 0 ? "text-[#B91C1C]" : "text-human")}>Difference to the spend cube</td>
            <td className={clsx("pt-1 text-right font-semibold tabnum", diff !== 0 ? "text-[#B91C1C]" : "text-human")}>
              <span className="inline-flex items-center gap-1">{money(diff, currency, { decimals: 2 })} <Icon name={diff === 0 ? "check" : "x"} size={14} /></span>
              {diff !== 0 && <div className="text-xs">This is a bug. Please report it.</div>}
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}
