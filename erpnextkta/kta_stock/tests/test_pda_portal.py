import json

import frappe
from frappe.utils.password import remove_encrypted_password, set_encrypted_password
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from erpnextkta.kta_stock.services.pda_service import (
    PDA_DEVICE_COOKIE,
    issue_pda_device_token,
    verify_pda_device_token,
)
from erpnextkta.kta_stock.setup import (
    PDA_ROLE_STOCK_USER,
    setup_pda_custom_fields,
    setup_pda_roles_and_permissions,
)
from erpnextkta.tests.test_utils import KTABaseTestCase, create_test_company

_MISSING = object()


class TestPdaPortal(KTABaseTestCase):
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
        self._had_redirect_location = "redirect_location" in frappe.local.flags
        self._saved_redirect_location = getattr(
            frappe.local.flags, "redirect_location", None
        )
        if not getattr(frappe.local, "lang", None):
            frappe.local.lang = "tr"
        setup_pda_roles_and_permissions()

    def tearDown(self):
        frappe.set_user("Administrator")
        if self._had_redirect_location:
            frappe.local.flags.redirect_location = self._saved_redirect_location
        else:
            frappe.local.flags.pop("redirect_location", None)

        for attr, val in self._saved_local.items():
            if val is _MISSING:
                if hasattr(frappe.local, attr):
                    delattr(frappe.local, attr)
            else:
                setattr(frappe.local, attr, val)
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
        dept.company = None
        dept.flags.ignore_mandatory = True
        dept.flags.ignore_links = True
        dept.insert(ignore_permissions=True)
        frappe.db.set_value("Department", dept.name, "company", company)
        return dept.name

    def _ensure_user_with_roles(
        self,
        email: str,
        first_name: str,
        roles: list[str],
        enabled: int = 1,
        user_type: str | None = None,
    ) -> str:
        for role_name in roles:
            if not frappe.db.exists("Role", role_name):
                frappe.get_doc(
                    {
                        "doctype": "Role",
                        "role_name": role_name,
                        "desk_access": 0 if role_name.startswith("KTA PDA ") else 1,
                    }
                ).insert(ignore_permissions=True)

        if not frappe.db.exists("User", email):
            user_data = {
                "doctype": "User",
                "email": email,
                "first_name": first_name,
                "enabled": enabled,
                "send_welcome_email": 0,
            }
            if user_type is not None:
                user_data["user_type"] = user_type
            user = frappe.get_doc(user_data)
            for role_name in roles:
                user.append("roles", {"role": role_name})
            user.insert(ignore_permissions=True)
        else:
            user = frappe.get_doc("User", email)
            user.enabled = enabled
            if user_type is not None:
                user.user_type = user_type
            user.set("roles", [{"role": r} for r in roles])
            user.save(ignore_permissions=True)

        frappe.clear_cache(user=email)
        return email

    def _ensure_test_pda_operator(
        self,
        email: str,
        first_name: str,
        department: str = "AMBAR - KTA",
        pin: str | None = "4829",
        roles: list[str] | None = None,
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
        self._ensure_user_with_roles(
            email=email,
            first_name=first_name,
            roles=target_roles,
            user_type=user_type,
        )

        emp_name = frappe.db.get_value(
            "Employee", {"user_id": email}, "name"
        ) or frappe.db.get_value("Employee", {"first_name": first_name}, "name")

        if not emp_name:
            emp = frappe.get_doc(
                {
                    "doctype": "Employee",
                    "first_name": first_name,
                    "gender": "Male",
                    "date_of_birth": "1990-01-01",
                    "date_of_joining": "2024-01-01",
                    "status": "Active",
                    "company": company,
                    "department": resolved_department,
                    "user_id": email,
                }
            )
            emp.insert(ignore_permissions=True)
            emp_name = emp.name
        else:
            frappe.db.set_value(
                "Employee",
                emp_name,
                {
                    "status": "Active",
                    "relieving_date": None,
                    "department": resolved_department,
                    "user_id": email,
                },
            )

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
        frappe.local.flags.pop("redirect_location", None)

    def test_pda_guest_without_device_cookie_redirects_to_login(self):
        self._set_request_with_cookie(token=None, path="/pda")
        frappe.set_user("Guest")

        from erpnextkta.www.pda import get_context

        with self.assertRaises(frappe.Redirect):
            get_context(frappe._dict())

        self.assertEqual(
            getattr(frappe.local.flags, "redirect_location", None),
            "/login?redirect-to=/pda",
        )

    def test_pda_guest_with_valid_device_cookie_renders_locked_boot(self):
        emp_name = self._ensure_test_pda_operator(
            email="pda_portal_guest@example.com",
            first_name="_Test PDA Portal Guest Op",
            department="AMBAR - KTA",
            pin="2468",
            roles=[PDA_ROLE_STOCK_USER],
        )
        token = issue_pda_device_token("test-portal-device-01")
        self._set_request_with_cookie(token=token, path="/pda")
        frappe.set_user("Guest")

        from erpnextkta.www.pda import get_context

        ctx = frappe._dict()
        get_context(ctx)

        self.assertTrue(ctx.get("csrf_token"))
        self.assertTrue(ctx.get("boot_json"))
        boot_data = json.loads(ctx.boot_json)
        self.assertIsInstance(boot_data.get("__messages"), dict)

        self.assertTrue(ctx.get("pda_boot_json"))
        pda_boot = json.loads(ctx.pda_boot_json)
        if ctx.get("pda_boot_data") is not None:
            self.assertEqual(ctx.pda_boot_data, pda_boot)

        self.assertEqual(pda_boot["current_user"], "Guest")
        self.assertIs(pda_boot["device_authorized"], True)
        self.assertIs(pda_boot["is_locked"], True)
        self.assertIsInstance(pda_boot["operators"], list)
        self.assertTrue(any(op["name"] == emp_name for op in pda_boot["operators"]))

    def test_pda_unauthorized_logged_in_user_throws_permission_error(self):
        email = "pda_portal_no_stock@example.com"
        self._ensure_user_with_roles(
            email=email,
            first_name="_Test PDA Portal No Stock",
            roles=["_Test Non Stock Portal Role"],
        )
        self._set_request_with_cookie(token=None, path="/pda")
        frappe.set_user(email)

        from erpnextkta.www.pda import get_context

        with self.assertRaises(frappe.PermissionError):
            get_context(frappe._dict())

    def test_pda_authorized_stock_user_populates_boot_and_sets_device_cookie(self):
        emp_name = self._ensure_test_pda_operator(
            email="pda_portal_stock@example.com",
            first_name="_Test PDA Portal Stock Op",
            department="Sevk",
            pin="1357",
            roles=[PDA_ROLE_STOCK_USER],
        )
        self._set_request_with_cookie(token=None, path="/pda")
        frappe.set_user("pda_portal_stock@example.com")

        from erpnextkta.www.pda import get_context

        ctx = frappe._dict()
        get_context(ctx)

        self.assertTrue(ctx.get("csrf_token"))
        self.assertTrue(ctx.get("boot_json"))
        boot_data = json.loads(ctx.boot_json)
        self.assertIsInstance(boot_data.get("__messages"), dict)

        self.assertTrue(ctx.get("pda_boot_json"))
        pda_boot = json.loads(ctx.pda_boot_json)
        if ctx.get("pda_boot_data") is not None:
            self.assertEqual(ctx.pda_boot_data, pda_boot)

        self.assertEqual(pda_boot["current_user"], "pda_portal_stock@example.com")
        self.assertIs(pda_boot["is_locked"], False)
        self.assertIs(pda_boot["device_authorized"], True)
        self.assertIsNotNone(pda_boot.get("active_operator"))
        self.assertEqual(pda_boot["active_operator"]["name"], emp_name)
        self.assertEqual(
            pda_boot["active_operator"]["user_id"], "pda_portal_stock@example.com"
        )

        cookie_entry = frappe.local.cookie_manager.cookies.get(PDA_DEVICE_COOKIE)
        self.assertIsNotNone(cookie_entry)
        self.assertTrue(cookie_entry.get("httponly"))
        self.assertTrue(verify_pda_device_token(cookie_entry.get("value")))

    def test_pda_full_page_render_contains_app_mount_and_bundles(self):
        email = "pda_portal_render@example.com"
        self._ensure_test_pda_operator(
            email=email,
            first_name="_Test PDA Portal Render Op",
            department="AMBAR - KTA",
            pin="7890",
            roles=[PDA_ROLE_STOCK_USER],
        )

        from frappe.utils import set_request
        from frappe.website.serve import get_response_content
        from frappe.website.utils import clear_website_cache

        saved_session_data = getattr(frappe.local.session, "data", _MISSING)
        saved_session_obj = getattr(frappe.local, "session_obj", _MISSING)
        try:
            clear_website_cache("pda")
            frappe.set_user(email)
            frappe.local.session.data = frappe._dict(
                {"csrf_token": "test-pda-render-csrf"}
            )
            frappe.local.session_obj = frappe._dict(
                {"data": frappe.local.session.data, "update": lambda **kw: None}
            )
            set_request(path="/pda")
            html = get_response_content("pda")
        finally:
            if saved_session_data is _MISSING:
                if hasattr(frappe.local.session, "data"):
                    delattr(frappe.local.session, "data")
            else:
                frappe.local.session.data = saved_session_data

            if saved_session_obj is _MISSING:
                if hasattr(frappe.local, "session_obj"):
                    delattr(frappe.local, "session_obj")
            else:
                frappe.local.session_obj = saved_session_obj

            clear_website_cache("pda")

        self.assertIn('<div id="pda-app"></div>', html)
        self.assertIn("set_style", html)
        self.assertIn("pda-hub.bundle", html)
        self.assertNotIn("Illegal template", html)
        self.assertNotIn("<title>Error</title>", html)

    def test_pda_portal_allows_pure_pda_stock_user_and_rejects_plain_stock_user(self):
        uid = frappe.generate_hash("", 5)
        pure_email = f"pda_portal_pure_{uid}@example.com"
        self._ensure_test_pda_operator(
            email=pure_email,
            first_name=f"_Test Portal Pure {uid}",
            department=f"_Test Saha {uid}",
            pin="3579",
            roles=[PDA_ROLE_STOCK_USER],
            user_type="Website User",
        )
        self.assertEqual(
            frappe.db.get_value("User", pure_email, "user_type"), "Website User"
        )

        self._set_request_with_cookie(token=None, path="/pda")
        frappe.set_user(pure_email)

        from erpnextkta.www.pda import get_context

        ctx = frappe._dict()
        get_context(ctx)
        pda_boot = json.loads(ctx.pda_boot_json)
        self.assertEqual(pda_boot["current_user"], pure_email)
        self.assertEqual([c["key"] for c in pda_boot["menu_categories"]], ["stock"])
        cookie_entry = frappe.local.cookie_manager.cookies.get(PDA_DEVICE_COOKIE)
        self.assertIsNotNone(cookie_entry)
        self.assertTrue(verify_pda_device_token(cookie_entry.get("value")))

        office_email = f"pda_portal_office_{uid}@example.com"
        self._ensure_user_with_roles(
            email=office_email,
            first_name=f"_Test Portal Office {uid}",
            roles=["Stock User"],
        )
        self._set_request_with_cookie(token=None, path="/pda")
        frappe.set_user(office_email)
        with self.assertRaises(frappe.PermissionError):
            get_context(frappe._dict())
