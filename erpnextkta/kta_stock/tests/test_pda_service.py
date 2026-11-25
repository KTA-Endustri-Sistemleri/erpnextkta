import time
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import cint, flt, nowdate, nowtime
from frappe.utils.password import remove_encrypted_password, set_encrypted_password
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from erpnextkta.kta_stock.services.pda_service import (
    ALLOWED_PDA_ROLES,
    PDA_DEVICE_COOKIE,
    PDA_DEVICE_TTL_SECONDS,
    PDA_INACTIVITY_TIMEOUT_SEC,
    get_pda_boot_data,
    get_pda_operators,
    has_valid_pda_device_cookie,
    issue_pda_device_token,
    pda_handover_logout,
    verify_pda_device_token,
    verify_pda_pin,
)
from erpnextkta.kta_stock.services.relabeling_service import get_batch_ledger_balances
from erpnextkta.kta_stock.setup import (
    PDA_ROLE_STOCK_USER,
    setup,
    setup_pda_custom_fields,
)
from erpnextkta.tests.test_utils import (
    KTABaseTestCase,
    create_test_company,
    create_test_item_group,
)

_MISSING = object()


class TestPdaService(KTABaseTestCase):
    def setUp(self):
        super().setUp()
        self._saved_local = {
            attr: getattr(frappe.local, attr, _MISSING)
            for attr in ("request", "request_ip", "cookie_manager", "login_manager")
        }
        frappe.cache().delete_keys("pda_pin_fail:")
        setup()
        self._ensure_zebra_templates()

    def _ensure_zebra_templates(self):
        if not frappe.db.exists("DocType", "KTA Zebra Templates"):
            return
        for tmpl_name in ("Depo Giriş Etiketi", "İş Emri Etiketi"):
            if not frappe.db.exists("KTA Zebra Templates", tmpl_name):
                frappe.get_doc(
                    {
                        "doctype": "KTA Zebra Templates",
                        "doctype_name": tmpl_name,
                        "zebra_template": "^XA^FD{data.item_code}|{data.sut_barcode}|{data.qty}^FS^XZ",
                    }
                ).insert(ignore_permissions=True, ignore_if_duplicate=True)
            frappe.cache().delete_value(f"kta_zebra_template_{tmpl_name}")

    def _ensure_pda_test_warehouses(self, suffix: str = "op"):
        company = self._get_test_company()
        abbr = frappe.db.get_value("Company", company, "abbr") or "_TC"
        parent_wh = frappe.db.get_value(
            "Warehouse", {"company": company, "is_group": 1}, "name"
        )
        group_label = f"_Test PDA Grp {suffix}"
        group_name = f"{group_label} - {abbr}"
        if not frappe.db.exists("Warehouse", group_name):
            group_doc = frappe.get_doc(
                {
                    "doctype": "Warehouse",
                    "warehouse_name": group_label,
                    "company": company,
                    "parent_warehouse": parent_wh,
                    "is_group": 1,
                }
            ).insert(ignore_permissions=True)
            group_name = group_doc.name

        leaves = []
        for idx in ("A", "B"):
            wh_label = f"_Test PDA Leaf {idx} {suffix}"
            wh_name = f"{wh_label} - {abbr}"
            if not frappe.db.exists("Warehouse", wh_name):
                wh_doc = frappe.get_doc(
                    {
                        "doctype": "Warehouse",
                        "warehouse_name": wh_label,
                        "company": company,
                        "parent_warehouse": group_name,
                        "is_group": 0,
                    }
                ).insert(ignore_permissions=True)
                wh_name = wh_doc.name
            leaves.append((wh_name, wh_label))

        return (
            company,
            group_name,
            leaves[0][0],
            leaves[0][1],
            leaves[1][0],
            leaves[1][1],
        )

    def _ensure_pda_batch_item(
        self, item_code: str = "_TEST-PDA-BATCH-ITEM", barcode: str | None = None
    ) -> str:
        item_group = create_test_item_group()
        if not frappe.db.exists("Item", item_code):
            doc = frappe.get_doc(
                {
                    "doctype": "Item",
                    "item_code": item_code,
                    "item_name": f"Test {item_code}",
                    "item_group": item_group,
                    "is_stock_item": 1,
                    "stock_uom": "Nos",
                    "has_batch_no": 1,
                    "create_new_batch": 0,
                }
            )
            if barcode:
                doc.append("barcodes", {"barcode": barcode})
            doc.insert(ignore_permissions=True)
        return item_code

    def _ensure_batch(self, batch_id: str, item_code: str, **kwargs):
        if frappe.db.exists("Batch", batch_id):
            return frappe.get_doc("Batch", batch_id)
        payload = {
            "doctype": "Batch",
            "batch_id": batch_id,
            "item": item_code,
            "batch_qty": 0,
        }
        payload.update(kwargs)
        doc = frappe.get_doc(payload)
        doc.flags.ignore_links = True
        doc.insert(ignore_permissions=True)
        return doc

    def _receive_batch_stock(
        self,
        item_code: str,
        warehouse: str,
        batch_no: str,
        qty: float,
        rate: float = 10.0,
        company: str | None = None,
    ):
        resolved_company = company or self._get_test_company()
        se = frappe.get_doc(
            {
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "purpose": "Material Receipt",
                "company": resolved_company,
                "posting_date": nowdate(),
                "posting_time": nowtime(),
                "items": [
                    {
                        "item_code": item_code,
                        "t_warehouse": warehouse,
                        "qty": flt(qty),
                        "basic_rate": flt(rate),
                        "allow_zero_valuation_rate": 1 if flt(rate) <= 0 else 0,
                        "batch_no": batch_no,
                        "use_serial_batch_fields": 1,
                    }
                ],
            }
        )
        se.insert(ignore_permissions=True)
        se.submit()
        return se

    def _create_box_label(
        self,
        item_code: str,
        batch_no: str,
        qty: float,
        warehouse: str,
        label_type: str = "Depo Giriş Etiketi",
        sut_barcode: str | None = None,
    ):
        lbl = frappe.get_doc(
            {
                "doctype": "KTA Stock Label",
                "label_type": label_type,
                "reference_doctype": "Purchase Receipt",
                "reference_name": f"MAT-PRE-{batch_no}",
                "item_code": item_code,
                "qty": flt(qty),
                "uom": "Nos",
                "batch": batch_no,
                "sut_barcode": sut_barcode or batch_no,
                "target_warehouse": warehouse,
                "quality_ref": "QI-PDA-TEST",
                "supplier_delivery_note": "IRS-PDA-01",
                "gr_posting_date": nowdate(),
            }
        )
        lbl.flags.ignore_links = True
        lbl.insert(ignore_permissions=True)
        return lbl

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.cache().delete_keys("pda_pin_fail:")
        for attr, val in self._saved_local.items():
            if val is _MISSING:
                if hasattr(frappe.local, attr):
                    delattr(frappe.local, attr)
            else:
                setattr(frappe.local, attr, val)
        frappe.db.rollback()
        super().tearDown()

    def _get_test_company(self) -> str:
        company = frappe.db.get_value(
            "Company", "_Test Company", "name"
        ) or frappe.db.get_value("Company", {}, "name")
        if not company:
            company = create_test_company("_Test Company")
        return company

    def _ensure_department(self, department_name: str, company: str) -> str:
        if frappe.db.exists("Department", department_name):
            return department_name

        existing = frappe.db.get_value(
            "Department", {"department_name": department_name}, "name"
        )
        if existing:
            return existing

        if not frappe.db.exists("Department", "All Departments"):
            root = frappe.get_doc(
                {
                    "doctype": "Department",
                    "department_name": "All Departments",
                    "is_group": 1,
                }
            )
            root.company = None
            root.flags.ignore_mandatory = True
            root.flags.ignore_links = True
            root.insert(ignore_permissions=True)

        dept = frappe.get_doc(
            {
                "doctype": "Department",
                "department_name": department_name,
            }
        )
        # Prevent Department.autoname from appending company abbr (e.g. " - _TC")
        dept.company = None
        dept.flags.ignore_mandatory = True
        dept.flags.ignore_links = True
        dept.insert(ignore_permissions=True)
        frappe.db.set_value("Department", dept.name, "company", company)
        return dept.name

    def _ensure_test_pda_operator(
        self,
        email: str = "pda_op_default@example.com",
        first_name: str = "_Test PDA Operator",
        department: str = "AMBAR - KTA",
        pin: str | None = "4829",
        roles: list[str] | None = None,
        enabled: int = 1,
        status: str = "Active",
        with_user: bool = True,
        user_type: str | None = None,
    ) -> str:
        if not frappe.db.exists("Custom Field", "Employee-custom_pda_pin"):
            setup_pda_custom_fields()

        company = self._get_test_company()
        resolved_department = self._ensure_department(department, company)

        if not frappe.db.exists("Gender", "Male"):
            frappe.get_doc({"doctype": "Gender", "gender": "Male"}).insert(
                ignore_permissions=True
            )

        target_roles = [PDA_ROLE_STOCK_USER] if roles is None else list(roles)

        if with_user:
            for role_name in target_roles:
                if not frappe.db.exists("Role", role_name):
                    frappe.get_doc(
                        {
                            "doctype": "Role",
                            "role_name": role_name,
                            "desk_access": 0 if role_name.startswith("KTA PDA ") else 1,
                        }
                    ).insert(ignore_permissions=True)

            if not frappe.db.exists("User", email):
                user_doc_data = {
                    "doctype": "User",
                    "email": email,
                    "first_name": first_name,
                    "enabled": 1,
                    "send_welcome_email": 0,
                }
                if user_type is not None:
                    user_doc_data["user_type"] = user_type
                user = frappe.get_doc(user_doc_data)
                for role_name in target_roles:
                    user.append("roles", {"role": role_name})
                user.insert(ignore_permissions=True)
            else:
                user = frappe.get_doc("User", email)
                user.enabled = 1
                if user_type is not None:
                    user.user_type = user_type
                user.set("roles", [{"role": r} for r in target_roles])
                user.save(ignore_permissions=True)

        emp_name = None
        if with_user:
            emp_name = frappe.db.get_value("Employee", {"user_id": email}, "name")
        if not emp_name:
            emp_name = frappe.db.get_value(
                "Employee", {"first_name": first_name}, "name"
            )

        if not emp_name:
            emp = frappe.get_doc(
                {
                    "doctype": "Employee",
                    "first_name": first_name,
                    "gender": "Male",
                    "date_of_birth": "1990-01-01",
                    "date_of_joining": "2024-01-01",
                    "relieving_date": "2025-01-01" if status == "Left" else None,
                    "status": status,
                    "company": company,
                    "department": resolved_department,
                    "user_id": email if with_user else None,
                }
            )
            emp.insert(ignore_permissions=True)
            emp_name = emp.name
        else:
            frappe.db.set_value(
                "Employee",
                emp_name,
                {
                    "status": status,
                    "relieving_date": "2025-01-01" if status == "Left" else None,
                    "department": resolved_department,
                    "user_id": email if with_user else None,
                },
            )

        if with_user and not enabled:
            frappe.db.set_value("User", email, "enabled", 0)
            frappe.clear_cache(user=email)
        elif with_user:
            frappe.db.set_value("User", email, "enabled", 1)
            frappe.clear_cache(user=email)

        if pin:
            set_encrypted_password(
                "Employee", emp_name, pin, fieldname="custom_pda_pin"
            )
        else:
            remove_encrypted_password("Employee", emp_name, fieldname="custom_pda_pin")

        return emp_name

    def _set_request_with_cookie(self, token: str | None = None, path: str = "/pda"):
        from frappe.auth import CookieManager

        headers = {}
        if token is not None:
            headers["Cookie"] = f"{PDA_DEVICE_COOKIE}={token}"
        env = EnvironBuilder(path=path, headers=headers).get_environ()
        frappe.local.request = Request(env)
        frappe.local.request_ip = "127.0.0.1"
        frappe.local.cookie_manager = CookieManager()

    def test_device_token_roundtrip_and_tamper_rejection(self):
        token = issue_pda_device_token("test-pda-device-01")
        self.assertIsInstance(token, str)
        self.assertIn(".", token)
        self.assertTrue(verify_pda_device_token(token))

        payload_b64, sig_hex = token.rsplit(".", 1)
        flipped = "0" if sig_hex[-1] != "0" else "1"
        tampered_sig = f"{payload_b64}.{sig_hex[:-1]}{flipped}"
        self.assertFalse(verify_pda_device_token(tampered_sig))

        tampered_payload = f"A{payload_b64[1:]}.{sig_hex}"
        self.assertFalse(verify_pda_device_token(tampered_payload))

        self.assertFalse(verify_pda_device_token(None))
        self.assertFalse(verify_pda_device_token(""))
        self.assertFalse(verify_pda_device_token("invalid-token"))
        self.assertFalse(verify_pda_device_token("ğüşi.1234"))

        now = time.time()
        with patch("erpnextkta.kta_stock.services.pda_service.time.time") as mock_time:
            mock_time.return_value = now
            short_lived = issue_pda_device_token("test-pda-device-02")
            mock_time.return_value = now + PDA_DEVICE_TTL_SECONDS + 5
            self.assertFalse(verify_pda_device_token(short_lived))

    def test_guest_without_device_cookie_rejected_on_boot_and_pin(self):
        emp_name = self._ensure_test_pda_operator(
            email="pda_guest_reject@example.com",
            first_name="_Test PDA Guest Reject",
        )
        self._set_request_with_cookie(token=None)
        frappe.set_user("Guest")

        self.assertFalse(has_valid_pda_device_cookie())
        with self.assertRaises(frappe.PermissionError):
            get_pda_boot_data()
        with self.assertRaises(frappe.PermissionError):
            verify_pda_pin(emp_name, "4829")
        with self.assertRaises(frappe.PermissionError):
            pda_handover_logout()

    def test_get_pda_operators_uses_pda_roles_without_department_and_excludes_plain_stock_user(
        self,
    ):
        from erpnextkta.kta_stock.services.pda_service import (
            ALL_PDA_ROLES,
            PDA_MODULE_REGISTRY,
            PDA_STOCK_ROLES,
        )

        self.assertNotIn("Stock User", ALL_PDA_ROLES)
        self.assertEqual(ALLOWED_PDA_ROLES, ALL_PDA_ROLES)
        self.assertIn(PDA_ROLE_STOCK_USER, PDA_STOCK_ROLES)
        self.assertEqual([c["key"] for c in PDA_MODULE_REGISTRY], ["stock"])

        uid = frappe.generate_hash("", 5)
        pda_emp = self._ensure_test_pda_operator(
            email=f"pda_other_dept_{uid}@example.com",
            first_name=f"_Test PDA OtherDept {uid}",
            department=f"_Test Üretim Hattı {uid}",
            pin="4829",
            roles=[PDA_ROLE_STOCK_USER],
            user_type="Website User",
        )
        emp_sevk = self._ensure_test_pda_operator(
            email=f"pda_op_sevk_{uid}@example.com",
            first_name=f"_Test PDA Sevk {uid}",
            department="Sevk",
            pin=None,
            roles=["Stock Manager"],
        )
        office_emp = self._ensure_test_pda_operator(
            email=f"office_stock_only_{uid}@example.com",
            first_name=f"_Test Office StockOnly {uid}",
            department="AMBAR - KTA",
            pin="4829",
            roles=["Stock User"],
        )
        emp_no_user = self._ensure_test_pda_operator(
            first_name=f"_Test PDA NoUser {uid}",
            department="AMBAR - KTA",
            with_user=False,
        )
        emp_disabled_user = self._ensure_test_pda_operator(
            email=f"pda_op_disabled_{uid}@example.com",
            first_name=f"_Test PDA Disabled {uid}",
            department="AMBAR - KTA",
            enabled=0,
        )
        emp_no_stock_role = self._ensure_test_pda_operator(
            email=f"pda_op_norole_{uid}@example.com",
            first_name=f"_Test PDA NoRole {uid}",
            department="AMBAR - KTA",
            roles=["Employee"],
        )
        emp_inactive = self._ensure_test_pda_operator(
            email=f"pda_op_inactive_{uid}@example.com",
            first_name=f"_Test PDA Inactive {uid}",
            department="AMBAR - KTA",
            status="Left",
        )

        operators = get_pda_operators()
        by_name = {row["name"]: row for row in operators}

        self.assertIn(pda_emp, by_name)
        self.assertTrue(by_name[pda_emp]["has_pin"])
        self.assertEqual(
            by_name[pda_emp]["user_id"], f"pda_other_dept_{uid}@example.com"
        )

        self.assertIn(emp_sevk, by_name)
        self.assertFalse(by_name[emp_sevk]["has_pin"])
        expected_sevk_dept = frappe.db.get_value("Employee", emp_sevk, "department")
        self.assertEqual(by_name[emp_sevk]["department"], expected_sevk_dept)
        self.assertTrue((expected_sevk_dept or "").startswith("Sevk"))

        self.assertNotIn(office_emp, by_name)
        self.assertNotIn(emp_no_user, by_name)
        self.assertNotIn(emp_disabled_user, by_name)
        self.assertNotIn(emp_no_stock_role, by_name)
        self.assertNotIn(emp_inactive, by_name)

        device_token = issue_pda_device_token("pda-role-menu-device")
        self._set_request_with_cookie(token=device_token)
        frappe.set_user("Guest")

        with self.assertRaises(frappe.ValidationError):
            verify_pda_pin(office_emp, "4829")

        res = verify_pda_pin(pda_emp, "4829")
        self.assertTrue(res["ok"])
        self.assertEqual([c["key"] for c in res["menu_categories"]], ["stock"])
        self.assertEqual(
            [item["key"] for item in res["menu_categories"][0]["items"]],
            ["picking", "split", "merge", "transfer", "lookup"],
        )
        self.assertEqual(len(res["menu_categories"][0]["items"]), 5)
        self.assertIn("open_picking_count", res)

    def test_pure_website_user_executes_picking_split_transfer_lookup_end_to_end(self):
        from erpnextkta.kta_stock.line_replenishment_service import (
            complete_line_replenishment_picking,
        )
        from erpnextkta.kta_stock.page.line_replenishment_picking.line_replenishment_picking import (
            get_open_replenishment_orders,
            get_replenishment_order_details,
            resolve_scanned_barcode,
        )
        from erpnextkta.kta_stock.services.pda_service import (
            pda_material_transfer,
            pda_package_merge,
            pda_package_split,
            pda_scan_box,
            pda_stock_lookup,
        )

        uid = frappe.generate_hash("", 5)
        company, _, wh_a, _, wh_b, wh_b_label = self._ensure_pda_test_warehouses(
            f"e2e_{uid}"
        )
        item_pick = self._ensure_pda_batch_item(f"_TEST-PDA-E2E-PICK-{uid}")
        item_box = self._ensure_pda_batch_item(f"_TEST-PDA-E2E-BOX-{uid}")

        pure_user = f"pda_pure_e2e_{uid}@example.com"
        self._ensure_test_pda_operator(
            email=pure_user,
            first_name=f"_Test Pure PDA {uid}",
            department=f"_Test Saha {uid}",
            pin="2468",
            roles=[PDA_ROLE_STOCK_USER],
            user_type="Website User",
        )
        self.assertEqual(
            frappe.db.get_value("User", pure_user, "user_type"), "Website User"
        )
        self.assertNotIn("Employee", frappe.get_roles(pure_user))
        self.assertNotIn("Stock User", frappe.get_roles(pure_user))

        office_user = f"pda_office_e2e_{uid}@example.com"
        self._ensure_test_pda_operator(
            email=office_user,
            first_name=f"_Test Office PDA {uid}",
            department="AMBAR - KTA",
            pin="1357",
            roles=["Stock User"],
        )

        pick_batch = f"K{frappe.generate_hash('', 6).upper()}0001"
        self._ensure_batch(pick_batch, item_pick)
        self._receive_batch_stock(item_pick, wh_a, pick_batch, 12.0, company=company)

        lro = frappe.get_doc(
            {
                "doctype": "KTA Line Replenishment Order",
                "target_warehouse": wh_b,
                "company": company,
                "items": [
                    {
                        "item_code": item_pick,
                        "deficit_qty": 12.0,
                        "suggested_source_warehouse": wh_a,
                        "suggested_batch_no": pick_batch,
                        "uom": "Nos",
                    }
                ],
            }
        )
        lro.flags.ignore_mandatory = True
        lro.insert(ignore_permissions=True)

        box_batch = f"B{frappe.generate_hash('', 6).upper()}0001"
        self._ensure_batch(box_batch, item_box)
        self._receive_batch_stock(item_box, wh_a, box_batch, 100.0, company=company)
        self._create_box_label(item_box, box_batch, 100.0, wh_a)

        # 1) Guest with device cookie receives empty menu_categories
        device_token = issue_pda_device_token(f"pda-e2e-dev-{uid}")
        self._set_request_with_cookie(token=device_token)
        frappe.set_user("Guest")
        guest_boot = get_pda_boot_data()
        self.assertEqual(guest_boot["menu_categories"], [])

        # 2) Pure Website User runs all 5 screens end-to-end with own SE owner
        frappe.set_user(pure_user)
        user_boot = get_pda_boot_data()
        self.assertEqual([c["key"] for c in user_boot["menu_categories"]], ["stock"])
        self.assertEqual(len(user_boot["menu_categories"][0]["items"]), 5)
        self.assertIn(
            "merge", [item["key"] for item in user_boot["menu_categories"][0]["items"]]
        )
        self.assertNotIn("allowed_roles", user_boot["menu_categories"][0])

        open_orders = get_open_replenishment_orders()
        self.assertTrue(any(o["name"] == lro.name for o in open_orders))
        details = get_replenishment_order_details(lro.name)
        self.assertEqual(details["name"], lro.name)
        resolved = resolve_scanned_barcode(pick_batch)
        self.assertEqual(resolved["item_code"], item_pick)

        pick_se_name = complete_line_replenishment_picking(lro.name)
        self.assertEqual(
            frappe.db.get_value("Stock Entry", pick_se_name, "owner"), pure_user
        )

        scan_res = pda_scan_box(box_batch)
        self.assertEqual(scan_res["batch_no"], box_batch)

        with patch(
            "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
            return_value=MagicMock(),
        ):
            split_res = pda_package_split(
                item_code=item_box,
                source_warehouse=wh_a,
                source_batch=box_batch,
                split_qtys=[30.0],
                reprint_source_label=0,
            )
        self.assertEqual(
            frappe.db.get_value("Stock Entry", split_res["stock_entry"], "owner"),
            pure_user,
        )
        new_batch = split_res["created_batches"][0]["batch_no"]

        xfer_res = pda_material_transfer(
            item_code=item_box,
            batch_no=new_batch,
            source_warehouse=wh_a,
            target_warehouse_barcode=wh_b_label,
        )
        self.assertEqual(xfer_res["owner"], pure_user)
        self.assertEqual(
            frappe.db.get_value("Stock Entry", xfer_res["stock_entry"], "owner"),
            pure_user,
        )

        lookup_res = pda_stock_lookup(new_batch)
        self.assertEqual(lookup_res["kind"], "batch")
        self.assertEqual(lookup_res["balances"], [{"warehouse": wh_b, "qty": 30.0}])

        with patch(
            "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
            return_value=MagicMock(),
        ):
            merge_res = pda_package_merge(
                source_boxes=[
                    {"batch_no": box_batch, "warehouse": wh_a},
                    {"batch_no": new_batch, "warehouse": wh_b},
                ],
                target_warehouse_barcode=wh_b_label,
                allow_mixed_lots=0,
            )
        self.assertTrue(merge_res["ok"])
        self.assertEqual(flt(merge_res["total_qty"]), 100.0)
        self.assertEqual(
            frappe.db.get_value("Stock Entry", merge_res["stock_entry"], "owner"),
            pure_user,
        )

        # 3) Plain office user holding only Stock User is rejected on PDA RPCs
        frappe.set_user(office_user)
        with self.assertRaises(frappe.PermissionError):
            pda_scan_box(box_batch)
        with self.assertRaises(frappe.PermissionError):
            pda_stock_lookup(box_batch)

    def test_verify_pda_pin_switches_frappe_session_and_returns_csrf(self):
        emp_name = self._ensure_test_pda_operator(
            email="pda_op_login@example.com",
            first_name="_Test PDA Login",
            department="AMBAR - KTA",
            pin="4829",
        )
        emp_doc = frappe.get_doc("Employee", emp_name)
        device_token = issue_pda_device_token("pda-login-device")
        self._set_request_with_cookie(token=device_token)
        frappe.set_user("Guest")

        self.assertTrue(has_valid_pda_device_cookie())

        res = verify_pda_pin(emp_name, "4829")
        self.assertTrue(res["ok"])
        self.assertEqual(res["user"], emp_doc.user_id)
        self.assertEqual(res["employee"], emp_name)
        self.assertEqual(res["employee_name"], emp_doc.employee_name)
        self.assertTrue(res.get("csrf_token"))
        self.assertEqual(frappe.session.user, emp_doc.user_id)
        self.assertIn(PDA_DEVICE_COOKIE, frappe.local.cookie_manager.cookies)

        boot = get_pda_boot_data()
        self.assertFalse(boot["is_locked"])
        self.assertEqual(boot["current_user"], emp_doc.user_id)
        self.assertEqual(boot["active_operator"]["name"], emp_name)
        self.assertTrue(boot["device_authorized"])
        self.assertEqual(boot["inactivity_timeout_sec"], PDA_INACTIVITY_TIMEOUT_SEC)
        self.assertIsInstance(boot["operators"], list)
        self.assertIsInstance(boot["open_picking_count"], int)

    def test_verify_pda_pin_rate_limits_after_five_failures_and_rejects_missing_pin(
        self,
    ):
        emp_no_pin = self._ensure_test_pda_operator(
            email="pda_op_nopin@example.com",
            first_name="_Test PDA NoPin",
            pin=None,
        )
        emp_with_pin = self._ensure_test_pda_operator(
            email="pda_op_ratelimit@example.com",
            first_name="_Test PDA RateLimit",
            pin="7391",
        )

        device_token = issue_pda_device_token("pda-ratelimit-device")
        self._set_request_with_cookie(token=device_token)
        frappe.set_user("Guest")

        with self.assertRaises(frappe.ValidationError):
            verify_pda_pin(emp_no_pin, "1234")

        for bad_pin in ("", "12", "12345", "12ab"):
            with self.assertRaises(frappe.ValidationError):
                verify_pda_pin(emp_with_pin, bad_pin)

        for _attempt in range(5):
            with self.assertRaises(frappe.ValidationError):
                verify_pda_pin(emp_with_pin, "0000")

        self.assertEqual(
            cint(
                frappe.cache().get_value(f"pda_pin_fail:{emp_with_pin}", expires=True)
            ),
            5,
        )

        # 6th attempt even with correct PIN must be blocked by lockout
        with self.assertRaises(frappe.ValidationError):
            verify_pda_pin(emp_with_pin, "7391")

        self.assertEqual(frappe.session.user, "Guest")

    def test_pda_handover_logout_ends_user_session_and_preserves_device_flow(self):
        emp_name = self._ensure_test_pda_operator(
            email="pda_op_handover@example.com",
            first_name="_Test PDA Handover",
            pin="6248",
        )
        device_token = issue_pda_device_token("pda-handover-device")
        self._set_request_with_cookie(token=device_token)
        frappe.set_user("Guest")

        login_res = verify_pda_pin(emp_name, "6248")
        old_csrf = login_res["csrf_token"]
        self.assertEqual(frappe.session.user, "pda_op_handover@example.com")

        from frappe.auth import LoginManager

        orig_logout = LoginManager.logout
        with patch.object(
            LoginManager,
            "logout",
            autospec=True,
            side_effect=lambda self_obj, *args, **kwargs: orig_logout(
                self_obj, *args, **kwargs
            ),
        ) as spy_logout:
            logout_res = pda_handover_logout()

        spy_logout.assert_called_once()
        self.assertTrue(logout_res["ok"])
        self.assertTrue(logout_res["is_locked"])
        self.assertTrue(logout_res["device_authorized"])
        self.assertTrue(logout_res.get("csrf_token"))
        self.assertNotEqual(logout_res["csrf_token"], old_csrf)
        self.assertEqual(frappe.session.user, "Guest")

        preserved_cookie = frappe.local.cookie_manager.cookies.get(PDA_DEVICE_COOKIE)
        self.assertIsNotNone(preserved_cookie)
        self.assertTrue(preserved_cookie.get("httponly"))
        self.assertNotIn(PDA_DEVICE_COOKIE, frappe.local.cookie_manager.to_delete)

        # Device cookie keeps working after handover logout
        self._set_request_with_cookie(token=preserved_cookie["value"])
        boot = get_pda_boot_data()
        self.assertTrue(boot["is_locked"])
        self.assertTrue(boot["device_authorized"])
        self.assertEqual(boot["current_user"], "Guest")

        relogin_res = verify_pda_pin(emp_name, "6248")
        self.assertTrue(relogin_res["ok"])
        self.assertEqual(frappe.session.user, "pda_op_handover@example.com")

    def test_resolve_warehouse_barcode_exact_and_without_company_suffix_and_rejects_group(
        self,
    ):
        from erpnextkta.kta_stock.services.pda_service import resolve_warehouse_barcode

        uid = frappe.generate_hash("", 5)
        company, group_wh, wh_a, wh_a_label, _, _ = self._ensure_pda_test_warehouses(
            f"res_{uid}"
        )

        exact = resolve_warehouse_barcode(wh_a, company=company)
        self.assertEqual(exact["name"], wh_a)
        self.assertEqual(exact["warehouse_name"], wh_a_label)
        self.assertEqual(exact["company"], company)
        self.assertEqual(exact["is_group"], 0)

        by_label = resolve_warehouse_barcode(wh_a_label, company=company)
        self.assertEqual(by_label["name"], wh_a)

        by_label_no_company = resolve_warehouse_barcode(wh_a_label)
        self.assertEqual(by_label_no_company["name"], wh_a)

        with self.assertRaises(frappe.ValidationError):
            resolve_warehouse_barcode(group_wh, company=company)

        with self.assertRaises(frappe.ValidationError):
            resolve_warehouse_barcode("NON-EXISTENT-WH-BARCODE")

    def _create_sap_test_warehouse(
        self,
        warehouse_name: str,
        company: str,
        parent_warehouse: str | None = None,
        is_group: int = 0,
        disabled: int = 0,
    ) -> str:
        doc = frappe.get_doc(
            {
                "doctype": "Warehouse",
                "warehouse_name": warehouse_name,
                "company": company,
                "parent_warehouse": parent_warehouse,
                "is_group": is_group,
                "disabled": disabled,
            }
        ).insert(ignore_permissions=True)
        return doc.name

    def _ensure_sap_depot_test_tree(self, uid: str) -> dict[str, str]:
        company = self._get_test_company()
        root_wh = frappe.db.get_value(
            "Warehouse",
            {"company": company, "is_group": 1, "parent_warehouse": ["in", ["", None]]},
            "name",
        ) or frappe.db.get_value(
            "Warehouse", {"company": company, "is_group": 1}, "name"
        )

        grp_110 = self._create_sap_test_warehouse(
            f"110 HAMMADDE {uid}", company, root_wh, is_group=1
        )
        grp_w1a = self._create_sap_test_warehouse(
            f"W1A {uid}", company, grp_110, is_group=1
        )
        wh_w1a = self._create_sap_test_warehouse(f"W1A-01-01-{uid}", company, grp_w1a)

        grp_w1f = self._create_sap_test_warehouse(
            f"W1F {uid}", company, grp_110, is_group=1
        )
        wh_w1f_active = self._create_sap_test_warehouse(
            f"W1F-01-01-{uid}", company, grp_w1f
        )
        wh_w1f_disabled = self._create_sap_test_warehouse(
            f"W1F-12-01-{uid}", company, grp_w1f, disabled=1
        )

        grp_170 = self._create_sap_test_warehouse(
            f"170 BİTMİŞ ÜRÜN {uid}", company, root_wh, is_group=1
        )
        wh_170_active = self._create_sap_test_warehouse(
            f"170-W1F-12-01-{uid}", company, grp_170
        )

        grp_1100 = self._create_sap_test_warehouse(
            f"1100 EXTRA {uid}", company, root_wh, is_group=1
        )
        wh_1100_leaf = self._create_sap_test_warehouse(
            f"B1A-01-01-{uid}", company, grp_1100
        )

        return {
            "company": company,
            "wh_w1a": wh_w1a,
            "wh_w1f_active": wh_w1f_active,
            "wh_w1f_disabled": wh_w1f_disabled,
            "wh_170_active": wh_170_active,
            "wh_1100_leaf": wh_1100_leaf,
        }

    def test_resolve_warehouse_barcode_sap_prefix_and_depot_ancestor_validation(self):
        from erpnextkta.kta_stock.services.pda_service import resolve_warehouse_barcode

        uid = frappe.generate_hash("", 5)
        tree = self._ensure_sap_depot_test_tree(uid)
        company = tree["company"]

        res_w1a = resolve_warehouse_barcode(f"110-W1A-01-01-{uid}", company=company)
        self.assertEqual(res_w1a["name"], tree["wh_w1a"])
        self.assertEqual(res_w1a["warehouse_name"], f"W1A-01-01-{uid}")

        res_w1a_norm = resolve_warehouse_barcode(
            f"  110-w1a-01-01-{uid}  ", company=company
        )
        self.assertEqual(res_w1a_norm["name"], tree["wh_w1a"])

        res_w1f = resolve_warehouse_barcode(f"110-W1F-01-01-{uid}", company=company)
        self.assertEqual(res_w1f["name"], tree["wh_w1f_active"])

        res_170 = resolve_warehouse_barcode(f"170-W1F-12-01-{uid}", company=company)
        self.assertEqual(res_170["name"], tree["wh_170_active"])

        with self.assertRaises(frappe.ValidationError) as ctx_disabled:
            resolve_warehouse_barcode(f"110-W1F-12-01-{uid}", company=company)
        self.assertIn(
            frappe._("Depo pasif durumda: {0}").format(tree["wh_w1f_disabled"]),
            str(ctx_disabled.exception),
        )

        with self.assertRaises(frappe.ValidationError) as ctx_wrong_depot:
            resolve_warehouse_barcode(f"170-W1F-01-01-{uid}", company=company)
        self.assertIn(
            frappe._("Depo barkodu bulunamadı: {0}").format(f"170-W1F-01-01-{uid}"),
            str(ctx_wrong_depot.exception),
        )

        with self.assertRaises(frappe.ValidationError) as ctx_boundary:
            resolve_warehouse_barcode(f"110-B1A-01-01-{uid}", company=company)
        self.assertIn(
            frappe._("Depo barkodu bulunamadı: {0}").format(f"110-B1A-01-01-{uid}"),
            str(ctx_boundary.exception),
        )

        with self.assertRaises(frappe.ValidationError) as ctx_unknown:
            resolve_warehouse_barcode(f"110-NON-EXISTENT-{uid}", company=company)
        self.assertIn(
            frappe._("Depo barkodu bulunamadı: {0}").format(f"110-NON-EXISTENT-{uid}"),
            str(ctx_unknown.exception),
        )

    def test_resolve_warehouse_barcode_sap_prefix_disambiguates_same_leaf_across_depots(
        self,
    ):
        from erpnextkta.kta_stock.services.pda_service import resolve_warehouse_barcode

        uid = frappe.generate_hash("", 5)
        company1 = self._get_test_company()
        root1 = frappe.db.get_value(
            "Warehouse",
            {
                "company": company1,
                "is_group": 1,
                "parent_warehouse": ["in", ["", None]],
            },
            "name",
        ) or frappe.db.get_value(
            "Warehouse", {"company": company1, "is_group": 1}, "name"
        )
        grp_110 = self._create_sap_test_warehouse(
            f"110 HAMMADDE {uid}", company1, root1, is_group=1
        )
        wh_110_shared = self._create_sap_test_warehouse(
            f"SHARED-01-{uid}", company1, grp_110
        )

        company2 = f"_Test SAP Co2 {uid}"
        if not frappe.db.exists("Company", company2):
            frappe.get_doc(
                {
                    "doctype": "Company",
                    "company_name": company2,
                    "abbr": f"S{uid.upper()}",
                    "default_currency": "TRY",
                    "country": "Turkey",
                }
            ).insert(ignore_permissions=True)
        root2 = frappe.db.get_value(
            "Warehouse",
            {
                "company": company2,
                "is_group": 1,
                "parent_warehouse": ["in", ["", None]],
            },
            "name",
        ) or frappe.db.get_value(
            "Warehouse", {"company": company2, "is_group": 1}, "name"
        )
        grp_170 = self._create_sap_test_warehouse(
            f"170 BİTMİŞ ÜRÜN {uid}", company2, root2, is_group=1
        )
        wh_170_shared = self._create_sap_test_warehouse(
            f"SHARED-01-{uid}", company2, grp_170
        )

        res_110 = resolve_warehouse_barcode(f"110-SHARED-01-{uid}")
        self.assertEqual(res_110["name"], wh_110_shared)
        self.assertEqual(res_110["company"], company1)

        res_170 = resolve_warehouse_barcode(f"170-SHARED-01-{uid}")
        self.assertEqual(res_170["name"], wh_170_shared)
        self.assertEqual(res_170["company"], company2)

        with self.assertRaises(frappe.ValidationError) as ctx_bad_prefix:
            resolve_warehouse_barcode(f"999-SHARED-01-{uid}")
        self.assertIn(
            frappe._("Depo barkodu bulunamadı: {0}").format(f"999-SHARED-01-{uid}"),
            str(ctx_bad_prefix.exception),
        )

    def test_warehouse_has_prefix_ancestor_parent_chain_fallback_without_nestedset(
        self,
    ):
        from erpnextkta.kta_stock.services.pda_service import (
            _warehouse_has_prefix_ancestor,
        )

        uid = frappe.generate_hash("", 5)
        tree = self._ensure_sap_depot_test_tree(uid)
        wh_meta = frappe.db.get_value(
            "Warehouse",
            tree["wh_w1a"],
            ["name", "warehouse_name", "company", "parent_warehouse"],
            as_dict=True,
        )
        wh_meta.lft = 0
        wh_meta.rgt = 0

        self.assertTrue(_warehouse_has_prefix_ancestor(wh_meta, "110"))
        self.assertFalse(_warehouse_has_prefix_ancestor(wh_meta, "170"))
        self.assertFalse(_warehouse_has_prefix_ancestor(wh_meta, "11"))

    def test_pda_stock_lookup_and_material_transfer_support_sap_prefixed_shelf_barcodes(
        self,
    ):
        from erpnextkta.kta_stock.services.pda_service import (
            pda_material_transfer,
            pda_stock_lookup,
        )

        uid = frappe.generate_hash("", 5)
        tree = self._ensure_sap_depot_test_tree(uid)
        company = tree["company"]
        wh_w1a = tree["wh_w1a"]
        wh_w1f = tree["wh_w1f_active"]

        item_code = self._ensure_pda_batch_item(f"_TEST-PDA-SAP-{uid}")
        std_batch = f"P{frappe.generate_hash('', 6).upper()}0001"
        self._ensure_batch(std_batch, item_code)
        self._receive_batch_stock(item_code, wh_w1a, std_batch, 25.0, company=company)
        lbl = self._create_box_label(item_code, std_batch, 25.0, wh_w1a)

        lookup_res = pda_stock_lookup(f"110-W1A-01-01-{uid}")
        self.assertEqual(lookup_res["kind"], "warehouse")
        self.assertEqual(lookup_res["warehouse"], wh_w1a)
        self.assertTrue(
            any(
                row["item_code"] == item_code and flt(row["actual_qty"]) == 25.0
                for row in lookup_res["items"]
            )
        )

        xfer_res = pda_material_transfer(
            item_code=item_code,
            batch_no=std_batch,
            source_warehouse=wh_w1a,
            target_warehouse_barcode=f"110-W1F-01-01-{uid}",
        )
        self.assertTrue(xfer_res["ok"])
        self.assertEqual(xfer_res["target_warehouse"], wh_w1f)
        self.assertEqual(
            get_batch_ledger_balances(item_code, std_batch),
            [{"warehouse": wh_w1f, "qty": 25.0}],
        )
        lbl.reload()
        self.assertEqual(lbl.target_warehouse, wh_w1f)

    def test_pda_scan_box_returns_balances_and_rejects_empty_batch(self):
        from erpnextkta.kta_stock.services.pda_service import pda_scan_box

        uid = frappe.generate_hash("", 5)
        company, _, wh_a, _, _, _ = self._ensure_pda_test_warehouses(f"scan_{uid}")
        item_code = self._ensure_pda_batch_item(f"_TEST-PDA-SCAN-{uid}")
        lot_prefix = f"S{frappe.generate_hash('', 6).upper()}"
        full_batch = f"{lot_prefix}0001"
        empty_batch = f"{lot_prefix}0002"
        sut_code = f"SUT-{full_batch}"

        self._ensure_batch(full_batch, item_code, expiry_date="2028-01-15")
        self._ensure_batch(empty_batch, item_code)
        self._receive_batch_stock(item_code, wh_a, full_batch, 45.0, company=company)
        lbl = self._create_box_label(
            item_code, full_batch, 45.0, wh_a, sut_barcode=sut_code
        )
        self._create_box_label(item_code, empty_batch, 10.0, wh_a)

        res_by_sut = pda_scan_box(sut_code)
        self.assertEqual(res_by_sut["item_code"], item_code)
        self.assertTrue(res_by_sut["item_name"])
        self.assertEqual(res_by_sut["stock_uom"], "Nos")
        self.assertEqual(res_by_sut["batch_no"], full_batch)
        self.assertTrue(res_by_sut["is_standard_batch"])
        self.assertEqual(res_by_sut["label_name"], str(lbl.name))
        self.assertEqual(res_by_sut["label_type"], "Depo Giriş Etiketi")
        self.assertEqual(res_by_sut["expiry_date"], "2028-01-15")
        self.assertEqual(flt(res_by_sut["total_qty"]), 45.0)
        self.assertEqual(res_by_sut["balances"], [{"warehouse": wh_a, "qty": 45.0}])

        res_by_batch = pda_scan_box(full_batch)
        self.assertEqual(res_by_batch["batch_no"], full_batch)
        self.assertEqual(res_by_batch["label_name"], str(lbl.name))
        self.assertEqual(res_by_batch["balances"], [{"warehouse": wh_a, "qty": 45.0}])

        with self.assertRaises(frappe.ValidationError):
            pda_scan_box(empty_batch)

    def test_pda_package_split_prints_targets_once_and_reprints_remaining_source_selectively(
        self,
    ):
        from erpnextkta.kta_stock.services.pda_service import pda_package_split

        uid = frappe.generate_hash("", 5)
        company, _, wh_a, _, _, _ = self._ensure_pda_test_warehouses(f"split_{uid}")
        item_code = self._ensure_pda_batch_item(f"_TEST-PDA-SPLIT-{uid}")
        self._ensure_test_pda_operator(
            email="pda_op_split@example.com",
            first_name="_Test PDA Split Op",
            department="AMBAR - KTA",
            pin="1122",
        )
        frappe.set_user("pda_op_split@example.com")

        lot_prefix = f"P{frappe.generate_hash('', 6).upper()}"
        src_batch = f"{lot_prefix}0001"
        self._ensure_batch(src_batch, item_code)
        self._receive_batch_stock(item_code, wh_a, src_batch, 100.0, company=company)
        src_lbl = self._create_box_label(item_code, src_batch, 100.0, wh_a)

        mock_printer = MagicMock()
        enqueue_calls = []
        from erpnextkta.kta_stock.label_manager import (
            enqueue_print_labels_by_names as real_enqueue,
        )

        def _spy_enqueue(label_names, user=None):
            enqueue_calls.append((list(label_names), user))
            return real_enqueue(label_names, user=user)

        with (
            patch(
                "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
                return_value=mock_printer,
            ),
            patch(
                "erpnextkta.kta_stock.services.pda_service.enqueue_print_labels_by_names",
                side_effect=_spy_enqueue,
            ),
        ):
            # 1) Partial split [30] with reprint_source_label=1 -> remaining 70 reprints source label ONCE, never targets
            res1 = pda_package_split(
                item_code=item_code,
                source_warehouse=wh_a,
                source_batch=src_batch,
                split_qtys=[30],
                reprint_source_label=1,
            )

        self.assertTrue(res1["ok"])
        self.assertEqual(flt(res1["remaining_qty"]), 70.0)
        self.assertTrue(res1["source_label_reprinted"])
        self.assertEqual(res1["queued_reprint_count"], 1)
        self.assertEqual(len(enqueue_calls), 1)
        self.assertEqual(
            enqueue_calls[0], ([str(src_lbl.name)], "pda_op_split@example.com")
        )
        se1 = frappe.get_doc("Stock Entry", res1["stock_entry"])
        self.assertEqual(se1.stock_entry_type, "Package Split")
        self.assertEqual(se1.owner, "pda_op_split@example.com")
        # Target batch printed via on_submit + source label reprinted via enqueue = 2 send_batch calls
        self.assertEqual(mock_printer.send_batch.call_count, 2)

        # 2) Partial split [20] with reprint_source_label=0 -> 0 calls to enqueue_print_labels_by_names
        enqueue_calls.clear()
        with (
            patch(
                "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
                return_value=mock_printer,
            ),
            patch(
                "erpnextkta.kta_stock.services.pda_service.enqueue_print_labels_by_names",
                side_effect=_spy_enqueue,
            ),
        ):
            res2 = pda_package_split(
                item_code=item_code,
                source_warehouse=wh_a,
                source_batch=src_batch,
                split_qtys=[20],
                reprint_source_label=0,
            )

        self.assertEqual(flt(res2["remaining_qty"]), 50.0)
        self.assertFalse(res2["source_label_reprinted"])
        self.assertEqual(res2["queued_reprint_count"], 0)
        self.assertEqual(len(enqueue_calls), 0)

        # 3) Full consumption of LEGACY batch [100] with reprint_source_label=1 -> remaining 0 => 0 calls
        legacy_batch = f"LEGACY-PDA-{frappe.generate_hash('', 5).upper()}"
        self._ensure_batch(legacy_batch, item_code)
        self._receive_batch_stock(item_code, wh_a, legacy_batch, 100.0, company=company)
        self._create_box_label(item_code, legacy_batch, 100.0, wh_a)
        enqueue_calls.clear()

        with (
            patch(
                "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
                return_value=mock_printer,
            ),
            patch(
                "erpnextkta.kta_stock.services.pda_service.enqueue_print_labels_by_names",
                side_effect=_spy_enqueue,
            ),
        ):
            res3 = pda_package_split(
                item_code=item_code,
                source_warehouse=wh_a,
                source_batch=legacy_batch,
                split_qtys=[100],
                reprint_source_label=1,
            )

        self.assertEqual(flt(res3["remaining_qty"]), 0.0)
        self.assertFalse(res3["source_label_reprinted"])
        self.assertEqual(res3["queued_reprint_count"], 0)
        self.assertEqual(len(enqueue_calls), 0)

    def test_pda_package_split_rejects_noop_single_full_qty_on_standard_batch(self):
        from erpnextkta.kta_stock.services.pda_service import pda_package_split

        uid = frappe.generate_hash("", 5)
        company, _, wh_a, _, _, _ = self._ensure_pda_test_warehouses(f"noop_{uid}")
        item_code = self._ensure_pda_batch_item(f"_TEST-PDA-NOOP-{uid}")
        std_batch = f"N{frappe.generate_hash('', 6).upper()}0001"
        self._ensure_batch(std_batch, item_code)
        self._receive_batch_stock(item_code, wh_a, std_batch, 50.0, company=company)

        with self.assertRaises(frappe.ValidationError):
            pda_package_split(
                item_code=item_code,
                source_warehouse=wh_a,
                source_batch=std_batch,
                split_qtys=[50.0],
            )

    def test_pda_material_transfer_moves_full_box_syncs_label_and_records_session_owner(
        self,
    ):
        from erpnextkta.kta_stock.services.pda_service import pda_material_transfer

        uid = frappe.generate_hash("", 5)
        company, _, wh_a, _, wh_b, wh_b_label = self._ensure_pda_test_warehouses(
            f"xfer_{uid}"
        )
        item_code = self._ensure_pda_batch_item(f"_TEST-PDA-XFER-{uid}")
        emp_name = self._ensure_test_pda_operator(
            email="pda_op_xfer@example.com",
            first_name="_Test PDA Xfer Op",
            department="Sevk",
            pin="3344",
        )
        device_token = issue_pda_device_token("pda-xfer-device")
        self._set_request_with_cookie(token=device_token)
        frappe.set_user("Guest")
        verify_pda_pin(emp_name, "3344")
        self.assertEqual(frappe.session.user, "pda_op_xfer@example.com")

        std_batch = f"X{frappe.generate_hash('', 6).upper()}0001"
        self._ensure_batch(std_batch, item_code)
        self._receive_batch_stock(item_code, wh_a, std_batch, 80.0, company=company)
        lbl = self._create_box_label(item_code, std_batch, 80.0, wh_a)

        res = pda_material_transfer(
            item_code=item_code,
            batch_no=std_batch,
            source_warehouse=wh_a,
            target_warehouse_barcode=wh_b_label,
        )

        self.assertTrue(res["ok"])
        self.assertEqual(res["owner"], "pda_op_xfer@example.com")
        self.assertEqual(flt(res["qty"]), 80.0)
        self.assertEqual(res["source_warehouse"], wh_a)
        self.assertEqual(res["target_warehouse"], wh_b)

        se = frappe.get_doc("Stock Entry", res["stock_entry"])
        self.assertEqual(se.docstatus, 1)
        self.assertEqual(se.stock_entry_type, "Material Transfer")
        self.assertEqual(se.owner, "pda_op_xfer@example.com")

        self.assertEqual(
            get_batch_ledger_balances(item_code, std_batch),
            [{"warehouse": wh_b, "qty": 80.0}],
        )
        lbl.reload()
        self.assertEqual(lbl.target_warehouse, wh_b)
        self.assertEqual(flt(lbl.qty), 80.0)

    def test_pda_material_transfer_rejects_partial_qty_same_wh_and_draft_reco_lock(
        self,
    ):
        from erpnextkta.kta_stock.services.pda_service import pda_material_transfer

        uid = frappe.generate_hash("", 5)
        company, _, wh_a, wh_a_label, wh_b, wh_b_label = (
            self._ensure_pda_test_warehouses(f"xferrej_{uid}")
        )
        item_code = self._ensure_pda_batch_item(f"_TEST-PDA-XFER-REJ-{uid}")
        self._ensure_test_pda_operator(
            email="pda_op_xfer_rej@example.com",
            first_name="_Test PDA Xfer Rej",
            department="AMBAR - KTA",
            pin="5566",
            roles=[PDA_ROLE_STOCK_USER],
        )
        frappe.set_user("pda_op_xfer_rej@example.com")

        std_batch = f"R{frappe.generate_hash('', 6).upper()}0001"
        self._ensure_batch(std_batch, item_code)
        self._receive_batch_stock(item_code, wh_a, std_batch, 60.0, company=company)
        sle_before = frappe.db.count("Stock Ledger Entry", {"item_code": item_code})

        with self.assertRaises(frappe.ValidationError):
            pda_material_transfer(
                item_code=item_code,
                batch_no=std_batch,
                source_warehouse=wh_a,
                target_warehouse_barcode=wh_b_label,
                qty=25.0,
            )

        with self.assertRaises(frappe.ValidationError):
            pda_material_transfer(
                item_code=item_code,
                batch_no=std_batch,
                source_warehouse=wh_a,
                target_warehouse_barcode=wh_a_label,
            )

        reco_name = None
        try:
            reco = frappe.get_doc(
                {
                    "doctype": "Stock Reconciliation",
                    "company": company,
                    "purpose": "Stock Reconciliation",
                    "posting_date": nowdate(),
                    "posting_time": nowtime(),
                    "set_warehouse": wh_b,
                    "items": [
                        {
                            "item_code": item_code,
                            "warehouse": wh_b,
                            "batch_no": std_batch,
                            "qty": 1.0,
                            "valuation_rate": 10.0,
                            "use_serial_batch_fields": 1,
                        }
                    ],
                }
            ).insert(ignore_permissions=True)
            reco_name = reco.name

            with self.assertRaises(frappe.ValidationError):
                pda_material_transfer(
                    item_code=item_code,
                    batch_no=std_batch,
                    source_warehouse=wh_a,
                    target_warehouse_barcode=wh_b_label,
                )
        finally:
            if reco_name and frappe.db.exists("Stock Reconciliation", reco_name):
                frappe.set_user("Administrator")
                frappe.delete_doc(
                    "Stock Reconciliation", reco_name, force=1, ignore_permissions=True
                )

        self.assertEqual(
            frappe.db.count("Stock Ledger Entry", {"item_code": item_code}), sle_before
        )

    def test_pda_stock_lookup_resolves_batch_warehouse_and_item(self):
        from erpnextkta.kta_stock.services.pda_service import pda_stock_lookup

        uid = frappe.generate_hash("", 5)
        company, _, wh_a, wh_a_label, _, _ = self._ensure_pda_test_warehouses(
            f"lkp_{uid}"
        )
        item_barcode = f"EAN-{frappe.generate_hash('', 6).upper()}"
        item_code = self._ensure_pda_batch_item(
            f"_TEST-PDA-LOOKUP-{uid}", barcode=item_barcode
        )
        std_batch = f"L{frappe.generate_hash('', 6).upper()}0001"
        self._ensure_batch(std_batch, item_code)
        self._receive_batch_stock(item_code, wh_a, std_batch, 33.0, company=company)
        self._create_box_label(item_code, std_batch, 33.0, wh_a)

        res_batch = pda_stock_lookup(std_batch)
        self.assertEqual(res_batch["kind"], "batch")
        self.assertEqual(res_batch["item_code"], item_code)
        self.assertEqual(res_batch["batch_no"], std_batch)
        self.assertEqual(flt(res_batch["total_qty"]), 33.0)
        self.assertEqual(res_batch["balances"], [{"warehouse": wh_a, "qty": 33.0}])

        res_wh = pda_stock_lookup(wh_a_label)
        self.assertEqual(res_wh["kind"], "warehouse")
        self.assertEqual(res_wh["warehouse"], wh_a)
        self.assertTrue(
            any(
                row["item_code"] == item_code and flt(row["actual_qty"]) == 33.0
                for row in res_wh["items"]
            )
        )

        res_item = pda_stock_lookup(item_barcode)
        self.assertEqual(res_item["kind"], "item")
        self.assertEqual(res_item["item_code"], item_code)
        self.assertEqual(flt(res_item["total_qty"]), 33.0)
        self.assertTrue(
            any(
                b["batch_no"] == std_batch and flt(b["qty"]) == 33.0
                for b in res_item["batches"]
            )
        )

        with self.assertRaises(frappe.ValidationError):
            pda_stock_lookup("UNKNOWN-BARCODE-XYZ")

    def test_pda_package_merge_validates_duplicates_items_qi_lock_and_prints_once(self):
        from erpnextkta.kta_stock.services.pda_service import (
            pda_package_merge,
            pda_scan_box,
        )

        uid = frappe.generate_hash("", 5).upper()
        company, _, wh_a, _, wh_b, wh_b_label = self._ensure_pda_test_warehouses(
            f"mrg_{uid}"
        )
        item_a = self._ensure_pda_batch_item(f"_TEST-PDA-MRG-A-{uid}")
        item_b = self._ensure_pda_batch_item(f"_TEST-PDA-MRG-B-{uid}")

        pure_user = f"pda_mrg_pure_{uid.lower()}@example.com"
        self._ensure_test_pda_operator(
            email=pure_user,
            first_name=f"_Test PDA Merge Pure {uid}",
            department=f"_Test Merge Dept {uid}",
            pin="1478",
            roles=[PDA_ROLE_STOCK_USER],
            user_type="Website User",
        )
        office_user = f"pda_mrg_office_{uid.lower()}@example.com"
        self._ensure_test_pda_operator(
            email=office_user,
            first_name=f"_Test PDA Merge Office {uid}",
            department="AMBAR - KTA",
            pin="2580",
            roles=["Stock User"],
        )

        lot_a = f"M{frappe.generate_hash('', 6).upper()}"
        b1 = f"{lot_a}0001"
        b2 = f"{lot_a}0002"
        other_item_batch = f"O{frappe.generate_hash('', 6).upper()}0001"

        self._ensure_batch(b1, item_a, expiry_date="2028-10-01")
        self._ensure_batch(b2, item_a, expiry_date="2028-04-01")
        self._ensure_batch(other_item_batch, item_b)

        self._receive_batch_stock(item_a, wh_a, b1, 40.0, company=company)
        self._receive_batch_stock(item_a, wh_a, b2, 60.0, company=company)
        self._receive_batch_stock(item_b, wh_a, other_item_batch, 20.0, company=company)
        lbl1 = self._create_box_label(item_a, b1, 40.0, wh_a)
        lbl2 = self._create_box_label(item_a, b2, 60.0, wh_a)

        frappe.set_user(pure_user)
        scan1 = pda_scan_box(b1)
        self.assertEqual(scan1["base_lot"], lot_a)

        # 1) < 2 boxes
        with self.assertRaises(frappe.ValidationError):
            pda_package_merge([{"batch_no": b1, "warehouse": wh_a}])

        # 2) Duplicate (batch_no, warehouse)
        with self.assertRaises(frappe.ValidationError):
            pda_package_merge(
                [
                    {"batch_no": b1, "warehouse": wh_a},
                    {"batch_no": b1, "warehouse": wh_a},
                ]
            )

        # 3) Partial qty != available balance
        with self.assertRaises(frappe.ValidationError):
            pda_package_merge(
                [
                    {"batch_no": b1, "warehouse": wh_a, "qty": 15.0},
                    {"batch_no": b2, "warehouse": wh_a},
                ]
            )

        # 4) Different item_code batches
        with self.assertRaises(frappe.ValidationError):
            pda_package_merge(
                [
                    {"batch_no": b1, "warehouse": wh_a},
                    {"batch_no": other_item_batch, "warehouse": wh_a},
                ],
                allow_mixed_lots=1,
            )

        # 5) Unapproved Quality Inspection blocks merge on PR-linked QI-required item
        frappe.set_user("Administrator")
        qi_item = f"_TEST-PDA-MRG-QI-{uid}"
        self._ensure_pda_batch_item(qi_item)
        frappe.db.set_value("Item", qi_item, "inspection_required_before_purchase", 1)
        pr_name = f"MAT-PRE-MRG-{uid}"
        qi_lot = f"Q{frappe.generate_hash('', 6).upper()}"
        qb1 = f"{qi_lot}0001"
        qb2 = f"{qi_lot}0002"
        self._ensure_batch(
            qb1, qi_item, reference_doctype="Purchase Receipt", reference_name=pr_name
        )
        self._ensure_batch(
            qb2, qi_item, reference_doctype="Purchase Receipt", reference_name=pr_name
        )
        self._receive_batch_stock(qi_item, wh_a, qb1, 10.0, company=company)
        self._receive_batch_stock(qi_item, wh_a, qb2, 10.0, company=company)
        frappe.set_user(pure_user)
        with self.assertRaises(frappe.ValidationError):
            pda_package_merge(
                [
                    {"batch_no": qb1, "warehouse": wh_a},
                    {"batch_no": qb2, "warehouse": wh_a},
                ]
            )

        # 6) Draft Stock Reconciliation lock blocks merge into locked target warehouse
        frappe.set_user("Administrator")
        reco_name = None
        try:
            reco = frappe.get_doc(
                {
                    "doctype": "Stock Reconciliation",
                    "company": company,
                    "purpose": "Stock Reconciliation",
                    "posting_date": nowdate(),
                    "posting_time": nowtime(),
                    "set_warehouse": wh_b,
                    "items": [
                        {
                            "item_code": item_a,
                            "warehouse": wh_b,
                            "batch_no": b1,
                            "qty": 1.0,
                            "valuation_rate": 10.0,
                            "use_serial_batch_fields": 1,
                        }
                    ],
                }
            ).insert(ignore_permissions=True)
            reco_name = reco.name
            frappe.set_user(pure_user)
            with self.assertRaises(frappe.ValidationError):
                pda_package_merge(
                    [
                        {"batch_no": b1, "warehouse": wh_a},
                        {"batch_no": b2, "warehouse": wh_a},
                    ],
                    target_warehouse_barcode=wh_b_label,
                )
        finally:
            if reco_name and frappe.db.exists("Stock Reconciliation", reco_name):
                frappe.set_user("Administrator")
                frappe.delete_doc(
                    "Stock Reconciliation", reco_name, force=1, ignore_permissions=True
                )

        # 7) Office Stock User is rejected with PermissionError
        frappe.set_user(office_user)
        with self.assertRaises(frappe.PermissionError):
            pda_package_merge(
                [
                    {"batch_no": b1, "warehouse": wh_a},
                    {"batch_no": b2, "warehouse": wh_a},
                ]
            )

        # 8) Pure Website User merges cleanly into wh_b, prints ONCE, deletes source labels
        frappe.set_user(pure_user)
        mock_printer = MagicMock()
        with patch(
            "kta_system_utils.kta_zebra_utils.printer_manager.ZebraPrinterManager.get_printer_for_user",
            return_value=mock_printer,
        ):
            res = pda_package_merge(
                source_boxes=[
                    {"batch_no": b1, "warehouse": wh_a},
                    {"batch_no": b2, "warehouse": wh_a},
                ],
                target_warehouse_barcode=wh_b_label,
                allow_mixed_lots=0,
            )

        self.assertTrue(res["ok"])
        self.assertEqual(res["owner"], pure_user)
        self.assertEqual(res["target_warehouse"], wh_b)
        self.assertEqual(res["target_batch"], f"{lot_a}0003")
        self.assertEqual(flt(res["total_qty"]), 100.0)
        self.assertFalse(res["is_mixed_lot"])
        self.assertTrue(res["target_label_name"])
        self.assertEqual(mock_printer.send_batch.call_count, 1)
        self.assertEqual(
            frappe.db.get_value("Stock Entry", res["stock_entry"], "owner"), pure_user
        )
        self.assertFalse(frappe.db.exists("KTA Stock Label", lbl1.name))
        self.assertFalse(frappe.db.exists("KTA Stock Label", lbl2.name))
