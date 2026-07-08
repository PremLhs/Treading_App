import json
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "nifty50.json"
INDEX_SYMBOLS = {"NSE:NIFTY", "NSE:BANKNIFTY"}


def _load_data() -> Dict[str, Any]:
    if not DATA_FILE.exists():
        return {"last_updated": None, "symbols": []}

    with DATA_FILE.open("r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError:
            return {"last_updated": None, "symbols": []}

    symbols = data.get("symbols", []) or []
    if isinstance(symbols, list):
        return {"last_updated": data.get("last_updated"), "symbols": symbols}
    return {"last_updated": data.get("last_updated"), "symbols": []}


def get_nifty50_data() -> Dict[str, Any]:
    return _load_data()


def get_nifty50_symbols() -> List[str]:
    data = get_nifty50_data()
    return [
        entry.get("symbol")
        for entry in data.get("symbols", [])
        if entry.get("symbol") and entry.get("symbol") not in INDEX_SYMBOLS
    ]


def get_symbol_token_map() -> Dict[str, Dict[str, str]]:
    data = get_nifty50_data()
    token_map: Dict[str, Dict[str, str]] = {}
    for entry in data.get("symbols", []):
        symbol = entry.get("symbol")
        if not symbol:
            continue
        token_map[symbol] = {
            "exchange": entry.get("exchange", "NSE"),
            "tradingsymbol": entry.get("tradingsymbol", symbol),
            "symboltoken": str(entry.get("symboltoken", "")),
        }
    return token_map
