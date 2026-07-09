import { applyDecimalInputMode } from "./common";

declare const __: any;
export function idcOlcumFields(docname: string, defaults: any = {}) {
    return applyDecimalInputMode([
        {
            fieldtype: "Link",
            label: __("Ürün Kodu"),
            fieldname: "item_code",
            options: "Item",
            reqd: 1,
            default: defaults.item_code || "",
            get_query: () => ({
                query: "erpnextkta.kta_calisma_karti.api.search_allowed_idc_items",
                filters: { calisma_karti: docname } // docname’i idcOlcumFields'e parametre geçeceğiz
            })
        },
        {
            fieldtype: "Float",
            label: __("Yükseklik (mm)"),
            fieldname: "yukseklik_mm",
            reqd: 0,
            default: defaults.yukseklik_mm ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Çekme (N)"),
            fieldname: "cekme_n",
            reqd: 0,
            default: defaults.cekme_n ?? 0,
        },
    ]);
}

export function krimpOlcumFields(defaults: any = {}) {
    return applyDecimalInputMode([
        {
            fieldtype: "Section Break",
            label: __("Makine Bilgileri")
        },
        {
            fieldtype: "Select",
            label: __("İlgili Alt İşlem"),
            fieldname: "alt_operasyon_kaydi",
            options: defaults.alt_op_options || [""],
            default: defaults.alt_operasyon_kaydi || "",
            reqd: 0
        },
        {
            fieldtype: "Link",
            label: __("Makine / Pres No"),
            fieldname: "makine_pres_no",
            options: "Asset",
            default: defaults.makine_pres_no || "",
        },
        {
            fieldtype: "Section Break",
            label: __("Kablo Bilgileri")
        },
        {
            fieldtype: "Data",
            label: __("Satır No"),
            fieldname: "satir_no",
            default: defaults.satir_no || "",
            read_only: 0
        },
        {
            fieldtype: "Link",
            label: __("Kablo No"),
            fieldname: "kablo_no",
            options: "Item",
            default: defaults.kablo_no || "",
            reqd: 0,
            get_query: () => ({
                query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
                filters: { calisma_karti: defaults.calisma_karti_name, type: "kablo" }
            })
        },
        { fieldtype: "Section Break", hide_border: 1 },
        {
            fieldtype: "Float",
            label: __("Hedef Kablo Boyu (mm)"),
            fieldname: "hedef_kablo_boyu",
            default: defaults.hedef_kablo_boyu ?? 0,
            read_only: 1,
        },
        {
            fieldtype: "Column Break",
        },
        {
            fieldtype: "Float",
            label: __("Ölçülen Kablo Boyu (mm)"),
            fieldname: "olculen_kablo_boyu",
            default: defaults.olculen_kablo_boyu ?? 0,
        },
        {
            fieldtype: "Section Break",
            label: __("Kablo Uç İşlemleri (Sıyırma & Çapak)")
        },
        { fieldtype: "Float", label: __("T1 Sıyırma Boyu (mm)"), fieldname: "siyirma_boyu", default: defaults.siyirma_boyu ?? 0 },
        { fieldtype: "Column Break" },
        { fieldtype: "Float", label: __("T2 Sıyırma Boyu (mm)"), fieldname: "yon_2_siyirma_boyu", default: defaults.yon_2_siyirma_boyu ?? 0 },

        { fieldtype: "Section Break", hide_border: 1 },
        { fieldtype: "Float", label: __("T1 Çapak Boyu (mm)"), fieldname: "capak_boyu", default: defaults.capak_boyu ?? 0 },
        { fieldtype: "Column Break" },
        { fieldtype: "Float", label: __("T2 Çapak Boyu (mm)"), fieldname: "yon_2_capak_boyu", default: defaults.yon_2_capak_boyu ?? 0 },

        {
            fieldtype: "Section Break",
            label: __("T1 - Terminal Bilgileri"),
            depends_on: "eval:doc.kontak_no"
        },
        {
            fieldtype: "Link",
            label: __("T1 Terminal No"),
            fieldname: "kontak_no",
            options: "Item",
            default: defaults.kontak_no || "",
            reqd: 0,
            get_query: () => ({
                query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
                filters: { calisma_karti: defaults.calisma_karti_name, type: "kontak" }
            })
        },
        {
            fieldtype: "Select",
            label: __("T1 Kablo Kesiti (Rehberden)"),
            fieldname: "kablo_kesiti",
            options: defaults.kablo_kesiti ? ["", defaults.kablo_kesiti] : [""],
            default: defaults.kablo_kesiti || "",
            reqd: 0
        },

        
        {
            fieldtype: "Section Break",
            label: __("T1 - Kalıp Bilgileri"),
            depends_on: "eval:doc.kontak_no"
        },
        {
            fieldtype: "Select",
            label: __("T1 Kalıp No"),
            fieldname: "kalip_no",
            options: defaults.kalip_list?.length ? ["", ...defaults.kalip_list] : (defaults.kalip_no ? ["", defaults.kalip_no] : [""]),
            default: defaults.kalip_no || "",
        },
        { fieldtype: "Section Break", label: __("T1 - Ölçümler"), depends_on: "eval:doc.kontak_no" },
        { fieldtype: "Float", label: __("T1 Hedef İletken Krimp Yük. (mm)"), fieldname: "hedef_iletken_krimp_yuksekliği", default: defaults.hedef_iletken_krimp_yuksekliği ?? 0, read_only: 1 },
        { fieldtype: "Column Break" },
        { fieldtype: "Float", label: __("T1 Ölçülen İletken Krimp Yük. (mm)"), fieldname: "olculen_iletken_krimp_yuksekliği", default: defaults.olculen_iletken_krimp_yuksekliği ?? 0 },

        { fieldtype: "Section Break", hide_border: 1, depends_on: "eval:doc.kontak_no" },
        { fieldtype: "Float", label: __("T1 Hedef Çekme Kuvveti (N)"), fieldname: "hedef_cekme_kuvveti_n", default: defaults.hedef_cekme_kuvveti_n ?? 0, read_only: 1 },
        { fieldtype: "Column Break" },
        { fieldtype: "Float", label: __("T1 Ölçülen Çekme Kuvveti (N)"), fieldname: "olculen_cekme_kuvveti_n", default: defaults.olculen_cekme_kuvveti_n ?? 0 },

        { fieldtype: "Section Break", hide_border: 1, depends_on: "eval:doc.kontak_no" },
        { fieldtype: "Float", label: __("T1 İzokrimp Yüksekliği (mm)"), fieldname: "izokrimp_yuksekligi", default: defaults.izokrimp_yuksekligi ?? 0 },

        {
            fieldtype: "Section Break",
            label: __("T1 - Görsel Kontroller"),
            depends_on: "eval:doc.kontak_no"
        },
        {
            fieldtype: "Check",
            label: __("T1 Radüs Mevcut"),
            fieldname: "radus_mevcut",
            default: defaults.radus_mevcut ?? 0,
        },
        {
            fieldtype: "Column Break"
        },
        {
            fieldtype: "Check",
            label: __("T1 Tel Kesme Mevcut"),
            fieldname: "tel_kesme_mevcut",
            default: defaults.tel_kesme_mevcut ?? 0,
        },
        {
            fieldtype: "Check",
            fieldname: "is_cift_tarafli",
            default: defaults.is_cift_tarafli || 0,
            hidden: 1
        },
        {
            fieldtype: "Section Break",
            label: __("T2 - Terminal Bilgileri"),
            depends_on: "eval:doc.yon_2_kontak_no"
        },
        {
            fieldtype: "Link",
            label: __("T2 Terminal No"),
            fieldname: "yon_2_kontak_no",
            options: "Item",
            default: defaults.yon_2_kontak_no || "",
            reqd: 0,
            depends_on: "eval:doc.yon_2_kontak_no",
            get_query: () => ({
                query: "erpnextkta.kta_calisma_karti.api.search_krimp_items",
                filters: { calisma_karti: defaults.calisma_karti_name, type: "kontak" }
            })
        },
        {
            fieldtype: "Select",
            label: __("T2 Kablo Kesiti (Rehberden)"),
            fieldname: "yon_2_kablo_kesiti",
            options: defaults.yon_2_kablo_kesiti ? ["", defaults.yon_2_kablo_kesiti] : [""],
            default: defaults.yon_2_kablo_kesiti || "",
            depends_on: "eval:doc.yon_2_kontak_no"
        },
        {
            fieldtype: "Section Break",
            label: __("T2 - Kalıp Bilgileri"),
            depends_on: "eval:doc.yon_2_kontak_no"
        },
        {
            fieldtype: "Select",
            label: __("T2 Kalıp No"),
            fieldname: "yon_2_kalip_no",
            options: defaults.yon_2_kalip_list?.length ? ["", ...defaults.yon_2_kalip_list] : (defaults.yon_2_kalip_no ? ["", defaults.yon_2_kalip_no] : [""]),
            default: defaults.yon_2_kalip_no || "",
            depends_on: "eval:doc.yon_2_kontak_no"
        },

        { fieldtype: "Section Break", label: __("T2 - Ölçümler"), depends_on: "eval:doc.yon_2_kontak_no" },
        { fieldtype: "Float", label: __("T2 Hedef İletken Krimp Yük. (mm)"), fieldname: "yon_2_hedef_iletken_krimp_yuksekligi", default: defaults.yon_2_hedef_iletken_krimp_yuksekligi ?? 0, read_only: 1, depends_on: "eval:doc.yon_2_kontak_no" },
        { fieldtype: "Column Break", depends_on: "eval:doc.yon_2_kontak_no" },
        { fieldtype: "Float", label: __("T2 Ölçülen İletken Krimp Yük. (mm)"), fieldname: "yon_2_olculen_iletken_krimp_yuksekligi", default: defaults.yon_2_olculen_iletken_krimp_yuksekligi ?? 0, depends_on: "eval:doc.yon_2_kontak_no" },

        { fieldtype: "Section Break", hide_border: 1, depends_on: "eval:doc.yon_2_kontak_no" },
        { fieldtype: "Float", label: __("T2 Hedef Çekme Kuvveti (N)"), fieldname: "yon_2_hedef_cekme_kuvveti_n", default: defaults.yon_2_hedef_cekme_kuvveti_n ?? 0, read_only: 1, depends_on: "eval:doc.yon_2_kontak_no" },
        { fieldtype: "Column Break", depends_on: "eval:doc.yon_2_kontak_no" },
        { fieldtype: "Float", label: __("T2 Ölçülen Çekme Kuvveti (N)"), fieldname: "yon_2_olculen_cekme_kuvveti_n", default: defaults.yon_2_olculen_cekme_kuvveti_n ?? 0, depends_on: "eval:doc.yon_2_kontak_no" },

        { fieldtype: "Section Break", hide_border: 1, depends_on: "eval:doc.yon_2_kontak_no" },
        { fieldtype: "Float", label: __("T2 İzokrimp Yüksekliği (mm)"), fieldname: "yon_2_izokrimp_yuksekligi", default: defaults.yon_2_izokrimp_yuksekligi ?? 0, depends_on: "eval:doc.yon_2_kontak_no" },

        {
            fieldtype: "Section Break",
            label: __("T2 - Görsel Kontroller"),
            depends_on: "eval:doc.yon_2_kontak_no"
        },
        {
            fieldtype: "Check",
            label: __("T2 Radüs Mevcut"),
            fieldname: "yon_2_radus_mevcut",
            default: defaults.yon_2_radus_mevcut ?? 0,
            depends_on: "eval:doc.yon_2_kontak_no"
        },
        {
            fieldtype: "Column Break",
            depends_on: "eval:doc.yon_2_kontak_no"
        },
        {
            fieldtype: "Check",
            label: __("T2 Tel Kesme Mevcut"),
            fieldname: "yon_2_tel_kesme_mevcut",
            default: defaults.yon_2_tel_kesme_mevcut ?? 0,
            depends_on: "eval:doc.yon_2_kontak_no"
        },
    ]);
}

