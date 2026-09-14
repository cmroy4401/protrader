from fastapi import FastAPI, Response
import requests
import time
import threading
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from config import ACCESS_TOKEN

load_dotenv()
app = FastAPI(title="PRO TRADER - Live Terminal")

STATIC_DIR = Path(__file__).parent / "static" if (Path(__file__).parent / "static").exists() else Path(__file__).parent
CACHE_FILE = Path(__file__).parent / "market_cache.json"

@app.get("/")
async def home():
    html_path = STATIC_DIR / "index.html" if (STATIC_DIR / "index.html").exists() else Path("index.html")
    if not html_path.exists():
        return Response(content="<h2>index.html not found</h2>", media_type="text/html", status_code=404)
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(
        content=content, 
        media_type="text/html", 
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

DEFAULT_INDICES = {
    "NIFTY": {"ltp": 23775.18, "ch": -122.60, "chp": -0.52, "market_status": "GREEN"},
    "BANKNIFTY": {"ltp": 57134.15, "ch": -101.95, "chp": -0.18, "market_status": "GREEN"},
    "SENSEX": {"ltp": 76106.15, "ch": -423.49, "chp": -0.56, "market_status": "GREEN"},
}

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
    "NIFTY Bank": {"ltp": 57134.15, "ch": -101.95, "chp": -0.18}
}

def load_persistent_cache():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and "indices" in data and len(data["indices"]) > 0:
                    return data
        except Exception:
            pass
    return {
        "indices": DEFAULT_INDICES,
        "sectors": DEFAULT_SECTORS,
        "global": {
            "SP500": {"symbol": "SP500", "ltp": 5850.00, "ch": 25.50, "chp": 0.44, "market_status": "RED"}
        },
    }

def save_persistent_cache(data):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def is_indian_market_open():
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist_tz)
    if now.weekday() >= 5:
        return False
    dec_time = now.hour + (now.minute / 60.0)
    return 9.25 <= dec_time <= 15.5

INDICES_KEYS = [
    "NSE_INDEX|Nifty 50",
    "NSE_INDEX|Nifty Bank",
    "BSE_INDEX|SENSEX",
    "MCX_FO|483079"
]

SECTOR_MAPPING = {
    "NIFTY IT": "NSE_INDEX|Nifty IT",
    "Nifty Realty": "NSE_INDEX|Nifty Realty",
    "NIFTY Metal": "NSE_INDEX|Nifty Metal",
    "NIFTY PSU Bank": "NSE_INDEX|Nifty PSU Bank",
    "NIFTY Commodities": "NSE_INDEX|Nifty Commodities",
    "Nifty Oil & Gas": "NSE_INDEX|Nifty Oil & Gas",
    "NIFTY FMCG": "NSE_INDEX|Nifty FMCG",
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
    "NIFTY Bank": "NSE_INDEX|Nifty Bank"
}

GLOBAL_CACHE = load_persistent_cache().get("global", {})
if "SP500" not in GLOBAL_CACHE or GLOBAL_CACHE["SP500"].get("ltp", 0) == 0:
    GLOBAL_CACHE["SP500"] = {"symbol": "SP500", "ltp": 5850.00, "ch": 25.50, "chp": 0.44, "market_status": "RED"}

HEALTH_LOCK = threading.Lock()
HEALTH_STATE = {
    "upstox": {"status": "UNKNOWN", "last_success": 0, "last_error": "", "http_status": None, "action": "Waiting for first Upstox response."},
    "tradingview": {"status": "UNKNOWN", "last_success": 0, "last_error": "", "http_status": None, "action": "Waiting for first TradingView response."},
    "sectors": {"status": "UNKNOWN", "last_success": 0, "last_error": "", "http_status": None, "action": "Waiting for first sector response."},
}

def health_ok(source, action=""):
    with HEALTH_LOCK:
        x = HEALTH_STATE[source]
        x.update({"status": "OK", "last_success": time.time(), "last_error": "", "http_status": 200, "action": action or "Data source working normally."})

