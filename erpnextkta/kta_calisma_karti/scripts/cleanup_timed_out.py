"""
Geçmiş timed-out kartları normalize eder.
Kullanım (bench console):
    %run /opt/frappe/frappe-bench/apps/erpnextkta/erpnextkta/kta_calisma_karti/scripts/cleanup_timed_out.py
"""
from erpnextkta.tasks import auto_close_timed_out_cards

print("auto_close_timed_out_cards başlatılıyor...")
auto_close_timed_out_cards()
print("Tamamlandı.")
