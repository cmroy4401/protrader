import time
import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()

GLOBAL_CACHE = {
    "DOW": {"symbol": "DOW", "ltp": 0.0, "ch": 0.0, "chp": 0.0, "market_status": "RED"},
    "DOW_FUT": {"symbol": "DOW_FUT", "ltp": 0.0, "market_status": "RED"}
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

def fetch_tradingview_global(session, api_timeout, load_cache_func, save_cache_func, health_ok_func, health_fail_func):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/"
    }
    payload = {
        "symbols": {
            "tickers": [
                "TVC:DJI", "CBOT:YM1!", "CBOT:YM", "DJ:DJI"
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
                persisted_global = load_cache_safely()
                for k, v in persisted_global.items():
                    GLOBAL_CACHE[k] = v

                for row in data.get("data", []):
                    s = row.get("s", "")
                    vals = row.get("d", [])
                    if len(vals) >= 3:
                        p = float(vals[0] or 0)
                        chp = float(vals[1] or 0)
                        ch = float(vals[2] or 0)
                        if p <= 0: continue
                        item_data = {"ltp": round(p, 2), "ch": round(ch, 2), "chp": round(chp, 2)}
                        
                        if "DJI" in s: 
                            GLOBAL_CACHE["DOW"] = {**item_data, "symbol": "DOW", "market_status": "RED"}
                        elif "YM" in s: 
                            GLOBAL_CACHE["DOW_FUT"] = {"symbol": "DOW_FUT", "ltp": round(p, 2), "market_status": "RED"}
                
                persisted = load_cache_func()
                persisted["global"] = GLOBAL_CACHE
                save_cache_func(persisted)
    except Exception as e:
        health_fail_func("tradingview", str(e))

@router.get("/api/global")
def get_global(symbol: str):
    sym = symbol.upper()
    
    cached_global = load_cache_safely()
    for k, v in cached_global.items():
        GLOBAL_CACHE[k] = v

    if sym == "DOW":
        dow_data = dict(GLOBAL_CACHE.get("DOW", {"symbol": "DOW", "ltp": 0, "ch": 0, "chp": 0, "market_status": "RED"}))
        fut_item = GLOBAL_CACHE.get("DOW_FUT", {})
        fut_val = fut_item.get("ltp", 0) if isinstance(fut_item, dict) else fut_item
        if fut_val > 0:
            dow_data["fut"] = fut_val
        return dow_data

    if sym in GLOBAL_CACHE:
        return GLOBAL_CACHE[sym]
    
    return {"symbol": symbol.upper(), "ltp": 0, "ch": 0, "chp": 0, "market_status": "UNKNOWN"}
