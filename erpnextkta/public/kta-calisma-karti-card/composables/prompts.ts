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