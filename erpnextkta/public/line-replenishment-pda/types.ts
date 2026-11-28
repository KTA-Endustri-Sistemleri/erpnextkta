// Copyright (c) 2026, KTA and Contributors
// See license.txt

export interface ReplenishmentOrder {
  name: string;
  target_warehouse: string;
  status: string;
  company?: string;
  total_deficit_qty?: number;
  creation?: string;
  can_skip_items?: boolean;
  skipped_count?: number;
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
  has_batch_no?: number | boolean;
  is_skipped?: number | boolean;
  skipped_by?: string | null;
  is_fifo_override?: number | boolean;
  suggested_source_warehouse?: string;
  suggested_batch_no?: string;
  picked_source_warehouse?: string;
  picked_batch_no?: string;
}

export interface ScanResult {
  item_code: string | null;
  batch_no: string | null;
  qty: number;
  warehouse?: string | null;
  available_balances?: Array<{ warehouse: string; qty: number }>;
  already_in_target?: boolean;
  batch_disabled?: boolean;
  has_batch_no?: number | boolean;
  label_name?: string;
  source?: string;
}

export interface FifoOverrideCandidate {
  row: PickingItem;
  resolved: ScanResult;
}

export function compareShelfNames(
  a?: string | null,
  b?: string | null
): number {
  const cleanA = (a || "").trim();
  const cleanB = (b || "").trim();

  if (!cleanA && !cleanB) return 0;
  if (!cleanA) return 1;
  if (!cleanB) return -1;

  const partsA = cleanA.split(/(\d+)/).filter(Boolean);
  const partsB = cleanB.split(/(\d+)/).filter(Boolean);
  const len = Math.min(partsA.length, partsB.length);

  for (let i = 0; i < len; i++) {
    const partA = partsA[i];
    const partB = partsB[i];
    const isNumA = /^\d+$/.test(partA);
    const isNumB = /^\d+$/.test(partB);

    if (isNumA && isNumB) {
      const diff = Number(partA) - Number(partB);
      if (diff !== 0) return diff;
    } else if (isNumA !== isNumB) {
      return isNumA ? -1 : 1;
    } else {
      const lowA = partA.toLowerCase();
      const lowB = partB.toLowerCase();
      if (lowA < lowB) return -1;
      if (lowA > lowB) return 1;
    }
  }

  return partsA.length - partsB.length;
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
