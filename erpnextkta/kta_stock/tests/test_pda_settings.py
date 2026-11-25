from unittest.mock import patch

import frappe
from frappe.utils import cint
from frappe.utils.password import (
    get_decrypted_password,
    remove_encrypted_password,
    set_encrypted_password,
    update_password,
)
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from erpnextkta.kta_stock.services.pda_service import (
    PDA_DEVICE_COOKIE,
    issue_pda_device_token,
    pda_handover_logout,
    verify_pda_pin,
)
from erpnextkta.kta_stock.setup import (
    PDA_ROLE_STOCK_USER,
    setup,
    setup_pda_custom_fields,
)
from erpnextkta.tests.test_utils import KTABaseTestCase, create_test_company

_MISSING = object()


class TestPdaSettings(KTABaseTestCase):
    def setUp(self):
        super().setUp()
        self._saved_local = {
            attr: getattr(frappe.local, attr, _MISSING)
            for attr in (
                "request",
                "request_ip",
                "cookie_manager",
                "login_manager",
                "lang",
            )
        }
        frappe.cache().delete_keys("pda_pin_fail:")
        frappe.cache().delete_keys("pda_pwd_fail:")
        setup()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.cache().delete_keys("pda_pin_fail:")
        frappe.cache().delete_keys("pda_pwd_fail:")
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

    def _ensure_role(self, role_name: str, desk_access: int = 1) -> None:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc(
                {
                    "doctype": "Role",
                    "role_name": role_name,
                    "desk_access": cint(desk_access),
                }
            ).insert(ignore_permissions=True)

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
            {"doctype": "Department", "department_name": department_name}
        )
        dept.company = None
        dept.flags.ignore_mandatory = True
        dept.flags.ignore_links = True
        dept.insert(ignore_permissions=True)
        frappe.db.set_value("Department", dept.name, "company", company)
        return dept.name

    def _ensure_user(
        self,
        email: str,
        first_name: str,
        roles: list[str],
        user_type: str | None = None,
        password: str | None = None,
        language: str = "tr",
    ) -> str:
        for role_name in roles:
            self._ensure_role(
                role_name, desk_access=0 if role_name.startswith("KTA PDA ") else 1
            )

        if not frappe.db.exists("User", email):
            payload = {
                "doctype": "User",
                "email": email,
                "first_name": first_name,
                "enabled": 1,
                "language": language,
                "send_welcome_email": 0,
                "roles": [{"role": r} for r in roles],
            }
            if user_type is not None:
                payload["user_type"] = user_type
            user = frappe.get_doc(payload).insert(ignore_permissions=True)
        else:
            user = frappe.get_doc("User", email)
            user.enabled = 1
            user.language = language
            if user_type is not None:
                user.user_type = user_type
            user.set("roles", [{"role": r} for r in roles])
            user.save(ignore_permissions=True)

        if password:
            update_password(user.name, password)
        frappe.clear_cache(user=user.name)
        return user.name

    def _ensure_pda_operator(
        self,
        email: str,
        first_name: str,
        department: str,
        roles: list[str] | None = None,
        pin: str | None = None,
        user_type: str | None = None,
        password: str | None = None,
        language: str = "tr",
    ) -> tuple[str, str]:
        if not frappe.db.exists("Custom Field", "Employee-custom_pda_pin"):
            setup_pda_custom_fields()

        company = self._get_test_company()
        resolved_dept = self._ensure_department(department, company)
        if not frappe.db.exists("Gender", "Male"):
            frappe.get_doc({"doctype": "Gender", "gender": "Male"}).insert(
                ignore_permissions=True
            )

        target_roles = [PDA_ROLE_STOCK_USER] if roles is None else list(roles)
        user_id = self._ensure_user(
            email=email,
            first_name=first_name,
            roles=target_roles,
            user_type=user_type,
            password=password,
            language=language,
        )

        emp = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": first_name,
                "gender": "Male",
                "date_of_birth": "1990-01-01",
                "date_of_joining": "2024-01-01",
                "status": "Active",
                "company": company,
                "department": resolved_dept,
                "user_id": user_id,
            }
        ).insert(ignore_permissions=True)

        if pin:
            set_encrypted_password(
                "Employee", emp.name, pin, fieldname="custom_pda_pin"
            )
        else:
            remove_encrypted_password("Employee", emp.name, fieldname="custom_pda_pin")

        return user_id, emp.name

    def _create_zebra_printer(
        self, printer_name: str, ip: str = "127.0.0.1", port: int = 9100
    ) -> str:
        doc = frappe.get_doc(
            {
                "doctype": "KTA Zebra Printers",
                "printer_name": printer_name,
                "ip": ip,
                "port": port,
            }
        ).insert(ignore_permissions=True)
        return doc.name

    def _set_request_with_cookie(self, token: str | None = None, path: str = "/pda"):
        from frappe.auth import CookieManager

        headers = {}
        if token is not None:
            headers["Cookie"] = f"{PDA_DEVICE_COOKIE}={token}"
        env = EnvironBuilder(path=path, headers=headers).get_environ()
        frappe.local.request = Request(env)
        frappe.local.request_ip = "127.0.0.1"
        frappe.local.cookie_manager = CookieManager()

    def test_pda_get_settings_data_for_pure_operator_and_employeeless_admin(self):
        from erpnextkta.kta_stock.services.pda_service import pda_get_settings_data

        uid = frappe.generate_hash("", 5).upper()
        pure_user, pure_emp = self._ensure_pda_operator(
            email=f"pda_set_pure_{uid.lower()}@example.com",
            first_name=f"_Test Settings Pure {uid}",
            department=f"_Test Settings Dept {uid}",
            roles=[PDA_ROLE_STOCK_USER],
            pin=None,
            user_type="Website User",
        )
        self.assertEqual(
            frappe.db.get_value("User", pure_user, "user_type"), "Website User"
        )

        open_printer = self._create_zebra_printer(f"ZEBRA-OPEN-{uid}", ip="127.0.0.10")
        pda_printer = self._create_zebra_printer(f"ZEBRA-PDA-{uid}", ip="127.0.0.11")
        restricted_printer = self._create_zebra_printer(
            f"ZEBRA-ADMIN-{uid}", ip="127.0.0.12"
        )
        frappe.get_doc(
            {
                "doctype": "KTA Printer Permission",
                "printer": pda_printer,
                "role": PDA_ROLE_STOCK_USER,
                "can_print": 1,
            }
        ).insert(ignore_permissions=True)
        frappe.get_doc(
            {
                "doctype": "KTA Printer Permission",
                "printer": restricted_printer,
                "role": "System Manager",
                "can_print": 1,
            }
        ).insert(ignore_permissions=True)

        frappe.set_user(pure_user)
        pure_data = pda_get_settings_data()
        self.assertTrue(pure_data["has_employee"])
        self.assertEqual(pure_data["employee"], pure_emp)
        self.assertFalse(pure_data["has_pin"])
        self.assertFalse(pure_data["can_manage_operator_pins"])
        self.assertEqual(pure_data["manageable_operators"], [])
        self.assertEqual(
            pure_data["printer_preferences"],
            {"printer": None, "fallback_printer": None, "disabled": 1},
        )
        self.assertEqual(pure_data["user_language"], "tr")
        printer_names = {p["name"] for p in pure_data["authorized_printers"]}
        self.assertIn(open_printer, printer_names)
        self.assertIn(pda_printer, printer_names)
        self.assertNotIn(restricted_printer, printer_names)

        # Employee-less System Manager does not raise DoesNotExistError
        frappe.set_user("Administrator")
        admin_user = self._ensure_user(
            email=f"pda_set_admin_noemp_{uid.lower()}@example.com",
            first_name=f"_Test Admin NoEmp {uid}",
            roles=["System Manager"],
            user_type="System User",
        )
        frappe.set_user(admin_user)
        admin_data = pda_get_settings_data()
        self.assertFalse(admin_data["has_employee"])
        self.assertIsNone(admin_data["employee"])
        self.assertFalse(admin_data["has_pin"])
        self.assertTrue(admin_data["can_manage_operator_pins"])
        self.assertTrue(
            any(op["user_id"] == pure_user for op in admin_data["manageable_operators"])
        )
        admin_printer_names = {p["name"] for p in admin_data["authorized_printers"]}
        self.assertIn(restricted_printer, admin_printer_names)

    def test_pda_update_own_pin_initial_current_pin_and_password_reset_without_employee_save(
        self,
    ):
        from erpnext.setup.doctype.employee.employee import Employee
        from hrms.overrides.employee_master import EmployeeMaster

        from erpnextkta.kta_stock.services.pda_service import pda_update_own_pin

        uid = frappe.generate_hash("", 5).upper()
        pure_user, pure_emp = self._ensure_pda_operator(
            email=f"pda_pin_self_{uid.lower()}@example.com",
            first_name=f"_Test Self PIN {uid}",
            department=f"_Test PIN Dept {uid}",
            roles=[PDA_ROLE_STOCK_USER],
            pin=None,
            user_type="Website User",
            password="StrongPdaPass!99",
        )

        frappe.set_user(pure_user)
        with (
            patch.object(
                EmployeeMaster,
                "save",
                side_effect=AssertionError("EmployeeMaster.save must not be called"),
            ),
            patch.object(
                Employee,
                "save",
                side_effect=AssertionError("Employee.save must not be called"),
            ),
        ):
            for bad_pin in ("12", "12345", "12ab", ""):
                with self.assertRaises(frappe.ValidationError):
                    pda_update_own_pin(bad_pin, bad_pin, mode="initial")

            with self.assertRaises(frappe.ValidationError):
                pda_update_own_pin("1234", "5678", mode="initial")

            init_res = pda_update_own_pin("4829", "4829", mode="initial")
            self.assertEqual(
                init_res, {"ok": True, "employee": pure_emp, "has_pin": True}
            )
            self.assertEqual(
                get_decrypted_password(
                    "Employee", pure_emp, fieldname="custom_pda_pin"
                ),
                "4829",
            )

            # Once PIN exists, initial mode or invalid mode is rejected
            with self.assertRaises(frappe.ValidationError):
                pda_update_own_pin("1111", "1111", mode="initial")

            # Valid current_pin mode updates PIN
            chg_res = pda_update_own_pin(
                "7391", "7391", mode="current_pin", current_pin="4829"
            )
            self.assertTrue(chg_res["ok"])
            self.assertEqual(
                get_decrypted_password(
                    "Employee", pure_emp, fieldname="custom_pda_pin"
                ),
                "7391",
            )

            # 5 wrong current_pin attempts lock out PIN checks
            for _attempt in range(5):
                with self.assertRaises(frappe.ValidationError):
                    pda_update_own_pin(
                        "2468", "2468", mode="current_pin", current_pin="0000"
                    )
            self.assertEqual(
                cint(
                    frappe.cache().get_value(f"pda_pin_fail:{pure_emp}", expires=True)
                ),
                5,
            )
            with self.assertRaises(frappe.ValidationError):
                pda_update_own_pin(
                    "2468", "2468", mode="current_pin", current_pin="7391"
                )

            # Wrong account_password locks out pda_pwd_fail:{user} after 5 attempts
            with self.assertRaises(frappe.ValidationError):
                pda_update_own_pin(
                    "6152", "6152", mode="account_password", account_password=""
                )
            for _attempt in range(5):
                with self.assertRaises(frappe.ValidationError):
                    pda_update_own_pin(
                        "6152",
                        "6152",
                        mode="account_password",
                        account_password="WrongPassword123",
                    )
            self.assertEqual(
                cint(
                    frappe.cache().get_value(f"pda_pwd_fail:{pure_user}", expires=True)
                ),
                5,
            )
            # Locked even with right password while pda_pwd_fail >= 5
            with self.assertRaises(frappe.ValidationError):
                pda_update_own_pin(
                    "6152",
                    "6152",
                    mode="account_password",
                    account_password="StrongPdaPass!99",
                )

            # Reset pwd lockout and verify valid password reset clears both lockouts
            frappe.cache().delete_value(f"pda_pwd_fail:{pure_user}")
            with self.assertRaises(frappe.ValidationError):
                pda_update_own_pin(
                    "6152",
                    "6152",
                    mode="account_password",
                    account_password="WrongOnce",
                )
            pwd_res = pda_update_own_pin(
                "6152",
                "6152",
                mode="account_password",
                account_password="StrongPdaPass!99",
            )
            self.assertEqual(
                pwd_res, {"ok": True, "employee": pure_emp, "has_pin": True}
            )
            self.assertIsNone(
                frappe.cache().get_value(f"pda_pin_fail:{pure_emp}", expires=True)
            )
            self.assertIsNone(
                frappe.cache().get_value(f"pda_pwd_fail:{pure_user}", expires=True)
            )
            self.assertEqual(
                get_decrypted_password(
                    "Employee", pure_emp, fieldname="custom_pda_pin"
                ),
                "6152",
            )

    def test_pda_admin_reset_operator_pin_enforces_strict_rbac_and_clears_lockout(self):
        from erpnextkta.kta_stock.services.pda_service import (
            pda_admin_reset_operator_pin,
            pda_get_settings_data,
        )

        uid = frappe.generate_hash("", 5).upper()
        dept = f"_Test RBAC Dept {uid}"
        op_user, op_emp = self._ensure_pda_operator(
            email=f"pda_rbac_op_{uid.lower()}@example.com",
            first_name=f"_Test RBAC Op {uid}",
            department=dept,
            roles=[PDA_ROLE_STOCK_USER],
            pin="1111",
            user_type="Website User",
        )
        mgr_a_user, mgr_a_emp = self._ensure_pda_operator(
            email=f"pda_rbac_mgra_{uid.lower()}@example.com",
            first_name=f"_Test RBAC MgrA {uid}",
            department=dept,
            roles=["Stock Manager"],
            pin="2222",
        )
        _mgr_b_user, mgr_b_emp = self._ensure_pda_operator(
            email=f"pda_rbac_mgrb_{uid.lower()}@example.com",
            first_name=f"_Test RBAC MgrB {uid}",
            department=dept,
            roles=["Stock Manager"],
            pin="3333",
        )
        sys_user, sys_emp = self._ensure_pda_operator(
            email=f"pda_rbac_sys_{uid.lower()}@example.com",
            first_name=f"_Test RBAC Sys {uid}",
            department=dept,
            roles=["System Manager"],
            pin="4444",
        )

        # 1) Plain KTA PDA Stock User cannot call admin reset
        frappe.set_user(op_user)
        with self.assertRaises(frappe.PermissionError):
            pda_admin_reset_operator_pin(op_emp, "9999", "9999")

        # 2) Stock Manager (without System Manager)
        frappe.set_user(mgr_a_user)
        mgr_a_settings = pda_get_settings_data()
        self.assertTrue(mgr_a_settings["can_manage_operator_pins"])
        manageable_ids = {op["name"] for op in mgr_a_settings["manageable_operators"]}
        self.assertIn(op_emp, manageable_ids)
        self.assertNotIn(mgr_a_emp, manageable_ids)
        self.assertNotIn(mgr_b_emp, manageable_ids)
        self.assertNotIn(sys_emp, manageable_ids)

        with self.assertRaises(frappe.PermissionError):
            pda_admin_reset_operator_pin(mgr_a_emp, "9001", "9001")
        with self.assertRaises(frappe.PermissionError):
            pda_admin_reset_operator_pin(mgr_b_emp, "9001", "9001")
        with self.assertRaises(frappe.PermissionError):
            pda_admin_reset_operator_pin(sys_emp, "9001", "9001")

        # Reset non-manager PDA operator and clear lockouts
        frappe.cache().set_value(f"pda_pin_fail:{op_emp}", 5, expires_in_sec=300)
        frappe.cache().set_value(f"pda_pwd_fail:{op_user}", 5, expires_in_sec=300)
        reset_res = pda_admin_reset_operator_pin(op_emp, "9012", "9012")
        self.assertTrue(reset_res["ok"])
        self.assertEqual(reset_res["employee"], op_emp)
        self.assertTrue(reset_res["has_pin"])
        self.assertEqual(
            get_decrypted_password("Employee", op_emp, fieldname="custom_pda_pin"),
            "9012",
        )
        self.assertIsNone(
            frappe.cache().get_value(f"pda_pin_fail:{op_emp}", expires=True)
        )
        self.assertIsNone(
            frappe.cache().get_value(f"pda_pwd_fail:{op_user}", expires=True)
        )

        # 3) System Manager can reset peer Stock Manager & operators, but NOT self
        frappe.set_user(sys_user)
        sys_settings = pda_get_settings_data()
        sys_manageable = {op["name"] for op in sys_settings["manageable_operators"]}
        self.assertIn(op_emp, sys_manageable)
        self.assertIn(mgr_a_emp, sys_manageable)
        self.assertIn(mgr_b_emp, sys_manageable)
        self.assertNotIn(sys_emp, sys_manageable)

        with self.assertRaises(frappe.PermissionError):
            pda_admin_reset_operator_pin(sys_emp, "8888", "8888")

        sys_reset = pda_admin_reset_operator_pin(mgr_b_emp, "8765", "8765")
        self.assertTrue(sys_reset["ok"])
        self.assertEqual(
            get_decrypted_password("Employee", mgr_b_emp, fieldname="custom_pda_pin"),
            "8765",
        )

    def test_printer_preferences_and_connection_test_enforce_user_can_print_and_distinct_fallback(
        self,
    ):
        from kta_system_utils.kta_zebra_utils.printer_manager import (
            ZebraPrinter,
            ZebraPrinterManager,
        )

        from erpnextkta.kta_stock.services.pda_service import (
            pda_get_settings_data,
            pda_save_printer_preferences,
            pda_test_printer_connection,
        )

        uid = frappe.generate_hash("", 5).upper()
        pure_user, _ = self._ensure_pda_operator(
            email=f"pda_prt_{uid.lower()}@example.com",
            first_name=f"_Test Printer Op {uid}",
            department=f"_Test Printer Dept {uid}",
            roles=[PDA_ROLE_STOCK_USER],
            pin="1234",
            user_type="Website User",
        )
        z1 = self._create_zebra_printer(f"ZEBRA-01-{uid}", ip="127.0.0.21")
        z2 = self._create_zebra_printer(f"ZEBRA-02-{uid}", ip="127.0.0.22")
        z_restricted = self._create_zebra_printer(f"ZEBRA-ADMIN-{uid}", ip="127.0.0.23")
        frappe.get_doc(
            {
                "doctype": "KTA Printer Permission",
                "printer": z_restricted,
                "role": "System Manager",
                "can_print": 1,
            }
        ).insert(ignore_permissions=True)

        frappe.set_user(pure_user)

        # 1) Unauthorized restricted printer rejected on save and connection test
        with self.assertRaises(frappe.PermissionError):
            pda_save_printer_preferences(printer=z_restricted, fallback_printer=None)
        with self.assertRaises(frappe.PermissionError):
            pda_test_printer_connection(z_restricted)

        # 2) Same printer and fallback_printer rejected
        with self.assertRaises(frappe.ValidationError):
            pda_save_printer_preferences(printer=z1, fallback_printer=z1)

        # 3) Missing printer rejected
        with self.assertRaises(frappe.ValidationError):
            pda_save_printer_preferences(printer=f"NO-SUCH-PRINTER-{uid}")

        # 4) Authorized printers create/update KTA User Zebra Printers (disabled=0)
        save_res = pda_save_printer_preferences(printer=z1, fallback_printer=z2)
        self.assertEqual(
            save_res, {"ok": True, "printer": z1, "fallback_printer": z2, "disabled": 0}
        )
        settings_after = pda_get_settings_data()
        self.assertEqual(
            settings_after["printer_preferences"],
            {"printer": z1, "fallback_printer": z2, "disabled": 0},
        )

        # 5) Clearing both printers sets disabled=1
        clear_res = pda_save_printer_preferences(printer=None, fallback_printer=None)
        self.assertEqual(
            clear_res,
            {"ok": True, "printer": None, "fallback_printer": None, "disabled": 1},
        )
        settings_cleared = pda_get_settings_data()
        self.assertEqual(
            settings_cleared["printer_preferences"],
            {"printer": None, "fallback_printer": None, "disabled": 1},
        )

        # 6) Connection test calls check_printer_status without printing ZPL or creating print logs
        logs_before = frappe.db.count("KTA Print Log")
        with (
            patch.object(
                ZebraPrinterManager,
                "check_printer_status",
                return_value={
                    "status": "Ready",
                    "color": "green",
                    "message": "Printer ready",
                },
            ) as mock_status,
            patch.object(
                ZebraPrinter,
                "send_batch",
                side_effect=AssertionError("send_batch must not be called"),
            ),
        ):
            online_res = pda_test_printer_connection(z1)
        mock_status.assert_called_once_with(z1)
        self.assertEqual(
            online_res,
            {
                "ok": True,
                "printer": z1,
                "online": True,
                "status": "Ready",
                "message": "Printer ready",
            },
        )
        self.assertEqual(frappe.db.count("KTA Print Log"), logs_before)

        with patch.object(
            ZebraPrinterManager,
            "check_printer_status",
            return_value={
                "status": "Offline",
                "color": "red",
                "message": "Connection refused",
            },
        ):
            offline_res = pda_test_printer_connection(z1)
        self.assertFalse(offline_res["online"])
        self.assertEqual(offline_res["status"], "Offline")
        self.assertEqual(offline_res["message"], "Connection refused")

    def test_live_language_sync_in_update_verify_pin_and_handover_logout(self):
        from erpnextkta.kta_stock.services.pda_service import pda_update_user_language

        uid = frappe.generate_hash("", 5).upper()
        pure_user, pure_emp = self._ensure_pda_operator(
            email=f"pda_lang_{uid.lower()}@example.com",
            first_name=f"_Test Lang Op {uid}",
            department=f"_Test Lang Dept {uid}",
            roles=[PDA_ROLE_STOCK_USER],
            pin="4829",
            user_type="Website User",
            language="tr",
        )

        # 1) Live language change updates User.language without needing User write DocPerm
        frappe.set_user(pure_user)
        with self.assertRaises(frappe.ValidationError):
            pda_update_user_language("fr")

        en_res = pda_update_user_language("en")
        self.assertTrue(en_res["ok"])
        self.assertEqual(en_res["lang"], "en")
        self.assertIsInstance(en_res["messages"], dict)
        self.assertGreater(len(en_res["messages"]), 0)
        self.assertEqual(frappe.db.get_value("User", pure_user, "language"), "en")
        self.assertEqual(frappe.local.lang, "en")

        # 2) verify_pda_pin switches session to operator and returns operator language + dict
        token = issue_pda_device_token(f"pda-lang-dev-{uid}")
        self._set_request_with_cookie(token=token)
        frappe.set_user("Guest")

        login_res = verify_pda_pin(pure_emp, "4829")
        self.assertTrue(login_res["ok"])
        self.assertEqual(login_res["lang"], "en")
        self.assertIsInstance(login_res["messages"], dict)
        self.assertGreater(len(login_res["messages"]), 0)
        self.assertEqual(frappe.local.lang, "en")

        # 3) pda_handover_logout resets to Guest and returns site default "tr" + Turkish messages
        logout_res = pda_handover_logout()
        self.assertTrue(logout_res["ok"])
        self.assertTrue(logout_res["is_locked"])
        self.assertEqual(logout_res["lang"], "tr")
        self.assertIsInstance(logout_res["messages"], dict)
        self.assertGreater(len(logout_res["messages"]), 0)
        self.assertEqual(frappe.local.lang, "tr")
