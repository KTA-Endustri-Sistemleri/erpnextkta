import { hurdaFields } from "../prompts";

export function useHurdaDialogs(props: any) {
  const __ = (...args: any[]) => (window as any).__(...args);
  const frappe = (window as any).frappe;

  let cachedNedenler: string[] | null = null;

  async function getNedenOptions(): Promise<string[]> {
    if (cachedNedenler && cachedNedenler.length > 0) {
      return cachedNedenler;
    }
    try {
      const r = await frappe.call("erpnextkta.kta_calisma_karti.api_impl.hurda.get_hurda_nedeni_options");
      cachedNedenler = r.message || [];
      return cachedNedenler || [];
    } catch {
      return [];
    }
  }

  async function addHurda() {
    const hurdaNedenleri = await getNedenOptions();
    frappe.prompt(
      hurdaFields({
        calisma_karti_name: props.doc.name,
        hurda_nedenleri: hurdaNedenleri,
      }),
      async (v: any) => {
        if (!v.parca_no) return frappe.msgprint(__("Lütfen bir parça seçin."));
        if (!v.hurda_nedeni) return frappe.msgprint(__("Lütfen bir hurda nedeni seçin."));
        if (!v.miktar || Number(v.miktar) <= 0) return frappe.msgprint(__("Lütfen geçerli bir miktar girin."));

        await props.onAdd({
          parca_no: v.parca_no,
          hurda_nedeni: v.hurda_nedeni,
          miktar: Number(v.miktar),
          aciklama: v.aciklama || null,
        });
        frappe.show_alert({ message: __("Hurda eklendi"), indicator: "green" });
      },
      __("Hurda Ekle"),
      __("Kaydet")
    );
  }

  async function editHurda(row: any) {
    if (!row?.name) return frappe.msgprint(__("Hurda satır kimliği (row name) bulunamadı."));
    const hurdaNedenleri = await getNedenOptions();

    frappe.prompt(
      hurdaFields({
        ...row,
        calisma_karti_name: props.doc.name,
        hurda_nedenleri: hurdaNedenleri,
        is_edit: true,
      }),
      async (v: any) => {
        if (!v.parca_no) return frappe.msgprint(__("Lütfen bir parça seçin."));
        if (!v.hurda_nedeni) return frappe.msgprint(__("Lütfen bir hurda nedeni seçin."));
        if (!v.miktar || Number(v.miktar) <= 0) return frappe.msgprint(__("Lütfen geçerli bir miktar girin."));

        await props.onUpdate({
          rowname: row.name,
          parca_no: v.parca_no,
          hurda_nedeni: v.hurda_nedeni,
          miktar: Number(v.miktar),
          aciklama: v.aciklama || null,
        });
        frappe.show_alert({ message: __("Hurda güncellendi"), indicator: "green" });
      },
      __("Hurda Düzenle"),
      __("Kaydet")
    );
  }

  function deleteHurda(row: any) {
    if (!row?.name) return frappe.msgprint(__("Hurda satır kimliği (row name) bulunamadı."));
    frappe.confirm(__("Bu hurda satırı silinecek. Emin misiniz?"), async () => {
      await props.onDelete(row.name);
      frappe.show_alert({ message: __("Hurda silindi"), indicator: "green" });
    });
  }

  return {
    addHurda,
    editHurda,
    deleteHurda,
  };
}
