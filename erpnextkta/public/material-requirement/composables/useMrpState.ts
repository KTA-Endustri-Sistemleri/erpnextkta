import { ref, reactive, computed } from "vue";
import type {
  WeekBucket,
  MaterialItem,
  MrpFilterState,
  MrpSummary,
  MrpSettings,
  MrpNettingDialogData,
  StatusFilterType,
  WeeklyViewType,
  GroupByType,
} from "../types/mrp";

const __ = (...args: any[]) => (window as any).__(...args);

export function getPlanningHorizonDays(): number {
  const bootDays = (window as any).frappe?.boot?.kta_mrp_settings
    ?.planning_horizon_days;
  if (bootDays) return Number(bootDays);
  const utilDays = (
    window as any
  ).kta?.report_utils?.get_planning_horizon_days?.();
  if (utilDays) return Number(utilDays);
  return 180;
}

export function computeDefaultToDate(
  fromDate?: string,
  horizonDays?: number
): string {
  const days = horizonDays || getPlanningHorizonDays();
  if ((window as any).kta?.report_utils?.get_default_to_date && !horizonDays) {
    return (window as any).kta.report_utils.get_default_to_date(fromDate);
  }
  const f = (window as any).frappe?.datetime;
  const today = f?.get_today?.() || new Date().toISOString().split("T")[0];
  const start = fromDate || today;
  const base = start > today ? start : today;
  if (f?.add_days) {
    return f.add_days(base, days);
  }
  const d = new Date(base);
  d.setDate(d.getDate() + days);
  return d.toISOString().split("T")[0];
}

