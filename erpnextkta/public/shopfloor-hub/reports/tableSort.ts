export type SortDirection = "asc" | "desc";

export function toggleSortState<K extends string>(
  currentKey: K,
  currentDir: SortDirection,
  nextKey: K,
  defaultDir: SortDirection = "desc"
): { key: K; dir: SortDirection } {
  if (currentKey === nextKey) {
    return { key: nextKey, dir: currentDir === "asc" ? "desc" : "asc" };
  }
  return { key: nextKey, dir: defaultDir };
}

function isEmptySortVal(val: string | number | null | undefined): boolean {
  if (val === null || val === undefined) return true;
  if (typeof val === "number") return Number.isNaN(val);
  return val.trim() === "";
}

export function sortItems<T>(
  items: T[],
  accessor: (item: T) => string | number,
  dir: SortDirection,
  tieBreaker?: (item: T) => string
): T[] {
  return [...items].sort((a, b) => {
    const va = accessor(a);
    const vb = accessor(b);
    const emptyA = isEmptySortVal(va);
    const emptyB = isEmptySortVal(vb);

    if (emptyA && emptyB) {
      return tieBreaker
        ? tieBreaker(a).localeCompare(tieBreaker(b), undefined, { numeric: true, sensitivity: "base" })
        : 0;
    }
    if (emptyA) return 1;
    if (emptyB) return -1;

    let cmp: number;
    if (typeof va === "number" && typeof vb === "number") {
      cmp = va - vb;
    } else {
      cmp = String(va).localeCompare(String(vb), undefined, { numeric: true, sensitivity: "base" });
    }

    const directed = dir === "asc" ? cmp : -cmp;
    if (directed !== 0) return directed;
    return tieBreaker
      ? tieBreaker(a).localeCompare(tieBreaker(b), undefined, { numeric: true, sensitivity: "base" })
      : 0;
  });
}
