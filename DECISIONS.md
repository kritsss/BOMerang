# Decisions

Choices where the build prompt was silent, or where the stack had to bend.

## Stack

* **shadcn/ui**: its CLI pulls components from a remote registry. I used the same Radix primitives it wraps (`@radix-ui/react-dialog`, `-tabs`, `-slider`, `-select`, `-tooltip`) with Tailwind classes written in the shadcn style, so components are accessible and can be swapped for generated shadcn files later.
* **Router**: React Router v6.
* **Fonts**: `@fontsource/inter` and `@fontsource/space-grotesk` (bundled, work offline) instead of Google Fonts.
* **Text similarity**: TF-IDF on character 2–4-grams (scikit-learn) with sparse matrix products for top-k retrieval, which handles German/English fragments and part-number noise well and keeps 50k lines fast. rapidfuzz is used for type-word matching and column-mapping suggestions. The multilingual sentence-transformers model is optional (`BOMERANG_EMBEDDINGS=1`) because it pulls in PyTorch; when on, it is blended 50/50 with TF-IDF (cosine in numpy, no vector DB).
* **DuckDB** is installed but the engine stayed in vectorized pandas: the BOM explosion is a level-by-level merge (same result as a recursive CTE, simpler to unit test). Performance target met: 50,000 lines, 2,500 parts, 4,800 BOM lines in about 30 s without the LLM on a 2-core container.
* **Run storage**: run results are pickled DataFrames under `BOMERANG_DATA_DIR/projects/<id>/runs/`; SQLite holds projects, uploads metadata, saved mappings, rule versions, learned rules, decisions, runs and the LLM cache.
* **Joint MILP balance (stretch)** not built; SciPy is a dependency for when it is.

## Matching

* **Attribute kinds are learned from the master**: a column whose values mostly parse as `a x b` is a dimension; mostly single numbers is numeric; otherwise text. Nothing is hard-coded per dataset.
* **Text attributes compare as word sets** after the synonym table. They *differ* only when each side has a word the other lacks (`{c45, carbon, steel}` vs `{stainless, 304}`); if one side is a subset (`stainless` vs `stainless 304`) they agree. A synonym group whose name matches a master column (e.g. group `material`, column `material`) adds its words to that attribute's vocabulary, so an invoice grade that is not in your master can still be recognised as different.
* **Numeric attributes**: an invoice "states" a value if one of its numbers equals a value that column takes somewhere in the master. If it states another known value but not this part's, it differs.
* **Dimensions** compare order-independently (8x120 = 120x8), and mm/inch-equivalent.
* Dimensions are pulled out of the text *before* synonyms, so `316 x 3` is a size, not stainless 316.
* **A hard attribute only applies to categories where the master fills it** (a shaft category with no hardness values is not blocked by "hardness missing"). Hard attributes are suggested from column names at mapping time and confirmed by the user there; per-category overrides live in Rules.
* **Part type guard**: a spec-rule link also needs the invoice to share a non-attribute word with the part description (e.g. "shaft"/"Welle"), else it is only a candidate. Prevents "stainless 8x120 screw" auto-linking to "stainless 8x120 shaft".
* **No hard attributes defined → spec rules cannot confirm**: items stay candidates and need the quantity balance or a person. Text similarity alone never auto-links.
* **Refused item**: best text match differs on a hard attribute and no non-refused candidate is at least 60% as similar.
* **Exact ID and cross-reference links are not price-gated** (the prompt says so for cross-references; exact IDs are the buyer's own field). Both still go to review if the purchase unit is unknown.
* **Balance winner "none"** (the item looks unnecessary) is never applied automatically: it goes to review with that suggestion.
* **AI proposals** become the first option of an ambiguous item after a rules re-check. They can be resolved by the quantity balance (independent evidence), otherwise they go to review. AI-read attributes only fill attributes the rules could not read and are tagged "AI-read".
* **Confidence**: exact 0.99, approved cross-reference 0.98, learned 0.97, your decision 1.0; spec rules 0.85 (+0.05 price pass, +0.05 quantities consistent); balance 0.70 + 0.2 × min(margin, 1); review 0.3 + 0.3 × similarity (max 0.6).

## Money

* All money is converted to the display currency and held in **integer cents**. Allocation splits use largest-remainder rounding, so the 8 classes add up to the spend cube exactly; the difference line is computed independently from the raw lines.
* **Class priority per line**: service/warranty → shop supplies → (by item status) pending review / refused / no match → linked: not in any active BOM, or allocated + bought beyond need.
* **No volumes**: allocation is impossible, so linked BOM spend is shown as a clearly labelled ninth row "Linked to a BOM part (no volumes to allocate)" and the Money flow screen shows the empty state for allocation. With volumes, exactly the 8 classes are used.
* **Missing FX rates block the run** (readiness asks for them) rather than dropping lines.
* Standard cost is assumed to be in the display currency unless the master maps a `currency` column.
* A credit note (negative line) is allocated proportionally like any other line; totals stay exact.

## Units

* Built-ins: EA/PC/ST…, C = 100, M = 1000 for count units (metre for length units), DZ = 12, mm/cm/m/in/ft, g/kg/lb/oz/t, ml/l. PK, BX and anything else only if defined.
* Learned unit factors from review are scoped to that supplier item (a box from one supplier is not a box from another). Conversions added in Rules or uploaded apply globally.
* Unit inference uses the quantity balance when volumes exist, otherwise the expected price.

## Data model

* For every file type except spend, the newest mapped upload replaces the previous one. Several spend files can be kept; the newest mapped is active; the proof screen runs on each.
* A **run** = stage 1 (matching, cached by data + rule version + learned cross-references) + stage 2 (decisions, checks, ledger). Review decisions create a new, fast run that reuses stage 1, so the ledger reconciles after every click. "Link again with everything learned" re-runs stage 1 with the learned rules.

## UI

* Class colours for the Sankey and ledger were checked with a palette validator (lightness band, chroma, colour-blind and normal-vision separation). Some sit below 3:1 contrast, so every class is always labelled and every chart has a table view.
* The Sankey enforces a minimum visual width (3% of total) for small streams and says so; labels and tooltips show real values.
* The Simulate result card counts to its new value (respects reduced motion); click the sensitivity chart to set the price; "Pin to compare" keeps one scenario beside the current one.
* User name for decisions defaults to "analyst" (no auth in scope).