export function getMondayOfCurrentWeek(): string {
  if ((window as any).moment) {
    return (window as any).moment().startOf("isoWeek").format("YYYY-MM-DD");
  }
  const now = new Date();
  const day = now.getDay();
  const diff = now.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(now.setDate(diff));
  const y = monday.getFullYear();
  const m = String(monday.getMonth() + 1).padStart(2, "0");
  const d = String(monday.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

const initialHorizon = getPlanningHorizonDays();
const initialFromDate = getMondayOfCurrentWeek();
const initialToDate = computeDefaultToDate(initialFromDate, initialHorizon);

const isCustomToDate = ref(false);

// Shared Module-level Singleton State
const filters = reactive<MrpFilterState>({
  from_date: initialFromDate,
  to_date: initialToDate,
  weekly_view: "Önerilen Sipariş",
  group_by: "Bitmiş Ürün + Hammadde",
  only_shortages: false,
  supplier: "",
  hammadde: "",
  custom_musteri_grubu: "",
  item_group: "",
  search_query: "",
  status_filter: "all",
});

const weeks = ref<WeekBucket[]>([]);
const materials = ref<MaterialItem[]>([]);
const summary = ref<MrpSummary>({
  total_items: 0,
  shortage_count: 0,
  urgent_count: 0,
  po_count: 0,
  antrepo_count: 0,
  yolda_count: 0,
  sufficient_count: 0,
  order_amount_by_currency: {},
});
const settings = ref<MrpSettings>({
  urgent_weeks: 4,
  default_include_po: 1,
  planning_horizon_days: initialHorizon,
});

const loading = ref(false);
const error = ref<string | null>(null);
const expandedRows = reactive(new Set<string>());
const activeWeekFilter = reactive<Record<string, string | null>>({});

// Modal state
const nettingModalOpen = ref(false);
const nettingModalLoading = ref(false);
const nettingModalData = ref<MrpNettingDialogData | null>(null);

// Print layout state
const printLayoutActive = ref(false);

// Sorting State
export type SortPresetType = "urgent" | "amount_desc" | "net_desc" | "code_asc";
const sortBy = ref<string | null>(null);
const sortOrder = ref<"asc" | "desc">("desc");
const sortPreset = ref<SortPresetType>("urgent");

function setSortColumn(colKey: string) {
  if (sortBy.value === colKey) {
    if (sortOrder.value === "desc") {
      sortOrder.value = "asc";
    } else {
      sortBy.value = null;
      sortOrder.value = "desc";
    }
  } else {
    sortBy.value = colKey;
    sortOrder.value = colKey === "item_code" ? "asc" : "desc";
  }
}

function setSortPreset(preset: SortPresetType) {
  sortPreset.value = preset;
  sortBy.value = null;
}

function resetSort() {
  sortBy.value = null;
  sortOrder.value = "desc";
  sortPreset.value = "urgent";
}

const activeSortLabel = computed(() => {
  if (!sortBy.value) return "";
  const weekMatch = weeks.value.find((w) => w.key === sortBy.value);
  if (weekMatch) {
    return `${weekMatch.label} (${
      sortOrder.value === "asc" ? __("Artan") : __("Azalan")
    })`;
  }
  const labelMap: Record<string, string> = {
    item_code: __("Hammadde Kodu"),
    order_amount: __("Sipariş Tutarı"),
    net_total: __("Net Eksik"),
    free_stock: __("Serbest Stok"),
    coverage_weeks: __("Kapsama Haftası"),
  };
  return `${labelMap[sortBy.value] || sortBy.value} (${
    sortOrder.value === "asc" ? __("Artan") : __("Azalan")
  })`;
});

// Filtered materials computation (instant in-memory filtering & sorting: 0.1 ms)
const filteredMaterials = computed(() => {
  const query = filters.search_query.trim().toLowerCase();
  const status = filters.status_filter;
  const onlyShortages = filters.only_shortages;

  const list = materials.value.filter((m) => {
    // Only shortages checkbox
    if (onlyShortages && !m.is_shortage) {
      return false;
    }

    // Status chip filter
    if (status === "urgent" && !m.is_urgent) return false;
    if (status === "shortages" && !m.is_shortage) return false;
    if (
      status === "antrepoda" &&
      (!m.antrepoda_total || m.antrepoda_total <= 0)
    )
      return false;
    if (
      status === "gumruklemede" &&
      (!m.gumruklemede_total || m.gumruklemede_total <= 0)
    )
      return false;
    if (status === "yolda" && (!m.yolda_total || m.yolda_total <= 0))
      return false;
    if (
      status === "uyusmazlikta" &&
      (!m.uyusmazlikta_total || m.uyusmazlikta_total <= 0)
    )
      return false;
    if (status === "has_po" && !m.has_po) return false;
    if (status === "sufficient" && m.is_shortage) return false;

    // Search query filter
    if (query) {
      const match =
        m.item_code.toLowerCase().includes(query) ||
        m.item_name.toLowerCase().includes(query) ||
        m.supplier.toLowerCase().includes(query);
      if (!match) return false;
    }

    return true;
  });

  // Dynamic Column Sorting
  if (sortBy.value) {
    const col = sortBy.value;
    const isAsc = sortOrder.value === "asc";
    const dir = isAsc ? 1 : -1;
    const view = filters.weekly_view;
    const viewFieldMap: Record<
      string,
      "order" | "net" | "gross" | "projected"
    > = {
      "Önerilen Sipariş": "order",
      "Net İhtiyaç": "net",
      "Brüt İhtiyaç": "gross",
      "Projeksiyon Bakiye": "projected",
    };
    const metricKey = viewFieldMap[view] || "order";

    return [...list].sort((a, b) => {
      // 1. If sorting by a week column (e.g. 2026_w46)
      if (a.weeks && a.weeks[col] !== undefined) {
        const valA = a.weeks[col]?.[metricKey] || 0;
        const valB = b.weeks[col]?.[metricKey] || 0;
        if (valA !== valB) return (valA - valB) * dir;
      }
      // 2. Named properties
      else if (col === "item_code") {
        return a.item_code.localeCompare(b.item_code) * dir;
      } else if (col === "order_amount") {
        return (a.order_amount - b.order_amount) * dir;
      } else if (col === "net_total") {
        return (a.net_total - b.net_total) * dir;
      } else if (col === "free_stock") {
        return (a.free_stock - b.free_stock) * dir;
      } else if (col === "coverage_weeks") {
        const covA = a.coverage_weeks ?? 999;
        const covB = b.coverage_weeks ?? 999;
        return (covA - covB) * dir;
      }
      return 0;
    });
  }

  // Preset Sorting
  if (sortPreset.value === "amount_desc") {
    return [...list].sort((a, b) => b.order_amount - a.order_amount);
  }
  if (sortPreset.value === "net_desc") {
    return [...list].sort((a, b) => b.net_total - a.net_total);
  }
  if (sortPreset.value === "code_asc") {
    return [...list].sort((a, b) => a.item_code.localeCompare(b.item_code));
  }

  // Default "urgent": Keep backend prioritization (Shortage tier -> Coverage weeks -> Order amount -> Net total -> Code)
  return list;
});

async function fetchMrpData() {
  loading.value = true;
  error.value = null;

  try {
    const res = await (window as any).frappe.call({
      method:
        "erpnextkta.kta_mrp.mrp_engine.service.get_material_requirements_data",
      args: {
        filters: JSON.stringify({
          from_date: filters.from_date,
          to_date: filters.to_date,
          supplier: filters.supplier || undefined,
          hammadde: filters.hammadde || undefined,
          custom_musteri_grubu: filters.custom_musteri_grubu || undefined,
          item_group: filters.item_group || undefined,
          group_by: filters.group_by,
        }),
      },
    });

    if (res && res.message) {
      const d = res.message;
      weeks.value = d.weeks || [];
      materials.value = d.materials || [];
      summary.value = d.summary || {
        total_items: 0,
        shortage_count: 0,
        urgent_count: 0,
        po_count: 0,
        antrepo_count: 0,
        gumruk_count: 0,
        yolda_count: 0,
        sufficient_count: 0,
        order_amount_by_currency: {},
      };
      if (d.settings) {
        settings.value = d.settings;
        if (d.settings.planning_horizon_days && !isCustomToDate.value) {
          const expectedTo = computeDefaultToDate(
            filters.from_date,
            d.settings.planning_horizon_days
          );
          if (filters.to_date !== expectedTo) {
            filters.to_date = expectedTo;
          }
        }
      }
    }
  } catch (err: any) {
    console.error("MRP Data Fetch Error:", err);
    error.value = err?.message || __("Veriler yüklenirken bir hata oluştu.");
  } finally {
    loading.value = false;
  }
}

async function initMrpSettings() {
  let horizon = getPlanningHorizonDays();
  try {
    if ((window as any).frappe?.db?.get_single_value) {
      const days = await (window as any).frappe.db.get_single_value(
        "KTA MRP Settings",
        "planning_horizon_days"
      );
      if (days) {
        horizon = Number(days);
        if ((window as any).frappe?.boot) {
          (window as any).frappe.boot.kta_mrp_settings =
            (window as any).frappe.boot.kta_mrp_settings || {};
          (window as any).frappe.boot.kta_mrp_settings.planning_horizon_days =
            horizon;
        }
      }
    }
  } catch (e) {
    // Keep fallback
  }

  settings.value.planning_horizon_days = horizon;
  if (!isCustomToDate.value) {
    filters.to_date = computeDefaultToDate(filters.from_date, horizon);
  }
}

function handleFromDateChange() {
  if (!isCustomToDate.value) {
    filters.to_date = computeDefaultToDate(
      filters.from_date,
      settings.value.planning_horizon_days
    );
  }
  fetchMrpData();
}

function handleToDateChange() {
  isCustomToDate.value = true;
  fetchMrpData();
}

function resetToHorizon() {
  isCustomToDate.value = false;
  filters.from_date = getMondayOfCurrentWeek();
  filters.to_date = computeDefaultToDate(
    filters.from_date,
    settings.value.planning_horizon_days
  );
  fetchMrpData();
}

async function openNettingModal(itemCode: string, week: string) {
  const weekCol = weeks.value.find((w) => w.key === week);
  const mat = materials.value.find((m) => m.item_code === itemCode);

  nettingModalOpen.value = true;
  nettingModalLoading.value = true;

  // Optimistic preview from local in-memory data
  if (mat && mat.weeks && mat.weeks[week]) {
    const cell = mat.weeks[week];
    nettingModalData.value = {
      item_code: mat.item_code,
      item_name: mat.item_name,
      uom: mat.uom,
      supplier: mat.supplier,
      moq: mat.moq,
      pack: mat.pack,
      lead_time: mat.lead_time_days,
      actual: mat.actual_stock,
      reserved: mat.reserved_stock,
      free_stock: mat.free_stock,
      week: week,
      week_label: weekCol?.label || week,
      balance_before: mat.free_stock,
      gross: cell.gross,
      receipts: cell.po,
      net: cell.net,
      order: cell.order,
      projected: cell.projected,
      include_po: 1,
      pos: [],
      demands: [],
    };
  }

  try {
    const res = await (window as any).frappe.call({
      method: "erpnextkta.kta_mrp.mrp_engine.service.get_week_netting_details",
      args: {
        item_code: itemCode,
        week: week,
        from_date: filters.from_date,
        to_date: filters.to_date,
        include_po: 1,
      },
    });

    if (res && res.message && !res.message.error) {
      nettingModalData.value = res.message;
    }
  } catch (e) {
    console.error("Netting modal fetch error", e);
  } finally {
    nettingModalLoading.value = false;
  }
}

function closeNettingModal() {
  nettingModalOpen.value = false;
  nettingModalData.value = null;
}

function toggleRow(itemCode: string) {
  if (expandedRows.has(itemCode)) {
    expandedRows.delete(itemCode);
    activeWeekFilter[itemCode] = null;
  } else {
    expandedRows.add(itemCode);
  }
}

function isRowExpanded(itemCode: string): boolean {
  return expandedRows.has(itemCode);
}

function expandAllRows() {
  filteredMaterials.value.forEach((m) => expandedRows.add(m.item_code));
}

function collapseAllRows() {
  expandedRows.clear();
  Object.keys(activeWeekFilter).forEach((k) => delete activeWeekFilter[k]);
}

function focusWeekForMaterial(itemCode: string, weekKey: string) {
  expandedRows.add(itemCode);
  // Toggle if clicking same week, otherwise select
  if (activeWeekFilter[itemCode] === weekKey) {
    activeWeekFilter[itemCode] = null;
  } else {
    activeWeekFilter[itemCode] = weekKey;
  }
}

function clearWeekFilter(itemCode: string) {
  activeWeekFilter[itemCode] = null;
}

function setWeekFilter(itemCode: string, weekKey: string | null) {
  activeWeekFilter[itemCode] = weekKey;
}

function setStatusFilter(status: StatusFilterType) {
  filters.status_filter = status;
}

function setWeeklyView(view: WeeklyViewType) {
  filters.weekly_view = view;
}

function setGroupBy(group: GroupByType) {
  filters.group_by = group;
  fetchMrpData();
}

export function useMrpState() {
  return {
    filters,
    weeks,
    materials,
    summary,
    settings,
    loading,
    error,
    expandedRows,
    activeWeekFilter,
    focusWeekForMaterial,
    clearWeekFilter,
    setWeekFilter,
    filteredMaterials,
    nettingModalOpen,
    nettingModalLoading,
    nettingModalData,
    printLayoutActive,
    isCustomToDate,
    initMrpSettings,
    handleFromDateChange,
    handleToDateChange,
    resetToHorizon,
    computeDefaultToDate,
    fetchMrpData,
    openNettingModal,
    closeNettingModal,
    sortBy,
    sortOrder,
    sortPreset,
    activeSortLabel,
    setSortColumn,
    setSortPreset,
    resetSort,
    toggleRow,
    isRowExpanded,
    expandAllRows,
    collapseAllRows,
    setStatusFilter,
    setWeeklyView,
    setGroupBy,
  };
}
