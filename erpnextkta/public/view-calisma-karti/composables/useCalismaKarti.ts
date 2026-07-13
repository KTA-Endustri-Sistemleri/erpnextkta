import { computed, ref, onMounted, onUnmounted, watch } from "vue";

const __ = (...args: any[]) => (window as any).__(...args);

export function useCalismaKarti(docname: ReturnType<typeof computed<string | null>>) {
    const loading = ref(false);
    const doc = ref<any | null>(null);
    const lastRefreshTime = ref(0);
    const pendingUpdate = ref(false);
    const showAutoPausedModal = ref(false);
    const autoPausedCards = ref<any[]>([]);
    
    const settings = ref({
        liste_yenileme_araligi_sn: 30,
        detay_yenileme_araligi_sn: 10
    });

    async function loadSettings() {
        try {
            const r = await (window as any).frappe.db.get_doc("KTA Calisma Karti Settings");
            if (r) {
                settings.value = {
                    liste_yenileme_araligi_sn: r.liste_yenileme_araligi_sn || 30,
                    detay_yenileme_araligi_sn: r.detay_yenileme_araligi_sn || 10
                };
            }
        } catch (e) {
            console.error("Settings load failed", e);
        }
    }

    async function load() {
        if (!docname.value) return;
        loading.value = true;
        try {
            const r = await frappe.call(
                "erpnextkta.kta_calisma_karti.api.get_calisma_karti_detail",
                { name: docname.value }
            );
            doc.value = r.message || null;
            lastRefreshTime.value = Date.now();
            pendingUpdate.value = false;
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
            if (loading.value) return;

            const now = Date.now();
            const intervalMs = settings.value.detay_yenileme_araligi_sn * 1000;
            const timeSinceLast = now - lastRefreshTime.value;

            if (timeSinceLast >= intervalMs) {
                load();
            } else {
                pendingUpdate.value = true;
                clearTimeout(docTimer);
                docTimer = setTimeout(() => {
                    if (!loading.value) load();
                }, intervalMs - timeSinceLast);
            }
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

    async function checkActiveCardData(): Promise<{
        has_incomplete: boolean;
        mode?: "hard" | "soft";
        card_name?: string;
        card_label?: string;
        missing?: string[];
    }> {
        const r = await frappe.call(
            "erpnextkta.kta_calisma_karti.api.check_active_card_data"
        );
        return r.message || { has_incomplete: false };
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
        aciklama?: string | null;
    }) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api_impl.hurda.add_hurda", {
                name: docname.value,
                ...payload,
            })
        );
    }

    async function updateHurda(payload: {
        rowname: string;
        parca_no: string;
        hurda_nedeni: string;
        miktar: number;
        aciklama?: string | null;
    }) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api_impl.hurda.update_hurda", {
                name: docname.value,
                ...payload,
            })
        );
    }

    async function deleteHurda(rowname: string) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api_impl.hurda.delete_hurda", {
                name: docname.value,
                rowname,
            })
        );
    }

    async function addAltOperasyon(payload: any) {
        // payload expects: { alt_operasyon: string, note?: string, satir_no?: string, hammadde_tuketimleri: any[] }
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.add_alt_operasyon_kaydi", {
                calisma_karti: docname.value,
                ...payload,
            })
        );
    }

    async function updateAltOperasyon(payload: any) {
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

    async function addKrimpOlcumu(payload: any) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.add_krimp_olcumu", {
                name: docname.value,
                payload,
            })
        );
    }

    async function updateKrimpOlcumu(payload: any) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.update_krimp_olcumu", {
                name: docname.value,
                ...payload,
            })
        );
    }

    async function deleteKrimpOlcumu(rowname: string) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.delete_krimp_olcumu", {
                name: docname.value,
                rowname,
            })
        );
    }

    async function addEnjeksiyonOlcumu(payload: any) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.add_enjeksiyon_olcumu", {
                name: docname.value,
                payload,
            })
        );
    }

    async function updateEnjeksiyonOlcumu(payload: any) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.update_enjeksiyon_olcumu", {
                name: docname.value,
                ...payload,
            })
        );
    }

    async function deleteEnjeksiyonOlcumu(rowname: string) {
        return refreshAfter(() =>
            frappe.call("erpnextkta.kta_calisma_karti.api.delete_enjeksiyon_olcumu", {
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

    async function submitStandardQC(payload: { template_name: string; readings: any[]; sample_size?: number; intent?: string; rowname?: string }) {
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

    async function checkAutoPausedCards() {
        const operatorName = doc.value?.operator;
        if (!operatorName) return;

        return frappe.call({
            method: 'erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.get_auto_paused_cards',
            args: { operator: operatorName },
            callback: function(r: any) {
                const cards = r.message || [];
                const other_cards = cards.filter((c: any) => c.name !== docname.value);
                
                if (other_cards.length > 0) {
                    autoPausedCards.value = other_cards;
                    showAutoPausedModal.value = true;
                }
            }
        });
    }

    async function handleAutoPausedAction(action: 'baslat' | 'git', targetDocname: string) {
        if (action === 'git') {
            return;
        }

        return new Promise<void>((resolve, reject) => {
            frappe.call({
                method: 'erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti.islem_yap',
                args: { docname: targetDocname, islem_tipi: 'Baslat' },
                freeze: false,
                callback: function(r: any) {
                    if (r.message && r.message.status === 'success') {
                        resolve();
                    } else {
                        reject(new Error("İşlem Başarısız"));
                    }
                }
            });
        });
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

    onMounted(async () => {
        await loadSettings();
        if (docname.value) bindDocRealtime(docname.value);
    });

    onUnmounted(() => {
        if (boundDocname) unbindDocRealtime(boundDocname);
    });

    return {
        loading,
        doc,
        load,
        checkActiveCardData,
        callIslem,
        updateQC,
        addHurda,
        updateHurda,
        deleteHurda,
        addIdcOlcumu,
        updateIdcOlcumu,
        deleteIdcOlcumu,
        addKrimpOlcumu,
        updateKrimpOlcumu,
        deleteKrimpOlcumu,
        addEnjeksiyonOlcumu,
        updateEnjeksiyonOlcumu,
        deleteEnjeksiyonOlcumu,
        addBarkodKaydi,
        updateBarkodKaydi,
        deleteBarkodKaydi,
        addAltOperasyon,
        updateAltOperasyon,
        deleteAltOperasyon,
        getQcTemplates,
        getTemplateDetails,
        submitStandardQC,
        pendingUpdate,
        showAutoPausedModal,
        autoPausedCards,
        checkAutoPausedCards,
        handleAutoPausedAction
    };
}
