(() => {
const MR_WEEK_FIELD = /^\d{4}_w\d{2}$/;
const MR_URGENT_WEEKS = 4;
const MR_ACTION_VIEWS = ["Önerilen Sipariş", "Net İhtiyaç"];

frappe.query_reports["Material Requirement"] = {
	initial_depth: 0,

	onload: function (report) {
		if (window.kta && kta.report_utils && kta.report_utils.sync_mrp_date_filters) {
			kta.report_utils.sync_mrp_date_filters(report);
		}
		mr_attach_click_listener();
	},

	filters: [
		{
			fieldname: "to_date",
			label: __("Bitiş Tarihi"),
			fieldtype: "Date",
			default: (window.kta && kta.report_utils && kta.report_utils.get_default_to_date)
				? kta.report_utils.get_default_to_date()
				: frappe.datetime.add_days(frappe.datetime.get_today(), 90),
			reqd: 1,
		},
		{
			fieldname: "weekly_view",
			label: __("Haftalık Gösterim"),
			fieldtype: "Select",
			options: ["Önerilen Sipariş", "Net İhtiyaç", "Brüt İhtiyaç", "Projeksiyon Bakiye"],
			default: "Önerilen Sipariş",
		},
		{
			fieldname: "group_by",
			label: __("Gruplama Şekli"),
			fieldtype: "Select",
			options: ["Bitmiş Ürün + Hammadde", "Sadece Hammadde"],
			default: "Bitmiş Ürün + Hammadde",
		},
		{
			fieldname: "only_shortages",
			label: __("Sadece Eksik Olanlar"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "supplier",
			label: __("Tedarikçi"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "hammadde",
			label: __("Hammadde"),
			fieldtype: "Link",
			options: "Item",
		},
		{
			fieldname: "custom_musteri_grubu",
			label: __("Müşteri Grubu"),
			fieldtype: "Link",
			options: "KTA Customer Group",
		},
		{
			fieldname: "item_group",
			label: __("Ürün Grubu"),
			fieldtype: "Link",
			options: "Item Group",
			get_query: function () {
				const musteri_grubu = frappe.query_report.get_filter_value("custom_musteri_grubu");
				return {
					query: "erpnextkta.kta_mrp.report_utils.get_item_group_query",
					filters: { custom_musteri_grubu: musteri_grubu },
				};
			},
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		const formatted = mr_base_format(value, row, column, data, default_formatter);
		if (!data) {
			return formatted;
		}

		const col_name = (column && (column.fieldname || column.id)) || "";

		if (data.is_po_row) {
			if (col_name === "hammadde") {
				const item_code = frappe.utils.escape_html(data.parent_item || "");
				const label = __("Açık PO Girişleri");
				return `<a href="/app/purchase-order?item_code=${encodeURIComponent(item_code)}&docstatus=1" class="mr-po-link" data-item="${item_code}" style="color: #2563eb; font-weight: 600; text-decoration: none;" title="${__("Açık Siparişleri Gör")}"><i class="fa fa-truck mr-1"></i> ${label}</a>`;
			}
			if (col_name === "po_teslimat") {
				return `<span style="color: #2563eb; font-weight: 600;">${formatted}</span>`;
			}
			if (MR_WEEK_FIELD.test(col_name)) {
				if (value > 0) {
					const item_code = frappe.utils.escape_html(data.parent_item || "");
					return `<span class="mr-cell-action" data-item="${item_code}" data-week="${col_name}" style="color: #2563eb; cursor: pointer; font-weight: 600; padding: 2px 5px; border-radius: 3px;" title="${__("Netleştirme Detayını Gör")}">+${formatted}</span>`;
				}
				return `<span style="color: var(--text-muted); opacity: 0.5;">-</span>`;
			}
			return formatted;
		}

		if (data.indent) {
			return formatted;
		}

		if (col_name === "ilk_eksik_hafta" && value) {
			return mr_shortage_badge(formatted, data.ilk_eksik_sira);
		}

		if (MR_WEEK_FIELD.test(col_name)) {
			if (!value || value === 0) {
				return `<span style="color: var(--text-muted); opacity: 0.35;">-</span>`;
			}

			let actionStyle = "";
			if (mr_is_action_view()) {
				actionStyle = "color: var(--orange-600);";
			}

			const item_code = frappe.utils.escape_html(data.hammadde);

			return `<span class="mr-cell-action" data-item="${item_code}" data-week="${col_name}" style="${actionStyle} cursor: pointer; font-weight: 600; padding: 2px 5px; border-radius: 3px;" title="${__("Netleştirme Detayını Gör")}">${formatted}</span>`;
		}
		return formatted;
	},

	after_datatable_render: function () {
		mr_attach_click_listener();
	},
};

function mr_base_format(value, row, column, data, default_formatter) {
	if (window.kta && kta.report_utils && kta.report_utils.std_formatter) {
		return kta.report_utils.std_formatter(value, row, column, data, default_formatter);
	}
	return default_formatter(value, row, column, data);
}

function mr_is_action_view() {
	return MR_ACTION_VIEWS.includes(frappe.query_report.get_filter_value("weekly_view"));
}

function mr_format_qty(val) {
	if (val === null || val === undefined) return "0";
	return Number(val).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}

function mr_format_uom(uom) {
	if (!uom) return "";
	if (uom === "Nos") {
		return __("Adet");
	}
	return __(uom);
}

function mr_attach_click_listener() {
	if (!document.getElementById("mr-netting-dialog-style")) {
		const style = document.createElement("style");
		style.id = "mr-netting-dialog-style";
		style.innerHTML = `
			.mr-cell-action {
				cursor: pointer;
				transition: background-color 0.12s ease;
			}
			.mr-cell-action:hover {
				background-color: rgba(37, 99, 235, 0.12) !important;
				text-decoration: underline;
			}
		`;
		document.head.appendChild(style);
	}

	$(document)
		.off("click.mrp_cell")
		.on("click.mrp_cell", function (e) {
			let $action = $(e.target).closest(".mr-cell-action");
			if (!$action.length) {
				$action = $(e.target).closest(".dt-cell").find(".mr-cell-action");
			}
			if ($action.length) {
				const item_code = $action.attr("data-item");
				const week = $action.attr("data-week");
				if (item_code && week) {
					e.preventDefault();
					e.stopPropagation();
					mr_open_netting_dialog(item_code, week);
				}
			}
		});

	$(document)
		.off("click.mr_po_link")
		.on("click.mr_po_link", ".mr-po-link", function (e) {
			e.preventDefault();
			e.stopPropagation();
			const item = $(this).attr("data-item");
			if (item) {
				frappe.route_options = {
					item_code: item,
					docstatus: 1,
					status: ["not in", ["Closed", "Completed", "Delivered", "On Hold"]],
				};
				frappe.set_route("List", "Purchase Order", "List");
			}
		});
}

function mr_open_netting_dialog(item_code, week) {
	const filters = frappe.query_report.get_values() || {};
	const dialog = new frappe.ui.Dialog({
		title: `${item_code} — ${__("Haftalık Netleştirme Detayı")}`,
		size: "large",
		fields: [
			{
				fieldname: "details",
				fieldtype: "HTML",
			},
		],
		primary_action_label: __("Kapat"),
		primary_action: function () {
			dialog.hide();
		},
	});

	// Check if client-side row data is available for instant rendering
	const reportData = (frappe.query_report && frappe.query_report.data) || [];
	const row = reportData.find(d => !d.indent && d.hammadde === item_code);

	if (row && row._week_details && row._week_details[week]) {
		let balance_before = row.serbest_stok || 0;
		const weekColumns = (frappe.query_report.columns || [])
			.map(c => c.fieldname || c.id)
			.filter(f => MR_WEEK_FIELD.test(f));
		const wIdx = weekColumns.indexOf(week);
		if (wIdx > 0) {
			const prevWeek = weekColumns[wIdx - 1];
			if (row._week_details[prevWeek]) {
				balance_before = row._week_details[prevWeek].projected;
			}
		}

		const wd = row._week_details[week];
		const weekCol = (frappe.query_report.columns || []).find(c => (c.fieldname || c.id) === week);
		const initialData = {
			item_code: item_code,
			item_name: row.urun_aciklamasi,
			uom: row.uom,
			supplier: row.varsayilan_tedarikci,
			moq: row.moq || 0,
			pack: row.pack || 1,
			lead_time: row.lead_time || 0,
			week: week,
			week_label: weekCol ? weekCol.label : week,
			balance_before: balance_before,
			gross: wd.gross,
			receipts: wd.po,
			net: wd.net,
			order: wd.order,
			projected: wd.projected,
			include_po: filters.include_po !== undefined ? filters.include_po : 1,
			pos: null,
			demands: null,
		};

		dialog.fields_dict.details.$wrapper.html(mr_render_dialog_html(initialData));
	} else {
		dialog.fields_dict.details.$wrapper.html(`
			<div class="text-center py-5">
				<div class="spinner-border text-primary" role="status"></div>
				<div class="text-muted mt-2">${__("Hesaplama detayları yükleniyor...")}</div>
			</div>
		`);
	}

	dialog.show();

	frappe.call({
		method: "erpnextkta.kta_mrp.report.material_requirement.material_requirement.get_week_netting_dialog",
		args: {
			item_code: item_code,
			week: week,
			from_date: filters.from_date,
			to_date: filters.to_date,
			include_po: filters.include_po !== undefined ? filters.include_po : 1,
		},
		callback: function (r) {
			if (r.message && !r.message.error) {
				dialog.fields_dict.details.$wrapper.html(mr_render_dialog_html(r.message));
			} else if (!row) {
				dialog.fields_dict.details.$wrapper.html(`
					<div class="alert alert-danger">
						${r.message ? r.message.error : __("Detaylar alınamadı.")}
					</div>
				`);
			}
		},
	});
}

function mr_render_dialog_html(d) {
	const formatQty = (v) => Number(v || 0).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
	const uom = mr_format_uom(d.uom);

	// PO Table HTML
	let posHtml = "";
	if (d.pos === null) {
		posHtml = `
			<div class="mt-4 p-3 bg-light rounded text-center text-muted small">
				<span class="spinner-border spinner-border-sm mr-2 text-primary" role="status"></span>
				${__("Açık PO ve Mamul detayları yükleniyor...")}
			</div>
		`;
	} else if (d.pos && d.pos.length > 0) {
		const poRows = d.pos.map(p => `
			<tr>
				<td><a href="/app/purchase-order/${encodeURIComponent(p.po_name)}" target="_blank" style="font-weight:600;">${p.po_name}</a></td>
				<td>${frappe.utils.escape_html(__(p.supplier) || "-")}</td>
				<td>${p.schedule_date}</td>
				<td class="text-right" style="color: #2563eb; font-weight:600;">+${formatQty(p.pending)} ${uom}</td>
			</tr>
		`).join("");
		posHtml = `
			<div class="mt-4">
				<h6 class="text-muted text-uppercase mb-2 font-weight-bold" style="font-size: 11px;">
					<i class="fa fa-truck mr-1 text-primary"></i> ${__("Bu Haftaya Düşen Açık Satınalma Siparişleri (PO)")}
				</h6>
				<table class="table table-bordered table-sm">
					<thead class="bg-light">
						<tr>
							<th>${__("Sipariş No")}</th>
							<th>${__("Tedarikçi")}</th>
							<th>${__("Termin Tarihi")}</th>
							<th class="text-right">${__("Bekleyen Miktar")}</th>
						</tr>
					</thead>
					<tbody>${poRows}</tbody>
				</table>
			</div>
		`;
	} else if (d.include_po) {
		posHtml = `<div class="text-muted small mt-2"><i>${__("Bu hafta için beklenen açık satınalma siparişi (PO) bulunmamaktadır.")}</i></div>`;
	} else {
		posHtml = `<div class="alert alert-warning small mt-2 py-1">${__("Açık PO filtresi kapalı olduğu için siparişler hesaba katılmamıştır.")}</div>`;
	}

	// Demand Table HTML
	let demandHtml = "";
	if (d.demands && d.demands.length > 0) {
		const demandRows = d.demands.map(dm => `
			<tr>
				<td><a href="/app/item/${encodeURIComponent(dm.finished_item)}" target="_blank" style="font-weight:600;">${dm.finished_item}</a></td>
				<td>${frappe.utils.escape_html(__(dm.item_name) || "")}</td>
				<td><a href="/app/bom/${encodeURIComponent(dm.bom)}" target="_blank">${dm.bom}</a></td>
				<td>${frappe.utils.escape_html(__(dm.customer_group) || "-")}</td>
				<td class="text-right" style="color: #dc2626; font-weight:600;">-${formatQty(dm.qty)} ${uom}</td>
			</tr>
		`).join("");
		demandHtml = `
			<div class="mt-4">
				<h6 class="text-muted text-uppercase mb-2 font-weight-bold" style="font-size: 11px;">
					<i class="fa fa-cogs mr-1 text-danger"></i> ${__("Bu Haftadaki Brüt İhtiyaç Kaynakları (Mamul Talepleri)")}
				</h6>
				<table class="table table-bordered table-sm">
					<thead class="bg-light">
						<tr>
							<th>${__("Bitmiş Ürün")}</th>
							<th>${__("Ürün Açıklaması")}</th>
							<th>${__("BOM")}</th>
							<th>${__("Müşteri Grubu")}</th>
							<th class="text-right">${__("Gereken Miktar")}</th>
						</tr>
					</thead>
					<tbody>${demandRows}</tbody>
				</table>
			</div>
		`;
	}

	return `
		<div style="font-family: inherit;">
			<!-- Header Info Bar -->
			<div class="d-flex flex-wrap justify-content-between align-items-center p-3 mb-3 bg-light rounded" style="border: 1px solid #e2e8f0;">
				<div>
					<h5 class="mb-1" style="font-weight: 700;">${d.item_code} <span class="text-muted font-weight-normal" style="font-size: 14px;">(${d.item_name})</span></h5>
					<div class="small text-muted mt-1">
						<span class="mr-3"><b>${__("Tedarikçi")}:</b> ${frappe.utils.escape_html(__(d.supplier) || "-")}</span>
						<span class="mr-3"><b>${__("Birim")}:</b> ${uom}</span>
						<span class="mr-3"><b>${__("Temin Süresi")}:</b> ${d.lead_time || 0} ${__("Gün")}</span>
						<span class="mr-3"><b>${__("Min. Sipariş Miktarı (MOQ)")}:</b> ${formatQty(d.moq)}</span>
						<span><b>${__("Paketleme Katı")}:</b> ${formatQty(d.pack)}</span>
					</div>
				</div>
				<div class="text-right">
					<span class="badge badge-primary px-3 py-2" style="font-size: 13px; font-weight:600;">📅 ${d.week_label}</span>
				</div>
			</div>

			<!-- Core MRP Calculation Table -->
			<div class="card p-3 mb-3" style="border: 1px solid #e2e8f0; background: #fafafa;">
				<h6 class="text-uppercase text-muted font-weight-bold mb-3" style="font-size: 11px;">${__("Netleştirme Hesabı")}</h6>
				<table class="table table-sm table-borderless mb-0">
					<tbody>
						<tr style="border-bottom: 1px solid #e2e8f0;">
							<td style="padding: 8px 4px;"><b>1. ${__("Önceki Haftadan Devreden Bakiye")}</b></td>
							<td class="text-right font-weight-bold ${d.balance_before < 0 ? 'text-danger' : 'text-success'}" style="padding: 8px 4px;">
								${formatQty(d.balance_before)} ${uom}
								${d.balance_before < 0 ? `<small class="badge badge-danger ml-1">${__("Eksik")}</small>` : ''}
							</td>
						</tr>
						<tr style="border-bottom: 1px solid #e2e8f0;">
							<td style="padding: 8px 4px;"><b>2. ${__("Gelen Açık Satınalma Siparişi (PO)")} (+)</b></td>
							<td class="text-right font-weight-bold text-primary" style="padding: 8px 4px;">+${formatQty(d.receipts)} ${uom}</td>
						</tr>
						<tr style="border-bottom: 1px solid #e2e8f0;">
							<td style="padding: 8px 4px;"><b>3. ${__("Brüt Üretim İhtiyacı")} (-)</b></td>
							<td class="text-right font-weight-bold text-danger" style="padding: 8px 4px;">-${formatQty(d.gross)} ${uom}</td>
						</tr>
						<tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1;">
							<td style="font-size: 14px; padding: 10px 4px;"><b>4. ${__("Net Eksik / İhtiyaç")}</b></td>
							<td class="text-right font-weight-bold text-danger" style="font-size: 15px; padding: 10px 4px;">${formatQty(d.net)} ${uom}</td>
						</tr>
						<tr style="background: #e0f2fe; border-bottom: 1px solid #bae6fd;">
							<td style="font-size: 14px; color: #0369a1; padding: 10px 4px;">
								<b>5. ${__("Önerilen Sipariş (MOQ & Paket Katı Uygulanmış)")}</b>
								<div class="small text-muted font-weight-normal">${__("Min. Sipariş Miktarı (MOQ)")}: ${formatQty(d.moq)} | ${__("Paketleme Katı")}: ${formatQty(d.pack)}</div>
							</td>
							<td class="text-right font-weight-bold" style="font-size: 16px; color: #0284c7; padding: 10px 4px;">
								${formatQty(d.order)} ${uom}
							</td>
						</tr>
						<tr style="border-top: 1px solid #cbd5e1; background: #f8fafc;">
							<td class="text-muted" style="padding: 8px 4px;"><b>6. ${__("Dönem Sonu Projeksiyon Bakiye")}</b></td>
							<td class="text-right font-weight-bold ${d.projected < 0 ? 'text-danger' : 'text-success'}" style="padding: 8px 4px;">${formatQty(d.projected)} ${uom}</td>
						</tr>
					</tbody>
				</table>
			</div>

			<!-- PO & Demand Details -->
			${posHtml}
			${demandHtml}
		</div>
	`;
}

function mr_shortage_badge(formatted, week_index) {
	const color = week_index < MR_URGENT_WEEKS ? "red" : "orange";
	return `<span class="indicator-pill ${color}">${formatted}</span>`;
}
})();