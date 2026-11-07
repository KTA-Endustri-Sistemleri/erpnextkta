---
layout: default
title: "KTA Çalışma Kartı Mimarisi ve Algoritma Akışı"
---

<main class="container" markdown="1">

# 📐 KTA Çalışma Kartı Mimarisi ve Algoritma Akışı

Bu doküman, `erpnextkta` uygulaması altındaki **`kta_calisma_karti`** modülü ve Vue tabanlı ön yüzünün (UI); sistem ayarlarından (`KTA Calisma Karti Settings`), ana operasyon yapılandırmalarına (`KTA Calisma Karti Operasyonlari`), alt operasyon kurallarına (`KTA Calisma Karti Alt Operasyonlari`), ERPNext Job Card eşleştirme motoruna ve malzeme grubu miras zincirine kadar tüm yaşam döngüsünü içeren eksiksiz mimari akış şemasıdır.

---

## 1. Uçtan Uca Mermaid Akış Şeması

```mermaid
flowchart TD
%% ─────────────────────────────────────────────────────────────
%% 0. SİSTEM, OPERASYON VE ALT OPERASYON YAPILANDIRMASI
%% ─────────────────────────────────────────────────────────────
    subgraph S0 ["0. SİSTEM, OPERASYON VE ALT OPERASYON MASTER AYARLARI"]
        direction TB
        
        subgraph S0_Settings ["KTA Calisma Karti Settings (Genel Sistem Ayarları)"]
            Set_General["• <b>max_kart_suresi_dk:</b> Vardiya net süre tavanı (örn: 430 dk)<br/>• <b>kart_uyari_suresi_dk:</b> Proaktif turuncu ikaz süresi (örn: 400 dk)<br/>• <b>tolerans_saat:</b> Tamamlanmış İş Emri kart açabilme toleransı (örn: 8 saat)<br/>• <b>kart_gecis_modu:</b> Sıkı (Hard) / Esnek (Soft)<br/>• <b>ariza_devam_modu:</b> Katı (Hard) / Esnek (Soft)<br/>• <b>mukerrer_kalite_kontrolu_yap:</b> 1 / 0 (Mükerrer QI ve Test Masası koruması)<br/>• <b>job_card_time_log_sync_modu:</b> Kapalı / Esnek (Soft) / Sıkı (Hard)<br/>• <b>hurda_gider_hesabi:</b> Hurda Stock Entry gider hesabı"]:::settingsNode
        end

        subgraph S0_Op ["KTA Calisma Karti Operasyonlari (Ana Operasyon Ayarları)"]
            Op_Master["• <b>calisma_karti_op & sequence:</b> Operasyon adı ve sıra<br/>• <b>erpnext_operations:</b> ERPNext Operasyon Eşleştirmeleri (Table)<br/>  <i>(erpnext_operation + production_item eşleme matrisi)</i><br/>• <b>allowed_material_groups:</b> Ana operasyon izinli malzeme grupları (Table)<br/>  <i>(item_group + hammadde_sira: Tümü / 1 / 2 / 3)</i><br/>• <b>board_dogrulamasi_gerektirir:</b> Test masası doğrulama şartı (1/0)<br/>• <b>customer_group & plant_floor:</b> Müşteri ve fabrika katı zorunluluğu<br/>• <b>miktar_zorunlu_mu:</b> Kart bitirilirken miktar > 0 zorunluluğu (1/0)<br/>• <b>ekran_tipi:</b> Tekli Hammadde / Çoklu Hammadde (3 hammaddeye kadar)<br/>• <b>has_krimp, has_idc, has_barkod, has_enjeksiyon:</b> Aktif form modülleri<br/>• <b>alt_operasyon_bazli_kalite:</b> Alt operasyon seviyesinde kalite (1/0)<br/>• <b>yuzde_yuz_kalite_kontrol:</b> %100 denetim zorunluluğu (1/0)<br/>• <b>tuketim_limiti_aktif:</b> WO BOM limitleri + Hurda toleransı denetimi (1/0)"]:::settingsNode
        end

        subgraph S0_SubOp ["KTA Calisma Karti Alt Operasyonlari (Alt Operasyon Ayarları)"]
            SubOp_Master["• <b>parent_operation:</b> Bağlı olduğu ana operasyon<br/>• <b>title & sequence:</b> Alt operasyon başlığı ve sıralama numarası<br/>• <b>is_active:</b> Aktif / Pasif durumu<br/>• <b>operasyon_tipi:</b> 'Blunt' / 'Tek Taraf' / 'Çift Taraf' (Krimp yön/terminal kuralı)<br/>• <b>is_tuketim_hesaplanir:</b> Tüketim Hesaplanır mı? (1/0)<br/>  <i>(Metre biriminde boyut_1_mm zorunluluğu ve adet*boyut/1000 formülü)</i><br/>• <b>allowed_material_groups:</b> Alt operasyona özel malzeme grupları (Table)<br/>  <i>(item_group + hammadde_sira: Tümü / 1 / 2 / 3)</i>"]:::settingsNode
        end
    end

%% ─────────────────────────────────────────────────────────────
%% 1. KART YARATMA & ERPNEXT EŞLEŞTİRME MOTORU (create.py)
%% ─────────────────────────────────────────────────────────────
    subgraph S1 ["1. KART YARATMA VE ERPNEXT OPERASYON EŞLEŞTİRME (create.py)"]
        UI_Start(["Operatör Girişi & Sihirbaz (UI)"]):::uiNode
        --> Select_JC["İş Kartı (Job Card) Seçimi"]
        
        Select_JC --> Match_Engine{"ERPNext Operasyon Eşleştirme Motoru<br/>(get_operations_for_job_card)"}
        
        Match_Engine -- "Öncelik 1: Tam Eşleşme" --> Match_P1["erpnext_operation == jc.operation<br/>VE production_item == jc.production_item<br/>(Ürüne Özel Operasyon Eşleşmesi)"]:::successNode
        Match_Engine -- "Öncelik 2: Genel Operasyon" --> Match_P2["erpnext_operation == jc.operation<br/>VE production_item BOŞ<br/>(Operasyon Seviyesinde Genel Eşleşme)"]:::infoNode
        Match_Engine -- "Öncelik 3: Eşlemesiz Genel" --> Match_P3["erpnext_operations tablosu BOŞ olan KTA Operasyonları<br/>(Tüm İş Kartlarına Açık Genel Operasyonlar)"]:::uiNode

        Match_P1 --> Filtered_Op_List["Operatöre Sunulan KTA Operasyon Listesi"]
        Match_P2 --> Filtered_Op_List
        Match_P3 --> Filtered_Op_List

        Filtered_Op_List --> Input_Select["İstasyon ve Operatör Seçimi"]
        --> Chk_Dup{"Mükerrer Koruma:<br/>Aynı JC + Op + Operatör için<br/>açık ve aktif kart var mı?"}
        
        Chk_Dup -- "Evet" --> Ret_Existing["Mevcut Açık Kartı Yükle<br/>(_is_existing = True)"]:::successNode
        --> UI_LoadCard(["Kart Detay Ekranını Yükle"]):::uiNode

        Chk_Dup -- "Hayır" --> Val_Req{"Zorunlu Alanlar Dolu mu?<br/>(is_karti, operasyon, is_istasyonu)"}
        Val_Req -- "Hayır" --> Err_Req["Hata: Eksik Zorunlu Alan"]:::errNode
        Val_Req -- "Evet" --> Chk_WO_Status{"İş Emri Durumu Nedir?"}
        
        Chk_WO_Status -- "Cancelled / Taslak" --> Err_WO_Status["Hata: İş Emri Geçersiz"]:::errNode
        Chk_WO_Status -- "In Process / Not Started" --> Val_WO_Tolerance
        Chk_WO_Status -- "Completed" --> Chk_Completed_Tol{"Settings.tolerans_saat<br/>Aşıldı mı?"}
        
        Chk_Completed_Tol -- "Tolerans Aşıldı" --> Err_WO_Tol["Hata: Tamamlanmış İş Emri Tolerans Süresi Doldu"]:::errNode
        Chk_Completed_Tol -- "Tolerans İçi" --> Val_WO_Tolerance{"İş Emri Fazla Üretim<br/>Toleransı Uygun mu?"}
        
        Val_WO_Tolerance -- "Aşıldı" --> Err_Tolerance["Hata: Tolerans Miktarı Aşıldı"]:::errNode
        Val_WO_Tolerance -- "Uygun" --> Calc_Shift["Vardiya Hesapla (find_shift_for_time)<br/>00:00=2.Vardiya, 08:00=3.Vardiya, 16:00=1.Vardiya"]
        --> Ins_CK["Calisma Karti Oluştur (docstatus=0)<br/>durum = 'Hazır', baslangic_saati = NULL"]
        --> Pub_Create["Realtime Event Yayınla (doc:create_calisma_karti)"]
        --> UI_LoadCard
    end

%% ─────────────────────────────────────────────────────────────
%% 2. ÇALIŞMA DÖNGÜSÜ & DURUM MAKİNESİ (cards.py / islem_yap)
%% ─────────────────────────────────────────────────────────────
    subgraph S2 ["2. ÇALIŞMA DÖNGÜSÜ & DURUM MAKİNESİ (cards.py)"]
        UI_LoadCard --> State_Check{"Kart Durumu?"}

        %% BAŞLAT
        State_Check -- "Hazır" --> Btn_Baslat["UI: 'Başlat' Butonu"]:::btnNode
        Btn_Baslat --> Act_Baslat["islem_yap('Baslat')"]
        Act_Baslat --> Check_Gecis_Modu{"Settings.kart_gecis_modu<br/>'Sıkı (Hard)' mı?"}
        
        Check_Gecis_Modu -- "Evet" --> Chk_Incomplete{"Operatörün Başka Açık Kartında<br/>Eksik Veri Var mı?"}
        Chk_Incomplete -- "Eksik Var" --> Err_Hard1["Hata: Önceki karttaki eksik verileri tamamlayın!"]:::errNode
        Chk_Incomplete -- "Eksik Yok" --> Set_Start
        Check_Gecis_Modu -- "Esnek (Soft)" --> Set_Start["baslangic_saati = now<br/>Operatörün diğer açık kartlarını 'Auto-Pause' yap<br/>(Settings.auto_pause_durus_nedeni ile)"]
        --> Durum_Calisiyor["durum = 'Çalışıyor'<br/>UI: Yeşil Çip (#059669) + Nabız Noktası"]:::workingNode

        %% SÜRE KONTROLLERİ
        Durum_Calisiyor --> Timer_Warn{"Geçen Süre ><br/>Settings.kart_uyari_suresi_dk?"}
        Timer_Warn -- "Evet" --> Show_Warn["UI: ⚠️ Proaktif Turuncu İkaz Göster"]:::warningNode
        Timer_Warn -- "Hayır" --> Operator_Actions{"Operatör / Denetçi İşlemleri"}

        %% DURUŞA GEÇİŞ
        Operator_Actions -- "Duruşa Geç" --> Btn_Durus["UI: 'Duruş' Butonu"]:::btnNode
        Btn_Durus --> Modal_Durus["Duruş Nedeni Seç (Arıza, Mola, Malzeme Bekleme, Ayar, Diğer)"]
        --> Act_Durus["islem_yap('Durus', durus_nedeni, aciklama)"]
        Act_Durus --> Val_Durus_Diger{"Neden 'Diğer' mi?"}
        Val_Durus_Diger -- "Evet ve Açıklama Yok" --> Err_Durus["Hata: 'Diğer' seçildiğinde açıklama zorunludur!"]:::errNode
        Val_Durus_Diger -- "Uygun" --> App_Durus["duruslar tablosuna satır ekle<br/>durus_baslangic = now"]
        --> Check_Ariza{"Duruş Nedeni == 'Arıza' mı?"}
        
        Check_Ariza -- "Evet" --> Handle_Ariza["Arıza Bakımı Başlat:<br/>• Asset Maintenance Task & Log üret<br/>• Takvim etkinliği oluştur<br/>UI: 'DURUŞTA (ARIZA)' (#e11d48, Pulsing Kırmızı Nokta)"]:::arizaNode
        Check_Ariza -- "Hayır" --> Handle_NormalDurus["UI: 'DURUŞTA' (#d97706, Sabit Amber Çerçeve)"]:::pauseNode
        Handle_Ariza --> Durum_Durusta["durum = 'Duruşta'"]
        Handle_NormalDurus --> Durum_Durusta

        %% DEVAM ET
        Durum_Durusta --> Btn_Devam["UI: 'Devam Et' Butonu"]:::btnNode
        Btn_Devam --> Act_Devam["islem_yap('DevamEt')"]
        Act_Devam --> Check_Ariza_Resume{"Duruş Nedeni 'Arıza' mı?"}
        
        Check_Ariza_Resume -- "Evet" --> Check_Ariza_Modu{"Settings.ariza_devam_modu<br/>'Katı (Hard)' mı?"}
        Check_Ariza_Modu -- "Katı (Hard)" --> Check_AML_Open{"Asset Maintenance Log<br/>Kapatıldı mı?"}
        Check_AML_Open -- "Hayır (Hala Açık)" --> Err_Ariza_Block["Hata: Bakım ekibi arızayı kapatmadan devam edilemez!"]:::errNode
        Check_AML_Open -- "Evet (Kapandı)" --> Close_Durus_Row
        Check_Ariza_Modu -- "Esnek (Soft)" --> Close_Durus_Row
        Check_Ariza_Resume -- "Normal Duruş" --> Close_Durus_Row["Son duruş satırını kapat:<br/>durus_bitis = now, durus_suresi hesapla"]
        --> Durum_Calisiyor
    end

%% ─────────────────────────────────────────────────────────────
%% 3. ALT OPERASYON, MALZEME GRUBU MİRASI VE TÜKETİM (S3)
%% ─────────────────────────────────────────────────────────────
    subgraph S3 ["3. MALZEME GRUBU MİRAS ZİNCİRİ, ALT OPERASYON VE ÖZEL FORMLAR"]
        Operator_Actions -- "Alt Operasyon Ekle" --> Select_SubOp["Alt Operasyon Seçimi (KTA Calisma Karti Alt Operasyonlari)"]
        
        %% MALZEME GRUBU MİRAS MOTORU (_helpers.py)
        Select_SubOp --> Resolve_Groups{"Malzeme Grubu Miras Motoru<br/>(_helpers.py: get_allowed_items_with_groups)"}
        
        Resolve_Groups -- "Alt Operasyon Grupları DOLU" --> Use_SubOp_Only["<b>Yalnızca Alt Operasyon Gruplarını Kullan:</b><br/>ao_doc.allowed_material_groups<br/>(Hammadde Sırasına Göre Filtrele: Tümü / 1 / 2 / 3)"]:::successNode
        
        Resolve_Groups -- "Alt Operasyon Grupları BOŞ" --> Cascade_Inheritance["<b>Kademeli Miras Al:</b><br/>1. Kendinden önceki tüm alt operasyonların grupları (sequence <= current)<br/>2. Ana operasyonun allowed_material_groups tablosu"]:::infoNode
        
        Use_SubOp_Only --> Filter_WO_Items["İş Emri BOM Kalemlerini Filtrele:<br/>Sadece eşleşen Item Group'lar açılır"]
        Cascade_Inheritance --> Filter_WO_Items
        
        Filter_WO_Items --> Check_SubOp_Type{"Alt Operasyon: operasyon_tipi?"}
        
        Check_SubOp_Type -- "Blunt" --> SubOp_Blunt["Uçsuz Kesim (Terminal yok)"]
        Check_SubOp_Type -- "Tek Taraf" --> SubOp_Single["Tek Yön Terminal / Krimp"]
        Check_SubOp_Type -- "Çift Taraf" --> SubOp_Double["Çift Yön Terminal / Krimp (Yön 2 Aktif)"]
        
        SubOp_Blunt --> Check_Ekran_Tipi
        SubOp_Single --> Check_Ekran_Tipi
        SubOp_Double --> Check_Ekran_Tipi{"Operasyon: ekran_tipi?"}

        Check_Ekran_Tipi -- "Tekli Hammadde" --> Form_Single["Tek Hammadde + Adet"]
        Check_Ekran_Tipi -- "Çoklu Hammadde" --> Form_Multi["3 Hammaddeye Kadar Eşzamanlı Matris<br/>(Hammadde 1, 2, 3 slot kısıtları)"]
        
        Form_Single --> Check_Tuketim_Bayrak{"Alt Operasyon: is_tuketim_hesaplanir?"}
        Form_Multi --> Check_Tuketim_Bayrak
        
        Check_Tuketim_Bayrak -- "1 (Aktif) ve UOM=='Metre'" --> Val_Boyut["boyut_1_mm Zorunlu!<br/>Tüketim = adet * boyut_1_mm / 1000"]
        Check_Tuketim_Bayrak -- "0 (Pasif) veya Adet Birimi" --> Val_Tuketim_Limit_Bayrak{"Operasyon: tuketim_limiti_aktif<br/>Açık mı (1)?"}
        Val_Boyut --> Val_Tuketim_Limit_Bayrak

        Val_Tuketim_Limit_Bayrak -- "1 (Açık)" --> Val_WO_Limits{"Toplam Sarfiyat ><br/>İş Emri Miktarı + Hurda Toleransı?"}
        Val_WO_Limits -- "Aşıyor" --> Err_WO_Limits["Hata: İş Emri hammadde tüketim limiti aşılıyor!"]:::errNode
        Val_WO_Limits -- "Limit İçi" --> Save_SubOp_Row
        Val_Tuketim_Limit_Bayrak -- "0 (Kapalı)" --> Bypass_Limit["Limit Kontrolü Atlandı (Bypass)"]:::infoNode
        --> Save_SubOp_Row["Alt operasyon satırı ekle (aok):<br/>quality_inspection_status = 'Onay Bekliyor'"]:::infoNode

        Save_SubOp_Row --> Natural_Sort["<b>Doğal Sıralama Motoru (natural_sort_key):</b><br/>• Satır No (1, 2, 10 ve '1,2,3' çoklu kesim formatları)<br/>• Enjeksiyonda Kalıp No doğal sıralaması"]:::successNode
        --> Special_Forms{"Özel Operasyon Formları"}

        %% ÖZEL FORMLAR
        Special_Forms -- "Krimp Formu (has_krimp==1)" --> Form_Krimp["krimp.py: add_krimp_olcumu<br/>• İletken Krimp Yüksekliği (Hedef vs Ölçülen)<br/>• İzokrimp Yüksekliği, Çekme Kuvveti (N), Çapak Boyu<br/>• Radüs, Tel Kesme ve Çift Yön Parametreleri"]
        
        Special_Forms -- "IDC Formu (has_idc==1)" --> Form_IDC["qc.py: add_idc_olcumu<br/>• BOM'daki 120, 110, 190 grubu IDC Soketleri<br/>• IDC Ölçümleri ve Görsel Doğrulamalar"]
        
        Special_Forms -- "Enjeksiyon Formu (has_enjeksiyon==1)" --> Form_Enj["enjeksiyon.py: add_enjeksiyon_olcumu<br/>• Kalıp No (Zorunlu)<br/>• Kazan, Hortum, Meme ve Soğuk Su Isıları<br/>• Motor Devri, Enjeksiyon & Soğutma Süreleri<br/>• KTA Enjeksiyon Toleransları Cetveli Kıyaslaması"]
        
        Special_Forms -- "Barkod Kaydı (has_barkod==1)" --> Form_Barcode["barcode.py: add_barkod_kaydi<br/>• Makara / Paket Barkod Okutma ve Doğrulama"]

        Operator_Actions -- "Hurda Kaydı" --> Add_Hurda["hurda.py: add_hurda"]
        Add_Hurda --> Cascade_Hurda_Groups["<b>Hurda Malzeme Grubu Zinciri:</b><br/>Önceki tüm ana operasyonlar + bağlı tüm alt operasyonların<br/>malzeme grupları taranarak geçerli hurda kalemleri listelenir"]
        --> Check_BOM_Item{"Parça bu operasyon zincirinde izinli mi?"}
        Check_BOM_Item -- "Hayır" --> Err_BOM_Item["Hata: İzinli olmayan hurda parçası!"]:::errNode
        Check_BOM_Item -- "Evet" --> Check_Scrap_Account["Settings.hurda_gider_hesabi ve Masraf Merkezi Al"]
        --> Create_Scrap_SE["ERPNext Stock Entry (Material Issue/Scrap) Oluştur ve SUBMIT Et"]:::successNode
    end

%% ─────────────────────────────────────────────────────────────
%% 4. KALİTE KONTROL, KARARLAR & KISMİ KABUL (S4)
%% ─────────────────────────────────────────────────────────────
    subgraph S4 ["4. KALİTE KONTROL, KARARLAR VE KISMİ KABUL (qc.py)"]
        Operator_Actions -- "Kalite Muayenesi" --> Check_Op_QC_Mode{"Operasyon: alt_operasyon_bazli_kalite<br/>Açık mı?"}

        %% STANDART KART BAZLI KALİTE
        Check_Op_QC_Mode -- "Kapalı (0) - Kart Bazlı" --> Card_QC_Flow["submit_standard_qc (rowname = NULL)"]
        Card_QC_Flow --> Card_QC_Decision{"Kalite Kararı?"}
        Card_QC_Decision -- "Kabul (Approve)" --> Card_Approve["kalite_kontrol = 'Onaylandı'<br/>QI Belgesi Taslak Olarak Bağlanır"]
        Card_QC_Decision -- "Ret (Reject)" --> Card_Reject["finalize_rejected_card:<br/>• QI SUBMIT edilir (docstatus=1)<br/>• Kart bitis_saati atanır, durum = 'Reddedildi'<br/>• KART SUBMIT EDİLİR VE ERKEN KAPANIR!"]:::errNode

        %% ALT OPERASYON BAZLI KALİTE
        Check_Op_QC_Mode -- "Açık (1) - Alt Op Bazlı" --> SubOp_QC_UI["UI: Her Satırda Bağımsız Karar Butonları<br/>• Yeşil: 'Kalite Onayı Ver'<br/>• Kırmızı: 'Reddet'"]
        SubOp_QC_UI --> SubOp_Decision{"Denetçi Kararı?"}
        
        SubOp_Decision -- "Onaylandı" --> Sub_Approve["Satır: quality_inspection_status = 'Onaylandı'<br/>QI Belgesi Taslak (docstatus=0) Olarak Bağlanır"]
        SubOp_Decision -- "Reddedildi" --> Sub_Reject["Satır: quality_inspection_status = 'Reddedildi'<br/>QI Belgesi Hemen SUBMIT Edilir (docstatus=1)<br/><b>KART AÇIK KALIR! (Kilitlenmez / Erken Kapanmaz)</b>"]
        
        Sub_Approve --> Rollup_Logic["qc.py: _update_parent_qc_status_from_alt_ops"]
        Sub_Reject --> Rollup_Logic
        
        Rollup_Logic --> Check_All_Rows{"Karttaki Tüm Alt Operasyon Satırlarının Durumu?"}
        Check_All_Rows -- "Tümü 'Onaylandı'" --> QC_Roll_Approved["Kart QC: 'Onaylandı' (Zümrüt Yeşili)"]:::successNode
        Check_All_Rows -- "Tümü 'Reddedildi'" --> QC_Roll_Rejected["Kart QC: 'Reddedildi' (Kırmızı)"]:::errNode
        Check_All_Rows -- "Hem Onaylı Hem Reddedilmiş Satır Var" --> QC_Roll_Partial["Kart QC: 'Kısmi Kabul Edildi'<br/><b>(ERP Standardı Mor / İndigo #7c3aed)</b>"]:::partialNode
        Check_All_Rows -- "Açıkta Bekleyen Var (Kart Çalışıyor/Duruşta)" --> QC_Roll_Pending["Kart QC: 'Onay Bekliyor' (Mavi)"]:::infoNode
        Check_All_Rows -- "Açıkta Bekleyen Var + En Az 1 Onay (Kart Bittiğinde)" --> QC_Roll_Finish_Partial["Kart QC: 'Kısmi Kabul Edildi'<br/><b>(Örnekleme Muayenesi Tamamlandı)</b>"]:::partialNode
    end

%% ─────────────────────────────────────────────────────────────
%% 5. BİTİRME, VALIDASYONLAR & ERP ENTEGRASYONU (S5)
%% ─────────────────────────────────────────────────────────────
    subgraph S5 ["5. BİTİRME VE ERPNEXT ENTEGRASYONU (cards.py / _handle_bitis)"]
        Operator_Actions -- "Kartı Bitir" --> Btn_Finish["UI: 'Bitir' Butonu"]:::btnNode
        QC_Roll_Approved --> Btn_Finish
        QC_Roll_Partial --> Btn_Finish
        QC_Roll_Finish_Partial --> Btn_Finish
        
        Btn_Finish --> Check_Finish_Pre{"Bitirme Ön Koşulları"}
        Check_Finish_Pre --> Chk_Already_Finished{"Kart Zaten Bitmiş mi?<br/>(bitis_saati, docstatus=1 veya durum bitmis/reddedildi)"}
        Chk_Already_Finished -- "Evet" --> Err_Already_Finished["Hata: Bu kart zaten bitmiş!"]:::errNode
        Chk_Already_Finished -- "Hayır" --> Chk_Has_SubOp{"En az bir alt operasyon<br/>kaydı var mı?"}
        Chk_Has_SubOp -- "Hayır" --> Err_Finish_NoSubOp["Hata: En az bir alt operasyon kaydı bulunmalıdır!"]:::errNode
        Chk_Has_SubOp -- "Evet" --> Chk_QC_Mode{"Operasyon: yuzde_yuz_kalite_kontrol?<br/>(1: %100 Kontrol | 0: Örnekleme)"}
        
        Chk_QC_Mode -- "1: %100 Kalite Kontrol" --> Val_QC_100{"Açıkta 'Onay Bekliyor' Satır Var mı?"}
        Val_QC_100 -- "Evet (Bekleyen Var)" --> Err_QC100["Hata: %100 kontrolde açıkta bekleyen satır varken kart bitirilemez!"]:::errNode
        Val_QC_100 -- "Hayır (Tümü Denetlenmiş)" --> Val_QC_100_Approve{"En az 1 satır Onaylı mı?"}
        Val_QC_100_Approve -- "Hayır (Tümü Ret)" --> Err_QC100_NoApprove["Hata: Kartın bitirilebilmesi için en az bir alt işlem onay almalıdır!"]:::errNode
        Val_QC_100_Approve -- "Evet" --> Chk_Mukerrer_QC
        
        Chk_QC_Mode -- "0: Örnekleme Muayenesi" --> Val_QC_Sample{"En az 1 satır Kalite Onayı almış mı?"}
        Val_QC_Sample -- "Hayır (Hiç Onay Yok)" --> Err_Sample_NoApprove["Hata: Onaysız kart kapatılamaz! En az bir alt işlem onaylanmalıdır."]:::errNode
        Val_QC_Sample -- "Evet (Minimum 1 Onay)" --> Set_Sample_Partial["Kalan satırlar beklese bile kart bitirilebilir<br/>(Kart QC: 'Kısmi Kabul Edildi' olarak kesinleşir)"]:::partialNode
        Set_Sample_Partial --> Chk_Mukerrer_QC
        
        Chk_Mukerrer_QC{"Settings.mukerrer_kalite_kontrolu_yap?<br/>Açık mı?"}
        Chk_Mukerrer_QC -- "Açık ve Belge Başka Kartta Kullanılmış" --> Err_Mukerrer["Hata: Kalite Muayene Belgesi başka kartta kullanılmış!"]:::errNode
        Chk_Mukerrer_QC -- "Uygun" --> Exec_Finish_Process
        
        Exec_Finish_Process["_handle_bitis Çalıştırılır:<br/>1. Varsa açık duruş kapatılır (durus_bitis = now)<br/>2. bitis_saati = now atanır<br/>3. hesapla_toplam_sure: Settings.max_kart_suresi_dk ve vardiya kapasite sınırı uygulanır"]
        --> Auto_Submit_All_QIs["<b>Otomatik QI Kapatma (_submit_linked_quality_inspection):</b><br/>Ana karttaki ve doc.alt_operasyon_kayitlari tablosundaki<br/>TÜM taslak (docstatus=0) QI belgeleri SUBMIT edilir (docstatus=1)"]:::successNode
        --> Update_Parent_QC["_update_parent_qc_status_from_alt_ops:<br/>Bitiş ile Kısmi Kabul Edildi / Onaylandı kesinleşir"]
        --> Submit_CK_Doc["Calisma Karti SUBMIT Edilir (docstatus=1)<br/>durum = 'Bitmiş' (Tüm satırlar ret ise 'Reddedildi')"]
        
        Submit_CK_Doc --> Hook_Submit["calisma_karti.py: on_submit()"]
        --> Chk_JC_Sync_Modu{"Settings.job_card_time_log_sync_modu?"}
        
        Chk_JC_Sync_Modu -- "Kapalı" --> Skip_JC_Sync["Job Card Süre Senkronizasyonu Atlanır"]
        Chk_JC_Sync_Modu -- "Esnek / Sıkı" --> Sync_JC_TimeLog["job_card_sync.py: sync_time_log_to_job_card<br/>Job Card'a Net Çalışma Süresi Time Log Satırı Ekle<br/>Job Card tamamlanan miktarını güncelle"]:::successNode
    end

%% ─────────────────────────────────────────────────────────────
%% 6. ZAMANLANMIŞ GÖREVLER (tasks.py)
%% ─────────────────────────────────────────────────────────────
    subgraph S6 ["6. VARDİYA BİTİMİ VE ARKA PLAN GÖREVLERİ (tasks.py)"]
        Cron_Shift["Zamanlanmış Görev: close_open_cards_for_shift<br/>(Her gün 00:00, 08:00, 16:00 vardiya sınırlarında)"]
        --> Scan_Open["Açık Kalan Kartları Tara (bitis_saati IS NULL, docstatus < 2)"]
        --> Filter_Cards{"Kart Tipi ve QC Durumu?"}
        Filter_Cards -- "Klasik QC Reddedildi" --> Skip_Close["Klasik ret kartı: Erken kapatıldığı için atla"]
        Filter_Cards -- "Alt Operasyonlu Açık Kart veya Normal Kart" --> Auto_Close_Shift["Açık duruşu kapat<br/>bitis_saati = vardiya_hedef_saati<br/>Settings.timeout_durus_nedeni ile 0 süreli kayıt ekle<br/>KARTLARI OTOMATİK SUBMIT ET"]:::warningNode
    end


%% Stil Tanımları
    classDef settingsNode fill:#f1f5f9,stroke:#475569,stroke-width:2px,color:#0f172a;
    classDef btnNode fill:#2563eb,stroke:#1d4ed8,stroke-width:2px,color:#ffffff;
    classDef uiNode fill:#f8fafc,stroke:#64748b,stroke-width:2px,color:#0f172a;
    classDef workingNode fill:#ecfdf5,stroke:#059669,stroke-width:2px,color:#065f46;
    classDef pauseNode fill:#fffbeb,stroke:#d97706,stroke-width:2px,color:#92400e;
    classDef arizaNode fill:#fff1f2,stroke:#e11d48,stroke-width:3px,color:#9f1239;
    classDef partialNode fill:#f5f3ff,stroke:#7c3aed,stroke-width:2px,color:#5b21b6;
    classDef successNode fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#14532d;
    classDef infoNode fill:#eff6ff,stroke:#3b82f6,stroke-width:2px,color:#1e40af;
    classDef warningNode fill:#fff7ed,stroke:#ea580c,stroke-width:2px,color:#9a3412;
    classDef errNode fill:#fef2f2,stroke:#dc2626,stroke-width:2px,color:#991b1b;
```

