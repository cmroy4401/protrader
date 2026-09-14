import time
import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()

OTHER_GLOBAL_CACHE = {
    "HANGSENG": {"symbol": "HANGSENG", "ltp": 16500.0, "ch": 100.0, "chp": 0.61, "market_status": "RED"},
    "FTSE": {"symbol": "FTSE", "ltp": 7900.0, "ch": 40.0, "chp": 0.51, "market_status": "RED"},
    "DAX": {"symbol": "DAX", "ltp": 18200.0, "ch": 80.0, "chp": 0.44, "market_status": "RED"},
    "CAC": {"symbol": "CAC", "ltp": 8100.0, "ch": 30.0, "chp": 0.37, "market_status": "RED"},
    "KOSPI": {"symbol": "KOSPI", "ltp": 2700.0, "ch": 15.0, "chp": 0.56, "market_status": "RED"},
    "SHANGHAI": {"symbol": "SHANGHAI", "ltp": 3050.0, "ch": 12.0, "chp": 0.39, "market_status": "RED"},
}

def load_other_cache_safely():
    try:
        cache_file = Path(__file__).parent / "market_cache.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                p_data = json.load(f)
                if "other_global" in p_data:
                    return p_data["other_global"]
    except Exception:
        pass
    return {}

def fetch_tradingview_other_global(session, api_timeout, load_cache_func, save_cache_func, health_ok_func, health_fail_func):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/"
    }
    payload = {
        "symbols": {
            "tickers": [
                "TVC:HSI", "HSI:HSI", "TVC:UKX", "TVC:DEU40", "DAX:DAX",
                "TVC:CAC40", "TVC:KOSPI", "SSE:000001", "SH:000001"
            ]
        },
        "columns": ["close", "change", "change_abs"]
    }
    
    try:
        r = session.post(
            "https://scanner.tradingview.com/global/scan",
            json=payload,
            headers=headers,
            timeout=api_timeout
        )
        if r.status_code == 200:
            health_ok_func("tradingview")
            data = r.json()
            if data and data.get("data"):
                cached_other = load_other_cache_safely()
                for k, v in cached_other.items():
                    OTHER_GLOBAL_CACHE[k] = v

                for row in data.get("data", []):
                    s = row.get("s", "")
                    vals = row.get("d", [])
                    if len(vals) >= 3:
                        p = float(vals[0] or 0)
                        chp = float(vals[1] or 0)
                        ch = float(vals[2] or 0)
                        if p <= 0: continue
                        item_data = {"ltp": round(p, 2), "ch": round(ch, 2), "chp": round(chp, 2)}
                        
                        if "HSI" in s: OTHER_GLOBAL_CACHE["HANGSENG"] = {**item_data, "symbol": "HANGSENG", "market_status": "RED"}
                        elif "UKX" in s: OTHER_GLOBAL_CACHE["FTSE"] = {**item_data, "symbol": "FTSE", "market_status": "RED"}
                        elif "DEU40" in s or "DAX" in s: OTHER_GLOBAL_CACHE["DAX"] = {**item_data, "symbol": "DAX", "market_status": "RED"}
                        elif "CAC40" in s: OTHER_GLOBAL_CACHE["CAC"] = {**item_data, "symbol": "CAC", "market_status": "RED"}
                        elif "KOSPI" in s: OTHER_GLOBAL_CACHE["KOSPI"] = {**item_data, "symbol": "KOSPI", "market_status": "RED"}
                        elif "000001" in s: OTHER_GLOBAL_CACHE["SHANGHAI"] = {**item_data, "symbol": "SHANGHAI", "market_status": "RED"}
                
                persisted = load_cache_func()
                persisted["other_global"] = OTHER_GLOBAL_CACHE
                save_cache_func(persisted)
    except Exception as e:
        health_fail_func("tradingview", str(e))

@router.get("/api/other-global")
def get_other_global(symbol: str):
    sym = symbol.upper()
    cached_other = load_other_cache_safely()
    for k, v in cached_other.items():
        OTHER_GLOBAL_CACHE[k] = v

    if sym in OTHER_GLOBAL_CACHE:
        return OTHER_GLOBAL_CACHE[sym]
    return {"symbol": symbol.upper(), "ltp": 0, "ch": 0, "chp": 0, "market_status": "UNKNOWN"}
