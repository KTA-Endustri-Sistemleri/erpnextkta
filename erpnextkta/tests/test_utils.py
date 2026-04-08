import frappe

def before_tests():
	"""
	Seed infrastructure needed by ERPNext (and erpnextkta) tests 
	before the test runner starts creating record dependencies.
	"""
	print("\nDEBUG: Running erpnextkta.tests.test_utils.before_tests hook...")
	from erpnext.setup.setup_wizard.setup_wizard import setup_complete
	
	# Check if setup is already complete to avoid re-running
	if not int(frappe.db.get_single_value('System Settings', 'setup_complete') or 0):
		print("DEBUG: System setup not complete. Running setup_complete...")
		args = frappe._dict({
			'language': 'English',
			'email': 'admin@example.com',
			'full_name': 'Administrator',
			'country': 'Turkey',
			'timezone': 'Europe/Istanbul',
			'currency': 'TRY',
			'company_name': 'KTA',
			'company_abbr': 'KTA',
			'chart_of_accounts': 'Standard Alternative', # Safe default for Turkey
			'fy_start_date': '2024-01-01',
			'fy_end_date': '2024-12-31',
			'setup_complete': 1
		})
		
		# Ensure some lower-level dependencies are met
		frappe.db.set_single_value('System Settings', 'country', 'Turkey')
		
		setup_complete(args)
		
		# Mark setup as complete in DB manually if setup_complete didn't do it
		frappe.db.set_single_value('System Settings', 'setup_complete', 1)
		frappe.db.commit()
		frappe.clear_cache()
		print("DEBUG: setup_complete finished successfully.")
	else:
		print("DEBUG: System setup already marked as complete.")
