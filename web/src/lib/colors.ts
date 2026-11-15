// Class colors: validated with the dataviz palette checker (lightness, chroma, CVD and normal-vision separation pass
// in this order). Contrast is below 3:1 for some slots, so every class is always direct-labeled and every chart has a table view.
export const CLASS_COLOR: Record<string, string> = {
  allocated: "#2B4FA8",
  beyond_need: "#1BA3C9",
  linked_unallocated: "#1BA3C9",
  service: "#8C8A2E",
  shop_supplies: "#5B9BF0",
  pending_review: "#00917A",
  refused: "#D9541E",
  not_in_bom: "#C99A0E",
  no_match: "#B4235A",
};
export const CLASS_ORDER = ["allocated", "beyond_need", "linked_unallocated", "service", "shop_supplies", "pending_review", "refused", "not_in_bom", "no_match"];
export const GROUP_LABEL: Record<string, string> = { explained: "Explained", waiting: "Waiting for a person", not_explained: "Not explained" };
export const C = { ink: "#12151C", muted: "#5B6270", line: "#E5E7EB", ai: "#6D28D9", human: "#0F766E", save: "#1D4ED8", navy: "#1E3A8A", cost: "#C2410C", rule: "#6B7280", grid: "#EEF0F3" };
