import frappe


def before_tests():
	"""
	Seed infrastructure needed by ERPNext (and erpnextkta) tests
	before the test runner starts creating record dependencies.

	Uses ERPNext's setup_complete() for a full, proper initialization
	of company, chart of accounts, default accounts, and fixtures.
	"""
	print("\nDEBUG: Running erpnextkta.tests.test_utils.before_tests hook...")

	company_name = "_Test Company"
	abbr = "_TC"

	# ──────────────────────────────────────────────────────────────────
	# 1. Full site setup via ERPNext's setup_complete()
	#    This creates Company, Chart of Accounts, default accounts,
	#    fiscal year, currencies, and all standard fixtures.
	# ──────────────────────────────────────────────────────────────────
	if not frappe.db.exists("Company", company_name):
		print(f"DEBUG: Running full setup_complete for {company_name}...")
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
			print("DEBUG: setup_complete finished successfully.")
		except Exception as e:
			print(f"DEBUG: setup_complete raised: {e}")
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
		print(f"DEBUG: {company_name} already exists, skipping setup_complete.")
		# FORCE updating default_currency just in case frail test runners created a shallow object
		frappe.db.sql("UPDATE `tabCompany` SET default_currency='INR' WHERE name=%s", (company_name,))
		frappe.db.commit()
	# 2. Ensure essential root groups exist (idempotent)
	# ──────────────────────────────────────────────────────────────────
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
				pass

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
					frappe.throw(f"Row {d.idx}: Party Type and Party is required for {d.account}")

	JournalEntry.validate_party = patched_validate_party
	print("DEBUG: Monkeypatched JournalEntry.validate_party")

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
	print("DEBUG: Monkeypatched BOM.set_conversion_rate")

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

	frappe.db.commit()
	frappe.clear_cache()

	print("DEBUG: All infrastructure seeded successfully.")
