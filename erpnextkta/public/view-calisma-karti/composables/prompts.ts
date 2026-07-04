const HURDA_PARENT_COST_CENTER = "Malzeme Sarfları - KTA";

export function hurdaNedeniLinkField(defaultValue = "") {
    return {
        fieldtype: "Link",
        label: __("Hurda Nedeni"),
        fieldname: "hurda_nedeni",
        options: "Cost Center",
        reqd: 1,
        default: defaultValue,
        get_query: () => ({
            filters: {
                parent_cost_center: HURDA_PARENT_COST_CENTER,
                is_group: 0,
            },
        }),
    };
}

function applyDecimalInputMode(fields: any[]) {
    fields.forEach(f => {
        if (["Float", "Currency", "Percent"].includes(f.fieldtype)) {
            f.on_make = (field: any) => {
                if (field.$input) {
                    field.$input.attr("inputmode", "decimal");
                }
            };
        }
    });
    return fields;
}

export function hurdaFields(defaults: any = {}) {
    return applyDecimalInputMode([
        {
            fieldtype: "Link",
            label: __("Parça Numarası"),
            fieldname: "parca_no",
            options: "Item",
            reqd: 1,
            default: defaults.parca_no || "",
            get_query: () => ({
                query: "erpnextkta.kta_calisma_karti.api.search_allowed_hurda_items",
                filters: {
                    calisma_karti: defaults.calisma_karti_name,
                },
            }),
        },
        hurdaNedeniLinkField(defaults.hurda_nedeni || ""),
        {
            fieldtype: "Float",
            label: __("Miktar"),
            fieldname: "miktar",
            reqd: 1,
            default: defaults.miktar ?? 0,
        },
        {
            fieldtype: "Link",
            label: __("Birim"),
            fieldname: "birim",
            options: "UOM",
            reqd: 1,
            default: defaults.birim || "",
        },
        {
            fieldtype: "Link",
            label: __("Depo"),
            fieldname: "depo",
            options: "Warehouse",
            default: defaults.depo || "",
        },
    ]);
}

// Hurda için: sadece ilgili operasyonun BOM item'larını göster
export function hurdaParcaNoField(calismaKartiName: string, defaultValue?: string) {
    return {
        fieldtype: "Link",
        label: __("Parça Numarası"),
        fieldname: "parca_no",
        options: "Item",
        reqd: 1,
        default: defaultValue || "",
        get_query: () => ({
            query: "erpnextkta.kta_calisma_karti.api.get_allowed_hurda_items",
            filters: {
                name: calismaKartiName,
            },
        }),
    };
}

export function durusFields(reasonOptions: string) {
    return applyDecimalInputMode([
        {
            fieldtype: "Select",
            label: __("Duruş Nedeni"),
            fieldname: "durus_nedeni",
            reqd: 1,
            options: reasonOptions
        },
        { fieldtype: "Small Text", label: __("Açıklama"), fieldname: "aciklama" }
    ]);
}



export function idcOlcumFields(docname: string, defaults: any = {}) {
    return applyDecimalInputMode([
        {
            fieldtype: "Link",
            label: __("Ürün Kodu"),
            fieldname: "item_code",
            options: "Item",
            reqd: 1,
            default: defaults.item_code || "",
            get_query: () => ({
                query: "erpnextkta.kta_calisma_karti.api.search_allowed_idc_items",
                filters: { calisma_karti: docname } // docname’i idcOlcumFields'e parametre geçeceğiz
            })
        },
        {
            fieldtype: "Float",
            label: __("Yükseklik (mm)"),
            fieldname: "yukseklik_mm",
            reqd: 0,
            default: defaults.yukseklik_mm ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Çekme (N)"),
            fieldname: "cekme_n",
            reqd: 0,
            default: defaults.cekme_n ?? 0,
        },
    ]);
}

