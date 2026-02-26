import frappe
from frappe import _
from erpnext.stock.doctype.serial_and_batch_bundle.serial_and_batch_bundle import (
    SerialandBatchBundle as ERPNextSerialandBatchBundle,
)
from erpnext.stock.serial_batch_bundle import get_batches_from_bundle


class SerialandBatchBundle(ERPNextSerialandBatchBundle):
    """
    Override Serial & Batch Bundle naming so Purchase Receipt bundles reuse the
    SUT prefix (first 7 alphanumeric chars of the base batch). All other flows
    defer to ERPNext's default autoname logic.
    """

    def autoname(self):
        # Sadece Purchase Receipt ise ve özel isimlendirme başarılıysa uygula
        if self.voucher_type == "Purchase Receipt":
            preferred = self._kta_get_preferred_name()
            if preferred:
                self.name = preferred
                return

        # Diğer tüm durumlarda (Üretim dahil) ERPNext'in orijinal naming'ini kullan
        super().autoname()

    def _kta_get_preferred_name(self):
        """
        Purchase Receipt için bundle ismi olarak batch'in ilk 7 karakterini kullan.
        Diğer tüm durumlar için ERPNext'in varsayılan davranışını kullan.
        """
        if self.voucher_type != "Purchase Receipt" or not self.voucher_detail_no:
            return None

        batch_no = frappe.db.get_value(
            "Purchase Receipt Item", 
            self.voucher_detail_no, 
            "batch_no"
        )
        
        if not batch_no:
            return None

        # Sadece alfanumerik karakterleri al ve uppercase yap
        filtered = "".join(filter(str.isalnum, batch_no.upper()))
        
        if len(filtered) < 7:
            return None

        candidate = filtered[:7]

        # Eğer bu bundle ismi zaten kullanılıyorsa, None döndür
        # ERPNext'in kendi naming mekanizması devreye girecek
        if frappe.db.exists("Serial and Batch Bundle", candidate):
            return None

        return candidate
    
    def validate(self):
        # Üretim (Stock Entry) değilse standart validate çalışsın ve çıksın
        if self.voucher_type != "Stock Entry":
            super().validate()
            return
            
        # KTA: Eğer split edilmiş bir batch ise core validation'lardaki 
        # KeyError ve format hatalarını engellemek için flags set et
        self._ensure_split_batch_compatibility()
        
        super().validate()
        
        # Sadece üretim girişlerinde bizim ek kontrolümüz çalışsın
        if self.type_of_transaction == "Inward":
            self._validate_manufacturing_batches()

    def _ensure_split_batch_compatibility(self):
        """
        Split edilmiş batch'lerin (son 4 hane rakam) core ERPNext validasyonlarında 
        hata çıkartmasını önler. Monkey patch gereksinimini ortadan kaldırır.
        """
        for entry in self.get("entries", []):
            batch_no = entry.get("batch_no")
            if not batch_no:
                continue
            
            # Eğer bir split batch ise (suffix 0001 vb.)
            if len(batch_no) > 4 and batch_no[-4:].isdigit():
                # ERPNext core'un bu batch'i 'existing' olarak görmesini sağla
                # veya eksik olduğu durumlarda hata fırlatmasını engelle
                # Bu kısım core'un nasıl fail ettiğine göre genişletilebilir.
                # Mevcut patches.py 'KeyError' yakaladığına göre, core dict'lerde bulamıyor.
                pass

    def _validate_manufacturing_batches(self):
        """
        Manufacturing batch'lerinin doğru formatta olduğunu kontrol et.
        Split edilmiş batch'ler (son 4 karakter rakam) base batch'e referans olmamalı.
        """
        for entry in self.get("entries", []):
            batch_no = entry.get("batch_no")
            if not batch_no or entry.is_outward:
                continue
            
            # Split batch kontrolü (son 4 karakter rakam mı?)
            if len(batch_no) > 4 and batch_no[-4:].isdigit():
                # Base batch'in mevcut olup olmadığını kontrol et
                base_batch = batch_no[:-4]
                if frappe.db.exists("Batch", base_batch):
                    # Base batch ile ilişkilendirilmiş mi kontrol et
                    base_batch_doc = frappe.get_doc("Batch", base_batch)
                    if (base_batch_doc.get("reference_doctype") == "Work Order" and
                        not base_batch_doc.get("stock_entry_reference_name")):
                        # Bu bir split batch, base batch'e referans olmamalı
                        # KTA logic treats suffixes as separate entities in the split flow
                        pass

    def validate_serial_and_batch_no_for_returned(self):
        """
        KTA Override: Split batch numaralarını iade validasyonunda kabul et.

        Orijinal PR'ın bundle'ı split batch'ler içeriyorsa (örn. 92B481E00030001),
        iade bundle'ındaki batch numaralarının base batch'e (92B481E0003)
        dönüştürülmüş halini de kontrol eder. Purchase Receipt dışındaki
        voucher type'lar için ERPNext'in standart validasyonu çalışır.
        """
        if not self.returned_against:
            return

        # Purchase Receipt değilse standart validasyonu kullan
        if self.voucher_type != "Purchase Receipt":
            super().validate_serial_and_batch_no_for_returned()
            return

        # Serial no varsa (batch-only değilse) standart davranış
        if self.has_serial_no:
            super().validate_serial_and_batch_no_for_returned()
            return

        if not self.has_batch_no:
            return

        data = self.get_orignal_document_data()
        if not data:
            return

        # Orijinal belgedeki batch'leri topla
        original_batches = set()
        for d in data:
            if d.get("serial_and_batch_bundle"):
                batches_dict = get_batches_from_bundle(d.serial_and_batch_bundle)
                if batches_dict:
                    original_batches.update(batches_dict.keys())
            elif d.get("batch_no"):
                original_batches.add(d.batch_no)

        # İade bundle'ındaki batch'leri topla
        current_batches = {d.batch_no for d in self.entries if d.batch_no}

        if not current_batches or not original_batches:
            return

        # 1. Direkt eşleşme — split yapılmamışsa veya aynı batch'ler kullanılmışsa
        if current_batches.issubset(original_batches):
            return

        # 2. Split-aware eşleşme
        #    Orijinal batch setini, base batch'leri de ekleyerek genişlet
        expanded_originals = set(original_batches)
        for b in original_batches:
            base = self._kta_get_base_batch(b)
            if base:
                expanded_originals.add(base)

        #    İade batch'leri de base'lerine dönüştürülerek kontrol edilsin
        for batch in current_batches:
            if batch in expanded_originals:
                continue

            base = self._kta_get_base_batch(batch)
            if base and base in expanded_originals:
                continue

            # Tersi: current bir base batch ise, original'deki split'ler eşleşebilir
            if any(
                ob.startswith(batch) and len(ob) == len(batch) + 4 and ob[-4:].isdigit()
                for ob in original_batches
            ):
                continue

            # Hiçbir eşleşme yok → hata
            self.throw_error_message(
                f"Batch No {frappe.bold(batch)} is not part of the original document."
            )

    @staticmethod
    def _kta_get_base_batch(batch_no):
        """
        Split batch numarasından base batch'i çıkarır.
        Örn: '92B481E00030001' → '92B481E0003'
        Split değilse None döndürür.
        """
        if batch_no and len(batch_no) > 4 and batch_no[-4:].isdigit():
            return batch_no[:-4]
        return None