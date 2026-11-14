<template>
  <div
    v-if="(allSupplies && allSupplies.length > 0) || selectedWeek"
    class="mrp-po-container"
  >
    <!-- 0. Mal Kabul Uyuşmazlığı (Kapıda Bloke / Karantina) -->
    <div
      v-if="disputeSupplies.length > 0"
      class="mrp-antrepo-pool-card mb-3"
      style="border-left: 4px solid #dc2626; background: #fff5f5"
    >
      <div
        class="mrp-antrepo-pool-header d-flex justify-content-between align-items-center flex-wrap gap-2"
      >
        <div class="d-flex align-items-center">
          <i class="fa fa-exclamation-triangle mr-2 text-danger"></i>
          <span class="font-weight-bold text-danger">
            {{ __("Mal Kabul Uyuşmazlığı (Kapıda Bloke / Karantina)") }}
          </span>
          <span class="badge badge-danger ml-2 font-weight-bold">
            {{ disputeSupplies.length }} {{ __("Belge") }}
          </span>
        </div>
        <span class="small text-danger font-italic">
          <i class="fa fa-ban mr-1"></i>
          {{
            __(
              "Uyuşmazlık çözülene kadar malzeme üretimde kullanılamaz ve haftalık arza (receipts = 0) dahil edilmez."
            )
          }}
        </span>
      </div>

      <div class="table-responsive mt-1">
        <table class="table table-sm table-bordered mrp-sub-table bg-white">
          <thead>
            <tr>
              <th style="min-width: 170px">{{ __("Belge No") }}</th>
              <th style="min-width: 150px">{{ __("Uyuşmazlık Nedeni") }}</th>
              <th style="min-width: 180px">{{ __("Açıklama") }}</th>
              <th style="min-width: 160px">{{ __("Tedarikçi") }}</th>
              <th class="text-right" style="min-width: 110px">
                {{ __("Miktar") }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(item, idx) in disputeSupplies"
              :key="`dispute-${item.name}-${idx}`"
            >
              <td>
                <div class="d-flex align-items-center">
                  <span
                    class="badge badge-pill badge-danger mr-2"
                    style="font-size: 9px; padding: 2px 6px"
                    >PR</span
                  >
                  <a
                    :href="getDocumentUrl(item)"
                    target="_blank"
                    class="font-weight-bold text-danger"
                  >
                    {{ item.name }}
                  </a>
                </div>
                <div
                  v-if="item.po_name"
                  class="small text-muted mt-1"
                  style="font-size: 10px"
                >
                  <span>{{ __("Sipariş") }}:</span>
                  <a
                    :href="`/app/purchase-order/${encodeURIComponent(
                      item.po_name
                    )}`"
                    target="_blank"
                    class="text-muted ml-1"
                  >
                    {{ item.po_name }}
                  </a>
                </div>
              </td>
              <td>
                <span class="badge badge-danger">
                  ⚠️ {{ item.dispute_reason || __("Uyuşmazlık Bildirildi") }}
                </span>
              </td>
              <td>
                <span class="small text-dark">{{
                  item.dispute_description || "-"
                }}</span>
              </td>
              <td>{{ item.supplier || "-" }}</td>
              <td class="text-right font-weight-bold text-danger">
                {{ formatQty(getItemQty(item)) }} {{ uom }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 1. Gümrüklü Antrepoda Bekleyen Teslimatlar (İşlem Bekleyen Stok Havuzu) -->
    <div v-if="antrepoSupplies.length > 0" class="mrp-antrepo-pool-card mb-3">
      <div
        class="mrp-antrepo-pool-header d-flex justify-content-between align-items-center flex-wrap gap-2"
      >
        <div class="d-flex align-items-center">
          <i class="fa fa-university mr-2 text-info"></i>
          <span class="font-weight-bold text-info-dark">
            {{
              __(
                "Gümrüklü Antrepoda Bekleyen Teslimatlar (İşlem Bekleyen Stok Havuzu)"
              )
            }}
          </span>
          <span class="badge badge-info ml-2 font-weight-bold">
            {{ antrepoSupplies.length }} {{ __("Belge") }}
          </span>
        </div>
        <span class="small text-muted font-italic">
          <i class="fa fa-info-circle mr-1 text-info"></i>
          {{
            __(
              "Antrepoda bekleyen malzemeler çekim işlemi başlatılana kadar haftalık timeline'a dahil edilmez. Gümrükleme başlatıldığında (+2 gün) fabrikaya sevk edilir."
            )
          }}
        </span>
      </div>

      <div class="table-responsive mt-1">
        <table
          class="table table-sm table-bordered mrp-sub-table mrp-antrepo-table"
        >
          <thead>
            <tr>
              <th style="min-width: 170px">{{ __("Belge No") }}</th>
              <th style="min-width: 140px">{{ __("Durum") }}</th>
              <th style="min-width: 160px">{{ __("Tedarikçi") }}</th>
              <th style="min-width: 130px">{{ __("Gümrüğe Geliş Tarihi") }}</th>
              <th style="min-width: 170px">
                {{ __("Fabrikaya Sevkiyat Koşulu") }}
              </th>
              <th class="text-right" style="min-width: 110px">
                {{ __("Miktar") }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(item, idx) in antrepoSupplies"
              :key="`antrepo-${item.name}-${idx}`"
            >
              <!-- Belge No & Bağlı PO -->
              <td>
                <div class="d-flex align-items-center">
                  <span
                    class="badge badge-pill badge-primary mr-2"
                    style="font-size: 9px; padding: 2px 6px"
                    >PR</span
                  >
                  <a
                    :href="getDocumentUrl(item)"
                    target="_blank"
                    class="font-weight-bold"
                  >
                    {{ item.name }}
                  </a>
                </div>
                <div
                  v-if="item.po_name"
                  class="small text-muted mt-1"
                  style="font-size: 10px"
                >
                  <span>{{ __("Sipariş") }}:</span>
                  <a
                    :href="`/app/purchase-order/${encodeURIComponent(
                      item.po_name
                    )}`"
                    target="_blank"
                    class="text-muted ml-1"
                  >
                    {{ item.po_name }}
                  </a>
                </div>
              </td>

              <!-- Durum -->
              <td>
                <span class="badge mrp-state-badge mrp-badge-antrepo">
                  <i class="fa fa-university mr-1"></i>
                  {{ __(item.state || "Antrepoda") }}
                </span>
              </td>

              <!-- Tedarikçi -->
              <td>{{ item.supplier || "-" }}</td>

              <!-- Gümrüğe Geliş Tarihi -->
              <td>
                <div class="d-flex flex-column">
                  <span class="font-weight-bold">{{
                    item.customs_date || item.date || "-"
                  }}</span>
                  <span class="small text-muted" style="font-size: 10px">{{
                    __("Gümrüğe Geliş")
                  }}</span>
                </div>
              </td>

              <!-- Fabrikaya Sevkiyat Koşulu -->
              <td>
                <span class="small text-muted">
                  <i class="fa fa-hourglass-start mr-1 text-primary"></i>
                  {{
                    __("İşlem başlatıldığında (+2 gün) fabrikaya ulaşacaktır")
                  }}
                </span>
              </td>

              <!-- Miktar -->
              <td class="text-right font-weight-bold text-primary">
                +{{ formatQty(getItemQty(item)) }} {{ uom }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 2. Haftalık Açık Siparişler ve Sevkiyatlar (PO / Yolda / Gümrükte) -->
    <div class="mrp-scheduled-supplies-section">
      <div
        class="mrp-sub-header d-flex justify-content-between align-items-center flex-wrap gap-2"
      >
        <div class="d-flex align-items-center">
          <i class="fa fa-calendar-check-o mr-2 text-primary"></i>
          <span class="font-weight-bold">{{
            __(
              "Haftalık Açık Siparişler ve Sevkiyatlar (PO / Yolda / Gümrükte)"
            )
          }}</span>
          <span
            v-if="selectedWeek"
            class="badge badge-primary ml-2 font-weight-normal"
            style="font-size: 11px"
          >
            📅 {{ formatWeek(selectedWeek) }}
          </span>
        </div>

        <!-- Week Filter Selector Pills -->
        <div class="d-flex align-items-center gap-1 flex-wrap">
          <button
            type="button"
            class="btn btn-xs mrp-week-pill"
            :class="{
              'btn-primary text-white font-weight-bold': !selectedWeek,
              'btn-light text-muted': selectedWeek,
            }"
            @click="selectWeek(null)"
          >
            {{ __("Tümü") }} ({{ scheduledSupplies.length }})
          </button>
          <button
            v-for="wk in availableWeeksWithCounts"
            :key="wk.key"
            type="button"
            class="btn btn-xs mrp-week-pill"
            :class="{
              'btn-primary text-white font-weight-bold':
                selectedWeek === wk.key,
              'btn-light text-dark': selectedWeek !== wk.key,
            }"
            @click="selectWeek(selectedWeek === wk.key ? null : wk.key)"
          >
            {{ formatWeek(wk.key) }} ({{ wk.count }})
          </button>
          <button
            v-if="selectedWeek && !hasItemsForSelectedWeek"
            type="button"
            class="btn btn-xs btn-primary text-white font-weight-bold mrp-week-pill"
          >
            {{ formatWeek(selectedWeek) }} (0)
          </button>
          <button
            v-if="selectedWeek"
            type="button"
            class="btn btn-xs btn-outline-secondary ml-1"
            :title="__('Hafta filtresini kaldır')"
            @click="selectWeek(null)"
          >
            <i class="fa fa-times mr-1"></i>{{ __("Temizle") }}
          </button>
        </div>
      </div>

      <!-- Empty state for selected week -->
      <div
        v-if="displayedScheduledSupplies.length === 0"
        class="py-3 px-2 text-center text-muted small bg-light rounded mt-2 border"
      >
        <i class="fa fa-info-circle mr-1 text-info"></i>
        <span v-if="selectedWeek">
          {{
            __(
              "{0} haftasında bekleyen açık teslimat veya sipariş bulunmamaktadır.",
              [formatWeek(selectedWeek)]
            )
          }}
        </span>
        <span v-else>
          {{
            __(
              "Haftalık planlanmış açık sipariş veya teslimat bulunmamaktadır."
            )
          }}
        </span>
        <button
          v-if="selectedWeek"
          type="button"
          class="btn btn-link btn-xs ml-2 font-weight-bold"
          @click="selectWeek(null)"
        >
          {{ __("Tüm açık siparişleri göster") }}
        </button>
      </div>

      <!-- Supplies Table -->
      <div v-else class="table-responsive mt-2">
        <table class="table table-sm table-bordered mrp-sub-table">
          <thead>
            <tr>
              <th style="min-width: 170px">{{ __("Belge No") }}</th>
              <th style="min-width: 140px">{{ __("Durum") }}</th>
              <th style="min-width: 160px">{{ __("Tedarikçi") }}</th>
              <th style="min-width: 110px">{{ __("Termin / Varış") }}</th>
              <th style="min-width: 90px">{{ __("Hafta") }}</th>
              <th class="text-right" style="min-width: 110px">
                {{ __("Miktar") }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(item, idx) in displayedScheduledSupplies"
              :key="`${item.type}-${item.name}-${item.week || ''}-${idx}`"
            >
              <!-- Belge No & Bağlı PO -->
              <td>
                <div class="d-flex align-items-center">
                  <span
                    v-if="isPR(item)"
                    class="badge badge-pill badge-primary mr-2"
                    style="font-size: 9px; padding: 2px 6px"
                  >
                    PR
                  </span>
                  <span
                    v-else
                    class="badge badge-pill badge-secondary mr-2"
                    style="font-size: 9px; padding: 2px 6px"
                  >
                    PO
                  </span>

                  <a
                    :href="getDocumentUrl(item)"
                    target="_blank"
                    class="font-weight-bold"
                  >
                    {{ item.name }}
                  </a>
                </div>

                <!-- Bağlı PO Linki (Eğer İrsaliye ise) -->
                <div
                  v-if="isPR(item) && item.po_name"
                  class="small text-muted mt-1"
                  style="font-size: 10px"
                >
                  <span>{{ __("Sipariş") }}:</span>
                  <a
                    :href="`/app/purchase-order/${encodeURIComponent(
                      item.po_name
                    )}`"
                    target="_blank"
                    class="text-muted ml-1"
                  >
                    {{ item.po_name }}
                  </a>
                </div>
              </td>

              <!-- Durum Rozeti -->
              <td>
                <span
                  :class="[
                    'badge mrp-state-badge',
                    getStateBadgeClass(item.state),
                  ]"
                >
                  <i :class="['fa mr-1', getStateIcon(item.state)]"></i>
                  {{ __(item.state || "Açık Sipariş") }}
                </span>
              </td>

              <!-- Tedarikçi -->
              <td>{{ item.supplier || "-" }}</td>

              <!-- Tarih & Detay -->
              <td>
                <div class="d-flex flex-column">
                  <div class="d-flex align-items-center">
                    <span class="font-weight-bold">{{
                      getItemDate(item)
                    }}</span>
                    <span
                      v-if="item.is_estimated"
                      class="badge badge-warning ml-1 text-dark"
                      style="font-size: 9px; padding: 1px 4px"
                      :title="
                        __(
                          'ETA girilmediği için yükleme tarihine varsayılan nakliye süresi eklendi'
                        )
                      "
                    >
                      {{ __("Tahmini") }}
                    </span>
                  </div>
                  <span class="small text-muted" style="font-size: 10px">
                    {{
                      item.date_label
                        ? __(item.date_label)
                        : isPR(item)
                        ? item.customs_date
                          ? __("Gümrüğe Geliş")
                          : __("Varış")
                        : __("Termin")
                    }}
                  </span>
                  <span
                    v-if="item.clearance_start_date"
                    class="small text-muted"
                    style="font-size: 9.5px"
                  >
                    {{ __("İşlem Başlama") }}: {{ item.clearance_start_date }}
                  </span>
                  <span
                    v-if="item.loading_date"
                    class="small text-muted"
                    style="font-size: 9.5px"
                  >
                    {{ __("Yükleme") }}: {{ item.loading_date }}
                  </span>
                </div>
              </td>

              <!-- Hafta -->
              <td>
                <span
                  v-if="item.week"
                  class="badge badge-light font-weight-normal"
                  >{{ formatWeek(item.week) }}</span
                >
                <span
                  v-else
                  class="badge badge-info font-weight-normal text-white"
                >
                  {{ __("Antrepoda") }}
                </span>
              </td>

              <!-- Miktar -->
              <td class="text-right font-weight-bold text-primary">
                +{{ formatQty(getItemQty(item)) }} {{ uom }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import type { OpenPOReceipt, OpenSupplyItem } from "../../types/mrp";

const __ = (...args: any[]) => (window as any).__(...args);

const props = defineProps<{
  pos?: (OpenPOReceipt | OpenSupplyItem)[];
  supplies?: OpenSupplyItem[];
  uom: string;
  selectedWeek?: string | null;
}>();

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
      const isPrDoc =
        (p as any).type === "PR" || (p as any).name?.startsWith?.("PREC-");
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

// Mal Kabul Uyuşmazlığı (kapıda bloke / karantina irsaliyeleri)
const disputeSupplies = computed<OpenSupplyItem[]>(() => {
  return allSupplies.value.filter((s) => {
    const st = (s.state || "").toLowerCase();
    return st.includes("uyuşmaz") || st.includes("uyusmaz");
  });
});

// Antrepoda bekleyen açık irsaliyeler (bağımsız bekleme havuzu)
const antrepoSupplies = computed<OpenSupplyItem[]>(() => {
  return allSupplies.value.filter((s) => {
    const st = (s.state || "").toLowerCase();
    if (st.includes("uyuşmaz") || st.includes("uyusmaz")) return false;
    return st.includes("antrepo") || (!s.week && isPR(s));
  });
});

// Haftalık timeline'a dahil olan planlı teslimatlar (PO, Yolda, Gümrükte, Mal Giriş)
const scheduledSupplies = computed<OpenSupplyItem[]>(() => {
  return allSupplies.value.filter((s) => {
    const st = (s.state || "").toLowerCase();
    if (st.includes("uyuşmaz") || st.includes("uyusmaz")) return false;
    return !st.includes("antrepo") && (Boolean(s.week) || !isPR(s));
  });
});

const availableWeeksWithCounts = computed(() => {
  const counts: Record<string, number> = {};
  for (const s of scheduledSupplies.value) {
    if (s.week) {
      counts[s.week] = (counts[s.week] || 0) + 1;
    }
  }
  return Object.keys(counts)
    .sort()
    .map((key) => ({ key, count: counts[key] }));
});

const hasItemsForSelectedWeek = computed(() => {
  if (!props.selectedWeek) return true;
  return scheduledSupplies.value.some((s) => s.week === props.selectedWeek);
});

const displayedScheduledSupplies = computed(() => {
  if (!props.selectedWeek) return scheduledSupplies.value;
  return scheduledSupplies.value.filter((s) => s.week === props.selectedWeek);
});

function isPR(item: any): boolean {
  return item.type === "PR" || item.name?.startsWith("PREC-");
}

function getDocumentUrl(item: any): string {
  if (isPR(item)) {
    return `/app/purchase-receipt/${encodeURIComponent(item.name)}`;
  }
  return `/app/purchase-order/${encodeURIComponent(item.name)}`;
}

function getStateBadgeClass(state?: string): string {
  const s = (state || "").toLowerCase();
  if (s.includes("gümrük") || s.includes("gumruk")) return "mrp-badge-gumruk";
  if (s.includes("antrepo")) return "mrp-badge-antrepo";
  if (s.includes("giriş") || s.includes("giris")) return "mrp-badge-giris";
  if (s.includes("yol")) return "mrp-badge-yolda";
  return "mrp-badge-po";
}

function getStateIcon(state?: string): string {
  const s = (state || "").toLowerCase();
  if (s.includes("gümrük") || s.includes("gumruk")) return "fa-hourglass-half";
  if (s.includes("antrepo")) return "fa-university";
  if (s.includes("giriş") || s.includes("giris")) return "fa-check-circle";
  if (s.includes("yol")) return "fa-ship";
  return "fa-file-text-o";
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
.mrp-po-container {
  background: #ffffff;
  padding: 10px 14px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

/* Antrepo Card Styling */
.mrp-antrepo-pool-card {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 6px;
  padding: 8px 12px;
}

.mrp-antrepo-pool-header {
  font-size: 11px;
  margin-bottom: 6px;
}

.text-info-dark {
  color: #0369a1;
}

.mrp-antrepo-table {
  background: #ffffff;
}

.mrp-scheduled-supplies-section {
  margin-top: 4px;
}

.mrp-sub-header {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  color: #64748b;
  margin-bottom: 6px;
}

.mrp-week-pill {
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
  transition: all 0.15s ease;
}

.mrp-week-pill:hover {
  filter: brightness(0.95);
}

.mrp-sub-table {
  font-size: 11px;
  margin-bottom: 0;
}

.mrp-sub-table th {
  background: #f8fafc;
  color: #475569;
  font-weight: 600;
  padding: 4px 6px;
}

.mrp-sub-table td {
  padding: 4px 6px;
  vertical-align: middle;
}

.mrp-state-badge {
  font-size: 10px;
  padding: 2px 7px;
  font-weight: 600;
  border-radius: 4px;
}

.mrp-badge-antrepo {
  color: #0284c7;
  background: #e0f2fe;
  border: 1px solid #7dd3fc;
}

.mrp-badge-gumruk {
  color: #c2410c;
  background: #fff7ed;
  border: 1px solid #fed7aa;
}

.mrp-badge-giris {
  color: #047857;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}

.mrp-badge-yolda {
  color: #d97706;
  background: #fef3c7;
  border: 1px solid #fde68a;
}

.mrp-badge-po {
  color: #4f46e5;
  background: #eef2ff;
  border: 1px solid #c7d2fe;
}
</style>
