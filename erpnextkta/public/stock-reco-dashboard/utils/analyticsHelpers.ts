import type {
  RecoAnalyticsItem,
  RecoAnomalyItem,
  RecoDocDetail,
} from "../types";

type TranslateFn = (msg: string, replace?: any[]) => string;

export function formatAnalyticsNumber(v: number | null | undefined): string {
  return Number(v || 0).toLocaleString(undefined, {
    maximumFractionDigits: 3,
  });
}

export function normalizeAnalyticsRow(it: any): RecoAnalyticsItem {
  const net = Number(it.net_diff || 0);
  let plus = 0;
  let minus = 0;
  const wh = Array.isArray(it.warehouses) ? it.warehouses : [];
  wh.forEach((w: any) => {
    const d = Number(w.diff || 0);
    if (d >= 0) plus += d;
    else minus += d;
  });
  const docs = Number(it.docs_count || 0);
  return {
    ...it,
    net_diff: net,
    total_plus: plus,
    total_minus: minus,
    docs_count: docs,
    risk_score: Math.abs(net) * Math.log(docs + 1),
    warehouses: wh,
  };
}

export function computeAnalyticsKpi(rows: RecoAnalyticsItem[]) {
  const whSet = new Set<string>();
  let totalPlus = 0;
  let totalMinus = 0;
  let net = 0;
  let maxDocs = 0;
  rows.forEach((it) => {
    net += Number(it.net_diff || 0);
    totalPlus += Number(it.total_plus || 0);
    totalMinus += Number(it.total_minus || 0);
    maxDocs = Math.max(maxDocs, Number(it.docs_count || 0));
    (it.warehouses || []).forEach((w) => whSet.add(w.warehouse));
  });
  return {
    itemsCount: rows.length,
    warehousesCount: whSet.size,
    totalPlus,
    totalMinus,
    net,
    maxDocsCount: maxDocs,
  };
}

function clamp(n: number, a: number, b: number): number {
  return Math.max(a, Math.min(b, n));
}

function severityFromScore(score: number): "HIGH" | "MED" | "LOW" {
  return score >= 75 ? "HIGH" : score >= 45 ? "MED" : "LOW";
}

function whStats(it: RecoAnalyticsItem) {
  let hasPos = false;
  let hasNeg = false;
  let totalAbs = 0;
  let maxAbs = 0;
  let maxWh = "";
  let maxDiff = 0;

  for (const w of it.warehouses || []) {
    const d = Number(w.diff || 0);
    if (d > 0) hasPos = true;
    if (d < 0) hasNeg = true;
    const a = Math.abs(d);
    totalAbs += a;
    if (a > maxAbs) {
      maxAbs = a;
      maxWh = w.warehouse;
      maxDiff = d;
    }
  }

  return {
    hasPos,
    hasNeg,
    totalAbs,
    maxAbs,
    maxWh,
    maxDiff,
    ratio: totalAbs > 0 ? maxAbs / totalAbs : 0,
    whCount: (it.warehouses || []).length,
  };
}

export function buildBaseAnomalies(
  rows: RecoAnalyticsItem[],
  __: TranslateFn
): RecoAnomalyItem[] {
  const out: RecoAnomalyItem[] = [];
  for (const it of rows) {
    const net = Number(it.net_diff || 0);
    const docsCount = Number(it.docs_count || 0);
    const st = whStats(it);

    if (st.hasPos && st.hasNeg && st.totalAbs > 0) {
      const score =
        20 +
        25 * Math.log10(st.totalAbs + 1) +
        10 * Math.log(docsCount + 1) +
        8 * st.whCount;
      out.push({
        id: `contr-${it.item_code}`,
        type: "CONTRADICTION",
        severity: severityFromScore(score),
        score: clamp(score, 0, 100),
        title: __("Depolar arası zıt yön"),
        desc: __("{0} depolar arasında hem + hem − fark gösteriyor.", [
          it.item_code,
        ]),
        action: { kind: "item", item_code: it.item_code },
      });
    }

    if (st.ratio >= 0.8 && st.totalAbs > 0) {
      const score =
        15 +
        30 * st.ratio +
        22 * Math.log10(st.totalAbs + 1) +
        6 * Math.log(docsCount + 1);
      out.push({
        id: `conc-${it.item_code}`,
        type: "CONCENTRATION",
        severity: severityFromScore(score),
        score: clamp(score, 0, 100),
        title: __("Tek depoda toplandı"),
        desc: __('Hareketin %{0} kadarı "{1}" deposundan ({2}).', [
          Math.round(st.ratio * 100),
          st.maxWh,
          formatAnalyticsNumber(st.maxDiff),
        ]),
        action: { kind: "item", item_code: it.item_code },
      });
    }

    if (docsCount >= 8) {
      const score =
        18 +
        14 * Math.log(docsCount + 1) +
        18 * Math.log10(Math.abs(net) + 1) +
        6 * st.whCount;
      out.push({
        id: `churn-${it.item_code}`,
        type: "CHURN",
        severity: severityFromScore(score),
        score: clamp(score, 0, 100),
        title: __("Sık değişiklik"),
        desc: __(
          "{0} kalemi {1} belgede yer alıyor (yüksek denetim riski).",
          [it.item_code, docsCount]
        ),
        action: { kind: "item", item_code: it.item_code },
      });
    }

    if (st.totalAbs > 0) {
      const ratioNet = Math.abs(net) / st.totalAbs;
      if (st.totalAbs >= 10 && ratioNet <= 0.15) {
        const score =
          22 +
          30 * (1 - ratioNet) +
          20 * Math.log10(st.totalAbs + 1) +
          8 * Math.log(docsCount + 1);
        out.push({
          id: `osci-${it.item_code}`,
          type: "OSCILLATION",
          severity: severityFromScore(score),
          score: clamp(score, 0, 100),
          title: __("Gidiş-geliş hareketi"),
          desc: __("Toplam hareket {0} ancak net {1} (oran %{2}).", [
            formatAnalyticsNumber(st.totalAbs),
            formatAnalyticsNumber(net),
            Math.round(ratioNet * 100),
          ]),
          action: { kind: "item", item_code: it.item_code },
        });
      }
    }
  }
  return out;
}

