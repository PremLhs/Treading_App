import csv
import os
from datetime import datetime
from typing import Dict, List, Tuple


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE_PATH = os.path.join(BASE_DIR, "data", "red_ball.csv")


def _safe_int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _format_date(date_str: str) -> str:
    if not date_str:
        return "-"
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d").strftime("%b %d, %Y")
    except ValueError:
        return date_str


def load_red_ball_data(csv_path: str = CSV_FILE_PATH) -> Tuple[List[Dict], int, int]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Red Ball CSV file not found: {csv_path}")

    rows: List[Dict] = []
    years = set()

    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {"Date", "Day", "Month", "Year", "Weekday", "Time"}

        if not reader.fieldnames:
            raise ValueError("Red Ball CSV file is empty or invalid.")

        normalized_headers = {header.strip() for header in reader.fieldnames}
        missing_columns = required_columns - normalized_headers
        if missing_columns:
            raise ValueError(f"Missing required columns in Red Ball CSV: {', '.join(sorted(missing_columns))}")

        for raw in reader:
            year = _safe_int(raw.get("Year"))
            if year is None:
                continue

            years.add(year)

            raw_date = (raw.get("Date") or "").strip()
            rows.append({
                "date": _format_date(raw_date),
                "day": (raw.get("Day") or "").strip() or "-",
                "month": (raw.get("Month") or "").strip() or "-",
                "year": year,
                "weekday": (raw.get("Weekday") or "").strip() or "-",
                "time": (raw.get("Time") or "").strip() or "-",
                "sort_date": raw_date,
            })

    if not rows:
        raise ValueError("No valid Red Ball records found in CSV.")

    rows.sort(key=lambda item: (item["year"], item["sort_date"]))

    min_year = min(years)
    max_year = max(years)
    return rows, min_year, max_year


def get_red_ball_data_by_year(year: int, csv_path: str = CSV_FILE_PATH) -> Dict:
    all_rows, min_year, max_year = load_red_ball_data(csv_path=csv_path)

    filtered_rows = [row for row in all_rows if row["year"] == year]

    cleaned_rows = []
    for row in filtered_rows:
        cleaned_rows.append({
            "date": row["date"],
            "day": row["day"],
            "month": row["month"],
            "year": row["year"],
            "weekday": row["weekday"],
            "time": row["time"],
        })

    return {
        "year": year,
        "rows": cleaned_rows,
        "total_records": len(cleaned_rows),
        "min_year": min_year,
        "max_year": max_year,
    }