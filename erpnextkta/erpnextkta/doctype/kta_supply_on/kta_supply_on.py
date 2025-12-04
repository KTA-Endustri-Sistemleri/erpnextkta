# Copyright (c) 2025, Framras AS and contributors
# For license information, please see license.txt

# import frappe
from datetime import datetime

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class KTASupplyOn(Document):
    """Validate incoming Supply On rows."""

    _DATE_FORMATS = ("%d.%m.%Y", "%d-%m-%Y", "%Y.%m.%d", "%m.%d.%Y")
    _INVALID_DATE_TOKENS = {"invalid date", "nan", "none", "null"}

    def validate(self):
        self._normalize_date_fields()
        self._ensure_supply_on_head()

    def _normalize_date_fields(self):
        if not hasattr(self, "_kta_date_fields"):
            meta = frappe.get_meta(self.doctype)
            self._kta_date_fields = [
                df.fieldname for df in meta.fields if df.fieldtype in ("Date", "Datetime")
            ]

        for fieldname in self._kta_date_fields:
            raw_value = self.get(fieldname)
            normalized_value = self._parse_date_value(fieldname, raw_value)
            self.set(fieldname, normalized_value)

    def _parse_date_value(self, fieldname, value):
        if not value:
            return None

        if isinstance(value, str):
            candidate = value.strip()
        else:
            candidate = value

        if not candidate:
            return None

        if isinstance(candidate, str) and candidate.lower() in self._INVALID_DATE_TOKENS:
            return None

        try:
            return getdate(candidate)
        except Exception:
            pass

        if isinstance(candidate, str):
            for fmt in self._DATE_FORMATS:
                try:
                    return datetime.strptime(candidate, fmt).date()
                except Exception:
                    continue

        frappe.logger("erpnextkta").warning(
            f"KTA Supply On -> Unable to parse date field '{fieldname}' with value '{value}'"
        )
        return None

    def _ensure_supply_on_head(self):
        """Ensure every record is linked to a Supply On Head even when imported via legacy templates."""
        if not self.supply_on_head and getattr(self, "parenttype", None) == "KTA Supply On Head":
            self.supply_on_head = getattr(self, "parent", None)

        if not self.supply_on_head:
            frappe.logger("erpnextkta").info(
                f"KTA Supply On kaydı {self.name} Supply On Head bağlantısı olmadan kaydediliyor."
            )
