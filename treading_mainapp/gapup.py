from datetime import datetime, timedelta, time
from decimal import Decimal
import logging

import requests
from django.utils import timezone

from .models import GapUpStatus

logger = logging.getLogger(__name__)


NIFTY_50_SYMBOLS = [
    "NSE:RELIANCE", "NSE:TCS", "NSE:HDFCBANK", "NSE:INFY", "NSE:ICICIBANK",
    "NSE:HINDUNILVR", "NSE:SBIN", "NSE:BHARTIARTL", "NSE:ITC", "NSE:LT",
    "NSE:KOTAKBANK", "NSE:AXISBANK", "NSE:BAJFINANCE", "NSE:ASIANPAINT",
    "NSE:MARUTI", "NSE:HCLTECH", "NSE:SUNPHARMA", "NSE:TITAN", "NSE:ULTRACEMCO",
    "NSE:WIPRO", "NSE:NESTLEIND", "NSE:POWERGRID", "NSE:NTPC", "NSE:ONGC",
    "NSE:TATAMOTORS", "NSE:M&M", "NSE:TECHM", "NSE:JSWSTEEL", "NSE:ADANIPORTS",
    "NSE:BAJAJFINSV", "NSE:INDUSINDBK", "NSE:HINDALCO", "NSE:TATASTEEL", "NSE:CIPLA",
    "NSE:GRASIM", "NSE:DRREDDY", "NSE:EICHERMOT", "NSE:HEROMOTOCO", "NSE:BRITANNIA",
    "NSE:DIVISLAB", "NSE:APOLLOHOSP", "NSE:BPCL", "NSE:COALINDIA", "NSE:SHRIRAMFIN",
    "NSE:SBILIFE", "NSE:HDFCLIFE", "NSE:BAJAJ-AUTO", "NSE:ADANIENT", "NSE:LTIM", "NSE:PIDILITIND"
]


def _to_decimal(value):
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return None


def _previous_trading_day(today):
    if today.weekday() == 0:
        return today - timedelta(days=3)
    if today.weekday() == 6:
        return today - timedelta(days=2)
    if today.weekday() == 5:
        return today - timedelta(days=1)
    return today - timedelta(days=1)


def _mock_fetch_ohlc(symbol, trade_date):
    base = abs(hash(f"{symbol}-{trade_date}")) % 1000 + 1000
    prev_open = Decimal(base)
    prev_high = prev_open + Decimal("18.50")
    prev_low = prev_open - Decimal("12.25")
    prev_close = prev_open + Decimal("4.75")

    today_open = prev_close + Decimal("6.20")
    today_high = today_open + Decimal("9.80")
    today_low = today_open - Decimal("5.15")
    today_close = today_open + Decimal("3.40")

    return {
        "prev_open": prev_open,
        "prev_high": prev_high,
        "prev_low": prev_low,
        "prev_close": prev_close,
        "today_open": today_open,
        "today_high": today_high,
        "today_low": today_low,
        "today_close": today_close,
    }


def build_gapup_record(symbol, trade_date=None):
    if trade_date is None:
        trade_date = timezone.localdate()

    prev_date = _previous_trading_day(trade_date)
    data = _mock_fetch_ohlc(symbol, trade_date)

    prev_open = _to_decimal(data["prev_open"])
    prev_high = _to_decimal(data["prev_high"])
    prev_low = _to_decimal(data["prev_low"])
    prev_close = _to_decimal(data["prev_close"])

    today_open = _to_decimal(data["today_open"])
    today_high = _to_decimal(data["today_high"])
    today_low = _to_decimal(data["today_low"])
    today_close = _to_decimal(data["today_close"])

    open_diff = _to_decimal(today_open - prev_open)
    high_diff = _to_decimal(today_high - prev_high)
    low_diff = _to_decimal(today_low - prev_low)
    close_diff = _to_decimal(today_close - prev_close)

    gap_up = today_open > prev_high
    gap_down = today_open < prev_low

    if gap_up:
        gap_type = "GAP UP"
        notes = f"Today open above previous high ({prev_date})"
    elif gap_down:
        gap_type = "GAP DOWN"
        notes = f"Today open below previous low ({prev_date})"
    else:
        gap_type = "NO GAP"
        notes = f"Today open inside previous range ({prev_date})"

    obj, _ = GapUpStatus.objects.update_or_create(
        symbol=symbol,
        trade_date=trade_date,
        defaults={
            "prev_open": prev_open,
            "prev_high": prev_high,
            "prev_low": prev_low,
            "prev_close": prev_close,
            "today_open": today_open,
            "today_high": today_high,
            "today_low": today_low,
            "today_close": today_close,
            "open_diff": open_diff,
            "high_diff": high_diff,
            "low_diff": low_diff,
            "close_diff": close_diff,
            "gap_up": gap_up,
            "gap_down": gap_down,
            "gap_type": gap_type,
            "notes": notes,
            "candle_start": time(9, 15),
            "candle_end": time(9, 30),
        }
    )
    return obj


def update_all_gapup_data(trade_date=None):
    if trade_date is None:
        trade_date = timezone.localdate()

    results = []
    for symbol in NIFTY_50_SYMBOLS:
        try:
            obj = build_gapup_record(symbol, trade_date=trade_date)
            results.append(obj)
        except Exception as exc:
            logger.exception("Gap-up update failed for %s: %s", symbol, exc)
    return results