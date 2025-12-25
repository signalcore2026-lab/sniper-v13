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
        requests.post(url, json=payload, timeout=10)
    except:
        pass

@st.cache_resource
def get_crypto():
    return ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })

exchange = get_crypto()

st.set_page_config(page_title="Sniper v13.7 Pro", layout="wide")
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
        
        if 0 < diff < 0.22 and is_breaking_up:
            stop_price = round(ema50.iloc[-1] * 0.995, 6)
            tp_price = round(close + ((close - stop_price) * 2), 6)
            coin_name = symbol.split('/')[0]
            signal_key = f"{coin_name}_{periyot}"
            
            if signal_key not in st.session_state.sent_signals:
                msg = (f"🚀 *YENİ SİNYAL: {coin_name}* ({periyot})\n"
                       f"📈 *Giriş:* {round(close, 6)}\n"
                       f"🛡 *Stop:* {stop_price}\n"
                       f"🎯 *Hedef:* {tp_price}")
                send_telegram_msg(msg)
                st.session_state.sent_signals.append(signal_key)
            return {"COİN": coin_name, "GİRİŞ": close, "STOP": stop_price, "HEDEF": tp_price}
    except:
        return None

if st.session_state.running:
    st.success("📡 Tarama yapılıyor...")
    try:
        # Hatanın alındığı satırı korumaya aldık
        tickers = exchange.fetch_tickers() 
        symbols = [s for s in tickers if s.endswith('/USDT:USDT') and (tickers[s]['quoteVolume'] or 0) > (hacim_limiti * 1000000)]
        
        found = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(check_and_notify, symbols))
            found = [r for r in results if r]
            
        if found: st.table(pd.DataFrame(found))
    except Exception as e:
        st.warning("🔄 Binance bağlantısı yenileniyor, lütfen bekleyin...")
        time.sleep(5)
    
    time.sleep(30)
    st.rerun()
