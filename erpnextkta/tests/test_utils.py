import frappe

def before_tests():
	"""
	Seed infrastructure needed by ERPNext (and erpnextkta) tests 
	before the test runner starts creating record dependencies.
	"""
	print("\nDEBUG: Running erpnextkta.tests.test_utils.before_tests hook...")
	from erpnext.setup.setup_wizard.operations import install_fixtures
	
	# Check if root groups exist, if not, install fixtures
	if not frappe.db.exists("Item Group", "All Item Groups"):
		print("DEBUG: Root groups missing. Installing ERPNext fixtures...")
		install_fixtures.install("Turkey")
		frappe.db.commit()
		frappe.clear_cache()
		print("DEBUG: Fixtures installed successfully.")
	else:
		print("DEBUG: Root groups already exist.")
