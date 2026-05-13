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

export function hurdaFields(defaults: any = {}) {
    return [
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
    ];
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
    return [
        {
            fieldtype: "Link",
            label: "Duruş Nedeni",
            fieldname: "durus_nedeni",
            reqd: 1,
            options: "KTA Durus Sebebi",
            get_query: () => ({ filters: { is_system: 0 } })
        },
        { fieldtype: "Small Text", label: "Açıklama", fieldname: "aciklama" }
    ];
}



export function idcOlcumFields(docname: string, defaults: any = {}) {
    return [
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
    ];
}

export function barkodKayitFields(defaults: any = {}) {
    return [
        {
            fieldtype: "Data",
            label: "Barkod",
            fieldname: "barcode",
            reqd: 1,
            default: defaults.barcode || "",
        },
    ];
}

export function altOperasyonFields(parentOperationLabel: string, calismaKartiName: string, defaults: any = {}, getAltOpValue?: () => string, altOpOptions: any[] = []) {
    return [
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
    ];
}

export function krimpOlcumFields(defaults: any = {}) {
    return [
        {
            fieldtype: "Section Break",
            label: "Kablo ve Kontak Bilgileri"
        },
        {
            fieldtype: "Data",
            label: "Kablo No",
            fieldname: "kablo_no",
            default: defaults.kablo_no || "",
        },
        {
            fieldtype: "Data",
            label: "Kontak No",
            fieldname: "kontak_no",
            default: defaults.kontak_no || "",
        },
        {
            fieldtype: "Data",
            label: "Kablo Kesiti",
            fieldname: "kablo_kesiti",
            default: defaults.kablo_kesiti || "",
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
            fieldtype: "Data",
            label: "Makine / Pres No",
            fieldname: "makine_pres_no",
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
    ];
}
