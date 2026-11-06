import { useMrpState } from "./useMrpState";

const __ = (...args: any[]) => (window as any).__(...args);

export function useMrpExport() {
  const { filters, weeks, filteredMaterials } = useMrpState();

  function exportExcel() {
    const url = `/api/method/erpnextkta.kta_mrp.mrp_engine.service.export_material_requirements_excel?filters=${encodeURIComponent(
      JSON.stringify({
        from_date: filters.from_date,
        to_date: filters.to_date,
        weekly_view: filters.weekly_view,
        group_by: filters.group_by,
        supplier: filters.supplier || undefined,
        hammadde: filters.hammadde || undefined,
        custom_musteri_grubu: filters.custom_musteri_grubu || undefined,
        item_group: filters.item_group || undefined,
      })
    )}`;
    window.open(url, "_blank");
  }

  function exportCsv() {
    const items = filteredMaterials.value;
    const weekCols = weeks.value;
    const view = filters.weekly_view;

    const viewFieldMap: Record<string, "order" | "net" | "gross" | "projected"> = {
      "Önerilen Sipariş": "order",
      "Net İhtiyaç": "net",
      "Brüt İhtiyaç": "gross",
      "Projeksiyon Bakiye": "projected",
    };
    const metricKey = viewFieldMap[view] || "order";

    const headers = [
      __("Hammadde Kodu"),
      __("Ürün Açıklaması"),
      __("Birim"),
      __("Varsayılan Tedarikçi"),
      __("Stok"),
      __("Rezerve Stok"),
      __("Serbest Stok"),
      __("Temin Süresi (Gün)"),
      __("Min. Sipariş Miktarı (MOQ)"),
      __("Paketleme Katı"),
      __("Birim Fiyat"),
      __("Para Birimi"),
      __("Önerilen Sipariş Tutarı"),
      ...weekCols.map((w) => w.label),
    ];

    const rows: string[][] = [headers];

    items.forEach((m) => {
      const row = [
        `"${m.item_code.replace(/"/g, '""')}"`,
        `"${m.item_name.replace(/"/g, '""')}"`,
        `"${m.uom}"`,
        `"${m.supplier.replace(/"/g, '""')}"`,
        String(m.actual_stock),
        String(m.reserved_stock),
        String(m.free_stock),
        String(m.lead_time_days),
        String(m.moq),
        String(m.pack),
        String(m.unit_price),
        `"${m.currency}"`,
        String(m.order_amount),
      ];

      weekCols.forEach((w) => {
        const val = m.weeks[w.key]?.[metricKey] || 0;
        row.push(String(val));
      });

      rows.push(row);
    });

    const csvContent = "\uFEFF" + rows.map((r) => r.join(";")).join("\r\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    const today = new Date().toISOString().split("T")[0];
    link.href = URL.createObjectURL(blob);
    link.setAttribute("download", `Hammadde_Ihtiyac_${today}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function triggerPrint() {
    window.print();
  }

  return {
    exportExcel,
    exportCsv,
    triggerPrint,
  };
}