---

## 2. ERPNext Eşleştirme Motoru ve Malzeme Grubu Miras Algoritmaları

### 2.1. ERPNext Operasyon Eşleştirme Motoru (`erpnext_operations`)
Bir operatör veya amir sihirbazda bir İş Kartı (Job Card) seçtiğinde, `create.py` altındaki `get_operations_for_job_card(job_card_name)` fonksiyonu şu **3 aşamalı öncelik sırasını** çalıştırır:

1. **Öncelik 1 (Ürüne ve Operasyona Özel Eşleşme - Specific Match):**
   * Koşul: `erpnext_operation == jc.operation` **VE** `production_item == jc.production_item`.
   * Eğer bu koşulu sağlayan KTA Operasyonları varsa, liste filtrelenir ve yalnızca bu operasyonlar döndürülür.
2. **Öncelik 2 (Genel Operasyon Eşleşmesi - Operation-Generic Match):**
   * Koşul: `erpnext_operation == jc.operation` **VE** `production_item` boş bırakılmış (`""`).
   * Üründen bağımsız olarak ilgili ERPNext operasyonunu karşılayan tüm genel KTA operasyonları döndürülür.
3. **Öncelik 3 (Tam Genel Fallback - Fully Generic Match):**
   * Koşul: `erpnext_operations` tablosunda **hiçbir satır tanımlanmamış** olan genel KTA Operasyonları.
   * Bu operasyonlar her türlü Job Card altında evrensel olarak kullanılabilir.

