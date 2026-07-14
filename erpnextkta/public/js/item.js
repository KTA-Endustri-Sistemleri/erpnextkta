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
    }
});