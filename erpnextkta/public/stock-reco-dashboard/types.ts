export type RecoMainTab = "operations" | "analytics";

export type RecoRelabelMode = "mode1_changed" | "mode2_all";

export type RecoRouteOptions = {
  doc?: string | null;
  tab?: string | null;
};

export interface StockRecoListRow {
  name: string;
  posting_date: string;
  posting_time: string;
  purpose: string;
  set_warehouse: string | null;
  company: string;
  docstatus: 0 | 1;
  owner: string;
  modified: string;
  item_count: number;
  positive_item_count: number;
}

export type RecoPreviewStatus =
  | "valid"
  | "qty_changed"
  | "missing_label"
  | "legacy_batch";

export interface StockRecoPreviewRow {
  row_name: string;
  item_code: string;
  item_name: string;
  uom: string | null;
  warehouse: string;
  batch_no: string | null;
  is_standard_batch: boolean;
  is_legacy: boolean;
  qty: number;
  current_qty: number;
  label_name: string | null;
  label_qty: number | null;
  status: RecoPreviewStatus;
  suggested_mode1_selected: boolean;
  has_batch_no: number | boolean;
}

export interface StockRecoPreviewDoc {
  name: string;
  docstatus: number;
  posting_date: string | null;
  posting_time: string | null;
  set_warehouse: string | null;
  company: string;
  purpose: string;
}

export interface StockRecoPreviewSummary {
  total_positive: number;
  valid: number;
  qty_changed: number;
  missing_label: number;
  legacy_batch: number;
}

export interface StockRecoPreviewResponse {
  doc: StockRecoPreviewDoc;
  rows: StockRecoPreviewRow[];
  summary: StockRecoPreviewSummary;
}

export interface StockRecoRelabelSelection {
  row_name: string;
  item_code: string;
  warehouse: string;
  source_batch: string | null;
  qty: number;
  convert_legacy: number;
  box_splits: number[];
}

export interface StockRecoRelabelResult {
  stock_reconciliation?: string;
  stock_conciliation?: string;
  docstatus?: number;
  stock_entries?: string[];
  labels: (string | number)[];
  queued_print_count: number;
}

export type RecoWarehouseDiff = {
  warehouse: string;
  diff: number;
};

export type RecoAnalyticsItem = {
  item_code: string;
  item_name: string;
  uom: string;
  net_diff: number;
  total_plus: number;
  total_minus: number;
  docs_count: number;
  risk_score: number;
  warehouses: RecoWarehouseDiff[];
};

export type RecoAnomalyItem = {
  id: string;
  type: string;
  severity: "HIGH" | "MED" | "LOW";
  score: number;
  title: string;
  desc: string;
  action: {
    kind: "item" | "doc";
    item_code?: string;
    docname?: string;
  };
};

export type RecoDocDetail = {
  name: string;
  posting_date: string;
  docstatus: number;
  warehouse: string;
  diff_qty: number;
};
