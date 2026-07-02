// utils/kalite_ui.ts
const __ = (...args: any[]) => (window as any).__(...args);

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