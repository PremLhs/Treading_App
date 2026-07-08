from django.test import SimpleTestCase

from .services.nifty50_loader import get_nifty50_data, get_nifty50_symbols, get_symbol_token_map


class Nifty50ConfigTests(SimpleTestCase):
    def test_loader_reads_master_json(self):
        data = get_nifty50_data()

        self.assertIn("symbols", data)
        self.assertTrue(data["symbols"])

        symbols = get_nifty50_symbols()
        self.assertTrue(symbols)
        self.assertIn("NSE:RELIANCE", symbols)
        self.assertNotIn("NSE:NIFTY", symbols)
        self.assertNotIn("NSE:BANKNIFTY", symbols)

        token_map = get_symbol_token_map()
        self.assertIn("NSE:RELIANCE", token_map)
        self.assertIn("NSE:NIFTY", token_map)
        self.assertIn("NSE:BANKNIFTY", token_map)
