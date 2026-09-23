from erpnext.stock.doctype.material_request.material_request import MaterialRequest
from frappe.desk.form.assign_to import _add as add_assign
import frappe

class KTAMaterialRequest(MaterialRequest):
    def after_insert(self):
        if hasattr(super(), "after_insert"):
            super().after_insert()
        if self.material_request_type == "Manufacture" and self.docstatus == 0:
            self._assign_from_rule("Material Request for Re-Order (Draft)")

    def submit(self, *args, **kwargs):
        # ERPNext'in standart otomatik "reorder" mekanizması (reorder_item.py)
        # Material Request'leri oluştururken doğrudan "submit" komutu gönderir
        # ve o esnada ignore_mandatory = True flag'ini set eder.
        # Biz KTA mantığında bunların (özellikle Üretim/Manufacture tiplerinin)
        # "Draft" (Taslak) kalmasını istediğimiz için
        # eger bu flag aktifse ve tip Manufacture ise submit işlemini atlıyoruz.
        if getattr(self.flags, "ignore_mandatory", False) and self.material_request_type == "Manufacture":
            return

        super().submit(*args, **kwargs)

    def on_submit(self):
        if hasattr(super(), "on_submit"):
            super().on_submit()
        if self.material_request_type == "Manufacture":
            self._close_open_todos()
            self._assign_from_rule("Material Request for Re-Order")

    def on_update(self):
        if hasattr(super(), "on_update"):
            super().on_update()
        if self.material_request_type == "Manufacture" and self.docstatus == 1:
            if self.per_ordered >= 100:
                self._close_open_todos()

    def update_completed_qty(self, mr_items=None, update_modified=True):
        if hasattr(super(), "update_completed_qty"):
            super().update_completed_qty(mr_items, update_modified)
            
        if self.material_request_type == "Manufacture" and self.docstatus == 1:
            per_ordered = frappe.db.get_value("Material Request", self.name, "per_ordered") or 0
            if per_ordered >= 100:
                self._close_open_todos()

    def _assign_from_rule(self, rule_name):
        if not frappe.db.exists("Assignment Rule", rule_name):
            return
            
        rule = frappe.get_doc("Assignment Rule", rule_name)
        user = rule.get_user(self)
        if user:
            try:
                add_assign({
                    "assign_to": [user],
                    "doctype": self.doctype,
                    "name": self.name,
                    "description": frappe.render_template(rule.description or "Atama: {{ name }}", self.as_dict())
                }, ignore_permissions=True)
            except Exception as e:
                frappe.log_error(f"Error assigning MR {self.name} via rule {rule_name}: {e}", "KTA Assignment Error")

    def _close_open_todos(self):
        todos = frappe.get_all("ToDo", filters={
            "reference_type": self.doctype,
            "reference_name": self.name,
            "status": "Open"
        }, pluck="name")
        
        for t in todos:
            todo = frappe.get_doc("ToDo", t)
            todo.status = "Closed"
            todo.save(ignore_permissions=True)
