import type {
  ConfirmationWorkOrderGroup,
  ManagementConfirmationRow,
  OperationCompletionRow,
  OperationCompletionWorkOrderGroup,
} from "../types";

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

export function getConfirmationTimestamp(row: ManagementConfirmationRow): string {
  return row.creation || [row.posting_date, row.posting_time].filter(Boolean).join(" ") || "";
}

export function getConfirmedByLabel(row: ManagementConfirmationRow): string {
  return row.confirmed_by_name || (row.confirmed_by || "").split("@")[0] || "";
}

export function groupConfirmationsByWorkOrder(
  rows: ManagementConfirmationRow[]
): ConfirmationWorkOrderGroup[] {
  const byWo = new Map<string, ManagementConfirmationRow[]>();
  for (const row of rows) {
    const existing = byWo.get(row.work_order);
    if (existing) existing.push(row);
    else byWo.set(row.work_order, [row]);
  }

  const groups: ConfirmationWorkOrderGroup[] = [];
  for (const [wo, list] of byWo.entries()) {
    const first = list[0];
    let activeCount = 0;
    let cancelledCount = 0;
    let totalYield = 0;
    let latestAt = "";
    let lastPostingDate = "";
    let lastPostingTime = "";
    let lastConfirmedBy = "";

    for (const row of list) {
      if (row.docstatus === 1) activeCount += 1;
      else if (row.docstatus === 2) cancelledCount += 1;
      totalYield += Number(row.yield_qty) || 0;

      const ts = getConfirmationTimestamp(row);
      const by = getConfirmedByLabel(row);
      if (ts && (!latestAt || ts > latestAt || (ts === latestAt && !lastConfirmedBy && by))) {
        latestAt = ts;
        lastPostingDate = row.posting_date || "";
        lastPostingTime = row.posting_time || "";
        lastConfirmedBy = by;
      }
    }

    groups.push({
      work_order: wo,
      production_item: first.production_item,
      item_name: first.item_name || list.find((x) => x.item_name)?.item_name || "",
      stock_uom: first.stock_uom || list.find((x) => x.stock_uom)?.stock_uom || "",
      wo_status: first.wo_status || list.find((x) => x.wo_status)?.wo_status || "",
      confirmations: list,
      active_count: activeCount,
      cancelled_count: cancelledCount,
      total_yield_qty: totalYield,
      last_confirmation_at: latestAt,
      last_posting_date: lastPostingDate,
      last_posting_time: lastPostingTime,
      last_confirmed_by: lastConfirmedBy,
    });
  }
  return groups;
}
