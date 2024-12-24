from datetime import datetime, date
import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import warnings
import io

from constants import (
    STOPAJ_ORANLARI, 
    TL_KOLONLAR, 
    USD_KOLONLAR,
    MEVDUAT_TIPLERI, 
    BANKALAR, 
    VARSAYILAN_FAIZ
)

# Uyarıları gizle
warnings.filterwarnings(
    'ignore',
    message='The \'unit\' keyword in TimedeltaIndex construction is deprecated',
    category=FutureWarning
)

def get_guncel_kur():
    """USD/TL güncel kur bilgisini al"""
    try:
        # Sadece TimedeltaIndex uyarısını gizle
        import warnings
        warnings.filterwarnings(
            'ignore',
            message='The \'unit\' keyword in TimedeltaIndex construction is deprecated',
            category=FutureWarning
        )
        
        kur = yf.Ticker("USDTRY=X")
        return round(kur.history(period="1d")['Close'].iloc[-1], 4)
    except Exception as e:
        st.error(f"Kur bilgisi alınamadı: {str(e)}")
        return 0.0

def hesapla_stopaj_orani(vade_gun, mevduat_tipi):
    """Mevduat tipine göre vade için stopaj oranı hesapla"""
    if vade_gun <= 180:  # 6 ay
        return STOPAJ_ORANLARI[mevduat_tipi]['6_ay']
    elif vade_gun <= 365:  # 1 yıl
        return STOPAJ_ORANLARI[mevduat_tipi]['1_yil']
    else:  # 1 yıldan uzun
        return STOPAJ_ORANLARI[mevduat_tipi]['uzun']

def hesapla_tl_mevduat(data, vade_gun):
    """TL mevduat hesaplamaları"""
    # Güncel kur bilgisini al
    guncel_kur = st.session_state.get('guncel_kur', get_guncel_kur())
    
    # Stopaj oranı hesapla
    stopaj_orani = hesapla_stopaj_orani(vade_gun, data['mevduat_tipi'])
    
    # Brüt faiz tutarı
    brut_faiz = round(
        data['tutar'] * 
        (data['faiz_orani'] / 100) * 
        (vade_gun / 365)
    )
    
    # Stopaj tutarı
    stopaj_tutari = round(
        brut_faiz * 
        (stopaj_orani / 100)
    )
    
    # Net faiz
    net_faiz = brut_faiz - stopaj_tutari
    
    # TL toplam dönüş
    donus_tutari_tl = data['tutar'] + net_faiz
    
    # USD karşılıkları
    tutar_usd = round(data['tutar'] / guncel_kur, 2)
    
    # Başabaş kur hesaplama
    brut_getiri = ((data['faiz_orani']/100) / 365) * vade_gun
    net_getiri = brut_getiri * (1 - stopaj_orani/100)
    basabas_kur = round(guncel_kur * (1 + net_getiri), 4)
    
    return {
        'stopaj_orani': stopaj_orani,
        'brut_faiz': brut_faiz,
        'stopaj_tutari': stopaj_tutari,
        'net_faiz': net_faiz,
        'donus_tutari_tl': donus_tutari_tl,
        'tutar_usd': tutar_usd,
        'baslangic_kur': guncel_kur,
        'basabas_kur': basabas_kur
    }

def hesapla_basabas_kur(faiz_orani, orijinal_vade, baslangic_kur, stopaj_orani):
    """USD mevduat için başabaş kur hesaplama"""
    brut_getiri = ((faiz_orani/100) / 365) * orijinal_vade
    net_getiri = brut_getiri * (1 - stopaj_orani/100)
    return round((1 + net_getiri) * baslangic_kur, 4)

