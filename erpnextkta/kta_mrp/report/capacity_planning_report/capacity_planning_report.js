frappe.query_reports["Capacity Planning Report"] = {
  onload: function (report) {
    function updateItemGroupOptions() {
      const from_date = report.get_filter_value("from_date");
      const to_date = report.get_filter_value("to_date");

      if (!from_date || !to_date) return;

      frappe.call({
        method: "erpnextkta.erpnextkta.report.capacity_planning_report.capacity_planning_report.get_item_groups",
        args: {
          from_date: from_date,
          to_date: to_date
        },
        callback: function (r) {
          const field = report.get_filter("item_group");
          const options = r.message || [];
          field.df.options = ["", ...options];
          field.refresh();
        }
      });
    }

    // İlk yüklemede çalıştır
    updateItemGroupOptions();

    // from_date veya to_date değiştiğinde tetikle
    report.get_filter("from_date").df.on_change = updateItemGroupOptions;
    report.get_filter("to_date").df.on_change = updateItemGroupOptions;
  },

  filters: [
    {
      fieldname: "from_date",
      label: __("Başlangıç Tarihi"),
      fieldtype: "Date",
      default: frappe.datetime.add_days(frappe.datetime.get_today(), 0),
      reqd: 1
    },
    {
      fieldname: "to_date",
      label: __("Bitiş Tarihi"),
      fieldtype: "Date",
      default: frappe.datetime.add_days(frappe.datetime.get_today(), 90),
      reqd: 1
    },
    {
      fieldname: "item_group",
      label: __("Ürün Grubu"),
      fieldtype: "Select",
      options: []  // dinamik olarak dolacak
    }
  ]
};