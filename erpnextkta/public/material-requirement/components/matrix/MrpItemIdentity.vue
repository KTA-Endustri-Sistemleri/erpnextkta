<template>
  <div class="mrp-item-identity">
    <button
      type="button"
      class="mrp-chevron-btn"
      :title="__('Detayı Aç / Kapat')"
      @click="toggleRow(material.item_code)"
    >
      <i :class="['fa', isExpanded ? 'fa-chevron-down' : 'fa-chevron-right']"></i>
    </button>

    <div class="mrp-item-text">
      <div class="mrp-item-title-row">
        <a
          :href="`/app/item/${encodeURIComponent(material.item_code)}`"
          class="mrp-item-code-link"
          target="_blank"
        >
          {{ material.item_code }}
        </a>

        <!-- Coverage or Shortage Badge -->
        <span
          v-if="material.first_shortage_week"
          :class="['mrp-badge', material.is_urgent ? 'mrp-badge-urgent' : 'mrp-badge-shortage']"
          :title="__('İlk Eksik Hafta')"
        >
          <i class="fa fa-exclamation-triangle mr-1"></i>
          {{ material.first_shortage_week }}
        </span>
      </div>

      <div class="mrp-item-name" :title="material.item_name">
        {{ material.item_name || "-" }}
      </div>

      <!-- Row 1: Primary Meta: Supplier / Quota, Free Stock, Order Amount -->
      <div class="mrp-item-meta-primary">
        <!-- Sourcing Strategy & Quota Badges -->
        <span
          v-if="isQuotaStrategy"
          class="mrp-tag mrp-tag-quota"
          :title="__('Kotalı Satınalma Dağılımı')"
        >
          <i class="fa fa-pie-chart mr-1"></i>{{ quotaSummary }}
        </span>
        <span
          v-else-if="material.sourcing_strategy && material.sourcing_strategy !== 'Varsayılan Tedarikçi (%100)'"
          class="mrp-tag mrp-tag-strategy"
          :title="__('Tedarik Stratejisi')"
        >
          <i class="fa fa-sliders mr-1"></i>{{ __(material.sourcing_strategy) }}
        </span>
        <span v-else-if="material.supplier" class="mrp-tag mrp-tag-supplier" :title="__('Varsayılan Tedarikçi')">
          <i class="fa fa-building-o mr-1"></i>{{ material.supplier }}
        </span>

        <!-- Free Stock -->
        <span class="mrp-tag mrp-tag-stock" :title="__('Serbest Stok')">
          <i class="fa fa-cubes mr-1"></i>{{ formatQty(material.free_stock) }} {{ material.uom }}
        </span>

        <!-- Order Amount -->
        <span v-if="material.order_amount > 0" class="mrp-tag mrp-tag-amount" :title="__('Önerilen Sipariş Tutarı')">
          <i class="fa fa-money mr-1"></i>{{ formatMoney(material.order_amount, material.currency) }}
        </span>
      </div>

      <!-- Row 2: Supply Pipeline (Chronological Progression: PO -> Yolda -> Antrepo -> Gümrükte) -->
      <div v-if="hasPipelineSupplies" class="mrp-item-pipeline">
        <span class="mrp-pipeline-label" :title="__('Tedarik Boru Hattı (Geliş Aşamaları)')">
          <i class="fa fa-random mr-1"></i>{{ __("Tedarik") }}:
        </span>

        <!-- 1. PO: Henüz Sevk Edilmemiş Açık PO -->
        <span
          v-if="material.po_kalan_total && material.po_kalan_total > 0"
          class="mrp-tag mrp-tag-po"
          :title="__('Henüz Sevk Edilmemiş Açık PO')"
        >
          <i class="fa fa-file-text-o mr-1"></i>{{ __("PO") }}: {{ formatQty(material.po_kalan_total) }}
        </span>

        <!-- 2. Yolda: Sevkiyatta / Yolda Olan Açık Teslimat -->
        <span
          v-if="material.yolda_total && material.yolda_total > 0"
          class="mrp-tag mrp-tag-yolda"
          :title="__('Sevkiyatta / Yolda Olan Açık Teslimat')"
        >
          <i class="fa fa-ship mr-1"></i>{{ __("Yolda") }}: {{ formatQty(material.yolda_total) }}
        </span>

        <!-- 3. Antrepo: Gümrüklü Antrepoda Bekleyen (Bekleme Havuzu) -->
        <span
          v-if="material.antrepoda_total && material.antrepoda_total > 0"
          class="mrp-tag mrp-tag-antrepo"
          :title="__('Gümrüklü Antrepoda Bekleyen Açık Teslimat (Bekleme Havuzu)')"
        >
          <i class="fa fa-university mr-1"></i>{{ __("Antrepo") }}: {{ formatQty(material.antrepoda_total) }}
        </span>

        <!-- 4. Gümrükte: Gümrükleme / Çekim İşlemi Başlatılmış (+2 Gün) -->
        <span
          v-if="material.gumruklemede_total && material.gumruklemede_total > 0"
          class="mrp-tag mrp-tag-gumruk"
          :title="__('Gümrükleme / Çekim İşlemi Başlatılmış Açık Teslimat (+2 Gün)')"
        >
          <i class="fa fa-hourglass-half mr-1"></i>{{ __("Gümrükte") }}: {{ formatQty(material.gumruklemede_total) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { MaterialItem } from "../../types/mrp";
import { useMrpState } from "../../composables/useMrpState";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  material: MaterialItem;
}>();

const { isRowExpanded, toggleRow } = useMrpState();

const isExpanded = computed(() => isRowExpanded(props.material.item_code));

const isQuotaStrategy = computed(() => {
  const strat = props.material.sourcing_strategy || "";
  return (
    strat.includes("Kotalı") &&
    Array.isArray(props.material.suppliers_quota) &&
    props.material.suppliers_quota.length > 1
  );
});

const hasPipelineSupplies = computed(() => {
  const m = props.material;
  return Boolean(
    (m.po_kalan_total && m.po_kalan_total > 0) ||
    (m.yolda_total && m.yolda_total > 0) ||
    (m.antrepoda_total && m.antrepoda_total > 0) ||
    (m.gumruklemede_total && m.gumruklemede_total > 0)
  );
});

const quotaSummary = computed(() => {
  if (!props.material.suppliers_quota) return "";
  return props.material.suppliers_quota
    .map((s) => {
      const name = (s.supplier || "").split(" ")[0];
      return `${name} %${Math.round(s.quota_share || 0)}`;
    })
    .join(" | ");
});

function formatQty(val: number): string {
  if (val === null || val === undefined) return "0";
  return Number(val).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}

function formatMoney(val: number, currency: string): string {
  if (!val) return "0";
  const formatted = Number(val).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return currency ? `${formatted} ${currency}` : formatted;
}
</script>

<style scoped>
.mrp-item-identity {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.mrp-chevron-btn {
  background: transparent;
  border: 1px solid var(--border-color, #cbd5e1);
  color: var(--text-muted, #64748b);
  border-radius: 4px;
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  margin-top: 2px;
  transition: all 0.15s ease;
}

.mrp-chevron-btn:hover {
  background: var(--bg-light-gray, #f1f5f9);
  color: #2563eb;
  border-color: #2563eb;
}

.mrp-item-text {
  flex: 1;
  min-width: 0;
}

.mrp-item-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.mrp-item-code-link {
  font-weight: 700;
  font-size: 13px;
  color: #2563eb;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mrp-item-code-link:hover {
  text-decoration: underline;
}

.mrp-item-name {
  font-size: 11px;
  color: var(--text-color, #334155);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}

.mrp-item-meta-primary {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 5px;
}

.mrp-item-pipeline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  padding-top: 4px;
  border-top: 1px dashed #e2e8f0;
}

.mrp-pipeline-label {
  font-size: 9.5px;
  font-weight: 700;
  text-transform: uppercase;
  color: #64748b;
  margin-right: 2px;
}

.mrp-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--bg-light-gray, #f1f5f9);
  color: var(--text-muted, #475569);
  border: 1px solid var(--border-color, #e2e8f0);
}

.mrp-tag-stock {
  font-weight: 600;
  color: #0369a1;
  background: #f0f9ff;
  border-color: #bae6fd;
}

.mrp-tag-amount {
  font-weight: 600;
  color: #15803d;
  background: #f0fdf4;
  border-color: #bbf7d0;
}

.mrp-tag-antrepo {
  font-weight: 600;
  color: #0284c7;
  background: #e0f2fe;
  border-color: #7dd3fc;
}

.mrp-tag-gumruk {
  font-weight: 600;
  color: #c2410c;
  background: #fff7ed;
  border-color: #fed7aa;
}

.mrp-tag-yolda {
  font-weight: 600;
  color: #d97706;
  background: #fef3c7;
  border-color: #fde68a;
}

.mrp-tag-po {
  font-weight: 600;
  color: #4f46e5;
  background: #eef2ff;
  border-color: #c7d2fe;
}

.mrp-tag-quota {
  font-weight: 600;
  color: #7e22ce;
  background: #f3e8ff;
  border-color: #d8b4fe;
}

.mrp-tag-strategy {
  font-weight: 600;
  color: #0f766e;
  background: #f0fdfa;
  border-color: #99f6e4;
}

.mrp-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
}

.mrp-badge-urgent {
  background: #fee2e2;
  color: #dc2626;
  border: 1px solid #fca5a5;
}

.mrp-badge-shortage {
  background: #ffedd5;
  color: #ea580c;
  border: 1px solid #fdba74;
}
</style>

