import frappe
from frappe.model.document import Document

SABIT_KRITERLER = [
    "Test masası elektriksel bağlantıları uygun mu?",
    "Test masası üstünde, işin doğru ve çabuk yapılabilmesi için anlaşılabilir işaretler ve uyarıcı yazılar kullanılmış mı?",
    "Test masası üzerinde test masası numarası var mı?",
    "Yapılan işaretler ve yazılar anlaşılır ve okunaklı mı?",
    "Tüm Soket ve Komponentler için gerekli 3D yazıcıyla POKE-YOKE ler yapılmış mı?",
    "Varlık kontrollü var mı ve switchler yaylı pim olarak mevcut mu?",
    "Soket ve komponentlerin takılacağı yuva ve pimler sağlam bir şekilde monte edilmiş ve işin yapılması sırasında gevşememesi sağlanmış mı?",
    "Test masasında kullanılan pimlerin kablo, kontak ve soket gibi üründe kullanılan parçalara zarar vermeyecek şekilde olmasına dikkat edilmiş mi?",
    "Test masası üzerinde hedef noktalarda kablo renkleri belirtilmiş mi?",
    "Renk kodlamaları ve etiketler doğru mu?",
    "Test masası üzerinde hedef noktalar birbirinden farklı olarak numaralandırılmış mı?",
    "Test masasındaki yazılı tanımlandırmaların, uygulama ve uyarı şekillerinin üstü kullanım sırasında yıpranmaya karşı şeffaf bir bant ile korunmaya alınmış mı?",
]

BAGLANTI_NOKTASI_SATIRLAR = [
    "Kilit Sistemi",
    "Uç Sayısı",
    "Poke-Yoke",
    "Board Görsel",
    "Board Çizim",
]


class TestMasasiDogrulamaKaydi(Document):
    def before_insert(self):
        self._doldur_sabit_satirlar()

    def validate(self):
        if not self.uygulama_metni:
            self.uygulama_metni = (
                "BU FORM, İLK DEVREYE ALMA SIRASINDA, MAKİNENİN REVİZYONU VE PROSES AKIŞI "
                "SIRASINDA BELİRLENEN PERİYOTLARDA YAPILACAK OLAN KONTROLERDE KULLANILIR. "
                "HER UYGUNSUZLUK İÇİN DÇF VE BERABER BİR ARIZA BİLDİRİM FORMU AÇILIR VE "
                "SONUÇLANDIRILINÇAYA KADAR MASA ONAYLANMAZ. MAKİNENİN ONAYLANMASI İÇİN "
                "UYGUNSUZLUKLARIN TAMAMIN GİDERİLMESİ GEREKLİDİR. UYGUN OLDUĞU TESPİT EDİLEN "
                "TEST ve FORM MASASI PTR 07/005 NUMARALI FORM DOLDURULARAK ONAYLANIR. AYNI İŞLEM "
                "UYGUN OLDUĞU TESPİT EDİLEN MONTAJ APARATI İÇİN DE PTR 07/0212 NUMARALI FORM "
                "DOLDURULARAK TEKRARLANIR."
            )

    def on_submit(self):
        # Update the parent Calisma Karti if a reference exists
        if self.calisma_karti_ref:
            frappe.db.set_value("Calisma Karti", self.calisma_karti_ref, "test_masasi_dogrulama_kaydi", self.name)
            frappe.db.commit()

    def after_insert(self):
        # Since submit is not checked in the current permission structure from JSON, we use after_insert/on_update
        if self.calisma_karti_ref:
            frappe.db.set_value("Calisma Karti", self.calisma_karti_ref, "test_masasi_dogrulama_kaydi", self.name)
            frappe.db.commit()

    def on_update(self):
        if self.calisma_karti_ref:
            frappe.db.set_value("Calisma Karti", self.calisma_karti_ref, "test_masasi_dogrulama_kaydi", self.name)
            frappe.db.commit()

    def _doldur_sabit_satirlar(self):
        if not self.degerlendirme_kriterleri:
            for i, kriter in enumerate(SABIT_KRITERLER, start=1):
                self.append("degerlendirme_kriterleri", {
                    "sira_no": i,
                    "kriter_metni": kriter,
                    "cevap": None,
                })

        if not self.baglanti_noktasi_tablosu:
            for i, tanim in enumerate(BAGLANTI_NOKTASI_SATIRLAR, start=1):
                self.append("baglanti_noktasi_tablosu", {
                    "sira_no": i,
                    "tanim": tanim,
                    "durum": None,
                })


@frappe.whitelist()
def get_item_customer_group(item_code):
    customer_group = frappe.db.get_value(
        "Item Customer Detail", {"parent": item_code}, "customer_group"
    )
    return customer_group
