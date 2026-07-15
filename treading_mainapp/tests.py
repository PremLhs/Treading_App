from datetime import datetime
from unittest.mock import patch

from django.test import SimpleTestCase

from .notification import _build_notification_item, sync_notifications_to_session
from .services.nifty50_loader import get_dashboard_symbols, get_nifty50_data, get_nifty50_symbols, get_symbol_token_map
from .views import build_calendar_events


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

    def test_loader_includes_amavasya_chart_symbols(self):
        symbols = get_dashboard_symbols()
        token_map = get_symbol_token_map()

        self.assertIn("NSE:AARTIIND", symbols)
        self.assertIn("NSE:AARTIIND", token_map)
        self.assertEqual(token_map["NSE:AARTIIND"]["tradingsymbol"], "AARTIIND-EQ")


class CalendarEventTests(SimpleTestCase):
    def test_calendar_includes_pentagon_and_red_ball_events(self):
        events = build_calendar_events()
        event_types = {event["extendedProps"]["eventType"] for event in events}

        self.assertIn("pentagon", event_types)
        self.assertIn("red_ball", event_types)

        pentagon_event = next(event for event in events if event["extendedProps"]["eventType"] == "pentagon")
        red_ball_event = next(event for event in events if event["extendedProps"]["eventType"] == "red_ball")

        self.assertEqual(pentagon_event["backgroundColor"], "#f472b6")
        self.assertEqual(pentagon_event["extendedProps"]["symbol"], "⬟")
        self.assertEqual(red_ball_event["backgroundColor"], "#ef4444")
        self.assertEqual(red_ball_event["extendedProps"]["symbol"], "●")


class NotificationSyncTests(SimpleTestCase):
    class DummySession(dict):
        def __init__(self):
            super().__init__()
            self.modified = False

    class DummyRequest:
        def __init__(self):
            self.session = NotificationSyncTests.DummySession()

    def _make_request(self):
        return self.DummyRequest()

    def test_today_and_upcoming_alerts_use_same_notification_id(self):
        event_row = {
            "title": "Amavasya",
            "month": "July",
            "year": "2026",
            "paksha": "",
            "start_dt": datetime(2026, 7, 10, 10, 0),
            "end_dt": None,
            "page_url": "/dark-day/",
            "color_class": "notification-danger",
            "event_key": "amavasya",
            "base_title": "Amavasya",
        }

        upcoming_item = _build_notification_item(event_row, "upcoming")
        today_item = _build_notification_item(event_row, "today")

        self.assertEqual(upcoming_item["id"], today_item["id"])

    def test_sync_reopens_notification_for_event_day(self):
        event_row = {
            "title": "Amavasya",
            "month": "July",
            "year": "2026",
            "paksha": "",
            "start_dt": datetime(2026, 7, 10, 10, 0),
            "end_dt": None,
            "page_url": "/dark-day/",
            "color_class": "notification-danger",
            "event_key": "amavasya",
            "base_title": "Amavasya",
        }

        upcoming_item = _build_notification_item(event_row, "upcoming")
        today_item = _build_notification_item(event_row, "today")

        request = self._make_request()
        request.session["notification_inbox"] = [{**upcoming_item, "read": True, "popup_shown": True}]

        with patch("treading_mainapp.notification.get_event_notifications", return_value=[today_item]):
            updated_inbox = sync_notifications_to_session(request)

        self.assertEqual(len(updated_inbox), 1)
        self.assertEqual(updated_inbox[0]["id"], today_item["id"])
        self.assertEqual(updated_inbox[0]["type"], "today")
        self.assertFalse(updated_inbox[0].get("read", True))
        self.assertFalse(updated_inbox[0].get("popup_shown", True))

    def test_loads_moon_mars_events_from_csv(self):
        from .notification import _load_event_rows

        config = {
            "key": "moon_marse",
            "title": "Top/Bottom Days",
            "file_path": __import__("pathlib").Path(__file__).resolve().parent / "data" / "moon_marse.csv",
            "page_url": "/top-bottom/",
            "color_class": "notification-primary",
            "required_columns": {"year", "month", "title", "start", "end"},
        }

        rows = _load_event_rows(config)

        self.assertTrue(rows)
        self.assertTrue(any(row["event_key"] == "moon_marse" for row in rows))
        self.assertTrue(any(row["start_dt"].date().day == 10 and row["start_dt"].year == 2026 for row in rows))
