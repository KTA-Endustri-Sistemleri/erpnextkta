// utils/kalite_ui.ts
const __ = (...args: any[]) => (window as any).__(...args);

export function isQcApproved(status?: string | null): boolean {
    const s = (status || "").trim().toLowerCase();
    return s === "onaylandı" || s === "accepted";
}

export function isQcRejected(status?: string | null): boolean {
    const s = (status || "").trim().toLowerCase();
    return s === "reddedildi" || s === "rejected" || s === "red";
}

export function isQcPending(status?: string | null): boolean {
    const s = (status || "").trim().toLowerCase();
    return !s || s === "onay bekliyor" || s === "pending";
}

export function getQcThemeClass(status?: string | null): string {
    if (isQcApproved(status)) return "is-accepted";
    if (isQcRejected(status)) return "is-rejected";
    const s = (status || "").trim().toLowerCase();
    if (s === "partially accepted" || s === "kısmi kabul edildi") return "is-partial";
    return "is-default";
}

export function getQcBadgeClass(status?: string | null): string {
    if (isQcApproved(status)) return "ck-badge--success";
    if (isQcRejected(status)) return "ck-badge--danger";
    const s = (status || "").trim().toLowerCase();
    if (s === "partially accepted" || s === "kısmi kabul edildi") return "ck-badge--partial";
    return "ck-badge--info";
}

export function formatAltOpLabel(title?: string | null, name?: string | null): string {
    const t = (title || "").trim();
    const n = (name || "").trim();
    if (t && n && t !== n) {
        return `${t} [${n}]`;
    }
    return t || n || "";
}

export function extractAltOpCode(val?: string | null): string {
    const s = (val || "").trim();
    if (s.includes("[") && s.endsWith("]")) {
        return s.split("[").pop()?.replace("]", "").trim() || "";
    }
    return s;
}

export function formatAltOpRowLabel(r: any): string {
    if (!r) return "";
    const title = r.alt_operasyon_title || r.title || r.alt_operasyon || "";
    const code = r.alt_operasyon || "";
    const display = r.alt_operasyon_display || formatAltOpLabel(title, code);
    if (r.satir_no) {
        return `${r.satir_no} - ${display}`;
    }
    if (r.kalip_no) {
        return `${__("Kalıp")} ${r.kalip_no} - ${display}`;
    }
    return display;
}

export function fmtDt(val?: string) {
    if (!val) return "";
    try {
        const d = new Date(val);
        if (isNaN(d.getTime())) return val;
        return d.toLocaleString("tr-TR");
    } catch {
        return val || "";
    }
}

export function copyToClipboard(text?: string) {
    const t = (text || "").trim();
    if (!t) return;
    navigator.clipboard?.writeText(t).then(
        () => frappe.show_alert({ message: __("Kopyalandı"), indicator: "green" }),
        () => frappe.msgprint(__("Kopyalama başarısız."))
    );
}

/** Visual-only deterministic bars (not a real barcode encoding). */
export function barcodeBars(str?: string) {
    const s = (str || "").trim();
    if (!s) return [];
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) {
        h ^= s.charCodeAt(i);
        h = Math.imul(h, 16777619);
    }
    const bars: number[] = [];
    let x = h >>> 0;
    for (let i = 0; i < 42; i++) {
        x = (x * 1103515245 + 12345) >>> 0;
        bars.push(1 + (x % 3));
    }
    return bars;
}

export function barX(bars: number[], idx: number) {
    let sum = 0;
    for (let i = 0; i < idx; i++) sum += bars[i] || 0;
    return sum;
}

export function barOpacity(idx: number) {
    return idx % 2 === 0 ? 1 : 0.15;
}

export function openActionSheet(title: string, options: string[], onPick: (picked: string) => void) {
    frappe.prompt(
        [
            {
                fieldtype: "Select",
                label: title,
                fieldname: "action",
                reqd: 1,
                options: options.join("\n"),
            },
        ],
        (v: any) => onPick(v.action),
        title,
        __("Seç")
    );
}

function extractFirstNumber(val: any): number {
    if (!val) return Infinity;
    const match = String(val).trim().match(/^(\d+(?:\.\d+)?)/);
    return match ? parseFloat(match[1]) : Infinity;
}

export function compareNatural(aStr?: string | null, bStr?: string | null): number {
    const sA = (aStr || "").trim();
    const sB = (bStr || "").trim();
    if (sA && !sB) return -1;
    if (!sA && sB) return 1;
    if (!sA && !sB) return 0;

    const numA = extractFirstNumber(sA);
    const numB = extractFirstNumber(sB);
    if (numA !== numB && numA !== Infinity && numB !== Infinity) {
        return numA - numB;
    }
    return sA.localeCompare(sB, undefined, { numeric: true, sensitivity: "base" });
}

export function sortAltOperasyonRows<T extends Record<string, any>>(rows: T[]): T[] {
    return [...(rows || [])].sort((a, b) => {
        // 1. Satır No varsa (Kablo Kesme, Krimp, IDC vb.) öncelikli doğal sıralama:
        const satA = (a.satir_no || "").toString().trim();
        const satB = (b.satir_no || "").toString().trim();
        if (satA || satB) {
            const res = compareNatural(satA, satB);
            if (res !== 0) return res;
        }

        // 2. Satır No yoksa Kalıp No varsa (Enjeksiyon vb.) kalıba göre doğal sıralama:
        const klpA = (a.kalip_no || "").toString().trim();
        const klpB = (b.kalip_no || "").toString().trim();
        if (klpA || klpB) {
            const res = compareNatural(klpA, klpB);
            if (res !== 0) return res;
        }

        // 3. Tanımdaki alt operasyon sequence değeri:
        const seqDiff = (a.alt_operasyon_sequence ?? 0) - (b.alt_operasyon_sequence ?? 0);
        if (seqDiff !== 0) return seqDiff;

        // 4. Kart içi eklenme sırası (idx):
        return (a.idx ?? 0) - (b.idx ?? 0);
    });
}