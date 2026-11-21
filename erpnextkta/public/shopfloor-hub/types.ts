// Types for Shopfloor Hub Cockpit

export type WorkOrderViewMode =
  | "work_orders"
  | "operations"
  | "work_cards"
  | "line_transfers";

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
  reserved_qty?: number;
  free_qty?: number;
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
  has_sibling_line_stock?: boolean;
  sibling_line_warehouses?: OtherWarehouseStock[];
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
  source_actual_qty?: number;
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

export interface MaterialConsumptionItem {
  item_code: string;
  item_name?: string | null;
  total_qty: number;
  uom: string;
}

export interface ScrapAllocationItem {
  item_code: string;
  qty: number;
  uom: string;
  reason?: string | null;
}

export interface CardDetailItem {
  card_name: string;
  operator?: string | null;
  durum: string;
  net_calisma_suresi: number;
  islem_adedi: number;
  creation: string;
}

export interface SubOperationAnalytics {
  sub_op_id: string;
  title: string;
  sequence: number;
  status: string;
  status_badge: string;
  is_tuketim_hesaplanir: number;
  total_process_qty: number;
  total_duration_mins: number;
  consumptions: MaterialConsumptionItem[];
  scraps: ScrapAllocationItem[];
  cards: CardDetailItem[];
}

export interface KtaOperationGroup {
  op_code: string;
  op_title: string;
  total_duration_mins: number;
  sub_operations: SubOperationAnalytics[];
}

export interface WorkCardSummaryStats {
  total_cards: number;
  completed_cards: number;
  in_progress_cards: number;
  total_duration_mins: number;
  total_scrap_qty: number;
}

export interface OperationAnalytics {
  operation_name: string;
  sequence_id?: number;
  job_card?: string | null;
  status: string;
  total_duration_mins: number;
  unmatched_scraps: ScrapAllocationItem[];
  sub_operations: SubOperationAnalytics[];
  kta_operations?: KtaOperationGroup[];
}

export type OperationCardAnalytics = OperationAnalytics;

export interface OperatorConsumptionItem {
  operator: string;
  operator_name: string;
  consumed_qty: number;
  card_count: number;
  percentage: number;
}

export interface MaterialReconciliationItem {
  item_code: string;
  item_name?: string | null;
  operation?: string | null;
  stock_uom: string;
  planned_qty: number;
  consumed_qty: number;
  scrap_qty: number;
  total_spent: number;
  variance: number;
  status: string;
  status_badge: string;
  operators?: OperatorConsumptionItem[];
}

export interface WorkCardAnalyticsResponse {
  work_order: string;
  production_item: string;
  item_name?: string | null;
  qty: number;
  summary: WorkCardSummaryStats;
  operations: OperationAnalytics[];
  material_reconciliation?: MaterialReconciliationItem[];
}

export type WorkOrderCardAnalyticsResponse = WorkCardAnalyticsResponse;

export type LineTransferSubMode = "deficit_pull" | "idle_push";

export interface ProductionWarehouseOption {
  warehouse: string;
  label: string;
}

export interface LineTransferSourceOption {
  warehouse: string;
  actual_qty: number;
  reserved_qty: number;
  free_qty: number;
  available_qty: number;
}

export interface LineTransferDeficitItem {
  item_code: string;
  item_name: string;
  uom: string;
  target_warehouse: string;
  line_actual_qty: number;
  reserved_qty: number;
  deficit_qty: number;
  suggested_source_warehouse: string;
  suggested_qty: number;
  uses_reserved_stock: boolean;
  default_selected: boolean;
  available_sources: LineTransferSourceOption[];
}

export interface LineIdleStockItem {
  item_code: string;
  item_name: string;
  uom: string;
  source_warehouse: string;
  actual_qty: number;
  reserved_qty: number;
  free_qty: number;
  suggested_target_warehouse: string;
  target_deficit_qty: number;
  suggested_qty: number;
}

export interface ManualTransferItemOption {
  item_code: string;
  item_name: string;
  uom: string;
  actual_qty: number;
  reserved_qty: number;
  free_qty: number;
}

export interface LineTransferPayloadItem {
  item_code: string;
  qty: number;
  source_warehouse: string;
  target_warehouse: string;
}

export interface LineTransferResponse {
  success: boolean;
  stock_entry: string;
  transferred_items: LineTransferPayloadItem[];
  used_reserved_stock?: boolean;
  message?: string;
}

export interface ReservedStockWarning {
  item_code: string;
  item_name?: string;
  uom?: string;
  source_warehouse: string;
  target_warehouse: string;
  qty: number;
  free_qty: number;
  actual_qty: number;
}