def health_fail(source, message, http_status=None, action="Check the data source and connection."):
    with HEALTH_LOCK:
        x = HEALTH_STATE[source]
        x.update({"status": "ERROR", "last_error": str(message)[:240], "http_status": http_status, "action": action})

def health_snapshot():
    with HEALTH_LOCK:
        return json.loads(json.dumps(HEALTH_STATE))

def build_health():
    now = time.time()
    market_open = is_indian_market_open()
    checks = health_snapshot()
    if not market_open:
        for key in ("upstox", "sectors"):
            if checks[key]["status"] == "ERROR":
                checks[key]["status"] = "WARNING"
                checks[key]["action"] = "Indian market is closed; re-check when NSE/BSE opens."
    stale_limits = {"upstox": 25, "sectors": 35, "tradingview": 30}
    for key, limit in stale_limits.items():
        last = checks[key].get("last_success", 0) or 0
        if checks[key]["status"] == "OK" and last and now - last > limit and (market_open or key not in ("upstox", "sectors")):
            checks[key]["status"] = "WARNING"
            checks[key]["last_error"] = f"No successful update for {int(now-last)}s"
            checks[key]["action"] = "Check network/API response; data may be stale."
    severity = "OK"
    if any(v["status"] == "ERROR" for v in checks.values()): severity = "ERROR"
    elif any(v["status"] == "WARNING" for v in checks.values()): severity = "WARNING"
    return {"status": severity, "market_open": market_open, "timestamp": now, "checks": checks}

_cache = {"indices_time": 0, "indices_data": {}, "sectors_time": 0, "sectors_data": {}}

def fetch_upstox_indices():
    now = time.time()
    if now - _cache["indices_time"] < 4.0 and _cache["indices_data"]:
        return _cache["indices_data"]
    
    persisted = load_persistent_cache()
    if not ACCESS_TOKEN:
        health_fail("upstox", "ACCESS_TOKEN is missing", action="Add a valid Upstox access token in .env.")
        return persisted.get("indices", DEFAULT_INDICES)

    try:
        res = requests.get("https://api.upstox.com/v2/market-quote/quotes", 
                           headers={'Accept': 'application/json', 'Authorization': f'Bearer {ACCESS_TOKEN}'}, 
                           params={'instrument_key': ",".join(INDICES_KEYS)}, timeout=3.5)
        if res.status_code == 200:
            health_ok("upstox", "Upstox index/Gold request succeeded.")
            js = res.json()
            if js.get('status') == 'success':
                raw = js.get('data', {})
                norm = {k.lower().replace("|", ":").strip(): v for k, v in raw.items()}
                parsed = {}
                mapping = {
                    "NIFTY": ["nse_index:nifty 50"],
                    "BANKNIFTY": ["nse_index:nifty bank"],
                    "SENSEX": ["bse_index:sensex"],
                }
                
                for sym, keys in mapping.items():
                    item = next((norm[k] for k in keys if k in norm), None)
                    if item:
                        ltp = float(item.get('last_price', 0) or 0)
                        close = float(item.get('ohlc', {}).get('close', 0) or ltp)
                        if ltp == 0 and close > 0: ltp = close
                        ch = float(item.get('net_change', 0) or (ltp - close))
                        chp = float(item.get('change_percent', 0) or ((ch / close * 100) if close > 0 else 0))
                        parsed[sym] = {"ltp": round(ltp, 2), "ch": round(ch, 2), "chp": round(chp, 2), "market_status": "GREEN"}

                for k, v in raw.items():
                    if "483079" in k or "gold" in k.lower():
                        g_ltp = float(v.get('last_price', 0) or 0)
                        g_close = float(v.get('ohlc', {}).get('close', 0) or g_ltp)
                        if g_ltp == 0 and g_close > 0: g_ltp = g_close
                        g_ch = float(v.get('net_change', 0) or (g_ltp - g_close))
                        g_chp = float(v.get('change_percent', 0) or ((g_ch / g_close * 100) if g_close > 0 else 0))
                        if g_ltp > 0:
                            GLOBAL_CACHE["GOLD_MCX"] = {"symbol": "GOLD_MCX", "ltp": round(g_ltp, 2), "ch": round(g_ch, 2), "chp": round(g_chp, 2), "market_status": "GREEN"}

                if parsed:
                    _cache["indices_data"] = parsed
                    _cache["indices_time"] = now
                    persisted["indices"] = parsed
                    persisted["global"] = GLOBAL_CACHE
                    save_persistent_cache(persisted)
                    return parsed
    except Exception as e:
        health_fail("upstox", e, action="Check Upstox token, internet connection, and API availability.")
    else:
        if "res" in locals() and res.status_code != 200:
            health_fail("upstox", f"HTTP {res.status_code}", res.status_code, "Check Upstox access token/permissions or API rate limit.")
    
    return persisted.get("indices", DEFAULT_INDICES)

