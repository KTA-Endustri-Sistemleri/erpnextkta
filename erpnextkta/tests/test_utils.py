import frappe

def before_tests():
	"""
	Seed infrastructure needed by ERPNext (and erpnextkta) tests 
	before the test runner starts creating record dependencies.
	"""
	print("\nDEBUG: Running erpnextkta.tests.test_utils.before_tests hook...")
	# 1. Warehouse Types (Essential for Company/Warehouse creation)
	for wt in ["Transit", "Work In Progress", "Finished Goods"]:
		if not frappe.db.exists("Warehouse Type", wt):
			frappe.get_doc({
				"doctype": "Warehouse Type",
				"name": wt
			}).insert(ignore_permissions=True, ignore_if_duplicate=True)
	
	# 2. Other global infrastructure can be added here if needed
	
	frappe.db.commit()
