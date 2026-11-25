import frappe
from frappe.utils import cint

from erpnextkta.tests.test_utils import KTABaseTestCase, create_test_company


class TestPdaRoleSetup(KTABaseTestCase):
    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.local.flags.pop("_kta_preserve_pda_website_users", None)
        frappe.db.rollback()
        super().tearDown()

    def _get_test_company(self) -> str:
        company = frappe.db.get_value(
            "Company", "_Test Company", "name"
        ) or frappe.db.get_value("Company", {}, "name")
        if not company:
            company = create_test_company("_Test Company")
        return company

    def _ensure_role(self, role_name: str, desk_access: int = 1) -> str:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc(
                {
                    "doctype": "Role",
                    "role_name": role_name,
                    "desk_access": cint(desk_access),
                }
            ).insert(ignore_permissions=True)
        return role_name

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

    def _create_user_and_employee(
        self,
        email: str,
        first_name: str,
        roles: list[str],
        department: str,
        user_type: str = "System User",
        enabled: int = 1,
        emp_status: str = "Active",
    ) -> tuple[str, str]:
        company = self._get_test_company()
        resolved_dept = self._ensure_department(department, company)
        if not frappe.db.exists("Gender", "Male"):
            frappe.get_doc({"doctype": "Gender", "gender": "Male"}).insert(
                ignore_permissions=True
            )

        for role_name in roles:
            self._ensure_role(role_name)

        user = frappe.get_doc(
            {
                "doctype": "User",
                "email": email,
                "first_name": first_name,
                "enabled": 1,
                "user_type": user_type,
                "send_welcome_email": 0,
                "roles": [{"role": r} for r in roles],
            }
        ).insert(ignore_permissions=True)

        emp = frappe.get_doc(
            {
                "doctype": "Employee",
                "first_name": first_name,
                "gender": "Male",
                "date_of_birth": "1990-01-01",
                "date_of_joining": "2024-01-01",
                "status": emp_status,
                "relieving_date": "2025-01-01" if emp_status == "Left" else None,
                "company": company,
                "department": resolved_dept,
                "user_id": user.name,
            }
        ).insert(ignore_permissions=True)

        if not enabled:
            frappe.db.set_value("User", user.name, "enabled", 0)
        frappe.clear_cache(user=user.name)
        return user.name, emp.name

    def test_setup_creates_pda_stock_role_docperms_and_home_page(self):
        from erpnextkta.kta_stock.setup import (
            PDA_ROLE_STOCK_USER,
            setup_pda_roles_and_permissions,
        )

        setup_pda_roles_and_permissions()
        setup_pda_roles_and_permissions()

        role = frappe.get_doc("Role", PDA_ROLE_STOCK_USER)
        self.assertEqual(cint(role.desk_access), 0)
        self.assertEqual(role.home_page, "/pda")

        expected_perms = {
            "Stock Entry": ("read", "write", "create", "submit"),
            "Serial and Batch Bundle": ("read", "write", "create", "submit"),
            "Batch": ("read", "write", "create"),
            "Stock Ledger Entry": ("read",),
            "Item": ("read",),
            "Warehouse": ("read",),
            "KTA Stock Label": ("read", "write", "create"),
            "KTA Line Replenishment Order": ("read", "write"),
        }
        for dt, rights in expected_perms.items():
            perm = frappe.db.get_value(
                "Custom DocPerm",
                {
                    "parent": dt,
                    "role": PDA_ROLE_STOCK_USER,
                    "permlevel": 0,
                    "if_owner": 0,
                },
                ["read", "write", "create", "submit"],
                as_dict=True,
            )
            self.assertIsNotNone(perm, f"Missing Custom DocPerm for {dt}")
            for right in ("read", "write", "create", "submit"):
                self.assertEqual(cint(perm[right]), 1 if right in rights else 0)

        self.assertTrue(
            frappe.db.exists(
                "Custom DocPerm",
                {
                    "parent": "Stock Entry",
                    "role": "Stock User",
                    "permlevel": 0,
                    "read": 1,
                },
            )
        )

    def test_setup_mirrors_printer_permissions_only_for_restricted_printers(self):
        from erpnextkta.kta_stock.setup import (
            PDA_ROLE_STOCK_USER,
            setup_pda_roles_and_permissions,
        )

        if not (
            frappe.db.exists("DocType", "KTA Zebra Printers")
            and frappe.db.exists("DocType", "KTA Printer Permission")
        ):
            self.skipTest("KTA Zebra printer permission DocTypes not installed")

        self._ensure_role("Stock User", desk_access=1)
        uid = frappe.generate_hash("", 5).upper()
        restricted_printer = frappe.get_doc(
            {
                "doctype": "KTA Zebra Printers",
                "printer_name": f"_TEST-PRINTER-RESTR-{uid}",
                "ip": "127.0.0.1",
                "port": 9100,
            }
        ).insert(ignore_permissions=True)
        open_printer = frappe.get_doc(
            {
                "doctype": "KTA Zebra Printers",
                "printer_name": f"_TEST-PRINTER-OPEN-{uid}",
                "ip": "127.0.0.2",
                "port": 9100,
            }
        ).insert(ignore_permissions=True)
        frappe.get_doc(
            {
                "doctype": "KTA Printer Permission",
                "printer": restricted_printer.name,
                "role": "Stock User",
                "can_print": 1,
            }
        ).insert(ignore_permissions=True)

        setup_pda_roles_and_permissions()
        setup_pda_roles_and_permissions()

        restricted_rows = frappe.get_all(
            "KTA Printer Permission",
            filters={"printer": restricted_printer.name, "role": PDA_ROLE_STOCK_USER},
            fields=["can_print"],
        )
        self.assertEqual(len(restricted_rows), 1)
        self.assertEqual(cint(restricted_rows[0].can_print), 1)

        open_rows = frappe.get_all(
            "KTA Printer Permission",
            filters={"printer": open_printer.name},
            pluck="role",
        )
        self.assertEqual(open_rows, [])

    def test_employee_save_preserves_website_user_for_pure_pda_operator_only(self):
        from erpnextkta.kta_stock.setup import (
            PDA_ROLE_STOCK_USER,
            setup_pda_roles_and_permissions,
        )

        setup_pda_roles_and_permissions()
        self._ensure_role("Employee", desk_access=1)
        self._ensure_role("KTA Çalışma Kartı Kullanıcısı", desk_access=1)

        uid = frappe.generate_hash("", 5)
        pure_user_id, pure_emp_name = self._create_user_and_employee(
            email=f"pda_guard_pure_{uid}@example.com",
            first_name="EskiSaha",
            roles=[PDA_ROLE_STOCK_USER],
            department=f"_Test Guard Dept {uid}",
            user_type="Website User",
        )
        desk_user_id, desk_emp_name = self._create_user_and_employee(
            email=f"pda_guard_desk_{uid}@example.com",
            first_name="EskiDesk",
            roles=["KTA Çalışma Kartı Kullanıcısı", PDA_ROLE_STOCK_USER],
            department=f"_Test Guard Dept {uid}",
            user_type="System User",
        )

        # 1) Pure Website User holding only KTA PDA Stock User
        pure_emp = frappe.get_doc("Employee", pure_emp_name)
        pure_emp.first_name = "GüncelSaha"
        pure_emp.save(ignore_permissions=True)

        pure_user = frappe.get_doc("User", pure_user_id)
        self.assertEqual(pure_user.user_type, "Website User")
        self.assertNotIn("Employee", frappe.get_roles(pure_user.name))
        self.assertEqual(pure_user.first_name, "GüncelSaha")

        # 2) Desk operator holding "KTA Çalışma Kartı Kullanıcısı" (desk_access=1)
        desk_emp = frappe.get_doc("Employee", desk_emp_name)
        desk_emp.first_name = "DeskOperatör"
        desk_emp.save(ignore_permissions=True)

        self.assertEqual(
            frappe.db.get_value("User", desk_user_id, "user_type"), "System User"
        )
        self.assertIn("Employee", frappe.get_roles(desk_user_id))

        # 3) Explicit admin edit directly on User form adding "Employee" is NOT stripped
        pure_user.reload()
        pure_user.append("roles", {"role": "Employee"})
        pure_user.save(ignore_permissions=True)

        self.assertIn("Employee", frappe.get_roles(pure_user.name))
        self.assertEqual(
            frappe.db.get_value("User", pure_user.name, "user_type"), "System User"
        )

    def test_backfill_adds_pda_stock_role_non_destructively(self):
        from erpnextkta.kta_stock.setup import (
            PDA_ROLE_STOCK_USER,
            setup_pda_roles_and_permissions,
        )
        from erpnextkta.patches.v4_4.setup_pda_stock_role_and_backfill import (
            backfill_existing_pda_stock_operators,
        )

        setup_pda_roles_and_permissions()
        self._ensure_role("Stock User", desk_access=1)
        self._ensure_role("Stock Manager", desk_access=1)

        uid = frappe.generate_hash("", 5)
        ambar_user, _ = self._create_user_and_employee(
            email=f"pda_backfill_ambar_{uid}@example.com",
            first_name=f"_Test Backfill Ambar {uid}",
            roles=["Stock User"],
            department="AMBAR - KTA",
            user_type="System User",
        )
        sevk_user, _ = self._create_user_and_employee(
            email=f"pda_backfill_sevk_{uid}@example.com",
            first_name=f"_Test Backfill Sevk {uid}",
            roles=["Stock Manager"],
            department="Sevk",
            user_type="System User",
        )
        other_dept_user, _ = self._create_user_and_employee(
            email=f"pda_backfill_other_{uid}@example.com",
            first_name=f"_Test Backfill Other {uid}",
            roles=["Stock User"],
            department=f"_Test Üretim {uid}",
            user_type="System User",
        )
        disabled_user, _ = self._create_user_and_employee(
            email=f"pda_backfill_dis_{uid}@example.com",
            first_name=f"_Test Backfill Dis {uid}",
            roles=["Stock User"],
            department="AMBAR - KTA",
            user_type="System User",
            enabled=0,
        )

        added_first = backfill_existing_pda_stock_operators()
        self.assertGreaterEqual(added_first, 2)
        self.assertIn(PDA_ROLE_STOCK_USER, frappe.get_roles(ambar_user))
        self.assertIn("Stock User", frappe.get_roles(ambar_user))
        self.assertIn(PDA_ROLE_STOCK_USER, frappe.get_roles(sevk_user))
        self.assertIn("Stock Manager", frappe.get_roles(sevk_user))
        self.assertNotIn(PDA_ROLE_STOCK_USER, frappe.get_roles(other_dept_user))
        self.assertNotIn(PDA_ROLE_STOCK_USER, frappe.get_roles(disabled_user))

        self.assertEqual(backfill_existing_pda_stock_operators(), 0)