---

### 2.2. Malzeme Grubu Filtreleme ve Kademeli Miras Zinciri (`allowed_material_groups`)
Alt operasyon ekleme veya hammadde arama sırasında (`_helpers.py: get_allowed_items_with_groups`), seçilebilecek hammadde listesi şu hiyerarşik algoritma ile daraltılır:

1. **Alt Operasyon Düzeyi Önceliği:**
   * Seçilen alt operasyonun (`KTA Calisma Karti Alt Operasyonlari`) `allowed_material_groups` tablosu taranır.
   * Tabloda `item_group` ve `hammadde_sira` (`Tümü`, `Hammadde 1`, `Hammadde 2`, `Hammadde 3`) alanları kontrol edilir.
   * **Eğer alt operasyonda grup tanımlanmışsa:** Yalnızca bu alt operasyonun grupları geçerli sayılır.
2. **Kademeli Miras (Cascade Inheritance):**
   * **Eğer alt operasyonda grup tanımlanmamışsa:**
     1. İlgili ana operasyona bağlı ve `sequence <= secilen_alt_op.sequence` olan **kendisinden önceki tüm alt operasyonların** grupları toplanır.
     2. Ana operasyonun (`KTA Calisma Karti Operasyonlari`) `allowed_material_groups` tablosundaki tüm gruplar toplanır.
     3. Tüm gruplar birleştirilerek tekil bir izin listesi oluşturulur.
