import streamlit as st
import pandas as pd
from datetime import datetime, date
import plotly.express as px
import locale
from mevduat import get_guncel_kur, veri_giris_formu, mevduat_listesi_tab, hesapla_ortalama_vade, export_to_excel, guncelle_mevcut_kayitlar
from constants import TL_KOLONLAR, USD_KOLONLAR, PORTFOY_KOLONLAR

# Türkçe tarih formatı
locale.setlocale(locale.LC_ALL, 'turkish')

st.set_page_config(
    page_title="Portföy Takip",
    page_icon="💸",
    layout="wide"
)

def hesapla_tl_tutarlar(df, guncel_kur):
    """USD mevduatları TL'ye çevirme işlemi"""
    # DataFrame'in bir kopyasını oluştur
    df_copy = df.copy()
    
    # Hesaplamaları kopyada yap
    df_copy.loc[:, 'tutar_tl'] = df_copy.apply(
        lambda x: x['tutar'] if x['mevduat_tipi'] == 'TL Mevduat' 
        else x['tutar'] * guncel_kur, 
        axis=1
    )
    
    df_copy.loc[:, 'net_faiz_tl'] = df_copy.apply(
        lambda x: x['net_faiz'] if x['mevduat_tipi'] == 'TL Mevduat'
        else x['net_faiz_usd'] * guncel_kur,
        axis=1
    )
    return df_copy

def goster_metrikler(df, prefix=""):
    """Metrik gösterimi"""
    toplam_anapara_tl = df['tutar_tl'].sum()
    toplam_net_faiz_tl = df['net_faiz_tl'].sum()
    toplam_getiri_orani = (toplam_net_faiz_tl / toplam_anapara_tl * 100) if toplam_anapara_tl > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(f"{prefix}Mevduat", f"{len(df)} Adet")
    with col2:
        st.metric(f"{prefix}Anapara (TL)", f"{toplam_anapara_tl:,.0f} ₺")
    with col3:
        st.metric(f"{prefix}Net Faiz (TL)", f"{toplam_net_faiz_tl:,.0f} ₺")
    with col4:
        if prefix:
            ort_vade = hesapla_ortalama_vade(df)
            st.metric("Ortalama Vade", f"{ort_vade:.0f} gün")
        else:
            st.metric("Toplam Getiri Oranı", f"%{toplam_getiri_orani:.2f}")

def olustur_dagilim_grafigi(df, values, names, title, hole=0.4):
    """Pasta grafiği oluşturma"""
    fig = px.pie(
        df,
        values=values,
        names=names,
        title=title,
        hole=hole
    )
    return fig

def olustur_vade_ozeti(aktif_df):
    """Vade dağılımı özeti"""
    def vade_grubu(gun):
        if gun <= 30: return "1 aya kadar"
        elif gun <= 90: return "1-3 ay"
        elif gun <= 180: return "3-6 ay"
        elif gun <= 365: return "6-12 ay"
        else: return "12+ ay"
    
    vade_sirasi = ["1 aya kadar", "1-3 ay", "3-6 ay", "6-12 ay", "12+ ay"]
    
    # DataFrame'in bir kopyasını oluştur
    df_copy = aktif_df.copy()
    df_copy.loc[:, 'vade_grubu'] = df_copy['kalan_gun'].apply(vade_grubu)
    
    vade_ozet = df_copy.groupby('vade_grubu').agg({
        'tutar_tl': 'sum',
        'net_faiz_tl': 'sum'
    }).reindex(vade_sirasi).reset_index()
    
    # NaN değerleri 0 ile doldur
    vade_ozet = vade_ozet.fillna(0)
    
    vade_ozet.loc[:, 'pay'] = (vade_ozet['tutar_tl'] / vade_ozet['tutar_tl'].sum() * 100).round(2)
    return vade_ozet

def portfoy_ozeti(df):
    """Toplam portföy özeti"""
    st.write("### Portföy Özeti")
    
    guncel_kur = st.session_state.get('guncel_kur', get_guncel_kur())
    df = hesapla_tl_tutarlar(df, guncel_kur)
    
    goster_metrikler(df)
    
    st.write("### Döviz Bazlı Dağılım")
    doviz_dagilimi = df.groupby('mevduat_tipi').agg({
        'tutar_tl': 'sum',
        'net_faiz_tl': 'sum'
    }).round(2)
    
    fig = olustur_dagilim_grafigi(
        doviz_dagilimi,
        'tutar_tl',
        doviz_dagilimi.index,
        'Döviz Bazlı Portföy Dağılımı'
    )
    st.plotly_chart(fig, use_container_width=True)

