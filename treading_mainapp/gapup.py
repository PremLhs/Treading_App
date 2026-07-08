from __future__ import annotations

import logging
import threading
import time as time_sleep
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

from django.db import transaction
from django.utils import timezone

from .models import GapUpStatus, GapScanRun
from .services.angel_api import AngelBroker
from .services.nifty50_loader import get_nifty50_symbols

logger = logging.getLogger(__name__)

REQUEST_SLEEP_SECONDS = 6.0
INTER_SYMBOL_SLEEP_SECONDS = 5.0
RUNNING_STALE_SECONDS = 900

NIFTY_50_SYMBOLS = get_nifty50_symbols()

SYMBOL_DISPLAY_NAMES = {symbol: symbol.replace("NSE:", "") for symbol in NIFTY_50_SYMBOLS}


@dataclass
class Candle:
    dt: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


def _debug(message: str) -> None:
    print(f"[GAPUP DEBUG] {message}")
    logger.info(message)


def _to_decimal(value) -> Optional[Decimal]:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_timestamp_to_local_dt(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=dt_timezone.utc).astimezone(timezone.get_current_timezone())


def _normalize_candles(raw_candles: List[dict]) -> List[Candle]:
    normalized: List[Candle] = []

    for item in raw_candles:
        try:
            if isinstance(item, dict) and item.get("dt"):
                dt = item["dt"]
                if timezone.is_naive(dt):
                    dt = timezone.make_aware(dt, timezone.get_current_timezone())
                else:
                    dt = timezone.localtime(dt, timezone.get_current_timezone())
            else:
                dt = _parse_timestamp_to_local_dt(item["time"])

            candle = Candle(
                dt=dt,
                open=_to_decimal(item["open"]),
                high=_to_decimal(item["high"]),
                low=_to_decimal(item["low"]),
                close=_to_decimal(item["close"]),
            )

            if None in (candle.open, candle.high, candle.low, candle.close):
                _debug(f"Skipping candle because OHLC conversion failed: {item}")
                continue

            normalized.append(candle)

        except Exception as exc:
            _debug(f"Skipping bad candle row: {item} | error={exc}")
            continue

    normalized.sort(key=lambda x: x.dt)
    _debug(f"Normalized candles count={len(normalized)}")
    return normalized


def _get_latest_previous_daily_candle(day_candles: List[Candle], trade_date) -> Optional[Candle]:
    eligible = [c for c in day_candles if c.dt.date() < trade_date]
    if not eligible:
        return None
    return eligible[-1]


def _get_first_15m_candle(intraday_candles: List[Candle], target_date) -> Optional[Candle]:
    filtered = [c for c in intraday_candles if c.dt.date() == target_date]
    if not filtered:
        return None

    filtered.sort(key=lambda x: x.dt)
    for candle in filtered:
        if candle.dt.time() >= time(9, 15):
            return candle
    return filtered[0]


def _classify_gap(prev_day: Candle, first_15m: Candle) -> Tuple[bool, bool, str, str]:
    if first_15m.low > prev_day.high:
        return (
            True,
            False,
            "GAP UP",
            f"First 15m candle stayed completely above previous day high ({prev_day.high})."
        )

    if first_15m.high < prev_day.low:
        return (
            False,
            True,
            "GAP DOWN",
            f"First 15m candle stayed completely below previous day low ({prev_day.low})."
        )

    return (
        False,
        False,
        "NO GAP",
        "First 15m candle overlapped previous day range."
    )


def _clear_price_fields() -> Dict[str, object]:
    return {
        "prev_trade_date": None,
        "prev_open": None,
        "prev_high": None,
        "prev_low": None,
        "prev_close": None,
        "today_open": None,
        "today_high": None,
        "today_low": None,
        "today_close": None,
        "open_diff": None,
        "high_diff": None,
        "low_diff": None,
        "close_diff": None,
    }


def _save_failed_scan(symbol: str, trade_date, message: str):
    company_name = SYMBOL_DISPLAY_NAMES.get(symbol, symbol.replace("NSE:", ""))
    defaults = {
        "company_name": company_name,
        "gap_up": False,
        "gap_down": False,
        "gap_type": "SCAN FAILED",
        "notes": message,
        "data_source": "ANGEL_ONE_SMARTAPI",
        "candle_start": time(9, 15),
        "candle_end": time(9, 30),
    }
    defaults.update(_clear_price_fields())

    obj, _ = GapUpStatus.objects.update_or_create(
        symbol=symbol,
        trade_date=trade_date,
        defaults=defaults,
    )
    return obj


