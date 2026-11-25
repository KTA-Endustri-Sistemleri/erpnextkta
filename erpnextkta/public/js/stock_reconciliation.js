// erpnextkta/public/js/stock_reconciliation.js

frappe.ui.form.on("Stock Reconciliation", {
  // We override only the `get_items` event used by the core refresh handler.
  // Core refresh does: frm.add_custom_button(__("Depodan Ürünleri Getir"), () => frm.events.get_items(frm))
  // Since events are merged, this definition will replace the core one if our app is loaded after erpnext.
  get_items: function (frm) {
    let fields = [
      {
        label: "Warehouse",
        fieldname: "warehouse",
        fieldtype: "Link",
        options: "Warehouse",
        reqd: 1,
        get_query: function () {
          return {
            filters: {
              company: frm.doc.company,
            },
          };
        },
      },
      {
        label: __("Ürün Kodu"),
        fieldname: "item_code",
        fieldtype: "Link",
        options: "Item",
      },
      {
        label: __("Boş Stokları Yoksay"),
        fieldname: "ignore_empty_stock",
        fieldtype: "Check",
      },
    ];

    frappe.prompt(
      fields,
      function (data) {
        frappe.call({
          // 🔴 IMPORTANT: use our custom server method instead of the core one
          method:
            "erpnextkta.kta_stock.services.stock_reconciliation_service.get_items_static",
          args: {
            warehouse: data.warehouse,
            posting_date: frm.doc.posting_date,
            posting_time: frm.doc.posting_time,
            company: frm.doc.company,
            item_code: data.item_code,
            ignore_empty_stock: data.ignore_empty_stock,
          },
          callback: function (r) {
            if (r.exc || !r.message || !r.message.length) return;

            frm.clear_table("items");

            r.message.forEach((row) => {
              let item = frm.add_child("items");
              $.extend(item, row);

              item.qty = item.qty || 0;
              item.valuation_rate = item.valuation_rate || 0;
              item.use_serial_batch_fields = cint(
                frappe.user_defaults?.use_serial_batch_fields
              );
            });
            frm.refresh_field("items");
          },
        });
      },
      __("Ürünleri Getir"),
      __("Güncelle")
    );
  },
  refresh(frm) {
    if (!frm.is_new() && frm.doc.docstatus < 2) {
      frm.add_custom_button(__("Sayım ve Etiket Merkezinde Aç"), () => {
        frappe.route_options = { doc: frm.doc.name, tab: "operations" };
        frappe.set_route("stock-reco-dashboard");
      });
    }
  },
});
