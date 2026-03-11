import streamlit as st
import yfinance as yf
import pandas as pd

# --- 頁面設定 ---
st.set_page_config(page_title="A+ 策略終極 App", layout="wide")
st.title("🍎 A+ 策略：全美股掃描與控倉系統")

# --- 核心邏輯：純 Pandas 計算 (不依賴 ta 套件) ---
def check_aplus(df, symbol):
    if len(df) < 255: return None
    
    # 1. 均線完全多頭排列 (10 > 20 > 50 > 100 > 150 > 200 > 250 MA)
    ma_list = [10, 20, 50, 100, 150, 200, 250]
    for m in ma_list:
        df[f'MA{m}'] = df['Close'].rolling(window=m).mean()
    
    # 檢查當前 MA 是否完全多頭
    ma_bullish = all(df[f'MA{ma_list[i]}'].iloc[-1] > df[f'MA{ma_list[i+1]}'].iloc[-1] for i in range(len(ma_list)-1))
    if not ma_bullish: return None

    # 2. MACD 計算 (純 Pandas 寫法)
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['DIF'] = ema12 - ema26
    df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean()
    
    # 判斷 MACD 是否在零軸上方
    if df['DIF'].iloc[-1] <= 0: return None

    # 3. 尋找最近金叉 (DIF 上穿 DEA)
    df['GC'] = (df['DIF'] > df['DEA']) & (df['DIF'].shift(1) <= df['DEA'].shift(1))
    gc_dates = df.index[df['GC']]
    if gc_dates.empty: return None
    
    last_gc_idx = df.index.get_loc(gc_dates[-1])
    
    # 檢查金叉當月或後 2 個月內有無收盤突破上月最高
    for i in range(3):
        idx = last_gc_idx + i
        if idx >= len(df): break
        if df['Close'].iloc[idx] > df['High'].iloc[idx-1]:
            return {
                "Symbol": symbol,
                "Type": ["A", "B", "C"][i],
                "Price": round(float(df['Close'].iloc[-1]), 2),
                "StopLoss": round(float(df['Low'].iloc[last_gc_idx]), 2),
                "LastLow": round(float(df['Low'].iloc[-2]), 2),
                "LastHigh": round(float(df['High'].iloc[-2]), 2)
            }
    return None

# --- UI 功能 ---
mode = st.sidebar.selectbox("切換模式", ["單股分析 & 控倉", "美股精選掃描"])
capital = st.sidebar.number_input("投資本金 (USD)", value=100000)

if mode == "單股分析 & 控倉":
    symbol = st.text_input("輸入代碼 (如 NVDA, AAPL)", "NVDA").upper()
    if st.button("開始分析"):
        t = yf.Ticker(symbol)
        df = t.history(period="10y", interval="1mo")
        res = check_aplus(df, symbol)
        
        if res:
            st.success(f"🔥 {symbol} 符合 A+ 策略 (情況 {res['Type']})")
            risk = res['Price'] - res['StopLoss']
            shares = int((capital * 0.05) / risk) if risk > 0 else 0
            st.metric("建議買入股數", f"{shares} 股")
            st.error(f"🔴 全清防線：${res['StopLoss']}")
            st.warning(f"🟡 階梯減持提示：盤中跌破 ${res['LastLow']} 立即減半")
        else:
            st.info("該標的目前不符合 A+ 條件。")

else: # 掃描模式
    if st.button("掃描 Nasdaq 100 指數股"):
        # 預設掃描 Nasdaq 100 較具代表性且市值大
        tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "COST", "NFLX"] # 此處可自行擴充
        results = []
        progress = st.progress(0)
        for i, s in enumerate(tickers):
            t = yf.Ticker(s)
            df = t.history(period="10y", interval="1mo")
            found = check_aplus(df, s)
            if found: results.append(found)
            progress.progress((i+1)/len(tickers))
        
        if results: st.table(pd.DataFrame(results))
        else: st.write("目前無符合標的。")
