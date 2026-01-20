import { computed, ref } from "vue";

export function useCalismaKarti(docname: ReturnType<typeof computed<string | null>>) {
    const loading = ref(false);
    const doc = ref<any | null>(null);

    async function load() {
        if (!docname.value) return;
        loading.value = true;
        try {
            const r = await frappe.call(
                "erpnextkta.kta_calisma_karti.api.get_calisma_karti_detail",
                { name: docname.value }
            );
            doc.value = r.message || null;
        } finally {
            loading.value = false;
        }
    }

    async function refreshAfter<T>(fn: () => Promise<T>): Promise<T> {
        const res = await fn();
        await load();
        return res;
    }

    async function callIslem(
        islem_tipi: string,
        durus_nedeni: string | null = null,
        aciklama: string | null = null,
        tamamlanan_miktar: number | null = null
    ) {
        return refreshAfter(() =>
            frappe.call({
                method:
                    "erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.islem_yap",
                args: {
                    docname: docname.value,
                    islem_tipi,
                    durus_nedeni,
                    aciklama,
                    tamamlanan_miktar,
                },
                freeze: true,
                freeze_message: "İşlem yapılıyor...",
            })
        );
    }

    async function updateQC(kalite_kontrol: string) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.update_kalite_kontrol", {
                name: docname.value,
                kalite_kontrol: (kalite_kontrol || "").trim(),
            })
        );
    }

    async function addHurda(payload: {
        parca_no: string;
        hurda_nedeni: string;
        miktar: number;
        birim: string;
        depo?: string | null;
    }) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.add_hurda", {
                name: docname.value,
                ...payload,
                depo: payload.depo || null,
            })
        );
    }

    async function updateHurda(payload: {
        rowname: string;
        parca_no: string;
        hurda_nedeni: string;
        miktar: number;
        birim: string;
        depo?: string | null;
    }) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.update_hurda", {
                name: docname.value,
                ...payload,
                depo: payload.depo || null,
            })
        );
    }

    async function deleteHurda(rowname: string) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.delete_hurda", {
                name: docname.value,
                rowname,
            })
        );
    }

    return {
        loading,
        doc,
        load,
        callIslem,
        updateQC,
        addHurda,
        updateHurda,
        deleteHurda,
    };
}