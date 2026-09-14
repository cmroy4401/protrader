import time
from fastapi import APIRouter

router = APIRouter()

DEFAULT_SECTORS = {
    "NIFTY IT": {"ltp": 41200.0, "ch": -1050.0, "chp": -2.50},
    "Nifty Realty": {"ltp": 1020.0, "ch": -13.0, "chp": -1.26},
    "NIFTY Metal": {"ltp": 9300.0, "ch": -110.0, "chp": -1.16},
    "NIFTY PSU Bank": {"ltp": 6700.0, "ch": -70.0, "chp": -1.02},
    "NIFTY Commodities": {"ltp": 7350.0, "ch": -71.0, "chp": -0.96},
    "Nifty Oil & Gas": {"ltp": 14000.0, "ch": -98.0, "chp": -0.70},
    "NIFTY FMCG": {"ltp": 60800.0, "ch": -360.0, "chp": -0.59},
    "Nifty Cons Durbl": {"ltp": 31000.0, "ch": -175.0, "chp": -0.56},
    "NIFTY Services": {"ltp": 31000.0, "ch": -143.0, "chp": -0.46},
    "Nifty FinSrv25/50": {"ltp": 23500.0, "ch": -85.0, "chp": -0.36},
    "NIFTY Fin Service": {"ltp": 23000.0, "ch": -67.0, "chp": -0.29},
    "NIFTY Consumption": {"ltp": 25000.0, "ch": -70.0, "chp": -0.28},
    "NIFTY Pharma": {"ltp": 21400.0, "ch": 100.0, "chp": 0.47},
    "Nifty Healthcare": {"ltp": 12900.0, "ch": 59.0, "chp": 0.46},
    "NIFTY Auto": {"ltp": 24200.0, "ch": 58.0, "chp": 0.24},
    "NIFTY Media": {"ltp": 1720.0, "ch": -48.0, "chp": -2.76},
    "Nifty Pvt Bank": {"ltp": 24400.0, "ch": -36.0, "chp": -0.15},
    "NIFTY Infra": {"ltp": 8550.0, "ch": -8.0, "chp": -0.09},
    "NIFTY Energy": {"ltp": 39200.0, "ch": -106.0, "chp": -0.27},
    "NIFTY PSE": {"ltp": 7850.0, "ch": -13.0, "chp": -0.17},
    "Nifty India Defence": {"ltp": 6200.0, "ch": 21.0, "chp": 0.35},
    "Nifty India Mfg": {"ltp": 15400.0, "ch": -29.0, "chp": -0.19},
    "MIDSMALL IT": {"ltp": 21000.0, "ch": 310.0, "chp": 1.50},
}

SECTOR_MAPPING = {
    "NIFTY IT": "NSE_INDEX|Nifty IT",
    "Nifty Realty": "NSE_INDEX|Nifty Realty",
    "NIFTY Metal": "NSE_INDEX|Nifty Metal",
    "NIFTY PSU Bank": "NSE_INDEX|Nifty PSU Bank",
    "NIFTY Commodities": "NSE_INDEX|Nifty Commodities",
    "Nifty Oil & Gas": "NSE_INDEX|Nifty Oil & Gas",
    "NIFTY FMCG": "NSE_INDEX|NIFTY FMCG",
    "Nifty Cons Durbl": "NSE_INDEX|Nifty Consumer Durables",
    "NIFTY Services": "NSE_INDEX|Nifty Services Sector",
    "Nifty FinSrv25/50": "NSE_INDEX|Nifty Fin Service 25/50",
    "NIFTY Fin Service": "NSE_INDEX|Nifty Financial Services",
    "NIFTY Consumption": "NSE_INDEX|Nifty Consumption",
    "NIFTY Pharma": "NSE_INDEX|Nifty Pharma",
    "Nifty Healthcare": "NSE_INDEX|Nifty Healthcare Index",
    "NIFTY Auto": "NSE_INDEX|Nifty Auto",
    "NIFTY Media": "NSE_INDEX|Nifty Media",
    "Nifty Pvt Bank": "NSE_INDEX|Nifty Private Bank",
    "NIFTY Infra": "NSE_INDEX|Nifty Infrastructure",
    "NIFTY Energy": "NSE_INDEX|Nifty Energy",
    "NIFTY PSE": "NSE_INDEX|Nifty PSE",
    "Nifty India Defence": "NSE_INDEX|Nifty India Defence",
    "Nifty India Mfg": "NSE_INDEX|Nifty India Mfg",
    "MIDSMALL IT": "NSE_INDEX|Nifty MidSmall IT & Telecom",
}

def fetch_upstox_sectors(session, access_token, cache, is_cache_valid_func, load_cache_func, save_cache_func, api_timeout, min_interval, health_fail_func, health_ok_func):
    now = time.time()
    if is_cache_valid_func(cache.get("sectors_time", 0), 6.0) and cache.get("sectors_data"):
        return cache["sectors_data"]
    
    persisted = load_cache_func()
    base_sectors = persisted.get("sectors", DEFAULT_SECTORS)
    sectors_parsed = dict(base_sectors)
    
    if not access_token:
        return sectors_parsed
    
    keys_list = list(SECTOR_MAPPING.values())
    for i in range(0, len(keys_list), 5):
        chunk = keys_list[i:i+5]
        try:
            time.sleep(min_interval)
            res = session.get(
                "https://api.upstox.com/v2/market-quote/quotes",
                headers={'Accept': 'application/json', 'Authorization': f'Bearer {access_token}'},
                params={'instrument_key': ",".join(chunk)},
                timeout=api_timeout
            )
            if res.status_code == 200:
                health_ok_func("sectors")
                js = res.json()
                if js.get('status') == 'success':
                    raw = js.get('data', {})
                    norm = {k.lower().replace("|", ":").strip(): v for k, v in raw.items()}
                    for sec_name, sec_key in SECTOR_MAPPING.items():
                        target_key = sec_key.lower().replace("|", ":").strip()
                        if target_key in norm:
                            item = norm.get(target_key)
                            ltp = float(item.get('last_price', 0) or 0)
                            close = float(item.get('ohlc', {}).get('close', 0) or ltp)
                            if ltp == 0 and close > 0: ltp = close
                            ch = float(item.get('net_change', 0) or (ltp - close))
                            chp = float(item.get('change_percent', 0) or ((ch / close * 100) if close > 0 else 0))
                            if ltp > 0:
                                sectors_parsed[sec_name] = {"ltp": round(ltp, 2), "ch": round(ch, 2), "chp": round(chp, 2)}
        except Exception as e:
            health_fail_func("sectors", str(e))
    
    if sectors_parsed:
        cache["sectors_data"] = sectors_parsed
        cache["sectors_time"] = now
        persisted["sectors"] = sectors_parsed
        save_cache_func(persisted)
        return sectors_parsed
    
    return base_sectors
