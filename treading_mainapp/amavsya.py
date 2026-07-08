import csv
import logging
import re
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


IST = timezone(timedelta(hours=5, minutes=30))

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
AMAVASYA_CSV_PATH = DATA_DIR / "amavasya.csv"

STRATEGY_INTERVAL = "15"
SUPPORTED_INTRADAY_INTERVALS = {"1", "3", "5", "15", "30", "60"}
# Allow daily 'D' strategy to evaluate breakouts using the whole trading day's candle
SUPPORTED_INTERVALS = set(SUPPORTED_INTRADAY_INTERVALS) | {"D"}


@dataclass(frozen=True)
class Candle:
    dt: datetime  # naive IST datetime
    open: float
    high: float
    low: float
    close: float

    @property
    def trading_date(self) -> date:
        return self.dt.date()

    @property
    def color(self) -> str:
        return "green" if self.close >= self.open else "red"


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_header(name: Any) -> str:
    return str(name or "").strip().lower()


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.strip("\"'").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_meridiem_text(text: str) -> str:
    normalized = _clean_text(text)
    if not normalized:
        return ""

    normalized = re.sub(r"\b(a\.?\s*m\.?)\b", "AM", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\b(p\.?\s*m\.?)\b", "PM", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bam\b", "AM", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\bpm\b", "PM", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _parse_epoch_to_datetime_ist(value: Any) -> Optional[datetime]:
    try:
        ts = int(float(value))
        return datetime.fromtimestamp(ts, tz=IST).replace(tzinfo=None)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _parse_candle_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(IST).replace(tzinfo=None)
        return value

    if isinstance(value, (int, float)):
        return _parse_epoch_to_datetime_ist(value)

    text = _clean_text(value)
    if not text:
        return None

    if text.isdigit():
        parsed = _parse_epoch_to_datetime_ist(text)
        if parsed:
            return parsed

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is not None:
                return parsed.astimezone(IST).replace(tzinfo=None)
            return parsed
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is not None:
            return parsed.astimezone(IST).replace(tzinfo=None)
        return parsed
    except ValueError:
        logger.warning("Unable to parse candle datetime: %s", text)
        return None


def _parse_event_datetime(date_text: Any, year: Optional[int] = None) -> Optional[datetime]:
    text = _normalize_meridiem_text(date_text)
    if not text:
        return None

    candidates: List[str] = []

    if year and str(year) not in text:
        candidates.append(f"{text} {year}")

    candidates.append(text)

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%b %d, %I:%M %p %Y",
        "%B %d, %I:%M %p %Y",
        "%b %d, %I:%M:%S %p %Y",
        "%B %d, %I:%M:%S %p %Y",
        "%b %d %Y",
        "%B %d %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]

    for candidate in candidates:
        for fmt in formats:
            try:
                parsed = datetime.strptime(candidate, fmt)
                return parsed.replace(tzinfo=IST)
            except ValueError:
                continue

    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=IST)
        return parsed.astimezone(IST)
    except ValueError:
        logger.warning("Unable to parse Amavasya event datetime: %s | year=%s", text, year)
        return None