def hesapla_usd_mevduat(data, vade_gun, guncel_kur):
    """USD mevduat hesaplamaları"""
    # Stopaj oranı hesapla
    stopaj_orani = hesapla_stopaj_orani(vade_gun, data['mevduat_tipi'])
    
    # USD cinsinden brüt faiz tutarı
    brut_faiz_usd = round(
        data['tutar'] * 
        (data['faiz_orani'] / 100) * 
        (vade_gun / 365)
    )
    
    # USD cinsinden stopaj tutarı
    stopaj_tutari_usd = round(
        brut_faiz_usd * 
        (stopaj_orani / 100)
    )
    
    # USD cinsinden net faiz
    net_faiz_usd = brut_faiz_usd - stopaj_tutari_usd
    
    # USD toplam dönüş
    donus_tutari_usd = data['tutar'] + net_faiz_usd
    
    # TL karşılıkları
    brut_faiz = round(brut_faiz_usd * guncel_kur)
    stopaj_tutari = round(stopaj_tutari_usd * guncel_kur)
    net_faiz = round(net_faiz_usd * guncel_kur)
    donus_tutari_tl = round(donus_tutari_usd * guncel_kur)
    
    # Başabaş kur hesaplama
    basabas_kur = hesapla_basabas_kur(
        data['faiz_orani'],
        data['orijinal_vade'],
        data.get('baslangic_kur', guncel_kur),
        stopaj_orani
    )
    
    return {
        'stopaj_orani': stopaj_orani,
        'brut_faiz': brut_faiz,
        'stopaj_tutari': stopaj_tutari,
        'net_faiz': net_faiz,
        'donus_tutari_tl': donus_tutari_tl,
        'brut_faiz_usd': brut_faiz_usd,
        'stopaj_tutari_usd': stopaj_tutari_usd,
        'net_faiz_usd': net_faiz_usd,
        'donus_tutari_usd': donus_tutari_usd,
        'basabas_kur': basabas_kur
    }

def hesapla(data):
    """Ana hesaplama fonksiyonu"""
    # Güncel kur bilgisini al
    guncel_kur = st.session_state.get('guncel_kur', get_guncel_kur())
    
    # Vade gün hesaplamaları
    vade_gun = (data['vade_bitis'] - data['vade_baslangic']).days
    kalan_gun = (data['vade_bitis'] - date.today()).days
    
    # Temel veri hazırlama
    hesaplama = {
        'mevduat_tipi': data['mevduat_tipi'],
        'banka': data['banka'],
        'tutar': round(float(data['tutar'])),
        'faiz_orani': round(float(data['faiz_orani']), 2),
        'vade_baslangic': data['vade_baslangic'],
        'vade_bitis': data['vade_bitis'],
        'orijinal_vade': vade_gun,  # Orijinal vade eklendi
        'kalan_gun': kalan_gun,
        'baslangic_kur': data.get('baslangic_kur', guncel_kur)
    }
    
    # Mevduat tipine göre hesaplama
    if hesaplama['mevduat_tipi'] == 'USD Mevduat':
        hesaplama.update(hesapla_usd_mevduat(hesaplama, vade_gun, guncel_kur))
    else:
        hesaplama.update(hesapla_tl_mevduat(hesaplama, vade_gun))
    
    return hesaplama

def veri_giris_formu():
    """Mevduat veri giriş formu"""
    col1, col2 = st.columns(2)
    
    with col1:
        mevduat_tipi = st.selectbox("Mevduat Tipi", MEVDUAT_TIPLERI)
        banka = st.selectbox("Banka", BANKALAR)
        tutar = st.number_input(
            "Tutar (USD)" if mevduat_tipi == "USD Mevduat" else "Tutar (TL)", 
            value=50000
        )
        
        # Her iki mevduat tipi için de başlangıç kuru göster
        baslangic_kur = st.number_input(
            "Başlangıç Kuru", 
            value=st.session_state.get('guncel_kur', get_guncel_kur()),
            format="%.4f"
        )
    
    with col2:
        vade_baslangic = st.date_input("Vade Başlangıç")
        vade_bitis = st.date_input("Vade Bitiş")
        varsayilan_faiz = VARSAYILAN_FAIZ[mevduat_tipi]
        faiz_orani = st.number_input("Faiz Oranı (%)", value=varsayilan_faiz)
        
        if vade_bitis:
            kalan_gun = (vade_bitis - date.today()).days
            st.metric("Vadeye Kalan Gün", kalan_gun)
    
    # Kaydet butonu
    if st.button("Kaydet", type="primary"):
        if tutar <= 0:
            st.error("Lütfen geçerli bir tutar giriniz!")
            return
        
        if vade_bitis <= vade_baslangic:
            st.error("Vade bitiş tarihi, başlangıç tarihinden sonra olmalıdır!")
            return
        
        # Mevduat hesaplama
        hesaplama_data = {
            'mevduat_tipi': mevduat_tipi,
            'banka': banka,
            'tutar': tutar,
            'faiz_orani': faiz_orani,
            'vade_baslangic': vade_baslangic,
            'vade_bitis': vade_bitis
        }
        
        if mevduat_tipi == "USD Mevduat":
            hesaplama_data['baslangic_kur'] = baslangic_kur
        
        hesaplama = hesapla(hesaplama_data)
        
        # Session state'e kaydet
        if 'mevduatlar' not in st.session_state:
            st.session_state.mevduatlar = []
        
        st.session_state.mevduatlar.append(hesaplama)
        st.success("Mevduat kaydedildi!")
        st.rerun()