def _rate_limit_pause():
    time_sleep.sleep(REQUEST_SLEEP_SECONDS)


def _fetch_required_candles(broker: AngelBroker, symbol: str) -> Tuple[List[Candle], List[Candle]]:
    _debug(f"Fetching DAILY candles for {symbol}")
    daily_result = broker.fetch_historical_candles(symbol=symbol, interval="D")
    if not daily_result.get("status"):
        logger.error("DAILY fetch failed for %s | meta=%s", symbol, daily_result.get("meta", {}))
        raise ValueError(daily_result.get("message", "Daily candle fetch failed."))

    daily_candles = _normalize_candles(daily_result.get("candles", []))
    if not daily_candles:
        raise ValueError(f"No daily candles returned for {symbol}.")

    _debug(f"Fetched DAILY candles count={len(daily_candles)} for {symbol}")
    _rate_limit_pause()

    _debug(f"Fetching 15m candles for {symbol}")
    intraday_result = broker.fetch_historical_candles(symbol=symbol, interval="15")
    if not intraday_result.get("status"):
        logger.error("15m fetch failed for %s | meta=%s", symbol, intraday_result.get("meta", {}))
        raise ValueError(intraday_result.get("message", "15m candle fetch failed."))

    intraday_candles = _normalize_candles(intraday_result.get("candles", []))
    if not intraday_candles:
        raise ValueError(f"No 15m candles returned for {symbol}.")

    _debug(f"Fetched 15m candles count={len(intraday_candles)} for {symbol}")
    _rate_limit_pause()

    return daily_candles, intraday_candles


def _heartbeat(run_id: int) -> None:
    GapScanRun.objects.filter(id=run_id).update(last_heartbeat=timezone.now())


@transaction.atomic
def build_gapup_record(symbol: str, broker: AngelBroker, trade_date=None) -> GapUpStatus:
    if trade_date is None:
        trade_date = timezone.localdate()

    _debug(f"Checking gap strategy for {symbol}")

    daily_candles, intraday_candles = _fetch_required_candles(broker, symbol)

    prev_day_candle = _get_latest_previous_daily_candle(daily_candles, trade_date)
    if not prev_day_candle:
        raise ValueError(f"Previous daily candle not found for {symbol} before {trade_date}.")

    first_15m_candle = _get_first_15m_candle(intraday_candles, trade_date)
    if not first_15m_candle:
        raise ValueError(f"Today's first 15m candle not found for {symbol} on {trade_date}.")

    _debug(
        f"{symbol} prev_day=({prev_day_candle.dt.date()} O={prev_day_candle.open} H={prev_day_candle.high} "
        f"L={prev_day_candle.low} C={prev_day_candle.close})"
    )
    _debug(
        f"{symbol} first_15m=({first_15m_candle.dt} O={first_15m_candle.open} H={first_15m_candle.high} "
        f"L={first_15m_candle.low} C={first_15m_candle.close})"
    )

    gap_up, gap_down, gap_type, notes = _classify_gap(prev_day_candle, first_15m_candle)
    company_name = SYMBOL_DISPLAY_NAMES.get(symbol, symbol.replace("NSE:", ""))

    obj, _ = GapUpStatus.objects.update_or_create(
        symbol=symbol,
        trade_date=trade_date,
        defaults={
            "company_name": company_name,
            "prev_trade_date": prev_day_candle.dt.date(),
            "prev_open": prev_day_candle.open,
            "prev_high": prev_day_candle.high,
            "prev_low": prev_day_candle.low,
            "prev_close": prev_day_candle.close,
            "today_open": first_15m_candle.open,
            "today_high": first_15m_candle.high,
            "today_low": first_15m_candle.low,
            "today_close": first_15m_candle.close,
            "open_diff": _to_decimal(first_15m_candle.open - prev_day_candle.open),
            "high_diff": _to_decimal(first_15m_candle.high - prev_day_candle.high),
            "low_diff": _to_decimal(first_15m_candle.low - prev_day_candle.low),
            "close_diff": _to_decimal(first_15m_candle.close - prev_day_candle.close),
            "gap_up": gap_up,
            "gap_down": gap_down,
            "gap_type": gap_type,
            "notes": notes,
            "candle_start": time(9, 15),
            "candle_end": time(9, 30),
            "data_source": "ANGEL_ONE_SMARTAPI",
        },
    )

    _debug(
        f"Completed {symbol} => {gap_type} | prev_high={prev_day_candle.high} prev_low={prev_day_candle.low} "
        f"first15_high={first_15m_candle.high} first15_low={first_15m_candle.low}"
    )
    return obj


