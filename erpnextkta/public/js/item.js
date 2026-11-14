frappe.ui.form.on('Item', {
    setup: function (frm) {
        // DocType schema'sında (JSON) bulunan link_filters ("is_group=0")
        // Frappe tarafından ezilmesin diye null yapıyoruz.
        if (frm.fields_dict.item_group && frm.fields_dict.item_group.df) {
            frm.fields_dict.item_group.df.link_filters = null;
        }

        frm.set_query("item_group", function () {
            return {
                filters: {} // Herhangi bir filtre olmadan tüm grupları getir
            };
        });
    },
    refresh: function (frm) {
        if (frm.fields_dict.item_group && frm.fields_dict.item_group.df) {
            frm.fields_dict.item_group.df.link_filters = null;
        }
        frm.set_query("item_group", function () {
            return {
                filters: {}
            };
        });
        update_sourcing_strategy_options(frm);
    }
});

frappe.ui.form.on('Item Supplier', {
    supplier_items_add: function (frm) {
        update_sourcing_strategy_options(frm);
    },
    supplier_items_remove: function (frm) {
        update_sourcing_strategy_options(frm);
    }
});

function update_sourcing_strategy_options(frm) {
    if (!frm.fields_dict.custom_sourcing_strategy) return;

    var suppliers = frm.doc.supplier_items || [];
    var count = suppliers.length;

    if (count <= 1) {
        // Tek tedarikçi: Sadece varsayılan ve kilitli
        frm.set_df_property("custom_sourcing_strategy", "options", [
            "Varsayılan Tedarikçi (%100)"
        ]);
        if (frm.doc.custom_sourcing_strategy !== "Varsayılan Tedarikçi (%100)") {
            frm.set_value("custom_sourcing_strategy", "Varsayılan Tedarikçi (%100)");
        }
        frm.set_df_property("custom_sourcing_strategy", "read_only", 1);
    } else {
        // 2 veya daha fazla tedarikçi: Varsayılan %100 kaldırılır, diğer 3 strateji sunulur
        frm.set_df_property("custom_sourcing_strategy", "read_only", 0);
        frm.set_df_property("custom_sourcing_strategy", "options", [
            "",
            "Kotalı Dağılım (% Paylaşım)",
            "En Düşük Fiyat Öncelikli",
            "Termin Süresi Öncelikli"
        ]);
        if (frm.doc.custom_sourcing_strategy === "Varsayılan Tedarikçi (%100)" || !frm.doc.custom_sourcing_strategy) {
            frm.set_value("custom_sourcing_strategy", "Kotalı Dağılım (% Paylaşım)");
        }
    }
}