export function buildDrawerAnomalies(
  selected: RecoAnalyticsItem | null,
  details: RecoDocDetail[],
  __: TranslateFn
): RecoAnomalyItem[] {
  if (!selected || !details?.length) return [];

  const absList = details
    .map((d) => Math.abs(Number(d.diff_qty || 0)))
    .filter(Number.isFinite);
  const sumAbs = absList.reduce((a, b) => a + b, 0);
  const avgAbs = absList.length ? sumAbs / absList.length : 0;

  let maxDoc: RecoDocDetail | null = null;
  for (const d of details) {
    if (
      !maxDoc ||
      Math.abs(Number(d.diff_qty || 0)) > Math.abs(Number(maxDoc.diff_qty || 0))
    ) {
      maxDoc = d;
    }
  }

  const net = Number(selected.net_diff || 0);
  const out: RecoAnomalyItem[] = [];

  if (details.length >= 2 && maxDoc) {
    const amax = Math.abs(Number(maxDoc.diff_qty || 0));
    const contributes = sumAbs > 0 ? amax / sumAbs : 0;
    if (amax >= avgAbs * 3 || contributes >= 0.7) {
      const score = 35 + 35 * contributes + 20 * Math.log10(amax + 1);
      out.push({
        id: `spike-${selected.item_code}-${maxDoc.name}`,
        type: "DOC_SPIKE",
        severity: severityFromScore(score),
        score: clamp(score, 0, 100),
        title: __("Tek belge sonuca hakim"),
        desc: __(
          "{0} belgesi ürün hareketinin %{1} kadarını oluşturuyor ({2}).",
          [
            maxDoc.name,
            Math.round(contributes * 100),
            formatAnalyticsNumber(maxDoc.diff_qty),
          ]
        ),
        action: { kind: "doc", docname: maxDoc.name },
      });
    }
  }

  if (sumAbs > 0) {
    const ratioNet = Math.abs(net) / sumAbs;
    if (sumAbs >= 10 && ratioNet <= 0.12 && details.length >= 3) {
      const score = 30 + 35 * (1 - ratioNet) + 18 * Math.log10(sumAbs + 1);
      out.push({
        id: `osci-doc-${selected.item_code}`,
        type: "DOC_OSCILLATION",
        severity: severityFromScore(score),
        score: clamp(score, 0, 100),
        title: __("Belgeler arası gidiş-geliş"),
        desc: __("Toplam belge hareketi {0} ancak net {1} (oran %{2}).", [
          formatAnalyticsNumber(sumAbs),
          formatAnalyticsNumber(net),
          Math.round(ratioNet * 100),
        ]),
        action: { kind: "item", item_code: selected.item_code },
      });
    }
  }

  return out.sort((a, b) => b.score - a.score);
}

function csvCell(v: unknown): string {
  const s = String(v ?? "");
  return s.includes(",") || s.includes('"') || s.includes("\n")
    ? `"${s.replace(/"/g, '""')}"`
    : s;
}

export function exportAnalyticsCsv(rows: RecoAnalyticsItem[], year: number) {
  const headers = [
    "item_code",
    "item_name",
    "uom",
    "net_diff",
    "total_plus",
    "total_minus",
    "docs_count",
    "warehouses_count",
  ];
  const lines = [headers.join(",")];
  rows.forEach((it) => {
    lines.push(
      [
        csvCell(it.item_code),
        csvCell(it.item_name),
        csvCell(it.uom),
        Number(it.net_diff || 0),
        Number(it.total_plus || 0),
        Number(it.total_minus || 0),
        Number(it.docs_count || 0),
        Number(it.warehouses?.length || 0),
      ].join(",")
    );
  });
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `stock-reco-dashboard-${year}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
