from __future__ import annotations
import frappe
from frappe import _
from .qc import _get_doc_for_idc_write, _assert_child_table_exists, _session_employee_name_or_throw
from ._helpers import _assert_enjeksiyon_kalip_valid

ENJEKSIYON_CHILD_FIELDNAME = "enjeksiyon_olcumleri"

@frappe.whitelist()
def get_enjeksiyon_tolerans(hammadde_no: str) -> dict:
    """Fetch tolerance values for a given raw material (hammadde) from KTA Enjeksiyon Toleranslari."""
    if not hammadde_no:
        return {}
    
    if not frappe.db.exists("KTA Enjeksiyon Toleranslari", {"hammadde_no": hammadde_no}):
        return {}
        
    doc = frappe.get_doc("KTA Enjeksiyon Toleranslari", {"hammadde_no": hammadde_no})
    
    def to_f(val):
        return float(val) if val else 0.0

    return {
        "hammadde_kazan_isisi_merkez": to_f(doc.hammadde_kazan_isisi_merkez),
        "hammadde_kazan_isisi_tolerans": to_f(doc.hammadde_kazan_isisi_tolerans),
        "ara_hortum_isisi_merkez": to_f(doc.ara_hortum_isisi_merkez),
        "ara_hortum_isisi_tolerans": to_f(doc.ara_hortum_isisi_tolerans),
        "kafa_meme_isisi_merkez": to_f(doc.kafa_meme_isisi_merkez),
        "kafa_meme_isisi_tolerans": to_f(doc.kafa_meme_isisi_tolerans),
        "soguk_su_isisi_min": to_f(doc.soguk_su_isisi_min),
        "soguk_su_isisi_maks": to_f(doc.soguk_su_isisi_maks),
        "motor_devir_min": to_f(doc.motor_devir_min),
        "motor_devir_maks": to_f(doc.motor_devir_maks),
        "enjeksiyon_zamani_min": to_f(doc.enjeksiyon_zamani_min),
        "enjeksiyon_zamani_maks": to_f(doc.enjeksiyon_zamani_maks),
        "sogutma_zamani_min": to_f(doc.sogutma_zamani_min),
        "sogutma_zamani_maks": to_f(doc.sogutma_zamani_maks),
        "cekme_kuvveti_min": to_f(doc.cekme_kuvveti_min)
    }

