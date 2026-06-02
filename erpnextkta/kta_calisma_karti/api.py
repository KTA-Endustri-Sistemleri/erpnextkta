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
from .api_impl.cards import get_calisma_karti_detail, get_my_calisma_kartlari, check_active_card_data
from .api_impl.create import create_calisma_karti, get_operations_for_job_card
from .api_impl.hurda import (
    add_hurda,
    delete_hurda,
    get_hurda_nedeni_options,
    search_allowed_hurda_items,
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
    get_qc_templates_for_ck,
    get_template_details,
    submit_kta_quality_inspection,
)

# Krimp
from .api_impl.krimp import (
    add_krimp_olcumu,
    update_krimp_olcumu,
    delete_krimp_olcumu,
    search_krimp_items,
    get_krimp_book_details,
    get_unique_kesit_list,
)

# Enjeksiyon
from .api_impl.enjeksiyon import (
    add_enjeksiyon_olcumu,
    update_enjeksiyon_olcumu,
    delete_enjeksiyon_olcumu,
    get_enjeksiyon_tolerans,
    search_enjeksiyon_allowed_items,
)

# Alt Operasyon
from .api_impl.alt_operasyon import (
    add_alt_operasyon_kaydi,
    update_alt_operasyon_kaydi,
    delete_alt_operasyon_kaydi,
    get_alt_operasyon_options,
)

__all__ = [
    "get_my_calisma_kartlari",
    "get_calisma_karti_detail",
    "check_active_card_data",

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
    "get_qc_templates_for_ck",
    "get_template_details",
    "submit_kta_quality_inspection",

    # Hurda
    "get_hurda_nedeni_options",
    "search_allowed_hurda_items",
    "add_hurda",
    "update_hurda",
    "delete_hurda",

    # Alt Operasyon
    "add_alt_operasyon_kaydi",
    "update_alt_operasyon_kaydi",
    "delete_alt_operasyon_kaydi",
    "get_alt_operasyon_options",

    # Create + barcode helpers
    "create_calisma_karti",
    "get_operations_for_job_card",
    "get_work_order_by_barcode",

    # Krimp
    "add_krimp_olcumu",
    "update_krimp_olcumu",
    "delete_krimp_olcumu",
    "search_krimp_items",
    "get_krimp_book_details",
    "get_unique_kesit_list",
    
    # Enjeksiyon
    "add_enjeksiyon_olcumu",
    "update_enjeksiyon_olcumu",
    "delete_enjeksiyon_olcumu",
    "get_enjeksiyon_tolerans",
    "search_enjeksiyon_allowed_items",
]