export function barkodKayitFields(defaults: any = {}) {
    return applyDecimalInputMode([
        {
            fieldtype: "Data",
            label: __("Barkod"),
            fieldname: "barcode",
            reqd: 1,
            default: defaults.barcode || "",
        },
    ]);
}

export function altOperasyonFieldsMulti(parentOperationLabel: string, calismaKartiName: string, defaults: any = {}, getAltOpValue?: () => string, altOpOptions: any[] = []) {
    // Generate depends_on expressions using JS functions for robustness in Frappe Dialogs
    const opsWith2OrMoreValues = altOpOptions.filter((o: any) => parseInt(o.hammadde_sayisi || "1") >= 2).map((o: any) => o.value);
    const opsWith2OrMoreLabels = altOpOptions.filter((o: any) => parseInt(o.hammadde_sayisi || "1") >= 2).map((o: any) => o.label);

    const opsWith3OrMoreValues = altOpOptions.filter((o: any) => parseInt(o.hammadde_sayisi || "1") >= 3).map((o: any) => o.value);
    const opsWith3OrMoreLabels = altOpOptions.filter((o: any) => parseInt(o.hammadde_sayisi || "1") >= 3).map((o: any) => o.label);

    const dependsOn2 = function (doc: any) {
        if (!doc || !doc.alt_operasyon) return false;
        const count = getHammaddeSayisi(doc);
        const tipi = getOperasyonTipi(doc);
        return count >= 2 || tipi === "Tek Taraf" || tipi === "Çift Taraf" || tipi === "Blunt" || opsWith2OrMoreValues.includes(doc.alt_operasyon) || opsWith2OrMoreLabels.includes(doc.alt_operasyon);
    };

    const dependsOn3 = function (doc: any) {
        if (!doc || !doc.alt_operasyon) return false;
        const count = getHammaddeSayisi(doc);
        const tipi = getOperasyonTipi(doc);
        return count >= 3 || tipi === "Tek Taraf" || tipi === "Çift Taraf" || tipi === "Blunt" || opsWith3OrMoreValues.includes(doc.alt_operasyon) || opsWith3OrMoreLabels.includes(doc.alt_operasyon);
    };

    const getHammaddeSayisi = function (doc: any) {
        if (!doc || !doc.alt_operasyon) return 1;
        const op = altOpOptions.find((o: any) => o.value === doc.alt_operasyon || o.label === doc.alt_operasyon);
        return op ? parseInt(op.hammadde_sayisi || "1") : 1;
    };

    const getOperasyonTipi = function (doc: any) {
        if (!doc || !doc.alt_operasyon) return "";
        const op = altOpOptions.find((o: any) => o.value === doc.alt_operasyon || o.label === doc.alt_operasyon);
        return op ? (op.operasyon_tipi || "") : "";
    };

    const isTekTaraf = function (doc: any) {
        const tipi = getOperasyonTipi(doc);
        if (tipi) return tipi === "Tek Taraf";
        return getHammaddeSayisi(doc) === 2;
    };

    const isCiftTaraf = function (doc: any) {
        const tipi = getOperasyonTipi(doc);
        if (tipi) return tipi === "Çift Taraf";
        return getHammaddeSayisi(doc) >= 3;
    };

    const showSiyirma2 = function (doc: any) {
        if (!dependsOn2(doc)) return false;
        return !isCiftTaraf(doc);
    };

    const showSiyirma3 = function (doc: any) {
        if (!dependsOn3(doc)) return false;
        return !isCiftTaraf(doc);
    };

    const showTerminal2 = function (doc: any) {
        if (!dependsOn2(doc)) return false;
        return getOperasyonTipi(doc) !== "Blunt";
    };

    const showTerminal3 = function (doc: any) {
        if (!dependsOn3(doc)) return false;
        return getOperasyonTipi(doc) !== "Blunt";
    };

    return applyDecimalInputMode([
        {
            fieldtype: "Select",
            label: __("Alt İşlem"),
            fieldname: "alt_operasyon",
            options: altOpOptions.map((o: any) => ({ label: o.label, value: o.value })),
            reqd: 1,
            default: defaults.alt_operasyon || "",
        },
        { fieldtype: "Section Break" },

        // Sütun 1: Sol Uç
        { fieldtype: "Column Break", depends_on: dependsOn2 },
        {
            fieldtype: "Link",
            label: __("Sol Uç (Terminal)"),
            fieldname: "hammadde_2",
            options: "Item",
            reqd: 0,
            default: defaults.hammadde_2 || "",
            depends_on: showTerminal2,
            get_query: () => {
                const currentOp = getAltOpValue ? getAltOpValue() : defaults.alt_operasyon;
                return {
                    query: "erpnextkta.kta_calisma_karti.api_impl.alt_operasyon.search_allowed_hammadde_items",
                    filters: { calisma_karti: calismaKartiName, alt_operasyon: currentOp || "", hammadde_sira: "Hammadde 1" }
                };
            }
        },
        {
            fieldtype: "Float",
            label: __("Sol Sıyırma (mm)"),
            fieldname: "boyut_2_mm",
            reqd: 0,
            default: defaults.boyut_2_mm ?? 0,
            depends_on: showSiyirma2,
        },


        // Sütun 2: Kablo
        { fieldtype: "Column Break" },
        {
            fieldtype: "Link",
            label: __("Kablo Seçimi"),
            fieldname: "hammadde",
            options: "Item",
            reqd: 1,
            default: defaults.hammadde || "",
            get_query: () => {
                const currentOp = getAltOpValue ? getAltOpValue() : defaults.alt_operasyon;
                return {
                    query: "erpnextkta.kta_calisma_karti.api_impl.alt_operasyon.search_allowed_hammadde_items",
                    filters: { calisma_karti: calismaKartiName, alt_operasyon: currentOp || "", hammadde_sira: "Hammadde 2" }
                };
            }
        },
        {
            fieldtype: "Float",
            label: __("Kablo Boyu (mm)"),
            description: __("Sadece stok birimi Metre olan hammaddelerde doldurun."),
            fieldname: "boyut_1_mm",
            reqd: 1,
            default: defaults.boyut_1_mm ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("İşlem Adedi (Kablo)"),
            fieldname: "islem_adedi_1",
            reqd: 1,
            default: defaults.islem_adedi_1 ?? 1,
        },

        // Sütun 3: Sağ Uç
        { fieldtype: "Column Break", depends_on: dependsOn3 },
        {
            fieldtype: "Link",
            label: __("Sağ Uç (Terminal)"),
            fieldname: "hammadde_3",
            options: "Item",
            reqd: 0,
            default: defaults.hammadde_3 || "",
            depends_on: showTerminal3,
            get_query: () => {
                const currentOp = getAltOpValue ? getAltOpValue() : defaults.alt_operasyon;
                return {
                    query: "erpnextkta.kta_calisma_karti.api_impl.alt_operasyon.search_allowed_hammadde_items",
                    filters: { calisma_karti: calismaKartiName, alt_operasyon: currentOp || "", hammadde_sira: "Hammadde 3" }
                };
            }
        },
        {
            fieldtype: "Float",
            label: __("Sağ Sıyırma (mm)"),
            fieldname: "boyut_3_mm",
            reqd: 0,
            default: defaults.boyut_3_mm ?? 0,
            depends_on: showSiyirma3,
        },


        { fieldtype: "Section Break" },
        {
            fieldtype: "Small Text",
            label: __("Not Açıklama"),
            fieldname: "note",
            reqd: 0,
            default: defaults.note || "",
        },
    ]);
}

