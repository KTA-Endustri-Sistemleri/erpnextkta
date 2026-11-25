import { markRaw } from "vue";
import OperationCompletionReport from "../components/reports/OperationCompletionReport.vue";
import MaterialShortageReport from "../components/reports/MaterialShortageReport.vue";
import type { ReportDefinition } from "../types";

export const REPORT_CATALOG: ReportDefinition[] = [
  {
    id: "operation_completion",
    title: "İş Emri Operasyon Tamamlanma Özeti",
    description:
      "Aktif iş emirlerinde teyit edilmiş tamamlanan ve kısmi operasyonların durumu, son onay bilgisi ve fiş detayları.",
    category: "Üretim Teyitleri",
    icon: "✅",
    component: markRaw(OperationCompletionReport),
  },
  {
    id: "material_shortage",
    title: "Eksik Malzeme ile Açılan İş Emirleri",
    description:
      "Eksik hammadde ile serbest bırakılmış aktif iş emirlerinin canlı stok karşılama durumu, eksik kalemleri ve depo detayları.",
    category: "Malzeme ve Stok",
    icon: "⚠️",
    component: markRaw(MaterialShortageReport),
  },
];

export function getReportById(id: string): ReportDefinition | null {
  return REPORT_CATALOG.find((report) => report.id === id) || null;
}
