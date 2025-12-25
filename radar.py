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
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Telegram Hatası: {e}")

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Sniper v13.7 Telegram", layout="wide")

@st.cache_resource
def get_crypto():
    return ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'},
        'urls': { 'api': { 'public': 'https://fapi.binance.com/fapi/v1', 'private': 'https://fapi.binance.com/fapi/v1' } }
    })

exchange = get_crypto()

# --- YAN MENÜ ---
st.sidebar.title("📡 Telegram Sniper")
if 'running' not in st.session_state: st.session_state.running = False
def toggle(): st.session_state.running = not st.session_state.running

if st.session_state.running:
    st.sidebar.button("🛑 SİSTEMİ DURDUR", on_click=toggle, type="primary", use_container_width=True)
else:
    st.sidebar.button("🚀 SİSTEMİ BAŞLAT", on_click=toggle, type="secondary", use_container_width=True)

periyot = st.sidebar.selectbox("Tarama Periyodu:", ["5m", "15m", "1h", "4h", "1d"], index=1)
hacim_limiti = st.sidebar.number_input("Min 24s Hacim (M$):", value=20)

if 'sent_signals' not in st.session_state:
    st.session_state.sent_signals = []

def check_and_notify(symbol):
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe=periyot, limit=100)
        df = pd.DataFrame(bars, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        close = df['c'].iloc[-1]
        
        ema20 = ta.trend.ema_indicator(df['c'], 20)
        ema50 = ta.trend.ema_indicator(df['c'], 50)
        
        diff = (ema50.iloc[-1] - ema20.iloc[-1]) / ema20.iloc[-1] * 100
        is_breaking_up = close > df['h'].iloc[-2]
        rsi = ta.momentum.rsi(df['c'], 14).iloc[-1]
        
        if 0 < diff < 0.22 and is_breaking_up and rsi > 50:
            stop_price = round(ema50.iloc[-1] * 0.995, 6)
            tp_price = round(close + ((close - stop_price) * 2), 6)
            coin_name = symbol.split('/')[0]
            
            signal_key = f"{coin_name}_{periyot}_{round(close, 4)}"
            if signal_key not in st.session_state.sent_signals:
                msg = (f"🚀 *YENİ SİNYAL: {coin_name}* ({periyot})\n\n"
                       f"📈 *Giriş:* {round(close, 6)}\n"
                       f"🛡 *Stop:* {stop_price}\n"
                       f"🎯 *Hedef:* {tp_price}\n"
                       f"⏰ {datetime.now().strftime('%H:%M:%S')}")
                send_telegram_msg(msg)
                st.session_state.sent_signals.append(signal_key)
                if len(st.session_state.sent_signals) > 30: st.session_state.sent_signals.pop(0)

            return {"COİN": coin_name, "GİRİŞ": close, "STOP": stop_price, "HEDEF": tp_price}
    except: return None

# --- ANA EKRAN ---
if st.session_state.running:
    status = st.empty()
    status.success(f"📡 Tarama Aktif! Sinyaller Telegram Grubuna Gönderiliyor... ({periyot})")
    
    tickers = exchange.fapiPublicGetTicker24hr()
    symbols = [f"{t['symbol'][:-4]}/USDT:USDT" for t in tickers if float(t['quoteVolume']) > (hacim_limiti * 1000000)]
    
    found = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for result in executor.map(check_and_notify, symbols):
            if result: found.append(result)
            
    if found:
        st.table(pd.DataFrame(found))
    
    time.sleep(30)
    st.rerun()
else:
    st.write("### ⏸ Sistem Beklemede")
    st.info("Kodu GitHub'a yükleyip Streamlit Cloud'da çalıştırdığında mesajlar gelmeye başlayacak.")