def portfoy_analizi(df):
    """Portföy analizi sekmesi"""
    aktif_df = df[pd.to_datetime(df['vade_bitis']).dt.date >= date.today()]
    
    if aktif_df.empty:
        st.warning("Aktif mevduat bulunmamaktadır!")
        return
        
    st.write("### Aktif Portföy Özeti")
    
    guncel_kur = st.session_state.get('guncel_kur', get_guncel_kur())
    aktif_df = hesapla_tl_tutarlar(aktif_df, guncel_kur)
    
    goster_metrikler(aktif_df, "Aktif ")
    
    # Döviz dağılımı grafiği
    st.write("### Döviz Dağılımı")
    doviz_ozet = aktif_df.groupby('mevduat_tipi').agg({
        'tutar_tl': 'sum',
        'net_faiz_tl': 'sum'
    }).round(2)
    
    doviz_ozet.columns = ['Toplam Anapara (TL)', 'Toplam Net Faiz (TL)']
    doviz_ozet['Portföy Payı (%)'] = (doviz_ozet['Toplam Anapara (TL)'] / doviz_ozet['Toplam Anapara (TL)'].sum() * 100).round(2)
    
    col1, col2 = st.columns(2)
    with col1:
        # Döviz dağılımı pasta grafiği
        fig_doviz = olustur_dagilim_grafigi(
            doviz_ozet,
            'Toplam Anapara (TL)',
            doviz_ozet.index,
            'Döviz Bazlı Portföy Dağılımı'
        )
        st.plotly_chart(fig_doviz, use_container_width=True)
    
    with col2:
        # Döviz dağılımı tablo
        st.dataframe(
            doviz_ozet.style.format({
                'Toplam Anapara (TL)': '{:,.0f} ₺',
                'Toplam Net Faiz (TL)': '{:,.0f} ₺',
                'Portföy Payı (%)': '{:.2f}%'
            }),
            use_container_width=True
        )
    
    st.write("### Dağılım Grafikleri")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("#### Banka Dağılımı")
        goster_banka_dagilimi(aktif_df)
    
    with col2:
        st.write("#### Vade Dağılımı")
        goster_vade_dagilimi(aktif_df)
    
    goster_veri_aktarim_butonlari()

def goster_banka_dagilimi(aktif_df):
    """Banka dağılımı gösterimi"""
    # Sadece banka bazlı toplam hesaplama
    banka_ozet = aktif_df.groupby('banka').agg({
        'tutar_tl': ['count', 'sum'],
        'net_faiz_tl': 'sum'
    }).round(2)
    
    # Özet tablo
    banka_ozet.columns = ['Adet', 'Toplam Anapara (TL)', 'Toplam Net Faiz (TL)']
    banka_ozet['Portföy Payı (%)'] = (banka_ozet['Toplam Anapara (TL)'] / banka_ozet['Toplam Anapara (TL)'].sum() * 100).round(2)
    
    # Banka dağılımı pasta grafiği
    fig_banka = olustur_dagilim_grafigi(
        banka_ozet,
        'Toplam Anapara (TL)',
        banka_ozet.index,
        'Bankalara Göre Aktif Mevduat Dağılımı'
    )
    st.plotly_chart(fig_banka, use_container_width=True)
    
    # Banka bazlı özet tablo
    st.write("##### Banka Bazlı Özet")
    st.dataframe(
        banka_ozet.style.format({
            'Adet': '{:,.0f}',
            'Toplam Anapara (TL)': '{:,.0f} ₺',
            'Toplam Net Faiz (TL)': '{:,.0f} ₺',
            'Portföy Payı (%)': '{:.2f}%'
        }),
        use_container_width=True
    )

def goster_vade_dagilimi(aktif_df):
    """Vade dağılımı gösterimi"""
    vade_ozet = olustur_vade_ozeti(aktif_df)
    
    # NaN değerleri 0 ile doldur
    vade_ozet = vade_ozet.fillna(0)
    
    fig_vade = px.bar(
        vade_ozet,
        x='vade_grubu',
        y='tutar_tl',
        title='Vade Sürelerine Göre Aktif Mevduat Dağılımı',
        text=vade_ozet['tutar_tl'].apply(lambda x: f'{x:,.0f} ₺')
    )
    fig_vade.update_traces(textposition='inside')
    st.plotly_chart(fig_vade, use_container_width=True)
    
    vade_ozet_tablo = pd.DataFrame({
        'Vade Grubu': vade_ozet['vade_grubu'],
        'Toplam Anapara (TL)': vade_ozet['tutar_tl'].apply(lambda x: f'{x:,.0f} ₺'),
        'Toplam Net Faiz (TL)': vade_ozet['net_faiz_tl'].apply(lambda x: f'{x:,.0f} ₺'),
        'Portföy Payı (%)': vade_ozet['pay'].apply(lambda x: f'{x:.2f}%')
    })
    # Tablodaki NaN değerleri 0 ile doldur
    vade_ozet_tablo = vade_ozet_tablo.fillna('0 ₺')
    st.dataframe(vade_ozet_tablo, use_container_width=True)