3. **Hurda Malzeme Grubu Zinciri:**
   * Hurda kaydında `alt_operasyon` bulunmadığı için zincir ana operasyon üzerinden geriye doğru yürütülür:
     * Kendisine eşit veya daha küçük `sequence` numarasına sahip **tüm önceki ana operasyonlar** ve bu ana operasyonlara bağlı **tüm alt operasyonların** izinli malzeme grupları harmanlanır.
4. **İş Emri BOM Eşleştirmesi:**
   * Elde edilen nihai `allowed_groups` kümesi, İş Emri'nin `required_items` listesindeki parçaların `item_group` alanlarıyla eşleştirilir.
   * Operatörün karşısına yalnızca bu filtreyi geçen hammadde kalemleri getirilir; izinli olmayan parçaların kartta sarf edilmesi engellenir.

---

### 2.3. Alt Operasyon Doğal Sıralaması (Natural Sort - Satır No ve Enjeksiyon Kalıp No)
Kablo kesim, krimp ve montaj işlemlerinde operatörler aynı veya farklı hammaddeler için kesim formundaki satır numaralarını kullanır. Arayüz ve API katmanında standart alfabetik sıralama (`["1", "10", "2"]`) yerine **doğal sayısal sıralama (Natural Sort)** uygulanır:

