---
trigger: always_on
---

# Naming Conventions

* **DocTypes:** Always singular, Title Case, separated by spaces (e.g., `Sales Invoice`).
* **Fields:** Slugged version of the label, lowercase, using underscores (e.g., label "Customer Name" -> field `customer_name`).
* **Link Fields:** The field name should match the name of the linked DocType in lowercase (e.g., link to `Employee` -> `employee`).
* **Variables:**
  * Use the slugged version of the DocType name for document objects (e.g., `sales_order = frappe.get_doc('Sales Order', ...)`).
  * Use `_name` suffix for variable names holding a document's key/ID (e.g., `sales_order_name`).
  * In loops over child tables, use `d` to reference the row object (e.g., `for d in self.items:`).