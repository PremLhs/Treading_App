import logging
import os
import socket
import time
from datetime import datetime, timedelta, time as dt_time
from typing import Any, Dict, List, Optional

import pyotp
import requests
from django.utils import timezone

from .nifty50_loader import get_symbol_token_map

logger = logging.getLogger(__name__)


class AngelBroker:
    BASE_URL = "https://apiconnect.angelone.in"
    LOGIN_URL = f"{BASE_URL}/rest/auth/angelbroking/user/v1/loginByPassword"
    HISTORICAL_URL = f"{BASE_URL}/rest/secure/angelbroking/historical/v1/getCandleData"

    REQUEST_TIMEOUT = 30
    MAX_RETRIES = 3
    RETRY_SLEEP_SECONDS = 2.5
    RATE_LIMIT_SLEEP_SECONDS = 1.5

    SYMBOL_TOKEN_MAP = get_symbol_token_map()

    INTERVAL_MAP = {
        "1": "ONE_MINUTE",
        "3": "THREE_MINUTE",
        "5": "FIVE_MINUTE",
        "15": "FIFTEEN_MINUTE",
        "30": "THIRTY_MINUTE",
        "60": "ONE_HOUR",
        "D": "ONE_DAY",
        "W": "ONE_WEEK",
    }

    def __init__(self) -> None:
        self.api_key = os.getenv("ANGEL_API_KEY", "").strip()
        self.client_id = os.getenv("ANGEL_CLIENT_ID", "").strip()
        self.pin = os.getenv("ANGEL_PIN", "").strip()
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET", "").strip()
        self.jwt_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.feed_token: Optional[str] = None
        self._public_ip_cache: Optional[str] = None
        self._local_ip_cache: Optional[str] = None
        self.session = requests.Session()

    def _env_status(self) -> Dict[str, Any]:
        return {
            "api_key_present": bool(self.api_key),
            "client_code_present": bool(self.client_id),
            "password_present": bool(self.pin),
            "totp_secret_present": bool(self.totp_secret),
        }

    def _get_public_ip(self) -> str:
        if self._public_ip_cache:
            return self._public_ip_cache
        try:
            self._public_ip_cache = self.session.get("https://api.ipify.org", timeout=5).text.strip()
        except Exception:
            self._public_ip_cache = "127.0.0.1"
        return self._public_ip_cache

    def _get_local_ip(self) -> str:
        if self._local_ip_cache:
            return self._local_ip_cache
        try:
            self._local_ip_cache = socket.gethostbyname(socket.gethostname())
        except Exception:
            self._local_ip_cache = "127.0.0.1"
        return self._local_ip_cache

    def _base_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": self._get_local_ip(),
            "X-ClientPublicIP": self._get_public_ip(),
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": self.api_key,
            "User-Agent": "Mozilla/5.0",
        }

    def _authorized_headers(self) -> Dict[str, str]:
        headers = self._base_headers().copy()
        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        return headers

    def get_symbol_config(self, symbol: str) -> Optional[Dict[str, str]]:
        return self.SYMBOL_TOKEN_MAP.get(symbol)

    def connect(self) -> Dict[str, Any]:
        env_status = self._env_status()

        if not all([self.api_key, self.client_id, self.pin, self.totp_secret]):
            logger.error("Angel credentials missing | env_status=%s", env_status)
            return {
                "status": False,
                "message": "Missing Angel credentials in environment.",
                "env_status": env_status,
            }

        if self.jwt_token:
            return {
                "status": True,
                "message": "Angel One session already active.",
                "env_status": env_status,
            }

        try:
            totp = pyotp.TOTP(self.totp_secret).now()
            payload = {
                "clientcode": self.client_id,
                "password": self.pin,
                "totp": totp,
            }

            logger.info("Connecting to Angel One for client_id=%s", self.client_id)

            response = self.session.post(
                self.LOGIN_URL,
                json=payload,
                headers=self._base_headers(),
                timeout=self.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("status"):
                logger.error("Angel login rejected | response=%s", data)
                return {
                    "status": False,
                    "message": data.get("message", "Angel login failed."),
                    "env_status": env_status,
                }

            jwt_data = data.get("data", {}) or {}
            self.jwt_token = jwt_data.get("jwtToken")
            self.refresh_token = jwt_data.get("refreshToken")
            self.feed_token = jwt_data.get("feedToken")

            logger.info("Angel login successful for client_id=%s", self.client_id)

            return {
                "status": True,
                "message": "Angel One login successful.",
                "env_status": env_status,
            }
        except Exception as exc:
            logger.exception("Angel login failed with exception")
            return {
                "status": False,
                "message": f"Angel login exception: {exc}",
                "env_status": env_status,
            }

    def _ensure_connected(self) -> Dict[str, Any]:
        if self.jwt_token:
            return {"status": True}
        return self.connect()

    def _build_historical_payload(self, symbol: str, interval: str) -> Optional[Dict[str, str]]:
        symbol_data = self.get_symbol_config(symbol)
        if not symbol_data:
            return None

        interval_key = self.INTERVAL_MAP.get(interval.upper())
        if not interval_key:
            return None

        now_local = timezone.localtime()
        if interval.upper() == "D":
            from_dt = now_local - timedelta(days=730)
        elif interval.upper() == "W":
            from_dt = now_local - timedelta(days=730)
        else:
            from_dt = now_local - timedelta(days=730)

        return {
            "exchange": symbol_data["exchange"],
            "symboltoken": symbol_data["symboltoken"],
            "interval": interval_key,
            "fromdate": from_dt.strftime("%Y-%m-%d %H:%M"),
            "todate": now_local.strftime("%Y-%m-%d %H:%M"),
        }

    def _normalize_candle_row(self, row: List[Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(row, list) or len(row) < 5:
            return None
        try:
            candle_dt = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
            candle_dt = timezone.localtime(candle_dt)
            return {
                "dt": candle_dt,
                "date": candle_dt.date(),
                "time": int(candle_dt.timestamp()),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]) if len(row) > 5 and row[5] is not None else 0,
            }
        except Exception:
            logger.exception("Failed to normalize candle row: %s", row)
            return None

    def _is_rate_limited(self, response: Optional[requests.Response], body_text: str) -> bool:
        if response is not None and response.status_code in (403, 429):
            lowered = body_text.lower()
            if "exceeding access rate" in lowered or "access rate" in lowered or "rate" in lowered:
                return True
        return False

    def _historical_request_with_retry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        last_error: Dict[str, Any] = {}

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.session.post(
                    self.HISTORICAL_URL,
                    json=payload,
                    headers=self._authorized_headers(),
                    timeout=self.REQUEST_TIMEOUT,
                )
                response.raise_for_status()
                return {
                    "status": True,
                    "data": response.json(),
                    "meta": {"attempt": attempt},
                }
            except requests.HTTPError as exc:
                status_code = exc.response.status_code if exc.response is not None else None
                body_text = exc.response.text[:500] if exc.response is not None else str(exc)

                logger.error(
                    "Historical fetch failed | interval=%s status=%s attempt=%s body=%s",
                    payload.get("interval"),
                    status_code,
                    attempt,
                    body_text,
                )

                last_error = {
                    "status": False,
                    "status_code": status_code,
                    "body_text": body_text,
                    "attempt": attempt,
                }

                if self._is_rate_limited(exc.response, body_text) and attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_SLEEP_SECONDS * attempt)
                    continue
                break
            except Exception as exc:
                logger.exception("Unexpected historical request failure")
                last_error = {
                    "status": False,
                    "status_code": None,
                    "body_text": str(exc),
                    "attempt": attempt,
                }
                break

        return last_error

    def fetch_historical_candles(self, symbol: str, interval: str) -> Dict[str, Any]:
        connection = self._ensure_connected()
        if not connection.get("status"):
            return {
                "status": False,
                "message": connection.get("message", "Broker connection failed."),
                "candles": [],
                "meta": {"symbol": symbol, "interval": interval, "source": "angel_historical"},
            }

        symbol_data = self.get_symbol_config(symbol)
        if not symbol_data:
            return {
                "status": False,
                "message": f"Symbol mapping not found for {symbol}.",
                "candles": [],
                "meta": {"symbol": symbol, "interval": interval, "source": "angel_historical"},
            }

        payload = self._build_historical_payload(symbol, interval)
        if not payload:
            return {
                "status": False,
                "message": f"Unsupported interval {interval}.",
                "candles": [],
                "meta": {"symbol": symbol, "interval": interval, "source": "angel_historical"},
            }

        logger.info("Fetching candles | symbol=%s interval=%s payload=%s", symbol, interval, payload)
        time.sleep(self.RATE_LIMIT_SLEEP_SECONDS)

        result = self._historical_request_with_retry(payload)
        if not result.get("status"):
            status_code = result.get("status_code")
            body_text = result.get("body_text", "")
            attempt = result.get("attempt")
            return {
                "status": False,
                "message": f"Historical candle API failed for interval {interval}: HTTP {status_code}",
                "candles": [],
                "meta": {
                    "symbol": symbol,
                    "interval": interval,
                    "payload_interval": payload["interval"],
                    "status_code": status_code,
                    "response_body": body_text,
                    "attempt": attempt,
                    "source": "angel_historical",
                },
            }

        data = result.get("data", {})
        rows = data.get("data", []) or []
        candles = [item for item in (self._normalize_candle_row(r) for r in rows) if item]

        logger.info(
            "Fetched candles success | symbol=%s interval=%s count=%s",
            symbol,
            interval,
            len(candles),
        )

        return {
            "status": True,
            "message": "Historical candles fetched successfully.",
            "candles": candles,
            "meta": {
                "symbol": symbol,
                "interval": interval,
                "payload_interval": payload["interval"],
                "count": len(candles),
                "attempt": result.get("meta", {}).get("attempt", 1),
                "source": "angel_historical",
            },
        }

    def fetch_first_15m_candle(self, symbol: str, trade_date=None) -> Dict[str, Any]:
        if trade_date is None:
            trade_date = timezone.localdate()

        result = self.fetch_historical_candles(symbol=symbol, interval="15")
        if not result.get("status"):
            return {
                "status": False,
                "message": result.get("message", "Unable to fetch 15m candles."),
                "candle": None,
                "meta": result.get("meta", {}),
            }

        candles = result.get("candles", [])
        todays = [c for c in candles if c.get("date") == trade_date]
        todays.sort(key=lambda x: x.get("time", 0))

        for candle in todays:
            dt_obj = candle.get("dt")
            if dt_obj and dt_obj.time() >= dt_time(9, 15):
                logger.info("First 15m candle found | symbol=%s trade_date=%s candle=%s", symbol, trade_date, candle)
                return {
                    "status": True,
                    "message": "09:15 candle fetched successfully.",
                    "candle": candle,
                    "meta": result.get("meta", {}),
                }

        logger.warning("09:15 candle not found | symbol=%s trade_date=%s", symbol, trade_date)
        return {
            "status": False,
            "message": f"09:15 candle not found for {symbol} on {trade_date}.",
            "candle": None,
            "meta": result.get("meta", {}),
        }

    def get_mock_candles(self, symbol=None, interval=None):
        return self.fetch_historical_candles(symbol=symbol, interval=interval)