1. **Satır Numarası Doğal Sıralaması (`satir_no`):**
   * Metinsel alan içerisindeki rakamlar tam sayıya (`int`) dönüştürülerek sıralanır (`1, 2, ..., 10, 11`).
   * Aynı ürün için birden fazla satır birleşik kesildiğinde girilen **virgüllü formatlar** (örn: `1,2,3` veya `2, 3`) desteklenir; sistem baştaki ilk sayıya göre (`1` veya `2`) doğru sıraya yerleştirir.
2. **Enjeksiyon Operasyonlarında Kalıp Numarası Sıralaması (`kalip_no`):**
   * Enjeksiyon operasyonlarında satır numarası kullanılmaz; kalıp numarası kullanılır.
   * `kalip_no` alanı da harf ve sayı bloklarına ayrılarak doğal sıralama motorundan geçirilir (örn: `KALIP-2` < `KALIP-10`).
3. **Nihai Sıralama Önceliği:**
   * Kayıtlar sırasıyla `(satir_no_natural_key, kalip_no_natural_key, idx)` hiyerarşisiyle dizilir.

---

## 3. Operasyon ve Alt Operasyon Ayarları Detay Matrisi

### 3.1. `KTA Calisma Karti Alt Operasyonlari` Ayarları
| Alan Adı | Tip | Değerler | Sistem Davranışı |
| :--- | :--- | :--- | :--- |
| **`parent_operation`** | Link | `KTA Calisma Karti Operasyonlari` | Bu alt işlemin ait olduğu ana operasyon bağlantısı. |
| **`title`** | Data | Metin (örn: "Kablo Kesim") | Alt operasyon başlığı. Doküman tekil kimliği `{parent_operation}-{title}` formatında oluşur. |
| **`sequence`** | Int | Sayısal | UI üzerindeki satır listeleme sırasını ve hammadde miras alma önceliğini belirler. |
| **`is_active`** | Check | `1` / `0` | Pasif alt operasyonlar kart ekranında operatörün seçim listesine gelmez. |
| **`operasyon_tipi`** | Select | `Blunt`, `Tek Taraf`, `Çift Taraf` | **Blunt:** Uçsuz düz kesim.<br/>**Tek Taraf:** Tek taraflı krimp/terminal çakım formu.<br/>**Çift Taraf:** Çift yönlü krimp (Yön 2 krimp yüksekliği, kontak no, kalıp no girişleri aktif olur). |
| **`is_tuketim_hesaplanir`** | Check | `1` / `0` | **`1` (Aktif):** Tüketim hesaplanır. Birim `Metre` ise `boyut_1_mm` (Parça Boyu mm) girilmesi zorunlu tutulur ve formül `Adet * Boyut / 1000` olarak işletilir.<br/>**`0` (Pasif):** Tüketim hesaplaması atlanır. |
| **`allowed_material_groups`** | Table | `Item Group` listesi | Bu alt operasyonda seçilebilecek hammadde grupları. **Eğer boş bırakılırsa, kendisinden önceki sequence'a sahip tüm alt operasyonların ve ana operasyonun malzeme gruplarını otomatik miras alır.** |

