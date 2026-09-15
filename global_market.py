import time
import json
import requests
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()

GLOBAL_CACHE = {
    "DOW": {"symbol": "DOW", "ltp": 0.0, "ch": 0.0, "chp": 0.0, "market_status": "RED"},
    "DOW_FUT": {"symbol": "DOW_FUT", "ltp": 0.0, "market_status": "RED"},
    "NASDAQ": {"symbol": "NASDAQ", "ltp": 0.0, "ch": 0.0, "chp": 0.0, "market_status": "RED"},
    "SP500": {"symbol": "SP500", "ltp": 0.0, "ch": 0.0, "chp": 0.0, "market_status": "RED"},
    "NIKKEI": {"symbol": "NIKKEI", "ltp": 0.0, "ch": 0.0, "chp": 0.0, "market_status": "RED"},
    "BRENT": {"symbol": "BRENT", "ltp": 0.0, "ch": 0.0, "chp": 0.0, "market_status": "RED"},
    "XAUUSD": {"symbol": "XAUUSD", "ltp": 0.0, "ch": 0.0, "chp": 0.0, "market_status": "RED"}
}

def load_cache_safely():
    try:
        cache_file = Path(__file__).parent / "market_cache.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                p_data = json.load(f)
                if "global" in p_data:
                    return p_data["global"]
    except Exception:
        pass
    return {}

def fetch_yahoo_symbol(session, symbol, yahoo_ticker):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}?interval=1d"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        r = session.get(url, headers=headers, timeout=3.5)
        if r.status_code == 200:
            res = r.json()
            meta = res['chart']['result'][0]['meta']
            ltp = float(meta.get('regularMarketPrice', 0) or meta.get('chartPreviousClose', 0))
            prev_close = float(meta.get('chartPreviousClose', 0) or meta.get('previousClose', ltp))
            ch = ltp - prev_close
            chp = (ch / prev_close * 100) if prev_close > 0 else 0.0
            if ltp > 0:
                return {"symbol": symbol, "ltp": round(ltp, 2), "ch": round(ch, 2), "chp": round(chp, 2), "market_status": "RED"}
    except Exception:
        pass
    return None

def fetch_tradingview_global(session, api_timeout, load_cache_func, save_cache_func, health_ok_func, health_fail_func):
    try:
        cached_data = load_cache_safely()
        for k, v in cached_data.items():
            if k in GLOBAL_CACHE and v.get("ltp", 0) > 0:
                GLOBAL_CACHE[k] = v

        tv_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://www.tradingview.com",
            "Referer": "https://www.tradingview.com/"
        }
        tv_payload = {
            "symbols": {
                "tickers": [
                    "TVC:DJI", "CBOT:YM1!", "CBOT:YM", "CAPITALCOM:US30", 
                    "TVC:IXIC", "TVC:SPX", "SP:SPX", "AMEX:SPY", "TVC:NI225"
                ]
            },
            "columns": ["close", "change", "change_abs"]
        }
        
        r = session.post("https://scanner.tradingview.com/global/scan", json=tv_payload, headers=tv_headers, timeout=api_timeout)
        if r.status_code == 200:
            data = r.json()
            if data and data.get("data"):
                for row in data.get("data", []):
                    s = row.get("s", "")
                    vals = row.get("d", [])
                    if len(vals) >= 3:
                        p = float(vals[0] or 0)
                        chp = float(vals[1] or 0)
                        ch = float(vals[2] or 0)
                        if p <= 0: continue
                        item_data = {"ltp": round(p, 2), "ch": round(ch, 2), "chp": round(chp, 2)}
                        
                        if s == "TVC:DJI":
                            GLOBAL_CACHE["DOW"] = {**item_data, "symbol": "DOW", "market_status": "RED"}
                        elif "YM" in s or "US30" in s:
                            GLOBAL_CACHE["DOW_FUT"] = {"symbol": "DOW_FUT", "ltp": round(p, 2), "market_status": "RED"}
                        elif s == "TVC:IXIC":
                            GLOBAL_CACHE["NASDAQ"] = {**item_data, "symbol": "NASDAQ", "market_status": "RED"}
                        elif s == "TVC:NI225":
                            GLOBAL_CACHE["NIKKEI"] = {**item_data, "symbol": "NIKKEI", "market_status": "RED"}
                        elif "SPX" in s or "SPY" in s:
                            if "SPY" in s and p < 1000:
                                p *= 10; ch *= 10
                                item_data = {"ltp": round(p, 2), "ch": round(ch, 2), "chp": chp}
                            GLOBAL_CACHE["SP500"] = {**item_data, "symbol": "SP500", "market_status": "RED"}

        yahoo_mapping = {
            "BRENT": "BZ=F",
            "XAUUSD": "GC=F"
        }
        for sym, ticker in yahoo_mapping.items():
            y_data = fetch_yahoo_symbol(session, sym, ticker)
            if y_data:
                GLOBAL_CACHE[sym] = y_data

        health_ok_func("tradingview", "Hybrid global fetch successful.")
        persisted = load_cache_func()
        persisted["global"] = GLOBAL_CACHE
        save_cache_func(persisted)
    except Exception as e:
        health_fail_func("tradingview", str(e))

@router.get("/api/global")
def get_global(symbol: str):
    sym = symbol.upper()
    if sym in ["SNP500", "SPX"]:
        sym = "SP500"
    
    cached_global = load_cache_safely()
    for k, v in cached_global.items():
        if k in GLOBAL_CACHE and v.get("ltp", 0) > 0:
            GLOBAL_CACHE[k] = v

    if sym == "DOW":
        dow_data = dict(GLOBAL_CACHE.get("DOW", {"symbol": "DOW", "ltp": 0, "ch": 0, "chp": 0, "market_status": "RED"}))
        fut_item = GLOBAL_CACHE.get("DOW_FUT", {})
        fut_val = fut_item.get("ltp", 0) if isinstance(fut_item, dict) else fut_item
        if fut_val > 0:
            dow_data["fut"] = fut_val
        return dow_data

    if sym in ["GOLD", "XAUUSD"]:
        xau = GLOBAL_CACHE.get("XAUUSD", {"ltp": 0, "ch": 0, "chp": 0})
        mcx = GLOBAL_CACHE.get("GOLD_MCX", {"ltp": 0, "ch": 0, "chp": 0})
        return {
            "symbol": "GOLD",
            "ltp": xau.get("ltp", 0),
            "ch": xau.get("ch", 0),
            "chp": xau.get("chp", 0),
            "inr": mcx.get("ltp", 0),
            "inr_ch": mcx.get("ch", 0),
            "inr_chp": mcx.get("chp", 0),
            "market_status": "RED"
        }

    if sym in ["OIL", "CRUDE", "BRENT"]:
        mcx_crude = GLOBAL_CACHE.get("CRUDE_MCX", {"ltp": 0, "ch": 0, "chp": 0})
        brent = GLOBAL_CACHE.get("BRENT", {"ltp": 0, "ch": 0, "chp": 0})
        return {
            "symbol": "OIL",
            "ltp": mcx_crude.get("ltp", 0),
            "ch": mcx_crude.get("ch", 0),
            "chp": mcx_crude.get("chp", 0),
            "brent_ltp": brent.get("ltp", 0),
            "brent_ch": brent.get("ch", 0),
            "brent_chp": brent.get("chp", 0),
            "market_status": "RED"
        }

    if sym in GLOBAL_CACHE:
        return GLOBAL_CACHE[sym]
    
    return {"symbol": symbol.upper(), "ltp": 0, "ch": 0, "chp": 0, "market_status": "UNKNOWN"}
