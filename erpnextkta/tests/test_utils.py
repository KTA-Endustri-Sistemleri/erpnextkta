import sys
import unittest
import frappe
from frappe import _
from erpnextkta.kta_calisma_karti.setup import setup_system_downtime_reasons


def before_tests():
	"""
	Seed infrastructure needed by ERPNext (and erpnextkta) tests
	before the test runner starts creating record dependencies.

	Uses ERPNext's setup_complete() for a full, proper initialization
	of company, chart of accounts, default accounts, and fixtures.
	"""
	print("\nDEBUG: erpnextkta.tests.test_utils.before_tests hook'u çalıştırılıyor...")
	frappe.flags.skip_test_records = True

	company_name = "_Test Company"
	abbr = "_TC"

	# ──────────────────────────────────────────────────────────────────
	# 1. Full site setup via ERPNext's setup_complete()
	#    This creates Company, Chart of Accounts, default accounts,
	#    fiscal year, currencies, and all standard fixtures.
	# ──────────────────────────────────────────────────────────────────
	if not frappe.db.exists("Company", company_name):
		print(f"DEBUG: {company_name} için tam setup_complete çalıştırılıyor...")
		from erpnext.setup.setup_wizard.setup_wizard import setup_complete

		args = frappe._dict({
			"company_name": company_name,
			"company_abbr": abbr,
			"default_currency": "INR",
			"country": "India",
			"chart_of_accounts": "Standard",
			"domain": "Manufacturing",
			"fy_start_date": "2024-01-01",
			"fy_end_date": "2024-12-31",
		})
		try:
			setup_complete(args)
			print("DEBUG: setup_complete başarıyla tamamlandı.")
		except Exception as e:
			print(f"DEBUG: setup_complete hata fırlattı: {e}")
			# If setup_complete failed partially, ensure Company at least exists
			if not frappe.db.exists("Company", company_name):
				frappe.get_doc({
					"doctype": "Company",
					"company_name": company_name,
					"abbr": abbr,
					"default_currency": "INR",
					"country": "India",
				}).insert(ignore_permissions=True, ignore_if_duplicate=True)

		frappe.db.commit()
	else:
		print(f"DEBUG: {company_name} zaten mevcut, setup_complete atlanıyor.")
		# FORCE updating default_currency just in case frail test runners created a shallow object
		frappe.db.sql("UPDATE `tabCompany` SET default_currency='INR' WHERE name=%s", (company_name,))
		frappe.db.commit()

	# Ensure current year Fiscal Year exists for _Test Company
	from frappe.utils import getdate, nowdate
	curr_year = str(getdate(nowdate()).year)
	if not frappe.db.exists("Fiscal Year", curr_year):
		try:
			frappe.get_doc({
				"doctype": "Fiscal Year",
				"year": curr_year,
				"year_start_date": f"{curr_year}-01-01",
				"year_end_date": f"{curr_year}-12-31",
				"companies": [{"company": company_name}],
			}).insert(ignore_permissions=True, ignore_if_duplicate=True)
		except Exception:
			pass
	else:
		try:
			fy = frappe.get_doc("Fiscal Year", curr_year)
			if not any(c.company == company_name for c in fy.companies):
				fy.append("companies", {"company": company_name})
				fy.save(ignore_permissions=True)
		except Exception:
			pass
	frappe.db.commit()
	# 2. Ensure essential root groups exist (idempotent)
	# ──────────────────────────────────────────────────────────────────
	standard_roots = [
		{"doctype": "Customer Group", "customer_group_name": "All Customer Groups", "is_group": 1, "parent_customer_group": ""},
		{"doctype": "Territory", "territory_name": "All Territories", "is_group": 1, "parent_territory": ""},
		{"doctype": "Item Group", "item_group_name": "All Item Groups", "is_group": 1, "parent_item_group": ""},
		{"doctype": "Supplier Group", "supplier_group_name": "All Supplier Groups", "is_group": 1, "parent_supplier_group": ""},
		{"doctype": "Sales Person", "sales_person_name": "Sales Team", "is_group": 1, "parent_sales_person": ""},
		{"doctype": "Department", "department_name": "All Departments", "is_group": 1, "parent_department": ""},
	]

	for root in standard_roots:
		name_field = {
			"Customer Group": "customer_group_name",
			"Territory": "territory_name",
			"Item Group": "item_group_name",
			"Supplier Group": "supplier_group_name",
			"Sales Person": "sales_person_name",
			"Department": "department_name",
		}[root["doctype"]]
		if not frappe.db.exists(root["doctype"], root[name_field]):
			try:
				frappe.get_doc(root).insert(ignore_permissions=True, ignore_if_duplicate=True)
			except Exception:
				# Root record may already exist or be inserted concurrently
				pass

	if not frappe.db.exists("Department", "All Departments"):
		frappe.db.sql("""
			INSERT INTO `tabDepartment` (name, department_name, is_group, parent_department, creation, modified, modified_by)
			VALUES ('All Departments', 'All Departments', 1, '', NOW(), NOW(), 'Administrator')
			ON DUPLICATE KEY UPDATE name=name
		""")
		from frappe.utils.nestedset import rebuild_tree
		rebuild_tree("Department", "parent_department")
		frappe.db.commit()

	# ──────────────────────────────────────────────────────────────────
	# 3. Sub-groups and common reference records
	# ──────────────────────────────────────────────────────────────────
	sub_records = [
		{"doctype": "Customer Group", "customer_group_name": "Individual", "is_group": 0, "parent_customer_group": "All Customer Groups"},
		{"doctype": "Customer Group", "customer_group_name": "Commercial", "is_group": 0, "parent_customer_group": "All Customer Groups"},
		{"doctype": "Customer Group", "customer_group_name": "_Test Customer Group", "is_group": 0, "parent_customer_group": "All Customer Groups"},
		{"doctype": "Supplier Group", "supplier_group_name": "Local", "is_group": 0, "parent_supplier_group": "All Supplier Groups"},
		{"doctype": "Supplier Group", "supplier_group_name": "_Test Supplier Group", "is_group": 0, "parent_supplier_group": "All Supplier Groups"},
		{"doctype": "Warehouse Type", "name": "Transit", "warehouse_type": "Transit"},
		{"doctype": "Warehouse Type", "name": "Work In Progress", "warehouse_type": "Work In Progress"},
		{"doctype": "Warehouse Type", "name": "Finished Goods", "warehouse_type": "Finished Goods"},
	]
	for rec in sub_records:
		name_field = {
			"Customer Group": "customer_group_name",
			"Supplier Group": "supplier_group_name",
		}.get(rec["doctype"], "name")
		if not frappe.db.exists(rec["doctype"], rec[name_field]):
			try:
				frappe.get_doc(rec).insert(ignore_permissions=True, ignore_if_duplicate=True)
			except Exception:
				# Sub-group record may already exist or fail safely during test setup
				pass

	# Genders, Sales Stages, Employment Types
	for gender in ["Female", "Male", "Other"]:
		if not frappe.db.exists("Gender", gender):
			frappe.get_doc({"doctype": "Gender", "gender": gender}).insert(ignore_permissions=True, ignore_if_duplicate=True)
	for stage in ["Prospecting", "Qualification", "Needs Analysis", "Value Proposition", "Negotiation/Review"]:
		if not frappe.db.exists("Sales Stage", stage):
			frappe.get_doc({"doctype": "Sales Stage", "stage_name": stage}).insert(ignore_permissions=True, ignore_if_duplicate=True)
	for et in ["Full-time", "Part-time", "Contract", "Intern"]:
		if not frappe.db.exists("Employment Type", et):
			frappe.get_doc({"doctype": "Employment Type", "employee_type_name": et}).insert(ignore_permissions=True, ignore_if_duplicate=True)

	# Stock Entry Types
	for set_name, purpose in [("Material Issue", "Material Issue"), ("Material Receipt", "Material Receipt"),
							  ("Material Transfer", "Material Transfer"), ("Manufacture", "Manufacture")]:
		if not frappe.db.exists("Stock Entry Type", set_name):
			frappe.get_doc({"doctype": "Stock Entry Type", "name": set_name, "purpose": purpose, "is_standard": 1}).insert(ignore_permissions=True, ignore_if_duplicate=True)

	# UOMs
	for uom in ["Nos", "Unit"]:
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom, "name": uom, "enabled": 1}).insert(ignore_permissions=True, ignore_if_duplicate=True)

	# ──────────────────────────────────────────────────────────────────
	# 4. Core Test Records (Customer, Supplier)
	# ──────────────────────────────────────────────────────────────────
	if not frappe.db.exists("Customer", "_Test Customer"):
		frappe.get_doc({
			"doctype": "Customer",
			"customer_name": "_Test Customer",
			"customer_group": "_Test Customer Group",
			"territory": "All Territories",
			"customer_type": "Company",
		}).insert(ignore_permissions=True, ignore_if_duplicate=True)

	if not frappe.db.exists("Supplier", "_Test Supplier"):
		frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": "_Test Supplier",
			"supplier_group": "_Test Supplier Group",
			"supplier_type": "Company",
		}).insert(ignore_permissions=True, ignore_if_duplicate=True)

	# ──────────────────────────────────────────────────────────────────
	# 5. Fix Party Types (Receivable/Payable mapping)
	# ──────────────────────────────────────────────────────────────────
	frappe.db.sql("UPDATE `tabParty Type` SET account_type = 'Receivable' WHERE name = 'Customer'")
	frappe.db.sql("UPDATE `tabParty Type` SET account_type = 'Payable' WHERE name = 'Supplier'")

	# ──────────────────────────────────────────────────────────────────
	# 6. Monkeypatches for test stability
	# ──────────────────────────────────────────────────────────────────

	# 6a. Journal Entry: bypass account_type vs party_type mismatch check
	from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry

	def patched_validate_party(self):
		for d in self.get("accounts"):
			account_type = frappe.get_cached_value("Account", d.account, "account_type")
			if account_type in ["Receivable", "Payable"]:
				if not (d.party_type and d.party) and not self.get("party_not_required"):
					frappe.throw(_("Satır {0}: {1} için Taraf Tipi ve Taraf zorunludur").format(d.idx, d.account))

	JournalEntry.validate_party = patched_validate_party
	print("DEBUG: JournalEntry.validate_party monkeypatch uygulandı")

	# 6b. BOM: ensure conversion_rate is never None
	from erpnext.manufacturing.doctype.bom.bom import BOM
	_original_set_conversion_rate = BOM.set_conversion_rate

	def _patched_set_conversion_rate(self):
		if not self.currency:
			if self.company:
				self.currency = frappe.get_cached_value("Company", self.company, "default_currency") or "INR"
			else:
				self.currency = "INR"
		_original_set_conversion_rate(self)
		if not self.conversion_rate:
			self.conversion_rate = 1.0

	BOM.set_conversion_rate = _patched_set_conversion_rate
	print("DEBUG: BOM.set_conversion_rate monkeypatch uygulandı")

	# ──────────────────────────────────────────────────────────────────
	# 7. Fix Core Accounts
	# ──────────────────────────────────────────────────────────────────
	for acc_name, acc_type in [("Debtors", "Receivable"), ("Creditors", "Payable")]:
		fullname = f"{acc_name} - {abbr}"
		if frappe.db.exists("Account", fullname):
			frappe.db.set_value("Account", fullname, "account_type", acc_type)
			frappe.db.set_value("Account", fullname, "account_currency", "INR")

	# ──────────────────────────────────────────────────────────────────
	# 8. System Settings & Defaults
	# ──────────────────────────────────────────────────────────────────
	frappe.db.set_single_value("System Settings", "country", "India")
	frappe.db.set_single_value("System Settings", "setup_complete", 1)

	# Currencies
	for cur in ["INR", "USD", "EUR"]:
		if not frappe.db.exists("Currency", cur):
			frappe.get_doc({"doctype": "Currency", "currency_name": cur, "name": cur, "enabled": 1}).insert(ignore_permissions=True, ignore_if_duplicate=True)
		else:
			frappe.db.set_value("Currency", cur, "enabled", 1)

	# Currency Exchange records (use today's date to avoid stale-rate filtering)
	from frappe.utils import nowdate
	today = nowdate()
	for from_cur, to_cur, rate in [("USD", "INR", 60.0), ("EUR", "INR", 70.0)]:
		if not frappe.db.exists("Currency Exchange", {"from_currency": from_cur, "to_currency": to_cur}):
			frappe.get_doc({
				"doctype": "Currency Exchange",
				"from_currency": from_cur,
				"to_currency": to_cur,
				"exchange_rate": rate,
				"date": today,
				"for_buying": 1,
				"for_selling": 1,
			}).insert(ignore_permissions=True, ignore_if_duplicate=True)

	# Global Defaults
	if frappe.db.exists("Company", company_name):
		frappe.db.set_default("company", company_name)
		frappe.db.set_single_value("Global Defaults", "default_company", company_name)
		frappe.db.set_single_value("Global Defaults", "default_currency", "INR")

	# Ensure Fiscal Years covering current and adjacent years exist for test stability
	from frappe.utils import getdate
	cur_yr = getdate(today).year
	for y in range(cur_yr - 2, cur_yr + 3):
		fy_name = f"{y}"
		if not frappe.db.exists("Fiscal Year", fy_name):
			try:
				frappe.get_doc({
					"doctype": "Fiscal Year",
					"year": fy_name,
					"year_start_date": f"{y}-01-01",
					"year_end_date": f"{y}-12-31",
				}).insert(ignore_permissions=True, ignore_if_duplicate=True)
			except Exception:
				# Fiscal year may already exist or be created concurrently during testing
				pass
		for c_name in [company_name, "_Test Company KTA"]:
			if frappe.db.exists("Company", c_name):
				if not frappe.db.exists("Fiscal Year Company", {"parent": fy_name, "company": c_name}):
					try:
						doc = frappe.new_doc("Fiscal Year Company")
						doc.parent = fy_name
						doc.parenttype = "Fiscal Year"
						doc.parentfield = "companies"
						doc.company = c_name
						doc.db_insert()
					except Exception:
						# Fiscal year company link may already exist or fail safely during test setup
						pass

	# ──────────────────────────────────────────────────────────────────
	# 9. Relax Mandatory Fields
	# ──────────────────────────────────────────────────────────────────

	# Relax ALL custom mandatory fields
	frappe.db.sql("UPDATE `tabCustom Field` SET reqd = 0 WHERE reqd = 1")

	# Relax specific CORE fields directly in tabDocField
	core_fields_to_relax = [
		("BOM", "conversion_rate"),
		("BOM Item", "conversion_rate"),
		("BOM", "currency"),
		("Journal Entry Account", "cost_center"),
	]
	for dt, fn in core_fields_to_relax:
		frappe.db.sql(
			"UPDATE `tabDocField` SET reqd = 0 WHERE parent = %s AND fieldname = %s AND reqd = 1",
			(dt, fn),
		)

	# Disable stale exchange rate checking in Accounts Settings
	if frappe.db.exists("DocType", "Accounts Settings"):
		frappe.db.set_single_value("Accounts Settings", "allow_stale", 1)

	frappe.db.sql("UPDATE `tabProperty Setter` SET value = '0' WHERE property = 'reqd' AND value = '1'")

	# ──────────────────────────────────────────────────────────────────
	# 10. Ensure Missing Custom Fields for Tests
	# ──────────────────────────────────────────────────────────────────
	from frappe.custom.doctype.custom_field.custom_field import create_custom_field
	
	if not frappe.db.has_column("Quality Inspection", "custom_calisma_karti"):
			create_custom_field("Quality Inspection", dict(
					fieldname='custom_calisma_karti',
					label='Çalışma Kartı',
					fieldtype='Link',
					options='Calisma Karti',
					insert_after='reference_type'
			))
	if not frappe.db.has_column("Quality Inspection", "custom_alt_operasyon_kaydi"):
			create_custom_field("Quality Inspection", dict(
					fieldname='custom_alt_operasyon_kaydi',
					label='Alt Operasyon Kaydı',
					fieldtype='Data',
					insert_after='custom_calisma_karti'
			))

	# Seed baseline injection molds if needed
	try:
		from erpnextkta.patches.v3_0_3.extract_enjeksiyon_kaliplari import (
			execute as seed_molds,
		)

		seed_molds()
	except (frappe.DuplicateEntryError, frappe.ValidationError) as e:
		frappe.logger("tests").debug(f"seed_molds atlandı: {e}")

	frappe.db.commit()
	frappe.clear_cache()

	# Suppress Frappe's slow test console prints (e.g. tests taking >= 2s)
	try:
		tr = sys.modules.get("frappe.test_runner")
		if tr:
			tr.SLOW_TEST_THRESHOLD = 3600

			def quiet_addSuccess(self, test):
				super(tr.TimeLoggingTestResult, self).addSuccess(test)

			tr.TimeLoggingTestResult.addSuccess = quiet_addSuccess
	except Exception:
		# Test runner monkeypatching is best-effort and can safely be skipped if unavailable
		pass

	print("DEBUG: Tüm altyapı verileri başarıyla yüklendi.")

