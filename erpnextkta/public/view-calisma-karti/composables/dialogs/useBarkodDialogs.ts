import { barkodKayitFields } from "../prompts";

export function useBarkodDialogs(props: any) {
  const __ = (...args: any[]) => (window as any).__(...args);
  const frappe = (window as any).frappe;

  function addBarkod() {
    frappe.prompt(
      barkodKayitFields(),
      async (v: any) => {
        await props.onAddBarkod({ barcode: v.barcode });
        frappe.show_alert({ message: __("Barkod kaydı eklendi"), indicator: "green" });
      },
      "Barkod Kaydı Ekle",
      __("Kaydet")
    );
  }

  function editBarkod(row: any) {
    if (!row?.name) return frappe.msgprint(__("Barkod satır kimliği (row name) bulunamadı."));
    frappe.prompt(
      barkodKayitFields(row),
      async (v: any) => {
        await props.onUpdateBarkod({ rowname: row.name, barcode: v.barcode });
        frappe.show_alert({ message: __("Barkod kaydı güncellendi"), indicator: "green" });
      },
      "Barkod Kaydı Düzenle",
      __("Kaydet")
    );
  }

  function deleteBarkod(row: any) {
    if (!row?.name) return frappe.msgprint(__("Barkod satır kimliği (row name) bulunamadı."));
    frappe.confirm(__("Bu barkod satırı silinecek. Emin misiniz?"), async () => {
      await props.onDeleteBarkod(row.name);
      frappe.show_alert({ message: __("Barkod kaydı silindi"), indicator: "green" });
    });
  }

  return {
    addBarkod,
    editBarkod,
    deleteBarkod,
  };
}
