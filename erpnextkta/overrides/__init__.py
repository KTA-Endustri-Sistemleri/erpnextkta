from erpnextkta.overrides.print_settings import set_print_templates_for_item_table


def apply():
    import erpnext.controllers.print_settings as ps

    if not hasattr(ps, "_original_set_print_templates_for_item_table"):
        ps._original_set_print_templates_for_item_table = (
            ps.set_print_templates_for_item_table
        )
        ps.set_print_templates_for_item_table = set_print_templates_for_item_table

    apply_bom_search_override()


def apply_bom_search_override():
    try:
        import erpnext.stock.report.bom_search.bom_search as bom_search
        import frappe

        if not hasattr(bom_search, "_original_execute"):
            bom_search._original_execute = bom_search.execute

            def custom_execute(filters=None):
                if not filters:
                    filters = {}

                # Create a dict copy of filters to avoid mutating the original (frappe.eval / execute passes dict-like object)
                copied_filters = frappe._dict(filters)
                only_default_boms = copied_filters.get("only_default_boms")
                
                if "only_default_boms" in copied_filters:
                    del copied_filters["only_default_boms"]

                columns, data = bom_search._original_execute(copied_filters)

                if only_default_boms:
                    # Find all active, default BOMs
                    default_boms = set(frappe.get_all("BOM", filters={"is_default": 1, "is_active": 1}, pluck="name"))

                    # Filter the rows, keeping only default BOMs or non-BOM rows (e.g. Product Bundles)
                    filtered_data = []
                    for row in data:
                        # Row can be list or tuple: (parent, parents[doctype]) -> (parent, 'BOM' or 'Product Bundle')
                        parent_name = row[0]
                        parent_type = row[1]
                        if parent_type == "BOM":
                            if parent_name in default_boms:
                                filtered_data.append(row)
                        else:
                            filtered_data.append(row)
                    data = filtered_data

                return columns, data

            bom_search.execute = custom_execute
    except Exception as e:
        import frappe
        frappe.log_error(f"Error applying BOM Search override: {e}", "KTA Override Error")
