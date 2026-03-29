<script setup lang="ts">
import { ref } from "vue";
import CkHurdaModal from "../components/CkHurdaModal.vue";

const props = defineProps<{
  doc: any;
  onAdd: (payload: any) => Promise<void>;
  onUpdate: (payload: any) => Promise<void>;
  onDelete: (rowname: string) => Promise<void>;
}>();

const showModal = ref(false);
const editItem = ref<any>(null);

function onHurdaEkle() {
  editItem.value = null;
  showModal.value = true;
}

function onHurdaDuzenle(h: any) {
  editItem.value = h;
  showModal.value = true;
}

async function handleModalSubmit(payload: any) {
  if (payload.rowname) {
    await props.onUpdate(payload);
    frappe.show_alert({ message: "Hurda güncellendi", indicator: "green" });
  } else {
    await props.onAdd(payload);
    frappe.show_alert({ message: "Hurda eklendi", indicator: "green" });
  }
}

function onHurdaSil(h: any) {
  if (!h?.name) {
    frappe.msgprint("Hurda satır kimliği (row name) bulunamadı.");
    return;
  }

  frappe.confirm("Bu hurda satırı silinecek. Emin misiniz?", async () => {
    await props.onDelete(h.name);
    frappe.show_alert({ message: "Hurda silindi", indicator: "green" });
  });
}

function openStockEntry() {
  if (props.doc.scrap_stock_entry) {
    frappe.set_route("Form", "Stock Entry", props.doc.scrap_stock_entry);
  }
}
</script>

<template>
  <div class="ck-card">
    <div class="ck-view-action" v-if="doc.durum !== 'Hazır' && doc.durum !== 'Bitmiş'">
      <button class="ck-btn ck-btn--ghost ck-btn--wide" @click="onHurdaEkle">Hurda Ekle</button>
    </div>

    <!-- Stock Entry Link -->
    <div v-if="doc.scrap_stock_entry" class="ck-se-link-box" @click="openStockEntry">
      <div class="ck-se-icon">📦</div>
      <div class="ck-se-text">
        <div class="ck-se-label">Bağlı Stok Belgesi</div>
        <div class="ck-se-name">{{ doc.scrap_stock_entry }}</div>
      </div>
      <div class="ck-se-arrow">→</div>
    </div>

    <div v-if="(doc.hurdalar||[]).length===0" class="ck-empty-state">Hurda kaydı yok.</div>

    <div v-else class="ck-mini-list">
      <div v-for="(h, i) in doc.hurdalar" :key="h.name || i" class="ck-mini-item">
        <div class="ck-mini-content">
            <b class="ck-mini-title">{{ h.parca_no || ('Hurda #' + (Number(i) + 1)) }}</b>
            <div class="ck-muted ck-mini-sub"><b>Neden:</b> {{ h.hurda_nedeni || "-" }}</div>
            <div class="ck-muted ck-mini-sub"><b>Miktar:</b> {{ h.miktar ?? "-" }} {{ h.birim || "" }}</div>
            <div v-if="h.aciklama" class="ck-muted ck-mini-sub italic">"{{ h.aciklama }}"</div>
        </div>

        <div class="ck-mini-actions">
          <button class="ck-btn ck-btn--ghost ck-btn-small" @click="onHurdaDuzenle(h)">Düzenle</button>
          <button class="ck-btn ck-btn--danger ck-btn-small" @click="onHurdaSil(h)">Sil</button>
        </div>
      </div>
    </div>

    <!-- Modal -->
    <CkHurdaModal
      :show="showModal"
      :doc="doc"
      :editData="editItem"
      @close="showModal = false"
      @submit="handleModalSubmit"
    />
  </div>
</template>

<style scoped>
.ck-view-action {
  padding: 0 10px 14px 10px;
  display: flex;
}

.ck-se-link-box {
    margin: 0 10px 14px;
    padding: 12px 16px;
    background: linear-gradient(135deg, rgba(var(--ck-primary-rgb), 0.1), rgba(var(--ck-primary-rgb), 0.05));
    border: 1px solid rgba(var(--ck-primary-rgb), 0.2);
    border-radius: 14px;
    display: flex;
    align-items: center;
    gap: 12px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.ck-se-link-box:hover {
    background: linear-gradient(135deg, rgba(var(--ck-primary-rgb), 0.15), rgba(var(--ck-primary-rgb), 0.1));
    transform: translateY(-1px);
    border-color: rgba(var(--ck-primary-rgb), 0.3);
}

.ck-se-icon {
    font-size: 20px;
}

.ck-se-text {
    flex: 1;
}

.ck-se-label {
    font-size: 11px;
    color: var(--ck-text-muted);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.ck-se-name {
    font-size: 14px;
    font-weight: 800;
    color: var(--ck-primary);
}

.ck-se-arrow {
    font-size: 18px;
    color: var(--ck-primary);
    opacity: 0.5;
}

.ck-empty-state {
  padding: 10px;
  text-align: center;
  color: var(--ck-text-muted);
  font-size: 13px;
  opacity: 0.7;
}
.ck-mini-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 10px 10px;
}
.ck-mini-item {
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border-soft);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  box-shadow: var(--ck-glass-highlight), 0 2px 8px rgba(0,0,0,0.02);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.ck-mini-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--ck-glass-highlight), 0 6px 16px rgba(0,0,0,0.06);
}
@media (max-width: 480px) {
  .ck-mini-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
.ck-mini-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ck-mini-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--ck-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ck-mini-sub {
  font-size: 12px;
  opacity: 0.8;
}
.italic {
    font-style: italic;
    font-size: 11px;
    color: var(--ck-text-muted);
}
.ck-mini-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.ck-btn-small {
  padding: 8px 14px;
  font-size: 13px;
  border-radius: 8px;
  font-weight: 700;
}
</style>

<style scoped>
.ck-view-action {
  padding: 0 10px 14px 10px;
  display: flex;
}
.ck-empty-state {
  padding: 10px;
  text-align: center;
  color: var(--ck-text-muted);
  font-size: 13px;
  opacity: 0.7;
}
.ck-mini-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 0 10px 10px;
}
.ck-mini-item {
  background: var(--ck-glass-bg);
  border: 1px solid var(--ck-glass-border-soft);
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  box-shadow: var(--ck-glass-highlight), 0 2px 8px rgba(0,0,0,0.02);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.ck-mini-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--ck-glass-highlight), 0 6px 16px rgba(0,0,0,0.06);
}
@media (max-width: 480px) {
  .ck-mini-item {
    flex-direction: column;
    align-items: flex-start;
  }
}
.ck-mini-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ck-mini-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--ck-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.ck-mini-sub {
  font-size: 12px;
  opacity: 0.8;
}
.ck-mini-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.ck-btn-small {
  padding: 8px 14px;
  font-size: 13px;
  border-radius: 8px;
  font-weight: 700;
}
</style>
