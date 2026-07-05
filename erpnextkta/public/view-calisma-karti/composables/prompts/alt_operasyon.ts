import { applyDecimalInputMode } from "./common";

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
