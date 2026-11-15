// Small fixtures created in test code. Never imported by the running app.
const csv = (rows: (string | number | null)[][]) => rows.map((r) => r.map((v) => (v === null ? "" : String(v))).join(",")).join("\n");

export const files = {
  "bom.csv": csv([
    ["Parent", "Component", "Qty", "UoM", "Text"],
    ["P-A", "SUB-1", 1, "EA", "Subassembly"],
    ["P-A", "PRT-SH1", 1, "EA", "Shaft"],
    ["P-A", "PRT-OR1", 2, "EA", "O-ring"],
    ["SUB-1", "PRT-SC1", 4, "EA", "Screw"],
    ["P-B", "PRT-SH1", 1, "EA", "Shaft"],
    ["P-B", "PRT-OR2", 2, "EA", "O-ring"],
    ["P-B", "PRT-SC1", 4, "EA", "Screw"],
  ]),
  "master.csv": csv([
    ["part_id", "description", "category", "base_uom", "standard_cost", "material", "size", "hardness"],
    ["PRT-SH1", "Shaft stainless", "Shafts", "EA", 3.0, "Stainless 1.4301", "8x120", null],
    ["PRT-OR1", "O-ring", "Seals", "EA", 0.15, "NBR", "20x2", 70],
    ["PRT-OR2", "O-ring", "Seals", "EA", 0.16, "NBR", "20x2", null],
    ["PRT-OR3", "O-ring", "Seals", "EA", 0.4, "FKM", "20x2", 90],
    ["PRT-SC1", "Screw", "Fasteners", "EA", 0.05, "A2", "M6x20", null],
  ]),
  "volumes.csv": csv([["product_id", "period", "units_built"], ...["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"].flatMap((m) => [["P-A", m, 1000], ["P-B", m, 500]])]),
  "spend.csv": csv([
    ["Line ID", "Vendor", "Vendor part", "Item text", "Quantity", "UoM", "Net price", "Curr", "Period", "Cost centre"],
    ["L1", "S1", "S1-SH8", "Welle 8x120 Edelstahl 1.4301", 6000, "EA", 3.1, "USD", "2026-02", "Production"],
    ["L2", "S2", "B-88", "Shaft SS304 8 x 120mm", 3000, "EA", 3.3, "USD", "2026-03", "Production"],
    ["L3", "S1", "S1-C45", "Welle 8x120 C45", 500, "EA", 1.9, "USD", "2026-03", "Production"],
    ["L4", "S3", "OR-90", "O-Ring 20x2 NBR 90 Shore", 6000, "EA", 0.16, "USD", "2026-02", "Production"],
    ["L5", "S3", "OR-70", "O-Ring 20x2 NBR 70 Shore", 12000, "EA", 0.15, "USD", "2026-02", "Production"],
    ["L6", "S4", "SC-620", "Screw M6x20 stainless A2", 360, "BX", 5.0, "USD", "2026-03", "Production"],
    ["L8", "S1", "S1-SH8", "Welle 8x120 1.4301 Ersatzteil", 200, "EA", 4.6, "USD", "2026-04", "Service"],
    ["L9", "S6", null, "Cleaning cloth", 10, "PK", 12.0, "USD", "2026-04", "Maintenance"],
  ]),
};
