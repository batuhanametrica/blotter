# Banka listesi
BANKALAR = [
    "Halkbank", 
    "Garanti Bank", 
    "Denizbank", 
    "Akbank", 
    "Yapı Kredi"
]

# Mevduat tipleri
MEVDUAT_TIPLERI = ["TL Mevduat", "USD Mevduat"]

# Varsayılan faiz oranları
VARSAYILAN_FAIZ = {
    'TL Mevduat': 50.00,
    'USD Mevduat': 4.75
}

# Stopaj oranları
STOPAJ_ORANLARI = {
    'TL Mevduat': {
        '6_ay': 10.0,  # 6 aya kadar %10
        '1_yil': 7.5,  # 1 yıla kadar %7.5
        'uzun': 5.0    # 1 yıldan uzun %5
    },
    'USD Mevduat': {
        '6_ay': 25.0,  # 6 aya kadar %15
        '1_yil': 25.0, # 1 yıla kadar %12
        'uzun': 25.0   # 1 yıldan uzun %10
    }
}

# Kolon tanımları
TL_KOLONLAR = [
    'mevduat_tipi',
    'banka',
    'vade_baslangic',
    'vade_bitis',
    'tutar',
    'faiz_orani',
    'stopaj_orani',
    'brut_faiz',
    'stopaj_tutari',
    'net_faiz',
    'donus_tutari_tl',
    'baslangic_kur',
    'basabas_kur',
    'orijinal_vade',
    'kalan_gun'
]

# USD mevduatlar için kolonlar
USD_KOLONLAR = [
    'mevduat_tipi',
    'banka',
    'vade_baslangic',
    'vade_bitis',
    'tutar',
    'faiz_orani',
    'stopaj_orani',
    'brut_faiz_usd',
    'stopaj_tutari_usd',
    'net_faiz_usd',
    'donus_tutari_usd',
    'baslangic_kur',
    'basabas_kur',
    'orijinal_vade',
    'kalan_gun'
]

# Portföy özeti için kolonlar
PORTFOY_KOLONLAR = [
    'mevduat_tipi',
    'banka',
    'vade_baslangic',
    'vade_bitis',
    'tutar',
    'faiz_orani',
    'net_faiz',
    'donus_tutari_tl',
    'kalan_gun'
]