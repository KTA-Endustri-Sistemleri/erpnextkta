const HURDA_PARENT_COST_CENTER = "Malzeme Sarfları - KTA";

export function hurdaNedeniLinkField(defaultValue = "") {
    return {
        fieldtype: "Link",
        label: "Hurda Nedeni",
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
            label: "Parça Numarası",
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
            label: "Miktar",
            fieldname: "miktar",
            reqd: 1,
            default: defaults.miktar ?? 0,
        },
        {
            fieldtype: "Link",
            label: "Birim",
            fieldname: "birim",
            options: "UOM",
            reqd: 1,
            default: defaults.birim || "",
        },
        {
            fieldtype: "Link",
            label: "Depo",
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
        label: "Parça Numarası",
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

export function durusFields() {
    return applyDecimalInputMode([
        {
            fieldtype: "Link",
            label: "Duruş Nedeni",
            fieldname: "durus_nedeni",
            reqd: 1,
            options: "KTA Durus Sebebi",
            get_query: () => ({ filters: { is_system: 0 } })
        },
        { fieldtype: "Small Text", label: "Açıklama", fieldname: "aciklama" }
    ]);
}



export function idcOlcumFields(docname: string, defaults: any = {}) {
    return applyDecimalInputMode([
        {
            fieldtype: "Link",
            label: "Item Code",
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
            label: "Yükseklik (mm)",
            fieldname: "yukseklik_mm",
            reqd: 0,
            default: defaults.yukseklik_mm ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Çekme (N)",
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
            label: "Barkod",
            fieldname: "barcode",
            reqd: 1,
            default: defaults.barcode || "",
        },
    ]);
}

export function altOperasyonFields(parentOperationLabel: string, calismaKartiName: string, defaults: any = {}, getAltOpValue?: () => string, altOpOptions: any[] = []) {
    return applyDecimalInputMode([
        {
            fieldtype: "Select",
            label: "Alt İşlem",
            fieldname: "alt_operasyon",
            options: altOpOptions,
            reqd: 1,
            default: defaults.alt_operasyon || "",
        },
        {
            fieldtype: "Link",
            label: "Hammadde (Opsiyonel)",
            fieldname: "hammadde",
            options: "Item",
            reqd: 0,
            default: defaults.hammadde || "",
            get_query: () => {
                const currentOp = getAltOpValue ? getAltOpValue() : defaults.alt_operasyon;
                return {
                    query: "erpnextkta.kta_calisma_karti.api_impl.alt_operasyon.search_allowed_hammadde_items",
                    filters: { calisma_karti: calismaKartiName, alt_operasyon: currentOp || "" }
                };
            }
        },
        {
            fieldtype: "Float",
            label: "Adet",
            fieldname: "adet",
            reqd: 0,
            default: defaults.adet ?? 1,
        },
        {
            fieldtype: "Link",
            label: "Birim",
            fieldname: "uom",
            options: "UOM",
            reqd: 0,
            default: defaults.uom || "",
        },
        {
            fieldtype: "Small Text",
            label: "Not Açıklama",
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
            label: "Kablo ve Kontak Bilgileri"
        },
        {
            fieldtype: "Select",
            label: "Kablo Kesiti (Rehberden)",
            fieldname: "kablo_kesiti",
            options: defaults.kablo_kesiti ? ["", defaults.kablo_kesiti] : [""],
            default: defaults.kablo_kesiti || "",
            reqd: 1
        },
        {
            fieldtype: "Link",
            label: "Kablo No",
            fieldname: "kablo_no",
            options: "Item",
            default: defaults.kablo_no || "",
            reqd: 1,
            get_query: () => ({
                query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
                filters: { calisma_karti: defaults.calisma_karti_name, type: "kablo" }
            })
        },
        {
            fieldtype: "Link",
            label: "Kontak No",
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
            fieldtype: "Section Break",
            label: "Makine ve Kalıp"
        },
        {
            fieldtype: "Data",
            label: "Kalıp No",
            fieldname: "kalip_no",
            default: defaults.kalip_no || "",
        },
        {
            fieldtype: "Link",
            label: "Makine / Pres No",
            fieldname: "makine_pres_no",
            options: "Asset",
            default: defaults.makine_pres_no || "",
        },
        {
            fieldtype: "Section Break",
            label: "Ölçümler"
        },
        {
            fieldtype: "Float",
            label: "Hedef Kablo Boyu (mm)",
            fieldname: "hedef_kablo_boyu",
            default: defaults.hedef_kablo_boyu ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Ölçülen Kablo Boyu (mm)",
            fieldname: "olculen_kablo_boyu",
            default: defaults.olculen_kablo_boyu ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Hedef İletken Krimp Yük. (mm)",
            fieldname: "hedef_iletken_krimp_yuksekliği",
            default: defaults.hedef_iletken_krimp_yuksekliği ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Ölçülen İletken Krimp Yük. (mm)",
            fieldname: "olculen_iletken_krimp_yuksekliği",
            default: defaults.olculen_iletken_krimp_yuksekliği ?? 0,
        },
        {
            fieldtype: "Float",
            label: "İzokrimp Yüksekliği (mm)",
            fieldname: "izokrimp_yuksekligi",
            default: defaults.izokrimp_yuksekligi ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Sıyırma Boyu (mm)",
            fieldname: "siyirma_boyu",
            default: defaults.siyirma_boyu ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Çekme Kuvveti (N)",
            fieldname: "cekme_kuvveti_n",
            default: defaults.cekme_kuvveti_n ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Çapak Boyu (mm)",
            fieldname: "capak_boyu",
            default: defaults.capak_boyu ?? 0,
        },
        {
            fieldtype: "Section Break",
            label: "Görsel Kontroller"
        },
        {
            fieldtype: "Check",
            label: "Radüs Mevcut",
            fieldname: "radus_mevcut",
            default: defaults.radus_mevcut ?? 0,
        },
        {
            fieldtype: "Check",
            label: "Tel Kesme Mevcut",
            fieldname: "tel_kesme_mevcut",
            default: defaults.tel_kesme_mevcut ?? 0,
        },
    ]);
}

export function enjeksiyonOlcumFields(defaults: any = {}) {
    return applyDecimalInputMode([
        {
            fieldtype: "Select",
            label: "Kontrol Periyodu",
            fieldname: "kontrol_periyodu",
            options: "Başlangıç\nAra\nBitiş",
            reqd: 1,
            default: defaults.kontrol_periyodu || "Başlangıç",
        },
        {
            fieldtype: "Link",
            label: "Hammadde No",
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
            label: "Göz Kontrol",
            fieldname: "goz_kontrol",
            default: defaults.goz_kontrol ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Çekme Kuvveti (N)",
            fieldname: "cekme_kuvveti_olculen",
            default: defaults.cekme_kuvveti_olculen ?? 0,
        },
        { fieldtype: "Section Break", label: "Proses Parametreleri" },
        {
            fieldtype: "Float",
            label: "Hammadde Kazan Isısı (°C)",
            fieldname: "hammadde_kazan_isisi",
            default: defaults.hammadde_kazan_isisi ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Ara Hortum Isısı (°C)",
            fieldname: "ara_hortum_isisi",
            default: defaults.ara_hortum_isisi ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Kafa (Meme) Isısı (°C)",
            fieldname: "kafa_meme_isisi",
            default: defaults.kafa_meme_isisi ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Soğuk Su Isısı (°C)",
            fieldname: "soguk_su_isisi",
            default: defaults.soguk_su_isisi ?? 0,
        },
        { fieldtype: "Column Break" },
        {
            fieldtype: "Float",
            label: "Motor Devir",
            fieldname: "motor_devir",
            default: defaults.motor_devir ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Hammadde Enjeksiyon Zamanı (sn)",
            fieldname: "hammadde_enjeksiyon_zamani",
            default: defaults.hammadde_enjeksiyon_zamani ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Soğutma Zamanı (sn)",
            fieldname: "sogutma_zamani",
            default: defaults.sogutma_zamani ?? 0,
        }
    ]);
}