---

### 3.2. `KTA Calisma Karti Operasyonlari` Ayarları
| Alan Adı | Tip | Değerler | Sistem Davranışı |
| :--- | :--- | :--- | :--- |
| **`board_dogrulamasi_gerektirir`** | Check | `1` / `0` | `1` ise kart bitirilmeden önce Test Masası Doğrulama Kaydı (`test_masasi_dogrulama_kaydi`) aranır; yoksa bitirme engellenir. |
| **`customer_group` & `plant_floor`** | Link | Müşteri / Kat | Belirli bir müşteri grubu seçildiğinde ilgili operasyonun atanacağı fabrika katı (`plant_floor`) zorunlu hale gelir. |
| **`miktar_zorunlu_mu`** | Check | `1` / `0` | `1` ise kart bitirilirken tamamlanan miktar > 0 olmak zorundadır. `0` ise sadece alt operasyon satırı girilerek 0 miktarla da bitirilebilir. |
| **`erpnext_operations`** | Table | Mapping | ERPNext İş Kartı (Job Card) üzerindeki standart operasyonlar ile eşleştirme tablosu. |
| **`tuketim_limiti_aktif`** | Check | `1` / `0` | **`1`:** Alt operasyon girilirken `İş Emri Miktarı + Hurda Toleransı` aşılıyorsa işlem durdurulur (`frappe.throw`).<br/>**`0`:** Limit aşım kontrolü tamamen atlanır (bypass). |
| **`alt_operasyon_bazli_kalite`** | Check | `1` / `0` | **`1`:** Her alt operasyon için bağımsız onay/ret/kısmi kabul döngüsü açılır. Ret alan kart kilitlenmez.<br/>**`0`:** Klasik kart bazlı kalite çalışır (Ret anında kartı submit edip kapatır). |
| **`yuzde_yuz_kalite_kontrol`** | Check | `1` / `0` | **`1` (%100 Kontrol Modu):** Kartın bitirilebilmesi için açıkta hiçbir `Onay Bekliyor` satır kalamaz; tüm satırlar denetlenmiş olmalı ve en az 1 onay bulunmalıdır (tümü ret ise kart bitirilemez).<br/>**`0` (Örnekleme / Numune Modu):** Kartın onaysız kapatılmasını önlemek için **minimum 1 alt işlemin onaylı olması zorunludur**. Diğer satırlar onay beklese bile kart bitirilebilir ve kart statüsü **Kısmi Kabul Edildi** olur. |
| **`ekran_tipi`** | Select | `Tekli Hammadde` / `Çoklu Hammadde` | Tekli hammadde veya eşzamanlı 3 hammadde (`hammadde`, `hammadde_2`, `hammadde_3`) giriş modu. |
| **`has_krimp, has_idc, has_barkod, has_enjeksiyon`** | Check | `1` / `0` | İlgili operasyona ait özel ölçüm ve veri toplama formlarını aktif/pasif eder. |