@frappe.whitelist()
def add_enjeksiyon_olcumu(name: str, payload: str | dict):
    """Add a new enjeksiyon measurement row."""
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, ENJEKSIYON_CHILD_FIELDNAME)

    if isinstance(payload, str):
        import json
        payload = json.loads(payload)

    kalip_no = (payload.get("kalip_no") or "").strip()
    if not kalip_no:
        frappe.throw(_("Kalıp No zorunludur."))

    if not payload.get("goz_kontrol"):
        frappe.throw(_("Göz Kontrol zorunludur."))

    ao_row_id = (payload.get("alt_operasyon_kaydi") or "").strip()
    ao_row = None
    hammadde_no = (payload.get("hammadde_no") or "").strip()
    if ao_row_id:
        ao_row = next((r for r in doc.get("alt_operasyon_kayitlari", []) if r.name == ao_row_id), None)
        if not ao_row:
            frappe.throw(_("Alt operasyon kaydı bulunamadı ({0}).").format(ao_row_id))
        if ao_row.kalip_no:
            kalip_no = (ao_row.kalip_no or "").strip()
        if ao_row.hammadde:
            hammadde_no = (ao_row.hammadde or "").strip()
        _validate_enjeksiyon_period_and_qc(doc, ao_row, (payload.get("kontrol_periyodu") or "").strip())

    _assert_enjeksiyon_kalip_valid(kalip_no)
    tolerans_doc = _validate_enjeksiyon_parameters(payload, hammadde_no)

    row = {
        "kontrol_periyodu": payload.get("kontrol_periyodu"),
        "kalip_no": kalip_no,
        "hammadde_no": hammadde_no,
        "goz_kontrol": 1 if payload.get("goz_kontrol") else 0,
        "cekme_kuvveti_olculen": float(payload.get("cekme_kuvveti_olculen") or 0),
        "hammadde_kazan_isisi": float(payload.get("hammadde_kazan_isisi") or 0),
        "ara_hortum_isisi": float(payload.get("ara_hortum_isisi") or 0),
        "kafa_meme_isisi": float(payload.get("kafa_meme_isisi") or 0),
        "soguk_su_isisi": float(payload.get("soguk_su_isisi") or 0),
        "motor_devir": float(payload.get("motor_devir") or 0),
        "hammadde_enjeksiyon_zamani": float(payload.get("hammadde_enjeksiyon_zamani") or 0),
        "sogutma_zamani": float(payload.get("sogutma_zamani") or 0),
        "hata_kodu": payload.get("hata_kodu"),
        "hata_miktari": float(payload.get("hata_miktari") or 0),
        
        "hedef_hammadde_kazan_isisi_merkez": float(tolerans_doc.hammadde_kazan_isisi_merkez or 0),
        "hedef_hammadde_kazan_isisi_tolerans": float(tolerans_doc.hammadde_kazan_isisi_tolerans or 0),
        "hedef_ara_hortum_isisi_merkez": float(tolerans_doc.ara_hortum_isisi_merkez or 0),
        "hedef_ara_hortum_isisi_tolerans": float(tolerans_doc.ara_hortum_isisi_tolerans or 0),
        "hedef_kafa_meme_isisi_merkez": float(tolerans_doc.kafa_meme_isisi_merkez or 0),
        "hedef_kafa_meme_isisi_tolerans": float(tolerans_doc.kafa_meme_isisi_tolerans or 0),
        "hedef_soguk_su_isisi_min": float(tolerans_doc.soguk_su_isisi_min or 0),
        "hedef_soguk_su_isisi_maks": float(tolerans_doc.soguk_su_isisi_maks or 0),
        "hedef_motor_devir_min": float(tolerans_doc.motor_devir_min or 0),
        "hedef_motor_devir_maks": float(tolerans_doc.motor_devir_maks or 0),
        "hedef_enjeksiyon_zamani_min": float(tolerans_doc.enjeksiyon_zamani_min or 0),
        "hedef_enjeksiyon_zamani_maks": float(tolerans_doc.enjeksiyon_zamani_maks or 0),
        "hedef_sogutma_zamani_min": float(tolerans_doc.sogutma_zamani_min or 0),
        "hedef_sogutma_zamani_maks": float(tolerans_doc.sogutma_zamani_maks or 0),
        "hedef_cekme_kuvveti_min": float(tolerans_doc.cekme_kuvveti_min or 0),

        "alt_operasyon_kaydi": payload.get("alt_operasyon_kaydi"),
        "olcum_tarihi": frappe.utils.now_datetime(),
        "operator": _session_employee_name_or_throw(),
    }

    doc.append(ENJEKSIYON_CHILD_FIELDNAME, row)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    frappe.db.commit()

    earned_points = _check_and_award_enjeksiyon_energy_points(
        doc, payload.get("alt_operasyon_kaydi")
    )
    return {"status": "success", "earned_points": earned_points}


def _ensure_enjeksiyon_energy_point_rule() -> str:
    rule_name = "Enjeksiyon 3/3 Ölçüm Tamamlama"
    if not frappe.db.exists("Energy Point Rule", rule_name):
        rule = frappe.new_doc("Energy Point Rule")
        rule.rule_name = rule_name
        rule.reference_doctype = "Calisma Karti"
        rule.for_doc_event = "Custom"
        rule.points = 3
        rule.enabled = 1
        rule.flags.ignore_permissions = True
        rule.insert()
        frappe.db.commit()
    return rule_name


def _check_and_award_enjeksiyon_energy_points(doc, ao_row_id: str) -> int:
    """Award 3 Energy Points if all 3 periods (Başlangıç, Ara, Bitiş) are completed for this sub-operation.

    Returns the awarded points (3) or 0 if incomplete or already awarded.
    """
    if not ao_row_id:
        return 0

    all_periods = {"Başlangıç", "Ara", "Bitiş"}
    sub_op_measurements = [
        r for r in doc.get("enjeksiyon_olcumleri", [])
        if (r.alt_operasyon_kaydi or "").strip() == ao_row_id
    ]
    periods = {(r.kontrol_periyodu or "").strip() for r in sub_op_measurements}
    if not all_periods.issubset(periods):
        return 0

    user = frappe.session.user
    if doc.operator:
        emp_user = frappe.db.get_value("Employee", doc.operator, "user_id")
        if emp_user and frappe.db.exists("User", emp_user):
            user = emp_user

    if not user or user == "Guest" or not frappe.db.exists("User", user):
        return 0

    already_awarded = frappe.db.sql(
        """
        SELECT name FROM `tabEnergy Point Log`
        WHERE reference_doctype = 'Calisma Karti'
          AND reference_name = %s
          AND reason LIKE %s
          AND reverted = 0
        LIMIT 1
        """,
        (doc.name, f"%[{ao_row_id}]%"),
    )
    if already_awarded:
        return 0

    rule_name = _ensure_enjeksiyon_energy_point_rule()
    points = int(frappe.db.get_value("Energy Point Rule", rule_name, "points") or 3)

    from frappe.social.doctype.energy_point_log.energy_point_log import create_energy_points_log

    reason_str = _("Enjeksiyon alt operasyonu için tüm periyot ölçümlerini (3/3) eksiksiz tamamlama. [{0}]").format(ao_row_id)
    create_energy_points_log(
        ref_doctype="Calisma Karti",
        ref_name=doc.name,
        doc={
            "points": points,
            "rule": rule_name,
            "user": user,
            "type": "Auto",
            "reason": reason_str,
        },
    )
    frappe.db.commit()
    return points

