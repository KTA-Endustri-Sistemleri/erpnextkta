// Copyright (c) 2026, KTA and Contributors
// See license.txt

export interface AllocatedBatch {
  batch_no: string;
  warehouse: string;
  shelf_location?: string | null;
  allocated_qty: number;
  available_qty?: number;
  expiry_date?: string | null;
}

export interface DeficitItem {
  item_code: string;
  item_name: string;
  uom?: string;
  deficit_qty: number;
  line_stock_qty: number;
  line_actual_qty?: number;
  reserved_qty?: number;
  available_stock: number; // Depodan Çıkacak Miktar
  source_parent_warehouse?: string;
  suggested_source_warehouse: string;
  suggested_batch_no?: string | null;
  box_count?: number;
  has_stock: boolean;
  in_flight_draft_orders?: string[];
  draft_orders?: string[];
  covered_by_draft?: boolean;
  draft_covered_qty?: number;
  allocated_batches: AllocatedBatch[];
  selected?: boolean;
  selectable?: boolean;
}

export interface FilterState {
  targetWarehouse: string;
}

export interface QuickLinePill {
  label: string;
  warehouse: string;
}

export function getInFlightDrafts(item: Partial<DeficitItem>): string[] {
  if (item.in_flight_draft_orders && item.in_flight_draft_orders.length > 0) {
    return item.in_flight_draft_orders;
  }
  if (item.draft_orders && item.draft_orders.length > 0) {
    return item.draft_orders;
  }
  return [];
}

export function isSelectable(item: DeficitItem): boolean {
  if (item.covered_by_draft) return false;
  if (item.selectable === false) return false;
  if (!item.has_stock || (Number(item.available_stock) || 0) <= 0) return false;
  if ((Number(item.deficit_qty) || 0) <= 0) return false;
  return true;
}
