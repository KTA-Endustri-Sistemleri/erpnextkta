import frappe
from erpnext.manufacturing.doctype.job_card.job_card import JobCard

class KTAJobCard(JobCard):
    def get_overlap_for(self, args, open_job_cards=None):
        if frappe.db.get_single_value("Manufacturing Settings", "disable_capacity_planning"):
            return {}
        return super().get_overlap_for(args, open_job_cards)

    def validate_sequence_id(self):
        if self.flags.get("kta_sync_mode"):
            return
        return super().validate_sequence_id()
