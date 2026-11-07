import { enjeksiyonOlcumFields } from "../prompts";
import { printEnjeksiyonProtocol as printEnjeksiyonProtocolUtil } from "../../utils/print_protocols";

export function useEnjeksiyonDialogs(props: any) {
  const __ = (...args: any[]) => (window as any).__(...args);
  const frappe = (window as any).frappe;

  function setupEnjeksiyonToleransLogic(dialog: any, initialTolerans?: any) {
    const hammadde_fld = dialog.get_field("hammadde_no");
    dialog.enjeksiyon_tolerans = initialTolerans || null;

    const applyToleransUI = (t: any) => {
      if (t && Object.keys(t).length > 0) {
        dialog.enjeksiyon_tolerans = t;
        const desc = (val: number, tol?: number) => val ? `${__("İstenen")}: ${val}${tol ? ` ±${tol}` : ''}` : '';
        const descRange = (min: number, max: number) => min || max ? `${__("İstenen")}: ${min} - ${max}` : '';
        const descMin = (min: number) => min ? `${__("Minimum")}: ${min}` : '';

        dialog.set_df_property("hammadde_kazan_isisi", "description", desc(t.hammadde_kazan_isisi_merkez, t.hammadde_kazan_isisi_tolerans));
        dialog.set_df_property("ara_hortum_isisi", "description", desc(t.ara_hortum_isisi_merkez, t.ara_hortum_isisi_tolerans));
        dialog.set_df_property("kafa_meme_isisi", "description", desc(t.kafa_meme_isisi_merkez, t.kafa_meme_isisi_tolerans));
        dialog.set_df_property("soguk_su_isisi", "description", descRange(t.soguk_su_isisi_min, t.soguk_su_isisi_maks));
        dialog.set_df_property("motor_devir", "description", descRange(t.motor_devir_min, t.motor_devir_maks));
        dialog.set_df_property("hammadde_enjeksiyon_zamani", "description", descRange(t.enjeksiyon_zamani_min, t.enjeksiyon_zamani_maks));
        dialog.set_df_property("sogutma_zamani", "description", descRange(t.sogutma_zamani_min, t.sogutma_zamani_maks));
        dialog.set_df_property("cekme_kuvveti_olculen", "description", descMin(Math.max(100, t.cekme_kuvveti_min || 0)));
      } else {
        dialog.enjeksiyon_tolerans = null;
        ["hammadde_kazan_isisi", "ara_hortum_isisi", "kafa_meme_isisi", "soguk_su_isisi", "motor_devir", "hammadde_enjeksiyon_zamani", "sogutma_zamani", "cekme_kuvveti_olculen"].forEach(f => {
          dialog.set_df_property(f, "description", "");
        });
      }
    };

    if (initialTolerans) {
      applyToleransUI(initialTolerans);
    }

    const updateDetails = () => {
      const hammadde = dialog.get_value("hammadde_no");
      if (hammadde) {
        frappe.call({
          method: "erpnextkta.kta_calisma_karti.api.get_enjeksiyon_tolerans",
          args: { hammadde_no: hammadde },
          callback: (r: any) => {
            if (r.message && Object.keys(r.message).length > 0) {
              applyToleransUI(r.message);
              frappe.show_alert({ message: __("Tolerans değerleri yüklendi"), indicator: "blue" });
            } else {
              applyToleransUI(null);
              frappe.msgprint({
                title: __("Tolerans Tanımı Eksik"),
                message: __("'{0}' hammaddesi için enjeksiyon proses toleransları tanımlanmamış. Tolerans kaydı olmadan ölçüm girilemez.", [hammadde]),
                indicator: "red"
              });
            }
          }
        });
      } else {
        applyToleransUI(null);
      }
    };

    if (hammadde_fld) {
      hammadde_fld.df.onchange = updateDetails;
    }
  }

  function bindEnjeksiyonDialogAction(
    dialog: any,
    label: string,
    onSave: (values: any) => Promise<void>
  ) {
    dialog.set_primary_action(label, async () => {
      const values = dialog.get_values();
      if (!values) return;

      const t = dialog.enjeksiyon_tolerans;
      if (!t || Object.keys(t).length === 0) {
        frappe.msgprint({
          title: __("Tolerans Tanımı Eksik"),
          message: __("Seçili hammadde için enjeksiyon toleransları tanımlanmadığından ölçüm kaydedilemez."),
          indicator: "red"
        });
        return;
      }

      if (!values.goz_kontrol) {
        frappe.msgprint({
          title: __("Eksik Zorunlu Alan"),
          message: __("Göz Kontrol zorunludur."),
          indicator: "red"
        });
        return;
      }

      const requiredParams: { [key: string]: string } = {
        hammadde_kazan_isisi: __("Hammadde Kazan Isısı"),
        ara_hortum_isisi: __("Ara Hortum Isısı"),
        kafa_meme_isisi: __("Kafa (Meme) Isısı"),
        soguk_su_isisi: __("Soğuk Su Isısı"),
        motor_devir: __("Motor Devir"),
        hammadde_enjeksiyon_zamani: __("Hammadde Enjeksiyon Zamanı"),
        sogutma_zamani: __("Soğutma Zamanı"),
      };

      for (const [key, fieldLabel] of Object.entries(requiredParams)) {
        const val = Number(values[key]) || 0;
        if (val <= 0) {
          frappe.msgprint({
            title: __("Eksik Zorunlu Alan"),
            message: __("'{0}' alanı boş veya 0 bırakılamaz.", [fieldLabel]),
            indicator: "red"
          });
          return;
        }
      }

      const cekme = Number(values.cekme_kuvveti_olculen) || 0;
      const cekmeMin = Math.max(100, Number(t.cekme_kuvveti_min) || 0);
      if (cekme < cekmeMin) {
        frappe.msgprint({
          title: __("Tolerans Dışı Değer"),
          message: __("Çekme Kuvveti ({0} N) kabul edilen minimum değerin ({1} N) altındadır.", [cekme, cekmeMin]),
          indicator: "red"
        });
        return;
      }

      const centerTolChecks: [string, string, number, number, string][] = [
        ["hammadde_kazan_isisi", __("Hammadde Kazan Isısı"), Number(t.hammadde_kazan_isisi_merkez) || 0, Number(t.hammadde_kazan_isisi_tolerans) || 0, "°C"],
        ["ara_hortum_isisi", __("Ara Hortum Isısı"), Number(t.ara_hortum_isisi_merkez) || 0, Number(t.ara_hortum_isisi_tolerans) || 0, "°C"],
        ["kafa_meme_isisi", __("Kafa (Meme) Isısı"), Number(t.kafa_meme_isisi_merkez) || 0, Number(t.kafa_meme_isisi_tolerans) || 0, "°C"],
      ];

      for (const [key, label, merkez, tol, unit] of centerTolChecks) {
        const val = Number(values[key]) || 0;
        if (merkez > 0) {
          const minVal = merkez - tol;
          const maxVal = merkez + tol;
          if (val < minVal || val > maxVal) {
            frappe.msgprint({
              title: __("Tolerans Dışı Değer"),
              message: __("'{0}' ({1} {2}) tolerans sınırları dışındadır. Kabul edilen aralık: {3} - {4} {2}", [label, val, unit, minVal, maxVal]),
              indicator: "red"
            });
            return;
          }
        }
      }

      const rangeChecks: [string, string, number, number, string][] = [
        ["soguk_su_isisi", __("Soğuk Su Isısı"), Number(t.soguk_su_isisi_min) || 0, Number(t.soguk_su_isisi_maks) || 0, "°C"],
        ["motor_devir", __("Motor Devir"), Number(t.motor_devir_min) || 0, Number(t.motor_devir_maks) || 0, ""],
        ["hammadde_enjeksiyon_zamani", __("Hammadde Enjeksiyon Zamanı"), Number(t.enjeksiyon_zamani_min) || 0, Number(t.enjeksiyon_zamani_maks) || 0, "sn"],
        ["sogutma_zamani", __("Soğutma Zamanı"), Number(t.sogutma_zamani_min) || 0, Number(t.sogutma_zamani_maks) || 0, "sn"],
      ];

      for (const [key, label, minLim, maxLim, unit] of rangeChecks) {
        const val = Number(values[key]) || 0;
        if ((minLim > 0 && val < minLim) || (maxLim > 0 && val > maxLim)) {
          const uStr = unit ? ` ${unit}` : "";
          frappe.msgprint({
            title: __("Tolerans Dışı Değer"),
            message: __("'{0}' ({1}{2}) tolerans sınırları dışındadır. Kabul edilen aralık: {3} - {4}{2}", [label, val, uStr, minLim, maxLim]),
            indicator: "red"
          });
          return;
        }
      }

      dialog.hide();
      await onSave(values);
    });
  }

  function getAllowedPeriods(altOpKaydiName?: string, excludeRowName?: string): string[] {
    if (!altOpKaydiName) {
      return ["Başlangıç", "Ara", "Bitiş"];
    }
    const all = props.rows || props.doc?.enjeksiyon_olcumleri || [];
    const altOpRow = (props.doc?.alt_operasyon_kayitlari || []).find((r: any) => r.name === altOpKaydiName);

    const existing = all.filter((m: any) => {
      if (excludeRowName && m.name === excludeRowName) return false;
      if (m.alt_operasyon_kaydi) {
        return m.alt_operasyon_kaydi === altOpKaydiName;
      }
      if (altOpRow && m.kalip_no && altOpRow.kalip_no) {
        const sameKalip = String(m.kalip_no).trim().toLowerCase() === String(altOpRow.kalip_no).trim().toLowerCase();
        if (sameKalip && altOpRow.hammadde && m.hammadde_no) {
          return String(m.hammadde_no).trim().toLowerCase() === String(altOpRow.hammadde).trim().toLowerCase();
        }
        return sameKalip;
      }
      return false;
    });

    if (existing.length >= 3) return [];
    const used = new Set(existing.map((m: any) => m.kontrol_periyodu).filter(Boolean));
    if (!used.has("Başlangıç")) {
      return ["Başlangıç"];
    }
    return ["Ara", "Bitiş"].filter(p => !used.has(p));
  }

  async function addEnjeksiyon(defaultKalipNo?: string, defaultHammadde?: string, altOpKaydiName?: string) {
    if (altOpKaydiName) {
      const allowedCheck = getAllowedPeriods(altOpKaydiName);
      if (allowedCheck.length === 0) {
        frappe.msgprint({
          title: __("Ölçüm Limiti"),
          message: __("Bu alt operasyon için tüm periyot ölçümleri (Başlangıç, Ara, Bitiş) tamamlanmıştır."),
          indicator: "orange"
        });
        return;
      }
    }

    const altOpRow = altOpKaydiName
      ? (props.doc.alt_operasyon_kayitlari || []).find((r: any) => r.name === altOpKaydiName)
      : null;
    const lastKalipNo = defaultKalipNo || altOpRow?.kalip_no || props.doc.alt_operasyon_kayitlari?.slice().reverse().find((r: any) => r.kalip_no)?.kalip_no || "";
    const lastHammadde = defaultHammadde || altOpRow?.hammadde || props.doc.alt_operasyon_kayitlari?.slice().reverse().find((r: any) => r.hammadde)?.hammadde || "";

    let initialTolerans: any = null;
    if (lastHammadde) {
      const r = await frappe.call({
        method: "erpnextkta.kta_calisma_karti.api.get_enjeksiyon_tolerans",
        args: { hammadde_no: lastHammadde }
      });
      if (!r.message || Object.keys(r.message).length === 0) {
        frappe.msgprint({
          title: __("Tolerans Tanımı Eksik"),
          message: __("'{0}' hammaddesi için enjeksiyon proses toleransları tanımlanmamış. Tolerans kaydı olmadan ölçüm girilemez.", [lastHammadde]),
          indicator: "red"
        });
        return;
      }
      initialTolerans = r.message;
    }

    const allowed = getAllowedPeriods(altOpKaydiName);
    const defaultPeriod = allowed.length > 0 ? allowed[0] : "Başlangıç";

    const dialog = frappe.prompt(
      enjeksiyonOlcumFields({
        calisma_karti_name: props.doc.name,
        kalip_no: lastKalipNo,
        hammadde_no: lastHammadde,
        alt_operasyon_kaydi: altOpKaydiName || "",
        allowed_periods: allowed,
        kontrol_periyodu: defaultPeriod
      }),
      () => {},
      __("Enjeksiyon Ölçümü Ekle"),
      __("Kaydet")
    );
    setupEnjeksiyonToleransLogic(dialog, initialTolerans);
    bindEnjeksiyonDialogAction(dialog, __("Kaydet"), async (v: any) => {
      const payload = { ...v };
      if (dialog.enjeksiyon_tolerans) {
         Object.keys(dialog.enjeksiyon_tolerans).forEach(k => {
             payload[`hedef_${k}`] = dialog.enjeksiyon_tolerans[k];
         });
      }
      const res: any = await props.onAddEnjeksiyon(payload);
      if (res?.message?.earned_points) {
        frappe.show_alert({
          message: __("Tebrikler! 3/3 ölçümü eksiksiz tamamlayarak {0} Enerji Puanı kazandınız! 🌟", [res.message.earned_points]),
          indicator: "green"
        }, 7);
      } else {
        frappe.show_alert({ message: __("Enjeksiyon ölçümü eklendi"), indicator: "green" });
      }
    });
  }

  async function editEnjeksiyon(row: any) {
    if (!row?.name) return frappe.msgprint(__("Enjeksiyon satır kimliği bulunamadı."));
    const altOpId = row.alt_operasyon_kaydi || "";
    const allowed = getAllowedPeriods(altOpId, row.name);
    if (row.kontrol_periyodu && !allowed.includes(row.kontrol_periyodu)) {
      allowed.unshift(row.kontrol_periyodu);
    }

    const altOpRow = altOpId
      ? (props.doc.alt_operasyon_kayitlari || []).find((r: any) => r.name === altOpId)
      : null;
    const kalipNo = altOpRow?.kalip_no || row.kalip_no;
    const hammaddeNo = altOpRow?.hammadde || row.hammadde_no;

    let initialTolerans: any = null;
    if (hammaddeNo) {
      const r = await frappe.call({
        method: "erpnextkta.kta_calisma_karti.api.get_enjeksiyon_tolerans",
        args: { hammadde_no: hammaddeNo }
      });
      if (!r.message || Object.keys(r.message).length === 0) {
        frappe.msgprint({
          title: __("Tolerans Tanımı Eksik"),
          message: __("'{0}' hammaddesi için enjeksiyon proses toleransları tanımlanmamış. Tolerans kaydı olmadan ölçüm girilemez.", [hammaddeNo]),
          indicator: "red"
        });
        return;
      }
      initialTolerans = r.message;
    }

    const dialog = frappe.prompt(
      enjeksiyonOlcumFields({
        ...row,
        kalip_no: kalipNo,
        hammadde_no: hammaddeNo,
        calisma_karti_name: props.doc.name,
        alt_operasyon_kaydi: altOpId,
        allowed_periods: allowed,
        kontrol_periyodu: row.kontrol_periyodu || (allowed[0] || "Başlangıç")
      }),
      () => {},
      __("Enjeksiyon Ölçümü Düzenle"),
      __("Kaydet")
    );
    setupEnjeksiyonToleransLogic(dialog, initialTolerans);
    bindEnjeksiyonDialogAction(dialog, __("Kaydet"), async (v: any) => {
      const payloadObj = { ...v };
      if (dialog.enjeksiyon_tolerans) {
         Object.keys(dialog.enjeksiyon_tolerans).forEach(k => {
             payloadObj[`hedef_${k}`] = dialog.enjeksiyon_tolerans[k];
         });
      }
      await props.onUpdateEnjeksiyon({ rowname: row.name, payload: payloadObj });
      frappe.show_alert({ message: __("Enjeksiyon ölçümü güncellendi"), indicator: "green" });
    });
  }

  function deleteEnjeksiyon(row: any) {
    if (!row?.name) return frappe.msgprint(__("Enjeksiyon satır kimliği bulunamadı."));
    frappe.confirm(__("Bu enjeksiyon ölçüm satırı silinecek. Emin misiniz?"), async () => {
      await props.onDeleteEnjeksiyon(row.name);
      frappe.show_alert({ message: __("Enjeksiyon ölçümü silindi"), indicator: "green" });
    });
  }

  async function cloneEnjeksiyon(row: any) {
    const altOpId = row.alt_operasyon_kaydi || "";
    if (altOpId) {
      const allowedCheck = getAllowedPeriods(altOpId);
      if (allowedCheck.length === 0) {
        frappe.msgprint({
          title: __("Ölçüm Limiti"),
          message: __("Bu alt operasyon için tüm periyot ölçümleri (Başlangıç, Ara, Bitiş) tamamlanmıştır."),
          indicator: "orange"
        });
        return;
      }
    }
    const allowed = getAllowedPeriods(altOpId);
    const defaultPeriod = allowed.length > 0 ? allowed[0] : (row.kontrol_periyodu || "Başlangıç");

    const altOpRow = altOpId
      ? (props.doc.alt_operasyon_kayitlari || []).find((r: any) => r.name === altOpId)
      : null;
    const kalipNo = altOpRow?.kalip_no || row.kalip_no;
    const hammaddeNo = altOpRow?.hammadde || row.hammadde_no;

    let initialTolerans: any = null;
    if (hammaddeNo) {
      const r = await frappe.call({
        method: "erpnextkta.kta_calisma_karti.api.get_enjeksiyon_tolerans",
        args: { hammadde_no: hammaddeNo }
      });
      if (!r.message || Object.keys(r.message).length === 0) {
        frappe.msgprint({
          title: __("Tolerans Tanımı Eksik"),
          message: __("'{0}' hammaddesi için enjeksiyon proses toleransları tanımlanmamış. Tolerans kaydı olmadan ölçüm girilemez.", [hammaddeNo]),
          indicator: "red"
        });
        return;
      }
      initialTolerans = r.message;
    }

    const cloneDefaults = {
      ...row,
      kalip_no: kalipNo,
      hammadde_no: hammaddeNo,
      calisma_karti_name: props.doc.name,
      alt_operasyon_kaydi: altOpId,
      allowed_periods: allowed,
      kontrol_periyodu: defaultPeriod,
      goz_kontrol: 0
    };

    const dialog = frappe.prompt(
      enjeksiyonOlcumFields(cloneDefaults),
      () => {},
      __("Enjeksiyon Ölçümü Kopyala"),
      __("Kaydet")
    );
    setupEnjeksiyonToleransLogic(dialog, initialTolerans);
    bindEnjeksiyonDialogAction(dialog, __("Kaydet"), async (v: any) => {
      const payload = { ...v };
      if (dialog.enjeksiyon_tolerans) {
         Object.keys(dialog.enjeksiyon_tolerans).forEach(k => {
             payload[`hedef_${k}`] = dialog.enjeksiyon_tolerans[k];
         });
      }
      const res: any = await props.onAddEnjeksiyon(payload);
      if (res?.message?.earned_points) {
        frappe.show_alert({
          message: __("Tebrikler! 3/3 ölçümü eksiksiz tamamlayarak {0} Enerji Puanı kazandınız! 🌟", [res.message.earned_points]),
          indicator: "green"
        }, 7);
      } else {
        frappe.show_alert({ message: __("Enjeksiyon ölçümü kopyalandı ve eklendi"), indicator: "green" });
      }
    });
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
