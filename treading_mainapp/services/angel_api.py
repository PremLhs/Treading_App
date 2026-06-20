import os
import socket
import pyotp
import requests

from datetime import datetime, timedelta, time as dt_time
from django.utils import timezone


class AngelBroker:
    BASE_URL = "https://apiconnect.angelone.in"

    SYMBOL_TOKEN_MAP = {
        "NSE:RELIANCE": {"exchange": "NSE", "tradingsymbol": "RELIANCE-EQ", "symboltoken": "2885"},
        "NSE:TCS": {"exchange": "NSE", "tradingsymbol": "TCS-EQ", "symboltoken": "11536"},
        "NSE:HDFCBANK": {"exchange": "NSE", "tradingsymbol": "HDFCBANK-EQ", "symboltoken": "1333"},
        "NSE:ICICIBANK": {"exchange": "NSE", "tradingsymbol": "ICICIBANK-EQ", "symboltoken": "4963"},
        "NSE:INFY": {"exchange": "NSE", "tradingsymbol": "INFY-EQ", "symboltoken": "1594"},
        "NSE:BHARTIARTL": {"exchange": "NSE", "tradingsymbol": "BHARTIARTL-EQ", "symboltoken": "10604"},
        "NSE:ITC": {"exchange": "NSE", "tradingsymbol": "ITC-EQ", "symboltoken": "1660"},
        "NSE:SBIN": {"exchange": "NSE", "tradingsymbol": "SBIN-EQ", "symboltoken": "3045"},
        "NSE:LT": {"exchange": "NSE", "tradingsymbol": "LT-EQ", "symboltoken": "11483"},
        "NSE:HINDUNILVR": {"exchange": "NSE", "tradingsymbol": "HINDUNILVR-EQ", "symboltoken": "1394"},
        "NSE:AXISBANK": {"exchange": "NSE", "tradingsymbol": "AXISBANK-EQ", "symboltoken": "5900"},
        "NSE:KOTAKBANK": {"exchange": "NSE", "tradingsymbol": "KOTAKBANK-EQ", "symboltoken": "1922"},
        "NSE:BAJFINANCE": {"exchange": "NSE", "tradingsymbol": "BAJFINANCE-EQ", "symboltoken": "317"},
        "NSE:M&M": {"exchange": "NSE", "tradingsymbol": "M&M-EQ", "symboltoken": "2031"},
        "NSE:MARUTI": {"exchange": "NSE", "tradingsymbol": "MARUTI-EQ", "symboltoken": "10999"},
        "NSE:SUNPHARMA": {"exchange": "NSE", "tradingsymbol": "SUNPHARMA-EQ", "symboltoken": "3351"},
        "NSE:NTPC": {"exchange": "NSE", "tradingsymbol": "NTPC-EQ", "symboltoken": "11630"},
        "NSE:POWERGRID": {"exchange": "NSE", "tradingsymbol": "POWERGRID-EQ", "symboltoken": "14977"},
        "NSE:ULTRACEMCO": {"exchange": "NSE", "tradingsymbol": "ULTRACEMCO-EQ", "symboltoken": "11532"},
        "NSE:TITAN": {"exchange": "NSE", "tradingsymbol": "TITAN-EQ", "symboltoken": "3506"},
        "NSE:ASIANPAINT": {"exchange": "NSE", "tradingsymbol": "ASIANPAINT-EQ", "symboltoken": "236"},
        "NSE:ADANIPORTS": {"exchange": "NSE", "tradingsymbol": "ADANIPORTS-EQ", "symboltoken": "15083"},
        "NSE:BAJAJFINSV": {"exchange": "NSE", "tradingsymbol": "BAJAJFINSV-EQ", "symboltoken": "16675"},
        "NSE:NESTLEIND": {"exchange": "NSE", "tradingsymbol": "NESTLEIND-EQ", "symboltoken": "17963"},
        "NSE:WIPRO": {"exchange": "NSE", "tradingsymbol": "WIPRO-EQ", "symboltoken": "3787"},
        "NSE:TECHM": {"exchange": "NSE", "tradingsymbol": "TECHM-EQ", "symboltoken": "13538"},
        "NSE:HCLTECH": {"exchange": "NSE", "tradingsymbol": "HCLTECH-EQ", "symboltoken": "7229"},
        "NSE:INDUSINDBK": {"exchange": "NSE", "tradingsymbol": "INDUSINDBK-EQ", "symboltoken": "5258"},
        "NSE:TATAMOTORS": {"exchange": "NSE", "tradingsymbol": "TATAMOTORS-EQ", "symboltoken": "3456"},
        "NSE:ETERNAL": {"exchange": "NSE", "tradingsymbol": "ETERNAL-EQ", "symboltoken": "10000"},
        "NSE:TRENT": {"exchange": "NSE", "tradingsymbol": "TRENT-EQ", "symboltoken": "1964"},
        "NSE:SHRIRAMFIN": {"exchange": "NSE", "tradingsymbol": "SHRIRAMFIN-EQ", "symboltoken": "4306"},
        "NSE:BEL": {"exchange": "NSE", "tradingsymbol": "BEL-EQ", "symboltoken": "383"},
        "NSE:COALINDIA": {"exchange": "NSE", "tradingsymbol": "COALINDIA-EQ", "symboltoken": "20374"},
        "NSE:JSWSTEEL": {"exchange": "NSE", "tradingsymbol": "JSWSTEEL-EQ", "symboltoken": "11723"},
        "NSE:TATASTEEL": {"exchange": "NSE", "tradingsymbol": "TATASTEEL-EQ", "symboltoken": "3499"},
        "NSE:GRASIM": {"exchange": "NSE", "tradingsymbol": "GRASIM-EQ", "symboltoken": "1232"},
        "NSE:DRREDDY": {"exchange": "NSE", "tradingsymbol": "DRREDDY-EQ", "symboltoken": "881"},
        "NSE:CIPLA": {"exchange": "NSE", "tradingsymbol": "CIPLA-EQ", "symboltoken": "694"},
        "NSE:APOLLOHOSP": {"exchange": "NSE", "tradingsymbol": "APOLLOHOSP-EQ", "symboltoken": "157"},
        "NSE:SBILIFE": {"exchange": "NSE", "tradingsymbol": "SBILIFE-EQ", "symboltoken": "21808"},
        "NSE:HDFCLIFE": {"exchange": "NSE", "tradingsymbol": "HDFCLIFE-EQ", "symboltoken": "467"},
        "NSE:BRITANNIA": {"exchange": "NSE", "tradingsymbol": "BRITANNIA-EQ", "symboltoken": "547"},
        "NSE:HEROMOTOCO": {"exchange": "NSE", "tradingsymbol": "HEROMOTOCO-EQ", "symboltoken": "1348"},
        "NSE:EICHERMOT": {"exchange": "NSE", "tradingsymbol": "EICHERMOT-EQ", "symboltoken": "910"},
        "NSE:BPCL": {"exchange": "NSE", "tradingsymbol": "BPCL-EQ", "symboltoken": "526"},
        "NSE:ONGC": {"exchange": "NSE", "tradingsymbol": "ONGC-EQ", "symboltoken": "2475"},
        "NSE:HINDALCO": {"exchange": "NSE", "tradingsymbol": "HINDALCO-EQ", "symboltoken": "1363"},
        "NSE:ADANIENT": {"exchange": "NSE", "tradingsymbol": "ADANIENT-EQ", "symboltoken": "25"},
        "NSE:NIFTY": {"exchange": "NSE", "tradingsymbol": "Nifty 50", "symboltoken": "99926000"},
        "NSE:BANKNIFTY": {"exchange": "NSE", "tradingsymbol": "Nifty Bank", "symboltoken": "99926009"},
    }

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

    def __init__(self):
        self.api_key = os.getenv("ANGEL_API_KEY", "").strip()
        self.client_id = os.getenv("ANGEL_CLIENT_ID", "").strip()
        self.pin = os.getenv("ANGEL_PIN", "").strip()
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET", "").strip()

        self.jwt_token = None
        self.refresh_token = None
        self.feed_token = None

    def _env_status(self):
        return {
            "api_key_present": bool(self.api_key),
            "client_code_present": bool(self.client_id),
            "password_present": bool(self.pin),
            "totp_secret_present": bool(self.totp_secret),
            "smartapi_module_present": False,
            "smartapi_import_error": "SDK not used. Requests-based integration active.",
        }

    def _get_local_ip(self):
        try:
            return socket.gethostbyname(socket.gethostname()) or "127.0.0.1"
        except Exception:
            return "127.0.0.1"

    def _get_public_ip(self):
        try:
            response = requests.get("https://api.ipify.org", timeout=5)
            response.raise_for_status()
            return response.text.strip()
        except Exception:
            return "127.0.0.1"

    def _headers(self, auth_required=False):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": self._get_local_ip(),
            "X-ClientPublicIP": self._get_public_ip(),
            "X-MACAddress": "02:00:00:00:00:00",
            "X-PrivateKey": self.api_key,
        }
        if auth_required and self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        return headers

    def _generate_totp(self):
        return pyotp.TOTP(self.totp_secret).now()

    def login(self):
        if not all([self.api_key, self.client_id, self.pin, self.totp_secret]):
            return {
                "status": False,
                "message": "Angel credentials missing in .env file.",
                "env_status": self._env_status(),
            }

        if self.api_key.startswith("http://") or self.api_key.startswith("https://"):
            return {
                "status": False,
                "message": "ANGEL_API_KEY is invalid. Put actual SmartAPI API key, not URL.",
                "env_status": self._env_status(),
            }

        login_url = f"{self.BASE_URL}/rest/auth/angelbroking/user/v1/loginByPassword"
        payload = {
            "clientcode": self.client_id,
            "password": self.pin,
            "totp": self._generate_totp(),
        }

        try:
            response = requests.post(
                login_url,
                json=payload,
                headers=self._headers(auth_required=False),
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return {
                "status": False,
                "message": f"Angel login request failed: {str(exc)}",
                "env_status": self._env_status(),
            }

        if not data.get("status"):
            return {
                "status": False,
                "message": data.get("message", "Angel login failed."),
                "env_status": self._env_status(),
            }

        token_data = data.get("data", {})
        self.jwt_token = token_data.get("jwtToken")
        self.refresh_token = token_data.get("refreshToken")
        self.feed_token = token_data.get("feedToken")

        return {
            "status": bool(self.jwt_token),
            "message": "Angel One login successful." if self.jwt_token else "JWT token missing in login response.",
            "env_status": self._env_status(),
        }

    def connect(self):
        return self.login()

    def get_symbol_config(self, symbol):
        return self.SYMBOL_TOKEN_MAP.get(symbol)

    def _market_close_datetime(self, current_dt):
        return current_dt.replace(hour=15, minute=30, second=0, microsecond=0)

    def get_from_to(self, interval):
        now = timezone.localtime()
        market_close_today = self._market_close_datetime(now)

        if interval == "1":
            from_dt = now - timedelta(days=2)
            to_dt = now
        elif interval in ["3", "5", "15"]:
            from_dt = now - timedelta(days=10)
            to_dt = now
        elif interval in ["30", "60"]:
            from_dt = now - timedelta(days=30)
            to_dt = now
        elif interval == "D":
            from_dt = (now - timedelta(days=365)).replace(hour=9, minute=15, second=0, microsecond=0)
            to_dt = market_close_today
        elif interval == "W":
            from_dt = (now - timedelta(days=365 * 3)).replace(hour=9, minute=15, second=0, microsecond=0)
            to_dt = market_close_today
        else:
            from_dt = now - timedelta(days=10)
            to_dt = now

        return from_dt, to_dt

    def _parse_candle_time(self, candle_time):
        if "T" in candle_time:
            dt = datetime.fromisoformat(candle_time.replace("Z", "+00:00"))
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            else:
                dt = timezone.localtime(dt)
            return dt

        naive_dt = datetime.strptime(candle_time, "%Y-%m-%d %H:%M")
        return timezone.make_aware(naive_dt, timezone.get_current_timezone())

    def fetch_historical_candles(self, symbol, interval):
        broker_status = self.login()
        if not broker_status.get("status"):
            return {
                "status": False,
                "message": broker_status.get("message", "Broker connection failed."),
                "candles": [],
                "meta": {},
            }

        symbol_config = self.get_symbol_config(symbol)
        if not symbol_config:
            return {
                "status": False,
                "message": f"Symbol mapping not found for {symbol}.",
                "candles": [],
                "meta": {},
            }

        angel_interval = self.INTERVAL_MAP.get(interval)
        if not angel_interval:
            return {
                "status": False,
                "message": f"Interval mapping not found for {interval}.",
                "candles": [],
                "meta": {},
            }

        from_dt, to_dt = self.get_from_to(interval)

        payload = {
            "exchange": symbol_config["exchange"],
            "symboltoken": symbol_config["symboltoken"],
            "interval": angel_interval,
            "fromdate": from_dt.strftime("%Y-%m-%d %H:%M"),
            "todate": to_dt.strftime("%Y-%m-%d %H:%M"),
        }

        url = f"{self.BASE_URL}/rest/secure/angelbroking/historical/v1/getCandleData"

        try:
            response = requests.post(
                url,
                json=payload,
                headers=self._headers(auth_required=True),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return {
                "status": False,
                "message": f"Candle API failed: {str(exc)}",
                "candles": [],
                "meta": {
                    "payload": payload,
                },
            }

        if not data.get("status"):
            return {
                "status": False,
                "message": data.get("message", "Historical candle API failed."),
                "candles": [],
                "meta": {
                    "payload": payload,
                    "raw_response": data,
                },
            }

        raw_candles = data.get("data", []) or []
        parsed = []

        for row in raw_candles:
            try:
                dt = self._parse_candle_time(row[0])
                parsed.append({
                    "time": int(dt.timestamp()),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                })
            except Exception:
                continue

        parsed.sort(key=lambda x: x["time"])

        deduped = []
        seen = set()
        for item in parsed:
            if item["time"] in seen:
                continue
            seen.add(item["time"])
            deduped.append(item)

        return {
            "status": True,
            "message": "Historical candles fetched successfully.",
            "candles": deduped,
            "meta": {
                "payload": payload,
                "records": len(deduped),
                "symboltoken": symbol_config["symboltoken"],
                "tradingsymbol": symbol_config["tradingsymbol"],
            },
        }

    def get_mock_candles(self, symbol=None, interval=None):
        return self.fetch_historical_candles(symbol=symbol, interval=interval)