export function altOperasyonFieldsSingle(parentOperationLabel: string, calismaKartiName: string, defaults: any = {}, getAltOpValue?: () => string, altOpOptions: any[] = []) {
    return applyDecimalInputMode([
        {
            fieldtype: "Select",
            label: __("Alt İşlem"),
            fieldname: "alt_operasyon",
            options: altOpOptions.map((o: any) => ({ label: o.label, value: o.value })),
            reqd: 1,
            default: defaults.alt_operasyon || "",
        },
        { fieldtype: "Section Break" },
        {
            fieldtype: "Link",
            label: __("Hammadde"),
            fieldname: "hammadde",
            options: "Item",
            reqd: 0,
            default: defaults.hammadde || "",
            get_query: () => {
                const currentOp = getAltOpValue ? getAltOpValue() : defaults.alt_operasyon;
                return {
                    query: "erpnextkta.kta_calisma_karti.api_impl.alt_operasyon.search_allowed_hammadde_items",
                    filters: { calisma_karti: calismaKartiName, alt_operasyon: currentOp || "", hammadde_sira: "Hammadde 1" }
                };
            }
        },

        {
            fieldtype: "Float",
            label: __("İşlem Adedi"),
            fieldname: "adet",
            reqd: 0,
            default: defaults.adet ?? 1,
        },
        {
            fieldtype: "Link",
            label: __("Birim"),
            fieldname: "uom",
            options: "UOM",
            reqd: 0,
            default: defaults.uom || "",
        },
        {
            fieldtype: "Small Text",
            label: __("Not Açıklama"),
            fieldname: "note",
            reqd: 0,
            default: defaults.note || "",
        },
    ]);
}

