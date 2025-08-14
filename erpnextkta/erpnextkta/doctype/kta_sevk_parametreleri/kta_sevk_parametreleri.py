from frappe.model.document import Document

class KTASevkParametreleri(Document):
    def autoname(self):
        self.name = f"{self.customer_name} - {self.customer_address}"
        self.custom_deliver_parameter_name = self.name