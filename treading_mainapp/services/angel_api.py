import os
import pyotp

SMARTAPI_IMPORT_ERROR = None
SmartConnect = None

try:
    from smartapi import SmartConnect as ImportedSmartConnect
    SmartConnect = ImportedSmartConnect
except Exception as e1:
    try:
        from SmartApi.smartConnect import SmartConnect as ImportedSmartConnect
        SmartConnect = ImportedSmartConnect
    except Exception as e2:
        SMARTAPI_IMPORT_ERROR = f"smartapi import failed: {e1} | SmartApi import failed: {e2}"


class AngelBroker:
    def __init__(self):
        self.api_key = os.getenv("ANGEL_API_KEY", "").strip()
        self.client_code = os.getenv("ANGEL_CLIENT_ID", "").strip()
        self.password = os.getenv("ANGEL_PIN", "").strip()
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET", "").strip()

    def env_status(self):
        return {
            "api_key_present": bool(self.api_key),
            "client_code_present": bool(self.client_code),
            "password_present": bool(self.password),
            "totp_secret_present": bool(self.totp_secret),
            "smartapi_module_present": SmartConnect is not None,
            "smartapi_import_error": SMARTAPI_IMPORT_ERROR,
        }

    def is_configured(self):
        status = self.env_status()
        return all([
            status["api_key_present"],
            status["client_code_present"],
            status["password_present"],
            status["totp_secret_present"],
            status["smartapi_module_present"],
        ])

    def connect(self):
        if not self.is_configured():
            return {
                "status": False,
                "message": "Angel API credentials or SmartAPI module not configured properly.",
                "env_status": self.env_status(),
            }

        try:
            smart = SmartConnect(api_key=self.api_key)
            totp = pyotp.TOTP(self.totp_secret).now()
            data = smart.generateSession(self.client_code, self.password, totp)

            if data and data.get("status") is True:
                return {
                    "status": True,
                    "message": "Broker connected successfully.",
                    "env_status": self.env_status(),
                    "data": data,
                }

            return {
                "status": False,
                "message": data.get("message", "Broker connection failed."),
                "env_status": self.env_status(),
                "data": data,
            }

        except Exception as e:
            return {
                "status": False,
                "message": f"Broker exception: {str(e)}",
                "env_status": self.env_status(),
            }

    def get_mock_candles(self, symbol="NSE:HDFCBANK", interval="5"):
        base_time = 1718000000
        candles = []
        price = 1650.0

        for i in range(120):
            open_price = price
            high_price = open_price + 8 + (i % 3)
            low_price = open_price - 6 - (i % 2)
            close_price = open_price + ((i % 5) - 2) * 2
            volume = 1000 + (i * 17)

            candles.append({
                "time": base_time + i * 300,
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": volume,
            })
            price = close_price

        return candles