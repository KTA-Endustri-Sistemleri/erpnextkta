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
            label: 'Makine (Asset)',
            options: 'Asset',
            reqd: 1,
            description: 'Bakım yapılacak makineyi seçin'
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
    <div class="ck-qc-header">
      <b>Makine Günlük Bakım</b>
      <button class="ck-btn ck-btn--primary" style="background: var(--btn-default-hover-bg);padding: 8px 10px;" @click="openMaintenanceDialog">
        + Ekle
      </button>
    </div>

    <div v-if="loading" class="ck-muted" style="margin-top: 14px;padding: 0px 6px;">
      Yükleniyor...
    </div>

    <div v-else-if="maintenanceRecords.length === 0" class="ck-muted" style="margin-top: 14px;padding: 0px 6px;">
      Henüz bakım kaydı yok.
    </div>

    <div v-else class="ck-mini-list" style="margin-top:8px;">
      <div v-for="record in maintenanceRecords" :key="record.name" class="ck-mini-item" @click="openMaintenanceRecord(record.name)" style="cursor: pointer;">
        <div style="display:flex; flex-direction:column; gap:8px;">
          <div class="ck-row">
            <span style="font-size: 14px; font-weight: 500;">Kayıt No:</span>
            <b style="font-size: 14px;">{{ record.name }}</b>
          </div>
          <div class="ck-row">
            <span>Makine:</span>
            <b>{{ record.makine }}</b>
          </div>
          <div class="ck-row">
            <span>Tarih:</span>
            <b>{{ frappe.datetime.str_to_user(record.tarih) }}</b>
          </div>
          <div class="ck-row">
            <span>Durum:</span>
            <b :style="{ color: record.docstatus === 1 ? 'var(--green)' : 'var(--orange)' }">
              {{ record.docstatus === 1 ? 'Onaylandı' : 'Taslak' }}
            </b>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