def _get_enjeksiyon_tolerans_doc_or_throw(hammadde_no: str):
    """Fetch tolerance doc from KTA Enjeksiyon Toleranslari or raise ValidationError."""
    if not hammadde_no:
        frappe.throw(_("Hammadde seçimi zorunludur."), frappe.ValidationError)

    if not frappe.db.exists("KTA Enjeksiyon Toleranslari", {"hammadde_no": hammadde_no}):
        frappe.throw(
            _("'{0}' hammaddesi için enjeksiyon tolerans parametresi bulunamadı. Ölçüm kaydedilemez.").format(hammadde_no),
            frappe.ValidationError,
        )

    return frappe.get_doc("KTA Enjeksiyon Toleranslari", {"hammadde_no": hammadde_no})

def _validate_enjeksiyon_center_tolerances(payload: dict, t):
    """Validate center ± tolerance limits."""
    checks = [
        ("hammadde_kazan_isisi", _("Hammadde Kazan Isısı"), t.hammadde_kazan_isisi_merkez, t.hammadde_kazan_isisi_tolerans, "°C"),
        ("ara_hortum_isisi", _("Ara Hortum Isısı"), t.ara_hortum_isisi_merkez, t.ara_hortum_isisi_tolerans, "°C"),
        ("kafa_meme_isisi", _("Kafa (Meme) Isısı"), t.kafa_meme_isisi_merkez, t.kafa_meme_isisi_tolerans, "°C"),
    ]
    for fieldname, label, merkez_val, tol_val, unit in checks:
        merkez = float(merkez_val or 0)
        tol = float(tol_val or 0)
        val = float(payload.get(fieldname) or 0)
        if merkez > 0 and (val < (merkez - tol) or val > (merkez + tol)):
            frappe.throw(
                _("'{0}' ({1} {2}) tolerans sınırları dışındadır. Kabul edilen aralık: {3} - {4} {2}").format(
                    label, val, unit, merkez - tol, merkez + tol
                ),
                frappe.ValidationError,
            )

def _validate_enjeksiyon_range_tolerances(payload: dict, t):
    """Validate min-max range limits."""
    checks = [
        ("soguk_su_isisi", _("Soğuk Su Isısı"), t.soguk_su_isisi_min, t.soguk_su_isisi_maks, "°C"),
        ("motor_devir", _("Motor Devir"), t.motor_devir_min, t.motor_devir_maks, ""),
        ("hammadde_enjeksiyon_zamani", _("Hammadde Enjeksiyon Zamanı"), t.enjeksiyon_zamani_min, t.enjeksiyon_zamani_maks, "sn"),
        ("sogutma_zamani", _("Soğutma Zamanı"), t.sogutma_zamani_min, t.sogutma_zamani_maks, "sn"),
    ]
    for fieldname, label, min_limit, max_limit, unit in checks:
        val = float(payload.get(fieldname) or 0)
        min_val = float(min_limit or 0)
        max_val = float(max_limit or 0)
        if (min_val > 0 and val < min_val) or (max_val > 0 and val > max_val):
            u_str = f" {unit}" if unit else ""
            frappe.throw(
                _("'{0}' ({1}{2}) tolerans sınırları dışındadır. Kabul edilen aralık: {3} - {4}{2}").format(
                    label, val, u_str, min_val, max_val
                ),
                frappe.ValidationError,
            )

