import logging
from fastapi import APIRouter
from fnouniverse import FNO_SYMBOLS

router = APIRouter()
logger = logging.getLogger(__name__)

def fetch_scan(session, api_timeout, sort_order, count=6):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/"
    }
    payload = {
        "filter": [{"left": "type", "operation": "equal", "right": "stock"}, {"left": "exchange", "operation": "equal", "right": "NSE"}],
        "symbols": {"query": {"types": []}},
        "columns": ["name", "close", "change", "change_abs", "volume"],
        "sort": {"sortBy": "change", "sortOrder": sort_order},
        "range": [0, 400]
    }
    try:
        r = session.post("https://scanner.tradingview.com/india/scan", json=payload, headers=headers, timeout=api_timeout)
        if r.status_code == 200:
            res_data = r.json()
            matched = []
            for row in res_data.get("data", []):
                s_symbol = row.get("s", "").split(":")[-1]
                if s_symbol in FNO_SYMBOLS:
                    vals = row.get("d", [])
                    if len(vals) >= 5:
                        matched.append({
                            "symbol": s_symbol,
                            "name": vals[0],
                            "ltp": round(float(vals[1] or 0), 2),
                            "chp": round(float(vals[2] or 0), 2),
                            "ch": round(float(vals[3] or 0), 2),
                            "volume": int(vals[4] or 0)
                        })
            return matched[:count]
    except Exception as e:
        logger.error(f"Scanner fetch error: {str(e)}")
    return []

@router.get("/api/scanner/gainers-losers")
def get_gainers_losers(session, api_timeout):
    top_gainers = fetch_scan(session, api_timeout, "desc", 6)
    top_losers = fetch_scan(session, api_timeout, "asc", 6)
    return {"status": "success", "gainers": top_gainers, "losers": top_losers}