def _latest_run_for_date(trade_date):
    return GapScanRun.objects.filter(trade_date=trade_date).order_by("-started_at", "-id").first()


def _get_symbols_needing_scan(trade_date, force=False, limit_symbols: Optional[int] = None) -> List[str]:
    symbols = list(NIFTY_50_SYMBOLS)
    if limit_symbols:
        symbols = symbols[:limit_symbols]

    if force:
        return symbols

    rows = GapUpStatus.objects.filter(trade_date=trade_date)
    existing_by_symbol = {row.symbol: row for row in rows}

    pending_symbols: List[str] = []
    for symbol in symbols:
        row = existing_by_symbol.get(symbol)
        if row is None:
            pending_symbols.append(symbol)
            continue
        if row.gap_type == "SCAN FAILED":
            pending_symbols.append(symbol)

    return pending_symbols


def _can_reuse_existing_data(trade_date, force=False, limit_symbols: Optional[int] = None):
    rows = GapUpStatus.objects.filter(trade_date=trade_date)
    symbols_needing_scan = _get_symbols_needing_scan(
        trade_date=trade_date,
        force=force,
        limit_symbols=limit_symbols,
    )

    if force:
        return False, rows.count(), symbols_needing_scan

    if not symbols_needing_scan and rows.exists():
        return True, rows.count(), []

    return False, rows.count(), symbols_needing_scan


def acquire_scan_run(
    trade_date=None,
    scan_type="MANUAL",
    trigger_source="",
    force=False,
    limit_symbols: Optional[int] = None,
) -> Tuple[Optional[GapScanRun], bool, str, List[str]]:
    if trade_date is None:
        trade_date = timezone.localdate()

    with transaction.atomic():
        latest = GapScanRun.objects.select_for_update().filter(trade_date=trade_date).order_by("-started_at", "-id").first()

        if latest and latest.status == "RUNNING":
            stale = latest.last_heartbeat and (timezone.now() - latest.last_heartbeat).total_seconds() > RUNNING_STALE_SECONDS
            if not stale:
                pending_symbols = _get_symbols_needing_scan(
                    trade_date=trade_date,
                    force=force,
                    limit_symbols=limit_symbols,
                )
                return latest, False, "Scan already running.", pending_symbols
            latest.status = "FAILED"
            latest.finished_at = timezone.now()
            latest.message = "Previous running scan marked stale and failed automatically."
            latest.save(update_fields=["status", "finished_at", "message", "updated_at"])

        reusable, row_count, symbols_needing_scan = _can_reuse_existing_data(
            trade_date=trade_date,
            force=force,
            limit_symbols=limit_symbols,
        )

        if reusable:
            latest_ok = GapScanRun.objects.filter(
                trade_date=trade_date,
                status="COMPLETED"
            ).order_by("-started_at", "-id").first()
            if latest_ok:
                return latest_ok, False, f"Using existing stored scan result ({row_count} rows).", []

        if symbols_needing_scan:
            message = f"Fresh scan started for {len(symbols_needing_scan)} pending symbol(s)."
        else:
            message = "Fresh scan started."

        run = GapScanRun.objects.create(
            trade_date=trade_date,
            scan_type=scan_type,
            status="RUNNING",
            started_at=timezone.now(),
            last_heartbeat=timezone.now(),
            trigger_source=trigger_source,
            lock_token=uuid.uuid4().hex,
            message=message,
        )
        return run, True, message, symbols_needing_scan


def finalize_scan_run(run_id: int, *, success_count: int, error_count: int, total_count: int, message: str, status: str):
    GapScanRun.objects.filter(id=run_id).update(
        status=status,
        finished_at=timezone.now(),
        last_heartbeat=timezone.now(),
        success_count=success_count,
        error_count=error_count,
        total_count=total_count,
        message=message,
    )