def _validate_enjeksiyon_parameters(payload: dict, hammadde_no: str):
    """Validate required fields, existence of tolerances, and tolerance limits."""
    t = _get_enjeksiyon_tolerans_doc_or_throw(hammadde_no)

    cekme = float(payload.get("cekme_kuvveti_olculen") or 0)
    cekme_min = max(100.0, float(t.cekme_kuvveti_min or 0))
    if cekme < cekme_min:
        frappe.throw(
            _("Çekme Kuvveti ({0} N) kabul edilen minimum değerin ({1} N) altındadır.").format(cekme, cekme_min),
            frappe.ValidationError,
        )

    required_params = {
        "hammadde_kazan_isisi": _("Hammadde Kazan Isısı"),
        "ara_hortum_isisi": _("Ara Hortum Isısı"),
        "kafa_meme_isisi": _("Kafa (Meme) Isısı"),
        "soguk_su_isisi": _("Soğuk Su Isısı"),
        "motor_devir": _("Motor Devir"),
        "hammadde_enjeksiyon_zamani": _("Hammadde Enjeksiyon Zamanı"),
        "sogutma_zamani": _("Soğutma Zamanı"),
    }
    for f, label in required_params.items():
        if float(payload.get(f) or 0) <= 0:
            frappe.throw(_("'{0}' alanı boş veya 0 bırakılamaz.").format(label), frappe.ValidationError)

    _validate_enjeksiyon_center_tolerances(payload, t)
    _validate_enjeksiyon_range_tolerances(payload, t)
    return t

def _validate_enjeksiyon_period_and_qc(doc, ao_row, kontrol_periyodu: str):
    """Enforce injection measurement period progression, 3-reading limit, and QC lock."""
    from ._helpers import has_qc_role, is_qc_rejected
    if not has_qc_role():
        if is_qc_rejected(ao_row.quality_inspection_status):
            frappe.throw(
                _("Bu alt operasyon kaydı kalite birimi tarafından reddedilmiştir. "
                  "Yeni ölçüm eklenemez.")
            )

    existing_for_ao = [
        r for r in doc.get(ENJEKSIYON_CHILD_FIELDNAME, [])
        if (r.alt_operasyon_kaydi or "").strip() == ao_row.name
    ]
    if len(existing_for_ao) >= 3:
        frappe.throw(
            _("Bir alt operasyon için en fazla 3 ölçüm (Başlangıç, Ara, Bitiş) girilebilir.")
        )

    existing_periods = {
        (r.kontrol_periyodu or "").strip() for r in existing_for_ao if (r.kontrol_periyodu or "").strip()
    }

    if len(existing_for_ao) == 0 and kontrol_periyodu != "Başlangıç":
        frappe.throw(_("İlk enjeksiyon ölçümü 'Başlangıç' periyodunda olmak zorundadır."))

    if "Başlangıç" not in existing_periods and kontrol_periyodu != "Başlangıç":
        frappe.throw(_("İlk enjeksiyon ölçümü 'Başlangıç' periyodunda olmak zorundadır."))

    if kontrol_periyodu in existing_periods:
        frappe.throw(
            _("'{0}' periyodu için zaten bir ölçüm kaydedilmiş.").format(kontrol_periyodu)
        )

def _validate_enjeksiyon_update_period(doc, ao_row_id: str, rowname: str, new_period: str):
    """Prevent duplicate periods within the same sub-operation during update."""
    if not (ao_row_id and new_period):
        return
    other_measurements = [
        r for r in doc.get(ENJEKSIYON_CHILD_FIELDNAME, [])
        if (r.alt_operasyon_kaydi or "").strip() == ao_row_id and r.name != rowname
    ]
    other_periods = {(r.kontrol_periyodu or "").strip() for r in other_measurements}
    if new_period in other_periods:
        frappe.throw(
            _("'{0}' periyodu için zaten bir ölçüm kaydedilmiş.").format(new_period)
        )

