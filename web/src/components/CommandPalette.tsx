import { Command } from "cmdk";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useProject } from "../lib/hooks";
import { useUI } from "../lib/store";

const SCREENS = [
  ["/", "1 Link"],
  ["/review", "2 Review"],
  ["/money", "3 Money flow"],
  ["/parts", "4 Parts"],
  ["/simulate", "5 Simulate"],
  ["/proof", "Proof"],
  ["/export", "Export"],
];

export function CommandPalette() {
  const open = useUI((s) => s.paletteOpen);
  const setOpen = useUI((s) => s.setPalette);
  const setRules = useUI((s) => s.setRules);
  const setLinkSearch = useUI((s) => s.setLinkSearch);
  const nav = useNavigate();
  const { pid } = useProject();
  const [q, setQ] = useState("");
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!useUI.getState().paletteOpen);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [setOpen]);
  const s = useQuery({ queryKey: ["search", pid, q], enabled: !!pid && open, queryFn: () => api(`/projects/${pid}/search?q=${encodeURIComponent(q)}`) });
  const go = (to: string) => {
    setOpen(false);
    setQ("");
    nav(to);
  };
  return (
    <Command.Dialog open={open} onOpenChange={setOpen} label="Jump to a part, supplier, product or screen" shouldFilter={false}
      className="fixed left-1/2 top-[12vh] z-50 w-[min(640px,92vw)] -translate-x-1/2 overflow-hidden rounded-card border border-line bg-white shadow-2xl"
      overlayClassName="fixed inset-0 z-40 bg-ink/30">
      <Command.Input value={q} onValueChange={setQ} placeholder="Jump to a part, supplier, product or screen…" className="w-full border-b border-line px-5 py-4 text-base outline-none" />
      <Command.List className="max-h-[60vh] overflow-auto p-2">
        <Command.Empty className="px-4 py-6 text-sm text-muted">Nothing found.</Command.Empty>
        <Command.Group heading="Screens" className="px-2 text-xs text-muted">
          {SCREENS.filter(([, l]) => l.toLowerCase().includes(q.toLowerCase())).map(([to, l]) => (
            <Item key={to} onSelect={() => go(to)}>{l}</Item>
          ))}
          {"rules".includes(q.toLowerCase()) && <Item onSelect={() => { setOpen(false); setRules(true); }}>Rules</Item>}
        </Command.Group>
        {s.data?.parts?.length ? (
          <Command.Group heading="Parts" className="px-2 text-xs text-muted">
            {s.data.parts.slice(0, 12).map((p: any) => (
              <Item key={p.part_id} onSelect={() => go(`/parts/${encodeURIComponent(p.part_id)}`)}>
                <span className="font-semibold">{p.part_id}</span> <span className="text-muted">{p.description}</span>
              </Item>
            ))}
          </Command.Group>
        ) : null}
        {s.data?.suppliers?.length ? (
          <Command.Group heading="Suppliers" className="px-2 text-xs text-muted">
            {s.data.suppliers.slice(0, 8).map((p: any) => (
              <Item key={p.supplier_name} onSelect={() => { setLinkSearch(p.supplier_name); go("/?links=1"); }}>{p.supplier_name}</Item>
            ))}
          </Command.Group>
        ) : null}
        {s.data?.products?.length ? (
          <Command.Group heading="Products" className="px-2 text-xs text-muted">
            {s.data.products.slice(0, 8).map((p: any) => (
              <Item key={p.product_id} onSelect={() => go(`/money?tab=bom&product=${encodeURIComponent(p.product_id)}`)}>
                <span className="font-semibold">{p.product_id}</span> <span className="text-muted">{p.name}</span>
              </Item>
            ))}
          </Command.Group>
        ) : null}
      </Command.List>
    </Command.Dialog>
  );
}

function Item({ children, onSelect }: { children: React.ReactNode; onSelect: () => void }) {
  return (
    <Command.Item onSelect={onSelect} className="cursor-pointer rounded-lg px-3 py-2.5 text-sm text-ink aria-selected:bg-soft">
      {children}
    </Command.Item>
  );
}
