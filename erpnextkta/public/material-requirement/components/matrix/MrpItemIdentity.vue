<template>
  <div class="mrp-item-identity">
    <div class="mrp-item-text" @click="handleItemClick" style="cursor: pointer;">
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
          :class="[
            'mrp-badge',
            material.is_urgent ? 'mrp-badge-urgent' : 'mrp-badge-shortage',
          ]"
          :title="__('İlk Eksik Hafta')"
        >
          <i class="fa fa-exclamation-triangle mr-1"></i>
          {{ material.first_shortage_week }}
        </span>

        <!-- Dispute Warning Badge -->
        <span
          v-if="material.uyusmazlikta_total && material.uyusmazlikta_total > 0"
          class="mrp-badge mrp-badge-dispute"
          :title="
            __('Mal Kabul Uyuşmazlığı (Kapıda Bloke / Karantina): {0} {1}', [
              formatQty(material.uyusmazlikta_total),
              material.uom,
            ])
          "
        >
          <i class="fa fa-exclamation-triangle mr-1"></i>
          {{ __("Uyuşmazlık") }}: {{ formatQty(material.uyusmazlikta_total) }}
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
          v-else-if="
            material.sourcing_strategy &&
            !material.sourcing_strategy.startsWith('Varsayılan Tedarikçi')
          "
          class="mrp-tag mrp-tag-strategy"
          :title="__('Tedarik Stratejisi')"
        >
          <i class="fa fa-sliders mr-1"></i>{{ __(material.sourcing_strategy) }}
        </span>
        <span
          v-else-if="material.supplier"
          class="mrp-tag mrp-tag-supplier"
          :title="__('Varsayılan Tedarikçi')"
        >
          <i class="fa fa-building-o mr-1"></i>{{ material.supplier }}
        </span>

        <!-- Free Stock -->
        <span class="mrp-tag mrp-tag-stock" :title="__('Serbest Stok')">
          <i class="fa fa-cubes mr-1"></i>{{ formatQty(material.free_stock) }}
          {{ material.uom }}
        </span>

        <!-- Order Amount -->
        <span
          v-if="material.order_amount > 0"
          class="mrp-tag mrp-tag-amount"
          :title="__('Önerilen Sipariş Tutarı')"
        >
          <i class="fa fa-money mr-1"></i
          >{{ formatMoney(material.order_amount, material.currency) }}
        </span>
      </div>

      <!-- Row 2: Supply Pipeline (Chronological Progression: PO -> Yolda -> Antrepo -> Gümrükte) -->
      <div v-if="hasPipelineSupplies" class="mrp-item-pipeline">
        <span
          class="mrp-pipeline-label"
          :title="__('Tedarik Boru Hattı (Geliş Aşamaları)')"
        >
          <i class="fa fa-random mr-1"></i>{{ __("Tedarik") }}:
        </span>

        <!-- 1. PO: Henüz Sevk Edilmemiş Açık PO -->
        <span
          v-if="material.po_kalan_total && material.po_kalan_total > 0"
          class="mrp-tag mrp-tag-po"
          :title="__('Henüz Sevk Edilmemiş Açık PO')"
        >
          <i class="fa fa-file-text-o mr-1"></i>{{ __("PO") }}:
          {{ formatQty(material.po_kalan_total) }}
        </span>

        <!-- 2. Yolda: Sevkiyatta / Yolda Olan Açık Teslimat -->
        <span
          v-if="material.yolda_total && material.yolda_total > 0"
          class="mrp-tag mrp-tag-yolda"
          :title="__('Sevkiyatta / Yolda Olan Açık Teslimat')"
        >
          <i class="fa fa-ship mr-1"></i>{{ __("Yolda") }}:
          {{ formatQty(material.yolda_total) }}
        </span>

        <!-- 3. Antrepo: Gümrüklü Antrepoda Bekleyen (Bekleme Havuzu) -->
        <span
          v-if="material.antrepoda_total && material.antrepoda_total > 0"
          class="mrp-tag mrp-tag-antrepo"
          :title="
            __('Gümrüklü Antrepoda Bekleyen Açık Teslimat (Bekleme Havuzu)')
          "
        >
          <i class="fa fa-university mr-1"></i>{{ __("Antrepo") }}:
          {{ formatQty(material.antrepoda_total) }}
        </span>

        <!-- 4. Gümrükte: Gümrükleme / Çekim İşlemi Başlatılmış (+2 Gün) -->
        <span
          v-if="material.gumruklemede_total && material.gumruklemede_total > 0"
          class="mrp-tag mrp-tag-gumruk"
          :title="
            __('Gümrükleme / Çekim İşlemi Başlatılmış Açık Teslimat (+2 Gün)')
          "
        >
          <i class="fa fa-hourglass-half mr-1"></i>{{ __("Gümrükte") }}:
          {{ formatQty(material.gumruklemede_total) }}
        </span>

        <!-- 5. Uyuşmazlık: Mal Kabul Uyuşmazlığı (Kapıda Bloke / Karantina) -->
        <span
          v-if="material.uyusmazlikta_total && material.uyusmazlikta_total > 0"
          class="mrp-tag mrp-tag-dispute"
          :title="__('Mal Kabul Uyuşmazlığı (Kapıda Bloke / Karantina)')"
        >
          <i class="fa fa-exclamation-triangle mr-1"></i>{{ __("Uyuşmazlık") }}:
          {{ formatQty(material.uyusmazlikta_total) }}
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

const { openDrawer } = useMrpState();

