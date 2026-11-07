import { computed, ref, watch } from "vue";
import { isQcApproved, isQcPending, isQcRejected } from "../utils/kalite_ui";
const __ = (...args: any[]) => (window as any).__(...args);

export type CKState = "ready" | "running" | "paused" | "finished" | "rejected" | "cancelled";

export function useCalismaKartiUi(docRef: any) {
    function computeState(d: any): CKState {
        if (!d) return "ready";

        // Cancelled status takes absolute precedence
        if (Number(d.docstatus) === 2 || (d.durum || "").toString().toLowerCase().includes("iptal")) return "cancelled";

        // Classic QC rejection:
        if (Number(d.alt_operasyon_bazli_kalite) !== 1) {
            if ((d.kalite_kontrol || "").trim() === "Reddedildi" || (d.durum || "").toString().includes("Reddedildi")) return "rejected";
        } else {
            // In sub-op mode: Only reject state if card is finished AND all sub-ops are rejected
            const altOps = d.alt_operasyon_kayitlari || [];
            if ((d.bitis_saati || d.durum === "Bitmiş") && altOps.length > 0 && altOps.every((r: any) => isQcRejected(r.quality_inspection_status))) {
                return "rejected";
            }
        }

        const duruslar = d.duruslar || [];
        const hasOpenStop = duruslar.some((x: any) => x?.durus_baslangic && !x?.durus_bitis);

        if (d.durum === "Bitmiş" || d.bitis_saati) return "finished";
        if (d.durum === "Duruşta" || hasOpenStop) return "paused";
        if (!d.baslangic_saati && d.durum === "Hazır") return "ready";
        return "running";
    }

    const state = computed<CKState>(() => computeState(docRef.value));

    const durumLabel = computed(() => {
        if (state.value === "paused") {
            const duruslar = docRef.value?.duruslar || [];
            const lastDurus = duruslar[duruslar.length - 1];
            if (lastDurus && !lastDurus.durus_bitis && lastDurus.durus_nedeni === "Arıza") {
                return __("Duruşta (Arıza)");
            }
        }
        return {
            ready: __("Hazır"),
            running: __("Çalışıyor"),
            paused: __("Duruşta"),
            finished: __("Bitmiş"),
            rejected: __("Reddedildi"),
            cancelled: __("İptal Edildi"),
        }[state.value] || "-";
    });

    const statusClass = computed(() => {
        if (state.value === "paused") {
            const duruslar = docRef.value?.duruslar || [];
            const lastDurus = duruslar[duruslar.length - 1];
            if (lastDurus && !lastDurus.durus_bitis && lastDurus.durus_nedeni === "Arıza") {
                return "ck-status--ariza";
            }
        }
        return {
            ready: "ck-status--ready",
            running: "ck-status--running",
            paused: "ck-status--paused",
            finished: "ck-status--finished",
            rejected: "ck-status--rejected",
            cancelled: "ck-status--cancelled",
        }[state.value] || "ck-status--ready";
    });

    const qcValue = computed(() => {
        const isFinished = !!(docRef.value?.bitis_saati || docRef.value?.durum === "Bitmiş" || docRef.value?.docstatus === 1);
        if (isFinished && docRef.value?.kalite_kontrol) {
            return docRef.value.kalite_kontrol.trim();
        }

        if (Number(docRef.value?.alt_operasyon_bazli_kalite) === 1) {
            const altOps = docRef.value?.alt_operasyon_kayitlari || [];
            if (altOps.length === 0) return "Onay Bekliyor";

            const hasPending = altOps.some((r: any) => isQcPending(r.quality_inspection_status));
            const hasApproved = altOps.some((r: any) => isQcApproved(r.quality_inspection_status));
            const hasRejected = altOps.some((r: any) => isQcRejected(r.quality_inspection_status));
            const allApproved = altOps.every((r: any) => isQcApproved(r.quality_inspection_status));
            const allRejected = altOps.every((r: any) => isQcRejected(r.quality_inspection_status));

            if (allApproved) return "Onaylandı";
            if (allRejected) return "Reddedildi";

            // Kart bitmişse ve en az 1 onaylı satır varsa (kalanlar bekleyen veya ret):
            if (isFinished && hasApproved) return "Kısmi Kabul Edildi";

            if (hasPending) return "Onay Bekliyor";
            if (hasApproved && hasRejected) return "Kısmi Kabul Edildi";
            return "Onay Bekliyor";
        }
        return (docRef.value?.kalite_kontrol || "Onay Bekliyor").trim();
    });

    const qcLabel = computed(() => __(qcValue.value));
    const qcApproved = computed(() => qcValue.value === "Onaylandı");

    const qcClass = computed(() => {
        if (qcValue.value === "Onaylandı") return "ck-status-qc--running"; // green
        if (qcValue.value === "Onay Bekliyor") return "ck-status-qc--pending"; // blue
        if (qcValue.value === "Reddedildi") return "ck-status-qc--rejected"; // red
        if (qcValue.value === "Kısmi Kabul Edildi") return "ck-status-qc--partial"; // purple / indigo
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
    const qcBypass = computed(() =>
        Number(docRef.value?.alt_operasyon_bazli_kalite) === 1 &&
        Number(docRef.value?.yuzde_yuz_kalite_kontrol) === 0
    );

    const showFinish = computed(() => {
        if (isCancelled.value) return false;
        if (state.value !== "running" && state.value !== "paused") return false;

        // Sub-op mode:
        if (Number(docRef.value?.alt_operasyon_bazli_kalite) === 1) {
            const altOps = docRef.value?.alt_operasyon_kayitlari || [];
            if (altOps.length === 0) return false;

            const hasApproved = altOps.some((r: any) => isQcApproved(r.quality_inspection_status));
            const allRejected = altOps.every((r: any) => isQcRejected(r.quality_inspection_status));
            const hasPending = altOps.some((r: any) => isQcPending(r.quality_inspection_status));

            // Eğer tüm alt işlemler reddedilmişse kart "Reddedildi" olarak kapatılabilir
            if (allRejected) return true;

            // %100 Kalite Kontrol seçili: Açıkta "Onay Bekliyor" satır kalmamış olmalı (ret satır olsa dahi Kısmi Kabul ile kapatılabilir)
            if (Number(docRef.value?.yuzde_yuz_kalite_kontrol) === 1) {
                return !hasPending && hasApproved;
            }

            // %100 Kalite Kontrol seçili değil: Minimum 1 alt işlem onaylı olmalı ki onaysız kapatılamasın
            return hasApproved;
        }

        // Klasik mod:
        return qcApproved.value;
    });

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
        qcBypass,
    };
}