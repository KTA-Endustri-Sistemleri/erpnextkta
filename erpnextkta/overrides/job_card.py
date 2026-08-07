import frappe
from frappe import _
from frappe.utils import flt
from erpnext.manufacturing.doctype.job_card.job_card import JobCard


class KTAJobCard(JobCard):
    def get_overlap_for(self, args, open_job_cards=None):
        if frappe.db.get_single_value("Manufacturing Settings", "disable_capacity_planning"):
            return {}
        return super().get_overlap_for(args, open_job_cards)

    def validate_sequence_id(self):
        if self.flags.get("kta_sync_mode"):
            return
        return super().validate_sequence_id()

    def before_validate(self):
        if hasattr(super(), "before_validate"):
            super().before_validate()
            
        if not self.get("items"):
            self.get_required_items()
            
        # Ensure existing items also have transferred_qty = required_qty to fix UI
        if self.get("work_order"):
            wo = frappe.get_cached_doc("Work Order", self.work_order)
            if wo and wo.skip_transfer:
                for row in self.get("items", []):
                    row.transferred_qty = row.required_qty

    @frappe.whitelist()
    def get_required_items(self):
        """Load operation-specific raw materials even when skip_transfer is enabled."""
        if not self.get("work_order"):
            return

        doc = frappe.get_doc("Work Order", self.get("work_order"))

        # Standard behaviour for non-skip-transfer cases
        if not doc.skip_transfer:
            return super().get_required_items()

        # ── KTA: skip_transfer=True ise de operasyona ait malzemeleri yükle ──
        for d in doc.required_items:
            if not d.operation:
                continue

            if self.get("operation") == d.operation:
                self.append(
                    "items",
                    {
                        "item_code": d.item_code,
                        "source_warehouse": d.source_warehouse,
                        "uom": frappe.db.get_value("Item", d.item_code, "stock_uom"),
                        "item_name": d.item_name,
                        "description": d.description,
                        "required_qty": (d.required_qty * flt(self.for_quantity)) / doc.qty,
                        "transferred_qty": (d.required_qty * flt(self.for_quantity)) / doc.qty,
                        "rate": d.rate,
                        "amount": d.amount,
                    },
                )

    def on_submit(self):
        super().on_submit()
        self._create_consumption_entry_if_needed()

    def on_cancel(self):
        self._cancel_consumption_entries()
        super().on_cancel()

    def validate_transfer_qty(self):
        """Skip transfer validation for skip_transfer Work Orders."""
        if not self.work_order:
            return super().validate_transfer_qty()

        wo_skip = frappe.get_cached_value("Work Order", self.work_order, "skip_transfer")
        if wo_skip:
            return

        return super().validate_transfer_qty()

    # ──────────────────────────────────────────────────────────────
    #  Operasyon bazında tüketim: Material Consumption Stock Entry
    # ──────────────────────────────────────────────────────────────

    def _create_consumption_entry_if_needed(self):
        """Create a Material Consumption for Manufacture Stock Entry
        for the raw materials belonging to this operation."""
        if not self.work_order:
            return

        wo = frappe.get_doc("Work Order", self.work_order)
        if not wo.skip_transfer:
            return

        items_to_consume = self._get_operation_raw_materials(wo)
        if not items_to_consume:
            return

        se = frappe.new_doc("Stock Entry")
        se.purpose = "Material Consumption for Manufacture"
        se.stock_entry_type = "Material Consumption for Manufacture"
        se.work_order = self.work_order
        se.company = wo.company
        se.from_bom = 1
        se.bom_no = wo.bom_no
        se.use_multi_level_bom = wo.use_multi_level_bom
        se.fg_completed_qty = self.total_completed_qty or self.for_quantity
        se.job_card = self.name

        for d in items_to_consume:
            has_batch = frappe.db.get_value("Item", d.item_code, "has_batch_no")
            if not has_batch:
                se.append("items", {
                    "item_code": d.item_code,
                    "item_name": d.item_name,
                    "description": d.description,
                    "qty": d.qty,
                    "uom": d.uom or d.stock_uom,
                    "stock_uom": d.stock_uom,
                    "conversion_factor": 1,
                    "s_warehouse": d.source_warehouse,
                    "t_warehouse": "",
                })
            else:
                batch_names = frappe.get_all("Batch", filters={"item": d.item_code, "disabled": 0}, pluck="name")
                batches = []
                if batch_names:
                    query = """
                        SELECT sb.batch_no, SUM(sb.qty) as qty 
                        FROM `tabStock Ledger Entry` sle 
                        JOIN `tabSerial and Batch Entry` sb ON sle.serial_and_batch_bundle = sb.parent 
                        WHERE sle.item_code = %s AND sle.warehouse = %s AND sle.is_cancelled = 0 AND sb.batch_no IN %s
                        GROUP BY sb.batch_no 
                        HAVING qty > 0
                        ORDER BY MIN(sb.creation) ASC
                    """
                    batches = frappe.db.sql(query, (d.item_code, d.source_warehouse, tuple(batch_names)), as_dict=True)

                remaining_qty = flt(d.qty)
                for batch in batches:
                    if remaining_qty <= 0:
                        break
                    
                    consume_qty = min(remaining_qty, flt(batch.qty))
                    se.append("items", {
                        "item_code": d.item_code,
                        "item_name": d.item_name,
                        "description": d.description,
                        "qty": consume_qty,
                        "uom": d.uom or d.stock_uom,
                        "stock_uom": d.stock_uom,
                        "conversion_factor": 1,
                        "s_warehouse": d.source_warehouse,
                        "t_warehouse": "",
                        "batch_no": batch.batch_no,
                        "use_serial_batch_fields": 1
                    })
                    remaining_qty -= consume_qty
                    
                if remaining_qty > 0:
                    frappe.throw(
                        _("Insufficient stock for batch item {0} in warehouse {1}. Required: {2}, Missing: {3}").format(
                            frappe.bold(d.item_code),
                            frappe.bold(d.source_warehouse),
                            d.qty,
                            remaining_qty
                        )
                    )

        if not se.items:
            return

        se.flags.ignore_validate = False
        se.set_stock_entry_type()
        se.calculate_rate_and_amount(raise_error_if_no_rate=False)
        se.insert(ignore_permissions=True)
        se.submit()

        frappe.msgprint(
            _("Material Consumption {0} created for operation {1}").format(
                frappe.utils.get_link_to_form("Stock Entry", se.name),
                frappe.bold(self.operation),
            ),
            alert=True,
            indicator="green",
        )

    def _get_operation_raw_materials(self, wo):
        """Return raw materials assigned to this operation, scaled to job card qty."""
        items = []
        for d in wo.required_items:
            if d.operation != self.operation:
                continue

            item_qty = flt(
                (d.required_qty / wo.qty) * flt(self.total_completed_qty or self.for_quantity),
                frappe.get_precision("Stock Entry Detail", "qty"),
            )

            if item_qty <= 0:
                continue

            items.append(
                frappe._dict(
                    {
                        "item_code": d.item_code,
                        "item_name": d.item_name,
                        "description": d.description,
                        "qty": item_qty,
                        "required_qty": item_qty,
                        "stock_uom": d.stock_uom,
                        "uom": d.stock_uom,
                        "source_warehouse": d.source_warehouse,
                    }
                )
            )
        return items

    def _cancel_consumption_entries(self):
        """Cancel all Material Consumption Stock Entries linked to this Job Card."""
        if not self.work_order:
            return

        entries = frappe.get_all(
            "Stock Entry",
            filters={
                "job_card": self.name,
                "work_order": self.work_order,
                "purpose": "Material Consumption for Manufacture",
                "docstatus": 1,
            },
            pluck="name",
        )

        for se_name in entries:
            se = frappe.get_doc("Stock Entry", se_name)
            se.cancel()
            frappe.msgprint(
                _("Material Consumption {0} cancelled").format(
                    frappe.utils.get_link_to_form("Stock Entry", se_name)
                ),
                alert=True,
                indicator="orange",
            )
