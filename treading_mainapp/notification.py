import csv
from pathlib import Path
from datetime import datetime, timedelta


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"


EVENT_CONFIGS = [
    {
        "key": "amavasya",
        "title": "Amavasya",
        "file_path": DATA_DIR / "amavasya.csv",
        "page_url": "/amavasya/",
        "color_class": "notification-danger",
        "required_columns": {"year", "month", "title", "start", "end"},
    },
    {
        "key": "purnima",
        "title": "Purnima",
        "file_path": DATA_DIR / "purnima.csv",
        "page_url": "/purnima/",
        "color_class": "notification-info",
        "required_columns": {"year", "month", "title", "start", "end"},
    },
    {
        "key": "trayodashi",
        "title": "Trayodashi",
        "file_path": DATA_DIR / "trayodashi.csv",
        "page_url": "/trayodashi/",
        "color_class": "notification-warning",
        "required_columns": {"year", "month", "paksha", "title", "start", "end"},
    },
    {
        "key": "pushya",
        "title": "Pushya Nakshatra",
        "file_path": DATA_DIR / "pushya.csv",
        "page_url": "/pushya/",
        "color_class": "notification-success",
        "required_columns": {"year", "month", "title", "start", "end"},
    },
]


def _safe_parse_datetime(value):
    value = str(value or "").strip()
    if not value:
        return None

    formats = [
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def _safe_parse_date(value):
    value = str(value or "").strip()
    if not value:
        return None

    formats = [
        "%d-%m-%Y",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    return None


def _load_event_rows(config):
    rows = []
    file_path = config["file_path"]

    if not file_path.exists():
        return rows

    with open(file_path, mode="r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            return rows

        fieldnames = set(reader.fieldnames)
        if not config["required_columns"].issubset(fieldnames):
            return rows

        for row in reader:
            start_raw = str(row.get("start", "")).strip()
            end_raw = str(row.get("end", "")).strip()
            title = str(row.get("title", "")).strip() or config["title"]
            month = str(row.get("month", "")).strip()
            year = str(row.get("year", "")).strip()
            paksha = str(row.get("paksha", "")).strip()

            start_dt = _safe_parse_datetime(start_raw)
            end_dt = _safe_parse_datetime(end_raw)

            if not start_dt:
                continue

            rows.append({
                "title": title,
                "month": month,
                "year": year,
                "paksha": paksha,
                "start_raw": start_raw,
                "end_raw": end_raw,
                "start_dt": start_dt,
                "end_dt": end_dt,
                "page_url": config["page_url"],
                "color_class": config["color_class"],
                "event_key": config["key"],
                "base_title": config["title"],
            })

    return rows


def _load_reversal_rows():
    rows = []
    seen_keys = set()

    try:
        from .views import generate_reversal_rows
    except Exception:
        return rows

    current_year = datetime.now().year
    candidate_years = [current_year - 1, current_year, current_year + 1]

    for year in candidate_years:
        try:
            reversal_data = generate_reversal_rows(year)
        except Exception:
            continue

        for item in reversal_data.get("rows", []):
            reversal_date_raw = str(item.get("reversal_date", "")).strip()
            degree = str(item.get("degree", "")).strip()
            elapsed_days = str(item.get("elapsed_days", "")).strip()
            calculated_degree = str(item.get("calculated_degree", "")).strip()

            if not reversal_date_raw or reversal_date_raw == "-":
                continue

            reversal_date = _safe_parse_date(reversal_date_raw)
            if not reversal_date:
                continue

            unique_key = f"{reversal_date.isoformat()}-{degree}"
            if unique_key in seen_keys:
                continue
            seen_keys.add(unique_key)

            start_dt = datetime.combine(reversal_date, datetime.min.time())

            rows.append({
                "title": "Reversal Date",
                "month": start_dt.strftime("%B"),
                "year": str(start_dt.year),
                "paksha": "",
                "start_raw": reversal_date_raw,
                "end_raw": "",
                "start_dt": start_dt,
                "end_dt": None,
                "page_url": "/reversal-dates/",
                "color_class": "notification-primary",
                "event_key": "reversal",
                "base_title": "Reversal Date",
                "degree": degree,
                "elapsed_days": elapsed_days,
                "calculated_degree": calculated_degree,
            })

    return rows


def _build_notification_item(event_row, alert_type):
    start_dt = event_row["start_dt"]
    event_date = start_dt.date()
    readable_start = start_dt.strftime("%d %b %Y, %I:%M %p")

    subtitle_parts = [readable_start]

    if event_row.get("month"):
        subtitle_parts.append(event_row["month"])

    if event_row.get("paksha"):
        subtitle_parts.append(event_row["paksha"])

    if event_row.get("event_key") == "reversal" and event_row.get("degree"):
        subtitle_parts.append(f"Level {event_row['degree']}°")

    subtitle = " • ".join(subtitle_parts)

    if alert_type == "today":
        message = f"{event_row['title']} is today."
        label = "Live Event Alert"
        sort_order = 0
    else:
        message = f"Tomorrow is {event_row['title']}."
        label = "Upcoming Event Alert"
        sort_order = 1

    notification_id = f"{event_row['event_key']}-{event_date.isoformat()}-{alert_type}"

    if event_row.get("event_key") == "reversal" and event_row.get("degree"):
        notification_id = f"{event_row['event_key']}-{event_date.isoformat()}-{event_row['degree']}-{alert_type}"

    return {
        "id": notification_id,
        "type": alert_type,
        "label": label,
        "message": message,
        "submessage": subtitle,
        "page_url": event_row["page_url"],
        "color_class": event_row["color_class"],
        "event_date": event_date.isoformat(),
        "event_time": start_dt.isoformat(),
        "sort_order": sort_order,
        "created_on": datetime.now().isoformat(),
    }


def get_event_notifications():
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)

    notifications = []

    for config in EVENT_CONFIGS:
        rows = _load_event_rows(config)

        for event_row in rows:
            event_date = event_row["start_dt"].date()

            if event_date == today:
                notifications.append(_build_notification_item(event_row, "today"))

            if event_date == tomorrow:
                notifications.append(_build_notification_item(event_row, "upcoming"))

    reversal_rows = _load_reversal_rows()

    for event_row in reversal_rows:
        event_date = event_row["start_dt"].date()

        if event_date == today:
            notifications.append(_build_notification_item(event_row, "today"))

        if event_date == tomorrow:
            notifications.append(_build_notification_item(event_row, "upcoming"))

    notifications.sort(key=lambda item: (item["sort_order"], item["event_time"]))
    return notifications


def sync_notifications_to_session(request):
    active_notifications = get_event_notifications()
    active_ids = {item["id"] for item in active_notifications}

    inbox = request.session.get("notification_inbox", [])
    inbox_map = {
        item["id"]: item
        for item in inbox
        if item.get("id") in active_ids
    }

    for item in active_notifications:
        existing_item = inbox_map.get(item["id"])

        if existing_item:
            inbox_map[item["id"]] = {
                **existing_item,
                **item,
                "read": existing_item.get("read", False),
                "popup_shown": existing_item.get("popup_shown", False),
            }
        else:
            inbox_map[item["id"]] = {
                **item,
                "read": False,
                "popup_shown": False,
            }

    updated_inbox = sorted(
        inbox_map.values(),
        key=lambda item: (
            item.get("read", False),
            item.get("sort_order", 99),
            item.get("event_time", ""),
        ),
    )

    request.session["notification_inbox"] = updated_inbox
    request.session.modified = True

    return updated_inbox

def get_unread_popup_notifications(request):
    inbox = sync_notifications_to_session(request)
    return [item for item in inbox if not item.get("popup_shown", False)]


def get_notification_context(request):
    inbox = sync_notifications_to_session(request)
    unread_count = len([item for item in inbox if not item.get("read", False)])
    popup_notifications = [item for item in inbox if not item.get("popup_shown", False)]

    return {
        "global_notifications": inbox,
        "popup_notifications": popup_notifications,
        "notification_unread_count": unread_count,
    }