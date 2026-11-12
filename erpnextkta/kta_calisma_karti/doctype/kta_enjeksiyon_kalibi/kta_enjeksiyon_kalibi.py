# Copyright (c) 2026, KTA Endustri Sistemleri and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class KTAEnjeksiyonKalibi(Document):
    def validate(self):
        if self.kalip_no:
            self.kalip_no = self.kalip_no.strip()
        if not self.kalip_adi and self.kalip_no:
            self.kalip_adi = f"{self.kalip_no} Enjeksiyon Kalıbı"
