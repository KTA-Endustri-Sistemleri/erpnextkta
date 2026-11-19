# English comments as requested

"""Public API entrypoint for kta_calisma_karti.

IMPORTANT:
This module path is referenced by frontend method strings, e.g.
  erpnextkta.kta_calisma_karti.api.get_my_calisma_kartlari

So we keep this file as a stable facade and move implementations into
`erpnextkta/kta_calisma_karti/api_impl/`.
"""

from __future__ import annotations

# Alt Operasyon
from .api_impl.alt_operasyon import (
    add_alt_operasyon_kaydi,
    delete_alt_operasyon_kaydi,
    get_alt_operasyon_options,
    update_alt_operasyon_kaydi,
)

# Analytics
from .api_impl.analytics import get_work_order_card_analytics

# Re-export whitelisted functions
from .api_impl.barcode import get_work_order_by_barcode
from .api_impl.cards import (
    check_active_card_data,
    get_calisma_karti_detail,
    get_my_calisma_kartlari,
)
from .api_impl.create import create_calisma_karti, get_operations_for_job_card

# Enjeksiyon
from .api_impl.enjeksiyon import (
    add_enjeksiyon_olcumu,
    delete_enjeksiyon_olcumu,
    get_enjeksiyon_tolerans,
    search_enjeksiyon_allowed_items,
    update_enjeksiyon_olcumu,
)
from .api_impl.hurda import (
    add_hurda,
    delete_hurda,
    get_hurda_nedeni_options,
    search_allowed_hurda_items,
    update_hurda,
)

# Krimp
from .api_impl.krimp import (
    add_krimp_olcumu,
    delete_krimp_olcumu,
    get_kalip_list,
    get_krimp_book_details,
    get_unique_kesit_list,
    search_krimp_items,
    update_krimp_olcumu,
)

# QC + QC child tables
from .api_impl.qc import (
    add_barkod_kaydi,
    add_idc_olcumu,
    delete_barkod_kaydi,
    delete_idc_olcumu,
    get_qc_templates_for_ck,
    get_template_details,
    search_allowed_idc_items,
    submit_kta_quality_inspection,
    update_barkod_kaydi,
    update_idc_olcumu,
    update_kalite_kontrol,
)

__all__ = [
    # Alt Operasyon
    "add_alt_operasyon_kaydi",
    "add_barkod_kaydi",
    # Enjeksiyon
    "add_enjeksiyon_olcumu",
    "add_hurda",
    "add_idc_olcumu",
    # Krimp
    "add_krimp_olcumu",
    "check_active_card_data",
    # Create + barcode helpers
    "create_calisma_karti",
    "delete_alt_operasyon_kaydi",
    "delete_barkod_kaydi",
    "delete_enjeksiyon_olcumu",
    "delete_hurda",
    "delete_idc_olcumu",
    "delete_krimp_olcumu",
    "get_alt_operasyon_options",
    "get_calisma_karti_detail",
    "get_enjeksiyon_tolerans",
    # Hurda
    "get_hurda_nedeni_options",
    # Print protocol
    "get_job_card_protocols_html",
    "get_kalip_list",
    "get_krimp_book_details",
    "get_my_calisma_kartlari",
    "get_operations_for_job_card",
    "get_qc_templates_for_ck",
    "get_template_details",
    "get_unique_kesit_list",
    "get_work_order_by_barcode",
    # Analytics
    "get_work_order_card_analytics",
    "search_allowed_hurda_items",
    # QC child tables
    "search_allowed_idc_items",
    "search_enjeksiyon_allowed_items",
    "search_krimp_items",
    "submit_kta_quality_inspection",
    "update_alt_operasyon_kaydi",
    "update_barkod_kaydi",
    "update_enjeksiyon_olcumu",
    "update_hurda",
    "update_idc_olcumu",
    # QC
    "update_kalite_kontrol",
    "update_krimp_olcumu",
]
from .api_impl.print_protocol import get_job_card_protocols_html