def fetch_upstox_sectors():
    now = time.time()
    if now - _cache["sectors_time"] < 6.0 and _cache["sectors_data"]:
        return _cache["sectors_data"]
    
    persisted = load_persistent_cache()
    base_sectors = persisted.get("sectors", DEFAULT_SECTORS)
    sectors_parsed = dict(base_sectors) 

    if not ACCESS_TOKEN:
        health_fail("sectors", "ACCESS_TOKEN is missing", action="Add a valid Upstox access token in .env.")
        return sectors_parsed

    keys_list = list(SECTOR_MAPPING.values())
    
    for i in range(0, len(keys_list), 5):
        chunk = keys_list[i:i+5]
        try:
            res = requests.get("https://api.upstox.com/v2/market-quote/quotes", 
                               headers={'Accept': 'application/json', 'Authorization': f'Bearer {ACCESS_TOKEN}'}, 
                               params={'instrument_key': ",".join(chunk)}, timeout=3.0)
            if res.status_code == 200:
                health_ok("sectors", "Upstox sector request succeeded.")
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
            time.sleep(0.15)
        except Exception as e:
            health_fail("sectors", e, action="Check Upstox sector API response and network.")

    if sectors_parsed:
        _cache["sectors_data"] = sectors_parsed
        _cache["sectors_time"] = now
        persisted["sectors"] = sectors_parsed
        save_persistent_cache(persisted)
        return sectors_parsed
    
    return base_sectors

