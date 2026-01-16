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
    update_hurda,
)
from .api_impl.qc import update_kalite_kontrol


__all__ = [
    "get_my_calisma_kartlari",
    "get_calisma_karti_detail",
    "update_kalite_kontrol",
    "get_hurda_nedeni_options",
    "add_hurda",
    "update_hurda",
    "delete_hurda",
    "create_calisma_karti",
    "get_job_card_by_barcode",
    "get_work_order_by_barcode",
]
