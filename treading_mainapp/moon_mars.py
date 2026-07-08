from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


DATE_INPUT_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


@dataclass
class MoonMarsEvent:
    year: int
    month: str
    title: str
    start: datetime
    end: Optional[datetime]
    start_display: str
    end_display: str
    duration_hours: Optional[float]


def _parse_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None

    cleaned = str(value).strip().replace('"', "")
    if not cleaned:
        return None

    for fmt in DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue

    return None


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _resolve_csv_path(csv_file: Optional[str] = None) -> Path:
    if csv_file:
        path = Path(csv_file)
        if path.exists():
            return path

    default_paths = [
        Path(__file__).resolve().parent / "data" / "moon_marse.csv",
        Path(__file__).resolve().parent / "moon_marse.csv",
    ]

    for path in default_paths:
        if path.exists():
            return path

    raise FileNotFoundError(
        "moon_marse.csv file not found. Place it in app/data/moon_marse.csv or app/moon_marse.csv."
    )


def load_moon_mars_events(csv_file: Optional[str] = None) -> List[MoonMarsEvent]:
    csv_path = _resolve_csv_path(csv_file)
    events: List[MoonMarsEvent] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
        reader = csv.DictReader(file_obj)

        for row in reader:
            year = _safe_int(row.get("year"))
            month = (row.get("month") or "").strip()
            title = (row.get("title") or "-").strip()

            start_dt = _parse_datetime(row.get("start", ""))
            end_dt = _parse_datetime(row.get("end", ""))

            if not year and start_dt:
                year = start_dt.year

            if not start_dt:
                continue

            duration_hours = None
            if end_dt:
                duration_hours = round((end_dt - start_dt).total_seconds() / 3600, 2)

            events.append(
                MoonMarsEvent(
                    year=year or start_dt.year,
                    month=month or start_dt.strftime("%B"),
                    title=title,
                    start=start_dt,
                    end=end_dt,
                    start_display=start_dt.strftime("%d %b %Y, %I:%M %p"),
                    end_display=end_dt.strftime("%d %b %Y, %I:%M %p") if end_dt else "TBA",
                    duration_hours=duration_hours,
                )
            )

    events.sort(key=lambda item: item.start)
    return events


def get_available_years(events: Optional[List[MoonMarsEvent]] = None, csv_file: Optional[str] = None) -> List[int]:
    event_list = events if events is not None else load_moon_mars_events(csv_file=csv_file)
    years = sorted({item.year for item in event_list if item.year})
    return years


def get_moon_mars_events_by_year(selected_year: Optional[int] = None, csv_file: Optional[str] = None) -> Dict[str, Any]:
    events = load_moon_mars_events(csv_file=csv_file)
    years = get_available_years(events=events)

    if not years:
        return {
            "selected_year": None,
            "available_years": [],
            "events": [],
            "total_events": 0,
        }

    if selected_year is None:
        selected_year = years[0]

    filtered = [item for item in events if item.year == selected_year]

    return {
        "selected_year": selected_year,
        "available_years": years,
        "events": [asdict(item) for item in filtered],
        "total_events": len(filtered),
    }