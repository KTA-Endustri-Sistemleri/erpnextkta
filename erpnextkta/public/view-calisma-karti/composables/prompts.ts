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
            fieldtype: "Select",
            label: "Duruş Nedeni",
            fieldname: "durus_nedeni",
            reqd: 1,
            options: "Ariza\nMalzeme Bekleme\nKalite Kontrol\nMola\nBakim\nDiger",
        },
        { fieldtype: "Small Text", label: "Açıklama", fieldname: "aciklama" },
        { fieldtype: "Float", label: "Tamamlanan Miktar (opsiyonel)", fieldname: "tamamlanan_miktar" },
    ];
}

export function bitirFields() {
    return [
        {
            fieldtype: "Float",
            label: "Tamamlanan Miktar",
            fieldname: "tamamlanan_miktar",
            reqd: 1,
            default: 0,
            description: "İşlemi bitirmek için tamamlanan miktar 0'dan büyük olmalı.",
        },
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
            reqd: 1,
            default: defaults.yukseklik_mm ?? 0,
        },
        {
            fieldtype: "Float",
            label: "Çekme (N)",
            fieldname: "cekme_n",
            reqd: 1,
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

export function altOperasyonFields(parentOperationLabel: string, defaults: any = {}) {
    return [
        {
            fieldtype: "Link",
            label: "Alt İşlem",
            fieldname: "alt_operasyon",
            options: "KTA Calisma Karti Alt Operasyonlari",
            reqd: 1,
            default: defaults.alt_operasyon || "",
            get_query: () => ({
                filters: {
                    parent_operation: parentOperationLabel,
                    is_active: 1
                }
            })
        },
        {
            fieldtype: "Link",
            label: "Hammadde (Opsiyonel)",
            fieldname: "hammadde",
            options: "Item",
            reqd: 0,
            default: defaults.hammadde || "",
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
