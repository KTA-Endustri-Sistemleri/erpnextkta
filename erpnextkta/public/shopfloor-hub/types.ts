// Types for Shopfloor Hub Cockpit
import type { Component } from "vue";

export type WorkOrderViewMode = "work_orders" | "operations" | "work_cards" | "reports";

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

export interface WorkOrderPrintFormatOption {
  name: string;
  label: string;
  is_default: boolean;
  default_print_language?: string;
  raw_printing?: number;
  print_format_builder_beta?: number;
}

export interface LetterHeadOption {
  name: string;
  is_default: number;
}

export interface WorkOrderPrintOptionsResponse {
  doctype: string;
  work_order: string | null;
  can_print: boolean;
  default_print_format: string;
  print_formats: WorkOrderPrintFormatOption[];
  default_letter_head: string;
  letter_heads: LetterHeadOption[];
  with_letterhead: number;
  allow_print_for_draft: number;
  allow_print_for_cancelled: number;
}

export type ReportCategory = "Üretim Teyitleri" | "Malzeme ve Stok" | "Analitik";

export interface ReportDefinition {
  id: string;
  title: string;
  description: string;
  category: ReportCategory;
  icon: string;
  component: Component;
}

export type OperationCompletionStatusFilter = "completed" | "partial" | "unconfirmed" | "all";

export interface OperationCompletionRow {
  work_order: string;
  production_item: string;
  item_name?: string | null;
  stock_uom?: string | null;
  wo_status?: string;
  operation: string;
  workstation?: string | null;
  sequence_id?: number;
  qty: number;
  completed_qty: number;
  confirmed_qty: number;
  pending_qty?: number;
  completion_pct: number;
  is_completed: boolean;
  confirmation_count: number;
  final_confirmation_count: number;
  stock_entry_count?: number;
  last_confirmation_at?: string | null;
  last_confirmed_by?: string | null;
  last_confirmation?: string | null;
  wo_creation?: string | null;
  custom_released_with_shortage?: number;
  source_type?: "co11n" | "legacy" | "mixed" | "none";
  wo_qty?: number;
  co11n_qty?: number;
  legacy_manufacture_qty?: number;
  completion_percent?: number;
  status?: "completed" | "partial" | "unconfirmed";
  has_final_confirmation?: number;
  last_posting_date?: string | null;
  last_posting_time?: string | null;
}

export interface OperationCompletionSummary {
  completed_operations: number;
  partial_operations: number;
  unconfirmed_operations: number;
  shortage_operations?: number;
  unique_work_orders: number;
  total_confirmed_qty: number;
}

export interface OperationCompletionCounts {
  completed: number;
  partial: number;
  unconfirmed: number;
  shortage?: number;
  all: number;
}

export interface OperationCompletionFilterOptions {
  operations: string[];
  workstations: string[];
}

export interface OperationCompletionResponse {
  rows: OperationCompletionRow[];
  summary: OperationCompletionSummary;
  counts: OperationCompletionCounts;
  filter_options: OperationCompletionFilterOptions;
}

export interface OperationCompletionWorkOrderGroup {
  work_order: string;
  wo_status: string;
  custom_released_with_shortage: number;
  production_item: string;
  item_name: string;
  stock_uom: string;
  qty: number;
  operations: OperationCompletionRow[];
  completed_count: number;
  partial_count: number;
  unconfirmed_count: number;
  overall_pct: number;
  wo_creation: string;
  last_confirmation_at: string;
  last_confirmed_by: string;
}

export type MaterialShortageStatusFilter =
  | "all"
  | "active_shortage"
  | "critical"
  | "transfer_required"
  | "resolved";

export interface MaterialShortageItemRow {
  item_code: string;
  item_name?: string | null;
  operation?: string | null;
  source_warehouse?: string | null;
  stock_uom?: string | null;
  required_qty?: number;
  consumed_qty?: number;
  remaining_required_qty: number;
  line_actual_qty: number;
  other_warehouses_qty: number;
  shortage_qty: number;
  availability_status: "critical" | "critical_shortage" | "transfer_required" | "available";
}

export interface MaterialShortageWorkOrderRow {
  work_order: string;
  wo_status: string;
  production_item: string;
  item_name?: string | null;
  stock_uom?: string | null;
  qty: number;
  produced_qty: number;
  wo_creation?: string | null;
  planned_start_date?: string | null;
  shortage_status: "critical" | "transfer_required" | "resolved";
  shortage_items_count: number;
  total_items: number;
  readiness_pct: number;
  items: MaterialShortageItemRow[];
}

export interface MaterialShortageSummary {
  total_work_orders: number;
  critical_work_orders: number;
  transfer_work_orders: number;
  resolved_work_orders?: number;
  total_shortage_items: number;
}

export interface MaterialShortageCounts {
  all: number;
  active_shortage?: number;
  critical: number;
  transfer_required: number;
  resolved: number;
}

export interface MaterialShortageFilterOptions {
  warehouses: string[];
}

export interface MaterialShortageResponse {
  rows: MaterialShortageWorkOrderRow[];
  summary: MaterialShortageSummary;
  counts: MaterialShortageCounts;
  filter_options: MaterialShortageFilterOptions;
}