def _assert_enjeksiyon_qc_unlocked(doc, enjeksiyon_row):
    """Check if the enjeksiyon row's parent alt operasyon is QC-locked."""
    from ._helpers import has_qc_role
    if has_qc_role():
        return

    ao_row_id = (enjeksiyon_row.alt_operasyon_kaydi or "").strip()
    ao_row = None
    alt_ops = doc.get("alt_operasyon_kayitlari") or []

    if ao_row_id:
        ao_row = next((r for r in alt_ops if r.name == ao_row_id), None)
    else:
        # Legacy resolution:
        # 1. Match by kalip_no if unique among sub-operations
        kalip = (enjeksiyon_row.kalip_no or "").strip().lower()
        if kalip:
            matching = [r for r in alt_ops if (r.kalip_no or "").strip().lower() == kalip]
            if len(matching) == 1:
                ao_row = matching[0]

        # 2. If exactly one sub-operation exists on the card, associate with it
        if not ao_row and len(alt_ops) == 1:
            ao_row = alt_ops[0]

    if ao_row:
        from .alt_operasyon import _assert_qc_unlocked
        _assert_qc_unlocked(doc, ao_row)
    else:
        # Unresolved legacy measurement:
        # If card has QC decision or is finished, do not grant silent write access to non-QC users
        card_qc = (doc.kalite_kontrol or "").strip()
        if card_qc in ["Onaylandı", "Accepted", "Reddedildi", "Rejected", "Kısmi Kabul Edildi"] or doc.bitis_saati:
            frappe.throw(
                _("Bu ölçüm kaydı kalite kontrolü tamamlanmış bir karta aittir. "
                  "Değişiklik veya silme işlemi için kalite birimini bilgilendirin.")
            )

@frappe.whitelist()
def update_enjeksiyon_olcumu(name: str, rowname: str, payload: str | dict):
    """Update an existing enjeksiyon measurement row."""
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, ENJEKSIYON_CHILD_FIELDNAME)

    if isinstance(payload, str):
        import json
        payload = json.loads(payload)

    rows = doc.get(ENJEKSIYON_CHILD_FIELDNAME) or []
    target = next((r for r in rows if r.name == rowname), None)
    if not target:
        frappe.throw(_("Enjeksiyon ölçüm satırı bulunamadı (rowname: {0}).").format(rowname))

    _assert_enjeksiyon_qc_unlocked(doc, target)

    kalip_no = (payload.get("kalip_no") or "").strip()
    if not kalip_no:
        frappe.throw(_("Kalıp No zorunludur."))

    if not payload.get("goz_kontrol"):
        frappe.throw(_("Göz Kontrol zorunludur."))

    ao_row_id = (payload.get("alt_operasyon_kaydi") or target.alt_operasyon_kaydi or "").strip()
    new_period = (payload.get("kontrol_periyodu") or target.kontrol_periyodu or "").strip()
    _validate_enjeksiyon_update_period(doc, ao_row_id, rowname, new_period)

    hammadde_no = (payload.get("hammadde_no") or target.hammadde_no or "").strip()
    if ao_row_id:
        ao_row = next((r for r in doc.get("alt_operasyon_kayitlari", []) if r.name == ao_row_id), None)
        if ao_row:
            if ao_row.kalip_no:
                kalip_no = (ao_row.kalip_no or "").strip()
            if ao_row.hammadde:
                hammadde_no = (ao_row.hammadde or "").strip()

    _assert_enjeksiyon_kalip_valid(kalip_no)
    tolerans_doc = _validate_enjeksiyon_parameters(payload, hammadde_no)

    target.kontrol_periyodu = payload.get("kontrol_periyodu")
    target.kalip_no = kalip_no
    target.hammadde_no = hammadde_no
    target.goz_kontrol = 1 if payload.get("goz_kontrol") else 0
    target.cekme_kuvveti_olculen = float(payload.get("cekme_kuvveti_olculen") or 0)
    target.hammadde_kazan_isisi = float(payload.get("hammadde_kazan_isisi") or 0)
    target.ara_hortum_isisi = float(payload.get("ara_hortum_isisi") or 0)
    target.kafa_meme_isisi = float(payload.get("kafa_meme_isisi") or 0)
    target.soguk_su_isisi = float(payload.get("soguk_su_isisi") or 0)
    target.motor_devir = float(payload.get("motor_devir") or 0)
    target.hammadde_enjeksiyon_zamani = float(payload.get("hammadde_enjeksiyon_zamani") or 0)
    target.sogutma_zamani = float(payload.get("sogutma_zamani") or 0)
    target.hata_kodu = payload.get("hata_kodu")
    target.hata_miktari = float(payload.get("hata_miktari") or 0)
    
    target.hedef_hammadde_kazan_isisi_merkez = float(tolerans_doc.hammadde_kazan_isisi_merkez or 0)
    target.hedef_hammadde_kazan_isisi_tolerans = float(tolerans_doc.hammadde_kazan_isisi_tolerans or 0)
    target.hedef_ara_hortum_isisi_merkez = float(tolerans_doc.ara_hortum_isisi_merkez or 0)
    target.hedef_ara_hortum_isisi_tolerans = float(tolerans_doc.ara_hortum_isisi_tolerans or 0)
    target.hedef_kafa_meme_isisi_merkez = float(tolerans_doc.kafa_meme_isisi_merkez or 0)
    target.hedef_kafa_meme_isisi_tolerans = float(tolerans_doc.kafa_meme_isisi_tolerans or 0)
    target.hedef_soguk_su_isisi_min = float(tolerans_doc.soguk_su_isisi_min or 0)
    target.hedef_soguk_su_isisi_maks = float(tolerans_doc.soguk_su_isisi_maks or 0)
    target.hedef_motor_devir_min = float(tolerans_doc.motor_devir_min or 0)
    target.hedef_motor_devir_maks = float(tolerans_doc.motor_devir_maks or 0)
    target.hedef_enjeksiyon_zamani_min = float(tolerans_doc.enjeksiyon_zamani_min or 0)
    target.hedef_enjeksiyon_zamani_maks = float(tolerans_doc.enjeksiyon_zamani_maks or 0)
    target.hedef_sogutma_zamani_min = float(tolerans_doc.sogutma_zamani_min or 0)
    target.hedef_sogutma_zamani_maks = float(tolerans_doc.sogutma_zamani_maks or 0)
    target.hedef_cekme_kuvveti_min = float(tolerans_doc.cekme_kuvveti_min or 0)

    if "alt_operasyon_kaydi" in payload:
        new_ao_id = (payload.get("alt_operasyon_kaydi") or "").strip()
        if new_ao_id and new_ao_id != (target.alt_operasyon_kaydi or "").strip():
            new_ao = next((r for r in doc.get("alt_operasyon_kayitlari", []) if r.name == new_ao_id), None)
            if not new_ao:
                frappe.throw(_("Alt operasyon kaydı bulunamadı ({0}).").format(new_ao_id))
            from .alt_operasyon import _assert_qc_unlocked
            _assert_qc_unlocked(doc, new_ao)
        target.alt_operasyon_kaydi = payload.get("alt_operasyon_kaydi")

    target.olcum_tarihi = frappe.utils.now_datetime()
    # target.operator intentionally left unchanged

    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
    return {"status": "success"}