function handleItemClick() {
  openDrawer(props.material.item_code);
}

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
      (m.gumruklemede_total && m.gumruklemede_total > 0) ||
      (m.uyusmazlikta_total && m.uyusmazlikta_total > 0)
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
  const formatted = Number(val).toLocaleString("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return currency ? `${formatted} ${currency}` : formatted;
}
</script>

<style scoped>
.mrp-item-identity {
  display: flex;
  align-items: flex-start;
  gap: 10px;
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
  color: #4338ca;
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mrp-item-code-link:hover {
  text-decoration: underline;
}
[data-theme="dark"] .mrp-item-code-link {
  color: #a5b4fc;
}

.mrp-item-name {
  font-size: 11px;
  color: var(--mrp-text-muted);
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
  border-top: 1px dashed var(--mrp-border);
}

.mrp-pipeline-label {
  font-size: 9.5px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--mrp-text-muted);
  margin-right: 2px;
}

.mrp-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--mrp-card-subtle);
  color: var(--mrp-text);
  border: 1px solid var(--mrp-border);
}

/* 6. Serbest Stok: Zümrüt Yeşili */
.mrp-tag-stock {
  font-weight: 600;
  color: #15803d;
  background: #dcfce7;
  border-color: rgba(21, 128, 61, 0.28);
}
[data-theme="dark"] .mrp-tag-stock {
  color: #86efac;
  background: rgba(34, 197, 94, 0.2);
  border-color: rgba(134, 239, 172, 0.3);
}

.mrp-tag-amount {
  font-weight: 600;
  color: #15803d;
  background: #dcfce7;
  border-color: rgba(21, 128, 61, 0.28);
}
[data-theme="dark"] .mrp-tag-amount {
  color: #86efac;
  background: rgba(34, 197, 94, 0.2);
  border-color: rgba(134, 239, 172, 0.3);
}

/* 1. PO: İndigo */
.mrp-tag-po {
  font-weight: 600;
  color: #4338ca;
  background: #eef2ff;
  border-color: rgba(67, 56, 202, 0.3);
}
[data-theme="dark"] .mrp-tag-po {
  color: #a5b4fc;
  background: rgba(99, 102, 241, 0.2);
  border-color: rgba(165, 180, 252, 0.3);
}

/* 2. Yolda: Amber / Altın Sarısı */
.mrp-tag-yolda {
  font-weight: 600;
  color: #b45309;
  background: #fef3c7;
  border-color: rgba(180, 83, 9, 0.3);
}
[data-theme="dark"] .mrp-tag-yolda {
  color: #fcd34d;
  background: rgba(245, 158, 11, 0.2);
  border-color: rgba(252, 211, 77, 0.3);
}

/* 3. Antrepo: Sky Blue */
.mrp-tag-antrepo {
  font-weight: 600;
  color: #0369a1;
  background: #e0f2fe;
  border-color: rgba(3, 105, 161, 0.3);
}
[data-theme="dark"] .mrp-tag-antrepo {
  color: #7dd3fc;
  background: rgba(14, 165, 233, 0.2);
  border-color: rgba(125, 211, 252, 0.3);
}

/* 4. Gümrük: Canlı Turuncu */
.mrp-tag-gumruk {
  font-weight: 600;
  color: #c2410c;
  background: #ffedd5;
  border-color: rgba(194, 65, 12, 0.3);
}
[data-theme="dark"] .mrp-tag-gumruk {
  color: #fdba74;
  background: rgba(249, 115, 22, 0.2);
  border-color: rgba(253, 186, 116, 0.3);
}

/* 5. Uyuşmazlık: Koyu Kırmızı */
.mrp-tag-dispute,
.mrp-badge-dispute {
  font-weight: 600;
  color: #b91c1c;
  background: #fee2e2;
  border: 1px solid rgba(185, 28, 28, 0.3);
}
[data-theme="dark"] .mrp-tag-dispute,
[data-theme="dark"] .mrp-badge-dispute {
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.25);
  border-color: rgba(252, 165, 165, 0.3);
}

/* 7. Acil Eksik: Kızıl Gül / Coral */
.mrp-badge-urgent {
  background: #ffe4e6;
  color: #be123c;
  border: 1px solid rgba(190, 18, 60, 0.3);
}
[data-theme="dark"] .mrp-badge-urgent {
  color: #fda4af;
  background: rgba(244, 63, 94, 0.25);
  border-color: rgba(253, 164, 175, 0.3);
}

.mrp-badge-shortage {
  background: #ffedd5;
  color: #c2410c;
  border: 1px solid rgba(194, 65, 12, 0.3);
}
[data-theme="dark"] .mrp-badge-shortage {
  color: #fdba74;
  background: rgba(249, 115, 22, 0.2);
  border-color: rgba(253, 186, 116, 0.3);
}

/* 8. Kotalı Alım: Menekşe Moru */
.mrp-tag-quota {
  font-weight: 600;
  color: #7e22ce;
  background: #f3e8ff;
  border-color: rgba(126, 34, 206, 0.28);
}
[data-theme="dark"] .mrp-tag-quota {
  color: #d8b4fe;
  background: rgba(168, 85, 247, 0.2);
  border-color: rgba(216, 180, 254, 0.3);
}

.mrp-tag-strategy {
  font-weight: 600;
  color: #0f766e;
  background: rgba(15, 118, 110, 0.12);
  border-color: rgba(15, 118, 110, 0.28);
}
[data-theme="dark"] .mrp-tag-strategy {
  color: #5eead4;
  background: rgba(20, 184, 166, 0.2);
  border-color: rgba(94, 234, 212, 0.3);
}

.mrp-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
}
</style>