def mevduat_listesi_tab(df, kolonlar):
    """Mevduat tablosu gösterimi"""
    # DataFrame'e seçim kolonu ekle
    df_edit = df.copy()
    df_edit.insert(0, "seç", False)
    
    # Temel kolon konfigürasyonu
    column_config = {
        "seç": st.column_config.CheckboxColumn(
            "Seç",
            help="Silmek istediğiniz kayıtları seçin",
            default=False
        ),
        "mevduat_tipi": "Mevduat Tipi",
        "banka": "Banka",
        "vade_baslangic": st.column_config.DateColumn("Vade Başlangıç"),
        "vade_bitis": st.column_config.DateColumn("Vade Bitiş"),
        "tutar": st.column_config.NumberColumn(
            "Anapara",
            help="Mevduat tutarı",
            format="%d"
        ),
        "faiz_orani": st.column_config.NumberColumn(
            "Faiz Oranı",
            help="Yıllık faiz oranı",
            format="%.2f%%"
        ),
        "stopaj_orani": st.column_config.NumberColumn(
            "Stopaj Oranı",
            help="Stopaj oranı",
            format="%.1f%%"
        ),
        "orijinal_vade": st.column_config.NumberColumn(
            "Orijinal Vade",
            help="Mevduatın açıldığı gündeki vade süresi",
            format="%d gün"
        ),
        "kalan_gun": st.column_config.NumberColumn(
            "Kalan Gün",
            help="Vadeye kalan gün sayısı",
            format="%d"
        )
    }
    
    # TL mevduat için ek kolonlar
    if 'brut_faiz' in kolonlar:
        column_config.update({
            "brut_faiz": st.column_config.NumberColumn(
                "Brüt Faiz",
                format="%d ₺"
            ),
            "stopaj_tutari": st.column_config.NumberColumn(
                "Stopaj Tutarı",
                format="%d ₺"
            ),
            "net_faiz": st.column_config.NumberColumn(
                "Net Faiz",
                format="%d ₺"
            ),
            "donus_tutari_tl": st.column_config.NumberColumn(
                "Toplam Dönüş (TL)",
                format="%d ₺"
            )
        })
    
    # USD mevduat için ek kolonlar
    if 'brut_faiz_usd' in kolonlar:
        column_config.update({
            "brut_faiz_usd": st.column_config.NumberColumn(
                "Brüt Faiz (USD)",
                format="%d $"
            ),
            "stopaj_tutari_usd": st.column_config.NumberColumn(
                "Stopaj (USD)",
                format="%d $"
            ),
            "net_faiz_usd": st.column_config.NumberColumn(
                "Net Faiz (USD)",
                format="%d $"
            ),
            "donus_tutari_usd": st.column_config.NumberColumn(
                "Toplam Dönüş (USD)",
                format="%d $"
            ),
            "baslangic_kur": st.column_config.NumberColumn(
                "Başlangıç Kuru",
                format="%.4f ₺"
            ),
            "basabas_kur": st.column_config.NumberColumn(
                "Başabaş Kur",
                format="%.4f ₺"
            )
        })
    
    # DataFrame'i göster
    secilen_satirlar = st.data_editor(
        df_edit[['seç'] + kolonlar],
        hide_index=True,
        column_config=column_config,
        disabled=kolonlar,
        use_container_width=True
    )
    
    # Silme butonu ve işlemi
    silinecek_indexler = secilen_satirlar[secilen_satirlar["seç"]].index.tolist()
    if silinecek_indexler:
        if st.button("Seçili Mevduatları Sil", type="primary"):
            st.session_state.mevduatlar = [
                m for i, m in enumerate(st.session_state.mevduatlar) 
                if i not in silinecek_indexler
            ]
            st.success("Seçili mevduatlar silindi!")
            st.rerun()
    
    return silinecek_indexler

