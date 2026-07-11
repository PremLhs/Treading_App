import json
from pathlib import Path
from typing import Any, Dict, List

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "nifty50.json"
EXTRA_SYMBOLS_FILE = BASE_DIR / "data" / "all_future_stock.json"
INDEX_SYMBOLS = {"NSE:NIFTY", "NSE:BANKNIFTY"}
MASTER_SCRIP_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"


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


def _load_master_symbol_tokens() -> Dict[str, str]:
    try:
        response = requests.get(MASTER_SCRIP_URL, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return {}

    if not isinstance(payload, list):
        return {}

    token_map: Dict[str, str] = {}
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol") or "").strip()
        if not symbol:
            continue
        if entry.get("token") is None:
            continue
        token_map[symbol] = str(entry.get("token", ""))
    return token_map


def _load_extra_symbol_entries() -> List[Dict[str, Any]]:
    if not EXTRA_SYMBOLS_FILE.exists():
        return []

    try:
        with EXTRA_SYMBOLS_FILE.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(payload, list):
        return []

    token_map = _load_master_symbol_tokens()
    entries: List[Dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol") or "").strip()
        if not symbol:
            continue
        tradingsymbol = str(entry.get("tradingsymbol") or symbol).strip()
        token = token_map.get(tradingsymbol) or token_map.get(symbol) or entry.get("symboltoken", "")
        entries.append({
            "symbol": symbol,
            "tradingsymbol": tradingsymbol,
            "symboltoken": str(token or ""),
            "exchange": str(entry.get("exchange") or "NSE"),
        })
    return entries


def get_dashboard_symbols() -> List[str]:
    data = get_nifty50_data()
    symbols = [
        entry.get("symbol")
        for entry in data.get("symbols", [])
        if entry.get("symbol") and entry.get("symbol") not in INDEX_SYMBOLS
    ]

    for entry in _load_extra_symbol_entries():
        symbol = entry.get("symbol")
        if symbol and symbol not in symbols:
            symbols.append(symbol)

    return symbols


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

    for entry in _load_extra_symbol_entries():
        symbol = entry.get("symbol")
        if not symbol:
            continue
        token_map[symbol] = {
            "exchange": entry.get("exchange", "NSE"),
            "tradingsymbol": entry.get("tradingsymbol", symbol),
            "symboltoken": str(entry.get("symboltoken", "")),
        }

    return token_map
