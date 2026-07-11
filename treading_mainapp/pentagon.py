import csv
import os
from datetime import datetime
from typing import List, Dict, Tuple


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE_PATH = os.path.join(BASE_DIR, "data", "Pentagon.csv")


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


def load_pentagon_data(csv_path: str = CSV_FILE_PATH) -> Tuple[List[Dict], int, int]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Pentagon CSV file not found: {csv_path}")

    rows = []
    years = set()

    with open(csv_path, mode="r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {
            "Year",
            "Start Date",
            "Start Weekday",
            "Start Time",
            "End Date",
            "End Weekday",
            "End Time",
        }

        if not reader.fieldnames:
            raise ValueError("Pentagon CSV file is empty or invalid.")

        normalized_headers = {header.strip() for header in reader.fieldnames}
        missing_columns = required_columns - normalized_headers
        if missing_columns:
            raise ValueError(f"Missing required columns in Pentagon CSV: {', '.join(sorted(missing_columns))}")

        for raw in reader:
            year = _safe_int(raw.get("Year"))
            if year is None:
                continue

            years.add(year)

            rows.append({
                "year": year,
                "start_date": _format_date(raw.get("Start Date", "").strip()),
                "start_weekday": raw.get("Start Weekday", "").strip() or "-",
                "start_time": raw.get("Start Time", "").strip() or "-",
                "end_date": _format_date(raw.get("End Date", "").strip()),
                "end_weekday": raw.get("End Weekday", "").strip() or "-",
                "end_time": raw.get("End Time", "").strip() or "-",
                "sort_start_date": raw.get("Start Date", "").strip(),
            })

    if not rows:
        raise ValueError("No valid Pentagon records found in CSV.")

    rows.sort(key=lambda item: (item["year"], item["sort_start_date"]))

    min_year = min(years)
    max_year = max(years)
    return rows, min_year, max_year


def get_pentagon_data_by_year(year: int, csv_path: str = CSV_FILE_PATH) -> Dict:
    all_rows, min_year, max_year = load_pentagon_data(csv_path=csv_path)

    filtered_rows = [row for row in all_rows if row["year"] == year]

    cleaned_rows = []
    for row in filtered_rows:
        cleaned_rows.append({
            "start_date": row["start_date"],
            "start_weekday": row["start_weekday"],
            "start_time": row["start_time"],
            "end_date": row["end_date"],
            "end_weekday": row["end_weekday"],
            "end_time": row["end_time"],
        })

    return {
        "year": year,
        "rows": cleaned_rows,
        "total_records": len(cleaned_rows),
        "min_year": min_year,
        "max_year": max_year,
    }