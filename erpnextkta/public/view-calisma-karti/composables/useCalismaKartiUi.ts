import { computed, ref, watch } from "vue";

export type CKState = "ready" | "running" | "paused" | "finished" | "rejected" | "cancelled";

export function useCalismaKartiUi(docRef: any) {
    function computeState(d: any): CKState {
        if (!d) return "ready";
        
        // Cancelled status takes absolute precedence
        if (Number(d.docstatus) === 2 || (d.durum || "").toString().toLowerCase().includes("iptal")) return "cancelled";

        // If QC rejected, lock UI state
        if ((d.kalite_kontrol || "").trim() === "Reddedildi" || (d.durum || "").toString().includes("Reddedildi")) return "rejected";

        const duruslar = d.duruslar || [];
        const hasOpenStop = duruslar.some((x: any) => x?.durus_baslangic && !x?.durus_bitis);

        if (d.durum === "Bitmiş" || d.bitis_saati) return "finished";
        if (d.durum === "Duruşta" || hasOpenStop) return "paused";
        if (!d.baslangic_saati && d.durum === "Hazır") return "ready";
        return "running";
    }

    const state = computed<CKState>(() => computeState(docRef.value));

    const durumLabel = computed(
        () =>
        ({
            ready: "Hazır",
            running: "Çalışıyor",
            paused: "Duruşta",
            finished: "Bitmiş",
            rejected: "Reddedildi",
            cancelled: "İptal Edildi",
        }[state.value] || "-")
    );

    const statusClass = computed(
        () =>
        ({
            ready: "ck-status--ready",
            running: "ck-status--running",
            paused: "ck-status--paused",
            finished: "ck-status--finished",
            rejected: "ck-status--rejected",
            cancelled: "ck-status--cancelled",
        }[state.value] || "ck-status--ready")
    );

    const qcValue = computed(() => (docRef.value?.kalite_kontrol || "Onay Bekliyor").trim());
    const qcLabel = computed(() => qcValue.value);
    const qcApproved = computed(() => qcValue.value === "Onaylandı");

    const qcClass = computed(() => {
        if (qcValue.value === "Onaylandı") return "ck-status-qc--running"; // green
        if (qcValue.value === "Onay Bekliyor") return "ck-status-qc--pending"; // blue
        if (qcValue.value === "Reddedildi") return "ck-status-qc--rejected"; // red
        return "ck-status--paused";
    });

    const qcOptions = ["Onay Bekliyor", "Onaylandı", "Reddedildi"];

    const canEditQC = computed(() => {
        // [STRATEGY] Locked if a QI document is already linked. 
        // Quality status must then be managed via the QI document itself.
        if (docRef.value?.quality_inspection) return false;

        const roles = frappe?.boot?.user?.roles || [];
        const adminRoles = frappe?.boot?.kta_admin_roles || ["System Manager", "Quality Manager", "Manufacturing Manager"];
        return adminRoles.some((r: string) => roles.includes(r));
    });

    const canEditData = computed(() => {
        if (state.value === "cancelled") return false;

        const roles = frappe?.boot?.user?.roles || [];
        const adminRoles = frappe?.boot?.kta_admin_roles || ["System Manager", "Quality Manager", "Manufacturing Manager"];
        
        const isManager = adminRoles.some((r: string) => roles.includes(r));
                          
        if (isManager) return true;

        // Normal operators can only edit if not finished/rejected/cancelled, and maybe not 'ready'
        return state.value !== "finished" && state.value !== "rejected" && state.value !== "ready";
    });

    const qcFormValue = ref("Onay Bekliyor");
    watch(
        qcValue,
        (v) => {
            qcFormValue.value = v;
        },
        { immediate: true }
    );

    const isCancelled = computed(() => state.value === "cancelled");
    const showStart = computed(() => state.value === "ready" && !isCancelled.value);
    const isRejected = computed(() => state.value === "rejected");
    const showResume = computed(() => state.value === "paused" && !isRejected.value && !isCancelled.value);
    const showStop = computed(() => state.value === "running" && !isRejected.value && !isCancelled.value);
    const showFinish = computed(
        () => !isRejected.value && !isCancelled.value && (state.value === "running" || state.value === "paused") && qcApproved.value
    );

    return {
        state,
        durumLabel,
        statusClass,
        qcValue,
        qcLabel,
        qcApproved,
        qcClass,
        qcOptions,
        canEditQC,
        qcFormValue,
        showStart,
        showResume,
        showStop,
        showFinish,
        isRejected,
        isCancelled,
        canEditData,
    };
}