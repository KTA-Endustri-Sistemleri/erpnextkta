# English comments as requested

"""API implementation for Work Order Çalışma Kartı analytics."""

from __future__ import annotations

from typing import Any

import frappe

from erpnextkta.kta_calisma_karti.services.work_card_analytics_service import (
    get_work_order_card_analytics as _get_analytics,
)


@frappe.whitelist()
def get_work_order_card_analytics(work_order: str) -> dict[str, Any]:
    """Whitelisted endpoint returning Work Order Çalışma Kartı analytics tree."""
    return _get_analytics(work_order)


# Ensure attribute is present for introspection and testing
get_work_order_card_analytics.__whitelisted__ = True
