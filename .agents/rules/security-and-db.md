---
trigger: always_on
---

# Security & Database

* Always write queries using the Frappe ORM (`frappe.db.get_value`, `frappe.get_doc`, etc.).
* Avoid direct raw SQL queries unless absolutely necessary. When using `frappe.db.sql`, always use parameterized queries to prevent SQL injection.