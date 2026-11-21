// Copyright (c) 2026, KTA and Contributors
// See license.txt

export interface ReplenishmentOrder {
  name: string;
  target_warehouse: string;
  status: string;
  company?: string;
  total_deficit_qty?: number;
  creation?: string;
  items?: PickingItem[];
}

export interface PickingItem {
  name: string;
  item_code: string;
  item_name?: string;
  uom?: string;
  deficit_qty: number;
  picked_qty: number;
  is_picked: number | boolean;
  suggested_source_warehouse?: string;
  suggested_batch_no?: string;
  picked_source_warehouse?: string;
  picked_batch_no?: string;
}

export interface ScanResult {
  item_code: string | null;
  batch_no: string | null;
  qty: number;
  label_name?: string;
  source?: string;
}

export function calculateMaxAllowed(deficitQty: number): number {
  const base = Number(deficitQty) || 0;
  return Math.max(base * 1.15, base + 1.0);
}

export function isOverTolerance(
  pickedQty: number,
  deficitQty: number
): boolean {
  const picked = Number(pickedQty) || 0;
  return picked > calculateMaxAllowed(deficitQty);
}
