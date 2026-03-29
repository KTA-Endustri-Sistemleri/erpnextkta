<script setup lang="ts">
import { ref, computed, watch, onMounted } from "vue";

const props = defineProps<{
  doc: any;
}>();

// Data Refs
const maintenanceRecords = ref([]);
const arizaRecords = ref([]);
const makineNoOptions = ref([]);

// Loading States
const loading = ref(false);
const arizaLoading = ref(false);

// Helpers
const isAdmin = computed(() => {
  try {
    return window.frappe?.session?.user === "Administrator";
  } catch (e) {
    return false;
  }
});

// Functions
async function loadMaintenanceRecords() {
  if (!props.doc?.name) return;
  loading.value = true;
  try {
    const response = await window.frappe.call({
      method: "frappe.client.get_list",
      args: {
        doctype: "Makine Gunluk Bakim Formu",
        filters: {
          calisma_karti_ref: props.doc.name,
          docstatus: ["!=", 2]
        },
        fields: ["name", "makine", "tarih", "onay", "docstatus", "creation"],
        order_by: "creation desc",
        limit_page_length: 20
      }
    });
    maintenanceRecords.value = response.message || [];
  } catch (error) {
    console.error("[BakimView] Error loading maintenance records:", error);
  } finally {
    loading.value = false;
  }
}

async function loadArizaRecords() {
  if (!props.doc?.name) return;
  arizaLoading.value = true;
  try {
    const response = await window.frappe.call({
      method: "frappe.client.get_list",
      args: {
        doctype: "Asset Maintenance Log",
        filters: {
          custom_calisma_karti_ref: props.doc.name
        },
        fields: ["name", "asset_name", "due_date", "custom_ariza_nedeni", "custom_ariza_aciklamasi", "creation", "maintenance_status"],
        order_by: "creation desc",
        limit_page_length: 50
      }
    });
    
    // Filter safely in frontend
    const allLogs = response.message || [];
    arizaRecords.value = allLogs.filter(log => {
      // Direct string comparison, case sensitive as in DB
      return log && log.maintenance_status === "Arıza Bildirimi";
    });
  } catch (error) {
    console.error("[BakimView] Error loading ariza records:", error);
  } finally {
    arizaLoading.value = false;
  }
}

async function loadMakineNoOptions() {
  try {
    const response = await window.frappe.call({
      method: "frappe.client.get_list",
      args: {
        doctype: "Asset",
        filters: { custom_makine_no: ["!=", ""] },
        fields: ["custom_makine_no"],
        limit_page_length: 0
      }
    });
    if (response.message) {
      const options = response.message.map(r => r.custom_makine_no).filter(Boolean);
      makineNoOptions.value = [...new Set(options)];
    }
  } catch (error) {
    console.error("[BakimView] Error loading makine options:", error);
  }
}

// Dialogs
function openMaintenanceDialog() {
  window.frappe.call({
    method: 'frappe.client.get',
    args: { doctype: 'Bakim Talimati', name: 'PTR.BT.049' },
    callback: (r) => {
      if (!r.message) return;
      const instruction = r.message;
      let html = `<div style="padding: 20px; background-color: var(--control-bg, #f9f9f9); border-radius: 5px; max-height: 500px; overflow-y: auto;">
          <h3 style="color: var(--text-color, #333); margin-top: 0;">${instruction.talimat_kodu} - ${instruction.talimat_adi}</h3>`;
      if (instruction.amac) html += `<p><strong>AMAÇ:</strong> ${instruction.amac}</p>`;
      if (instruction.kapsam) html += `<p><strong>KAPSAM:</strong> ${instruction.kapsam}</p>`;
      html += '<hr style="border: 0; border-top: 2px solid var(--border-color, #ddd); margin: 15px 0;">';
      if (instruction.talimat_metni) html += instruction.talimat_metni;
      html += '</div>';

      const dialog = new window.frappe.ui.Dialog({
        title: 'Günlük Bakım Onayı',
        fields: [
          { fieldtype: 'Link', fieldname: 'makine', label: 'Makine No', options: 'Asset', reqd: 1 },
          { fieldtype: 'HTML', fieldname: 'instruction_html', options: html },
          { fieldtype: 'Check', fieldname: 'onay', label: 'Onaylıyorum', reqd: 1 },
          { fieldtype: 'Small Text', fieldname: 'notlar', label: 'Notlar' }
        ],
        primary_action_label: 'Kaydet',
        primary_action: (values) => {
          window.frappe.call({
            method: 'frappe.client.insert',
            args: {
              doc: {
                doctype: 'Makine Gunluk Bakim Formu',
                calisma_karti_ref: props.doc.name,
                operator: props.doc.operator,
                makine: values.makine,
                tarih: window.frappe.datetime.get_today(),
                bakim_talimati: 'PTR.BT.049',
                notlar: values.notlar || '',
                onay: 1
              }
            },
            callback: (r) => {
              if (r.message) {
                window.frappe.call({
                  method: 'frappe.client.submit',
                  args: { doc: r.message },
                  callback: () => {
                    dialog.hide();
                    loadMaintenanceRecords();
                  }
                });
              }
            }
          });
        }
      });
      dialog.show();
    }
  });
}

function openArizaDialog() {
  const dialog = new window.frappe.ui.Dialog({
    title: 'Arıza Bildirimi',
    fields: [
      { fieldtype: 'Autocomplete', fieldname: 'makine_no', label: 'Makine No', reqd: 1, options: makineNoOptions.value.join('\n') },
      { fieldtype: 'Link', fieldname: 'ariza_nedeni', label: 'Arıza Nedeni', options: 'Ariza Nedeni', reqd: 1 },
      { fieldtype: 'Small Text', fieldname: 'aciklama', label: 'Açıklama', reqd: 1 }
    ],
    primary_action: (values) => {
      window.frappe.call({
        method: 'erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.create_ariza_bildirimi',
        args: {
          calisma_karti: props.doc.name,
          makine_no: values.makine_no,
          ariza_nedeni: values.ariza_nedeni,
          aciklama: values.aciklama
        },
        callback: (r) => {
          if (!r.exc) {
            dialog.hide();
            loadArizaRecords();
          }
        }
      });
    }
  });
  dialog.show();
}

