import streamlit as st
import ccxt
import pandas as pd
import ta
import time
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# --- TELEGRAM BİLGİLERİN ---
TELEGRAM_TOKEN = "8508647074:AAFWmewidJ4_-q3pBd-t86m0NA-IbN1EuOc"
TELEGRAM_CHAT_ID = "-1003619321555"

def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=5)
    except:
        pass

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Sniper v14.2 Multi-EMA", layout="wide")

@st.cache_resource
def get_crypto():
    return ccxt.binance({
        'enableRateLimit': False, 
        'options': {'defaultType': 'future'}
    })

exchange = get_crypto()

# --- YAN MENÜ ---
st.sidebar.title("🚀 Sniper Radar v14.2")
if 'running' not in st.session_state: st.session_state.running = False
def toggle(): st.session_state.running = not st.session_state.running

if st.session_state.running:
    st.sidebar.button("🛑 SİSTEMİ DURDUR", on_click=toggle, type="primary", use_container_width=True)
else:
    st.sidebar.button("🚀 SİSTEMİ BAŞLAT", on_click=toggle, type="secondary", use_container_width=True)

# --- YENİ: EMA STRATEJİ SEÇİMİ ---
ema_secim = st.sidebar.selectbox("EMA Stratejisi Seç:", ["9 / 21 (Hızlı - Scalp)", "20 / 50 (Standart - Trend)", "50 / 200 (Güçlü - Golden Cross)"])

# Seçime göre EMA değerlerini belirle
if "9 / 21" in ema_secim:
    ema_hizli, ema_yavas = 9, 21
elif "20 / 50" in ema_secim:
    ema_hizli, ema_yavas = 20, 50
else:
    ema_hizli, ema_yavas = 50, 200

periyot = st.sidebar.selectbox("Grafik Zaman Dilimi:", ["1m", "5m", "15m", "1h", "4h", "1d"], index=1)
sıklık_etiket = st.sidebar.selectbox("Tarama Yenileme Sıklığı:", ["Anlık (Hızlı)", "1 Dakika", "5 Dakika"], index=0)

sıklık_saniye = 1
if sıklık_etiket == "1 Dakika": sıklık_saniye = 60
elif sıklık_etiket == "5 Dakika": sıklık_saniye = 300

hacim_limiti = st.sidebar.number_input("Min 24s Hacim (M$):", value=20)

if 'sent_signals' not in st.session_state:
    st.session_state.sent_signals = []

def check_and_notify(symbol):
    try:
        # Seçilen EMA değerine göre yeterli mum çek (En az ema_yavas kadar)
        bars = exchange.fetch_ohlcv(symbol, timeframe=periyot, limit=250)
        df = pd.DataFrame(bars, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        close = df['c'].iloc[-1]
        
        # Dinamik EMA hesaplama
        ema_fast_val = ta.trend.ema_indicator(df['c'], ema_hizli)
        ema_slow_val = ta.trend.ema_indicator(df['c'], ema_yavas)
        
        diff = (ema_slow_val.iloc[-1] - ema_fast_val.iloc[-1]) / ema_fast_val.iloc[-1] * 100
        is_breaking_up = close > df['h'].iloc[-2] 
        rsi = ta.momentum.rsi(df['c'], 14).iloc[-1]
        
        # Filtre: Fiyat yavaş EMA üzerinde ve RSI 50'den büyük
        if 0 < diff < 0.30 and is_breaking_up and rsi > 50:
            stop_price = round(ema_slow_val.iloc[-1] * 0.995, 6)
            tp_price = round(close + ((close - stop_price) * 2), 6)
            coin_name = symbol.split('/')[0]
            
            signal_key = f"{coin_name}_{periyot}_{ema_secim}_{round(close, 4)}"
            if signal_key not in st.session_state.sent_signals:
                msg = (f"🚀 *YENİ SİNYAL: {coin_name}*\n"
                       f"📊 *Strateji:* EMA {ema_hizli}/{ema_yavas}\n"
                       f"⏱ *Periyot:* {periyot}\n\n"
                       f"📈 *Giriş:* {round(close, 6)}\n"
                       f"🛡 *Stop:* {stop_price}\n"
                       f"🎯 *Hedef:* {tp_price}")
                send_telegram_msg(msg)
                st.session_state.sent_signals.append(signal_key)

            return {"COİN": coin_name, "GİRİŞ": close, "STOP": stop_price, "HEDEF": tp_price}
    except: return None

# --- ANA EKRAN ---
if st.session_state.running:
    st.success(f"📡 EMA {ema_hizli}/{ema_yavas} Taraması Aktif... ({periyot})")
    
    try:
        tickers = exchange.fetch_tickers()
        symbols = [s for s in tickers if s.endswith('/USDT:USDT') and (tickers[s]['quoteVolume'] or 0) > (hacim_limiti * 1000000)]
        
        found = []
        with ThreadPoolExecutor(max_workers=15) as executor:
            results = list(executor.map(check_and_notify, symbols))
            found = [r for r in results if r]
            
        if found: st.table(pd.DataFrame(found))
    except: pass
    
    time.sleep(sıklık_saniye)
    st.rerun()
else:
    st.info("### ⏸ Sistem Beklemede. Ayarları yapıp Başlat'a bas.")
