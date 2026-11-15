# BOMerang

Links every BOM part to the purchase lines that bought it, with evidence for every link, refuses look-alikes, explains every dollar of spend, and lets an analyst review, explore and simulate.

> We can't promise to match everything. We promise to show what we matched, why, and what we couldn't.

The app starts **empty**. There is no sample data anywhere in the running app. Every number comes from the files you upload.

## Setup

Requirements: Python 3.11+, Node 18+.

```bash
make install      # pip install -r api/requirements.txt, npm install (root + web)
make dev          # API on http://localhost:8000, web app on http://localhost:5173
```

Open http://localhost:5173.

Or with Docker: `docker compose up --build` (same ports).

### Environment variables (all optional, see `.env.example`)

| Variable | Default | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | unset | Turns on AI suggestions. Without it the AI rung is skipped and the header says "AI suggestions off". |
| `LLM_MODEL` | `claude-sonnet-5-5` | Model for the AI rung. |
| `AI_MAX_ITEMS` | `200` | Max items sent to the AI per run (highest spend first). Responses are cached, so reruns are identical and work offline. |
| `BOMERANG_DATA_DIR` | `./data` | SQLite DB, uploads and run results. Created empty. |
| `BOMERANG_EMBEDDINGS` | `0` | `1` blends a multilingual sentence-transformers model into candidate retrieval (install `sentence-transformers` first). |

## File formats

Upload CSV (any delimiter, any common encoding) or XLSX (each tab can be a different file type). Column names do not matter: every file goes through **column mapping** with suggestions from header names and sample values. Mappings are saved per project, so a re-upload with the same headers is one click.

Required:

* **BOM**: `parent_id`, `component_id`, `qty_per_parent`, optional `uom`, `description_as_written`, `revision`. Multi-level is fine.
* **Spend lines**: `description`, `qty`, `supplier_id` or `supplier_name`, `unit_price` or `amount` (the other is derived), plus optional `line_id`, `purchase_uom`, `currency`, `invoice_date` / `invoice_month`, `supplier_part_no`, `material_id_if_known`, `cost_center`, `po_number`, `supplier_country`.

Optional (each unlocks features; the readiness card says what is on and how to turn the rest on):

* **Material master**: `part_id`, `description`, `category`, `base_uom`, `standard_cost`, optional `currency`, plus any attribute columns (material, size, hardness…). You tick the attribute columns and mark the **hard** ones during mapping; refine per category in Rules.
* **Production volumes**: `product_id`, `period`, `units_built`.
* **Products**: `product_id`, `name`, `family`, `status` (`discontinued` products are excluded from demand).
* **Suppliers**, **Unit conversions** (`purchase_uom`, `base_uom`, `factor`), **FX rates** (`currency`, `rate_to_display_currency`, optional `period`), **Approved cross-references** (`supplier_id`/`supplier_name`, `supplier_part_no`, `part_id`, `approved_by`, `approved_on`).
* **Answer key** (proof screen only, never used by the matcher): `line_id`, `true_part_id` (or `NONE`), optional `class`.

## 2-minute tour

1. **Link.** Create a project, drop your files, confirm each mapping, read the readiness card (enter any missing FX rates), press **Link my data**. Watch the matching ladder fill with the real counts. The table below lists every supplier item with its status; click a row for its evidence.
2. **Review.** One card at a time, ordered by money at stake. Purchase vs suggested part, attribute chips (green agrees, amber missing, red differs), and four checks: what the invoice says, price gauge, quantity balance bars, timing. `A` approve, `R` not a BOM part, `U` undo, `J`/`K` next/previous. Approving saves a learned rule.
3. **Money flow.** The Sankey: total spend → 8 classes → products. Click any stream or number for its lines and the formula. The ledger shows "Difference to the spend cube: 0.00 ✓". Tab **BOM cost** shows each product's indented BOM with standard and actual-price cost.
4. **Parts.** Pick a part (or ⌘K): spend, products using it, supplier price gap, refused look-alikes, a suppliers → part → products flow, price per piece by supplier with spare/warranty greyed.
5. **Simulate.** Choose a baseline, drag the new price and the share of volume, edit planned units. Every product row shows its formula; the sensitivity line shows the whole range. Export the scenario.

**Rules** (header) holds synonyms, hard attributes per category, units, price band, thresholds, learned rules and shop-supply settings, with an impact preview before applying. **Proof** appears when an answer key is uploaded. **Export** downloads the Excel workbook and the link table CSV.

## Tests

```bash
make test          # pytest (engine + API flow, fixtures built in code) and Vitest
make e2e           # Playwright smoke test; needs `make dev` running and a Chromium
                   # (npx playwright install chromium, or PW_CHROMIUM_PATH=/path/to/chrome)
```

See `DECISIONS.md` for choices the spec left open and `HANDOFF.md` for status, limits and every default threshold.