function openMaintenanceRecord(recordName) {
  window.frappe.set_route("Form", "Makine Gunluk Bakim Formu", recordName);
}

function openArizaRecord(recordName) {
  window.frappe.set_route("Form", "Asset Maintenance Log", recordName);
}

// Watcher at the end for cleanliness
watch(() => props.doc?.name, (newVal) => {
  if (newVal) {
    loadMaintenanceRecords();
    loadArizaRecords();
    loadMakineNoOptions();
  }
}, { immediate: true });

</script>

<template>
  <div class="ck-card">
    <div class="ck-qc-header">
      <b style="font-size: 15px;">Makine Günlük Bakım</b>
      <button class="ck-btn ck-btn--primary" style="background: var(--btn-default-hover-bg);padding: 8px 10px;" @click="openMaintenanceDialog">
        + Ekle
      </button>
    </div>

    <div v-if="loading" class="ck-empty-state">Yükleniyor...</div>
    <div v-else-if="!maintenanceRecords || maintenanceRecords.length === 0" class="ck-empty-state">Henüz bakım kaydı yok.</div>
    <div v-else class="ck-mini-list">
      <div v-for="record in maintenanceRecords" :key="record.name" class="ck-mini-item" @click="openMaintenanceRecord(record.name)">
        <div class="ck-mini-content">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <b class="ck-mini-title">{{ record.name }}</b>
            <span class="ck-status-pill" :class="record.docstatus === 1 ? 'is-success' : 'is-warning'">
              {{ record.docstatus === 1 ? 'Onaylandı' : 'Taslak' }}
            </span>
          </div>
          <div class="ck-muted ck-mini-sub">Makine: <strong style="color:var(--ck-text);">{{ record.makine }}</strong></div>
          <div class="ck-muted ck-mini-sub">Tarih: {{ record.tarih || '---' }}</div>
        </div>
      </div>
    </div>
    
    <div style="margin-top: 24px;"></div>
    
    <div class="ck-qc-header">
      <b style="font-size: 15px;">Makine Arıza Bildirimi</b>
      <button class="ck-btn ck-btn--primary" style="background: var(--btn-default-hover-bg); padding: 8px 10px;" @click="openArizaDialog">
        + Arıza Bildir
      </button>
    </div>

    <div v-if="arizaLoading" class="ck-empty-state">Yükleniyor...</div>
    <div v-else-if="!arizaRecords || arizaRecords.length === 0" class="ck-empty-state">Henüz arıza bildirimi yapılmamış.</div>
    <div v-else class="ck-mini-list">
      <div v-for="record in arizaRecords" :key="record.name" class="ck-mini-item" @click="openArizaRecord(record.name)" style="border-left: 3px solid var(--ck-danger, #ef4444);">
        <div class="ck-mini-content" v-if="record">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <b class="ck-mini-title">{{ record.name }}</b>
            <span class="ck-status-pill is-danger" style="background: rgba(239, 68, 68, 0.12); color: var(--ck-danger, #ef4444); border: 1px solid rgba(239, 68, 68, 0.3);">
              Arıza Bildirimi
            </span>
          </div>
          <div class="ck-muted ck-mini-sub">Makine: <strong>{{ record.asset_name || '---' }}</strong></div>
          <div class="ck-muted ck-mini-sub" style="margin-top: 4px; font-style: italic;">"{{ record.custom_ariza_aciklamasi || 'Açıklama yok' }}"</div>
          <div class="ck-muted ck-mini-sub" style="margin-top: 4px;">Tarih: {{ record.due_date || (record.creation ? record.creation.split(' ')[0] : '---') }}</div>
        </div>
      </div>
    </div>

    <!-- Admin Debug -->
    <div v-if="isAdmin" style="margin-top: 50px; padding: 10px; border: 1px dashed #ccc; font-size: 10px; opacity: 0.5;">
      <b>Admin Debug:</b><br>
      ID: {{ props.doc?.name }}<br>
      Ariza Count: {{ arizaRecords.length }}
    </div>
  </div>
</template>

<style scoped>
.ck-qc-header {
  padding: 6px 14px 14px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(128,128,128,0.1);
  margin-bottom: 10px;
}
.ck-empty-state { padding: 10px; text-align: center; color: var(--ck-text-muted); font-size: 13px; opacity: 0.7; }
.ck-mini-list { display: flex; flex-direction: column; gap: 10px; padding: 0 10px 10px; }
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
  cursor: pointer;
}
.ck-mini-item:hover { transform: translateY(-2px); box-shadow: var(--ck-glass-highlight), 0 6px 16px rgba(0,0,0,0.06); }
.ck-mini-content { min-width: 0; display: flex; flex-direction: column; gap: 4px; width: 100%; }
.ck-mini-title { font-size: 15px; font-weight: 800; color: var(--ck-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ck-mini-sub { font-size: 12px; opacity: 0.8; }
.ck-status-pill { font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.02em; }
.ck-status-pill.is-success { background: rgba(34, 197, 94, 0.12); color: var(--success, #22c55e); border: 1px solid rgba(34, 197, 94, 0.2); }
.ck-status-pill.is-warning { background: rgba(245, 158, 11, 0.12); color: var(--warning, #f59e0b); border: 1px solid rgba(245, 158, 11, 0.2); }
</style>
