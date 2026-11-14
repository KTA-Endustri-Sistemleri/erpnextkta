export interface WeekBucket {
  key: string; // Örn: "2026_w45"
  label: string; // Örn: "2026-W45"
  is_current: boolean;
}

export interface NettingCellDetail {
  gross: number;
  po: number;
  net: number;
  order: number;
  projected: number;
}

export interface PeggingDemand {
  finished_item: string;
  item_name: string;
  bom: string;
  customer_group?: string;
  total: number;
  weeks: Record<string, number>;
}

export interface OpenPOReceipt {
  po_name: string;
  supplier: string;
  schedule_date: string;
  pending_qty: number;
  week: string;
}

export interface OpenSupplyItem {
  type: "PR" | "PO";
  name: string;
  po_name?: string;
  supplier?: string;
  state:
    | "Antrepoda"
    | "Gümrüklemede"
    | "Yolda"
    | "Mal Giriş"
    | "Mal Girişe Hazır"
    | "Açık Sipariş"
    | string;
  qty: number;
  date: string;
  week: string;
  date_label?: string;
  is_estimated?: boolean;
  loading_date?: string;
  eta_date?: string;
  customs_date?: string;
  clearance_start_date?: string;
  dispute_reason?: string;
  dispute_description?: string;
}

export interface SupplierQuotaInfo {
  supplier: string;
  quota_share: number;
  moq: number;
  pack: number;
  price: number;
  currency: string;
  lead_time_days: number;
  is_default?: boolean;
}

export interface MaterialItem {
  item_code: string;
  item_name: string;
  uom: string;
  supplier: string;
  sourcing_strategy?: string;
  suppliers_quota?: SupplierQuotaInfo[];
  planned_orders_by_supplier?: Record<string, Record<string, number>>;
  actual_stock: number;
  reserved_stock: number;
  free_stock: number;
  lead_time_days: number;
  moq: number;
  pack: number;
  unit_price: number;
  currency: string;
  planned_order_total: number;
  gross_total: number;
  net_total: number;
  po_total: number;
  antrepoda_total?: number;
  gumruklemede_total?: number;
  yolda_total?: number;
  po_kalan_total?: number;
  uyusmazlikta_total?: number;
  projected_total: number;
  order_amount: number;
  first_shortage_week?: string | null;
  coverage_weeks?: number;
  is_urgent: boolean;
  is_shortage: boolean;
  has_po: boolean;
  weeks: Record<string, NettingCellDetail>;
  pegging: PeggingDemand[];
  open_pos: (OpenPOReceipt | OpenSupplyItem)[];
  open_supplies?: OpenSupplyItem[];
}

export type WeeklyViewType =
  | "Önerilen Sipariş"
  | "Net İhtiyaç"
  | "Brüt İhtiyaç"
  | "Projeksiyon Bakiye";
export type GroupByType = "Bitmiş Ürün + Hammadde" | "Sadece Hammadde";
export type StatusFilterType =
  | "all"
  | "urgent"
  | "shortages"
  | "antrepoda"
  | "gumruklemede"
  | "yolda"
  | "uyusmazlikta"
  | "has_po"
  | "sufficient";

export interface MrpFilterState {
  from_date: string;
  to_date: string;
  weekly_view: WeeklyViewType;
  group_by: GroupByType;
  only_shortages: boolean;
  supplier: string;
  hammadde: string;
  custom_musteri_grubu: string;
  item_group: string;
  search_query: string;
  status_filter: StatusFilterType;
}

export interface MrpSummary {
  total_items: number;
  shortage_count: number;
  urgent_count: number;
  po_count: number;
  antrepo_count?: number;
  gumruk_count?: number;
  yolda_count?: number;
  uyusmazlik_count?: number;
  sufficient_count: number;
  order_amount_by_currency: Record<string, number>;
}

export interface MrpSettings {
  urgent_weeks: number;
  default_include_po: number;
  planning_horizon_days: number;
}

export interface MrpNettingDialogData {
  item_code: string;
  item_name: string;
  uom: string;
  supplier: string;
  moq: number;
  pack: number;
  lead_time: number;
  actual: number;
  reserved: number;
  free_stock: number;
  week: string;
  week_label: string;
  balance_before: number;
  gross: number;
  receipts: number;
  net: number;
  order: number;
  projected: number;
  include_po: number;
  pos: Array<{
    po_name: string;
    supplier: string;
    schedule_date: string;
    pending: number;
  }>;
  demands: Array<{
    finished_item: string;
    item_name: string;
    bom: string;
    customer_group: string;
    qty: number;
  }>;
}