---

## 4. Kalite Kontrol ve Kısmi Kabul (Partial Acceptance) Döngüsü

Alt operasyon bazlı kalite (`alt_operasyon_bazli_kalite == 1`) seçili operasyonlarda kart seviyesindeki `kalite_kontrol` statüsü, alt satırların anlık ve nihai durumuna göre otomatik olarak belirlenir:

```
┌───────────────────────────────────────────────────────────┐
│        Alt Operasyon Kalite Statüsü Belirleme Kuralı      │
├────────────────────────────────┬──────────────────────────┤
│ Koşul                          │ Sonuç (kalite_kontrol)   │
├────────────────────────────────┼──────────────────────────┤
│ Tüm satırlar onaylı            │ Onaylandı (Yeşil)        │
│ Tüm satırlar ret               │ Reddedildi (Kırmızı)     │
│ Hem onay hem ret var           │ Kısmi Kabul Edildi (Mor) │
│ Açıkta bekleyen var (Açık kart)│ Onay Bekliyor (Mavi)     │
│ Bittiğinde + En az 1 onay var  │ Kısmi Kabul Edildi (Mor) │
└────────────────────────────────┴──────────────────────────┘
```

* **Örnekleme Muayenesi Güvencesi:** `%100 Kontrol` kapalıyken 10 kablo kesen operatörün kartında 1 satır test edilip onaylandığında, kalan 9 satır açıkta beklese dahi kart bitirilebilir. Kart bittiğinde sistem bu durumu **Kısmi Kabul Edildi** statüsüne dönüştürerek onay bekleyen kart karmaşasını önler.
* **Üst Başlık Çipi Entegrasyonu:** Kart bitirildiğinde veya onaylandığında veritabanındaki kesinleşmiş statü ön yüze (`qcValue`) yansıtılır.

---

## 5. Kart Bitirme Validasyonları Matrisi

| Doğrulama Adımı | Koşul / Kural | Hata Durumunda Sistem Tepkisi |
| :--- | :--- | :--- |
| **Mükerrer Bitiş Engeli** | `doc.bitis_saati` dolu, `docstatus == 1` veya durum `bitmis`/`reddedildi` | `Bu kart zaten bitmiş.` |
| **Alt Operasyon Zorunluluğu** | `len(alt_operasyon_kayitlari) > 0` | `İşlemin bitirilebilmesi için en az bir alt operasyon kaydı bulunmalıdır.` |
| **%100 Kalite Kontrolü** | `yuzde_yuz_kalite_kontrol == 1` | `Açıkta onay bekleyen alt işlem varken kart bitirilemez.` |
| **Minimum Onay Şartı** | `yuzde_yuz_kalite_kontrol == 0` | `Kartın bitirilebilmesi için en az bir alt işlemin kalite onayı almış olması gerekir.` |
| **Mükerrer Kalite Belgesi** | `mukerrer_kalite_kontrolu_yap == 1` | Belge başka bir aktif kartta kullanılmışsa işlem durdurulur (`frappe.throw`). |

</main>

