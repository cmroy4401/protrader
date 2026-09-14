import time
from fastapi import APIRouter

router = APIRouter()

DEFAULT_INDICES = {
    "NIFTY": {"ltp": 23775.18, "ch": -122.60, "chp": -0.52, "market_status": "GREEN"},
    "BANKNIFTY": {"ltp": 57134.15, "ch": -101.95, "chp": -0.18, "market_status": "GREEN"},
    "SENSEX": {"ltp": 76106.15, "ch": -423.49, "chp": -0.56, "market_status": "GREEN"},
}

INDICES_KEYS = [
    "NSE_INDEX|Nifty 50",
    "NSE_INDEX|Nifty Bank",
    "BSE_INDEX|SENSEX",
    "MCX_FO|483079",
    "MCX_FO|584777"
]

def fetch_upstox_indices(session, access_token, cache, global_cache, api_timeout, is_cache_valid_func, load_cache_func, save_cache_func, health_ok_func, health_fail_func):
    now = time.time()
    if is_cache_valid_func(cache.get("indices_time", 0), 5.0) and cache.get("indices_data"):
        return cache["indices_data"]
    
    persisted = load_cache_func()
    indices_parsed = dict(persisted.get("indices", DEFAULT_INDICES))
    
    if not access_token:
        health_fail_func("upstox", "ACCESS_TOKEN is missing", action="Add a valid Upstox access token.")
        return indices_parsed
    
    try:
        res = session.get(
            "https://api.upstox.com/v2/market-quote/quotes",
            headers={'Accept': 'application/json', 'Authorization': f'Bearer {access_token}'},
            params={'instrument_key': ",".join(INDICES_KEYS)},
            timeout=api_timeout
        )
        
        if res.status_code == 200:
            js = res.json()
            if js.get('status') == 'success':
                health_ok_func("upstox", "Upstox indices request succeeded.")
                raw = js.get('data', {})
                norm = {k.lower().replace("|", ":").strip(): v for k, v in raw.items()}
                
                if "nse_index:nifty 50" in norm:
                    item = norm["nse_index:nifty 50"]
                    ltp = float(item.get('last_price', 0) or 0)
                    close = float(item.get('ohlc', {}).get('close', 0) or ltp)
                    if ltp == 0 and close > 0: ltp = close
                    ch = float(item.get('net_change', 0) or (ltp - close))
                    chp = float(item.get('change_percent', 0) or ((ch / close * 100) if close > 0 else 0))
                    if ltp > 0:
                        indices_parsed["NIFTY"] = {"ltp": round(ltp, 2), "ch": round(ch, 2), "chp": round(chp, 2), "market_status": "GREEN"}
                
                if "nse_index:nifty bank" in norm:
                    item = norm["nse_index:nifty bank"]
                    ltp = float(item.get('last_price', 0) or 0)
                    close = float(item.get('ohlc', {}).get('close', 0) or ltp)
                    if ltp == 0 and close > 0: ltp = close
                    ch = float(item.get('net_change', 0) or (ltp - close))
                    chp = float(item.get('change_percent', 0) or ((ch / close * 100) if close > 0 else 0))
                    if ltp > 0:
                        indices_parsed["BANKNIFTY"] = {"ltp": round(ltp, 2), "ch": round(ch, 2), "chp": round(chp, 2), "market_status": "GREEN"}
                
                if "bse_index:sensex" in norm:
                    item = norm["bse_index:sensex"]
                    ltp = float(item.get('last_price', 0) or 0)
                    close = float(item.get('ohlc', {}).get('close', 0) or ltp)
                    if ltp == 0 and close > 0: ltp = close
                    ch = float(item.get('net_change', 0) or (ltp - close))
                    chp = float(item.get('change_percent', 0) or ((ch / close * 100) if close > 0 else 0))
                    if ltp > 0:
                        indices_parsed["SENSEX"] = {"ltp": round(ltp, 2), "ch": round(ch, 2), "chp": round(chp, 2), "market_status": "GREEN"}

                for k, v in raw.items():
                    if "483079" in k or "gold" in k.lower():
                        g_ltp = float(v.get('last_price', 0) or 0)
                        g_close = float(v.get('ohlc', {}).get('close', 0) or g_ltp)
                        if g_ltp == 0 and g_close > 0: g_ltp = g_close
                        g_ch = float(v.get('net_change', 0) or (g_ltp - g_close))
                        g_chp = float(v.get('change_percent', 0) or ((g_ch / g_close * 100) if g_close > 0 else 0))
                        if g_ltp > 0:
                            global_cache["GOLD_MCX"] = {"symbol": "GOLD_MCX", "ltp": round(g_ltp, 2), "ch": round(g_ch, 2), "chp": round(g_chp, 2), "market_status": "GREEN"}
                    
                    if "584777" in k or "crude" in k.lower():
                        c_ltp = float(v.get('last_price', 0) or 0)
                        c_close = float(v.get('ohlc', {}).get('close', 0) or c_ltp)
                        if c_ltp == 0 and c_close > 0: c_ltp = c_close
                        c_ch = float(v.get('net_change', 0) or (c_ltp - c_close))
                        c_chp = float(v.get('change_percent', 0) or ((c_ch / c_close * 100) if c_close > 0 else 0))
                        if c_ltp > 0:
                            global_cache["CRUDE_MCX"] = {"symbol": "CRUDE_MCX", "ltp": round(c_ltp, 2), "ch": round(c_ch, 2), "chp": round(c_chp, 2), "market_status": "GREEN"}
        else:
            health_fail_func("upstox", f"HTTP {res.status_code}", res.status_code)
    except Exception as e:
        health_fail_func("upstox", str(e))
    
    if indices_parsed:
        cache["indices_data"] = indices_parsed
        cache["indices_time"] = now
        persisted["indices"] = indices_parsed
        persisted["global"] = global_cache
        save_cache_func(persisted)
    
    return indices_parsed
