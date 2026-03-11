import { computed, ref, onMounted, onUnmounted, watch } from "vue";

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
    // --------------------
    // Realtime (Socket.IO) - live detail refresh
    // --------------------
    let docHandler: any = null;
    let docTimer: any = null;
    let boundDocname: string | null = null;

    function bindDocRealtime(name: string) {
        const rt = (window as any)?.frappe?.realtime;
        if (!rt || !name) return;

        const eventName = `kta_calisma_karti:doc_changed:${name}`;

        docHandler = (_payload: any) => {
            clearTimeout(docTimer);
            docTimer = setTimeout(() => {
                // Avoid stacking loads
                if (!loading.value) load();
            }, 150);
        };

        rt.on(eventName, docHandler);
        boundDocname = name;
    }

    function unbindDocRealtime(name: string) {
        const rt = (window as any)?.frappe?.realtime;
        if (!rt || !name) return;

        const eventName = `kta_calisma_karti:doc_changed:${name}`;
        if (docHandler) rt.off(eventName, docHandler);

        docHandler = null;
        clearTimeout(docTimer);
        docTimer = null;
        boundDocname = null;
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

    async function addAltOperasyon(payload: {
        alt_operasyon: string;
        hammadde?: string;
        adet: number;
        uom?: string;
        note?: string;
    }) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.add_alt_operasyon_kaydi", {
                calisma_karti: docname.value,
                ...payload,
            })
        );
    }

    async function updateAltOperasyon(payload: {
        row_id: string;
        alt_operasyon: string;
        hammadde?: string;
        adet: number;
        uom?: string;
        note?: string;
    }) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.update_alt_operasyon_kaydi", {
                calisma_karti: docname.value,
                ...payload,
            })
        );
    }

    async function deleteAltOperasyon(row_id: string) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.delete_alt_operasyon_kaydi", {
                calisma_karti: docname.value,
                row_id,
            })
        );
    }

    async function addIdcOlcumu(payload: any) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.add_idc_olcumu", {
                name: docname.value,
                ...payload,
            })
        );
    }

    async function updateIdcOlcumu(payload: any) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.update_idc_olcumu", {
                name: docname.value,
                ...payload,
            })
        );
    }

    async function deleteIdcOlcumu(rowname: string) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.delete_idc_olcumu", {
                name: docname.value,
                rowname,
            })
        );
    }

    async function addBarkodKaydi(payload: any) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.add_barkod_kaydi", {
                name: docname.value,
                ...payload,
            })
        );
    }

    async function updateBarkodKaydi(payload: any) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.update_barkod_kaydi", {
                name: docname.value,
                ...payload,
            })
        );
    }

    async function deleteBarkodKaydi(rowname: string) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.delete_barkod_kaydi", {
                name: docname.value,
                rowname,
            })
        );
    }

    async function getQcTemplates() {
        return frappe.call({
            method: "erpnextkta.kta_calisma_karti.api.get_qc_templates_for_ck",
            args: { ck_name: docname.value },
        });
    }

    async function getTemplateDetails(template_name: string) {
        return frappe.call({
            method: "erpnextkta.kta_calisma_karti.api.get_template_details",
            args: { template_name },
        });
    }

    async function submitStandardQC(payload: { template_name: string; readings: any[] }) {
        return refreshAfter(() =>
            frappe.call({
                method: "erpnextkta.kta_calisma_karti.api.submit_kta_quality_inspection",
                args: {
                    ck_name: docname.value,
                    ...payload,
                },
                freeze: true,
                freeze_message: "Kalite belgesi oluşturuluyor...",
            })
        );
    }

    // When docname changes (route changes), re-bind realtime listener
    watch(
        () => docname.value,
        (next, prev) => {
            if (prev) unbindDocRealtime(prev);
            if (next) bindDocRealtime(next);
        },
        { immediate: true }
    );

    onMounted(() => {
        if (docname.value) bindDocRealtime(docname.value);
    });

    onUnmounted(() => {
        if (boundDocname) unbindDocRealtime(boundDocname);
    });

    return {
        loading,
        doc,
        load,
        callIslem,
        updateQC,
        addHurda,
        updateHurda,
        deleteHurda,
        addIdcOlcumu,
        updateIdcOlcumu,
        deleteIdcOlcumu,
        addBarkodKaydi,
        updateBarkodKaydi,
        deleteBarkodKaydi,
        addAltOperasyon,
        updateAltOperasyon,
        deleteAltOperasyon,
        getQcTemplates,
        getTemplateDetails,
        submitStandardQC,
    };
}
