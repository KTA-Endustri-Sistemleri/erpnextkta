import type { OperationCompletionRow, OperationCompletionWorkOrderGroup } from "../types";

export function opRowKey(row: OperationCompletionRow): string {
  return `${row.work_order}::${row.operation}`;
}

export function getWoQty(row: OperationCompletionRow): number {
  return Number(row.qty ?? row.wo_qty ?? 0) || 0;
}

export function getConfirmedQty(row: OperationCompletionRow): number {
  return Number(row.confirmed_qty ?? row.co11n_qty ?? 0) || 0;
}

export function getCompletionPct(row: OperationCompletionRow): number {
  return Number(row.completion_pct ?? row.completion_percent ?? 0) || 0;
}

export function isOpCompleted(row: OperationCompletionRow): boolean {
  return typeof row.is_completed === "boolean"
    ? row.is_completed
    : row.status === "completed";
}

export function hasFinalConfirmation(row: OperationCompletionRow): boolean {
  return Number(row.final_confirmation_count ?? row.has_final_confirmation ?? 0) > 0;
}

export function getLastConfirmedAt(row: OperationCompletionRow): string {
  return (
    row.last_confirmation_at ||
    [row.last_posting_date, row.last_posting_time].filter(Boolean).join(" ") ||
    ""
  );
}

export function formatQty(val: number): string {
  const n = Number(val) || 0;
  return Number.isInteger(n) ? String(n) : n.toFixed(2).replace(/\.?0+$/, "");
}

export function formatTimestamp(val: string): string {
  return val ? val.slice(0, 16) : "—";
}

export function groupRowsByWorkOrder(
  rows: OperationCompletionRow[]
): OperationCompletionWorkOrderGroup[] {
  const byWo = new Map<string, OperationCompletionRow[]>();
  for (const row of rows) {
    const existing = byWo.get(row.work_order);
    if (existing) existing.push(row);
    else byWo.set(row.work_order, [row]);
  }

  const groups: OperationCompletionWorkOrderGroup[] = [];
  for (const [wo, ops] of byWo.entries()) {
    const sortedOps = [...ops].sort((a, b) => {
      const seqDiff = (Number(a.sequence_id) || 0) - (Number(b.sequence_id) || 0);
      return seqDiff !== 0 ? seqDiff : (a.operation || "").localeCompare(b.operation || "");
    });
    const first = sortedOps[0];
    let completedCount = 0;
    let partialCount = 0;
    let unconfirmedCount = 0;
    let pctSum = 0;
    let latestAt = "";
    let latestBy = "";
    let hasShortage = 0;

    for (const op of sortedOps) {
      if (op.status === "completed" || isOpCompleted(op)) completedCount += 1;
      else if (op.status === "unconfirmed") unconfirmedCount += 1;
      else partialCount += 1;

      pctSum += getCompletionPct(op);
      if (op.custom_released_with_shortage) hasShortage = 1;

      const opAt = getLastConfirmedAt(op);
      if (opAt && (!latestAt || opAt > latestAt || (opAt === latestAt && !latestBy && op.last_confirmed_by))) {
        latestAt = opAt;
        latestBy = op.last_confirmed_by || "";
      }
    }

    groups.push({
      work_order: wo,
      wo_status: first.wo_status || "",
      custom_released_with_shortage: hasShortage,
      production_item: first.production_item,
      item_name: first.item_name || "",
      stock_uom: first.stock_uom || "",
      qty: getWoQty(first),
      operations: sortedOps,
      completed_count: completedCount,
      partial_count: partialCount,
      unconfirmed_count: unconfirmedCount,
      overall_pct: sortedOps.length > 0 ? Math.round((pctSum / sortedOps.length) * 10) / 10 : 0,
      wo_creation: first.wo_creation || sortedOps.find((o) => o.wo_creation)?.wo_creation || "",
      last_confirmation_at: latestAt,
      last_confirmed_by: latestBy,
    });
  }
  return groups;
}
