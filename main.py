from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import requests
import time
import threading
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from config import ACCESS_TOKEN

# Import modular router files
import indianindex
import global_market
import otherglobal
import sectorheatmap
import scanner

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
app = FastAPI(title="PRO TRADER - Live Terminal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(global_market.router)
app.include_router(otherglobal.router)
app.include_router(scanner.router)

STATIC_DIR = Path(__file__).parent / "static" if (Path(__file__).parent / "static").exists() else Path(__file__).parent
CACHE_FILE = Path(__file__).parent / "market_cache.json"

API_TIMEOUT = 3.5
REQUEST_RETRY_COUNT = 2
MIN_REQUEST_INTERVAL = 0.2
BACKGROUND_FETCH_INTERVAL = 10

_cache = {
    "indices_data": {},
    "indices_time": 0,
    "sectors_data": {},
    "sectors_time": 0
}

def create_session():
    s = requests.Session()
    retry = Retry(
        total=REQUEST_RETRY_COUNT,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount('http://', adapter)
    s.mount('https://', adapter)
    return s

session = create_session()

@app.get("/")
async def home():
    html_path = STATIC_DIR / "index.html" if (STATIC_DIR / "index.html").exists() else Path("index.html")
    if not html_path.exists():
        logger.error(f"index.html not found at {html_path}")
        return Response(content="<h2>index.html not found</h2>", media_type="text/html", status_code=404)
    try:
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
    except Exception as e:
        logger.error(f"Error reading index.html: {str(e)}")
        return Response(content=f"<h2>Error loading page: {str(e)}</h2>", media_type="text/html", status_code=500)

def load_persistent_cache():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and "indices" in data and len(data["indices"]) > 0:
                    return data
        except Exception as e:
            logger.warning(f"Error loading cache file: {str(e)}")
    
    return {
        "indices": indianindex.DEFAULT_INDICES,
        "sectors": sectorheatmap.DEFAULT_SECTORS,
        "global": global_market.GLOBAL_CACHE,
        "other_global": otherglobal.OTHER_GLOBAL_CACHE
    }

def save_persistent_cache(data):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving cache: {str(e)}")

def is_indian_market_open():
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist_tz)
    if now.weekday() >= 5:
        return False
    dec_time = now.hour + (now.minute / 60.0)
    return 9.25 <= dec_time <= 15.5

def is_cache_valid(cache_time, cache_duration):
    return time.time() - cache_time < cache_duration

HEALTH_LOCK = threading.Lock()
HEALTH_STATE = {
    "upstox": {"status": "UNKNOWN", "last_success": 0, "last_error": "", "http_status": None, "action": "Waiting for first Upstox response."},
    "tradingview": {"status": "UNKNOWN", "last_success": 0, "last_error": "", "http_status": None, "action": "Waiting for first TradingView response."},
    "sectors": {"status": "UNKNOWN", "last_success": 0, "last_error": "", "http_status": None, "action": "Waiting for first sector response."},
}

def health_ok(source, action=""):
    with HEALTH_LOCK:
        if source in HEALTH_STATE:
            x = HEALTH_STATE[source]
            x.update({"status": "OK", "last_success": time.time(), "last_error": "", "http_status": 200, "action": action or "Data source working normally."})

def health_fail(source, message, http_status=None, action="Check the data source and connection."):
    with HEALTH_LOCK:
        if source in HEALTH_STATE:
            x = HEALTH_STATE[source]
            x.update({"status": "ERROR", "last_error": str(message)[:240], "http_status": http_status, "action": action})

def health_snapshot():
    with HEALTH_LOCK:
        return json.loads(json.dumps(HEALTH_STATE))

@app.get("/api/health")
def get_health():
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
        if checks[key]["status"] == "OK" and last and now - last > limit:
            if market_open or key not in ("upstox", "sectors"):
                checks[key]["status"] = "WARNING"
                checks[key]["action"] = f"Data is stale ({int(now - last)}s old). Re-fetching..."
    
    has_error = any(v["status"] == "ERROR" for v in checks.values())
    has_warning = any(v["status"] == "WARNING" for v in checks.values())
    overall = "ERROR" if has_error else "WARNING" if has_warning else "OK"
    
    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks
    }

@app.get("/api/spots")
def get_all_spots():
    persisted = load_persistent_cache()
    global_cache = persisted.get("global", global_market.GLOBAL_CACHE)
    data = indianindex.fetch_upstox_indices(
        session=session,
        access_token=ACCESS_TOKEN,
        cache=_cache,
        global_cache=global_cache,
        api_timeout=API_TIMEOUT,
        is_cache_valid_func=is_cache_valid,
        load_cache_func=load_persistent_cache,
        save_cache_func=save_persistent_cache,
        health_ok_func=health_ok,
        health_fail_func=health_fail
    )
    return {
        "status": "success",
        "is_market_live": is_indian_market_open(),
        "data": data
    }

@app.get("/api/sectors")
def get_sectors():
    sectors_data = sectorheatmap.fetch_upstox_sectors(
        session=session,
        access_token=ACCESS_TOKEN,
        cache=_cache,
        is_cache_valid_func=is_cache_valid,
        load_cache_func=load_persistent_cache,
        save_cache_func=save_persistent_cache,
        api_timeout=API_TIMEOUT,
        min_interval=MIN_REQUEST_INTERVAL,
        health_fail_func=health_fail,
        health_ok_func=health_ok
    )
    out = []
    for name, info in sectors_data.items():
        chp = info.get("chp", 0)
        status = "MOMENTUM" if abs(chp) >= 0.5 else "NEUTRAL"
        out.append({
            "name": name,
            "ltp": info.get("ltp", 0),
            "ch": info.get("ch", 0),
            "chp": chp,
            "status": status
        })
    out.sort(key=lambda x: x["chp"], reverse=True)
    return out

@app.get("/api/scanner/gainers-losers")
def get_scanner_gainers_losers():
    return scanner.get_gainers_losers(session, API_TIMEOUT)

def background_worker():
    while True:
        try:
            global_market.fetch_tradingview_global(
                session=session,
                api_timeout=API_TIMEOUT,
                load_cache_func=load_persistent_cache,
                save_cache_func=save_persistent_cache,
                health_ok_func=health_ok,
                health_fail_func=health_fail
            )
        except Exception:
            pass
        try:
            otherglobal.fetch_tradingview_other_global(
                session=session,
                api_timeout=API_TIMEOUT,
                load_cache_func=load_persistent_cache,
                save_cache_func=save_persistent_cache,
                health_ok_func=health_ok,
                health_fail_func=health_fail
            )
        except Exception:
            pass
        time.sleep(BACKGROUND_FETCH_INTERVAL)

threading.Thread(target=background_worker, daemon=True).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
