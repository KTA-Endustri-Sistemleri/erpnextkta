// Copyright (c) 2026, Framras AS and contributors
// For license information, please see license.txt

const AMBALAJ_METHOD = "erpnextkta.kta_stock.doctype.iade_edilebilir_ambalaj_fisi.iade_edilebilir_ambalaj_fisi";

frappe.ui.form.on("Iade Edilebilir Ambalaj Fisi", {
	setup(frm) {
		frm.set_query("purchase_receipt", () => {
			const filters = { docstatus: 1 }; // Sadece onaylanmış irsaliyeler
			if (frm.doc.supplier) filters.supplier = frm.doc.supplier;
			return { filters };
		});
	},

	refresh(frm) {
		frm.trigger("type");
		frm.trigger("show_supplier_balance");
	},

	type(frm) {
		// Giriş yapılıyorsa Mal Alım İrsaliyesi seçmek zorunlu olsun
		frm.toggle_reqd("purchase_receipt", frm.doc.type === "Giriş");
	},

	supplier(frm) {
		frm.trigger("show_supplier_balance");
	},

	show_supplier_balance(frm) {
		frm.dashboard.clear_headline();
		if (!frm.doc.supplier) return;
		frappe.call({
			method: `${AMBALAJ_METHOD}.get_supplier_balance`,
			args: { supplier: frm.doc.supplier },
			callback: (r) => {
				frm.dashboard.set_headline(
					__("Tedarikçi Ambalaj Bakiyesi: {0}", [r.message || 0]),
					(r.message || 0) > 0 ? "blue" : "gray"
				);
			},
		});
	},

	purchase_receipt(frm) {
		if (!frm.doc.purchase_receipt) {
			frm.set_value("calculated_qty", 0);
			return;
		}
		if (frm.doc.type !== "Giriş") frm.set_value("type", "Giriş");

		frappe.db.get_value("Purchase Receipt", frm.doc.purchase_receipt, "supplier").then((r) => {
			const supplier = r.message && r.message.supplier;
			if (supplier && frm.doc.supplier !== supplier) frm.set_value("supplier", supplier);
		});

		frappe.call({
			method: `${AMBALAJ_METHOD}.calculate_packaging_qty`,
			args: { purchase_receipt: frm.doc.purchase_receipt },
			callback: (r) => show_calculation(frm, r.message),
		});
	},
});

function show_calculation(frm, result) {
	const total = (result && result.total) || 0;
	frm.set_value("calculated_qty", total);
	if (!total) return;

	const rows = result.details
		.map((d) => `<li>${d.item_code}: ${d.qty} / ${d.split_qty} = <b>${d.count}</b></li>`)
		.join("");
	frappe.msgprint({
		title: __("Tahmini Ambalaj Sayısı"),
		message: `<p>${__("Seçilen irsaliyedeki kalemlere göre hesaplanan ambalaj sayısı: {0}", [total])}</p>
			<ul>${rows}</ul>
			<p>${__("Lütfen Adet alanına bu değeri veya fiziki sayım sonucunuzu girin.")}</p>`,
		indicator: "blue",
	});
}
