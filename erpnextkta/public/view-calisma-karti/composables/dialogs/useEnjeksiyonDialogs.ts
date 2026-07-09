import { enjeksiyonOlcumFields } from "../prompts";
import { printEnjeksiyonProtocol as printEnjeksiyonProtocolUtil } from "../../utils/print_protocols";

export function useEnjeksiyonDialogs(props: any) {
  const __ = (...args: any[]) => (window as any).__(...args);
  const frappe = (window as any).frappe;

  function setupEnjeksiyonToleransLogic(dialog: any) {
    const hammadde_fld = dialog.get_field("hammadde_no");
    dialog.enjeksiyon_tolerans = {}; // store fetched limits

    const updateDetails = () => {
      const hammadde = dialog.get_value("hammadde_no");
      if (hammadde) {
        frappe.call({
          method: "erpnextkta.kta_calisma_karti.api.get_enjeksiyon_tolerans",
          args: { hammadde_no: hammadde },
          callback: (r: any) => {
            if (r.message && Object.keys(r.message).length > 0) {
              dialog.enjeksiyon_tolerans = r.message;
              const t = r.message;
              
              const desc = (val: number, tol?: number) => val ? `İstenen: ${val} ${tol ? `±${tol}` : ''}` : '';
              const descRange = (min: number, max: number) => min || max ? `İstenen: ${min} - ${max}` : '';
              const descMin = (min: number) => min ? `Minimum: ${min}` : '';

              dialog.set_df_property("hammadde_kazan_isisi", "description", desc(t.hammadde_kazan_isisi_merkez, t.hammadde_kazan_isisi_tolerans));
              dialog.set_df_property("ara_hortum_isisi", "description", desc(t.ara_hortum_isisi_merkez, t.ara_hortum_isisi_tolerans));
              dialog.set_df_property("kafa_meme_isisi", "description", desc(t.kafa_meme_isisi_merkez, t.kafa_meme_isisi_tolerans));
              dialog.set_df_property("soguk_su_isisi", "description", descRange(t.soguk_su_isisi_min, t.soguk_su_isisi_maks));
              dialog.set_df_property("motor_devir", "description", descRange(t.motor_devir_min, t.motor_devir_maks));
              dialog.set_df_property("hammadde_enjeksiyon_zamani", "description", descRange(t.enjeksiyon_zamani_min, t.enjeksiyon_zamani_maks));
              dialog.set_df_property("sogutma_zamani", "description", descRange(t.sogutma_zamani_min, t.sogutma_zamani_maks));
              dialog.set_df_property("cekme_kuvveti_olculen", "description", descMin(t.cekme_kuvveti_min));

              frappe.show_alert({ message: __("Tolerans değerleri yüklendi"), indicator: "blue" });
            } else {
               dialog.enjeksiyon_tolerans = {};
               ["hammadde_kazan_isisi", "ara_hortum_isisi", "kafa_meme_isisi", "soguk_su_isisi", "motor_devir", "hammadde_enjeksiyon_zamani", "sogutma_zamani", "cekme_kuvveti_olculen"].forEach(f => {
                 dialog.set_df_property(f, "description", "");
               });
            }
          }
        });
      }
    };

    if (hammadde_fld) {
      hammadde_fld.df.onchange = updateDetails;
    }
  }

  function addEnjeksiyon() {
    const dialog = frappe.prompt(
      enjeksiyonOlcumFields({ calisma_karti_name: props.doc.name }),
      async (v: any) => {
        const payload = { ...v };
        if (dialog.enjeksiyon_tolerans) {
           Object.keys(dialog.enjeksiyon_tolerans).forEach(k => {
               payload[`hedef_${k}`] = dialog.enjeksiyon_tolerans[k];
           });
        }
        await props.onAddEnjeksiyon(payload);
        frappe.show_alert({ message: __("Enjeksiyon ölçümü eklendi"), indicator: "green" });
      },
      __("Enjeksiyon Ölçümü Ekle"),
      __("Kaydet")
    );
    setupEnjeksiyonToleransLogic(dialog);
  }

  function editEnjeksiyon(row: any) {
    if (!row?.name) return frappe.msgprint(__("Enjeksiyon satır kimliği bulunamadı."));
    const dialog = frappe.prompt(
      enjeksiyonOlcumFields({ ...row, calisma_karti_name: props.doc.name }),
      async (v: any) => {
        const payloadObj = { ...v };
        if (dialog.enjeksiyon_tolerans) {
           Object.keys(dialog.enjeksiyon_tolerans).forEach(k => {
               payloadObj[`hedef_${k}`] = dialog.enjeksiyon_tolerans[k];
           });
        }
        await props.onUpdateEnjeksiyon({ rowname: row.name, payload: payloadObj });
        frappe.show_alert({ message: __("Enjeksiyon ölçümü güncellendi"), indicator: "green" });
      },
      __("Enjeksiyon Ölçümü Düzenle"),
      __("Kaydet")
    );
    setupEnjeksiyonToleransLogic(dialog);
    if (row.hammadde_no) {
        setTimeout(() => dialog.get_field("hammadde_no").df.onchange(), 100);
    }
  }

  function deleteEnjeksiyon(row: any) {
    if (!row?.name) return frappe.msgprint(__("Enjeksiyon satır kimliği bulunamadı."));
    frappe.confirm(__("Bu enjeksiyon ölçüm satırı silinecek. Emin misiniz?"), async () => {
      await props.onDeleteEnjeksiyon(row.name);
      frappe.show_alert({ message: __("Enjeksiyon ölçümü silindi"), indicator: "green" });
    });
  }

  function cloneEnjeksiyon(row: any) {
    const cloneDefaults = {
      ...row,
      calisma_karti_name: props.doc.name,
    };

    const dialog = frappe.prompt(
      enjeksiyonOlcumFields(cloneDefaults),
      async (v: any) => {
        const payload = { ...v };
        if (dialog.enjeksiyon_tolerans) {
           Object.keys(dialog.enjeksiyon_tolerans).forEach(k => {
               payload[`hedef_${k}`] = dialog.enjeksiyon_tolerans[k];
           });
        }
        await props.onAddEnjeksiyon(payload);
        frappe.show_alert({ message: __("Enjeksiyon ölçümü kopyalandı ve eklendi"), indicator: "green" });
      },
      __("Enjeksiyon Ölçümü Kopyala"),
      __("Kaydet")
    );
    setupEnjeksiyonToleransLogic(dialog);
    if (row.hammadde_no) {
        setTimeout(() => dialog.get_field("hammadde_no").df.onchange(), 100);
    }
  }

  function printEnjeksiyonProtocol() { 
    printEnjeksiyonProtocolUtil(props.doc); 
  }

  return {
    addEnjeksiyon,
    editEnjeksiyon,
    deleteEnjeksiyon,
    cloneEnjeksiyon,
    printEnjeksiyonProtocol
  };
}
