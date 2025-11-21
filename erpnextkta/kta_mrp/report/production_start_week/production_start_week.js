frappe.query_reports["Production Start Week"] = {
  onload: function (report) {
    const update_item_groups = () => {
      frappe.call({
        method: "erpnextkta.kta_mrp.report.production_start_week.production_start_week.get_item_groups",
        args: {
          from_date: report.get_filter_value("from_date"),
          to_date: report.get_filter_value("to_date")
        },
        callback: function (r) {
          const field = report.get_filter("item_group");
          field.df.options = ["", ...r.message];
          field.refresh();
        }
      });
    };

    // Rapor yüklendiğinde item_group listesini güncelle
    update_item_groups();

    // Kullanıcı manuel olarak yenilemek isterse butonla yapabilsin
    report.page.set_primary_action(__("Yenile Ürün Grupları"), update_item_groups);
  },

  filters: [
    {
      fieldname: "from_date",
      label: __("Başlangıç Tarihi"),
      fieldtype: "Date",
      default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
      reqd: 1,
      onchange: function () {
        frappe.query_report.refresh();
      }
    },
    {
      fieldname: "to_date",
      label: __("Bitiş Tarihi"),
      fieldtype: "Date",
      default: frappe.datetime.get_today(),
      reqd: 1,
      onchange: function () {
        frappe.query_report.refresh();
      }
    },
    {
      fieldname: "item_group",
      label: __("Ürün Grubu"),
      fieldtype: "Select",
      options: [],
      onchange: function () {
        frappe.query_report.refresh(); // Grup değişince rapor otomatik çalışsın
      }
    },
    {
      fieldname: "group_by_item_only",
      label: __("Yalnızca Ürün Bazlı Grupla"),
      fieldtype: "Check",
      default: 0,
      onchange: function () {
        frappe.query_report.refresh();
      }
    }
  ]
};
