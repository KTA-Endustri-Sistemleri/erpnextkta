import { applyDecimalInputMode } from "./common";

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
