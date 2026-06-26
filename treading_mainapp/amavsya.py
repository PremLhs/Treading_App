import csv
import logging
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


@dataclass(frozen=True)
class Candle:
    dt: datetime
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


def _safe_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_epoch_to_datetime(value: Any) -> Optional[datetime]:
    try:
        ts = int(float(value))
        return datetime.fromtimestamp(ts)
    except (TypeError, ValueError, OSError):
        return None


def _parse_candle_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value

    if isinstance(value, (int, float)):
        return _parse_epoch_to_datetime(value)

    text = str(value).strip()
    if not text:
        return None

    if text.isdigit():
        parsed = _parse_epoch_to_datetime(text)
        if parsed:
            return parsed

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None)
            return parsed
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def _parse_event_datetime(date_text: str, year: int) -> Optional[datetime]:
    if date_text is None:
        return None

    text = str(date_text).strip()
    if not text:
        return None

    candidates = [f"{text} {year}", text]
    formats = [
        "%b %d, %I:%M %p %Y",
        "%B %d, %I:%M %p %Y",
        "%b %d, %I:%M:%S %p %Y",
        "%B %d, %I:%M:%S %p %Y",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
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


def load_amavasya_reference_dates() -> List[Dict]:
    rows: List[Dict] = []

    if not AMAVASYA_CSV_PATH.exists():
        logger.warning("amavasya.csv not found at %s", AMAVASYA_CSV_PATH)
        return rows

    with open(AMAVASYA_CSV_PATH, mode="r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            logger.warning("amavasya.csv has no headers")
            return rows

        fieldnames = {name.strip() for name in reader.fieldnames if name}

        simple_date_mode = "date" in fieldnames
        detailed_mode = {"year", "month", "title", "start", "end"}.issubset(fieldnames)

        if not simple_date_mode and not detailed_mode:
            logger.warning("amavasya.csv invalid headers: %s", reader.fieldnames)
            return rows

        for row in reader:
            if simple_date_mode:
                raw_date = str(row.get("date", "")).strip()
                try:
                    event_dt = datetime.strptime(raw_date, "%Y-%m-%d")
                except ValueError:
                    continue

                rows.append({
                    "year": event_dt.year,
                    "month": event_dt.strftime("%B"),
                    "title": "Amavasya",
                    "start": raw_date,
                    "end": raw_date,
                    "start_dt": event_dt,
                    "end_dt": event_dt,
                    "event_date": event_dt.date(),
                })
                continue

            year_raw = str(row.get("year", "")).strip()
            if not year_raw.isdigit():
                continue

            year = int(year_raw)
            month = str(row.get("month", "")).strip()
            title = str(row.get("title", "")).strip() or "Amavasya"
            start_text = str(row.get("start", "")).strip()
            end_text = str(row.get("end", "")).strip()

            end_dt = _parse_event_datetime(end_text, year)
            start_dt = _parse_event_datetime(start_text, year)

            if end_dt is None:
                continue

            rows.append({
                "year": year,
                "month": month,
                "title": title,
                "start": start_text,
                "end": end_text,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "event_date": end_dt.astimezone(IST).date(),
            })

    rows.sort(key=lambda item: item["event_date"])
    return rows


def normalize_candles(raw_candles: List[Any]) -> List[Candle]:
    normalized: List[Candle] = []
    seen: set[Tuple[datetime, float, float, float, float]] = set()

    for item in raw_candles or []:
        dt = None
        open_price = None
        high_price = None
        low_price = None
        close_price = None

        if isinstance(item, dict):
            dt = _parse_candle_datetime(item.get("dt") or item.get("time"))
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
    eligible = [d for d in ordered_trading_dates if d <= event_date]
    return eligible[-1] if eligible else None


def find_next_same_color_trading_day(
    reference_date: date,
    reference_color: str,
    ordered_trading_dates: List[date],
    daily_map: Dict[date, Candle],
) -> Optional[date]:
    try:
        reference_index = ordered_trading_dates.index(reference_date)
    except ValueError:
        return None

    for next_date in ordered_trading_dates[reference_index + 1:]:
        day_candle = daily_map.get(next_date)
        if day_candle and day_candle.color == reference_color:
            return next_date

    return None


def find_breakout_breakdown_signals(
    intraday_candles: List[Candle],
    reference_high: float,
    reference_low: float,
) -> List[Dict]:
    signals: List[Dict] = []
    high_break_added = False
    low_break_added = False

    for candle in intraday_candles:
        if (not high_break_added) and candle.high > reference_high:
            signals.append({
                "type": "high_break",
                "line_price": candle.high,
                "candle_time": candle.dt,
                "break_candle_open": candle.open,
                "break_candle_high": candle.high,
                "break_candle_low": candle.low,
                "break_candle_close": candle.close,
            })
            high_break_added = True

        if (not low_break_added) and candle.low < reference_low:
            signals.append({
                "type": "low_break",
                "line_price": candle.low,
                "candle_time": candle.dt,
                "break_candle_open": candle.open,
                "break_candle_high": candle.high,
                "break_candle_low": candle.low,
                "break_candle_close": candle.close,
            })
            low_break_added = True

        if high_break_added and low_break_added:
            break

    return signals


def _build_level_payload(
    event: Dict,
    reference_trading_date: date,
    reference_day: Candle,
    trigger_date: date,
    signal: Dict,
) -> Dict:
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


def generate_amavasya_levels(raw_candles: List[Any], interval: Optional[str] = None, **kwargs) -> Dict:
    requested_interval = str(interval or STRATEGY_INTERVAL).strip().upper()

    if requested_interval not in SUPPORTED_INTRADAY_INTERVALS:
        return {
            "status": False,
            "message": f"Amavasya strategy supports only intraday intervals {sorted(SUPPORTED_INTRADAY_INTERVALS)}. Received: {requested_interval}",
            "levels": [],
            "meta": {
                "strategy_interval": STRATEGY_INTERVAL,
                "requested_interval": requested_interval,
                "total_candles": 0,
                "trading_days": 0,
                "amavasya_events_loaded": 0,
                "levels_generated": 0,
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
            },
        }

    grouped_intraday = group_candles_by_date(candles)
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
            },
        }

    levels: List[Dict] = []
    processed_keys = set()

    for event in amavasya_rows:
        event_date = event["event_date"]

        reference_trading_date = find_previous_or_same_trading_date(
            event_date=event_date,
            ordered_trading_dates=ordered_trading_dates,
        )
        if not reference_trading_date:
            continue

        reference_day = daily_map.get(reference_trading_date)
        if not reference_day:
            continue

        next_same_color_date = find_next_same_color_trading_day(
            reference_date=reference_trading_date,
            reference_color=reference_day.color,
            ordered_trading_dates=ordered_trading_dates,
            daily_map=daily_map,
        )
        if not next_same_color_date:
            continue

        trigger_day_candles = grouped_intraday.get(next_same_color_date, [])
        if not trigger_day_candles:
            continue

        signals = find_breakout_breakdown_signals(
            intraday_candles=trigger_day_candles,
            reference_high=reference_day.high,
            reference_low=reference_day.low,
        )
        if not signals:
            continue

        for signal in signals:
            unique_key = (
                event_date.isoformat(),
                reference_trading_date.isoformat(),
                next_same_color_date.isoformat(),
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
                    trigger_date=next_same_color_date,
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
        },
    }