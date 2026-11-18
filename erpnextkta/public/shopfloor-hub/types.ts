// Types for Shopfloor Hub Cockpit

export type WorkOrderViewMode = "work_orders" | "operations";

export interface LinkedStockEntry {
  name: string;
  purpose: string;
  type: "consumption" | "manufacture";
  label: string;
}

export interface WorkOrderSummary {
  name: string;
  production_item: string;
  item_name?: string | null;
  qty: number;
  produced_qty: number;
  docstatus?: number;
  status: string;
  planned_start_date?: string | null;
  planned_end_date?: string | null;
  modified?: string | null;
}

export interface OperationInfo {
  operation: string;
  sequence_id: number;
  workstation?: string | null;
  completed_qty: number;
  pending_qty: number;
  status: string;
  is_last_op: boolean;
  job_card?: string | null;
}

export interface WorkOrderContext {
  work_order: string;
  item_code: string;
  item_name: string;
  stock_uom?: string;
  qty: number;
  produced_qty: number;
  docstatus?: number;
  status: string;
  custom_released_with_shortage?: number;
  source_warehouse?: string | null;
  fg_warehouse?: string | null;
  company?: string | null;
  selected_operation?: string | null;
  selected_job_card?: string | null;
  operations: OperationInfo[];
}

export interface ConfirmationRecord {
  name: string;
  operation: string;
  yield_qty: number;
  posting_date: string;
  posting_time?: string | null;
  confirmed_by?: string | null;
  stock_entry?: string | null;
  stock_entries?: LinkedStockEntry[];
  docstatus: number;
  is_final_confirmation?: number | boolean;
  creation?: string | null;
}

export interface ConfirmationPayload {
  work_order: string;
  operation: string;
  job_card?: string | null;
  yield_qty: number;
  is_final_confirmation: number;
}

export interface ConfirmationResponse {
  success: boolean;
  confirmation: string;
  stock_entry?: string | null;
  stock_entries?: LinkedStockEntry[];
  message?: string;
}

export interface OtherWarehouseStock {
  warehouse: string;
  actual_qty: number;
  available_qty: number;
}

export interface ItemAlternativeOption {
  item_code: string;
  item_name: string;
  description?: string;
  stock_uom: string;
  line_available_qty: number;
  other_warehouses_qty: number;
  two_way?: boolean;
}

export interface WorkOrderItemAlternativesResponse {
  work_order: string;
  row_name: string;
  current_item_code: string;
  root_item_code: string;
  is_alternative: boolean;
  can_swap: boolean;
  alternatives: ItemAlternativeOption[];
}

export type AvailabilityStatus =
  | "available"
  | "transfer_required"
  | "critical_shortage";

export interface MaterialAvailabilityItem {
  row_name?: string;
  custom_original_item?: string | null;
  is_alternative?: boolean;
  has_alternatives?: boolean;
  can_swap?: boolean;
  item_code: string;
  item_name: string;
  description?: string;
  required_qty: number;
  available_qty: number;
  line_available_qty?: number;
  line_actual_qty?: number;
  line_reserved_qty?: number;
  other_warehouses_qty?: number;
  other_warehouses?: OtherWarehouseStock[];
  shortage_qty: number;
  coverage_percent: number;
  is_available?: boolean;
  availability_status?: AvailabilityStatus;
  uom?: string;
  stock_uom?: string;
  warehouse?: string | null;
  source_warehouse?: string | null;
  is_shortage?: boolean;
}

export interface MaterialAvailabilityResponse {
  work_order: string;
  overall_readiness_percent: number;
  has_shortage: boolean;
  has_line_shortage?: boolean;
  has_critical_shortage?: boolean;
  can_fulfill_via_transfer?: boolean;
  shortage_count: number;
  critical_shortage_count?: number;
  transfer_required_count?: number;
  total_items?: number;
  items: MaterialAvailabilityItem[];
}

export interface CreateWorkOrderPayload {
  item_code: string;
  qty: number;
  bom_no?: string;
  source_warehouse?: string;
  wip_warehouse?: string;
  fg_warehouse?: string;
  planned_start_date?: string;
  planned_end_date?: string;
  company?: string;
  customer?: string;
}

export interface MaterialShortageItem {
  item_code: string;
  item_name: string;
  required_qty: number;
  line_actual_qty: number;
  shortage_qty: number;
  target_warehouse: string;
  source_warehouse: string | null;
  source_available_qty: number;
  available_sources: OtherWarehouseStock[];
  stock_uom: string;
}

export interface MaterialShortageCheckResponse {
  has_shortage: boolean;
  shortages: MaterialShortageItem[];
}

export interface MaterialTransferItem {
  item_code: string;
  qty: number;
  source_warehouse: string;
  target_warehouse: string;
}

export interface MaterialStagingResponse {
  success: boolean;
  stock_entry: string;
  transferred_items: any[];
  message?: string;
}

export type MaterialAvailability = MaterialAvailabilityResponse;
export type ShortageItem = MaterialAvailabilityItem;
