import streamlit as st
import ccxt
import pandas as pd
import ta
from concurrent.futures import ThreadPoolExecutor
from streamlit_autorefresh import st_autorefresh

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Sniper v13.6 Turbo (Stable)", layout="wide")

# --- BAĞLANTI OLUŞTURMA ---
@st.cache_resource
def get_crypto():
    return ccxt.binance({
        'enableRateLimit': True,
        'rateLimit': 300,  # hızlı tarama için optimize
        'options': {'defaultType': 'future'},
        'urls': {'api': {'public': 'https://fapi.binance.com/fapi/v1', 'private': 'https://fapi.binance.com/fapi/v1'}}
    })

exchange = get_crypto()

# --- YAN MENÜ ---
st.sidebar.title("⚡ Hızlı Tarama Paneli")
if 'running' not in st.session_state:
    st.session_state.running = False

def toggle():
    st.session_state.running = not st.session_state.running

if st.session_state.running:
    st.sidebar.button("🛑 DURDUR", on_click=toggle, type="primary", use_container_width=True)
else:
    st.sidebar.button("🚀 BAŞLAT", on_click=toggle, type="secondary", use_container_width=True)

# --- PERİYOT SEÇİMİ ---
periyot_gorunum = st.sidebar.selectbox(
    "Periyot:",
    ["5 Dakika", "15 Dakika", "1 Saat", "4 Saat", "1 Günlük"],
    index=0
)
periyot_map = {
    "5 Dakika": "5m",
    "15 Dakika": "15m",
    "1 Saat": "1h",
    "4 Saat": "4h",
    "1 Günlük": "1d"
}
periyot = periyot_map[periyot_gorunum]

# --- DİĞER AYARLAR ---
hacim_limiti = st.sidebar.number_input("Min Hacim (M$):", value=20)
tarama_araligi = st.sidebar.slider("Tarama Yenileme Süresi (sn):", 10, 60, 20)

# --- SİNYAL ANALİZİ ---
def check_signal_with_targets(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe=periyot, limit=80)
        df = pd.DataFrame(bars, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        if len(df) < 50 or df['c'].isnull().any():
            return None
        
        close = df['c'].iloc[-1]
        ema20 = ta.trend.ema_indicator(df['c'], 20)
        ema50 = ta.trend.ema_indicator(df['c'], 50)
        rsi = ta.momentum.rsi(df['c'], 14).iloc[-1]

        diff = (ema50.iloc[-1] - ema20.iloc[-1]) / ema20.iloc[-1] * 100
        is_breaking_up = close > df['h'].iloc[-2]

        if 0 < diff < 0.22 and is_breaking_up and rsi > 50:
            stop = ema50.iloc[-1] * 0.995
            tp = close * 1.01  # sabit %1 hedef
            return {
                "COİN": symbol.split('/')[0],
                "GİRİŞ": round(close, 6),
                "STOP": round(stop, 6),
                "HEDEF (TP)": round(tp, 6),
                "DURUM": "💎 GÜÇLÜ" if close > ema50.iloc[-1] else "📈 DÖNÜŞ"
            }
    except Exception:
        return None

# --- ANA EKRAN ---
st.header("🎯 Sniper v13.6 Turbo (Stable)")
status = st.empty()
tablo = st.empty()

# --- OTO YENİLEME ---
count = st_autorefresh(interval=tarama_araligi * 1000, limit=None, key="tarama_refresh")

if st.session_state.running:
    status.info(f"⚡ {periyot_gorunum} periyodunda hızlı tarama yapılıyor...")

    tickers = exchange.fapiPublicGetTicker24hr()
    symbols = [
        f"{t['symbol'][:-4]}/USDT:USDT"
        for t in tickers if float(t['quoteVolume']) > (hacim_limiti * 1_000_000)
    ]

    found = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for result in executor.map(check_signal_with_targets, symbols):
            if result:
                found.append(result)

    if found:
        tablo.dataframe(pd.DataFrame(found))
        status.success(f"✅ {len(found)} yeni işlem planı bulundu.")
    else:
        status.warning("⏳ Uygun sinyal bulunamadı.")
else:
    st.write("### ⏸ Sistem Beklemede")
    st.info("Başlatmak için 🚀 BAŞLAT'a basın.")
