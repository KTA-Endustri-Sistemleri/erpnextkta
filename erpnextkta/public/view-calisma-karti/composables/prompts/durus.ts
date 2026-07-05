import { applyDecimalInputMode } from "./common";

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
