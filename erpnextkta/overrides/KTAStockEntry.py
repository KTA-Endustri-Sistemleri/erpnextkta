import inspect

import frappe
from erpnext.stock.doctype.stock_entry.stock_entry import (
    OperationsNotCompleteError,
    StockEntry,
)
from frappe import _
from frappe.utils import cint, flt

from erpnextkta.kta_stock.batch_manager import BatchSplitManager
from erpnextkta.kta_stock.services.relabeling_service import (
    delete_labels_with_print_logs,
    get_batch_ledger_balances,
    sync_batch_label_to_ledger_balance,
    upsert_box_label,
)
from erpnextkta.overrides.company_wip_validation import (
    get_validated_wip_consumption_account,
)


class KTAStockEntry(StockEntry):
    def get_work_order_raw_materials(self, qty):
        """Override to deduct quantities already consumed via
        operation-based Material Consumption Stock Entries."""
        if self.purpose == "Manufacture" and self._should_use_consumption_entry_cost():
            return {}

        item_dict = super().get_work_order_raw_materials(qty)

        if not (self.work_order and self.pro_doc and self.pro_doc.skip_transfer):
            return item_dict

        consumed = self._get_already_consumed_qty()
        if not consumed:
            return item_dict

        items_to_remove = []
        for item_code, row in item_dict.items():
            already = flt(consumed.get(row.get("item_code") or item_code, 0))
            if already <= 0:
                continue
            remaining = flt(row.qty) - already
            if remaining <= 0:
                items_to_remove.append(item_code)
            else:
                row.qty = flt(
                    remaining,
                    frappe.get_precision("Stock Entry Detail", "qty"),
                )

        for key in items_to_remove:
            del item_dict[key]

        return item_dict

    def _get_already_consumed_qty(self):
        """Return {item_code: consumed_qty} from submitted
        Material Consumption for Manufacture Stock Entries
        against this Work Order."""
        data = frappe.db.sql(
            """
            SELECT detail.item_code, SUM(detail.qty) as qty
            FROM `tabStock Entry` entry
            INNER JOIN `tabStock Entry Detail` detail ON detail.parent = entry.name
            WHERE entry.work_order = %s
                AND entry.purpose = 'Material Consumption for Manufacture'
                AND entry.docstatus = 1
                AND detail.s_warehouse IS NOT NULL
            GROUP BY detail.item_code
            """,
            (self.work_order,),
            as_dict=True,
        )
        return {d.item_code: flt(d.qty) for d in data} if data else {}

    def get_unconsumed_raw_materials(self):
        """Skip adding raw materials for Manufacture entries costed from consumption entries."""
        if self.purpose == "Manufacture" and self._should_use_consumption_entry_cost():
            return
        if hasattr(super(), "get_unconsumed_raw_materials"):
            super().get_unconsumed_raw_materials()

    def add_transfered_raw_materials_in_items(self):
        """Skip adding transferred raw materials for Manufacture entries costed from consumption entries."""
        if self.purpose == "Manufacture" and self._should_use_consumption_entry_cost():
            return
        if hasattr(super(), "add_transfered_raw_materials_in_items"):
            super().add_transfered_raw_materials_in_items()

    def validate_component_and_quantities(self):
        """Skip BOM raw material presence check when Manufacture entry uses consumption entries."""
        if self.purpose == "Manufacture" and self._should_use_consumption_entry_cost():
            self._validate_no_raw_materials_in_manufacture_entry(
                frappe.get_single("Manufacturing Settings")
            )
            return
        super().validate_component_and_quantities()

    def get_basic_rate_for_manufactured_item(
        self, finished_item_qty, outgoing_items_cost=0, has_consumption_basis=False
    ) -> float:
        """Compute finished good basic rate from Work Order consumption pool across partial entries."""
        settings = frappe.get_single("Manufacturing Settings")
        if not self._should_use_consumption_entry_cost(settings):
            return self._call_super_basic_rate(
                finished_item_qty, outgoing_items_cost, has_consumption_basis
            )

        self._validate_no_raw_materials_in_manufacture_entry(settings)

        fg_qty = flt(finished_item_qty)
        if fg_qty <= 0:
            return 0.0

        scrap_items_cost = sum(
            flt(d.basic_amount) for d in (self.get("items") or []) if d.is_scrap_item
        )
        manual_qty, manual_cost = self._get_manual_finished_items_qty_and_cost()

        allocated_cost = self._resolve_consumption_pool_allocated_cost(
            fg_qty, manual_qty
        )
        cost_left = flt(allocated_cost) - scrap_items_cost - manual_cost
        if self.flags.get("via_repost"):
            cost_left = max(cost_left, 0.0)

        return flt(cost_left / fg_qty)

    def _should_use_consumption_entry_cost(self, settings=None) -> bool:
        """Return True when Manufacturing Settings and submitted consumption entries apply."""
        if not self.work_order:
            return False
        settings = settings or frappe.get_single("Manufacturing Settings")
        return bool(
            cint(settings.get("material_consumption"))
            and cint(settings.get("get_rm_cost_from_consumption_entry"))
            and self._has_submitted_consumption_entries()
        )

    def _has_submitted_consumption_entries(self) -> bool:
        """Return True if the Work Order has any submitted Material Consumption entry."""
        if not self.work_order:
            return False
        return bool(
            frappe.db.exists(
                "Stock Entry",
                {
                    "docstatus": 1,
                    "work_order": self.work_order,
                    "purpose": "Material Consumption for Manufacture",
                },
            )
        )

    def _call_super_basic_rate(
        self, finished_item_qty, outgoing_items_cost=0, has_consumption_basis=False
    ) -> float:
        """Invoke base get_basic_rate_for_manufactured_item compatibly across ERPNext v15 versions."""
        params = inspect.signature(
            super().get_basic_rate_for_manufactured_item
        ).parameters
        if "has_consumption_basis" in params:
            return flt(
                super().get_basic_rate_for_manufactured_item(
                    finished_item_qty, outgoing_items_cost, has_consumption_basis
                )
            )
        return flt(
            super().get_basic_rate_for_manufactured_item(
                finished_item_qty, outgoing_items_cost
            )
        )

    def _get_manual_finished_items_qty_and_cost(self) -> tuple[float, float]:
        """Return manually rated finished goods (qty, cost) if supported by base StockEntry."""
        if hasattr(super(), "get_manually_rated_finished_items"):
            qty, cost = self.get_manually_rated_finished_items()
            return (flt(qty), flt(cost))
        return (0.0, 0.0)

    def _validate_no_raw_materials_in_manufacture_entry(self, settings) -> None:
        """Ensure Manufacture entry does not contain raw materials when consumption costing applies."""
        for item in self.get("items") or []:
            if not item.is_finished_item and not item.is_scrap_item:
                label = frappe.get_meta(settings.doctype).get_label(
                    "get_rm_cost_from_consumption_entry"
                )
                frappe.throw(
                    _(
                        "Row {0}: As {1} is enabled, raw materials cannot be added to {2} entry. Use {3} entry to consume raw materials."
                    ).format(
                        item.idx,
                        frappe.bold(label),
                        frappe.bold(_("Manufacture")),
                        frappe.bold(_("Material Consumption for Manufacture")),
                    )
                )

    def _get_total_consumed_cost(self) -> float:
        """Return net actual cost of submitted consumption minus WIP return receipts."""
        if not self.work_order:
            return 0.0
        res = frappe.db.sql(
            """
			SELECT COALESCE(
				SUM(
					COALESCE(
						sle_agg.sle_val,
						COALESCE(detail.valuation_rate, 0) * COALESCE(detail.transfer_qty, 0)
					)
				),
				0
			)
			FROM `tabStock Entry` entry
			INNER JOIN `tabStock Entry Detail` detail ON detail.parent = entry.name
			LEFT JOIN (
				SELECT sle.voucher_detail_no,
					SUM(-COALESCE(sle.stock_value_difference, 0)) AS sle_val
				FROM `tabStock Ledger Entry` sle
				INNER JOIN `tabStock Entry` se_sle ON se_sle.name = sle.voucher_no
				WHERE sle.voucher_type = 'Stock Entry'
					AND sle.is_cancelled = 0
					AND se_sle.work_order = %s
					AND se_sle.purpose = 'Material Consumption for Manufacture'
					AND se_sle.docstatus = 1
				GROUP BY sle.voucher_detail_no
			) sle_agg ON sle_agg.voucher_detail_no = detail.name
			WHERE entry.work_order = %s
				AND entry.purpose = 'Material Consumption for Manufacture'
				AND entry.docstatus = 1
				AND IFNULL(detail.s_warehouse, '') != ''
			""",
            (self.work_order, self.work_order),
        )
        total_consumed = flt(res[0][0]) if res else 0.0

        total_returned = 0.0
        wip_account = get_validated_wip_consumption_account(self.company)
        if wip_account:
            ret_res = frappe.db.sql(
                """
				SELECT COALESCE(
					SUM(
						COALESCE(
							sle_agg.sle_val,
							COALESCE(detail.valuation_rate, 0) * COALESCE(detail.transfer_qty, 0)
						)
					),
					0
				)
				FROM `tabStock Entry` entry
				INNER JOIN `tabStock Entry Detail` detail ON detail.parent = entry.name
				LEFT JOIN (
					SELECT sle.voucher_detail_no,
						SUM(COALESCE(sle.stock_value_difference, 0)) AS sle_val
					FROM `tabStock Ledger Entry` sle
					INNER JOIN `tabStock Entry` se_sle ON se_sle.name = sle.voucher_no
					WHERE sle.voucher_type = 'Stock Entry'
						AND sle.is_cancelled = 0
						AND se_sle.work_order = %s
						AND se_sle.purpose = 'Material Receipt'
						AND se_sle.docstatus = 1
					GROUP BY sle.voucher_detail_no
				) sle_agg ON sle_agg.voucher_detail_no = detail.name
				WHERE entry.work_order = %s
					AND entry.purpose = 'Material Receipt'
					AND entry.docstatus = 1
					AND IFNULL(detail.s_warehouse, '') = ''
					AND detail.expense_account = %s
				""",
                (self.work_order, self.work_order, wip_account),
            )
            total_returned = flt(ret_res[0][0]) if ret_res else 0.0

        total_je_adj = 0.0
        if wip_account and frappe.db.has_column(
            "Journal Entry Account", "custom_work_order"
        ):
            je_res = frappe.db.sql(
                """
				SELECT COALESCE(SUM(COALESCE(jea.debit, 0) - COALESCE(jea.credit, 0)), 0)
				FROM `tabJournal Entry Account` jea
				INNER JOIN `tabJournal Entry` je ON je.name = jea.parent
				WHERE je.docstatus = 1
					AND je.company = %s
					AND jea.custom_work_order = %s
					AND jea.account = %s
				""",
                (self.company, self.work_order, wip_account),
            )
            total_je_adj = flt(je_res[0][0]) if je_res else 0.0

        return max(0.0, total_consumed - total_returned + total_je_adj)

    def _get_previous_fg_only_manufacture_cost(self) -> float:
        """Return already-allocated cost from prior submitted FG-only Manufacture entries."""
        if not self.work_order:
            return 0.0
        current_name = self.name or ""
        res = frappe.db.sql(
            """
			SELECT COALESCE(SUM(COALESCE(detail.basic_amount, 0)), 0)
			FROM `tabStock Entry` entry
			INNER JOIN `tabStock Entry Detail` detail ON detail.parent = entry.name
			WHERE entry.work_order = %s
				AND entry.purpose = 'Manufacture'
				AND entry.docstatus = 1
				AND entry.name != %s
				AND COALESCE(entry.total_outgoing_value, 0) = 0
				AND (detail.is_finished_item = 1 OR detail.is_scrap_item = 1)
				AND NOT EXISTS (
					SELECT 1
					FROM `tabStock Entry Detail` out_detail
					WHERE out_detail.parent = entry.name
						AND IFNULL(out_detail.s_warehouse, '') != ''
				)
			""",
            (self.work_order, current_name),
        )
        return flt(res[0][0]) if res else 0.0

    def _is_final_manufacture_entry(self, finished_item_qty: float, wo_data) -> bool:
        """Determine whether this Manufacture entry closes the remaining consumption pool."""
        if getattr(self.flags, "kta_is_final_confirmation", False):
            return True
        if (
            self.get("custom_confirmation")
            and frappe.db.exists(
                "KTA Production Confirmation", self.custom_confirmation
            )
            and cint(
                frappe.db.get_value(
                    "KTA Production Confirmation",
                    self.custom_confirmation,
                    "is_final_confirmation",
                )
            )
        ):
            return True

        wo_qty = flt(wo_data.get("qty")) if wo_data else 0.0
        produced_qty = flt(wo_data.get("produced_qty")) if wo_data else 0.0
        if wo_qty <= 0:
            return False
        precision = self.precision("fg_completed_qty") or 4
        return flt(produced_qty + flt(finished_item_qty), precision) >= flt(
            wo_qty, precision
        )

    def _resolve_consumption_pool_allocated_cost(
        self, finished_item_qty: float, manual_qty: float = 0.0
    ) -> float:
        """Allocate consumption pool cost for partial or final Manufacture entries."""
        total_consumed_cost = self._get_total_consumed_cost()
        prev_fg_only_cost = self._get_previous_fg_only_manufacture_cost()
        remaining_pool_cost = max(0.0, total_consumed_cost - prev_fg_only_cost)
        if remaining_pool_cost <= 0:
            return self._get_fallback_bom_cost(finished_item_qty, manual_qty)

        wo_data = frappe.db.get_value(
            "Work Order", self.work_order, ["qty", "produced_qty"], as_dict=True
        )
        if self._is_final_manufacture_entry(finished_item_qty, wo_data):
            return remaining_pool_cost

        wo_qty = flt(wo_data.get("qty")) if wo_data else 0.0
        proportional_cost = self._get_proportional_actual_cost(
            finished_item_qty, wo_qty
        )
        if proportional_cost > 0:
            return min(remaining_pool_cost, proportional_cost)
        if wo_qty > 0:
            return min(
                remaining_pool_cost,
                flt((finished_item_qty / wo_qty) * total_consumed_cost),
            )
        return remaining_pool_cost

    def _get_proportional_actual_cost(
        self, finished_item_qty: float, wo_qty: float
    ) -> float:
        """Calculate proportional actual material cost per BOM/Work Order required item ratios."""
        if wo_qty <= 0 or finished_item_qty <= 0:
            return 0.0

        wo_items = self._get_work_order_required_items()
        consumption_rows = self._get_submitted_consumption_rows()
        if not consumption_rows:
            return 0.0
        if not wo_items:
            return flt(
                (flt(finished_item_qty) / flt(wo_qty))
                * sum(
                    flt(r["actual_cost"])
                    if r.get("actual_cost") is not None
                    else flt(r.get("valuation_rate")) * flt(r.get("transfer_qty"))
                    for r in consumption_rows
                )
            )

        required_qty_by_key, item_to_key = self._build_work_order_item_map(wo_items)
        cost_by_key, qty_by_key = self._aggregate_consumption_by_key(
            consumption_rows, required_qty_by_key, item_to_key
        )

        ratio = flt(finished_item_qty) / flt(wo_qty)
        total = 0.0
        for key, total_qty in qty_by_key.items():
            if total_qty <= 0:
                continue
            req_qty = required_qty_by_key.get(key, 0.0)
            if req_qty <= 0:
                continue
            avg_rate = cost_by_key[key] / total_qty
            total += ratio * req_qty * avg_rate

        return flt(total)

    def _get_work_order_required_items(self) -> list:
        """Fetch Work Order Item rows including custom_original_item when present."""
        if not self.work_order:
            return []
        fields = ["item_code", "required_qty"]
        if frappe.db.has_column("Work Order Item", "custom_original_item"):
            fields.append("custom_original_item")
        return frappe.get_all(
            "Work Order Item",
            filters={"parent": self.work_order},
            fields=fields,
        )

    def _get_submitted_consumption_rows(self) -> list:
        """Fetch submitted outgoing rows from Material Consumption entries for the Work Order."""
        if not self.work_order:
            return []
        custom_orig_select = (
            ", detail.custom_original_item"
            if frappe.db.has_column("Stock Entry Detail", "custom_original_item")
            else ""
        )
        return frappe.db.sql(
            f"""
			SELECT detail.item_code,
				detail.original_item
				{custom_orig_select},
				COALESCE(detail.valuation_rate, 0) AS valuation_rate,
				COALESCE(detail.transfer_qty, 0) AS transfer_qty,
				COALESCE(
					sle_agg.sle_val,
					COALESCE(detail.valuation_rate, 0) * COALESCE(detail.transfer_qty, 0)
				) AS actual_cost
			FROM `tabStock Entry` entry
			INNER JOIN `tabStock Entry Detail` detail ON detail.parent = entry.name
			LEFT JOIN (
				SELECT sle.voucher_detail_no,
					SUM(-COALESCE(sle.stock_value_difference, 0)) AS sle_val
				FROM `tabStock Ledger Entry` sle
				INNER JOIN `tabStock Entry` se_sle ON se_sle.name = sle.voucher_no
				WHERE sle.voucher_type = 'Stock Entry'
					AND sle.is_cancelled = 0
					AND se_sle.work_order = %s
					AND se_sle.purpose = 'Material Consumption for Manufacture'
					AND se_sle.docstatus = 1
				GROUP BY sle.voucher_detail_no
			) sle_agg ON sle_agg.voucher_detail_no = detail.name
			WHERE entry.work_order = %s
				AND entry.purpose = 'Material Consumption for Manufacture'
				AND entry.docstatus = 1
				AND IFNULL(detail.s_warehouse, '') != ''
			""",
            (self.work_order, self.work_order),
            as_dict=True,
        )

    @staticmethod
    def _build_work_order_item_map(wo_items) -> tuple[dict[str, float], dict[str, str]]:
        """Map required Work Order items and substituted items to canonical original item keys."""
        required_qty_by_key: dict[str, float] = {}
        item_to_key: dict[str, str] = {}
        for row in wo_items:
            item_code = row.get("item_code")
            canonical_key = row.get("custom_original_item") or item_code
            if not canonical_key:
                continue
            required_qty_by_key[canonical_key] = required_qty_by_key.get(
                canonical_key, 0.0
            ) + flt(row.get("required_qty"))
            if item_code:
                item_to_key[item_code] = canonical_key
            item_to_key[canonical_key] = canonical_key
        return required_qty_by_key, item_to_key

    @staticmethod
    def _aggregate_consumption_by_key(
        consumption_rows,
        required_qty_by_key: dict[str, float],
        item_to_key: dict[str, str],
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Aggregate consumed cost and quantity per canonical Work Order item key."""
        cost_by_key: dict[str, float] = {}
        qty_by_key: dict[str, float] = {}
        for row in consumption_rows:
            item_code = row.get("item_code")
            orig = row.get("custom_original_item") or row.get("original_item")
            if orig and orig in required_qty_by_key:
                key = orig
            elif item_code in item_to_key:
                key = item_to_key[item_code]
            else:
                key = orig or item_code
            if not key:
                continue
            qty = flt(row.get("transfer_qty"))
            cost = (
                flt(row["actual_cost"])
                if row.get("actual_cost") is not None
                else flt(row.get("valuation_rate")) * qty
            )
            cost_by_key[key] = cost_by_key.get(key, 0.0) + cost
            qty_by_key[key] = qty_by_key.get(key, 0.0) + qty
        return cost_by_key, qty_by_key

    def _get_fallback_bom_cost(
        self, finished_item_qty: float, manual_qty: float = 0.0
    ) -> float:
        """Return BOM-based fallback cost when no consumption pool balance remains."""
        if not self.get("bom_no"):
            return 0.0
        target_qty = flt(finished_item_qty) + flt(manual_qty)
        if target_qty <= 0:
            return 0.0
        params = inspect.signature(self.get_bom_raw_materials).parameters
        if "split_alternative_items" in params:
            bom_items = self.get_bom_raw_materials(
                target_qty, split_alternative_items=False
            )
        else:
            bom_items = self.get_bom_raw_materials(target_qty)
        return sum(
            flt(row.get("qty")) * flt(row.get("rate"))
            for row in (bom_items or {}).values()
        )

    def check_if_operations_completed(self):
        """Override to validate operation completed quantities directly against
        fg_completed_qty without requiring submitted Job Cards or failing on missing Job Cards.
        """
        if self.purpose == "Material Consumption for Manufacture":
            return

        if self.purpose != "Manufacture" or not self.work_order:
            return

        prod_order = frappe.get_doc("Work Order", self.work_order)
        allowance_percentage = flt(
            frappe.db.get_single_value(
                "Manufacturing Settings", "overproduction_percentage_for_work_order"
            )
        )

        precision = self.precision("fg_completed_qty") or 2

        for d in prod_order.get("operations", []):
            total_completed_qty = flt(self.fg_completed_qty) + flt(
                prod_order.produced_qty
            )
            completed_qty = (
                flt(d.completed_qty)
                + flt(d.process_loss_qty)
                + (allowance_percentage / 100 * flt(d.completed_qty))
            )
            if flt(total_completed_qty, precision) > flt(completed_qty, precision):
                frappe.throw(
                    _(
                        "Row #{0}: Operation {1} has not been sufficiently confirmed yet for Work Order {2}. Required finished goods qty: {3}, confirmed operation qty: {4}."
                    ).format(
                        d.idx,
                        frappe.bold(d.operation),
                        frappe.bold(self.work_order),
                        frappe.bold(str(total_completed_qty)),
                        frappe.bold(
                            str(flt(d.completed_qty) + flt(d.process_loss_qty))
                        ),
                    ),
                    OperationsNotCompleteError,
                )

    def validate_purpose(self):
        valid_purposes = [
            "Material Issue",
            "Material Receipt",
            "Material Transfer",
            "Material Transfer for Manufacture",
            "Manufacture",
            "Repack",
            "Send to Subcontractor",
            "Material Consumption for Manufacture",
            "Disassemble",
        ]

        if self.purpose not in valid_purposes:
            frappe.throw(
                _("Purpose must be one of {0}").format(", ".join(valid_purposes))
            )

        # KTA Override: Allow 'Material Consumption for Manufacture' against Job Card
        allowed_job_card_purposes = [
            "Material Transfer for Manufacture",
            "Repack",
            "Material Consumption for Manufacture",
        ]
        if self.job_card and self.purpose not in allowed_job_card_purposes:
            frappe.throw(
                _("For job card {0}, you can only make {1} type stock entries").format(
                    self.job_card, ", ".join(allowed_job_card_purposes)
                )
            )

    def validate_raw_materials_exists(self):
        """Override upstream ERPNext v15.95+ raw materials presence check.

        In KTA Shopfloor architecture:
        - Confirmations (custom_confirmation) create FG-only Stock Entries because
          materials are backflushed separately via 'Material Consumption for Manufacture'.
        - If a Work Order already has submitted Material Consumption entries, FG entries
          do not need to re-include raw materials.
        - Legacy or ad-hoc Work Orders without a BOM do not require raw materials.
        """
        if self.purpose not in ["Manufacture", "Repack", "Disassemble"]:
            return

        if frappe.db.get_single_value("Manufacturing Settings", "material_consumption"):
            return

        if self.purpose == "Manufacture" and self.work_order:
            if self.get("custom_confirmation"):
                return

            if frappe.db.exists(
                "Stock Entry",
                {
                    "work_order": self.work_order,
                    "purpose": "Material Consumption for Manufacture",
                    "docstatus": 1,
                },
            ):
                return

            bom_no = self.get("bom_no") or frappe.db.get_value(
                "Work Order", self.work_order, "bom_no"
            )
            if not bom_no:
                return

        if hasattr(super(), "validate_raw_materials_exists"):
            super().validate_raw_materials_exists()

    def get_matched_items(self, item_code):
        matched = super().get_matched_items(item_code)
        if matched:
            return matched

        matched_items = []
        # Check if any item row was substituted from item_code
        for item in self.items:
            orig = item.get("custom_original_item") or item.get("original_item")
            if orig and orig == item_code:
                matched_items.append(item)
                continue

            # Check approved Item Alternative relationship
            if (
                item.item_code
                and item_code
                and (
                    frappe.db.exists(
                        "Item Alternative",
                        {
                            "item_code": item_code,
                            "alternative_item_code": item.item_code,
                        },
                    )
                    or frappe.db.exists(
                        "Item Alternative",
                        {
                            "item_code": item.item_code,
                            "alternative_item_code": item_code,
                            "two_way": 1,
                        },
                    )
                )
            ):
                matched_items.append(item)

        return matched_items

    def _apply_wip_consumption_account(self) -> None:
        """Route Work Order consumption and FG-only Manufacture entries to Company WIP account."""
        wip_account = get_validated_wip_consumption_account(self.company)
        if not wip_account:
            return

        if not self.work_order or not self.get("items"):
            return

        if self.purpose == "Material Consumption for Manufacture":
            for d in self.items:
                if d.get("s_warehouse") and not d.get("t_warehouse"):
                    d.expense_account = wip_account
            return

        if (
            self.purpose == "Manufacture"
            and all(not d.get("s_warehouse") for d in self.items)
            and any(d.get("t_warehouse") for d in self.items)
        ):
            for d in self.items:
                if d.get("t_warehouse"):
                    d.expense_account = wip_account

    def _is_wip_return_receipt(self) -> bool:
        """Return True if this Material Receipt returns consumed stock against WIP account."""
        if self.purpose != "Material Receipt" or not self.work_order:
            return False

        wip_account = get_validated_wip_consumption_account(self.company)
        if not wip_account:
            return False

        return any(
            d.get("t_warehouse")
            and not d.get("s_warehouse")
            and d.get("expense_account") == wip_account
            for d in (self.get("items") or [])
        )

    def validate_work_order(self):
        """Retain Work Order link on WIP return Material Receipt entries."""
        if self._is_wip_return_receipt():
            wo = frappe.db.get_value(
                "Work Order",
                self.work_order,
                ["name", "docstatus", "company"],
                as_dict=True,
            )
            if not wo:
                frappe.throw(
                    _("Work Order {0} does not exist.").format(
                        frappe.bold(self.work_order)
                    )
                )
            if cint(wo.docstatus) != 1:
                frappe.throw(
                    _("Work Order {0} must be submitted.").format(
                        frappe.bold(self.work_order)
                    )
                )
            if wo.company != self.company:
                frappe.throw(
                    _("Work Order {0} does not belong to Company {1}.").format(
                        frappe.bold(self.work_order), frappe.bold(self.company)
                    )
                )
            return

        super().validate_work_order()

    def update_work_order(self):
        """Skip Work Order status/qty updates for WIP return Material Receipt entries."""
        if self._is_wip_return_receipt():
            return

        super().update_work_order()

    def validate(self):
        self._apply_wip_consumption_account()
        self._validate_single_item_package_split()

        # 1. Standart ERPNext kontrollerini yap
        super().validate()

        # 2. Sadece Manufacture tipinde ve Draft (0) durumundaysa calis
        if (
            self.purpose == "Manufacture"
            and self.work_order
            and self.docstatus == 0
            and not self.get("__splitting_batches")
        ):
            # 3. Sonsuz dongu korumasi (Flag)
            self.set("__splitting_batches", True)
            BatchSplitManager.split_manufacturing_batches(self)

    def _validate_single_item_package_split(self):
        """Ensure Package Split / Package Merge Stock Entries operate on a single item code."""
        if self.stock_entry_type not in ("Package Split", "Package Merge"):
            return

        items = self.get("items") or []
        distinct_target_items = {
            d.get("item_code")
            for d in items
            if d.get("t_warehouse") and d.get("item_code")
        }
        distinct_source_items = {
            d.get("item_code")
            for d in items
            if d.get("s_warehouse") and d.get("item_code")
        }
        distinct_all_items = {d.get("item_code") for d in items if d.get("item_code")}
        if (
            len(distinct_target_items) > 1
            or len(distinct_source_items) > 1
            or len(distinct_all_items) > 1
        ):
            frappe.throw(
                _("{0} allows only one item per Stock Entry.").format(
                    self.stock_entry_type
                )
            )

    def update_stock_ledger(
        self, allow_negative_stock=False, via_landed_cost_voucher=False
    ):
        """
        Base StockEntry.update_stock_ledger does not accept via_landed_cost_voucher, swallow it here
        """
        super().update_stock_ledger(allow_negative_stock=allow_negative_stock)

    def on_submit(self):
        super().on_submit()
        if not self.stock_entry_type:
            return

        is_printable = bool(
            cint(
                frappe.db.get_value(
                    "Stock Entry Type",
                    self.stock_entry_type,
                    "custom_etiket_basilabilir",
                )
            )
        )
        if not is_printable:
            return

        frappe.enqueue(
            "erpnextkta.overrides.KTAStockEntry.print_labels_on_submit",
            stock_entry=self.name,
            user=frappe.session.user,
            queue="short",
            timeout=120,
            now=bool(frappe.flags.in_test),
            enqueue_after_commit=not bool(frappe.flags.in_test),
        )

    def on_cancel(self):
        batches_to_disable = []
        if self.purpose == "Manufacture":
            batches_to_disable = self._get_generated_batches()

        relabeling_types = (
            "Return from Production Supply",
            "Package Split",
            "Package Merge",
        )
        touched_pairs: set[tuple[str, str]] = set()
        target_pairs: set[tuple[str, str]] = set()
        if self.stock_entry_type in relabeling_types:
            touched_pairs, target_pairs = self._collect_touched_item_batches()

        super().on_cancel()

        self._delete_associated_labels()

        if self.purpose == "Manufacture":
            for batch_name in batches_to_disable:
                if frappe.db.exists("Batch", batch_name):
                    frappe.db.set_value(
                        "Batch",
                        batch_name,
                        {"batch_qty": 0, "disabled": 1},
                        update_modified=False,
                    )

        if self.stock_entry_type in relabeling_types:
            self._clear_batch_reference_links()
            self._sync_relabeling_on_cleanup(
                touched_pairs,
                target_pairs,
                disable_empty_targets=self.stock_entry_type
                in ("Package Split", "Package Merge"),
            )

    def on_trash(self):
        batches_to_delete = []
        if self.purpose == "Manufacture":
            batches_to_delete = self._get_generated_batches()

        relabeling_types = (
            "Return from Production Supply",
            "Package Split",
            "Package Merge",
        )
        touched_pairs: set[tuple[str, str]] = set()
        target_pairs: set[tuple[str, str]] = set()
        if self.stock_entry_type in relabeling_types:
            touched_pairs, target_pairs = self._collect_touched_item_batches()
            self._clear_batch_reference_links()

        self._delete_associated_labels()
        super().on_trash()

        if self.purpose == "Manufacture":
            for batch_name in batches_to_delete:
                if frappe.db.exists("Batch", batch_name):
                    try:
                        frappe.delete_doc("Batch", batch_name, ignore_permissions=True)
                    except Exception:
                        # If deletion fails (e.g., due to LinkExistsError), ensure it's empty and disabled
                        frappe.db.set_value(
                            "Batch",
                            batch_name,
                            {"batch_qty": 0, "disabled": 1},
                            update_modified=False,
                        )

        if self.stock_entry_type in relabeling_types:
            self._sync_relabeling_on_cleanup(
                touched_pairs,
                target_pairs,
                disable_empty_targets=(
                    self.stock_entry_type in ("Package Split", "Package Merge")
                    and self.docstatus == 2
                ),
            )

    def _clear_batch_reference_links(self) -> None:
        """Clear Stock Entry back-links on Batch records so trash never fails with LinkExistsError."""
        linked_batches = frappe.get_all(
            "Batch",
            filters={"reference_doctype": "Stock Entry", "reference_name": self.name},
            pluck="name",
        )
        for batch_name in linked_batches:
            frappe.db.set_value(
                "Batch",
                batch_name,
                {"reference_doctype": None, "reference_name": None},
                update_modified=False,
            )

    def _delete_associated_labels(self):
        labels = frappe.get_all(
            "KTA Stock Label",
            filters={"reference_doctype": "Stock Entry", "reference_name": self.name},
            pluck="name",
        )
        delete_labels_with_print_logs(labels)

    def _collect_touched_item_batches(
        self,
    ) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
        """Collect all (item_code, batch_no) pairs and target pairs from rows and bundles."""
        touched_pairs: set[tuple[str, str]] = set()
        target_pairs: set[tuple[str, str]] = set()
        target_row_names: set[str] = set()

        for row in self.get("items") or []:
            item_code = row.get("item_code")
            batch_no = row.get("batch_no")
            is_target = bool(row.get("t_warehouse"))
            if is_target and row.get("name"):
                target_row_names.add(row.get("name"))

            if item_code and batch_no:
                touched_pairs.add((item_code, batch_no))
                if is_target:
                    target_pairs.add((item_code, batch_no))

            bundle_name = row.get("serial_and_batch_bundle")
            if bundle_name:
                self._add_bundle_entries(
                    bundle_name,
                    item_code,
                    is_target=is_target,
                    touched_pairs=touched_pairs,
                    target_pairs=target_pairs,
                )

        db_bundles = frappe.get_all(
            "Serial and Batch Bundle",
            filters={"voucher_type": "Stock Entry", "voucher_no": self.name},
            fields=["name", "item_code", "type_of_transaction", "voucher_detail_no"],
        )
        for bundle in db_bundles:
            b_name = bundle.get("name")
            b_item = bundle.get("item_code")
            if not b_name or not b_item:
                continue
            is_inward_bundle = (
                bundle.get("type_of_transaction") == "Inward"
                or bundle.get("voucher_detail_no") in target_row_names
            )
            self._add_bundle_entries(
                b_name,
                b_item,
                is_target=is_inward_bundle,
                touched_pairs=touched_pairs,
                target_pairs=target_pairs,
            )

        return touched_pairs, target_pairs

    @staticmethod
    def _add_bundle_entries(
        bundle_name: str,
        item_code: str | None,
        is_target: bool,
        touched_pairs: set[tuple[str, str]],
        target_pairs: set[tuple[str, str]],
    ) -> None:
        if not item_code:
            return
        entries = frappe.get_all(
            "Serial and Batch Entry",
            filters={
                "parent": bundle_name,
                "parenttype": "Serial and Batch Bundle",
            },
            fields=["batch_no", "is_outward"],
        )
        for entry in entries:
            entry_batch = entry.get("batch_no")
            if not entry_batch:
                continue
            touched_pairs.add((item_code, entry_batch))
            if is_target and not cint(entry.get("is_outward")):
                target_pairs.add((item_code, entry_batch))

    @staticmethod
    def _sync_relabeling_on_cleanup(
        touched_pairs: set[tuple[str, str]],
        target_pairs: set[tuple[str, str]],
        disable_empty_targets: bool = False,
    ) -> None:
        for item_code, batch_no in sorted(touched_pairs):
            sync_batch_label_to_ledger_balance(item_code, batch_no)
            if (item_code, batch_no) not in target_pairs:
                balances = get_batch_ledger_balances(item_code, batch_no)
                total_qty = flt(sum(flt(b["qty"]) for b in balances))
                if total_qty > 1e-6:
                    existing_label = frappe.get_all(
                        "KTA Stock Label",
                        filters={
                            "label_type": [
                                "in",
                                ["Depo Giriş Etiketi", "İş Emri Etiketi"],
                            ],
                            "item_code": item_code,
                        },
                        or_filters=[
                            ["batch", "=", batch_no],
                            ["sut_barcode", "=", batch_no],
                        ],
                        limit=1,
                    )
                    if not existing_label:
                        positive_balances = [
                            b for b in balances if flt(b["qty"]) > 1e-6
                        ]
                        best_wh = max(positive_balances, key=lambda b: flt(b["qty"]))[
                            "warehouse"
                        ]
                        upsert_box_label(
                            item_code=item_code,
                            batch_no=batch_no,
                            qty=total_qty,
                            target_warehouse=best_wh,
                            fallback_ref="TRANSFER",
                        )

        if not disable_empty_targets:
            return

        for item_code, batch_no in sorted(target_pairs):
            if not frappe.db.exists("Batch", batch_no):
                continue
            balances = get_batch_ledger_balances(item_code, batch_no)
            total_qty = flt(sum(flt(b["qty"]) for b in balances))
            if total_qty <= 1e-6:
                frappe.db.set_value(
                    "Batch",
                    batch_no,
                    {"batch_qty": 0, "disabled": 1},
                    update_modified=False,
                )

    def _get_generated_batches(self):
        batches = set()

        # 1. Try to find bundles via voucher_no in DB (works even if doc is cancelled and row links are cleared)
        bundles = frappe.get_all(
            "Serial and Batch Bundle",
            filters={"voucher_type": "Stock Entry", "voucher_no": self.name},
            pluck="name",
        )

        # 2. Fallback to row fields if not found (e.g. before save/submit)
        if not bundles:
            bundles = [
                row.get("serial_and_batch_bundle")
                for row in self.get("items", [])
                if row.get("is_finished_item") and row.get("serial_and_batch_bundle")
            ]

        for bundle in bundles:
            entries = frappe.get_all(
                "Serial and Batch Entry",
                filters={"parent": bundle, "is_outward": 0},
                pluck="batch_no",
            )
            for b in entries:
                if b:
                    batches.add(b)
        return list(batches)


def print_labels_on_submit(stock_entry, user=None):
    if user:
        frappe.set_user(user)

    from erpnextkta.kta_stock.label_manager import print_stock_entry_labels

    try:
        doc = frappe.get_doc("Stock Entry", stock_entry)
        if doc.stock_entry_type:
            is_printable = frappe.db.get_value(
                "Stock Entry Type", doc.stock_entry_type, "custom_etiket_basilabilir"
            )
            if is_printable:
                print_stock_entry_labels(stock_entry)
    except Exception:
        import traceback

        frappe.log_error(
            f"Stock Entry Print Error: {traceback.format_exc()}",
            "Stock Entry Submit Print Error",
        )
