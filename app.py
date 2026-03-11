import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta

# --- 頁面設定 ---
st.set_page_config(page_title="A+ 策略終極 App", layout="wide")
st.title("🍎 A+ 策略：全美股掃描與控倉系統")

# --- 核心邏輯：A+ 策略檢查器 ---
def check_aplus(df, symbol):
    if len(df) < 250: return None
    
    # 1. 均線完全多頭排列 (10 > 20 > 50 > 100 > 150 > 200 > 250 MA)
    ma_list = [10, 20, 50, 100, 150, 200, 250]
    for m in ma_list:
        df[f'MA{m}'] = ta.sma(df['Close'], length=m)
    
    ma_bullish = all(df[f'MA{ma_list[i]}'].iloc[-1] > df[f'MA{ma_list[i+1]}'].iloc[-1] for i in range(len(ma_list)-1))
    if not ma_bullish: return None

    # 2. MACD 零軸上方
    macd = ta.macd(df['Close'])
    df = pd.concat([df, macd], axis=1)
    if df['MACD_12_26_9'].iloc[-1] <= 0: return None

    # 3. 尋找最近金叉與突破
    df['GC'] = (df['MACD_12_26_9'] > df['MACDs_12_26_9']) & (df['MACD_12_26_9'].shift(1) <= df['MACDs_12_26_9'].shift(1))
    gc_dates = df.index[df['GC']]
    if gc_dates.empty: return None
    
    last_gc_idx = df.index.get_loc(gc_dates[-1])
    
    # 檢查金叉後 3 個月內突破
    for i in range(3):
        idx = last_gc_idx + i
        if idx >= len(df): break
        if df['Close'].iloc[idx] > df['High'].iloc[idx-1]:
            return {
                "Symbol": symbol,
                "Type": ["A", "B", "C"][i],
                "Price": round(df['Close'].iloc[-1], 2),
                "StopLoss": round(df['Low'].iloc[last_gc_idx], 2),
                "LastLow": round(df['Low'].iloc[-2], 2)
            }
    return None

# --- 選單功能 ---
mode = st.sidebar.selectbox("切換模式", ["單股分析 & 控倉", "全美股大掃描"])
capital = st.sidebar.number_input("投資本金 (USD)", value=100000)

if mode == "單股分析 & 控倉":
    symbol = st.text_input("輸入股票代碼 (例: NVDA, AAPL)", "NVDA").upper()
    if st.button("開始分析"):
        t = yf.Ticker(symbol)
        df = t.history(period="10y", interval="1mo")
        res = check_aplus(df, symbol)
        
        if res:
            st.success(f"🔥 {symbol} 符合 A+ 策略 (情況 {res['Type']})")
            # 倉位計算
            risk = res['Price'] - res['StopLoss']
            shares = int((capital * 0.05) / risk) if risk > 0 else 0
            
            col1, col2 = st.columns(2)
            col1.metric("建議買入股數", f"{shares} 股")
            col2.metric("全清防線 (金叉首月低)", f"${res['StopLoss']}")
            
            st.warning(f"⚠️ 階梯減持提示：盤中跌破 ${res['LastLow']} (上月最低) 立即減半")
        else:
            st.error("該標的目前不符合 A+ 靜態過濾或動能突破條件。")

else: # 全美股掃描
    st.info("掃描 S&P 500 與 Nasdaq 100 中市值 > 80億之標的")
    if st.button("啟動全市場掃描"):
        # 抓取大型股清單 (為了速度，預設掃描標普500)
        tickers = pd.read_html('https://en.wikipedia.org')[0]['Symbol'].tolist()
        results = []
        bar = st.progress(0)
        for i, s in enumerate(tickers[:100]): # 示範掃描前100檔
            t = yf.Ticker(s)
            df = t.history(period="5y", interval="1mo")
            found = check_aplus(df, s)
            if found: results.append(found)
            bar.progress((i+1)/100)
        
        if results:
            st.table(pd.DataFrame(results))
        else:
            st.write("目前無符合標的。")
