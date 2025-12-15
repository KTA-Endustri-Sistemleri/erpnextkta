from erpnextkta.overrides.print_settings import set_print_templates_for_item_table


def apply():
    import erpnext.controllers.print_settings as ps

    if not hasattr(ps, "_original_set_print_templates_for_item_table"):
        ps._original_set_print_templates_for_item_table = (
            ps.set_print_templates_for_item_table
        )
        ps.set_print_templates_for_item_table = set_print_templates_for_item_table
