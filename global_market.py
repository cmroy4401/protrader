import time
from fastapi import APIRouter

router = APIRouter()

GLOBAL_CACHE = {
    "SP500": {"symbol": "SP500", "ltp": 5850.00, "ch": 25.50, "chp": 0.44, "market_status": "RED"},
    "NIKKEI": {"symbol": "NIKKEI", "ltp": 0.0, "ch": 0.0, "chp": 0.0, "market_status": "RED"},
}

def fetch_tradingview_global(session, api_timeout, load_cache_func, save_cache_func, health_ok_func, health_fail_func):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/"
    }
    payload = {
        "symbols": {
            "tickers": [
                "TVC:DJI", "CBOT:YM1!", "TVC:IXIC", "TVC:SPX", "SP:SPX", "AMEX:SPY", "FOREXCOM:SPXUSD",
                "TVC:NI225", "NYMEX:CL1!", "NYMEX:BZ1!", "TVC:GOLD"
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
                for row in data.get("data", []):
                    s = row.get("s")
                    vals = row.get("d", [])
                    if len(vals) >= 3:
                        p = float(vals[0] or 0)
                        chp = float(vals[1] or 0)
                        ch = float(vals[2] or 0)
                        if p <= 0: continue
                        item_data = {"ltp": round(p, 2), "ch": round(ch, 2), "chp": round(chp, 2)}
                        
                        if "DJI" in s: GLOBAL_CACHE["DOW"] = {**item_data, "symbol": "DOW", "market_status": "RED"}
                        elif "YM1!" in s: GLOBAL_CACHE["DOW_FUT"] = {"symbol": "DOW_FUT", "ltp": round(p, 2), "market_status": "RED"}
                        elif "IXIC" in s: GLOBAL_CACHE["NASDAQ"] = {**item_data, "symbol": "NASDAQ", "market_status": "RED"}
                        elif "SPX" in s or "SPXUSD" in s:
                            if "SPY" in s and p < 1000:
                                p *= 10; ch *= 10
                                item_data = {"ltp": round(p, 2), "ch": round(ch, 2), "chp": chp}
                            GLOBAL_CACHE["SP500"] = {**item_data, "symbol": "SP500", "market_status": "RED"}
                        elif "NI225" in s: GLOBAL_CACHE["NIKKEI"] = {**item_data, "symbol": "NIKKEI", "market_status": "RED"}
                        elif "CL1!" in s: GLOBAL_CACHE["CRUDE"] = {**item_data, "symbol": "CRUDE", "market_status": "RED"}
                        elif "BZ1!" in s: GLOBAL_CACHE["BRENT"] = {**item_data, "symbol": "BRENT", "market_status": "RED"}
                        elif "GOLD" in s:
                            if p < 5000:
                                GLOBAL_CACHE["XAUUSD"] = {**item_data, "symbol": "XAUUSD", "market_status": "RED"}
                
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
    
    if sym in ["GOLD", "XAUUSD"]:
        xau = GLOBAL_CACHE.get("XAUUSD", {"ltp": 0, "ch": 0, "chp": 0})
        return {
            "symbol": "GOLD",
            "ltp": xau.get("ltp", 0),
            "ch": xau.get("ch", 0),
            "chp": xau.get("chp", 0),
            "market_status": "RED"
        }

    if sym in ["OIL", "CRUDE", "BRENT"]:
        crude = GLOBAL_CACHE.get("CRUDE", {"ltp": 0, "ch": 0, "chp": 0})
        brent = GLOBAL_CACHE.get("BRENT", {"ltp": 0, "ch": 0, "chp": 0})
        return {
            "symbol": "OIL",
            "ltp": crude.get("ltp", 0),
            "ch": crude.get("ch", 0),
            "chp": crude.get("chp", 0),
            "brent_ltp": brent.get("ltp", 0),
            "brent_ch": brent.get("ch", 0),
            "brent_chp": brent.get("chp", 0),
            "market_status": "RED"
        }

    if sym == "DOW" and "DOW" in GLOBAL_CACHE and "DOW_FUT" in GLOBAL_CACHE:
        GLOBAL_CACHE["DOW"]["fut"] = GLOBAL_CACHE["DOW_FUT"]["ltp"]

    if sym in GLOBAL_CACHE:
        return GLOBAL_CACHE[sym]
    
    return {"symbol": symbol.upper(), "ltp": 0, "ch": 0, "chp": 0, "market_status": "UNKNOWN"}