@frappe.whitelist()
def delete_enjeksiyon_olcumu(name: str, rowname: str):
    """Delete an enjeksiyon measurement row."""
    doc = _get_doc_for_idc_write(name)
    _assert_child_table_exists(doc, ENJEKSIYON_CHILD_FIELDNAME)

    rows = doc.get(ENJEKSIYON_CHILD_FIELDNAME) or []
    idx = next((i for i, r in enumerate(rows) if r.name == rowname), None)

    if idx is None:
        frappe.throw(_("Enjeksiyon ölçüm satırı bulunamadı (rowname: {0}).").format(rowname))

    target = rows[idx]
    _assert_enjeksiyon_qc_unlocked(doc, target)

    rows.pop(idx)
    doc.set(ENJEKSIYON_CHILD_FIELDNAME, rows)
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()

    return {"status": "success"}

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_enjeksiyon_allowed_items(doctype, txt, searchfield, start, page_len, filters):
    """Link field search for allowed enjeksiyon items that have tolerance data.

    filters expected:
      - calisma_karti: Calisma Karti name
    """
    from ._helpers import get_allowed_items_with_groups
    
    if isinstance(filters, str):
        import json
        filters = json.loads(filters)

    calisma_karti = (filters or {}).get("calisma_karti")
    if not calisma_karti:
        return []

    allowed_items = get_allowed_items_with_groups(calisma_karti)
    if not allowed_items:
        return []

    txt = (txt or "").strip()

    items_placeholder = ", ".join(["%s"] * len(allowed_items))
    return frappe.db.sql(
        f"""
        SELECT name, item_name, item_group
        FROM `tabItem`
        WHERE
            name IN ({items_placeholder})
            AND disabled = 0
            AND name IN (SELECT hammadde_no FROM `tabKTA Enjeksiyon Toleranslari`)
            AND (name LIKE %s OR item_name LIKE %s)
        ORDER BY name ASC
        LIMIT %s, %s
        """,
        tuple(allowed_items) + (f"%{txt}%", f"%{txt}%", int(start), int(page_len)),
    )
