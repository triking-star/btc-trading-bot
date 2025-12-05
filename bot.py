#!/usr/bin/env python3

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import pytz
import time

# ===== CONFIG =====

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = '7426005448'
SYMBOL = 'BTC'
RSI_PERIOD = 14
RSI_OVERBOUGHT = 45
RSI_OVERSOLD = 35
EMA_FAST = 12
EMA_SLOW = 26

def send_telegram_message(msg):
    """ส่ง Message ไป Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        'chat_id': CHAT_ID,
        'text': msg,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print(f"✅ Message sent at {datetime.now().strftime('%H:%M:%S')}")
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_btc_data(max_retries=3, timeout=15):
    """ดึงข้อมูล BTC จาก CoinGecko with timeout and retry"""
    for attempt in range(max_retries):
        try:
            url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=365&interval=daily"
            headers = {'User-Agent': 'Mozilla/5.0'}
            print(f"📡 Fetching BTC data (attempt {attempt+1}/{max_retries})...")
            start_time = datetime.now()
            response = requests.get(url, headers=headers, timeout=timeout)
            if response.status_code != 200:
                raise Exception(f"API status {response.status_code}")
            data = response.json()
            prices = data['prices']
            df = pd.DataFrame({
                'timestamp': [datetime.fromtimestamp(p[0]/1000) for p in prices],
                'close': [p[1] for p in prices]
            })
            df['open'] = df['close'].shift(1).fillna(df['close'])
            df['high'] = df['close'].rolling(window=2, min_periods=1).max()
            df['low'] = df['close'].rolling(window=2, min_periods=1).min()
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"✅ Got {len(df)} candles in {elapsed:.1f}s")
            return df.reset_index(drop=True)
        except requests.Timeout:
            print(f"⚠️ Timeout on attempt {attempt+1}")
            if attempt < max_retries - 1:
                print(f"⏳ Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print(f"❌ Failed after {max_retries} attempts")
                return None
        except Exception as e:
            print(f"❌ Error: {e}")
            if attempt < max_retries - 1:
                print(f"⏳ Retrying in 5 seconds...")
                time.sleep(5)
            else:
                return None

def calculate_rsi(prices, period=14):
    """Calculate RSI using NumPy"""
    deltas = np.diff(prices)
    seed = deltas[:period+1]
    up = seed[seed>=0].sum()/period
    down = -seed[seed<0].sum()/period
    rs = up/down if down != 0 else 0
    rsi = np.zeros_like(prices)
    rsi[:period] = 100. - 100./(1. + rs)

    for i in range(period, len(prices)):
        delta = deltas[i-1]
        if delta>0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta
        up = (up*(period-1) + upval)/period
        down = (down*(period-1) + downval)/period
        rs = up/down if down != 0 else 0
        rsi[i] = 100. - 100./(1. + rs)
    return rsi

def calculate_ema(prices, period):
    """Calculate EMA using NumPy"""
    ema = np.zeros_like(prices, dtype=float)
    ema[0] = prices[0]
    multiplier = 2.0 / (period + 1.0)
    for i in range(1, len(prices)):
        ema[i] = prices[i] * multiplier + ema[i-1] * (1 - multiplier)
    return ema

def get_thailand_time():
    """ดึงเวลา Thailand (UTC+7)"""
    utc_tz = pytz.UTC
    thailand_tz = pytz.timezone('Asia/Bangkok')
    utc_time = datetime.now(utc_tz)
    thailand_time = utc_time.astimezone(thailand_tz)
    return thailand_time

def send_heartbeat():
    """ส่ง Heartbeat status ทุก 5 นาที"""
    thailand_time = get_thailand_time()
    timestamp = thailand_time.strftime('%Y-%m-%d %H:%M:%S')
    heartbeat_msg = (
        f"✅ *Bot Status Check - Still Running!*\n\n"
        f"⏰ Check Time: `{timestamp}`\n"
        f"🤖 Status: HEALTHY ✅\n"
        f"🔄 Service: Monitoring BTC 24/7\n"
        f"🚨 Alert System: Active & Ready"
    )
    send_telegram_message(heartbeat_msg)
    print("✅ Heartbeat sent to Telegram")

def analyze_market():
    """วิเคราะห์ BTC"""
    try:
        thailand_time = get_thailand_time()
        timestamp = thailand_time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n🔍 [{timestamp}] Analyzing BTC...")
        df = get_btc_data()
        if df is None or len(df) == 0:
            raise Exception("No data")

        df['rsi'] = calculate_rsi(df['close'].values, RSI_PERIOD)
        df['ema_fast'] = calculate_ema(df['close'].values, EMA_FAST)
        df['ema_slow'] = calculate_ema(df['close'].values, EMA_SLOW)

        df_clean = df.dropna(subset=['rsi', 'ema_fast', 'ema_slow']).copy()
        if len(df_clean) == 0:
            raise Exception("No valid data")

        last_row = df_clean.iloc[-1]
        prev_row = df_clean.iloc[-2] if len(df_clean) > 1 else last_row

        last_rsi = float(last_row['rsi'])
        last_price = float(last_row['close'])
        ema_fast_last = float(last_row['ema_fast'])
        ema_slow_last = float(last_row['ema_slow'])
        ema_fast_prev = float(prev_row['ema_fast'])
        ema_slow_prev = float(prev_row['ema_slow'])

        print(f"📊 BTC: ${last_price:,.2f} | RSI: {last_rsi:.2f}")
        print(f"📈 EMA {EMA_FAST}: {ema_fast_last:.2f} | EMA {EMA_SLOW}: {ema_slow_last:.2f}")

        alerts = []

        if last_rsi >= RSI_OVERBOUGHT:
            alerts.append(f"🔥 *RSI OVERBOUGHT!* ({last_rsi:.2f})")
        elif last_rsi <= RSI_OVERSOLD:
            alerts.append(f"🥶 *RSI OVERSOLD!* ({last_rsi:.2f})")

        if ema_fast_prev <= ema_slow_prev and ema_fast_last > ema_slow_last:
            alerts.append(f"✨ *GOLDEN CROSS!* EMA {EMA_FAST} > EMA {EMA_SLOW}")
        if ema_fast_prev >= ema_slow_prev and ema_fast_last < ema_slow_last:
            alerts.append(f"💀 *DEATH CROSS!* EMA {EMA_FAST} < EMA {EMA_SLOW}")

        if alerts:
            print(f"🚨 Found {len(alerts)} alert(s)!")
            alert_msg = f"🚨 *TRADING ALERT!*\n\n"
            for i, alert in enumerate(alerts, 1):
                alert_msg += f"{i}. {alert}\n"
            alert_msg += f"\n📊 *Market Data:*\n"
            alert_msg += f"Price: `${last_price:,.2f}`\n"
            alert_msg += f"RSI(14): `{last_rsi:.2f}`\n"
            alert_msg += f"EMA {EMA_FAST}: `{ema_fast_last:.2f}`\n"
            alert_msg += f"EMA {EMA_SLOW}: `{ema_slow_last:.2f}`\n"
            alert_msg += f"Time: `{timestamp}`"
            send_telegram_message(alert_msg)
            print("🚨 ALERT SENT!")
        else:
        print("➡️ Market normal (no alerts, no Telegram message sent)")                f"Time: `{timestamp}`"
            
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        send_telegram_message(f"⚠️ *Bot Error!*\n`{type(e).__name__}: {str(e)[:150]}`")

if __name__ == "__main__":
    print("=" * 70)
    print("🤖 BTC Trading Bot - GitHub Actions Version (Optimized)")
    print("=" * 70)
    analyze_market()