def fetch_tradingview_batch():
    headers = {"User-Agent": "Mozilla/5.0", "Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/"}
    payload = {
        "symbols": {
            "tickers": [
                "TVC:DJI", "TVC:IXIC", "CBOT_MINI:YM1!", "TVC:SPX", "SP:SPX", "AMEX:SPY", "FOREXCOM:SPXUSD", "TVC:NI225",
                "TVC:HSI", "SSE:000001", "TVC:KOSPI",
                "TVC:DEU40", "TVC:CAC40", "TVC:UKX",
                "NYMEX:CL1!", "NYMEX:BZ1!", "TVC:GOLD"
            ]
        },
        "columns": ["close", "change", "change_abs"]
    }
    try:
        r = requests.post("https://scanner.tradingview.com/global/scan", json=payload, headers=headers, timeout=4.0)
        if r.status_code == 200:
            health_ok("tradingview", "TradingView batch request succeeded.")
            for row in r.json().get("data", []):
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
                            p *= 10
                            ch *= 10
                            item_data = {"ltp": round(p, 2), "ch": round(ch, 2), "chp": chp}
                        GLOBAL_CACHE["SP500"] = {**item_data, "symbol": "SP500", "market_status": "RED"}
                    elif "NI225" in s: GLOBAL_CACHE["NIKKEI"] = {**item_data, "symbol": "NIKKEI", "market_status": "RED"}
                    elif "KOSPI" in s: GLOBAL_CACHE["KOSPI"] = {**item_data, "symbol": "KOSPI", "market_status": "RED"}
                    elif "HSI" in s: GLOBAL_CACHE["HANGSENG"] = {**item_data, "symbol": "HANGSENG", "market_status": "RED"}
                    elif "000001" in s: GLOBAL_CACHE["SHANGHAI"] = {**item_data, "symbol": "SHANGHAI", "market_status": "RED"}
                    elif "DEU40" in s: GLOBAL_CACHE["DAX"] = {**item_data, "symbol": "DAX", "market_status": "RED"}
                    elif "CAC40" in s: GLOBAL_CACHE["CAC"] = {**item_data, "symbol": "CAC", "market_status": "RED"}
                    elif "UKX" in s: GLOBAL_CACHE["FTSE"] = {**item_data, "symbol": "FTSE", "market_status": "RED"}
                    elif "CL1!" in s: GLOBAL_CACHE["CRUDE"] = {**item_data, "symbol": "CRUDE", "market_status": "RED"}
                    elif "BZ1!" in s: GLOBAL_CACHE["BRENT"] = {**item_data, "symbol": "BRENT", "market_status": "RED"}
                    elif "GOLD" in s: 
                        if p < 5000:
                            GLOBAL_CACHE["XAUUSD"] = {**item_data, "symbol": "XAUUSD", "market_status": "RED"}

            if "DOW" in GLOBAL_CACHE and "DOW_FUT" in GLOBAL_CACHE:
                GLOBAL_CACHE["DOW"]["fut"] = GLOBAL_CACHE["DOW_FUT"]["ltp"]

            persisted = load_persistent_cache()
            persisted["global"] = GLOBAL_CACHE
            save_persistent_cache(persisted)
        else:
            health_fail("tradingview", f"HTTP {r.status_code}", r.status_code, "Check TradingView endpoint/network or rate limit.")
    except Exception as e:
        health_fail("tradingview", e, action="Check internet connection or TradingView availability.")

def global_background_worker():
    while True:
        try:
            fetch_tradingview_batch()
        except Exception:
            pass
        time.sleep(10)

threading.Thread(target=global_background_worker, daemon=True).start()

@app.get("/api/health")
def get_health():
    return build_health()

@app.get("/api/spots")
def get_all_spots():
    return {"status": "success", "is_market_live": is_indian_market_open(), "data": fetch_upstox_indices()}

@app.get("/api/global")
def get_global(symbol: str):
    sym = symbol.upper()
    if sym in ["SNP500", "SPX"]:
        sym = "SP500"
    if sym == "DOW" and "DOW" in GLOBAL_CACHE and "DOW_FUT" in GLOBAL_CACHE:
        GLOBAL_CACHE["DOW"]["fut"] = GLOBAL_CACHE["DOW_FUT"]["ltp"]
    if sym in GLOBAL_CACHE:
        return GLOBAL_CACHE[sym]
    persisted = load_persistent_cache()
    cached_global = persisted.get("global", {})
    if sym in ["SNP500", "SPX"]:
        sym = "SP500"
    if sym == "DOW" and "DOW" in cached_global and "DOW_FUT" in cached_global:
        cached_global["DOW"]["fut"] = cached_global["DOW_FUT"]["ltp"]
    if sym in cached_global:
        cached_global_key = next((k for k in cached_global if k.upper() == sym), None)
        return cached_global[cached_global_key] if cached_global_key else cached_global[sym]
    if sym == "DOW":
        return {"symbol": "DOW", "ltp": 43500.00, "fut": 43550.00, "ch": 100.00, "chp": 0.23, "market_status": "RED"}
    return {"symbol": symbol.upper(), "ltp": 5850.00, "ch": 25.50, "chp": 0.44, "market_status": "RED"}

@app.get("/api/sectors")
def get_sectors():
    sectors_data = fetch_upstox_sectors()
    out = []
    for name, info in sectors_data.items():
        chp = info["chp"]
        status = "MOMENTUM" if abs(chp) >= 0.5 else "NEUTRAL"
        out.append({"name": name, "ltp": info["ltp"], "ch": info["ch"], "chp": chp, "status": status})
    out.sort(key=lambda x: x["chp"], reverse=True)
    return out

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
