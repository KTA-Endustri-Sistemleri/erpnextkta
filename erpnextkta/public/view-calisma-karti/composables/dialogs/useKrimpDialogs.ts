import { krimpOlcumFields } from "../prompts";
import { printKrimpProtocol as printKrimpProtocolUtil } from "../../utils/print_protocols";

export function useKrimpDialogs(props: any) {
  const __ = (...args: any[]) => (window as any).__(...args);
  const frappe = (window as any).frappe;

  function setupKrimpBookLogic(dialog: any) {
    const kesit_fld = dialog.get_field("kablo_kesiti");
    const kablo_fld = dialog.get_field("kablo_no");
    const kontak_fld = dialog.get_field("kontak_no");
    
    const yon_2_kontak_fld = dialog.get_field("yon_2_kontak_no");
    const yon_2_kesit_fld = dialog.get_field("yon_2_kablo_kesiti");
    
    dialog.last_kesit = dialog.get_value("kablo_kesiti");
    dialog.last_kablo = dialog.get_value("kablo_no");
    dialog.last_kontak = dialog.get_value("kontak_no");
    dialog.last_yon_2_kontak = dialog.get_value("yon_2_kontak_no");
    dialog.last_yon_2_kesit = dialog.get_value("yon_2_kablo_kesiti");

    const updateDetails = () => {
      const kesit = dialog.get_value("kablo_kesiti");
      const kontak = dialog.get_value("kontak_no");

      if (kesit && kontak) {
        frappe.call({
          method: "erpnextkta.kta_calisma_karti.api.get_krimp_book_details",
          args: { kablo_no: dialog.get_value("kablo_no") || "", kontak_no: kontak, selected_kesit: kesit },
          callback: (r: any) => {
            if (r.message && Object.keys(r.message).length > 0) {
              const data = r.message;
              dialog.set_value("hedef_iletken_krimp_yuksekliği", data.hedef_iletken_krimp_yuksekliği);
              dialog.set_value("hedef_cekme_kuvveti_n", data.hedef_cekme_kuvveti_n);
              dialog.set_value("izokrimp_yuksekligi", data.izokrimp_yuksekligi);
              frappe.show_alert({ message: __("Krimp Book değerleri yüklendi"), indicator: "blue" });
            }
          }
        });
        // Load kalip options separately so user can choose when multiple exist
        frappe.call({
          method: "erpnextkta.kta_calisma_karti.api.get_kalip_list",
          args: { kontak_no: kontak, selected_kesit: kesit },
          callback: (r: any) => {
            const list: string[] = r.message || [];
            dialog.set_df_property("kalip_no", "options", ["", ...list]);
            if (list.length === 1) {
              dialog.set_value("kalip_no", list[0]);
            } else if (list.length > 1) {
              dialog.set_value("kalip_no", "");
            } else {
              dialog.set_value("kalip_no", "");
            }
          }
        });
      } else {
        dialog.set_value("kalip_no", "");
        dialog.set_df_property("kalip_no", "options", [""]);
        dialog.set_value("hedef_iletken_krimp_yuksekliği", 0);
        dialog.set_value("hedef_cekme_kuvveti_n", 0);
        dialog.set_value("izokrimp_yuksekligi", 0);
      }
    };

    const updateYon2Details = () => {
      const kesit = dialog.get_value("yon_2_kablo_kesiti");
      const kontak = dialog.get_value("yon_2_kontak_no");

      if (kesit && kontak) {
        frappe.call({
          method: "erpnextkta.kta_calisma_karti.api.get_krimp_book_details",
          args: { kablo_no: dialog.get_value("kablo_no") || "", kontak_no: kontak, selected_kesit: kesit },
          callback: (r: any) => {
            if (r.message && Object.keys(r.message).length > 0) {
              const data = r.message;
              dialog.set_value("yon_2_hedef_iletken_krimp_yuksekligi", data.hedef_iletken_krimp_yuksekliği);
              dialog.set_value("yon_2_hedef_cekme_kuvveti_n", data.hedef_cekme_kuvveti_n);
              dialog.set_value("yon_2_izokrimp_yuksekligi", data.izokrimp_yuksekligi);
              frappe.show_alert({ message: __("T2 Krimp Book değerleri yüklendi"), indicator: "blue" });
            }
          }
        });
        // Load T2 kalip options
        frappe.call({
          method: "erpnextkta.kta_calisma_karti.api.get_kalip_list",
          args: { kontak_no: kontak, selected_kesit: kesit },
          callback: (r: any) => {
            const list: string[] = r.message || [];
            dialog.set_df_property("yon_2_kalip_no", "options", ["", ...list]);
            if (list.length === 1) {
              dialog.set_value("yon_2_kalip_no", list[0]);
            } else {
              dialog.set_value("yon_2_kalip_no", "");
            }
          }
        });
      } else {
        dialog.set_value("yon_2_kalip_no", "");
        dialog.set_df_property("yon_2_kalip_no", "options", [""]);
        dialog.set_value("yon_2_hedef_iletken_krimp_yuksekligi", 0);
        dialog.set_value("yon_2_hedef_cekme_kuvveti_n", 0);
        dialog.set_value("yon_2_izokrimp_yuksekligi", 0);
      }
    };

    if (kontak_fld) {
      kontak_fld.df.onchange = () => {
        const current_kontak = dialog.get_value("kontak_no");
        if (dialog.last_kontak === current_kontak) return;
        dialog.last_kontak = current_kontak;
        dialog.set_value("kablo_kesiti", "");
        // dialog.set_value("kablo_no", ""); // do not clear kablo_no
        if (current_kontak) {
          frappe.call({
            method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
            args: { kontak_no: current_kontak },
            callback: (r: any) => {
              if (r.message) {
          dialog.set_df_property("kablo_kesiti", "options", ["", ...r.message]);
          dialog.set_df_property("yon_2_kablo_kesiti", "options", ["", ...r.message]);
        }
            }
          });
        } else {
          frappe.call({
            method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
            callback: (r: any) => {
              if (r.message) dialog.set_df_property("kablo_kesiti", "options", ["", ...r.message]);
            }
          });
        }
        updateDetails();
      };
    }

    if (kesit_fld) {
      kesit_fld.df.onchange = () => {
        const current_kesit = dialog.get_value("kablo_kesiti");
        if (dialog.last_kesit === current_kesit) return;
        dialog.last_kesit = current_kesit;
        // dialog.set_value("kablo_no", ""); // do not clear kablo_no
        updateDetails();
      };
    }

    if (kablo_fld) {
      kablo_fld.df.onchange = () => {
        const current = dialog.get_value("kablo_no");
        if (dialog.last_kablo === current) return;
        dialog.last_kablo = current;
        updateDetails();
      };
    }

    if (yon_2_kontak_fld) {
      yon_2_kontak_fld.df.onchange = () => {
        const current_kontak = dialog.get_value("yon_2_kontak_no");
        if (dialog.last_yon_2_kontak === current_kontak) return;
        dialog.last_yon_2_kontak = current_kontak;
        dialog.set_value("yon_2_kablo_kesiti", "");
        if (current_kontak) {
          frappe.call({
            method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
            args: { kontak_no: current_kontak },
            callback: (r: any) => {
              if (r.message) dialog.set_df_property("yon_2_kablo_kesiti", "options", ["", ...r.message]);
            }
          });
        } else {
          frappe.call({
            method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
            callback: (r: any) => {
              if (r.message) dialog.set_df_property("yon_2_kablo_kesiti", "options", ["", ...r.message]);
            }
          });
        }
        updateYon2Details();
      };
    }

    if (yon_2_kesit_fld) {
      yon_2_kesit_fld.df.onchange = () => {
        const current_kesit = dialog.get_value("yon_2_kablo_kesiti");
        if (dialog.last_yon_2_kesit === current_kesit) return;
        dialog.last_yon_2_kesit = current_kesit;
        updateYon2Details();
      };
    }

    const altOpFld = dialog.get_field("alt_operasyon_kaydi");
    if (altOpFld) {
      altOpFld.df.onchange = () => {
        const rowId = dialog.get_value("alt_operasyon_kaydi");
        const altOpRow = getAltOpRow(rowId);
        if (altOpRow) {
          const sides = resolveAltOpSides(altOpRow);
          if (sides) {
            dialog.set_value("is_cift_tarafli", sides.is_cift ? 1 : 0);
            dialog.set_value("kontak_no", sides.t1.kontak);
            dialog.set_value("siyirma_boyu", sides.t1.siyirma);
            if (sides.is_cift && sides.t2) {
              dialog.set_value("yon_2_kontak_no", sides.t2.kontak);
              dialog.set_value("yon_2_siyirma_boyu", sides.t2.siyirma);
            } else {
              dialog.set_value("yon_2_kontak_no", "");
              dialog.set_value("yon_2_siyirma_boyu", 0);
            }
          }
          if (altOpRow.hammadde) dialog.set_value("kablo_no", altOpRow.hammadde);
          if (altOpRow.satir_no) dialog.set_value("satir_no", altOpRow.satir_no);
          if (altOpRow.boyut_1_mm) dialog.set_value("hedef_kablo_boyu", parseFloat(altOpRow.boyut_1_mm));
        }
      };
    }
  }

  /** Resolve alt operasyon row from doc by name */
  function getAltOpRow(altOpKaydiName?: string) {
    if (!altOpKaydiName) return null;
    return (props.doc.alt_operasyon_kayitlari || []).find(
      (r: any) => r.name === altOpKaydiName
    ) || null;
  }

  function resolveAltOpSides(altOpRow: any) {
    if (!altOpRow) return null;
    const solKontak = (altOpRow.hammadde_2 || "").trim();
    const sagKontak = (altOpRow.hammadde_3 || "").trim();
    const solSiyirma = parseFloat(altOpRow.boyut_2_mm || 0);
    const sagSiyirma = parseFloat(altOpRow.boyut_3_mm || 0);

    const is_cift = !!(sagKontak || sagSiyirma > 0 || altOpRow.operasyon_tipi === "Çift Taraf");

    return { 
      is_cift: is_cift, 
      t1: { kontak: solKontak, siyirma: solSiyirma }, 
      t2: { kontak: sagKontak, siyirma: sagSiyirma } 
    };
  }

  function addKrimp(altOpKaydiName?: string) {
    const altOpOptions = [
      "",
      ...(props.doc.alt_operasyon_kayitlari || [])
        .map((r: any) => ({
          label: r.alt_operasyon_title || r.alt_operasyon,
          value: r.name
        }))
    ];

    const altOpRow = getAltOpRow(altOpKaydiName);
    const sides = resolveAltOpSides(altOpRow);

    const defaults: any = {
      calisma_karti_name: props.doc.name,
      alt_op_options: altOpOptions,
      alt_operasyon_kaydi: altOpKaydiName || ""
    };

    if (sides) {
      defaults.is_cift_tarafli = sides.is_cift ? 1 : 0;
      defaults.kontak_no = sides.t1.kontak;
      defaults.siyirma_boyu = sides.t1.siyirma;
      if (sides.is_cift && sides.t2) {
        defaults.yon_2_kontak_no = sides.t2.kontak;
        defaults.yon_2_siyirma_boyu = sides.t2.siyirma;
      }
    }
    
    if (altOpRow) {
      defaults.kablo_no = altOpRow.hammadde || "";
      defaults.satir_no = altOpRow.satir_no || "";
      defaults.hedef_kablo_boyu = parseFloat(altOpRow.boyut_1_mm || 0);
    }

    const dialog = frappe.prompt(
      krimpOlcumFields(defaults),
      async (v: any) => {
        await props.onAddKrimp(v);
        frappe.show_alert({ message: __("Krimp ölçümü eklendi"), indicator: "green" });
      },
      __("Krimp Ölçümü Ekle"),
      __("Kaydet")
    );

    dialog.fields_dict.kablo_no.get_query = () => ({
      query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
      filters: { calisma_karti: props.doc.name, kablo_kesiti: dialog.get_value("kablo_kesiti"), type: "kablo" }
    });
    dialog.fields_dict.kontak_no.get_query = () => ({
      query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
      filters: { calisma_karti: props.doc.name, kablo_kesiti: dialog.get_value("kablo_kesiti"), type: "kontak" }
    });
    if (dialog.fields_dict.yon_2_kontak_no) {
      dialog.fields_dict.yon_2_kontak_no.get_query = () => ({
        query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
        filters: { calisma_karti: props.doc.name, kablo_kesiti: dialog.get_value("yon_2_kablo_kesiti"), type: "kontak" }
      });
    }

    dialog.is_loading = true;
    frappe.call({
      method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
      callback: (r: any) => {
        if (r.message) dialog.set_df_property("kablo_kesiti", "options", ["", ...r.message]);
        dialog.is_loading = false;

        // If we have a terminal, fetch kesit list for it and pre-load kalip options
        const currentKontak = dialog.get_value("kontak_no");
        if (currentKontak) {
          frappe.call({
            method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
            args: { kontak_no: currentKontak },
            callback: (r2: any) => {
              if (r2.message) {
                dialog.set_df_property("kablo_kesiti", "options", ["", ...r2.message]);
                // Auto-select if only one kesit available
                if (r2.message.length === 1) {
                  dialog.set_value("kablo_kesiti", r2.message[0]);
                }
              }
            }
          });
        }
      }
    });
    setupKrimpBookLogic(dialog);
  }

  async function editKrimp(row: any) {
    if (!row?.name) return frappe.msgprint(__("Krimp satır kimliği bulunamadı."));

    const altOpOptions = [
      "",
      ...(props.doc.alt_operasyon_kayitlari || [])
        .map((r: any) => ({
          label: r.alt_operasyon_title || r.alt_operasyon,
          value: r.name
        }))
    ];

    let isKutKablo = false;
    const altOpRow = props.doc.alt_operasyon_kayitlari?.find((r: any) => r.name === row.alt_operasyon_kaydi);
    if (altOpRow && altOpRow.alt_operasyon) {
      isKutKablo = await frappe.call({
        method: "erpnextkta.kta_calisma_karti.api.is_kut_kablo_operation",
        args: { operasyon_name: altOpRow.alt_operasyon }
      }).then((r: any) => r.message || false);
    }

    const dialog = frappe.prompt(
      krimpOlcumFields({ ...row, calisma_karti_name: props.doc.name, isKutKablo, alt_op_options: altOpOptions }),
      async (v: any) => {
        await props.onUpdateKrimp({ rowname: row.name, payload: v });
        frappe.show_alert({ message: __("Krimp ölçümü güncellendi"), indicator: "green" });
      },
      __("Krimp Ölçümü Düzenle"),
      __("Kaydet")
    );

    dialog.fields_dict.kablo_no.get_query = () => ({
      query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
      filters: { calisma_karti: props.doc.name, kablo_kesiti: dialog.get_value("kablo_kesiti"), type: "kablo" }
    });
    dialog.fields_dict.kontak_no.get_query = () => ({
      query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
      filters: { calisma_karti: props.doc.name, kablo_kesiti: dialog.get_value("kablo_kesiti"), type: "kontak" }
    });
    if (dialog.fields_dict.yon_2_kontak_no) {
      dialog.fields_dict.yon_2_kontak_no.get_query = () => ({
        query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
        filters: { calisma_karti: props.doc.name, kablo_kesiti: dialog.get_value("yon_2_kablo_kesiti"), type: "kontak" }
      });
    }

    dialog.is_loading = true;
    frappe.call({
      method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
      callback: (r: any) => {
        if (r.message) {
          dialog.set_df_property("kablo_kesiti", "options", ["", ...r.message]);
          dialog.set_df_property("yon_2_kablo_kesiti", "options", ["", ...r.message]);
          const currentVal = row.kablo_kesiti;
          if (currentVal) dialog.set_value("kablo_kesiti", currentVal);
          const currentYon2Val = row.yon_2_kablo_kesiti;
          if (currentYon2Val) dialog.set_value("yon_2_kablo_kesiti", currentYon2Val);
        }
        dialog.is_loading = false;

        // Pre-load kalip options for T1 if kontak + kesit available
        const kontak = row.kontak_no;
        const kesit = row.kablo_kesiti;
        if (kontak && kesit) {
          frappe.call({
            method: "erpnextkta.kta_calisma_karti.api.get_kalip_list",
            args: { kontak_no: kontak, selected_kesit: kesit },
            callback: (r2: any) => {
              const list: string[] = r2.message || [];
              const current = row.kalip_no || "";
              const opts = list.length ? ["", ...list] : (current ? ["", current] : [""]);
              dialog.set_df_property("kalip_no", "options", opts);
              if (current) dialog.set_value("kalip_no", current);
            }
          });
        }

        // Pre-load kalip options for T2
        const yon2Kontak = row.yon_2_kontak_no;
        const yon2Kesit = row.yon_2_kablo_kesiti;
        if (yon2Kontak && yon2Kesit) {
          frappe.call({
            method: "erpnextkta.kta_calisma_karti.api.get_kalip_list",
            args: { kontak_no: yon2Kontak, selected_kesit: yon2Kesit },
            callback: (r2: any) => {
              const list: string[] = r2.message || [];
              const current = row.yon_2_kalip_no || "";
              const opts = list.length ? ["", ...list] : (current ? ["", current] : [""]);
              dialog.set_df_property("yon_2_kalip_no", "options", opts);
              if (current) dialog.set_value("yon_2_kalip_no", current);
            }
          });
        }
      }
    });
    setupKrimpBookLogic(dialog);
  }

  function deleteKrimp(row: any) {
    if (!row?.name) return frappe.msgprint(__("Krimp satır kimliği bulunamadı."));
    frappe.confirm(__("Bu krimp ölçüm satırı silinecek. Emin misiniz?"), async () => {
      await props.onDeleteKrimp(row.name);
      frappe.show_alert({ message: __("Krimp ölçümü silindi"), indicator: "green" });
    });
  }

  function cloneKrimp(row: any) {
    const altOpOptions = [
      "",
      ...(props.doc.alt_operasyon_kayitlari || [])
        .map((r: any) => ({
          label: r.alt_operasyon_title || r.alt_operasyon,
          value: r.name
        }))
    ];

    const cloneDefaults = {
      calisma_karti_name: props.doc.name,
      alt_op_options: altOpOptions,
      alt_operasyon_kaydi: row.alt_operasyon_kaydi || "",
      kablo_kesiti: row.kablo_kesiti || "",
      kablo_no: row.kablo_no || "",
      kontak_no: row.kontak_no || "",
      kalip_no: row.kalip_no || "",
      makine_pres_no: row.makine_pres_no || "",
      hedef_kablo_boyu: row.hedef_kablo_boyu ?? 0,
      hedef_iletken_krimp_yuksekliği: row.hedef_iletken_krimp_yuksekliği ?? 0,
      hedef_cekme_kuvveti_n: row.hedef_cekme_kuvveti_n ?? 0,
      olculen_cekme_kuvveti_n: row.olculen_cekme_kuvveti_n ?? 0,
      izokrimp_yuksekligi: row.izokrimp_yuksekligi ?? 0,
      radus_mevcut: row.radus_mevcut ?? 0,
      tel_kesme_mevcut: row.tel_kesme_mevcut ?? 0,
      olculen_kablo_boyu: 0,
      olculen_iletken_krimp_yuksekliği: 0,
      siyirma_boyu: 0,
      capak_boyu: 0,

      yon_2_kablo_kesiti: row.yon_2_kablo_kesiti || "",
      yon_2_kontak_no: row.yon_2_kontak_no || "",
      yon_2_kalip_no: row.yon_2_kalip_no || "",
            yon_2_hedef_iletken_krimp_yuksekligi: row.yon_2_hedef_iletken_krimp_yuksekligi ?? 0,
      yon_2_hedef_cekme_kuvveti_n: row.yon_2_hedef_cekme_kuvveti_n ?? 0,
      yon_2_izokrimp_yuksekligi: row.yon_2_izokrimp_yuksekligi ?? 0,
      yon_2_radus_mevcut: row.yon_2_radus_mevcut ?? 0,
      yon_2_tel_kesme_mevcut: row.yon_2_tel_kesme_mevcut ?? 0,

      yon_2_olculen_iletken_krimp_yuksekligi: 0,
      yon_2_olculen_cekme_kuvveti_n: 0,
      yon_2_siyirma_boyu: 0,
      yon_2_capak_boyu: 0,
    };

    const dialog = frappe.prompt(
      krimpOlcumFields(cloneDefaults),
      async (v: any) => {
        await props.onAddKrimp(v);
        frappe.show_alert({ message: __("Krimp ölçümü kopyalandı ve eklendi"), indicator: "green" });
      },
      __("Krimp Ölçümü Kopyala"),
      __("Kaydet")
    );

    dialog.fields_dict.kablo_no.get_query = () => ({
      query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
      filters: { calisma_karti: props.doc.name, kablo_kesiti: dialog.get_value("kablo_kesiti"), type: "kablo" }
    });
    dialog.fields_dict.kontak_no.get_query = () => ({
      query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
      filters: { calisma_karti: props.doc.name, kablo_kesiti: dialog.get_value("kablo_kesiti"), type: "kontak" }
    });
    if (dialog.fields_dict.yon_2_kontak_no) {
      dialog.fields_dict.yon_2_kontak_no.get_query = () => ({
        query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
        filters: { calisma_karti: props.doc.name, kablo_kesiti: dialog.get_value("yon_2_kablo_kesiti"), type: "kontak" }
      });
    }

    dialog.is_loading = true;
    frappe.call({
      method: "erpnextkta.kta_calisma_karti.api.get_unique_kesit_list",
      callback: (r: any) => {
        if (r.message) {
          dialog.set_df_property("kablo_kesiti", "options", ["", ...r.message]);
          dialog.set_df_property("yon_2_kablo_kesiti", "options", ["", ...r.message]);
          if (cloneDefaults.kablo_kesiti) dialog.set_value("kablo_kesiti", cloneDefaults.kablo_kesiti);
          if (cloneDefaults.yon_2_kablo_kesiti) dialog.set_value("yon_2_kablo_kesiti", cloneDefaults.yon_2_kablo_kesiti);
        }
        dialog.is_loading = false;
      }
    });
    setupKrimpBookLogic(dialog);
  }

  function printKrimpProtocol() { 
    printKrimpProtocolUtil(props.doc); 
  }

  return {
    addKrimp,
    editKrimp,
    deleteKrimp,
    cloneKrimp,
    printKrimpProtocol
  };
}
