# English comments as requested

"""Public API entrypoint for kta_calisma_karti.

IMPORTANT:
This module path is referenced by frontend method strings, e.g.
  erpnextkta.kta_calisma_karti.api.get_my_calisma_kartlari

So we keep this file as a stable facade and move implementations into
`erpnextkta/kta_calisma_karti/api_impl/`.
"""

from __future__ import annotations

# Re-export whitelisted functions
from .api_impl.barcode import get_job_card_by_barcode, get_work_order_by_barcode
from .api_impl.cards import get_calisma_karti_detail, get_my_calisma_kartlari
from .api_impl.create import create_calisma_karti
from .api_impl.hurda import (
    add_hurda,
    delete_hurda,
    get_hurda_nedeni_options,
    search_allowed_hurda_items,  # <-- EKLE
    update_hurda,
)

# QC + QC child tables
from .api_impl.qc import (
    search_allowed_idc_items,
    update_kalite_kontrol,
    add_idc_olcumu,
    update_idc_olcumu,
    delete_idc_olcumu,
    add_barkod_kaydi,
    update_barkod_kaydi,
    delete_barkod_kaydi,
)

__all__ = [
    "get_my_calisma_kartlari",
    "get_calisma_karti_detail",

    # QC
    "update_kalite_kontrol",

    # QC child tables
    "search_allowed_idc_items",
    "add_idc_olcumu",
    "update_idc_olcumu",
    "delete_idc_olcumu",
    "add_barkod_kaydi",
    "update_barkod_kaydi",
    "delete_barkod_kaydi",

    # Hurda
    "get_hurda_nedeni_options",
    "search_allowed_hurda_items",
    "add_hurda",
    "update_hurda",
    "delete_hurda",

    # Create + barcode helpers
    "create_calisma_karti",
    "get_job_card_by_barcode",
    "get_work_order_by_barcode",
]