def load_amavasya_reference_dates() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    if not AMAVASYA_CSV_PATH.exists():
        logger.warning("amavasya.csv not found at %s", AMAVASYA_CSV_PATH)
        return rows

    with open(AMAVASYA_CSV_PATH, mode="r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            logger.warning("amavasya.csv has no headers")
            return rows

        normalized_headers = [_normalize_header(name) for name in reader.fieldnames if name]
        simple_date_mode = "date" in normalized_headers
        detailed_mode = {"year", "month", "title", "start", "end"}.issubset(set(normalized_headers))

        if not simple_date_mode and not detailed_mode:
            logger.warning("amavasya.csv invalid headers: %s", reader.fieldnames)
            return rows

        for raw_row in reader:
            row = {
                _normalize_header(k): (_clean_text(v) if v is not None else "")
                for k, v in raw_row.items()
            }

            if simple_date_mode:
                event_dt = _parse_event_datetime(row.get("date"))
                if not event_dt:
                    logger.warning("Skipping invalid Amavasya simple date row: %s", raw_row)
                    continue

                event_date = event_dt.astimezone(IST).date()
                rows.append({
                    "year": event_dt.year,
                    "month": event_dt.strftime("%B"),
                    "title": "Amavasya",
                    "start": event_dt.strftime("%Y-%m-%d"),
                    "end": event_dt.strftime("%Y-%m-%d"),
                    "start_dt": event_dt,
                    "end_dt": event_dt,
                    "event_date": event_date,
                })
                continue

            year_raw = row.get("year", "")
            if not year_raw.isdigit():
                logger.warning("Skipping row with invalid year: %s", raw_row)
                continue

            year = int(year_raw)
            month = row.get("month", "")
            title = row.get("title", "") or "Amavasya"
            start_text = row.get("start", "")
            end_text = row.get("end", "") or start_text

            start_dt = _parse_event_datetime(start_text, year)
            end_dt = _parse_event_datetime(end_text, year)

            if end_dt is not None:
                chosen_dt = end_dt
            elif start_dt is not None:
                chosen_dt = start_dt
            else:
                logger.warning("Skipping row with invalid start/end: %s", raw_row)
                continue

            event_date = chosen_dt.astimezone(IST).date()

            rows.append({
                "year": year,
                "month": month or chosen_dt.strftime("%B"),
                "title": title,
                "start": start_text,
                "end": end_text,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "event_date": event_date,
            })

    unique_rows: List[Dict[str, Any]] = []
    seen = set()
    for item in sorted(rows, key=lambda x: (x["event_date"], x.get("title", ""), x.get("month", ""))):
        key = (item["event_date"], item.get("title", ""), item.get("month", ""))
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(item)

    return unique_rows


def normalize_candles(raw_candles: List[Any]) -> List[Candle]:
    normalized: List[Candle] = []
    seen: set[Tuple[datetime, float, float, float, float]] = set()

    for item in raw_candles or []:
        dt = open_price = high_price = low_price = close_price = None

        if isinstance(item, dict):
            dt = _parse_candle_datetime(
                item.get("dt") or item.get("time") or item.get("datetime") or item.get("timestamp")
            )
            open_price = _safe_float(item.get("open"))
            high_price = _safe_float(item.get("high"))
            low_price = _safe_float(item.get("low"))
            close_price = _safe_float(item.get("close"))
        elif isinstance(item, (list, tuple)) and len(item) >= 5:
            dt = _parse_candle_datetime(item[0])
            open_price = _safe_float(item[1])
            high_price = _safe_float(item[2])
            low_price = _safe_float(item[3])
            close_price = _safe_float(item[4])

        if not dt or None in (open_price, high_price, low_price, close_price):
            continue

        candle_key = (dt, open_price, high_price, low_price, close_price)
        if candle_key in seen:
            continue
        seen.add(candle_key)

        normalized.append(
            Candle(
                dt=dt,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
            )
        )

    normalized.sort(key=lambda x: x.dt)
    return normalized


def group_candles_by_date(candles: List[Candle]) -> Dict[date, List[Candle]]:
    grouped: Dict[date, List[Candle]] = {}
    for candle in candles:
        grouped.setdefault(candle.trading_date, []).append(candle)

    for trading_day in grouped:
        grouped[trading_day].sort(key=lambda x: x.dt)

    return grouped


def build_daily_ohlc_from_intraday(grouped_intraday: Dict[date, List[Candle]]) -> Dict[date, Candle]:
    daily_map: Dict[date, Candle] = {}

    for trading_day, day_candles in grouped_intraday.items():
        if not day_candles:
            continue

        first_candle = day_candles[0]
        last_candle = day_candles[-1]

        daily_map[trading_day] = Candle(
            dt=first_candle.dt,
            open=first_candle.open,
            high=max(c.high for c in day_candles),
            low=min(c.low for c in day_candles),
            close=last_candle.close,
        )

    return daily_map


def find_previous_or_same_trading_date(event_date: date, ordered_trading_dates: List[date]) -> Optional[date]:
    idx = bisect_right(ordered_trading_dates, event_date) - 1
    if idx < 0:
        return None
    return ordered_trading_dates[idx]


def get_future_trading_dates(reference_date: date, ordered_trading_dates: List[date]) -> List[date]:
    idx = bisect_right(ordered_trading_dates, reference_date)
    if idx >= len(ordered_trading_dates):
        return []
    return ordered_trading_dates[idx:]


def find_first_breaks_across_future_days(
    grouped_intraday: Dict[date, List[Candle]],
    daily_map: Dict[date, Candle],
    future_trading_dates: List[date],
    reference_high: float,
    reference_low: float,
) -> List[Tuple[date, Dict[str, Any]]]:
    """Find first break signals across future trading days.

    This function prefers using the day's aggregated OHLC (from daily_map)
    to detect and mark breakouts so the breakout line reflects the full
    trading day's high/low instead of a single intraday candle.
    """
    high_signal: Optional[Tuple[date, Dict[str, Any]]] = None
    low_signal: Optional[Tuple[date, Dict[str, Any]]] = None

    for trading_day in future_trading_dates:
        # Prefer the aggregated daily candle if available
        day_candle = daily_map.get(trading_day)
        intraday_candles = grouped_intraday.get(trading_day, [])

        if day_candle:
            # Use full-day high/low to determine break
            if high_signal is None and day_candle.high > reference_high:
                # Use the day's high as the breakout price; for timing use last intraday candle if present
                trigger_dt = intraday_candles[-1].dt if intraday_candles else day_candle.dt
                high_signal = (
                    trading_day,
                    {
                        "type": "high_break",
                        "line_price": day_candle.high,
                        "candle_time": trigger_dt,
                        "break_candle_open": day_candle.open,
                        "break_candle_high": day_candle.high,
                        "break_candle_low": day_candle.low,
                        "break_candle_close": day_candle.close,
                    },
                )

            if low_signal is None and day_candle.low < reference_low:
                trigger_dt = intraday_candles[-1].dt if intraday_candles else day_candle.dt
                low_signal = (
                    trading_day,
                    {
                        "type": "low_break",
                        "line_price": day_candle.low,
                        "candle_time": trigger_dt,
                        "break_candle_open": day_candle.open,
                        "break_candle_high": day_candle.high,
                        "break_candle_low": day_candle.low,
                        "break_candle_close": day_candle.close,
                    },
                )

        else:
            # Fallback: scan intraday candles if no aggregated day candle available
            if not intraday_candles:
                continue

            for candle in intraday_candles:
                if high_signal is None and candle.high > reference_high:
                    high_signal = (
                        trading_day,
                        {
                            "type": "high_break",
                            "line_price": candle.high,
                            "candle_time": candle.dt,
                            "break_candle_open": candle.open,
                            "break_candle_high": candle.high,
                            "break_candle_low": candle.low,
                            "break_candle_close": candle.close,
                        },
                    )

                if low_signal is None and candle.low < reference_low:
                    low_signal = (
                        trading_day,
                        {
                            "type": "low_break",
                            "line_price": candle.low,
                            "candle_time": candle.dt,
                            "break_candle_open": candle.open,
                            "break_candle_high": candle.high,
                            "break_candle_low": candle.low,
                            "break_candle_close": candle.close,
                        },
                    )

                if high_signal is not None and low_signal is not None:
                    break

        if high_signal is not None and low_signal is not None:
            break

    results: List[Tuple[date, Dict[str, Any]]] = []
    if high_signal is not None:
        results.append(high_signal)
    if low_signal is not None:
        results.append(low_signal)

    results.sort(key=lambda item: (item[1]["candle_time"], item[1]["line_price"]))
    return results


def _build_level_payload(
    event: Dict[str, Any],
    reference_trading_date: date,
    reference_day: Candle,
    trigger_date: date,
    signal: Dict[str, Any],
) -> Dict[str, Any]:
    signal_type = signal["type"]
    line_price = round(float(signal["line_price"]), 2)
    trigger_time = signal["candle_time"]

    is_high_break = signal_type == "high_break"
    line_color = "#22c55e" if is_high_break else "#ef4444"
    short_tag = "AMV HIGH" if is_high_break else "AMV LOW"

    return {
        "event_type": "amavasya",
        "title": event.get("title", "Amavasya"),
        "month": event.get("month", ""),
        "amavasya_calendar_date": event["event_date"].isoformat(),
        "reference_date": reference_trading_date.isoformat(),
        "reference_day_color": reference_day.color,
        "reference_high": round(reference_day.high, 2),
        "reference_low": round(reference_day.low, 2),
        "trigger_date": trigger_date.isoformat(),
        "trigger_time": trigger_time.strftime("%Y-%m-%d %H:%M:%S"),
        "signal_type": signal_type,
        "line_price": line_price,
        "line_color": line_color,
        "line_style": 0,
        "line_width": 2,
        "label": f"{short_tag} {trigger_date.strftime('%d-%b-%Y')} @ {line_price}",
        "meta_label": f"Amavasya {reference_trading_date.isoformat()} -> {trigger_date.isoformat()}",
        "break_candle_open": round(signal["break_candle_open"], 2),
        "break_candle_high": round(signal["break_candle_high"], 2),
        "break_candle_low": round(signal["break_candle_low"], 2),
        "break_candle_close": round(signal["break_candle_close"], 2),
    }


def generate_amavasya_levels(raw_candles: List[Any], interval: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    requested_interval = str(interval or STRATEGY_INTERVAL).strip()

    if requested_interval not in SUPPORTED_INTERVALS:
        return {
            "status": False,
            "message": f"Amavasya strategy supports only intervals {sorted(SUPPORTED_INTERVALS)}. Received: {requested_interval}",
            "levels": [],
            "meta": {
                "strategy_interval": STRATEGY_INTERVAL,
                "requested_interval": requested_interval,
                "total_candles": 0,
                "trading_days": 0,
                "amavasya_events_loaded": 0,
                "levels_generated": 0,
                "skipped_events": [],
            },
        }

    candles = normalize_candles(raw_candles)
    if not candles:
        return {
            "status": False,
            "message": "No intraday candle data available for Amavasya strategy.",
            "levels": [],
            "meta": {
                "strategy_interval": STRATEGY_INTERVAL,
                "requested_interval": requested_interval,
                "total_candles": 0,
                "trading_days": 0,
                "amavasya_events_loaded": 0,
                "levels_generated": 0,
                "skipped_events": [],
            },
        }

    # If requested interval is daily, build daily OHLC by grouping intraday and
    # using each trading day's full range (high/low over the day).
    if requested_interval == "D":
        grouped_intraday = group_candles_by_date(candles)
        daily_map = build_daily_ohlc_from_intraday(grouped_intraday)
    else:
        grouped_intraday = group_candles_by_date(candles)
        # For intraday strategy, the grouped_intraday is used as-is and daily_map is built
        # from the group's first/last candle logic (already handled by function)
        daily_map = build_daily_ohlc_from_intraday(grouped_intraday)
    ordered_trading_dates = sorted(daily_map.keys())
    amavasya_rows = load_amavasya_reference_dates()

    if not amavasya_rows:
        return {
            "status": False,
            "message": f"amavasya.csv not found or invalid at {AMAVASYA_CSV_PATH}",
            "levels": [],
            "meta": {
                "strategy_interval": STRATEGY_INTERVAL,
                "requested_interval": requested_interval,
                "total_candles": len(candles),
                "trading_days": len(ordered_trading_dates),
                "amavasya_events_loaded": 0,
                "levels_generated": 0,
                "skipped_events": [],
            },
        }

    levels: List[Dict[str, Any]] = []
    processed_keys = set()
    skipped_events: List[Dict[str, str]] = []

    for event in amavasya_rows:
        event_date = event["event_date"]

        reference_trading_date = find_previous_or_same_trading_date(
            event_date=event_date,
            ordered_trading_dates=ordered_trading_dates,
        )
        if not reference_trading_date:
            skipped_events.append({
                "event_date": event_date.isoformat(),
                "month": event.get("month", ""),
                "reason": "no_previous_or_same_trading_day",
            })
            continue

        reference_day = daily_map.get(reference_trading_date)
        if not reference_day:
            skipped_events.append({
                "event_date": event_date.isoformat(),
                "month": event.get("month", ""),
                "reason": "reference_day_missing",
            })
            continue

        future_trading_dates = get_future_trading_dates(
            reference_date=reference_trading_date,
            ordered_trading_dates=ordered_trading_dates,
        )
        if not future_trading_dates:
            skipped_events.append({
                "event_date": event_date.isoformat(),
                "month": event.get("month", ""),
                "reason": "no_future_trading_days_found",
            })
            continue

        signals_with_dates = find_first_breaks_across_future_days(
            grouped_intraday=grouped_intraday,
            daily_map=daily_map,
            future_trading_dates=future_trading_dates,
            reference_high=reference_day.high,
            reference_low=reference_day.low,
        )
        if not signals_with_dates:
            skipped_events.append({
                "event_date": event_date.isoformat(),
                "month": event.get("month", ""),
                "reason": "no_break_signal_found_across_future_days",
            })
            continue

        for trigger_date, signal in signals_with_dates:
            unique_key = (
                event_date.isoformat(),
                reference_trading_date.isoformat(),
                trigger_date.isoformat(),
                signal["type"],
                round(float(signal["line_price"]), 2),
            )
            if unique_key in processed_keys:
                continue

            processed_keys.add(unique_key)
            levels.append(
                _build_level_payload(
                    event=event,
                    reference_trading_date=reference_trading_date,
                    reference_day=reference_day,
                    trigger_date=trigger_date,
                    signal=signal,
                )
            )

    levels.sort(key=lambda item: (item["trigger_time"], item["line_price"]))

    return {
        "status": True,
        "message": f"Amavasya strategy calculated successfully. Total levels: {len(levels)}",
        "levels": levels,
        "meta": {
            "strategy_interval": STRATEGY_INTERVAL,
            "requested_interval": requested_interval,
            "total_candles": len(candles),
            "trading_days": len(ordered_trading_dates),
            "amavasya_events_loaded": len(amavasya_rows),
            "levels_generated": len(levels),
            "csv_path": str(AMAVASYA_CSV_PATH),
            "skipped_events": skipped_events,
        },
    }