import { applyDecimalInputMode } from "./common";

declare const __: any;

export function hurdaFields(defaults: any = {}) {
    const rawNedenleri: any[] = defaults.hurda_nedenleri || [];
    const nedenOptions = [
        "",
        ...rawNedenleri.map((n: any) =>
            typeof n === "string" ? { label: __(n), value: n } : { label: __(n.label || n.value), value: n.value }
        ),
    ];

    return applyDecimalInputMode([
        {
            fieldtype: "Link",
            label: __("Parça Numarası"),
            fieldname: "parca_no",
            options: "Item",
            reqd: 1,
            default: defaults.parca_no || "",
            description: __("Mevcut ve önceki operasyonlara ait izinli BOM hammaddeleri"),
            get_query: () => ({
                query: "erpnextkta.kta_calisma_karti.api.search_allowed_hurda_items",
                filters: {
                    calisma_karti: defaults.calisma_karti_name,
                },
            }),
        },
        {
            fieldtype: "Select",
            label: __("Hurda Nedeni"),
            fieldname: "hurda_nedeni",
            options: nedenOptions,
            reqd: 1,
            default: defaults.hurda_nedeni || "",
        },
        {
            fieldtype: "Float",
            label: __("Miktar"),
            fieldname: "miktar",
            reqd: 1,
            default: defaults.miktar ?? "",
        },
        {
            fieldtype: "Small Text",
            label: __("Açıklama"),
            fieldname: "aciklama",
            reqd: 0,
            default: defaults.aciklama || "",
        },
    ]);
}