def mevduat_analizleri(df):
    """Mevduat portföy analizleri"""
    # Aktif mevduatları filtrele
    aktif_df = df[pd.to_datetime(df['vade_bitis']).dt.date >= date.today()].copy()
    
    if aktif_df.empty:
        st.warning("Aktif mevduat bulunmamaktadır!")
        return
    
    # NA değerleri doldur
    aktif_df = aktif_df.fillna(0, inplace=True)
    
    st.write("### Aktif Portföy Özeti")
    
    # USD mevduatları TL'ye çevir
    guncel_kur = st.session_state.get('guncel_kur', get_guncel_kur())
    aktif_df['tutar_tl'] = aktif_df.apply(
        lambda x: x['tutar'] if x['mevduat_tipi'] == 'TL Mevduat' 
        else x['tutar'] * guncel_kur, 
        axis=1
    )
    aktif_df['net_faiz_tl'] = aktif_df.apply(
        lambda x: x['net_faiz'] if x['mevduat_tipi'] == 'TL Mevduat'
        else x['net_faiz_usd'] * guncel_kur,
        axis=1
    )
    
    # Metrikleri hesapla
    toplam_anapara_tl = aktif_df['tutar_tl'].sum()
    toplam_net_faiz_tl = aktif_df['net_faiz_tl'].sum()
    toplam_getiri_orani = (toplam_net_faiz_tl / toplam_anapara_tl * 100) if toplam_anapara_tl > 0 else 0
    
    # Ana metrikler
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Aktif Mevduat", f"{len(aktif_df)} Adet")
    with col2:
        st.metric("Toplam Anapara (TL)", f"{toplam_anapara_tl:,.0f} ₺")
    with col3:
        st.metric("Toplam Net Faiz (TL)", f"{toplam_net_faiz_tl:,.0f} ₺")
    with col4:
        st.metric("Toplam Getiri Oranı", f"%{toplam_getiri_orani:.2f}")
    
    # Grafikleri yan yana göster
    st.write("### Dağılım Grafikleri")
    col1, col2 = st.columns(2)
    
    with col1:
        # Banka dağılımı pasta grafiği
        fig_banka = px.pie(
            aktif_df,
            values='tutar_tl',
            names='banka',
            title='Bankalara Göre Aktif Mevduat Dağılımı',
            hole=0.4
        )
        st.plotly_chart(fig_banka, use_container_width=True)
        
        # Banka bazlı özet tablo - Daha basit çözüm
        banka_ozet = (
            aktif_df.fillna(0)  # Önce NA değerleri doldur
            .groupby('banka')
            .agg({
                'tutar_tl': ['count', 'sum'],
                'net_faiz_tl': 'sum'
            })
        )
        
        banka_ozet.columns = ['Adet', 'Toplam Anapara (TL)', 'Toplam Net Faiz (TL)']
        st.dataframe(banka_ozet, use_container_width=True)
    
    with col2:
        # Vade gruplarını belirleme
        def vade_grubu(gun):
            if gun <= 30:
                return "1 aya kadar"
            elif gun <= 90:
                return "1-3 ay"
            elif gun <= 180:
                return "3-6 ay"
            elif gun <= 365:
                return "6-12 ay"
            else:
                return "12+ ay"
        
        aktif_df['vade_grubu'] = aktif_df['kalan_gun'].apply(vade_grubu)
        vade_sirasi = ["1 aya kadar", "1-3 ay", "3-6 ay", "6-12 ay", "12+ ay"]
        
        # Vade dağılımı - Daha basit çözüm
        vade_ozet = (
            aktif_df.fillna(0)  # Önce NA değerleri doldur
            .groupby('vade_grubu')
            .agg({
                'tutar_tl': 'sum',
                'net_faiz_tl': 'sum'
            })
            .reindex(vade_sirasi)  # Vade sırasını düzenle
            .reset_index()
        )

        vade_ozet.fillna(0, inplace=True)
        
        # Portföy payı hesapla
        toplam_tutar = vade_ozet['tutar_tl'].sum()
        vade_ozet['pay'] = (vade_ozet['tutar_tl'] / toplam_tutar * 100).round(2)
        
        # Vade dağılımı bar grafiği
        fig_vade = px.bar(
            vade_ozet,
            x='vade_grubu',
            y='tutar_tl',
            title='Vade Sürelerine Göre Aktif Mevduat Dağılımı',
            text=vade_ozet['tutar_tl'].apply(lambda x: f'{x:,.0f} ₺')
        )
        fig_vade.update_traces(textposition='inside')
        st.plotly_chart(fig_vade, use_container_width=True)
        
        # Tabloya çevir
        vade_ozet_tablo = pd.DataFrame({
            'Vade Grubu': vade_ozet['vade_grubu'],
            'Toplam Anapara (TL)': vade_ozet['tutar_tl'].apply(lambda x: f'{x:,.0f} ₺'),
            'Toplam Net Faiz (TL)': vade_ozet['net_faiz_tl'].apply(lambda x: f'{x:,.0f} ₺'),
            'Portföy Payı (%)': vade_ozet['pay'].apply(lambda x: f'{x:.2f}%')
        })

        vade_ozet_tablo.fillna(0, inplace=True)

        st.dataframe(vade_ozet_tablo, use_container_width=True)

