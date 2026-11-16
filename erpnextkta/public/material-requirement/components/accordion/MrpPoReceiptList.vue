<template>
  <div
    v-if="(allSupplies && allSupplies.length > 0) || selectedWeek"
    :class="['mrp-po-container', { 'is-flush': flush }]"
  >
    <!-- Sub Header if week is selected or multiple weeks exist -->
    <div v-if="!flush" class="mrp-po-header">
      <div class="d-flex align-items-center gap-2">
        <i class="fa fa-truck text-info"></i>
        <span class="mrp-po-title">{{ __("Açık Siparişler ve Teslimatlar") }}</span>
        <span v-if="selectedWeek" class="mrp-badge-week">
          {{ formatWeek(selectedWeek) }}
        </span>
      </div>
      <button
        v-if="selectedWeek"
        type="button"
        class="btn btn-xs btn-link text-muted p-0"
        :title="__('Filtreyi Temizle')"
        @click="selectWeek(null)"
      >
        <i class="fa fa-times mr-1"></i>{{ __("Tümü") }}
      </button>
    </div>

    <!-- Empty State for Selected Week -->
    <div
      v-if="displaySupplies.length === 0"
      class="mrp-po-empty py-3 px-3 text-center text-muted small"
    >
      <i class="fa fa-info-circle mr-1 text-info"></i>
      <span v-if="selectedWeek">
        {{ __("{0} haftasında bekleyen açık teslimat veya sipariş bulunmamaktadır.", [formatWeek(selectedWeek)]) }}
      </span>
      <span v-else>
        {{ __("Bekleyen açık sipariş veya teslimat bulunmamaktadır.") }}
      </span>
      <button
        v-if="selectedWeek && allSupplies.length > 0"
        type="button"
        class="btn btn-link btn-xs ml-2 font-weight-bold"
        @click="selectWeek(null)"
      >
        {{ __("Tüm açık siparişleri göster") }}
      </button>
    </div>

    <!-- Modern Supply Cards List -->
    <div v-else class="mrp-supply-cards-list">
      <div
        v-for="(item, idx) in displaySupplies"
        :key="`${item.type}-${item.name}-${item.week || ''}-${idx}`"
        :class="['mrp-supply-card', { 'is-dispute-card': isDispute(item) }]"
      >
        <!-- Left: Doc Link, Type, PO Link, Logistic Badge & Meta -->
        <div class="mrp-supply-main-info">
          <div class="mrp-supply-title-line">
            <span :class="['mrp-doc-type-badge', isPR(item) ? 'type-pr' : 'type-po']">
              {{ isPR(item) ? 'PR' : 'PO' }}
            </span>

            <a
              :href="getDocumentUrl(item)"
              target="_blank"
              class="mrp-doc-link"
              :title="__('Belgeyi Görüntüle')"
            >
              {{ item.name }}
            </a>

            <!-- Linked PO for PR docs -->
            <a
              v-if="isPR(item) && item.po_name"
              :href="`/app/purchase-order/${encodeURIComponent(item.po_name)}`"
              target="_blank"
              class="mrp-linked-po-badge"
              :title="__('Bağlı Satınalma Siparişi: {0}', [item.po_name])"
            >
              <i class="fa fa-link mr-1"></i>{{ item.po_name }}
            </a>

            <!-- Logistic Status Badge (Açık PO, Yolda, Gümrükte, Antrepoda, Uyuşmazlık) -->
            <span :class="['mrp-logistic-badge', getStatusBadgeClass(item.state)]">
              <i :class="['fa mr-1', getStatusIcon(item.state)]"></i>
              {{ getStatusLabel(item.state) }}
            </span>
          </div>

          <!-- Meta Line: Supplier, Date, Estimated Flag -->
          <div class="mrp-supply-meta-line">
            <span v-if="item.supplier" class="mrp-meta-item" :title="__('Tedarikçi')">
              <i class="fa fa-building-o mr-1 text-muted"></i>{{ item.supplier }}
            </span>

            <span class="mrp-meta-item" :title="__('Termin / Varış Tarihi')">
              <i class="fa fa-calendar-o mr-1 text-muted"></i>
              <span>{{ getDateLabel(item) }}:</span>
              <strong class="ml-1">{{ getItemDate(item) }}</strong>
              <span
                v-if="item.is_estimated"
                class="mrp-estimated-badge ml-1"
                :title="__('ETA girilmediği için tahmini hesaplanmıştır')"
              >
                {{ __("Tahmini") }}
              </span>
            </span>
          </div>

          <!-- Dispute Warning Box -->
          <div v-if="isDispute(item)" class="mrp-dispute-banner">
            <i class="fa fa-exclamation-triangle mr-1 text-danger"></i>
            <span class="font-weight-bold">{{ item.dispute_reason || __("Mal Kabul Uyuşmazlığı Bildirildi") }}</span>
            <span v-if="item.dispute_description" class="ml-1 text-muted">
              - {{ item.dispute_description }}
            </span>
          </div>
        </div>

        <!-- Right: Delivery Quantity Pill -->
        <div class="mrp-supply-qty-wrap">
          <span
            :class="[
              'mrp-supply-qty-pill',
              isDispute(item)
                ? 'qty-dispute'
                : isAntrepo(item)
                  ? 'qty-antrepo'
                  : 'qty-valid',
            ]"
          >
            +{{ formatQty(getItemQty(item)) }} {{ uom }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { OpenPOReceipt, OpenSupplyItem } from "../../types/mrp";

const __ = (...args: any[]) => (window as any).__(...args);

const props = withDefaults(
  defineProps<{
    pos?: (OpenPOReceipt | OpenSupplyItem)[];
    supplies?: OpenSupplyItem[];
    uom: string;
    selectedWeek?: string | null;
    flush?: boolean;
  }>(),
  {
    pos: () => [],
    supplies: () => [],
    uom: "",
    selectedWeek: null,
    flush: false,
  }
);

const emit = defineEmits<{
  (e: "selectWeek", week: string | null): void;
}>();

function selectWeek(week: string | null) {
  emit("selectWeek", week);
}

const allSupplies = computed<OpenSupplyItem[]>(() => {
  if (props.supplies && props.supplies.length > 0) return props.supplies;
  if (props.pos && props.pos.length > 0) {
    return props.pos.map((p) => {
      const isPrDoc = (p as any).type === "PR" || (p as any).name?.startsWith?.("PREC-");
      return {
        type: isPrDoc ? "PR" : "PO",
        name: (p as any).name || (p as any).po_name,
        po_name: (p as any).po_name,
        supplier: p.supplier,
        state: (p as any).state || "Açık Sipariş",
        qty: (p as any).qty ?? (p as any).pending_qty ?? 0,
        date: (p as any).date || (p as any).schedule_date || "",
        week: p.week,
        date_label: (p as any).date_label,
        is_estimated: (p as any).is_estimated,
        loading_date: (p as any).loading_date,
        eta_date: (p as any).eta_date,
        customs_date: (p as any).customs_date,
        clearance_start_date: (p as any).clearance_start_date,
        dispute_reason: (p as any).dispute_reason,
        dispute_description: (p as any).dispute_description,
      } as OpenSupplyItem;
    });
  }
  return [];
});

// Deliveries to display based on week filter (Antrepo items are also included in flat list)
const displaySupplies = computed<OpenSupplyItem[]>(() => {
  if (!props.selectedWeek) {
    return allSupplies.value;
  }
  return allSupplies.value.filter((s) => s.week === props.selectedWeek);
});

function isPR(item: any): boolean {
  return item.type === "PR" || item.name?.startsWith("PREC-");
}

function isAntrepo(item: any): boolean {
  const s = (item.state || "").toLowerCase();
  return s.includes("antrepo");
}

function isDispute(item: any): boolean {
  const st = (item.state || "").toLowerCase();
  return st.includes("uyuşmaz") || st.includes("uyusmaz");
}

function getDocumentUrl(item: any): string {
  if (isPR(item)) {
    return `/app/purchase-receipt/${encodeURIComponent(item.name)}`;
  }
  return `/app/purchase-order/${encodeURIComponent(item.name)}`;
}

function getStatusLabel(state?: string): string {
  const s = (state || "").toLowerCase();
  if (s.includes("uyuşmaz") || s.includes("uyusmaz")) return __("Uyuşmazlık");
  if (s.includes("antrepo")) return __("Antrepoda");
  if (s.includes("gümrük") || s.includes("gumruk")) return __("Gümrükte");
  if (s.includes("yol")) return __("Yolda");
  if (s.includes("giriş") || s.includes("giris")) return __("Mal Giriş");
  return __("Açık PO");
}

function getStatusIcon(state?: string): string {
  const s = (state || "").toLowerCase();
  if (s.includes("uyuşmaz") || s.includes("uyusmaz")) return "fa-ban";
  if (s.includes("antrepo")) return "fa-university";
  if (s.includes("gümrük") || s.includes("gumruk")) return "fa-hourglass-half";
  if (s.includes("yol")) return "fa-ship";
  if (s.includes("giriş") || s.includes("giris")) return "fa-check-circle";
  return "fa-file-text-o";
}

function getStatusBadgeClass(state?: string): string {
  const s = (state || "").toLowerCase();
  if (s.includes("uyuşmaz") || s.includes("uyusmaz")) return "mrp-badge-dispute";
  if (s.includes("antrepo")) return "mrp-badge-antrepo";
  if (s.includes("gümrük") || s.includes("gumruk")) return "mrp-badge-gumruk";
  if (s.includes("yol")) return "mrp-badge-yolda";
  if (s.includes("giriş") || s.includes("giris")) return "mrp-badge-giris";
  return "mrp-badge-po";
}

function getDateLabel(item: any): string {
  if (item.date_label) return __(item.date_label);
  if (isPR(item)) {
    return item.customs_date ? __("Gümrüğe Geliş") : __("Varış");
  }
  return __("Termin");
}

function getItemDate(item: any): string {
  return (
    item.date ||
    item.customs_date ||
    item.schedule_date ||
    item.loading_date ||
    "-"
  );
}

function getItemQty(item: any): number {
  if (item.qty !== undefined && item.qty !== null) return item.qty;
  return item.pending_qty || 0;
}

function formatQty(val: number): string {
  if (val === null || val === undefined) return "0";
  return Number(val).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}

function formatWeek(weekKey?: string | null): string {
  if (!weekKey) return "";
  try {
    const parts = weekKey.split("_w");
    return `${parts[0]}-W${parts[1]}`;
  } catch (e) {
    return weekKey;
  }
}
</script>

<style scoped>
.mrp-po-container { background: var(--mrp-card-bg, #ffffff); border: 1px solid var(--mrp-border, #e2e8f0); border-radius: 6px; padding: 10px 14px; }
.mrp-po-container.is-flush { background: transparent; border: none; border-radius: 0; padding: 0; }
.mrp-po-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.mrp-po-title { font-weight: 700; font-size: 11px; text-transform: uppercase; color: var(--mrp-text-muted, #64748b); }
.mrp-badge-week { font-size: 10px; font-weight: 700; background: rgba(37, 99, 235, 0.1); color: #2563eb; border: 1px solid rgba(37, 99, 235, 0.25); border-radius: 4px; padding: 1px 6px; }
.mrp-po-empty { background: var(--mrp-card-subtle, #f8fafc); border: 1px dashed var(--mrp-border, #cbd5e1); border-radius: 6px; margin: 10px 12px; }
.mrp-supply-cards-list { display: flex; flex-direction: column; }
.mrp-supply-card { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--mrp-border, #e2e8f0); background: var(--mrp-card-bg, #ffffff); gap: 12px; transition: background 0.15s ease; }
.mrp-supply-card:last-child { border-bottom: none; }
.mrp-supply-card:hover { background: var(--mrp-cell-hover, rgba(37, 99, 235, 0.04)); }
.mrp-supply-card.is-dispute-card { background: rgba(220, 38, 38, 0.03); border-left: 3px solid #dc2626; }
.mrp-supply-main-info { flex: 1; min-width: 0; }
.mrp-supply-title-line { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; }
.mrp-doc-type-badge { font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 3px; text-transform: uppercase; }
.mrp-doc-type-badge.type-pr { background: rgba(2, 132, 199, 0.12); color: #0284c7; border: 1px solid rgba(2, 132, 199, 0.3); }
.mrp-doc-type-badge.type-po { background: rgba(79, 70, 229, 0.12); color: #4f46e5; border: 1px solid rgba(79, 70, 229, 0.3); }
.mrp-doc-link { font-weight: 700; font-size: 12px; color: #2563eb; text-decoration: none; }
.mrp-doc-link:hover { text-decoration: underline; }
.mrp-linked-po-badge { font-size: 10px; color: var(--mrp-text-muted, #64748b); background: var(--mrp-card-subtle, #f1f5f9); border: 1px solid var(--mrp-border, #cbd5e1); border-radius: 4px; padding: 1px 5px; text-decoration: none; }
.mrp-linked-po-badge:hover { color: #2563eb; border-color: #93c5fd; }
.mrp-logistic-badge { font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 4px; }
.mrp-badge-po { color: #4338ca; background: #eef2ff; border: 1px solid rgba(67, 56, 202, 0.3); }
.mrp-badge-yolda { color: #b45309; background: #fef3c7; border: 1px solid rgba(180, 83, 9, 0.3); }
.mrp-badge-gumruk { color: #c2410c; background: #ffedd5; border: 1px solid rgba(194, 65, 12, 0.3); }
.mrp-badge-antrepo { color: #0369a1; background: #e0f2fe; border: 1px solid rgba(3, 105, 161, 0.3); }
.mrp-badge-dispute { color: #b91c1c; background: #fee2e2; border: 1px solid rgba(185, 28, 28, 0.3); }
.mrp-badge-giris { color: #15803d; background: #dcfce7; border: 1px solid rgba(21, 128, 61, 0.28); }
[data-theme="dark"] .mrp-badge-po { color: #a5b4fc; background: rgba(99, 102, 241, 0.2); border-color: rgba(165, 180, 252, 0.3); }
[data-theme="dark"] .mrp-badge-yolda { color: #fcd34d; background: rgba(245, 158, 11, 0.2); border-color: rgba(252, 211, 77, 0.3); }
[data-theme="dark"] .mrp-badge-gumruk { color: #fdba74; background: rgba(249, 115, 22, 0.2); border-color: rgba(253, 186, 116, 0.3); }
[data-theme="dark"] .mrp-badge-antrepo { color: #7dd3fc; background: rgba(14, 165, 233, 0.2); border-color: rgba(125, 211, 252, 0.3); }
[data-theme="dark"] .mrp-badge-dispute { color: #fca5a5; background: rgba(239, 68, 68, 0.25); border-color: rgba(252, 165, 165, 0.3); }
[data-theme="dark"] .mrp-badge-giris { color: #86efac; background: rgba(34, 197, 94, 0.2); border-color: rgba(134, 239, 172, 0.3); }
.mrp-supply-meta-line { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 3px; }
.mrp-meta-item { font-size: 10px; color: var(--mrp-text-muted, #64748b); }
.mrp-estimated-badge { font-size: 9px; background: rgba(245, 158, 11, 0.15); color: #d97706; border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 3px; padding: 0 4px; }
.mrp-dispute-banner { margin-top: 4px; font-size: 10px; color: #dc2626; background: rgba(220, 38, 38, 0.08); border: 1px solid rgba(220, 38, 38, 0.2); border-radius: 4px; padding: 3px 6px; }
.mrp-supply-qty-wrap { flex-shrink: 0; }
.mrp-supply-qty-pill { display: inline-block; font-size: 12px; font-weight: 700; border-radius: 9999px; padding: 3px 10px; white-space: nowrap; }
.mrp-supply-qty-pill.qty-valid { color: #2563eb; background: rgba(37, 99, 235, 0.1); border: 1px solid rgba(37, 99, 235, 0.25); }
.mrp-supply-qty-pill.qty-dispute { color: #dc2626; background: rgba(220, 38, 38, 0.1); border: 1px solid rgba(220, 38, 38, 0.25); }
.mrp-supply-qty-pill.qty-antrepo { color: #0284c7; background: rgba(2, 132, 199, 0.1); border: 1px solid rgba(2, 132, 199, 0.25); }
</style>
