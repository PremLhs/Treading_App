from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from django.utils import timezone

from .services.angel_api import AngelBroker

PINBAR_SYMBOLS = [
    "NFO:NIFTY",
    "MCX:GOLD",
    "MCX:SILVER",
    "MCX:COPPER",
    "MCX:CRUDEOIL",
]


def _get_today_candles(candles: List[Dict[str, Any]], trade_date: date) -> List[Dict[str, Any]]:
    return sorted(
        [c for c in candles if c.get("date") == trade_date],
        key=lambda item: item.get("time", 0),
    )


def _format_candle_period(candle_dt) -> Optional[str]:
    if not candle_dt:
        return None

    candle_end = candle_dt
    candle_start = candle_end - timedelta(minutes=15)
    return f"{candle_start.strftime('%H:%M')} - {candle_end.strftime('%H:%M')}"


def _find_latest_pin_bar_candle(candles: List[Dict[str, Any]], trade_date: date) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    todays = _get_today_candles(candles, trade_date)
    cutoff = timezone.localtime()
    # consider candles that have ended (dt <= now). Previous logic required
    # an extra 15-minute delay which skipped recently completed 15m candles.
    completed = [c for c in todays if c.get("dt") and c["dt"] <= cutoff]

    for candle in reversed(completed):
        evaluation = detect_pin_bar(candle)
        if evaluation["is_pin_bar"]:
            return candle, evaluation
    return None, None


def detect_pin_bar(candle: Dict[str, Any]) -> Dict[str, Any]:
    open_price = float(candle.get("open", 0))
    high_price = float(candle.get("high", 0))
    low_price = float(candle.get("low", 0))
    close_price = float(candle.get("close", 0))

    body = abs(close_price - open_price)
    total_range = high_price - low_price
    upper_wick = high_price - max(open_price, close_price)
    lower_wick = min(open_price, close_price) - low_price

    is_pin_bar = False
    pinbar_type = None
    reason = ""

    if total_range <= 0 or body <= 0:
        return {
            "is_pin_bar": False,
            "pinbar_type": None,
            "body": body,
            "upper_wick": upper_wick,
            "lower_wick": lower_wick,
            "range": total_range,
            "reason": "Invalid candle range or body size.",
        }

    body_ratio = body / total_range
    dominant_wick = max(upper_wick, lower_wick)
    opposite_wick = min(upper_wick, lower_wick)
    dominant_wick_ratio = dominant_wick / total_range
    opposite_wick_ratio = opposite_wick / total_range

    if body_ratio > 0.25:
        reason = "Body is too large to qualify as a clean pin bar."
    elif dominant_wick < body * 2.5:
        reason = "Dominant wick must be at least 2.5x the body."
    elif dominant_wick_ratio < 0.60:
        reason = "Dominant wick is not long enough compared to the full range."
    elif opposite_wick_ratio > 0.15:
        reason = "Opposite wick is too large for a strong pin bar."
    else:
        is_pin_bar = True
        if lower_wick > upper_wick:
            pinbar_type = "bullish"
            reason = "Bullish pin bar with a long lower wick and small body."
        else:
            pinbar_type = "bearish"
            reason = "Bearish pin bar with a long upper wick and small body."

    return {
        "is_pin_bar": is_pin_bar,
        "pinbar_type": pinbar_type,
        "body": round(body, 4),
        "upper_wick": round(upper_wick, 4),
        "lower_wick": round(lower_wick, 4),
        "range": round(total_range, 4),
        "reason": reason,
    }


def scan_pinbar_signals(symbols: Optional[List[str]] = None, trade_date: Optional[date] = None) -> List[Dict[str, Any]]:
    symbols = symbols or PINBAR_SYMBOLS
    trade_date = trade_date or timezone.localdate()

    broker = AngelBroker()
    scan_results: List[Dict[str, Any]] = []

    for symbol in symbols:
        result = broker.fetch_historical_candles(symbol=symbol, interval="15")
        if not result.get("status"):
            scan_results.append({
                "symbol": symbol,
                "trade_date": trade_date.isoformat(),
                "is_pin_bar": False,
                "pinbar_type": None,
                "candle_time": None,
                "open": None,
                "high": None,
                "low": None,
                "close": None,
                "body": None,
                "upper_wick": None,
                "lower_wick": None,
                "range": None,
                "reason": result.get("message", "Failed to fetch 15m candles."),
                "error": True,
            })
            continue

        candles = result.get("candles", []) or []
        latest_pinbar_candle, evaluation = _find_latest_pin_bar_candle(candles, trade_date)

        if not latest_pinbar_candle:
            scan_results.append({
                "symbol": symbol,
                "trade_date": trade_date.isoformat(),
                "is_pin_bar": False,
                "pinbar_type": None,
                "candle_time": None,
                "candle_period": None,
                "open": None,
                "high": None,
                "low": None,
                "close": None,
                "body": None,
                "upper_wick": None,
                "lower_wick": None,
                "range": None,
                "reason": f"No 15-minute pin bar found for {trade_date.isoformat()}.",
                "error": True,
            })
            continue

        candle_dt = latest_pinbar_candle.get("dt")
        scan_results.append({
            "symbol": symbol,
            "trade_date": trade_date.isoformat(),
            "is_pin_bar": evaluation["is_pin_bar"],
            "pinbar_type": evaluation["pinbar_type"],
            "candle_time": candle_dt.strftime("%H:%M") if candle_dt else None,
            "candle_period": _format_candle_period(candle_dt),
            "open": latest_pinbar_candle.get("open"),
            "high": latest_pinbar_candle.get("high"),
            "low": latest_pinbar_candle.get("low"),
            "close": latest_pinbar_candle.get("close"),
            "body": evaluation["body"],
            "upper_wick": evaluation["upper_wick"],
            "lower_wick": evaluation["lower_wick"],
            "range": evaluation["range"],
            "reason": evaluation["reason"],
            "error": False,
        })

    return scan_results