export function krimpOlcumFields(defaults: any = {}) {
    return applyDecimalInputMode([
        {
            fieldtype: "Section Break",
            label: __("Kablo ve Kontak Bilgileri")
        },
        {
            fieldtype: "Link",
            label: __("Kontak No"),
            fieldname: "kontak_no",
            options: "Item",
            default: defaults.kontak_no || "",
            reqd: 1,
            get_query: () => ({
                query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
                filters: { calisma_karti: defaults.calisma_karti_name, type: "kontak" }
            })
        },
        {
            fieldtype: "Select",
            label: __("Kablo Kesiti (Rehberden)"),
            fieldname: "kablo_kesiti",
            options: defaults.kablo_kesiti ? ["", defaults.kablo_kesiti] : [""],
            default: defaults.kablo_kesiti || "",
            reqd: 1
        },
        {
            fieldtype: "Link",
            label: __("Kablo No"),
            fieldname: "kablo_no",
            options: "Item",
            default: defaults.kablo_no || "",
            reqd: 0,
            get_query: () => ({
                query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
                filters: { calisma_karti: defaults.calisma_karti_name, type: "kablo" }
            })
        },
        {
            fieldtype: "Section Break",
            label: __("Makine ve Kalıp")
        },
        {
            fieldtype: "Data",
            label: __("Kalıp No"),
            fieldname: "kalip_no",
            default: defaults.kalip_no || "",
        },
        {
            fieldtype: "Link",
            label: __("Makine / Pres No"),
            fieldname: "makine_pres_no",
            options: "Asset",
            default: defaults.makine_pres_no || "",
        },
        {
            fieldtype: "Section Break",
            label: __("Ölçümler")
        },
        {
            fieldtype: "Float",
            label: __("Hedef Kablo Boyu (mm)"),
            fieldname: "hedef_kablo_boyu",
            default: defaults.hedef_kablo_boyu ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Ölçülen Kablo Boyu (mm)"),
            fieldname: "olculen_kablo_boyu",
            default: defaults.olculen_kablo_boyu ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Hedef İletken Krimp Yük. (mm)"),
            fieldname: "hedef_iletken_krimp_yuksekliği",
            default: defaults.hedef_iletken_krimp_yuksekliği ?? 0,
            read_only: 1,
        },
        {
            fieldtype: "Float",
            label: __("Ölçülen İletken Krimp Yük. (mm)"),
            fieldname: "olculen_iletken_krimp_yuksekliği",
            default: defaults.olculen_iletken_krimp_yuksekliği ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("İzokrimp Yüksekliği (mm)"),
            fieldname: "izokrimp_yuksekligi",
            default: defaults.izokrimp_yuksekligi ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Sıyırma Boyu (mm)"),
            fieldname: "siyirma_boyu",
            default: defaults.siyirma_boyu ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Hedef Çekme Kuvveti (N)"),
            fieldname: "hedef_cekme_kuvveti_n",
            default: defaults.hedef_cekme_kuvveti_n ?? 0,
            read_only: 1,
        },
        {
            fieldtype: "Float",
            label: __("Ölçülen Çekme Kuvveti (N)"),
            fieldname: "olculen_cekme_kuvveti_n",
            default: defaults.olculen_cekme_kuvveti_n ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Çapak Boyu (mm)"),
            fieldname: "capak_boyu",
            default: defaults.capak_boyu ?? 0,
        },
        {
            fieldtype: "Section Break",
            label: __("Görsel Kontroller")
        },
        {
            fieldtype: "Check",
            label: __("Radüs Mevcut"),
            fieldname: "radus_mevcut",
            default: defaults.radus_mevcut ?? 0,
        },
        {
            fieldtype: "Check",
            label: __("Tel Kesme Mevcut"),
            fieldname: "tel_kesme_mevcut",
            default: defaults.tel_kesme_mevcut ?? 0,
        },
    ]);
}

