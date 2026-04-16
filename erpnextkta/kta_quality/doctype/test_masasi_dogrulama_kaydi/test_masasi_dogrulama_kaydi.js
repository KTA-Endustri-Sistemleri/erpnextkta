frappe.ui.form.on('Test Masasi Dogrulama Kaydi', {
    refresh: function(frm) {
        if (frm.is_new()) {
            frm.events.doldur_sabit_satirlar(frm);
        }
    },
    
    doldur_sabit_satirlar: function(frm) {
        let changed = false;

        const SABIT_KRITERLER = [
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
            "Test masasındaki yazılı tanımlandırmaların, uygulama ve uyarı şekillerinin üstü kullanım sırasında yıpranmaya karşı şeffaf bir bant ile korunmaya alınmış mı?"
        ];

        const BAGLANTI_NOKTASI_SATIRLAR = [
            "Kilit Sistemi",
            "Uç Sayısı",
            "Poke-Yoke",
            "Board Görsel",
            "Board Çizim"
        ];

        if (!frm.doc.degerlendirme_kriterleri || frm.doc.degerlendirme_kriterleri.length === 0) {
            SABIT_KRITERLER.forEach((kriter, i) => {
                let row = frm.add_child('degerlendirme_kriterleri');
                row.sira_no = i + 1;
                row.kriter_metni = kriter;
            });
            changed = true;
        }

        if (!frm.doc.baglanti_noktasi_tablosu || frm.doc.baglanti_noktasi_tablosu.length === 0) {
            BAGLANTI_NOKTASI_SATIRLAR.forEach((tanim, i) => {
                let row = frm.add_child('baglanti_noktasi_tablosu');
                row.sira_no = i + 1;
                row.tanim = tanim;
            });
            changed = true;
        }

        if (!frm.doc.uygulama_metni) {
            frm.set_value('uygulama_metni', "BU FORM, İLK DEVREYE ALMA SIRASINDA, MAKİNENİN REVİZYONU VE PROSES AKIŞI SIRASINDA BELİRLENEN PERİYOTLARDA YAPILACAK OLAN KONTROLERDE KULLANILIR. HER UYGUNSUZLUK İÇİN DÇF VE BERABER BİR ARIZA BİLDİRİM FORMU AÇILIR VE SONUÇLANDIRILINÇAYA KADAR MASA ONAYLANMAZ. MAKİNENİN ONAYLANMASI İÇİN UYGUNSUZLUKLARIN TAMAMIN GİDERİLMESİ GEREKLİDİR. UYGUN OLDUĞU TESPİT EDİLEN TEST ve FORM MASASI PTR 07/005 NUMARALI FORM DOLDURULARAK ONAYLANIR. AYNI İŞLEM UYGUN OLDUĞU TESPİT EDİLEN MONTAJ APARATI İÇİN DE PTR 07/0212 NUMARALI FORM DOLDURULARAK TEKRARLANIR.");
        }

        if (changed) {
            frm.refresh_field('degerlendirme_kriterleri');
            frm.refresh_field('baglanti_noktasi_tablosu');
        }
    }
});