def update_all_gapup_data(
    trade_date=None,
    limit_symbols: Optional[int] = None,
    scan_type="MANUAL",
    trigger_source="",
    force=False,
) -> Dict[str, object]:
    if trade_date is None:
        trade_date = timezone.localdate()

    run, should_scan, run_message, symbols_to_scan = acquire_scan_run(
        trade_date=trade_date,
        scan_type=scan_type,
        trigger_source=trigger_source,
        force=force,
        limit_symbols=limit_symbols,
    )

    if not should_scan:
        rows = list(GapUpStatus.objects.filter(trade_date=trade_date).order_by("symbol"))
        errors = []
        failed_count = sum(1 for row in rows if row.gap_type == "SCAN FAILED")
        return {
            "trade_date": trade_date,
            "success_count": max(len(rows) - failed_count, 0),
            "error_count": failed_count,
            "errors": errors,
            "records": rows,
            "status": failed_count == 0,
            "message": run_message,
            "scan_skipped": True,
            "run_id": run.id if run else None,
        }

    results = []
    errors = []

    try:
        broker = AngelBroker()
        connection = broker.connect()
        if not connection.get("status"):
            raise ValueError(connection.get("message", "Broker login failed."))

        symbols = symbols_to_scan or _get_symbols_needing_scan(
            trade_date=trade_date,
            force=force,
            limit_symbols=limit_symbols,
        )

        _debug(f"========== GAP STRATEGY SCAN STARTED FOR {trade_date} ==========")
        _debug(f"Pending symbols count={len(symbols)}")

        for idx, symbol in enumerate(symbols, start=1):
            _heartbeat(run.id)
            _debug(f"[{idx}/{len(symbols)}] Scanning {symbol}")
            try:
                obj = build_gapup_record(symbol=symbol, broker=broker, trade_date=trade_date)
                results.append(obj)
            except Exception as exc:
                logger.exception("Gap scan failed for %s", symbol)
                failed_obj = _save_failed_scan(symbol, trade_date, str(exc))
                results.append(failed_obj)
                errors.append({"symbol": symbol, "error": str(exc)})
                _debug(f"FAILED {symbol} => {exc}")

            time_sleep.sleep(INTER_SYMBOL_SLEEP_SECONDS)

        all_rows = list(GapUpStatus.objects.filter(trade_date=trade_date).order_by("symbol"))
        total_failed_now = sum(1 for row in all_rows if row.gap_type == "SCAN FAILED")
        total_success_now = len(all_rows) - total_failed_now

        finalize_scan_run(
            run.id,
            success_count=total_success_now,
            error_count=total_failed_now,
            total_count=len(all_rows),
            status="COMPLETED" if total_failed_now == 0 else "COMPLETED",
            message=(
                f"Gap scan completed for {trade_date}. "
                f"Scanned={len(symbols)} TotalSuccess={total_success_now} TotalFailed={total_failed_now}"
            ),
        )

        _debug(
            f"========== GAP STRATEGY SCAN COMPLETED | scanned={len(symbols)} "
            f"total_success={total_success_now} total_failed={total_failed_now} =========="
        )

        return {
            "trade_date": trade_date,
            "success_count": total_success_now,
            "error_count": total_failed_now,
            "errors": errors,
            "records": all_rows,
            "status": total_failed_now == 0,
            "message": (
                f"Gap scan completed for {trade_date}. "
                f"Scanned={len(symbols)} TotalSuccess={total_success_now} TotalFailed={total_failed_now}"
            ),
            "scan_skipped": False,
            "run_id": run.id,
        }

    except Exception as exc:
        logger.exception("Gap scan fatal failure")
        finalize_scan_run(
            run.id,
            success_count=0,
            error_count=1,
            total_count=0,
            status="FAILED",
            message=str(exc),
        )
        raise


