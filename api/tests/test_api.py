"""End-to-end API flow with fixtures created in code: upload -> map -> run -> review -> money flow -> export."""
import io
import time

import pandas as pd
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from tests import fixtures as fx


def _csv(df: pd.DataFrame, **rename) -> tuple[str, bytes, str]:
    return df.rename(columns=rename).to_csv(index=False).encode()


def client():
    import main
    c = TestClient(main.app)
    c.__enter__()
    return c


def wait(c, pid, rid):
    for _ in range(200):
        r = c.get(f"/api/projects/{pid}/runs/{rid}").json()
        if r["status"] in ("done", "failed"):
            return r
        time.sleep(0.05)
    raise AssertionError("run did not finish")


def test_full_flow():
    c = client()
    assert c.get("/api/projects").json() == []          # starts empty
    pid = c.post("/api/projects", json={"name": "T", "display_currency": "USD"}).json()["id"]
    rd = c.get(f"/api/projects/{pid}/readiness").json()
    assert not rd["can_run"]
    # different column names than canonical, plus an xlsx with two tabs
    spend = fx.spend().rename(columns={"supplier_name": "Vendor", "description": "Item text", "qty": "Quantity", "unit_price": "Net price",
                                       "purchase_uom": "UoM", "currency": "Curr", "supplier_part_no": "Vendor part", "cost_center": "Cost centre",
                                       "line_id": "Line ID", "invoice_month": "Period", "material_id_if_known": "Material number"})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        fx.bom().rename(columns={"parent_id": "Parent", "component_id": "Component", "qty_per_parent": "Qty"}).to_excel(w, sheet_name="BOM", index=False)
        fx.volumes().to_excel(w, sheet_name="Volumes", index=False)
    files = [("files", ("book.xlsx", buf.getvalue(), "application/octet-stream")),
             ("files", ("spend.csv", spend.to_csv(index=False).encode(), "text/csv")),
             ("files", ("master.csv", fx.master().to_csv(index=False).encode(), "text/csv")),
             ("files", ("products.csv", fx.products().to_csv(index=False).encode(), "text/csv")),
             ("files", ("fx.csv", fx.fx().to_csv(index=False).encode(), "text/csv")),
             ("files", ("xref.csv", fx.xrefs().to_csv(index=False).encode(), "text/csv")),
             ("files", ("key.csv", fx.answer_key().to_csv(index=False).encode(), "text/csv"))]
    ups = c.post(f"/api/projects/{pid}/uploads", files=files).json()
    by = {(u["filename"], u["sheet"]): u for u in ups}
    assert by[("book.xlsx", "BOM")]["suggested_type"] == "bom"
    assert by[("spend.csv", "")]["suggested_type"] == "spend"
    sm = by[("spend.csv", "")]["mapping"]
    assert sm["description"] == "Item text" and sm["qty"] == "Quantity" and sm["supplier_name"] == "Vendor"
    types = {("book.xlsx", "BOM"): "bom", ("book.xlsx", "Volumes"): "volumes", ("spend.csv", ""): "spend", ("master.csv", ""): "master",
             ("products.csv", ""): "products", ("fx.csv", ""): "fx", ("xref.csv", ""): "xrefs", ("key.csv", ""): "answer_key"}
    for k, u in by.items():
        t = types[k]
        m = u["mapping"] if u["suggested_type"] == t else c.get(f"/api/projects/{pid}/uploads/{u['id']}/suggest", params={"file_type": t}).json()["mapping"]
        body = {"file_type": t, "mapping": m}
        if t == "master":
            body["attribute_columns"] = ["material", "size", "hardness"]
            body["hard_attributes"] = ["material", "size", "hardness"]
        r = c.post(f"/api/projects/{pid}/uploads/{u['id']}/mapping", json=body)
        assert r.status_code == 200, (k, r.text)
    rd = c.get(f"/api/projects/{pid}/readiness").json()
    assert rd["can_run"], rd
    run = c.post(f"/api/projects/{pid}/runs").json()
    run = wait(c, pid, run["id"])
    assert run["status"] == "done", run
    assert run["summary"]["ledger"]["difference_cents"] == 0
    q = c.get(f"/api/projects/{pid}/review").json()
    assert q["queue"], q
    item = q["queue"][0]
    det = c.get(f"/api/projects/{pid}/items/{item['item_id']}").json()
    assert det["item"]["evidence"]
    # approving an unknown unit without factor is refused, with factor works
    r = c.post(f"/api/projects/{pid}/review/{item['item_id']}", json={"action": "approve"})
    assert r.status_code == 400
    r = c.post(f"/api/projects/{pid}/review/{item['item_id']}", json={"action": "approve", "unit_factor": 100}).json()
    assert r["summary"]["ledger"]["difference_cents"] == 0
    assert any("=" in s for s in r["saved_rules"])
    # undo then redo
    assert c.post(f"/api/projects/{pid}/review/undo").json()["ok"]
    c.post(f"/api/projects/{pid}/review/{item['item_id']}", json={"action": "approve", "unit_factor": 100})
    mf = c.get(f"/api/projects/{pid}/moneyflow").json()
    assert mf["summary"]["difference_cents"] == 0
    rc = c.get(f"/api/projects/{pid}/receipts", params={"kind": "class", "key": "allocated"}).json()
    assert rc["count"] > 0 and rc["formula"]
    part = c.get(f"/api/projects/{pid}/parts").json()[0]["part_id"]
    pdet = c.get(f"/api/projects/{pid}/parts/{part}").json()
    assert pdet["spend_cents"] > 0
    si = c.get(f"/api/projects/{pid}/simulate/{part}").json()
    assert si["rows"] and si["baselines"]
    # refusal override needs a reason
    ref = q["refused"][0]
    r = c.post(f"/api/projects/{pid}/review/{ref['item_id']}", json={"action": "approve", "part_id": ref["suggestion_part_id"]})
    assert r.status_code == 400
    # rules preview + apply
    rules = c.get(f"/api/projects/{pid}/rules").json()["rules"]
    rules["hard_attributes"] = {"*": ["material"]}
    pv = c.post(f"/api/projects/{pid}/rules/preview", json={"rules": rules}).json()
    assert "adds" in pv and pv["loosened"]
    assert c.post(f"/api/projects/{pid}/rules", json={"rules": rules}).status_code == 400   # needs reason
    ap = c.post(f"/api/projects/{pid}/rules", json={"rules": rules, "why": "test"}).json()
    run2 = wait(c, pid, ap["run_id"])
    assert run2["summary"]["ledger"]["difference_cents"] == 0
    # proof
    pr = c.get(f"/api/projects/{pid}/proof").json()
    assert pr["available"] and len(pr["datasets"][0]["rows"]) == 3
    # export
    x = c.post(f"/api/projects/{pid}/export", json={"scenario": {"part_id": part, "rows": si["rows"], "baseline": si["baselines"][0]["value"],
                                                                 "new_price": si["baselines"][0]["value"] * 0.9, "share": 1.0}})
    wb = load_workbook(io.BytesIO(x.content))
    assert {"Links", "Allocation by product", "Spend explainer", "Explainer lines", "BOM cost", "Scenario", "Review decisions",
            "Learned rules", "Rule version", "Data readiness"} <= set(wb.sheetnames)
    csv = c.get(f"/api/projects/{pid}/export/links.csv")
    assert csv.status_code == 200 and b"item_id" in csv.content
    # saved mapping reused on re-upload with the same headers
    again = c.post(f"/api/projects/{pid}/uploads", files=[("files", ("spend2.csv", spend.to_csv(index=False).encode(), "text/csv"))]).json()[0]
    assert again["saved_mapping"] and again["suggested_type"] == "spend"