export function enjeksiyonOlcumFields(defaults: any = {}) {
    return applyDecimalInputMode([
        {
            fieldtype: "Select",
            label: __("Kontrol Periyodu"),
            fieldname: "kontrol_periyodu",
            options: "Başlangıç\nAra\nBitiş",
            reqd: 1,
            default: defaults.kontrol_periyodu || "Başlangıç",
        },
        {
            fieldtype: "Link",
            label: __("Hammadde No"),
            fieldname: "hammadde_no",
            options: "Item",
            reqd: 1,
            default: defaults.hammadde_no || "",
            get_query: () => ({
                query: "erpnextkta.kta_calisma_karti.api.search_enjeksiyon_allowed_items",
                filters: { calisma_karti: defaults.calisma_karti_name }
            })
        },
        {
            fieldtype: "Column Break"
        },
        {
            fieldtype: "Check",
            label: __("Göz Kontrol"),
            fieldname: "goz_kontrol",
            default: defaults.goz_kontrol ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Çekme Kuvveti (N)"),
            fieldname: "cekme_kuvveti_olculen",
            default: defaults.cekme_kuvveti_olculen ?? 0,
        },
        { fieldtype: "Section Break", label: __("Proses Parametreleri") },
        {
            fieldtype: "Float",
            label: __("Hammadde Kazan Isısı (°C)"),
            fieldname: "hammadde_kazan_isisi",
            default: defaults.hammadde_kazan_isisi ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Ara Hortum Isısı (°C)"),
            fieldname: "ara_hortum_isisi",
            default: defaults.ara_hortum_isisi ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Kafa (Meme) Isısı (°C)"),
            fieldname: "kafa_meme_isisi",
            default: defaults.kafa_meme_isisi ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Soğuk Su Isısı (°C)"),
            fieldname: "soguk_su_isisi",
            default: defaults.soguk_su_isisi ?? 0,
        },
        { fieldtype: "Column Break" },
        {
            fieldtype: "Float",
            label: __("Motor Devir"),
            fieldname: "motor_devir",
            default: defaults.motor_devir ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Hammadde Enjeksiyon Zamanı (sn)"),
            fieldname: "hammadde_enjeksiyon_zamani",
            default: defaults.hammadde_enjeksiyon_zamani ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Soğutma Zamanı (sn)"),
            fieldname: "sogutma_zamani",
            default: defaults.sogutma_zamani ?? 0,
        }
    ]);
}
