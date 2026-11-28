frappe.query_reports["KTA WIP Valuation Report"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "as_of_date",
			label: __("As Of Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "work_order",
			label: __("Work Order"),
			fieldtype: "Link",
			options: "Work Order",
			get_query: function () {
				const company = frappe.query_report.get_filter_value("company");
				return company ? { filters: { company: company } } : {};
			},
		},
		{
			fieldname: "wo_status",
			label: __("Work Order Status"),
			fieldtype: "Select",
			options: [
				"",
				"In Process",
				"Not Started",
				"Completed",
				"Stopped",
				"Closed",
				"Cancelled",
			],
		},
		{
			fieldname: "only_open_wip",
			label: __("Only Open WIP"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "show_consumption_details",
			label: __("Show Operation & Material Breakdown"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "include_classic_manufacture",
			label: __("Include Classic Manufacture"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "view_mode",
			label: __("View Mode"),
			fieldtype: "Select",
			options: "Tree View\nFlat 2D (Pivot)",
			default: "Tree View",
		},
	],

	tree: true,
	name_field: "tree_node",
	parent_field: "parent_node",
	initial_depth: 0,

	onload: function (report) {
		report.page.add_inner_button(__("Export 2D Excel"), function () {
			const filters = report.get_values() || {};
			open_url_post(
				"/api/method/erpnextkta.kta_shopfloor.report.kta_wip_valuation_report.kta_wip_valuation_report.export_flat_2d_excel",
				{ filters: JSON.stringify(filters) }
			);
		});
	},

	formatter: function (value, row, column, data, default_formatter) {
		if (value === null || value === undefined || value === "") {
			return "";
		}

		if (data && data.row_type === "total") {
			value = default_formatter(value, row, column, data);
			return value !== null && value !== undefined && value !== ""
				? `<strong>${value}</strong>`
				: "";
		}

		if (data && data.row_type && column.fieldname === "work_order") {
			if (data.indent === 0) {
				value = `<strong>${frappe.utils.get_form_link(
					"Work Order",
					data.work_order_ref || data.work_order,
					true
				)}</strong>`;
			} else if (data.indent === 1) {
				value = `<strong>${frappe.utils.escape_html(data.operation || value)}</strong>`;
			} else if (data.indent === 2) {
				value = frappe.utils.get_form_link(
					"Item",
					data.material_item || data.work_order,
					true
				);
			}
		} else {
			value = default_formatter(value, row, column, data);
		}

		if (!data) {
			return value;
		}

		const terminalStatuses = new Set([
			"Stopped",
			"Closed",
			"Completed",
			"Cancelled",
		]);

		if (data.row_type) {
			const isTerminalOpenWip =
				data.indent === 0 &&
				terminalStatuses.has(data.wo_status) &&
				Math.abs(flt(data.wip_balance)) > 0.01;

			if (column.fieldname === "wo_status" && data.wo_status) {
				const translatedStatus = __(data.wo_status);
				if (isTerminalOpenWip) {
					return `<span class="indicator-pill red">${frappe.utils.escape_html(
						translatedStatus
					)}</span>`;
				}
				return frappe.utils.escape_html(translatedStatus);
			}

			if (isTerminalOpenWip) {
				if (column.fieldname === "wip_balance") {
					return `<span style="color: var(--red-600); font-weight: 600;">${value}</span>`;
				}
				return `<span style="background-color: var(--bg-orange); display: inline-block; width: 100%;">${value}</span>`;
			}

			return value;
		}

		if (data.wo_wip_balance !== undefined) {
			const isFlatTerminalOpenWip =
				terminalStatuses.has(data.wo_status) &&
				Math.abs(flt(data.wo_wip_balance)) > 0.01;

			if (column.fieldname === "work_order" && data.work_order) {
				value = frappe.utils.get_form_link("Work Order", data.work_order, true);
			} else if (column.fieldname === "wo_status" && data.wo_status) {
				const translatedStatus = __(data.wo_status);
				if (isFlatTerminalOpenWip) {
					return `<span class="indicator-pill red">${frappe.utils.escape_html(
						translatedStatus
					)}</span>`;
				}
				return frappe.utils.escape_html(translatedStatus);
			} else if (
				column.fieldname === "consumption_source" &&
				data.consumption_source
			) {
				return frappe.utils.escape_html(__(data.consumption_source));
			}

			if (isFlatTerminalOpenWip) {
				if (column.fieldname === "wo_wip_balance") {
					return `<span style="color: var(--red-600); font-weight: 600;">${value}</span>`;
				}
				return `<span style="background-color: var(--bg-orange); display: inline-block; width: 100%;">${value}</span>`;
			}
		}

		return value;
	},
};
