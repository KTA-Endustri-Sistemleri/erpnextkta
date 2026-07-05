import { applyDecimalInputMode } from "./common";

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
