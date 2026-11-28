export type PdaScreenKey = "picking" | "split" | "merge" | "transfer" | "lookup";

export type PdaUtilityScreenKey = "settings";

export type PdaModuleKey = "home" | PdaScreenKey | PdaUtilityScreenKey;

export interface PdaMenuScreenItem {
  key: PdaScreenKey;
  title: string;
  subtitle: string;
  icon: string;
  accent: string;
}

export interface PdaMenuCategory {
  key: string;
  title: string;
  icon: string;
  items: PdaMenuScreenItem[];
}

export interface PdaOperator {
  employee: string;
  name: string;
  employee_name: string;
  department: string;
  user_id: string;
  has_pin: boolean;
}

export interface PdaBootData {
  is_locked: boolean;
  current_user: string;
  active_operator: PdaOperator | null;
  device_authorized: boolean;
  inactivity_timeout_sec: number;
  operators: PdaOperator[];
  open_picking_count: number;
  menu_categories: PdaMenuCategory[];
}

export interface VerifyPdaPinResponse {
  ok: boolean;
  user: string;
  employee: string;
  employee_name: string;
  csrf_token: string;
  menu_categories?: PdaMenuCategory[];
  open_picking_count?: number;
  lang?: string;
  messages?: Record<string, string>;
}

export interface HandoverLogoutResponse {
  ok: boolean;
  is_locked: boolean;
  device_authorized: boolean;
  csrf_token: string;
  lang?: string;
  messages?: Record<string, string>;
}

export interface BoxWarehouseBalance {
  warehouse: string;
  qty: number;
}

export interface BoxScanResult {
  item_code: string;
  item_name: string | null;
  stock_uom: string | null;
  batch_no: string;
  base_lot?: string | null;
  is_standard_batch: boolean;
  label_name: string | null;
  label_type: string | null;
  sut_barcode: string | null;
  expiry_date: string | null;
  total_qty: number;
  balances: BoxWarehouseBalance[];
  kind?: string;
}

export interface PackageMergeSourceInput {
  batch_no: string;
  warehouse: string;
  qty?: number;
}

export interface PackageMergeResponse {
  ok: boolean;
  stock_entry: string;
  item_code: string;
  base_lot: string;
  target_batch: string;
  target_warehouse: string;
  total_qty: number;
  is_mixed_lot: boolean;
  remarks: string;
  source_batches: string[];
  target_label_name?: string | null;
  quality_ref?: string | null;
  owner?: string;
}

export interface CreatedSplitBatch {
  batch_no: string;
  qty: number;
  label_name?: string | null;
}

export interface PackageSplitResponse {
  ok: boolean;
  stock_entry: string;
  base_lot: string;
  source_batch: string;
  source_warehouse: string;
  remaining_qty: number;
  created_batches: CreatedSplitBatch[];
  source_label_name?: string | null;
  source_label_reprinted?: boolean;
  queued_reprint_count?: number;
}

export interface MaterialTransferResponse {
  ok: boolean;
  stock_entry: string;
  item_code: string;
  batch_no: string;
  qty: number;
  source_warehouse: string;
  target_warehouse: string;
  owner: string;
}

export interface StockLookupWarehouseResult {
  kind: "warehouse";
  warehouse: string;
  warehouse_name: string;
  company: string;
  items: Array<{
    item_code: string;
    item_name?: string;
    stock_uom?: string;
    actual_qty: number;
    reserved_qty?: number;
  }>;
}

export interface StockLookupItemResult {
  kind: "item";
  item_code: string;
  item_name: string | null;
  stock_uom: string | null;
  has_batch_no: number;
  total_qty: number;
  warehouses: Array<{ warehouse: string; qty: number; reserved_qty?: number }>;
  batches: Array<{ warehouse: string; batch_no: string; qty: number; is_standard_batch?: boolean }>;
}

export type StockLookupResult =
  | (BoxScanResult & { kind: "batch" })
  | StockLookupWarehouseResult
  | StockLookupItemResult;

export interface PdaPrinterOption {
  name: string;
  printer_name: string;
  ip: string | null;
  port: number;
}

export interface PdaPrinterPreferences {
  printer: string | null;
  fallback_printer: string | null;
  disabled: number;
}

export interface PdaSettingsData {
  has_employee: boolean;
  employee: string | null;
  employee_name: string | null;
  department: string | null;
  has_pin: boolean;
  can_manage_operator_pins: boolean;
  authorized_printers: PdaPrinterOption[];
  printer_preferences: PdaPrinterPreferences;
  user_language: string;
  manageable_operators: PdaOperator[];
}

export interface PdaPrinterTestResponse {
  ok: boolean;
  printer: string;
  online: boolean;
  status: string;
  message: string;
}

export interface PdaLanguageUpdateResponse {
  ok: boolean;
  lang: string;
  messages: Record<string, string>;
}
