import csv
import io
import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .nifty50_loader import DATA_FILE, get_nifty50_data, get_symbol_token_map

DEFAULT_SOURCE_URLS = [
    "https://www.niftyindices.com/indices/equity/broad-based-indices/nifty--50",
    "https://www.nseindia.com/static/products-services/indices-nifty50-index",
    "https://www.nseindia.com/all-reports",
    "https://www.nseindia.com/content/indices/ind_nifty50list.csv",
    "https://www1.nseindia.com/content/indices/ind_nifty50list.csv",
]


def _normalize_symbol(symbol: str) -> str:
    cleaned = str(symbol or "").strip().upper().replace(" ", "")
    if not cleaned:
        return ""
    if cleaned.startswith("NSE:"):
        return cleaned
    if cleaned.startswith("NSE"):
        return cleaned
    return f"NSE:{cleaned}"


def _extract_value(row: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        value = str(value).strip()
        if value:
            return value
    return None


def _parse_csv_rows(payload: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(payload))
    for row in reader:
        rows.append(row)
    return rows


def _build_payload_from_rows(rows: List[Dict[str, Any]], existing_map: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    seen = set()

    for row in rows:
        symbol_value = _extract_value(row, "symbol", "Symbol", "SYMBOL", "securityId", "security")
        if not symbol_value:
            continue

        tradingsymbol_value = _extract_value(row, "tradingsymbol", "TradingSymbol", "tradingSymbol", "securityName")
        token_value = _extract_value(row, "symboltoken", "symbolToken", "token")

        normalized_symbol = _normalize_symbol(symbol_value)
        if not normalized_symbol or normalized_symbol in seen:
            continue

        seen.add(normalized_symbol)

        existing_entry = existing_map.get(normalized_symbol, {})
        payload.append({
            "symbol": normalized_symbol,
            "tradingsymbol": tradingsymbol_value or existing_entry.get("tradingsymbol", normalized_symbol.replace("NSE:", "")),
            "symboltoken": token_value or existing_entry.get("symboltoken", ""),
            "exchange": "NSE",
        })

    return payload


def _build_payload_from_json(data: Any, existing_map: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        if isinstance(data.get("symbols"), list):
            rows = data.get("symbols")
        elif isinstance(data.get("data"), list):
            rows = data.get("data")
        else:
            rows = []
    elif isinstance(data, list):
        rows = data
    else:
        rows = []

    payload: List[Dict[str, Any]] = []
    seen = set()

    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol_value = _extract_value(row, "symbol", "Symbol", "SYMBOL")
        if not symbol_value:
            continue
        normalized_symbol = _normalize_symbol(symbol_value)
        if not normalized_symbol or normalized_symbol in seen:
            continue
        seen.add(normalized_symbol)
        existing_entry = existing_map.get(normalized_symbol, {})
        payload.append({
            "symbol": normalized_symbol,
            "tradingsymbol": _extract_value(row, "tradingsymbol", "TradingSymbol", "tradingSymbol") or existing_entry.get("tradingsymbol", normalized_symbol.replace("NSE:", "")),
            "symboltoken": _extract_value(row, "symboltoken", "symbolToken", "token") or existing_entry.get("symboltoken", ""),
            "exchange": _extract_value(row, "exchange", "Exchange") or "NSE",
        })

    return payload


def refresh_nifty50_data(source_url: Optional[str] = None) -> Dict[str, Any]:
    existing_data = get_nifty50_data()
    existing_map = get_symbol_token_map()

    urls = [source_url] if source_url else DEFAULT_SOURCE_URLS
    payload: Optional[Dict[str, Any]] = None

    for url in urls:
        try:
            response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            text = response.text

            if "application/json" in content_type.lower():
                data = response.json()
                payload = {"last_updated": existing_data.get("last_updated"), "symbols": _build_payload_from_json(data, existing_map)}
            elif "text/csv" in content_type.lower() or text.lstrip().startswith(("symbol", "SYMBOL", "Name")):
                payload = {"last_updated": existing_data.get("last_updated"), "symbols": _build_payload_from_rows(_parse_csv_rows(text), existing_map)}
            elif "nifty" in text.lower() or "banknifty" in text.lower() or "indices" in text.lower():
                payload = {"last_updated": existing_data.get("last_updated"), "symbols": _build_payload_from_rows(_parse_csv_rows(text), existing_map)}
            else:
                continue
            break
        except Exception:
            continue

    if not payload:
        return existing_data

    existing_symbols = [entry.get("symbol") for entry in existing_data.get("symbols", []) if entry.get("symbol")]
    index_symbols = [symbol for symbol in existing_symbols if symbol in {"NSE:NIFTY", "NSE:BANKNIFTY"}]
    new_symbols = payload.get("symbols", [])

    combined_symbols = []
    seen = set()
    for symbol in index_symbols + [entry.get("symbol") for entry in new_symbols if entry.get("symbol")]:
        if symbol and symbol not in seen:
            seen.add(symbol)
            combined_symbols.append(symbol)

    merged_entries: List[Dict[str, Any]] = []
    entry_map: Dict[str, Dict[str, Any]] = {}

    for entry in existing_data.get("symbols", []):
        if isinstance(entry, dict) and entry.get("symbol"):
            entry_map[entry["symbol"]] = entry

    for symbol in combined_symbols:
        if symbol in entry_map:
            merged_entries.append(entry_map[symbol])
        else:
            for item in new_symbols:
                if item.get("symbol") == symbol:
                    merged_entries.append(item)
                    break

    final_payload = {
        "last_updated": existing_data.get("last_updated") or date.today().isoformat(),
        "symbols": merged_entries,
    }

    DATA_FILE.write_text(json.dumps(final_payload, indent=2), encoding="utf-8")
    return final_payload
