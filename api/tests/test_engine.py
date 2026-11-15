import copy

import pandas as pd

from engine.bom import explode, required_quantities, top_level_products
from engine.ledger import split_int
from engine.pipeline import stage1, stage2
from engine.simulator import simulate
from tests import fixtures as fx


def run(**over):
    inp = fx.inputs(**over)
    return stage2(stage1(inp), inp), inp


def status_of(res, desc):
    r = res["items"][res["items"]["description"] == desc].iloc[0]
    return r


def test_bom_explosion_multilevel():
    b = fx.bom()
    prods = top_level_products(b, fx.products())
    tree, leaves = explode(b, prods["product_id"].tolist())
    sc1_pa = leaves[(leaves.product_id == "P-A") & (leaves.part_id == "PRT-SC1")].qty_per_unit.iloc[0]
    assert sc1_pa == 4  # via SUB-1
    rpp, _ = required_quantities(leaves, fx.volumes(), {"P-A", "P-B"})
    assert rpp[rpp.part_id == "PRT-SH1"].required.sum() == 6000 + 3000


def test_split_int_exact():
    for total in (0, 1, 7, 1000003, -55):
        parts = split_int(total, [1, 2, 3.5, 0.25])
        assert sum(parts) == total


def test_ladder_outcomes():
    res, _ = run()
    assert status_of(res, "Bracket").rung == "exact"
    assert status_of(res, "Fastener pack").rung == "xref"
    r = status_of(res, "Welle 8x120 Edelstahl 1.4301")
    assert r.status == "auto" and r.part_id == "PRT-SH1"
    assert status_of(res, "O-Ring 20x2 NBR 70 Shore").part_id == "PRT-OR1"


def test_hard_conflict_never_linked_even_if_price_qty_point_to_it():
    # make the carbon-steel look-alike cheap-looking and its quantity exactly fill the demand
    sp = fx.spend()
    sp.loc[sp.line_id == "L3", ["qty", "unit_price"]] = [3000, 3.0]
    sp = sp[sp.line_id != "L2"]
    sp = sp[sp.line_id != "L11"]
    res, _ = run(spend=sp)
    r = status_of(res, "Welle 8x120 C45")
    assert r.status == "refused" and pd.isna(r.part_id)
    assert "material" in r.reason


def test_missing_attribute_resolved_only_with_margin():
    res, _ = run()
    r = status_of(res, "O-Ring 20x2 NBR 90 Shore")
    assert r.status == "evidence" and r.part_id == "PRT-OR2"   # OR1 refused (hardness 70), OR2 missing hardness, balance decides
    # with a tiny quantity the balance margin is not met -> review with suggestion
    sp = fx.spend()
    sp.loc[sp.line_id == "L4", "qty"] = 600
    vol = fx.volumes()
    res2, _ = run(spend=sp, volumes=vol)
    r2 = status_of(res2, "O-Ring 20x2 NBR 90 Shore")
    inp = fx.inputs(spend=sp)
    inp.rules["thresholds"]["balance_margin"] = 0.95
    res3 = stage2(stage1(inp), inp)
    r3 = status_of(res3, "O-Ring 20x2 NBR 90 Shore")
    assert r3.status == "review" and r3.suggestion_part_id == "PRT-OR2"


def test_unknown_unit_goes_to_review_and_learned_factor_converts_next_time():
    res, inp = run()
    r = status_of(res, "Screw M6x20 stainless A2")
    assert r.status == "review"
    assert r.evidence["unit"]["factor"] == 100
    learned = [{"id": 1, "kind": "unit", "value": {"purchase_uom": "BX", "base_uom": "EA", "factor": 100, "item_key": r.item_key}},
               {"id": 2, "kind": "xref", "value": {"supplier_key": r.supplier_key, "supplier_pn": r.supplier_pn, "item_key": r.item_key, "part_id": "PRT-SC1"}}]
    inp2 = fx.inputs(learned=learned)
    res2 = stage2(stage1(inp2), inp2)
    r2 = status_of(res2, "Screw M6x20 stainless A2")
    assert r2.status == "auto" and r2.part_id == "PRT-SC1" and r2.base_qty == 36000


