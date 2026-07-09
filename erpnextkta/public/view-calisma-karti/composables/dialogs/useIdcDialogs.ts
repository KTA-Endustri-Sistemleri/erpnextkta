import { idcOlcumFields } from "../prompts";
import { printIdcProtocol as printIdcProtocolUtil } from "../../utils/print_protocols";

export function useIdcDialogs(props: any) {
  const __ = (...args: any[]) => (window as any).__(...args);
  const frappe = (window as any).frappe;

  function addIdc() {
    frappe.prompt(
      idcOlcumFields(props.doc.name),
      async (v: any) => {
        await props.onAddIdc({
          item_code: v.item_code,
          yukseklik_mm: v.yukseklik_mm,
          cekme_n: v.cekme_n,
        });
        frappe.show_alert({ message: __("IDC ölçümü eklendi"), indicator: "green" });
      },
      __("IDC Ölçümü Ekle"),
      __("Kaydet")
    );
  }

  function editIdc(row: any) {
    if (!row?.name) return frappe.msgprint(__("IDC satır kimliği (row name) bulunamadı."));
    frappe.prompt(
      idcOlcumFields(props.doc.name, row),
      async (v: any) => {
        await props.onUpdateIdc({
          rowname: row.name,
          item_code: v.item_code,
          yukseklik_mm: v.yukseklik_mm,
          cekme_n: v.cekme_n,
        });
        frappe.show_alert({ message: __("IDC ölçümü güncellendi"), indicator: "green" });
      },
      __("IDC Ölçümü Düzenle"),
      __("Kaydet")
    );
  }

  function deleteIdc(row: any) {
    if (!row?.name) return frappe.msgprint(__("IDC satır kimliği (row name) bulunamadı."));
    frappe.confirm(__("Bu IDC ölçüm satırı silinecek. Emin misiniz?"), async () => {
      await props.onDeleteIdc(row.name);
      frappe.show_alert({ message: __("IDC ölçümü silindi"), indicator: "green" });
    });
  }

  function cloneIdc(row: any) {
    frappe.prompt(
      idcOlcumFields(props.doc.name, row),
      async (v: any) => {
        await props.onAddIdc({
          item_code: v.item_code,
          yukseklik_mm: v.yukseklik_mm,
          cekme_n: v.cekme_n,
        });
        frappe.show_alert({ message: __("IDC ölçümü kopyalandı ve eklendi"), indicator: "green" });
      },
      __("IDC Ölçümü Kopyala"),
      __("Kaydet")
    );
  }

  function printIdcProtocol() { 
    printIdcProtocolUtil(props.doc); 
  }

  return {
    addIdc,
    editIdc,
    deleteIdc,
    cloneIdc,
    printIdcProtocol
  };
}
