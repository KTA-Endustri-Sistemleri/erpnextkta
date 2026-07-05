frappe.query_reports["Is Emri Hammadde Tuketim Raporu"] = {
	filters: [
		{
			fieldname: "work_order",
			label: __("İş Emri"),
			fieldtype: "Link",
			options: "Work Order",
			reqd: 0,
		},
		{
			fieldname: "operator",
			label: __("Operatör"),
			fieldtype: "Link",
			options: "Employee",
			reqd: 0,
		},
		{
			fieldname: "item_code",
			label: __("Hammadde"),
			fieldtype: "Link",
			options: "Item",
			reqd: 0,
		},
	],
	formatter: function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.is_spacer && column.fieldtype === "Float") {
			return "";
		}
		return value;
	}
};
