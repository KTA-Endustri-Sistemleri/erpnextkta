<script setup lang="ts">
import { ref, computed } from "vue";

const props = defineProps<{
  doc: any;
}>();

function openMaintenanceDialog() {
  // Fetch instruction content
  frappe.call({
    method: 'frappe.client.get',
    args: {
      doctype: 'Bakim Talimati',
      name: 'PTR.BT.049'
    },
    callback: function(r) {
      if (!r.message) {
        frappe.msgprint('Bakım talimatı bulunamadı.');
        return;
      }

      const instruction = r.message;
      let html = `
        <div style="padding: 20px; background-color: #f9f9f9; border-radius: 5px; max-height: 500px; overflow-y: auto;">
          <h3 style="color: #333; margin-top: 0;">${instruction.talimat_kodu} - ${instruction.talimat_adi}</h3>
      `;

      if (instruction.amac) {
        html += `<p><strong>AMAÇ:</strong> ${instruction.amac}</p>`;
      }

      if (instruction.kapsam) {
        html += `<p><strong>KAPSAM:</strong> ${instruction.kapsam}</p>`;
      }

      html += '<hr style="border: 0; border-top: 2px solid #ddd; margin: 15px 0;">';

      if (instruction.talimat_metni) {
        html += instruction.talimat_metni;
      }

      html += '</div>';

      // Create the dialog
      const dialog = new frappe.ui.Dialog({
        title: 'Günlük Bakım Onayı',
        fields: [
          {
            fieldtype: 'Link',
            fieldname: 'makine',
            label: 'Makine No',
            options: 'Asset',
            reqd: 1,
            description: 'Makine numarasını yazarak seçin (ör: M 1)'
          },
          {
            fieldtype: 'Section Break',
            label: 'Bakım Talimatı'
          },
          {
            fieldtype: 'HTML',
            fieldname: 'instruction_html',
            options: html
          },
          {
            fieldtype: 'Section Break',
            label: 'Onay'
          },
          {
            fieldtype: 'Check',
            fieldname: 'onay',
            label: 'Günlük bakımı talimata göre kontrol ettim ve sorun bulunmamıştır.',
            reqd: 1
          },
          {
            fieldtype: 'Small Text',
            fieldname: 'notlar',
            label: 'Notlar (İsteğe Bağlı)'
          }
        ],
        primary_action_label: 'Onayla ve Kaydet',
        primary_action: function(values) {
          if (!values.onay) {
            frappe.msgprint('Lütfen bakım kontrolünü onaylayın.');
            return;
          }

          if (!values.makine) {
            frappe.msgprint('Lütfen makine seçin.');
            return;
          }

          // Create the maintenance record
          frappe.call({
            method: 'frappe.client.insert',
            args: {
              doc: {
                doctype: 'Makine Gunluk Bakim Formu',
                calisma_karti_ref: props.doc.name,
                operator: props.doc.operator,
                makine: values.makine,
                tarih: frappe.datetime.get_today(),
                bakim_talimati: 'PTR.BT.049',
                notlar: values.notlar || '',
                onay: 1
              }
            },
            callback: function(r) {
              if (r.message) {
                // Submit the document
                frappe.call({
                  method: 'frappe.client.submit',
                  args: {
                    doc: r.message
                  },
                  callback: function(submit_r) {
                    dialog.hide();
                    frappe.msgprint({
                      title: 'Başarılı',
                      message: 'Günlük bakım kaydı oluşturuldu ve onaylandı.',
                      indicator: 'green'
                    });

                    // Reload the page to refresh data
                    frappe.set_route('view-calisma-karti', props.doc.name);
                  }
                });
              }
            }
          });
        }
      });

      dialog.show();
      dialog.$wrapper.find('.modal-dialog').css("max-width", "800px");
    }
  });
}

// Fetch existing maintenance records for today
const maintenanceRecords = ref<any[]>([]);
const loading = ref(false);

async function loadMaintenanceRecords() {
  loading.value = true;
  try {
    const result = await frappe.call({
      method: 'frappe.client.get_list',
      args: {
        doctype: 'Makine Gunluk Bakim Formu',
        filters: {
          calisma_karti_ref: props.doc.name,
          docstatus: ['!=', 2] // Not cancelled
        },
        fields: ['name', 'makine', 'tarih', 'onay', 'docstatus', 'creation'],
        order_by: 'creation desc',
        limit_page_length: 10
      }
    });

    maintenanceRecords.value = result.message || [];
  } catch (error) {
    console.error('Error loading maintenance records:', error);
    maintenanceRecords.value = [];
  } finally {
    loading.value = false;
  }
}

// Load records on mount
loadMaintenanceRecords();

function openMaintenanceRecord(recordName: string) {
  frappe.set_route('Form', 'Makine Gunluk Bakim Formu', recordName);
}
</script>

<template>
  <div class="ck-card">
    <div class="ck-view-action">
      <b style="font-size: 15px;">Makine Günlük Bakım</b>
      <button class="ck-btn ck-btn--ghost ck-btn-small" @click="openMaintenanceDialog">
        + Ekle
      </button>
    </div>

    <div v-if="loading" class="ck-empty-state">
      Yükleniyor...
    </div>

    <div v-else-if="maintenanceRecords.length === 0" class="ck-empty-state">
      Henüz bakım kaydı yok.
    </div>

    <div v-else class="ck-mini-list">
      <div v-for="record in maintenanceRecords" :key="record.name" class="ck-mini-item" @click="openMaintenanceRecord(record.name)" style="cursor: pointer;">
        <div class="ck-mini-content">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <b class="ck-mini-title">{{ record.name }}</b>
            <span class="ck-status-pill" :class="record.docstatus === 1 ? 'is-success' : 'is-warning'">
              {{ record.docstatus === 1 ? 'Onaylandı' : 'Taslak' }}
            </span>
          </div>
          <div class="ck-muted ck-mini-sub">Makine: <strong style="color:var(--ck-text);">{{ record.makine }}</strong></div>
          <div class="ck-muted ck-mini-sub">Tarih: {{ frappe.datetime.str_to_user(record.tarih) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ck-view-action {
  padding: 6px 14px 14px 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid rgba(128,128,128,0.1);
  margin-bottom: 10px;
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
.ck-mini-content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
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
.ck-btn-small {
  padding: 6px 14px;
  font-size: 13px;
  border-radius: 8px;
  font-weight: 700;
}
.ck-status-pill {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
.ck-status-pill.is-success {
  background: rgba(34, 197, 94, 0.12);
  color: var(--success, #22c55e);
  border: 1px solid rgba(34, 197, 94, 0.2);
}
.ck-status-pill.is-warning {
  background: rgba(245, 158, 11, 0.12);
  color: var(--warning, #f59e0b);
  border: 1px solid rgba(245, 158, 11, 0.2);
}
</style>