def hesapla_ortalama_vade(df):
    """Ağırlıklı ortalama vade hesaplama"""
    if df.empty:
        return 0
        
    toplam_tutar = df['tutar'].sum()
    if toplam_tutar == 0:
        return 0
        
    # Ağırlıklı ortalama vade hesaplama
    agirlikli_vade = (df['tutar'] * df['kalan_gun']).sum() / toplam_tutar
    return round(agirlikli_vade, 0)

def export_to_excel():
    """Mevduat verilerini Excel'e aktar"""
    if 'mevduatlar' not in st.session_state or not st.session_state.mevduatlar:
        st.warning("Dışa aktarılacak veri bulunmamaktadır!")
        return None
    
    df = pd.DataFrame(st.session_state.mevduatlar)
    
    # Excel dosyasını oluştur
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Aktif mevduatlar
        aktif_df = df[pd.to_datetime(df['vade_bitis']).dt.date >= date.today()]
        if not aktif_df.empty:
            aktif_df.to_excel(writer, sheet_name='Aktif Mevduatlar', index=False)
        
        # Kapanmış mevduatlar
        kapanmis_df = df[pd.to_datetime(df['vade_bitis']).dt.date < date.today()]
        if not kapanmis_df.empty:
            kapanmis_df.to_excel(writer, sheet_name='Kapanmış Mevduatlar', index=False)
        
        # Özet sayfası
        ozet_df = pd.DataFrame({
            'Metrik': ['Toplam Mevduat Sayısı', 'Aktif Mevduat Sayısı', 'Ortalama Vade (Gün)'],
            'Değer': [
                len(df),
                len(aktif_df),
                hesapla_ortalama_vade(aktif_df) if not aktif_df.empty else 0
            ]
        })
        ozet_df.to_excel(writer, sheet_name='Özet', index=False)
    
    return output.getvalue()

def guncelle_mevcut_kayitlar():
    """Mevcut kayıtları güncelle"""
    if 'mevduatlar' in st.session_state and st.session_state.mevduatlar:
        for m in st.session_state.mevduatlar:
            # TL mevduat için USD karşılığı ve başabaş kur hesapla
            if m['mevduat_tipi'] == 'TL Mevduat':
                guncel_kur = st.session_state.get('guncel_kur', get_guncel_kur())
                m['tutar_usd'] = round(m['tutar'] / guncel_kur, 2)
                
                # Başabaş kur hesapla
                vade_gun = (m['vade_bitis'] - m['vade_baslangic']).days
                stopaj_orani = hesapla_stopaj_orani(vade_gun, m['mevduat_tipi'])
                brut_getiri = ((m['faiz_orani']/100) / 365) * vade_gun
                net_getiri = brut_getiri * (1 - stopaj_orani/100)
                m['basabas_kur'] = round(guncel_kur * (1 + net_getiri), 4)