def test_learned_xref_links_same_supplier_pn_without_review():
    learned = [{"id": 9, "kind": "xref", "value": {"supplier_key": "s3", "supplier_pn": "OR-90", "item_key": "x", "part_id": "PRT-OR2"}}]
    res, _ = run(learned=learned)
    r = status_of(res, "O-Ring 20x2 NBR 90 Shore")
    assert r.status == "auto" and r.rung == "learned"


def test_ledger_reconciles_exactly_after_decisions_and_rule_changes():
    res, inp = run()
    assert res["summary"]["difference_cents"] == 0
    assert res["summary"]["total_cents"] == res["lines"]["cents"].sum()
    # a human decision
    screw = status_of(res, "Screw M6x20 stainless A2")
    inp.decisions = [{"item_id": screw.item_id, "item_key": screw.item_key, "action": "approve", "part_id": "PRT-SC1", "unit_factor": 100}]
    res2 = stage2(stage1(inp), inp)
    assert res2["summary"]["difference_cents"] == 0
    assert status_of(res2, "Screw M6x20 stainless A2").status == "human"
    # a rule change
    inp3 = fx.inputs()
    inp3.rules["price_band"] = {"low": 0.95, "high": 1.05}
    inp3.rules["hard_attributes"] = {"*": ["material"]}
    res3 = stage2(stage1(inp3), inp3)
    assert res3["summary"]["difference_cents"] == 0
    # credit note and odd amounts
    sp = fx.spend()
    sp.loc[len(sp)] = ["L99", "S1", "S1-SH8", "Welle 8x120 Edelstahl 1.4301", -10, "EA", 3.333, "USD", "2026-06", "Production", None]
    res4, _ = run(spend=sp)
    assert res4["summary"]["difference_cents"] == 0


def test_eight_classes_and_service():
    res, _ = run()
    keys = [c["key"] for c in res["summary"]["classes"]]
    assert keys == ["allocated", "beyond_need", "service", "shop_supplies", "pending_review", "refused", "not_in_bom", "no_match"]
    cls = res["ledger"].groupby("class")["cents"].sum()
    assert cls["service"] == 200 * 460
    assert cls["not_in_bom"] == 50 * 210
    assert cls["shop_supplies"] == 10 * 1200


def test_no_volumes_runs_and_allocation_off():
    res, _ = run(volumes=None)
    assert res["summary"]["difference_cents"] == 0
    assert all(c["key"] not in ("allocated", "beyond_need") for c in res["summary"]["classes"])


def test_simulator_acceptance():
    rows = [{"product_id": "X", "qty_per_unit": 4, "planned_volume": 10000}]
    r = simulate(rows, 0.50, 0.40, 1.0)
    assert round(r["total_change"], 6) == -4000
    assert simulate(rows, 0.50, 0.60, 1.0)["total_change"] > 0
    assert round(simulate(rows, 0.50, 0.40, 0.5)["total_change"], 6) == -2000
    assert simulate([{"product_id": "X", "qty_per_unit": 4, "planned_volume": None}], 0.5, 0.4, 1)["per_unit_only"]


def test_no_hardcoded_data_in_engine():
    """The engine must not contain fixture identifiers."""
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    for p in list((root / "engine").glob("*.py")) + list((root / "routes").glob("*.py")):
        txt = p.read_text()
        for token in ("PRT-", "P-A", "Pump A", "OR-90", "S1-SH8"):
            assert token not in txt, f"{token} found in {p}"


