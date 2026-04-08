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
			frappe.get_doc({"doctype": "Warehouse Type", "name": wt, "warehouse_type": wt}).insert(ignore_permissions=True)
	
	# 2. Root Groups (Essential for Company/Setup creation)
	roots = [
		{"doctype": "Customer Group", "name": "All Customer Groups", "is_group": 1},
		{"doctype": "Territory", "name": "All Territories", "is_group": 1},
		{"doctype": "Item Group", "name": "All Item Groups", "is_group": 1},
	]
	
	for root in roots:
		if not frappe.db.exists(root["doctype"], root["name"]):
			frappe.get_doc(root).insert(ignore_permissions=True)

	frappe.db.commit()
