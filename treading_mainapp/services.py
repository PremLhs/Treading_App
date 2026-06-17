import os
import pyotp

try:
    from SmartApi import SmartConnect
except Exception:
    SmartConnect = None


class AngelSmartAPIService:
    def __init__(self):
        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_id = os.getenv("ANGEL_CLIENT_ID")
        self.password = os.getenv("ANGEL_PASSWORD")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")
        self.client = SmartConnect(api_key=self.api_key) if SmartConnect and self.api_key else None

    def generate_totp(self):
        if not self.totp_secret:
            return None
        return pyotp.TOTP(self.totp_secret).now()

    def create_session(self):
        if not self.client:
            return {"status": False, "message": "SmartAPI client not configured."}

        try:
            totp = self.generate_totp()
            response = self.client.generateSession(self.client_id, self.password, totp)
            return {"status": True, "data": response}
        except Exception as e:
            return {"status": False, "message": str(e)}

    def get_profile(self, refresh_token):
        try:
            return self.client.getProfile(refresh_token)
        except Exception as e:
            return {"status": False, "message": str(e)}

    def get_ltp_data(self, exchange="NSE", tradingsymbol="SBIN-EQ", symboltoken="3045"):
        try:
            return self.client.ltpData(exchange, tradingsymbol, symboltoken)
        except Exception as e:
            return {"status": False, "message": str(e)}

    def place_order(self, order_data):
        try:
            return self.client.placeOrder(order_data)
        except Exception as e:
            return {"status": False, "message": str(e)}