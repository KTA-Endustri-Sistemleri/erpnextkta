import frappe
from frappe import _
from frappe.utils import cint


def _fetch_wip_account_details(account_name: str):
    """Fetch core validation fields for an Account record."""
    return frappe.db.get_value(
        "Account",
        account_name,
        ["name", "company", "is_group", "account_type"],
        as_dict=True,
    )


def _is_valid_wip_account(acc, company: str) -> bool:
    """Return True if account dict exists, matches company, is non-group, and is not Stock type."""
    if not acc:
        return False
    if acc.company != company:
        return False
    if cint(acc.is_group):
        return False
    return (acc.account_type or "") != "Stock"


def validate_wip_consumption_account(doc, method=None):
    """Validate Company.custom_wip_consumption_account on Company save/validate."""
    wip_account = doc.get("custom_wip_consumption_account")
    if not wip_account:
        return

    acc = _fetch_wip_account_details(wip_account)
    if not acc or acc.company != doc.name:
        frappe.throw(
            _("WIP Consumption Account {0} must belong to Company {1}.").format(
                frappe.bold(wip_account), frappe.bold(doc.name)
            ),
            frappe.ValidationError,
        )

    if cint(acc.is_group):
        frappe.throw(
            _("WIP Consumption Account {0} cannot be a Group account.").format(
                frappe.bold(wip_account)
            ),
            frappe.ValidationError,
        )

    if (acc.account_type or "") == "Stock":
        frappe.throw(
            _(
                "WIP Consumption Account {0} cannot be a Stock-type account. ERPNext forbids Stock-type accounts as Difference Account, and 151 Stock warehouse accounts cannot be used."
            ).format(frappe.bold(wip_account)),
            frappe.ValidationError,
        )


def get_validated_wip_consumption_account(company: str | None) -> str | None:
    """Return validated WIP consumption account for a company, or None if unset/invalid."""
    if not company or not frappe.db.has_column(
        "Company", "custom_wip_consumption_account"
    ):
        return None

    acc_name = frappe.db.get_value("Company", company, "custom_wip_consumption_account")
    if not acc_name:
        return None

    acc = _fetch_wip_account_details(acc_name)
    if not _is_valid_wip_account(acc, company):
        return None

    return acc.name


def ensure_journal_entry_work_order_field() -> None:
    """Idempotently create Journal Entry Account.custom_work_order custom field."""
    if frappe.db.has_column("Journal Entry Account", "custom_work_order"):
        return

    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    custom_fields = {
        "Journal Entry Account": [
            {
                "fieldname": "custom_work_order",
                "label": "Work Order",
                "fieldtype": "Link",
                "options": "Work Order",
                "insert_after": "project",
                "module": "erpnextkta",
            }
        ]
    }
    create_custom_fields(custom_fields, ignore_validate=True)
    frappe.clear_cache(doctype="Journal Entry Account")
