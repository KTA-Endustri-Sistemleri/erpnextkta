// Copyright (c) 2026, Framras AS and contributors
// For license information, please see license.txt

frappe.ui.form.on("Makine Gunluk Bakim Formu", {
	refresh(frm) {
		// Load instruction content when form loads
		if (frm.doc.bakim_talimati && !frm.is_new()) {
			load_instruction_content(frm);
		}
	},

	bakim_talimati(frm) {
		// Load instruction content when instruction is changed
		if (frm.doc.bakim_talimati) {
			load_instruction_content(frm);
		}
	}
});

function load_instruction_content(frm) {
	frappe.call({
		method: 'frappe.client.get',
		args: {
			doctype: 'Bakim Talimati',
			name: frm.doc.bakim_talimati
		},
		callback: function(r) {
			if (r.message) {
				const instruction = r.message;

				// Build HTML content
				let html = `
					<div style="padding: 15px; background-color: #f9f9f9; border-radius: 5px;">
						<h3>${instruction.talimat_kodu} - ${instruction.talimat_adi}</h3>
				`;

				if (instruction.amac) {
					html += `<p><strong>AMAÇ:</strong> ${instruction.amac}</p>`;
				}

				if (instruction.kapsam) {
					html += `<p><strong>KAPSAM:</strong> ${instruction.kapsam}</p>`;
				}

				html += '<hr>';

				if (instruction.talimat_metni) {
					html += instruction.talimat_metni;
				}

				html += '</div>';

				// Set the HTML field
				frm.set_df_property('talimat_metni', 'options', html);
				frm.refresh_field('talimat_metni');
			}
		}
	});
}
