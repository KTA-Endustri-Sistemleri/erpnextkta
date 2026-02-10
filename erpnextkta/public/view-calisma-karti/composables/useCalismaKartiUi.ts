import { computed, ref, watch } from "vue";

export type CKState = "ready" | "running" | "paused" | "finished";

export function useCalismaKartiUi(docRef: any) {
    function computeState(d: any): CKState {
        const duruslar = d?.duruslar || [];
        const hasOpenStop = duruslar.some((x: any) => x?.durus_baslangic && !x?.durus_bitis);

        if (d?.bitis_saati) return "finished";
        if (!d?.baslangic_saati) return "ready";
        if (hasOpenStop) return "paused";
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
        const roles = frappe?.boot?.user?.roles || [];
        return (
            roles.includes("System Manager") ||
            roles.includes("Quality Manager") ||
            roles.includes("KTA Kalite Kullanıcısı")
        );
    });

    const qcFormValue = ref("Onay Bekliyor");
    watch(
        qcValue,
        (v) => {
            qcFormValue.value = v;
        },
        { immediate: true }
    );

    const showStart = computed(() => state.value === "ready");
    const showResume = computed(() => state.value === "paused");
    const showStop = computed(() => state.value === "running");
    const showFinish = computed(
        () => (state.value === "running" || state.value === "paused") && qcApproved.value
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
    };
}