def start_gap_scan_in_background(
    trade_date=None,
    limit_symbols: Optional[int] = None,
    scan_type="MANUAL",
    trigger_source="",
    force=False,
) -> Dict[str, object]:
    if trade_date is None:
        trade_date = timezone.localdate()

    run, should_scan, run_message, symbols_to_scan = acquire_scan_run(
        trade_date=trade_date,
        scan_type=scan_type,
        trigger_source=trigger_source,
        force=force,
        limit_symbols=limit_symbols,
    )

    if not should_scan:
        return {
            "status": True,
            "queued": False,
            "message": run_message,
            "run_id": run.id if run else None,
            "trade_date": str(trade_date),
        }

    def _runner():
        try:
            broker = AngelBroker()
            connection = broker.connect()
            if not connection.get("status"):
                raise ValueError(connection.get("message", "Broker login failed."))

            symbols = symbols_to_scan or _get_symbols_needing_scan(
                trade_date=trade_date,
                force=force,
                limit_symbols=limit_symbols,
            )
            results = []
            errors = []

            _debug(f"========== BACKGROUND GAP STRATEGY SCAN STARTED FOR {trade_date} ==========")
            _debug(f"Pending symbols count={len(symbols)}")

            for idx, symbol in enumerate(symbols, start=1):
                _heartbeat(run.id)
                _debug(f"[BG {idx}/{len(symbols)}] Scanning {symbol}")
                try:
                    obj = build_gapup_record(symbol=symbol, broker=broker, trade_date=trade_date)
                    results.append(obj)
                except Exception as exc:
                    logger.exception("Background gap scan failed for %s", symbol)
                    failed_obj = _save_failed_scan(symbol, trade_date, str(exc))
                    results.append(failed_obj)
                    errors.append({"symbol": symbol, "error": str(exc)})
                time_sleep.sleep(INTER_SYMBOL_SLEEP_SECONDS)

            all_rows = list(GapUpStatus.objects.filter(trade_date=trade_date).order_by("symbol"))
            total_failed_now = sum(1 for row in all_rows if row.gap_type == "SCAN FAILED")
            total_success_now = len(all_rows) - total_failed_now

            finalize_scan_run(
                run.id,
                success_count=total_success_now,
                error_count=total_failed_now,
                total_count=len(all_rows),
                status="COMPLETED",
                message=(
                    f"Gap scan completed for {trade_date}. "
                    f"Scanned={len(symbols)} TotalSuccess={total_success_now} TotalFailed={total_failed_now}"
                ),
            )

            _debug(
                f"========== BACKGROUND GAP STRATEGY SCAN COMPLETED | scanned={len(symbols)} "
                f"total_success={total_success_now} total_failed={total_failed_now} =========="
            )

        except Exception as exc:
            logger.exception("Background gap scan fatal failure")
            finalize_scan_run(
                run.id,
                success_count=0,
                error_count=1,
                total_count=0,
                status="FAILED",
                message=str(exc),
            )

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()

    return {
        "status": True,
        "queued": True,
        "message": (
            f"Gap scan started in background for "
            f"{len(symbols_to_scan) if symbols_to_scan else 0} pending symbol(s)."
        ),
        "run_id": run.id,
        "trade_date": str(trade_date),
    }


def get_gap_scan_runtime_status(trade_date=None) -> Dict[str, object]:
    if trade_date is None:
        trade_date = timezone.localdate()

    latest = _latest_run_for_date(trade_date)
    rows = GapUpStatus.objects.filter(trade_date=trade_date)
    failed_rows = rows.filter(gap_type="SCAN FAILED").count()
    total_symbols = len(NIFTY_50_SYMBOLS)
    db_rows = rows.count()
    pending_count = max(total_symbols - (db_rows - failed_rows), 0)

    if not latest:
        return {
            "trade_date": str(trade_date),
            "has_run": False,
            "status": "NOT_STARTED",
            "message": "No scan started yet.",
            "total_rows": db_rows,
            "failed_count": failed_rows,
            "pending_count": pending_count,
        }

    return {
        "trade_date": str(trade_date),
        "has_run": True,
        "run_id": latest.id,
        "scan_type": latest.scan_type,
        "status": latest.status,
        "message": latest.message,
        "started_at": timezone.localtime(latest.started_at).strftime("%d-%m-%Y %I:%M:%S %p") if latest.started_at else "",
        "finished_at": timezone.localtime(latest.finished_at).strftime("%d-%m-%Y %I:%M:%S %p") if latest.finished_at else "",
        "last_heartbeat": timezone.localtime(latest.last_heartbeat).strftime("%d-%m-%Y %I:%M:%S %p") if latest.last_heartbeat else "",
        "success_count": latest.success_count,
        "error_count": latest.error_count,
        "total_count": latest.total_count,
        "db_rows": db_rows,
        "failed_count": failed_rows,
        "pending_count": pending_count,
        "is_running": latest.status == "RUNNING",
    }