def test_ai_only_proposes_and_rules_recheck():
    """A fake ranker: the AI's pick is re-checked; a hard conflict drops it; nothing is auto-linked on AI alone."""
    sp = fx.spend()
    sp.loc[len(sp)] = ["L50", "S9", "Z-1", "Dichtring Viton", 100, "EA", 0.4, "USD", "2026-03", "Production", None]
    inp = fx.inputs(spend=sp, volumes=None)
    calls = []

    def fake(payload):
        calls.append(payload)
        ids = [c["part_id"] for c in payload["candidates"]]
        return {"best_part_id": ids[0], "reason": "Looks like the same seal.", "attributes": {}}

    res = stage2(stage1(inp, ai=fake), inp)
    assert calls, "AI was not asked about unresolved items"
    it = res["items"]
    assert not ((it["rung"] == "ai") & it["status"].isin(["auto"])).any()
    for r in it[it["ai_proposed"]].itertuples():
        assert r.status in ("review", "evidence")
    assert res["summary"]["difference_cents"] == 0


def test_guardrails():
    from llm.guardrails import explanation_ok, filter_attributes, numbers_supported
    assert numbers_supported("8x120", "Welle 8 x 120 C45")
    assert not numbers_supported("8x150", "Welle 8 x 120 C45")
    assert numbers_supported("12.7", "rod 0.5 in")          # mm <-> inch
    assert filter_attributes({"size": "8x999", "material": "stainless"}, "shaft 8x120 Edelstahl", ["size", "material"]) == {"material": "stainless"}
    assert not explanation_ok("Costs 42 more", "price 3.10")


def test_blank_supplier_part_numbers_do_not_pool_items():
    import numpy as np
    from engine.items import build_items, prepare_lines
    from engine.normalize import fx_lookup, synonym_key
    from engine.rules import default_rules
    r = default_rules()
    sp = pd.DataFrame({"supplier_name": ["S", "S", "S"], "supplier_part_no": [np.nan, "", None], "description": ["housing A1", "housing B2", "housing A1"],
                       "qty": [1, 1, 1], "unit_price": [1, 1, 1]})
    items = build_items(prepare_lines(sp, fx_lookup(None, "USD"), synonym_key(r["synonyms"]), r))
    assert len(items) == 2  # one item per description, never one "nan" item per supplier
    assert not items["item_key"].str.contains("nan").any()


def test_size_in_mixed_notation_and_finish_words():
    from engine.ladder import AttrMeta, analyze_text, compare_attr
    from engine.normalize import synonym_key
    from engine.rules import default_rules
    k = synonym_key(default_rules()["synonyms"])
    import engine.ladder as L
    L._CURRENT_SYN[0] = k
    L._PV_CACHE.clear()
    size = AttrMeta("size", "text", vocab={"d16", "l200", "d12", "l150", "16", "200", "12", "150", "kw", "3", "1.5", "cp", "100", "300"}, size_like=True)
    assert compare_attr(size, "D16 L200", analyze_text("SHAFT 16X200 SS", k))["result"] == "agree"
    assert compare_attr(size, "D12 L150", analyze_text("SHAFT 16X200 SS", k))["result"] == "differ"
    assert compare_attr(size, "3 kW", analyze_text("MTR 3KW", k))["result"] == "agree"
    assert compare_attr(size, "1.5 kW", analyze_text("MTR 3KW", k))["result"] == "differ"
    assert compare_attr(size, "CP-300", analyze_text("HOUSING CP300", k))["result"] == "agree"
    assert compare_attr(size, "CP-100", analyze_text("HOUSING CP300", k))["result"] == "differ"
    mat = AttrMeta("material", "text", vocab={"steel", "8.8", "zinc", "stainless", "a2", "bronze", "cc491k", "c45", "carbon"})
    assert compare_attr(mat, "steel 8.8 zinc", analyze_text("Hex bolt M10x30 gr 8.8 zinc plated", k))["result"] == "agree"
    assert compare_attr(mat, "bronze CC491K", analyze_text("Impeller 120mm bronze C90700", k))["result"] == "agree"
    assert compare_attr(mat, "stainless A2", analyze_text("Hex cap screw M6x20 gr 8.8 zinc", k))["result"] == "differ"


def test_discontinued_status_any_spelling():
    from engine.bom import top_level_products
    p = pd.DataFrame({"product_id": ["A", "B"], "status": ["active", "discontinued 2024"]})
    out = top_level_products(fx.bom(), p).set_index("product_id")["status"]
    assert out["B"] == "discontinued" and out["A"] == "active"