export function enjeksiyonOlcumFields(defaults: any = {}) {
    return applyDecimalInputMode([
        {
            fieldtype: "Select",
            label: __("Kontrol Periyodu"),
            fieldname: "kontrol_periyodu",
            options: "Başlangıç\nAra\nBitiş",
            reqd: 1,
            default: defaults.kontrol_periyodu || "Başlangıç",
        },
        {
            fieldtype: "Link",
            label: __("Hammadde No"),
            fieldname: "hammadde_no",
            options: "Item",
            reqd: 1,
            default: defaults.hammadde_no || "",
            get_query: () => ({
                query: "erpnextkta.kta_calisma_karti.api.search_enjeksiyon_allowed_items",
                filters: { calisma_karti: defaults.calisma_karti_name }
            })
        },
        {
            fieldtype: "Column Break"
        },
        {
            fieldtype: "Check",
            label: __("Göz Kontrol"),
            fieldname: "goz_kontrol",
            default: defaults.goz_kontrol ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Çekme Kuvveti (N)"),
            fieldname: "cekme_kuvveti_olculen",
            default: defaults.cekme_kuvveti_olculen ?? 0,
        },
        { fieldtype: "Section Break", label: __("Proses Parametreleri") },
        {
            fieldtype: "Float",
            label: __("Hammadde Kazan Isısı (°C)"),
            fieldname: "hammadde_kazan_isisi",
            default: defaults.hammadde_kazan_isisi ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Ara Hortum Isısı (°C)"),
            fieldname: "ara_hortum_isisi",
            default: defaults.ara_hortum_isisi ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Kafa (Meme) Isısı (°C)"),
            fieldname: "kafa_meme_isisi",
            default: defaults.kafa_meme_isisi ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Soğuk Su Isısı (°C)"),
            fieldname: "soguk_su_isisi",
            default: defaults.soguk_su_isisi ?? 0,
        },
        { fieldtype: "Column Break" },
        {
            fieldtype: "Float",
            label: __("Motor Devir"),
            fieldname: "motor_devir",
            default: defaults.motor_devir ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Hammadde Enjeksiyon Zamanı (sn)"),
            fieldname: "hammadde_enjeksiyon_zamani",
            default: defaults.hammadde_enjeksiyon_zamani ?? 0,
        },
        {
            fieldtype: "Float",
            label: __("Soğutma Zamanı (sn)"),
            fieldname: "sogutma_zamani",
            default: defaults.sogutma_zamani ?? 0,
        }
    ]);
}
