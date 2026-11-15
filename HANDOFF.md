# Handoff

## Run it

```bash
make install && make dev      # http://localhost:5173 (API on :8000)
make test                     # pytest + Vitest
make e2e                      # Playwright smoke (with make dev running)
```

The app starts with no projects and no data. Upload a BOM and a spend file to begin.

## Built

* Upload (CSV/XLSX, multi-tab), column mapping with suggestions and 5-row preview, saved mappings, data readiness with "how to turn it on", FX entry for missing rates.
* Engine: normalization (units, currency, synonyms EN/DE, spec regex), multi-level BOM explosion, supplier items, ladder rungs 1–3 with hard-attribute refusals, AI rung (guarded, cached, optional), price gate, per-item quantity balance, unit inference, timing check, confidence and money at stake, learning from decisions, allocation and the 8-class ledger in integer cents, BOM cost, part explorer, simulator, readiness, proof (text-only vs rules-only vs full).
* Screens: Link (with animated ladder and links table with evidence drawer), Review (keyboard, evidence panel, part picker, unit factor, undo, refusal override with written reason), Money flow (Sankey, ledger with difference line, zoom bar, unexplained items, BOM cost tab), Parts, Simulate (baseline picker, sliders, editable volumes, formulas, sensitivity, pin/compare, export), Proof, Rules drawer (all tabs, impact preview, versioning, loosening needs a reason), Export (Excel workbook with all listed sheets + links CSV).
* Receipts drawer on every number in Money flow, Parts and Simulate; command palette (⌘K / Ctrl+K); table view on every chart.
* Stretch built: timing check; price over time on the part page; scenario pin/compare.

## Not built (stretch)

Joint quantity balance (MILP), savings list, tariff / price-shock test, analyst Q&A chat, duplicate-part finder, rule rollback, multi-component / supplier-switch simulator, one-page PDF, hover-linking between Sankey and BOM table, story mode.

## Known limits

* No authentication; review decisions are recorded as "analyst" (rule changes take a "who" field).
* Rule changes and removing a learned rule re-run matching in the background; the screens refresh a few seconds later; on very large files reload once the run finishes.
* Without production volumes, allocation is off and linked BOM spend is shown as one labelled row instead of being split.
* Fractional inch dimensions (`1/2"`) are not parsed; decimals are.
* AI calls are capped at `AI_MAX_ITEMS` per run (highest spend first); the rest stay with the deterministic result.
* The Playwright smoke test needs a Chromium; set `PW_CHROMIUM_PATH` if `npx playwright install` is not possible.

## Default thresholds (all editable in **Rules**, stored per project and versioned; defaults in `api/engine/rules.py`)

| Setting | Default | Rules tab | Effect |
|---|---|---|---|
| Price band low / high | 0.6× / 1.6× | Price band | Spec-rule link outside the band goes to review |
| Auto-link minimum text similarity | 0.30 | Thresholds | A unique all-hard-attributes-agree candidate must reach this to auto-link |
| Quantity balance margin | 0.25 | Thresholds | Best option must beat the next by this to resolve an ambiguous item |
| Minimum similarity for a candidate | 0.20 | Thresholds | Below this a part is not considered |
| Candidates compared per item | 12 | Thresholds | Top-k from text retrieval |
| Money-at-stake floor (review) | 0.3 | Thresholds | Stake = spend × max(1 − confidence, floor) |
| Unit inference factors | 1, 6, 10, 12, 24, 50, 100, 144, 250, 500, 1000 | code: `UNIT_INFERENCE_FACTORS` in `api/engine/rules.py` | Factors tested for unknown units |
| Service keywords | spare, service, warranty, repair, replacement, aftermarket, rma | Service and shop supplies | Cost center or description → Service and warranty |
| Shop-supply cost centers | maintenance, mro, facility, facilities, workshop, tooling, cleaning | Service and shop supplies | → Shop supplies |
| Shop-supply categories / keywords | empty | Service and shop supplies | → Shop supplies |
| Hard attributes | none until confirmed at mapping (suggested from column names: material / size / dimension…) | Hard attributes per category | Difference → refusal |
| Synonyms | ~100 EN/DE engineering terms | Synonyms and translations | Applied before matching |
| AI guardrail: number tolerance | 2% (mm/inch aware) | code: `api/llm/guardrails.py` | AI-read numbers must appear in the source text |
| Timing chunks / cost | 4 chunks, 0.1 × (1 − fit) | code: `api/engine/checks.py`, `pipeline.py` | Timing is a small cost in the balance |
| Sankey minimum stream width | 3% of total | code: `web/src/components/Sankey.tsx` | Visual only, labelled |