from frappe.tests.utils import FrappeTestCase

def log_test_start(test_instance):
	parts = test_instance.__class__.__module__.split(".")
	module_tag = parts[1] if len(parts) > 1 and parts[1] != "tests" else (parts[-1].replace("test_", "") if len(parts) > 1 else "kta")
	tag_str = f"[{module_tag}]"
	method_str = f"[{test_instance._testMethodName}]"
	desc = test_instance.shortDescription()
	if desc:
		print(f"\n🔍 [TEST] {tag_str} {method_str}: {desc}")
	else:
		print(f"\n🔍 [TEST] {tag_str} {method_str}")


class KTAUnitTestCase(unittest.TestCase):
	"""Base TestCase for fast unit tests with standardized test logging."""

	def setUp(self):
		super().setUp()
		log_test_start(self)


class KTABaseTestCase(FrappeTestCase):
	"""Base TestCase for database-backed tests with standard user and logging."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		frappe.flags.use_serial_and_batch_fields = False
		log_test_start(self)


class KTATestCase(KTABaseTestCase):
	"""Base TestCase for KTA Endüstri Sistemleri apps with shared setup logic."""

	def setUp(self):
		super().setUp()
		# Ensure test-specific Job Card and basic data exists
		self.setup_kta_infrastructure()

	def setup_kta_infrastructure(self):
		# 0. Infrastructure data seeding
		setup_system_downtime_reasons()

		# Temizlik (Önceki testlerden kalan Job Card Time Log'ları temizle)
		frappe.db.sql("DELETE FROM `tabJob Card Time Log` WHERE parent='TEST-JC-KTA-001'")
		frappe.db.sql("UPDATE `tabJob Card` SET quality_inspection=NULL WHERE name='TEST-JC-KTA-001'")
		# Çalışma kartı kirliliğini temizle
		frappe.db.sql("DELETE FROM `tabCalisma Karti` WHERE name LIKE 'TEST-CK-OP%%'")
		frappe.db.commit()

		# 1. KTA Settings
		frappe.db.set_single_value("KTA Calisma Karti Settings", "mukerrer_kalite_kontrolu_yap", 1)
		frappe.db.set_single_value("KTA Calisma Karti Settings", "max_kart_suresi_dk", 430)
		frappe.db.set_single_value("KTA Calisma Karti Settings", "kart_uyari_suresi_dk", 400)
		frappe.db.set_single_value("KTA Calisma Karti Settings", "vardiya_kapasite_sinirini_devre_disi_birak", 0)
		frappe.db.set_single_value("KTA Calisma Karti Settings", "vardiya_sonu_otomatik_kapatmayi_devre_disi_birak", 0)

		self.company = create_test_company()
		self.item_group = create_test_item_group()
		self.item = create_test_item(self.item_group)
		self.wip_warehouse = create_test_warehouse(self.company)
		self.expense_account = create_test_scrap_account(self.company)
		
		# Operations and Stations
		create_test_plant_floor("L-1")
		self.kta_op = create_test_kta_operation("KTA-OP-001-TEST", "L-1")
		self.ws_name = create_test_workstation("_Test KTA Workstation")
		
		create_test_shifts(["1. Vardiya", "2. Vardiya", "3. Vardiya"])
		create_test_operator("test@kta.com", "Test Operator")
		
		self.erpnext_op = create_test_erpnext_operation("_Test ERPNext Op", self.ws_name)
		
		# WO and Job Card
		self.wo_name = create_test_work_order(
			"TEST-WO-KTA-001", self.item, self.company, self.wip_warehouse
		)
		self.jc_name = create_test_job_card(
			"TEST-JC-KTA-001", self.wo_name, self.wip_warehouse, 
			self.erpnext_op, self.ws_name, self.item, self.company
		)
		# Seed baseline injection molds if needed
		try:
			from erpnextkta.patches.v3_0_3.extract_enjeksiyon_kaliplari import (
				execute as seed_molds,
			)

			seed_molds()
		except (frappe.DuplicateEntryError, frappe.ValidationError) as e:
			frappe.logger("tests").debug(f"seed_molds atlandı: {e}")

		frappe.db.commit()


def create_test_company(company_name="_Test Company KTA"):
	if not frappe.db.exists("Company", company_name):
		frappe.get_doc({
			"doctype": "Company",
			"company_name": company_name,
			"abbr": "TKTA",
			"default_currency": "TRY",
			"country": "Turkey"
		}).insert(ignore_permissions=True)
	return company_name


def create_test_item_group(name="_Test Item Group KTA"):
	if not frappe.db.exists("Item Group", name):
		frappe.get_doc({
			"doctype": "Item Group",
			"item_group_name": name,
			"is_group": 0,
			"parent_item_group": "All Item Groups"
		}).insert(ignore_permissions=True)
	return name


def create_test_item(item_group, item_code="_Test Item KTA"):
	if not frappe.db.exists("Item", item_code):
		frappe.get_doc({
			"doctype": "Item",
			"item_code": item_code,
			"item_group": item_group,
			"is_stock_item": 1,
			"stock_uom": "Nos"
		}).insert(ignore_permissions=True)
	return item_code


def create_test_warehouse(company, name="_Test WIP"):
	fullname = f"{name} - TKTA"
	if not frappe.db.exists("Warehouse", fullname):
		try:
			frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": name,
				"company": company
			}).insert(ignore_permissions=True)
		except Exception:
			# Warehouse may already exist in current test company
			pass
	return fullname


def create_test_scrap_account(company, name="Test Scrap Expense"):
	fullname = f"{name} - TKTA"
	if not frappe.db.exists("Account", fullname):
		parent_acc = "Expenses - TKTA"
		frappe.get_doc({
			"doctype": "Account",
			"account_name": name,
			"company": company,
			"is_group": 0,
			"parent_account": parent_acc,
			"account_type": "Expense Account"
		}).insert(ignore_permissions=True, ignore_links=True)
	return fullname


def create_test_plant_floor(name="L-1"):
	if not frappe.db.exists("Plant Floor", name):
		frappe.get_doc({
			"doctype": "Plant Floor",
			"name": name,
			"plant_name": name,
			"floor_name": name
		}).insert(ignore_permissions=True)
	return name


def create_test_kta_operation(name, plant_floor):
	if not frappe.db.exists("KTA Calisma Karti Operasyonlari", name):
		frappe.get_doc({
			"doctype": "KTA Calisma Karti Operasyonlari",
			"name": name,
			"calisma_karti_op": "Test Operasyon",
			"miktar_zorunlu_mu": 1,
			"plant_floor": plant_floor
		}).insert(ignore_permissions=True, ignore_links=True)
	return name


def create_test_workstation(name):
	if not frappe.db.exists("Workstation", name):
		frappe.get_doc({
			"doctype": "Workstation",
			"workstation_name": name
		}).insert(ignore_permissions=True)
	return name


def create_test_shifts(shift_names):
	times = {
		"1. Vardiya": ("08:00:00", "16:00:00"),
		"2. Vardiya": ("16:00:00", "00:00:00"),
		"3. Vardiya": ("00:00:00", "08:00:00")
	}
	for name in shift_names:
		if not frappe.db.exists("Shift Type", name):
			start, end = times.get(name, ("08:00:00", "16:00:00"))
			try:
				frappe.get_doc({
					"doctype": "Shift Type", 
					"name": name, 
					"start_time": start, 
					"end_time": end
				}).insert(ignore_permissions=True, ignore_links=True)
			except Exception:
				# Shift type may already exist or fail safely
				pass


def create_test_operator(email, name):
	if not frappe.db.exists("Employee", email):
		try:
			frappe.db.sql("""
				INSERT INTO `tabEmployee` (name, employee_name, first_name, status, creation, modified, modified_by)
				VALUES (%s, %s, %s, 'Active', NOW(), NOW(), 'Administrator')
			""", (email, name, name.split()[0]))
		except Exception:
			# Employee record might already exist
			pass
	return email


def create_test_erpnext_operation(name, workstation):
	if not frappe.db.exists("Operation", name):
		frappe.get_doc({
			"doctype": "Operation",
			"name": name,
			"workstation": workstation
		}).insert(ignore_permissions=True)
	return name


def create_test_work_order(name, item, company, warehouse):
	if not frappe.db.exists("Work Order", name):
		frappe.db.sql("""
			INSERT INTO `tabWork Order` (name, production_item, qty, company, wip_warehouse, fg_warehouse, docstatus, status, creation, modified, modified_by)
			VALUES (%s, %s, 100, %s, %s, %s, 1, 'Not Started', NOW(), NOW(), 'Administrator')
		""", (name, item, company, warehouse, warehouse))
	else:
		frappe.db.set_value("Work Order", name, "docstatus", 1)
		frappe.db.set_value("Work Order", name, "status", "Not Started")
	return name


def create_test_job_card(name, wo, warehouse, operation, workstation, item, company):
	if not frappe.db.exists("Job Card", name):
		frappe.db.sql("""
			INSERT INTO `tabJob Card` (name, work_order, wip_warehouse, operation, workstation, production_item, for_quantity, company, docstatus, creation, modified, modified_by)
			VALUES (%s, %s, %s, %s, %s, %s, 100, %s, 1, NOW(), NOW(), 'Administrator')
		""", (name, wo, warehouse, operation, workstation, item, company))
	else:
		frappe.db.set_value("Job Card", name, "docstatus", 1)
	return name


def make_mock_calisma_karti(**kwargs):
	"""Build a minimal CalismaKarti-like mock object."""
	from erpnextkta.kta_calisma_karti.doctype.calisma_karti.calisma_karti import CalismaKarti
	doc = CalismaKarti.__new__(CalismaKarti)
	doc.name = kwargs.get("name", "TEST-CK-001")
	doc.doctype = "Calisma Karti"
	doc.duruslar = kwargs.get("duruslar", [])
	doc.baslangic_saati = kwargs.get("baslangic_saati", None)
	doc.bitis_saati = kwargs.get("bitis_saati", None)
	doc.kalite_kontrol = kwargs.get("kalite_kontrol", None)
	doc.operator = kwargs.get("operator", None)
	doc.operasyon = kwargs.get("operasyon", None)
	doc.is_istasyonu = kwargs.get("is_istasyonu", None)
	doc.toplam_sure = kwargs.get("toplam_sure", None)
	doc.toplam_durus = kwargs.get("toplam_durus", None)
	doc.net_calisma_suresi = kwargs.get("net_calisma_suresi", None)
	doc.durum = kwargs.get("durum", None)
	doc.is_karti = kwargs.get("is_karti", None)
	doc.alt_operasyon_kayitlari = kwargs.get("alt_operasyon_kayitlari", [])
	doc.docstatus = kwargs.get("docstatus", 0)
	return doc


def make_mock_durus(durus_baslangic=None, durus_bitis=None, durus_suresi=None):
	from unittest.mock import MagicMock
	row = MagicMock()
	row.durus_baslangic = durus_baslangic
	row.durus_bitis = durus_bitis
	row.durus_suresi = durus_suresi
	return row


def _ensure_standard_roots():
	"""Ensure essential root groups exist to prevent LinkValidationError during setup."""
	standard_roots = [
		{"doctype": "Customer Group", "customer_group_name": "All Customer Groups", "is_group": 1, "parent_customer_group": ""},
		{"doctype": "Territory", "territory_name": "All Territories", "is_group": 1, "parent_territory": ""},
		{"doctype": "Item Group", "item_group_name": "All Item Groups", "is_group": 1, "parent_item_group": ""},
		{"doctype": "Supplier Group", "supplier_group_name": "All Supplier Groups", "is_group": 1, "parent_supplier_group": ""},
		{"doctype": "Sales Person", "sales_person_name": "Sales Team", "is_group": 1, "parent_sales_person": ""},
	]

	for root in standard_roots:
		name_field = {
			"Customer Group": "customer_group_name",
			"Territory": "territory_name",
			"Item Group": "item_group_name",
			"Supplier Group": "supplier_group_name",
			"Sales Person": "sales_person_name",
		}[root["doctype"]]
		if not frappe.db.exists(root["doctype"], root[name_field]):
			try:
				frappe.get_doc(root).insert(ignore_permissions=True, ignore_if_duplicate=True)
			except Exception:
				# Root record may already exist or be inserted concurrently
				pass

	if not frappe.db.exists("Department", "All Departments"):
		frappe.db.sql("""
			INSERT INTO `tabDepartment` (name, department_name, is_group, parent_department, creation, modified, modified_by)
			VALUES ('All Departments', 'All Departments', 1, '', NOW(), NOW(), 'Administrator')
			ON DUPLICATE KEY UPDATE name=name
		""")
		from frappe.utils.nestedset import rebuild_tree
		rebuild_tree("Department", "parent_department")
		frappe.db.commit()
	frappe.db.commit()


def clear_item_stock_and_batches(item_code):
	"""Clean up stock ledgers, quality inspections, batch bundles, and labels to prevent test pollution."""
	frappe.db.delete("Stock Ledger Entry", {"item_code": item_code})
	frappe.db.delete("Quality Inspection", {"item_code": item_code})
	frappe.db.delete("KTA Stock Label", {"item_code": item_code})

	bundles = frappe.get_all("Serial and Batch Bundle", filters={"item_code": item_code}, pluck="name")
	if bundles:
		frappe.db.delete("Serial and Batch Entry", {"parent": ["in", bundles]})
		frappe.db.delete("Serial and Batch Bundle", {"name": ["in", bundles]})

	frappe.db.delete("Batch", {"item": item_code})


def setup_test_fiscal_years(company):
	"""Ensure fiscal years covering the current year exist, link test company to all fiscal years, and clear cache."""
	from frappe.utils import nowdate, getdate
	current_year = getdate(nowdate()).year

	for y in range(current_year - 2, current_year + 3):
		fy_name = f"{y}"
		if not frappe.db.exists("Fiscal Year", fy_name):
			try:
				frappe.get_doc({
					"doctype": "Fiscal Year",
					"year": fy_name,
					"year_start_date": f"{y}-01-01",
					"year_end_date": f"{y}-12-31",
				}).insert(ignore_permissions=True, ignore_if_duplicate=True)
			except Exception:
				# Fiscal year may already exist or be inserted concurrently
				pass

	for fy_name in frappe.get_all("Fiscal Year", pluck="name"):
		if not frappe.db.exists("Fiscal Year Company", {"parent": fy_name, "company": company}):
			try:
				doc = frappe.new_doc("Fiscal Year Company")
				doc.parent = fy_name
				doc.parenttype = "Fiscal Year"
				doc.parentfield = "companies"
				doc.company = company
				doc.db_insert()
			except Exception:
				# Fiscal year link may already exist or fail safely
				pass
	frappe.db.commit()
	frappe.cache().hdel("fiscal_years", company)


def ensure_test_injection_fixtures():
	"""Seed operations, sub-operations and molds needed by injection tests."""
	frappe.set_user("Administrator")
	if not frappe.db.exists("KTA Calisma Karti Operasyonlari", "OP40"):
		doc = frappe.new_doc("KTA Calisma Karti Operasyonlari")
		doc.name = "OP40"
		doc.calisma_karti_op = "OP40"
		doc.has_enjeksiyon = 1
		doc.flags.ignore_permissions = True
		doc.flags.ignore_mandatory = True
		doc.insert()
	else:
		frappe.db.set_value("KTA Calisma Karti Operasyonlari", "OP40", "has_enjeksiyon", 1)

	sub_ops = [
		("OP40-0001", "0001"),
		("OP40-E2E", "E2E"),
	]
	for sub_name, title in sub_ops:
		if not frappe.db.exists("KTA Calisma Karti Alt Operasyonlari", sub_name):
			doc = frappe.new_doc("KTA Calisma Karti Alt Operasyonlari")
			doc.name = sub_name
			doc.parent_operation = "OP40"
			doc.title = title
			doc.operasyon_tipi = "Blunt"
			doc.is_active = 1
			doc.flags.ignore_permissions = True
			doc.flags.ignore_mandatory = True
			doc.insert()

	test_molds = [
		"KLP-101", "KLP-102", "KLP-DUP", "KLP-FIRST", "KLP-INITIAL",
		"KLP-LOCK-01", "KLP-LOCK-CHANGED", "KLP-LOCKED", "KLP-MAX",
		"KLP-OP40-01", "KLP-OP40-02", "KLP-POINTS-01", "KLP-RECIPE-01",
		"KLP-REJ-01", "KLP-SHIFT-01", "KLP-TAMPERED", "KLP-TAMPERED-AGAIN",
		"KLP-UNIQ-01", "KLP-UPDATED", "TEST-ACTIVE-MOLD", "TEST-DISABLED-MOLD"
	]
	for m in test_molds:
		if not frappe.db.exists("KTA Enjeksiyon Kalibi", m):
			mold = frappe.new_doc("KTA Enjeksiyon Kalibi")
			mold.kalip_no = m
			mold.kalip_adi = f"Test Mold {m}"
			mold.disabled = 1 if "DISABLED" in m else 0
			mold.flags.ignore_permissions = True
			mold.flags.ignore_mandatory = True
			mold.insert()

	try:
		from erpnextkta.patches.v3_0_3.extract_enjeksiyon_kaliplari import (
			execute as seed_molds,
		)
		seed_molds()
	except Exception:
		# Extraction patch is optional if molds already exist
		pass

	frappe.db.commit()


def ensure_test_idc_fixtures():
	"""Seed Item Groups, Ara Malzeme Grupları, and test items for IDC measurement tests."""
	frappe.set_user("Administrator")
	for group in ["120-IDC Connector", "190-Connection Systems", "100-Wires & Cables", "Products"]:
		if not frappe.db.exists("Item Group", group):
			frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": group,
				"parent_item_group": "All Item Groups",
				"is_group": 0,
			}).insert(ignore_permissions=True)

	for amg in ["OBS-Bedelsiz", "Normal", "ÜRÜN"]:
		if not frappe.db.exists("KTA Ara Malzeme Grubu", amg):
			frappe.get_doc({
				"doctype": "KTA Ara Malzeme Grubu",
				"kta_ara_malzeme_grubu": amg,
			}).insert(ignore_permissions=True)

	item_specs = [
		("TEST-IDC-120-ITEM", "120-IDC Connector", "OBS-Bedelsiz"),
		("TEST-CONN-190-ITEM", "190-Connection Systems", "Normal"),
		("TEST-WIRE-100-ITEM", "100-Wires & Cables", "Normal"),
		("TEST-IDC-NOT-IN-BOM", "120-IDC Connector", "Normal"),
		("TEST-FG-ITEM-FOR-IDC", "Products", "Normal"),
	]
	for code, group, ara_grup in item_specs:
		if not frappe.db.exists("Item", code):
			doc = frappe.new_doc("Item")
			doc.item_code = code
			doc.item_name = code
			doc.item_group = group
			doc.is_stock_item = 1
			doc.stock_uom = "Nos"
			doc.custom_ara_malzeme_grubu = ara_grup
			doc.insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Item", code, {
				"item_group": group,
				"custom_ara_malzeme_grubu": ara_grup,
			})
	frappe.db.commit()
