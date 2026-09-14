import json
from pathlib import Path

def load_fno_symbols():
    fno_symbols = set()
    try:
        json_path = Path(__file__).parent / "fyers_fno_universe.json"
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("stocks", []):
                    sym_clean = item.get("symbol", "").replace("NSE:", "").replace("-EQ", "")
                    if sym_clean:
                        fno_symbols.add(sym_clean)
        print(f"Successfully loaded {len(fno_symbols)} F&O symbols from fyers_fno_universe.json")
    except Exception as e:
        print(f"Error loading fyers_fno_universe.json: {str(e)}")
    return fno_symbols

FNO_SYMBOLS = load_fno_symbols()