def goster_veri_aktarim_butonlari():
    """Veri aktarım butonlarını göster"""
    st.write("### Veri Aktarımı")
    if st.button("Excel'e Aktar", type="primary"):
        excel_data = export_to_excel()
        if excel_data:
            st.download_button(
                label="Excel Dosyasını İndir",
                data=excel_data,
                file_name="mevduat_portfoy.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

def mevduat_listesi(df):
    """Mevduat listesi sekmesi"""
    # TL ve USD mevduatları ayır
    tl_df = df[df['mevduat_tipi'] == 'TL Mevduat']
    usd_df = df[df['mevduat_tipi'] == 'USD Mevduat']
    
    tab1, tab2 = st.tabs(["TL Mevduatlar", "USD Mevduatlar"])
    
    with tab1:
        if not tl_df.empty:
            mevduat_listesi_tab(tl_df, TL_KOLONLAR)
        else:
            st.info("TL mevduat bulunmamaktadır.")
            
    with tab2:
        if not usd_df.empty:
            mevduat_listesi_tab(usd_df, USD_KOLONLAR)
        else:
            st.info("USD mevduat bulunmamaktadır.")

def export_to_excel():
    """Excel'e aktarım için veriyi hazırla"""
    if 'mevduatlar' in st.session_state and st.session_state.mevduatlar:
        df = pd.DataFrame(st.session_state.mevduatlar)
        
        # Temel hesaplamalar
        aktif_df = df[pd.to_datetime(df['vade_bitis']).dt.date >= date.today()]
        aktif_tl = aktif_df[aktif_df['mevduat_tipi'] == 'TL Mevduat']
        aktif_usd = aktif_df[aktif_df['mevduat_tipi'] == 'USD Mevduat']
        guncel_kur = st.session_state.get('guncel_kur', get_guncel_kur())
        
        # Toplam portföy değerleri (TL cinsinden)
        toplam_tl_portfoy = aktif_tl['tutar'].sum()
        toplam_usd_portfoy_tl = aktif_usd['tutar'].sum() * guncel_kur
        toplam_portfoy = toplam_tl_portfoy + toplam_usd_portfoy_tl
        
        # Getiri hesaplamaları
        tl_getiri = (aktif_tl['net_faiz'].sum() / toplam_tl_portfoy) if toplam_tl_portfoy > 0 else 0
        usd_getiri = (aktif_usd['net_faiz_usd'].sum() / aktif_usd['tutar'].sum()) if len(aktif_usd) > 0 else 0
        toplam_getiri = ((aktif_tl['net_faiz'].sum() + aktif_usd['net_faiz_usd'].sum() * guncel_kur) / 
                        toplam_portfoy) if toplam_portfoy > 0 else 0
        
        # Excel yazıcı oluştur
        excel_writer = pd.ExcelWriter('mevduat_portfoy.xlsx', engine='xlsxwriter')
        workbook = excel_writer.book
        
        # Formatlar
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'bg_color': '#D9D9D9'
        })
        money_tl = workbook.add_format({'num_format': '#,##0 ₺'})
        money_usd = workbook.add_format({'num_format': '#,##0 $'})
        percent = workbook.add_format({'num_format': '0.00%'})
        number = workbook.add_format({'num_format': '0'})
        kur = workbook.add_format({'num_format': '0.0000'})
        
        # Özet sayfası
        ozet = excel_writer.book.add_worksheet('Portföy Özeti')
        ozet.set_column('A:A', 40)
        ozet.set_column('B:B', 20)
        
        # Veri listesi
        data = [
            ['1. GENEL PORTFÖY BİLGİLERİ', ''],
            ['Toplam Mevduat Adedi', len(df)],
            ['Aktif Mevduat Adedi', len(aktif_df)],
            ['Kapanmış Mevduat Adedi', len(df) - len(aktif_df)],
            ['Ortalama Vade (Gün)', hesapla_ortalama_vade(aktif_df)],
            ['', ''],
            ['2. TL MEVDUAT BİLGİLERİ', ''],
            ['TL Mevduat Adedi', len(aktif_tl)],
            ['Toplam TL Anapara', aktif_tl['tutar'].sum()],
            ['Toplam TL Net Faiz', aktif_tl['net_faiz'].sum()],
            ['TL Portföy Getiri Oranı', tl_getiri],
            ['', ''],
            ['3. USD MEVDUAT BİLGİLERİ', ''],
            ['USD Mevduat Adedi', len(aktif_usd)],
            ['Toplam USD Anapara', aktif_usd['tutar'].sum()],
            ['Toplam USD Net Faiz', aktif_usd['net_faiz_usd'].sum()],
            ['USD Portföy Getiri Oranı', usd_getiri],
            ['', ''],
            ['4. TOPLAM PORTFÖY (TL)', ''],
            ['Toplam Portföy Değeri (TL)', toplam_portfoy],
            ['Toplam Net Faiz (TL)', aktif_tl['net_faiz'].sum() + aktif_usd['net_faiz_usd'].sum() * guncel_kur],
            ['Genel Portföy Getiri Oranı', toplam_getiri],
            ['', ''],
            ['5. DÖVİZ DAĞILIMI', ''],
            ['TL Portföy Oranı', toplam_tl_portfoy / toplam_portfoy if toplam_portfoy > 0 else 0],
            ['USD Portföy Oranı', toplam_usd_portfoy_tl / toplam_portfoy if toplam_portfoy > 0 else 0],
            ['', ''],
            ['6. GÜNCEL BİLGİLER', ''],
            ['Güncel USD/TL Kuru', guncel_kur],
            ['Rapor Tarihi', datetime.now().strftime('%d.%m.%Y %H:%M')]
        ]
        
        # Verileri yaz ve formatla
        for row, (label, value) in enumerate(data):
            ozet.write(row, 0, label)
            
            # Başlıklar
            if label.startswith(('1.', '2.', '3.', '4.', '5.', '6.')):
                ozet.write(row, 0, label, header_format)
                ozet.write(row, 1, value, header_format)
                continue
                
            # Boş satırlar
            if label == '':
                ozet.write(row, 1, value)
                continue
            
            # Değer formatlamaları
            if 'Adedi' in label or 'Gün' in label:
                ozet.write(row, 1, value, number)
            elif 'TL' in label and ('Anapara' in label or 'Faiz' in label or 'Değeri' in label):
                ozet.write(row, 1, value, money_tl)
            elif 'USD' in label and ('Anapara' in label or 'Faiz' in label):
                ozet.write(row, 1, value, money_usd)
            elif 'Oran' in label or 'Payı' in label:
                ozet.write(row, 1, value, percent)
            elif 'Kur' in label:
                ozet.write(row, 1, value, kur)
            else:
                ozet.write(row, 1, value)
        
        # Diğer sayfaları yaz
        if not df[df['mevduat_tipi'] == 'TL Mevduat'].empty:
            df[df['mevduat_tipi'] == 'TL Mevduat'][TL_KOLONLAR].to_excel(
                excel_writer, sheet_name='TL Mevduatlar', index=False
            )
        
        if not df[df['mevduat_tipi'] == 'USD Mevduat'].empty:
            df[df['mevduat_tipi'] == 'USD Mevduat'][USD_KOLONLAR].to_excel(
                excel_writer, sheet_name='USD Mevduatlar', index=False
            )
        
        excel_writer.close()
        
        with open('mevduat_portfoy.xlsx', 'rb') as f:
            return f.read()
    return None

def main():
    """Ana uygulama"""
    st.title("Portföy Takip 💸")
    
    if 'guncel_kur' not in st.session_state:
        st.session_state.guncel_kur = get_guncel_kur()
    
    guncelle_mevcut_kayitlar()
    
    kur_col1, kur_col2 = st.columns([3, 1])
    with kur_col1:
        st.info(f"Güncel USD/TL Kuru: {st.session_state.guncel_kur:.4f} ₺")
    with kur_col2:
        if st.button("Güncel Kuru Getir", type="primary"):
            st.session_state.guncel_kur = get_guncel_kur()
            st.rerun()
    
    tab1, tab2, tab3 = st.tabs(["Veri Girişi", "Mevduat Listesi", "Portföy Analizi"])
    
    with tab1:
        veri_giris_formu()
    
    if 'mevduatlar' in st.session_state and st.session_state.mevduatlar:
        df = pd.DataFrame(st.session_state.mevduatlar)
        
        with tab2:
            mevduat_listesi(df)
        
        with tab3:
            portfoy_analizi(df)
    else:
        with tab2, tab3:
            st.warning("Henüz kayıtlı mevduat bulunmamaktadır!")

if __name__ == "__main__":
    main()