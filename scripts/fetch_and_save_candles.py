#!/usr/bin/env python3
"""
Fetch 15-minute candles for configured symbols and save to media/candles/<symbol>.json
Usage:
  python scripts/fetch_and_save_candles.py
Requires broker credentials in env and project venv active.
"""
import json
from pathlib import Path
from datetime import datetime

from treading_mainapp.services.angel_api import AngelBroker

SYMBOLS = [
    "NFO:NIFTY",
    "MCX:SILVER",
    "MCX:CRUDEOIL",
]
INTERVAL = "15"
OUT_DIR = Path(__file__).resolve().parent.parent / "media" / "candles"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_and_save():
    broker = AngelBroker()
    conn = broker._ensure_connected()
    if not conn.get("status"):
        print("Broker not connected; attempting login...")
        login = broker.connect()
        if not login.get("status"):
            print("Broker connection failed:", login.get("message"))
            return

    for sym in SYMBOLS:
        print(f"Fetching {sym} {INTERVAL}...", end=" ")
        res = broker.fetch_historical_candles(symbol=sym, interval=INTERVAL)
        if not res.get("status"):
            print("FAILED:", res.get("message"))
            continue
        candles = res.get("candles", [])
        out_file = OUT_DIR / (sym.replace(":", "_").replace("/", "_") + ".json")
        payload = {
            "symbol": sym,
            "interval": INTERVAL,
            "fetched_on": datetime.utcnow().isoformat() + "Z",
            "count": len(candles),
            "candles": [
                {
                    "dt": c.get("dt").isoformat() if c.get("dt") else None,
                    "time": c.get("time"),
                    "open": c.get("open"),
                    "high": c.get("high"),
                    "low": c.get("low"),
                    "close": c.get("close"),
                    "volume": c.get("volume", 0),
                }
                for c in candles
            ],
            "meta": res.get("meta", {}),
        }
        out_file.write_text(json.dumps(payload, indent=2))
        print("OK ->", out_file)


if __name__ == "__main__":
    fetch_and_save()
