from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .forms import LoginForm
from .services.angel_api import AngelBroker

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import GapUpStatus
import treading_mainapp.gapup

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .moon_mars import get_moon_mars_events_by_year

INDEX_SYMBOLS = [
    "NSE:NIFTY",
    "NSE:BANKNIFTY",
]

STOCK_SYMBOLS = [
    "NSE:RELIANCE",
    "NSE:TCS",
    "NSE:HDFCBANK",
    "NSE:ICICIBANK",
    "NSE:INFY",
    "NSE:BHARTIARTL",
    "NSE:ITC",
    "NSE:SBIN",
    "NSE:LT",
    "NSE:HINDUNILVR",
    "NSE:AXISBANK",
    "NSE:KOTAKBANK",
    "NSE:BAJFINANCE",
    "NSE:M&M",
    "NSE:MARUTI",
    "NSE:SUNPHARMA",
    "NSE:NTPC",
    "NSE:POWERGRID",
    "NSE:ULTRACEMCO",
    "NSE:TITAN",
    "NSE:ASIANPAINT",
    "NSE:ADANIPORTS",
    "NSE:BAJAJFINSV",
    "NSE:NESTLEIND",
    "NSE:WIPRO",
    "NSE:TECHM",
    "NSE:HCLTECH",
    "NSE:INDUSINDBK",
    "NSE:TATAMOTORS",
    "NSE:ETERNAL",
    "NSE:TRENT",
    "NSE:SHRIRAMFIN",
    "NSE:BEL",
    "NSE:COALINDIA",
    "NSE:JSWSTEEL",
    "NSE:TATASTEEL",
    "NSE:GRASIM",
    "NSE:DRREDDY",
    "NSE:CIPLA",
    "NSE:APOLLOHOSP",
    "NSE:SBILIFE",
    "NSE:HDFCLIFE",
    "NSE:BRITANNIA",
    "NSE:HEROMOTOCO",
    "NSE:EICHERMOT",
    "NSE:BPCL",
    "NSE:ONGC",
    "NSE:HINDALCO",
    "NSE:ADANIENT",
]

DEFAULT_SYMBOL = "NSE:RELIANCE"
ALLOWED_INTERVALS = ["1", "3", "5", "15", "30", "60", "D", "W"]


REVERSAL_LEVELS = [
    11.25, 22.50, 33.75, 45.00, 56.25, 60.00, 67.50, 78.75,
    90.00, 101.25, 112.50, 120.00, 123.75, 135.00, 146.25,
    157.50, 168.75, 180.00, 191.25, 202.50, 213.75, 225.00,
    236.25, 240.00, 247.50, 258.75, 270.00, 281.25, 292.50,
    300.00, 303.75, 315.00, 326.25, 337.50, 348.75, 360.00
]



def home_redirect(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    form = LoginForm(request=request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("dashboard")

    return render(request, "auth/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")

@login_required
def dashboard_view(request):
    symbol = request.GET.get("symbol", DEFAULT_SYMBOL).strip()
    interval = request.GET.get("interval", "5").strip().upper()

    all_symbols = INDEX_SYMBOLS + STOCK_SYMBOLS

    if symbol not in all_symbols:
        symbol = DEFAULT_SYMBOL

    if interval not in ALLOWED_INTERVALS:
        interval = "5"

    broker = AngelBroker()
    broker_response = broker.connect()

    context = {
        "tv_symbol": symbol,
        "tv_interval": interval,
        "index_symbols": INDEX_SYMBOLS,
        "stock_symbols": STOCK_SYMBOLS,
        "default_symbol": DEFAULT_SYMBOL,
        "broker_connected": broker_response.get("status", False),
        "broker_message": broker_response.get("message", "Unknown broker state."),
        "env_status": broker_response.get("env_status", {}),
    }
    return render(request, "dashboard/chart.html", with_global_notifications(request, context))


@login_required
def broker_health_view(request):
    broker = AngelBroker()
    broker_response = broker.connect()
    return JsonResponse({
        "status": broker_response.get("status", False),
        "message": broker_response.get("message", ""),
        "env_status": broker_response.get("env_status", {}),
    })


@login_required
def candles_api_view(request):
    symbol = request.GET.get("symbol", DEFAULT_SYMBOL).strip()
    interval = request.GET.get("interval", "5").strip().upper()

    all_symbols = INDEX_SYMBOLS + STOCK_SYMBOLS

    if symbol not in all_symbols:
        symbol = DEFAULT_SYMBOL

    if interval not in ALLOWED_INTERVALS:
        interval = "5"

    broker = AngelBroker()
    result = broker.fetch_historical_candles(symbol=symbol, interval=interval)

    return JsonResponse({
        "status": result.get("status", False),
        "message": result.get("message", ""),
        "symbol": symbol,
        "interval": interval,
        "candles": result.get("candles", []),
        "meta": result.get("meta", {}),
    })


def is_leap_year(year: int) -> bool:
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def get_cycle_dates(year: int):
    start_date = date(year, 3, 20)
    end_date = date(year + 1, 3, 19)
    return start_date, end_date


def generate_reversal_rows(year: int):
    start_date, end_date = get_cycle_dates(year)

    actual_days = 366 if is_leap_year(year) else 365
    divisor_days = 366 if is_leap_year(year) else 365.25

    rows = []

    for level in REVERSAL_LEVELS:
        reversal_date = None
        elapsed_days_at_cross = None
        calculated_degree = None

        for day in range(1, actual_days + 1):
            yesterday_degree = ((day - 1) * 360) / divisor_days
            today_degree = (day * 360) / divisor_days

            if yesterday_degree < level <= today_degree:
                current_date = start_date + timedelta(days=day)
                reversal_date = current_date.strftime("%d-%m-%Y")
                elapsed_days_at_cross = day
                calculated_degree = round(today_degree, 6)
                break

        rows.append({
            "degree": f"{level:.2f}",
            "elapsed_days": elapsed_days_at_cross,
            "calculated_degree": f"{calculated_degree:.6f}" if calculated_degree is not None else "-",
            "reversal_date": reversal_date or "-",
        })

    return {
        "year": year,
        "start_date": start_date.strftime("%d-%m-%Y"),
        "end_date": end_date.strftime("%d-%m-%Y"),
        "total_days": actual_days,
        "divisor_days": divisor_days,
        "rows": rows,
    }


@login_required
def reversal_dates_view(request):
    from datetime import datetime

    current_year = datetime.now().year
    data = generate_reversal_rows(current_year)

    return render(request, "revesal.html", data)


@login_required
def reversal_dates_api_view(request):
    year_text = str(request.GET.get("year", "")).strip()

    if not year_text:
        return JsonResponse({
            "success": False,
            "message": "Year is required."
        }, status=400)

    if not year_text.isdigit():
        return JsonResponse({
            "success": False,
            "message": "Please enter a valid numeric year."
        }, status=400)

    year = int(year_text)

    if year < 1900 or year > 2100:
        return JsonResponse({
            "success": False,
            "message": "Year must be between 1900 and 2100."
        }, status=400)

    data = generate_reversal_rows(year)

    return JsonResponse({
        "success": True,
        "message": f"Reversal dates loaded for {year}.",
        "data": data
    })

############################ amavasya code ###########################################

import csv
from pathlib import Path

from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from datetime import datetime


BASE_DIR = Path(__file__).resolve().parent
AMAVASYA_CSV_PATH = BASE_DIR / "data" / "amavasya.csv"
DEFAULT_AMAVASYA_YEAR = 2026


def load_amavasya_data():
    data = {}

    if not AMAVASYA_CSV_PATH.exists():
        return data

    with open(AMAVASYA_CSV_PATH, mode="r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {"year", "month", "title", "start", "end"}
        if not reader.fieldnames or not required_columns.issubset(set(reader.fieldnames)):
            return data

        for row in reader:
            year_raw = str(row.get("year", "")).strip()
            month = str(row.get("month", "")).strip()
            title = str(row.get("title", "")).strip()
            start = str(row.get("start", "")).strip()
            end = str(row.get("end", "")).strip()

            if not year_raw or not month or not start or not end:
                continue

            try:
                year = int(year_raw)
            except ValueError:
                continue

            data.setdefault(year, []).append({
                "month": month,
                "title": title,
                "start": start,
                "end": end,
            })

    return data


def get_amavasya_year_bounds(amavasya_data):
    if not amavasya_data:
        return None, None

    years = sorted(amavasya_data.keys())
    return years[0], years[-1]


def get_valid_default_year(amavasya_data):
    if not amavasya_data:
        return DEFAULT_AMAVASYA_YEAR

    if DEFAULT_AMAVASYA_YEAR in amavasya_data:
        return DEFAULT_AMAVASYA_YEAR

    return sorted(amavasya_data.keys())[0]


def get_amavasya_year_data(year, amavasya_data=None):
    if amavasya_data is None:
        amavasya_data = load_amavasya_data()

    min_year, max_year = get_amavasya_year_bounds(amavasya_data)
    rows = amavasya_data.get(year, [])

    return {
        "year": year,
        "min_year": min_year,
        "max_year": max_year,
        "total_records": len(rows),
        "rows": rows,
    }


@login_required
def amavasya_view(request):
    amavasya_data = load_amavasya_data()

    if not amavasya_data:
        context = {
            "year": DEFAULT_AMAVASYA_YEAR,
            "min_year": None,
            "max_year": None,
            "total_records": 0,
            "rows": [],
            "error_message": f"amavasya.csv file not found or invalid at: {AMAVASYA_CSV_PATH}",
        }
        return render(request, "amavasya.html",  with_global_notifications(request, context))

    min_year, max_year = get_amavasya_year_bounds(amavasya_data)
    default_year = get_valid_default_year(amavasya_data)

    year = request.GET.get("year")

    try:
        year = int(year) if year else default_year
    except ValueError:
        year = default_year

    if year < min_year or year > max_year or year not in amavasya_data:
        year = default_year

    data = get_amavasya_year_data(year, amavasya_data)

    context = {
        "year": data["year"],
        "min_year": data["min_year"],
        "max_year": data["max_year"],
        "total_records": data["total_records"],
        "rows": data["rows"],
        "error_message": "",
    }
    return render(request, "amavasya.html", with_global_notifications(request, context))


@login_required
def amavasya_api_view(request):
    amavasya_data = load_amavasya_data()

    if not amavasya_data:
        return JsonResponse({
            "success": False,
            "message": f"amavasya.csv file not found or invalid at: {AMAVASYA_CSV_PATH}"
        }, status=500)

    min_year, max_year = get_amavasya_year_bounds(amavasya_data)

    year = request.GET.get("year")

    if not year:
        return JsonResponse({
            "success": False,
            "message": "Please enter a year."
        }, status=400)

    try:
        year = int(year)
    except ValueError:
        return JsonResponse({
            "success": False,
            "message": "Year must be a valid number."
        }, status=400)

    if year < min_year or year > max_year or year not in amavasya_data:
        return JsonResponse({
            "success": False,
            "message": f"Year must be between {min_year} and {max_year}, and data must exist in amavasya.csv."
        }, status=400)

    data = get_amavasya_year_data(year, amavasya_data)

    return JsonResponse({
        "success": True,
        "message": f"Amavasya data loaded for {year}.",
        "data": data
    })

########################### purnima code ##############################################

import csv
from pathlib import Path
from datetime import datetime

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"

PURNIMA_CSV_PATH = DATA_DIR / "purnima.csv"
DEFAULT_PURNIMA_YEAR = 2026


def load_purnima_data():
    data = {}

    if not PURNIMA_CSV_PATH.exists():
        return data

    with open(PURNIMA_CSV_PATH, mode="r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {"year", "month", "title", "start", "end"}
        if not reader.fieldnames or not required_columns.issubset(set(reader.fieldnames)):
            return data

        for row in reader:
            year_raw = str(row.get("year", "")).strip()
            month = str(row.get("month", "")).strip()
            title = str(row.get("title", "")).strip()
            start = str(row.get("start", "")).strip()
            end = str(row.get("end", "")).strip()

            if not year_raw or not month or not start or not end:
                continue

            try:
                year = int(year_raw)
            except ValueError:
                continue

            data.setdefault(year, []).append({
                "month": month,
                "title": title or "Purnima",
                "start": start,
                "end": end,
            })

    return data


def get_purnima_year_bounds(purnima_data):
    if not purnima_data:
        return None, None

    years = sorted(purnima_data.keys())
    return years[0], years[-1]


def get_valid_purnima_default_year(purnima_data):
    if not purnima_data:
        return DEFAULT_PURNIMA_YEAR

    if DEFAULT_PURNIMA_YEAR in purnima_data:
        return DEFAULT_PURNIMA_YEAR

    return sorted(purnima_data.keys())[0]


def get_purnima_year_data(year, purnima_data=None):
    if purnima_data is None:
        purnima_data = load_purnima_data()

    min_year, max_year = get_purnima_year_bounds(purnima_data)
    rows = purnima_data.get(year, [])

    return {
        "year": year,
        "min_year": min_year,
        "max_year": max_year,
        "total_records": len(rows),
        "rows": rows,
    }


@login_required
def purnima_view(request):
    purnima_data = load_purnima_data()

    if not purnima_data:
        context = {
            "year": DEFAULT_PURNIMA_YEAR,
            "min_year": None,
            "max_year": None,
            "total_records": 0,
            "rows": [],
            "error_message": f"purnima.csv file not found or invalid at: {PURNIMA_CSV_PATH}",
        }
        return render(request, "purnima.html", with_global_notifications(request, context))

    min_year, max_year = get_purnima_year_bounds(purnima_data)
    default_year = get_valid_purnima_default_year(purnima_data)

    year = request.GET.get("year")

    try:
        year = int(year) if year else default_year
    except ValueError:
        year = default_year

    if year < min_year or year > max_year or year not in purnima_data:
        year = default_year

    data = get_purnima_year_data(year, purnima_data)

    context = {
        "year": data["year"],
        "min_year": data["min_year"],
        "max_year": data["max_year"],
        "total_records": data["total_records"],
        "rows": data["rows"],
        "error_message": "",
    }
    return render(request, "purnima.html", with_global_notifications(request, context))


@login_required
def purnima_api_view(request):
    purnima_data = load_purnima_data()

    if not purnima_data:
        return JsonResponse({
            "success": False,
            "message": f"purnima.csv file not found or invalid at: {PURNIMA_CSV_PATH}"
        }, status=500)

    min_year, max_year = get_purnima_year_bounds(purnima_data)

    year = request.GET.get("year")

    if not year:
        return JsonResponse({
            "success": False,
            "message": "Please enter a year."
        }, status=400)

    try:
        year = int(year)
    except ValueError:
        return JsonResponse({
            "success": False,
            "message": "Year must be a valid number."
        }, status=400)

    if year < min_year or year > max_year or year not in purnima_data:
        return JsonResponse({
            "success": False,
            "message": f"Year must be between {min_year} and {max_year}, and data must exist in purnima.csv."
        }, status=400)

    data = get_purnima_year_data(year, purnima_data)

    return JsonResponse({
        "success": True,
        "message": f"Purnima data loaded for {year}.",
        "data": data
    })


import csv
from pathlib import Path

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"

TRAYODASHI_CSV_PATH = DATA_DIR / "trayodashi.csv"
DEFAULT_TRAYODASHI_YEAR = 2026


def load_trayodashi_data():
    data = {}

    if not TRAYODASHI_CSV_PATH.exists():
        return data

    with open(TRAYODASHI_CSV_PATH, mode="r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required_columns = {"year", "month", "paksha", "title", "start", "end"}
        if not reader.fieldnames or not required_columns.issubset(set(reader.fieldnames)):
            return data

        for row in reader:
            year_raw = str(row.get("year", "")).strip()
            month = str(row.get("month", "")).strip()
            paksha = str(row.get("paksha", "")).strip()
            title = str(row.get("title", "")).strip()
            start = str(row.get("start", "")).strip()
            end = str(row.get("end", "")).strip()

            if not year_raw or not month or not paksha or not start or not end:
                continue

            try:
                year = int(year_raw)
            except ValueError:
                continue

            data.setdefault(year, []).append({
                "month": month,
                "paksha": paksha,
                "title": title or "Trayodashi",
                "start": start,
                "end": end,
            })

    return data


def get_trayodashi_year_bounds(trayodashi_data):
    if not trayodashi_data:
        return None, None

    years = sorted(trayodashi_data.keys())
    return years[0], years[-1]


def get_valid_trayodashi_default_year(trayodashi_data):
    if not trayodashi_data:
        return DEFAULT_TRAYODASHI_YEAR

    if DEFAULT_TRAYODASHI_YEAR in trayodashi_data:
        return DEFAULT_TRAYODASHI_YEAR

    return sorted(trayodashi_data.keys())[0]


def get_trayodashi_year_data(year, trayodashi_data=None):
    if trayodashi_data is None:
        trayodashi_data = load_trayodashi_data()

    min_year, max_year = get_trayodashi_year_bounds(trayodashi_data)
    rows = trayodashi_data.get(year, [])

    return {
        "year": year,
        "min_year": min_year,
        "max_year": max_year,
        "total_records": len(rows),
        "rows": rows,
    }


@login_required
def trayodashi_view(request):
    trayodashi_data = load_trayodashi_data()

    if not trayodashi_data:
        context = {
            "year": DEFAULT_TRAYODASHI_YEAR,
            "min_year": None,
            "max_year": None,
            "total_records": 0,
            "rows": [],
            "error_message": f"trayodashi.csv file not found or invalid at: {TRAYODASHI_CSV_PATH}",
        }
        return render(request, "trayodashi.html", with_global_notifications(request, context))

    min_year, max_year = get_trayodashi_year_bounds(trayodashi_data)
    default_year = get_valid_trayodashi_default_year(trayodashi_data)

    year = request.GET.get("year")

    try:
        year = int(year) if year else default_year
    except ValueError:
        year = default_year

    if year < min_year or year > max_year or year not in trayodashi_data:
        year = default_year

    data = get_trayodashi_year_data(year, trayodashi_data)

    context = {
        "year": data["year"],
        "min_year": data["min_year"],
        "max_year": data["max_year"],
        "total_records": data["total_records"],
        "rows": data["rows"],
        "error_message": "",
    }
    return render(request, "trayodashi.html", with_global_notifications(request, context))


@login_required
def trayodashi_api_view(request):
    trayodashi_data = load_trayodashi_data()

    if not trayodashi_data:
        return JsonResponse({
            "success": False,
            "message": f"trayodashi.csv file not found or invalid at: {TRAYODASHI_CSV_PATH}"
        }, status=500)

    min_year, max_year = get_trayodashi_year_bounds(trayodashi_data)

    year = request.GET.get("year")

    if not year:
        return JsonResponse({
            "success": False,
            "message": "Please enter a year."
        }, status=400)

    try:
        year = int(year)
    except ValueError:
        return JsonResponse({
            "success": False,
            "message": "Year must be a valid number."
        }, status=400)

    if year < min_year or year > max_year or year not in trayodashi_data:
        return JsonResponse({
            "success": False,
            "message": f"Year must be between {min_year} and {max_year}, and data must exist in trayodashi.csv."
        }, status=400)

    data = get_trayodashi_year_data(year, trayodashi_data)

    return JsonResponse({
        "success": True,
        "message": f"Trayodashi data loaded for {year}.",
        "data": data
    })



########################pushay code  ########################################
import csv
from pathlib import Path
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render


def load_pushya_rows():
    file_path = Path(__file__).resolve().parent / "data" / "pushya.csv"
    rows = []

    if not file_path.exists():
        print("DEBUG pushya.csv not found at:", file_path)
        return rows

    with open(file_path, mode="r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)

        print("DEBUG CSV headers:", reader.fieldnames)

        for row in reader:
            year = str(row.get("year", "")).strip()
            month = str(row.get("month", "")).strip()
            title = str(row.get("title", "")).strip()
            start_raw = str(row.get("start", "")).strip()
            end_raw = str(row.get("end", "")).strip()

            if not year or not start_raw or not end_raw:
                continue

            try:
                start_dt = datetime.strptime(start_raw, "%Y-%m-%d %H:%M")
                end_dt = datetime.strptime(end_raw, "%Y-%m-%d %H:%M")
            except ValueError as e:
                print("DEBUG datetime parse error:", e, row)
                continue

            rows.append({
                "year": year,
                "month": month,
                "title": title,
                "start": start_raw,
                "end": end_raw,
                "start_display": start_dt.strftime("%d %b %Y, %I:%M %p"),
                "end_display": end_dt.strftime("%d %b %Y, %I:%M %p"),
                "duration_hours": round((end_dt - start_dt).total_seconds() / 3600, 2),
            })

    rows.sort(key=lambda item: item["start"])
    print("DEBUG total parsed pushya rows:", len(rows))
    return rows


def get_pushya_years(rows):
    return sorted({row["year"] for row in rows if row["year"]})


@login_required
def pushya_view(request):
    all_rows = load_pushya_rows()
    years = get_pushya_years(all_rows)

    selected_year = request.GET.get("year", "").strip()
    if not selected_year:
        selected_year = years[0] if years else ""

    filtered_rows = [row for row in all_rows if row["year"] == selected_year]

    context = {
        "page_title": "Pushya Nakshatra Calendar",
        "page_tag": "Nakshatra Calendar",
        "page_description": "View Pushya Nakshatra dates year-wise with start and end timings.",
        "selected_year": selected_year,
        "available_years": years,
        "rows": filtered_rows,
        "total_count": len(filtered_rows),
        "event_title": "Pushya Nakshatra",
        "empty_message": "No Pushya Nakshatra data found for the selected year.",
    }
    return render(request, "pushya.html", with_global_notifications(request, context))


@login_required
def pushya_api_view(request):
    all_rows = load_pushya_rows()
    years = get_pushya_years(all_rows)

    selected_year = request.GET.get("year", "").strip()

    if not selected_year:
        return JsonResponse({
            "success": False,
            "message": "Year is required.",
            "data": {
                "rows": [],
                "available_years": years,
            }
        }, status=400)

    filtered_rows = [row for row in all_rows if row["year"] == selected_year]

    return JsonResponse({
        "success": True,
        "message": f"Pushya Nakshatra dates loaded for {selected_year}.",
        "data": {
            "title": "Pushya Nakshatra",
            "year": selected_year,
            "total_count": len(filtered_rows),
            "available_years": years,
            "rows": filtered_rows,
        }
    })

from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .notification import get_notification_context

def with_global_notifications(request, context=None):
    context = context or {}
    context.update(get_notification_context(request))
    return context


@login_required
@require_POST
def mark_notifications_popup_shown_view(request):
    inbox = request.session.get("notification_inbox", [])

    for item in inbox:
        item["popup_shown"] = True

    request.session["notification_inbox"] = inbox
    request.session.modified = True

    return JsonResponse({
        "success": True,
        "message": "Popup notifications marked as shown."
    })


@login_required
@require_POST
def mark_notification_read_view(request):
    notification_id = request.POST.get("notification_id", "").strip()
    inbox = request.session.get("notification_inbox", [])

    updated = False
    for item in inbox:
        if item.get("id") == notification_id:
            item["read"] = True
            item["popup_shown"] = True
            updated = True
            break

    request.session["notification_inbox"] = inbox
    request.session.modified = True

    return JsonResponse({
        "success": updated,
        "message": "Notification updated." if updated else "Notification not found."
    })


@login_required
def notifications_list_view(request):
    inbox = request.session.get("notification_inbox", [])
    unread_count = len([item for item in inbox if not item.get("read", False)])

    return JsonResponse({
        "success": True,
        "unread_count": unread_count,
        "notifications": inbox,
    })

from .notification import get_notification_context

def with_global_notifications(request, context=None):
    context = context or {}
    context.update(get_notification_context(request))
    return context



##################################Calendar##########################################
import os
import csv
from datetime import datetime, date
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


EVENT_SOURCES = {
    "amavasya": {
        "file": "amavasya.csv",
        "title": "Amavasya",
        "color": "#ef4444",
        "text_color": "#ffffff",
        "symbol": "●",
    },
    "purnima": {
        "file": "purnima.csv",
        "title": "Purnima",
        "color": "#22c55e",
        "text_color": "#ffffff",
        "symbol": "●",
    },
    "trayodashi": {
        "file": "trayodashi.csv",
        "title": "Trayodashi",
        "color": "#3b82f6",
        "text_color": "#ffffff",
        "symbol": "●",
    },
    "pushya": {
        "file": "pushya.csv",
        "title": "Pushya",
        "color": "#facc15",
        "text_color": "#111827",
        "symbol": "●",
    },
}


def extract_dates_from_csv(file_path):
    items = []

    if not os.path.exists(file_path):
        return items

    seen = set()

    with open(file_path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            try:
                year = str(row.get("year", "")).strip()
                start_text = str(row.get("start", "")).strip()
                row_title = str(row.get("title", "")).strip()

                if not year or not start_text:
                    continue

                parsed = None
                
                # Try format 1: "Jan 10, 8:11 pm" (amavasya, purnima)
                try:
                    parsed = datetime.strptime(
                        f"{start_text} {year}".upper(),
                        "%b %d, %I:%M %p %Y"
                    )
                except ValueError:
                    # Try format 2: "2024-01-08 23:59" (trayodashi, pushya)
                    try:
                        parsed = datetime.strptime(start_text, "%Y-%m-%d %H:%M")
                    except ValueError:
                        continue

                if not parsed:
                    continue

                iso_date = parsed.date().isoformat()

                unique_key = f"{iso_date}|{row_title}"
                if unique_key in seen:
                    continue

                seen.add(unique_key)

                items.append({
                    "date": iso_date,
                    "display_date": parsed.strftime("%d %b %Y"),
                    "title": row_title,
                })
            except Exception:
                continue

    items.sort(key=lambda x: x["date"])
    return items


def build_calendar_events():
    data_dir = os.path.join(
        settings.BASE_DIR,
        "treading_mainapp",
        "data"
    )

    events = []

    for event_key, config in EVENT_SOURCES.items():
        file_path = os.path.join(data_dir, config["file"])
        csv_items = extract_dates_from_csv(file_path)

        print("FILE =", file_path)
        print("DATES =", len(csv_items))

        for item in csv_items:
            actual_title = item["title"] if item["title"] else config["title"]
            label = f'{item["display_date"]} {actual_title}'

            events.append({
                "title": actual_title,
                "start": item["date"],
                "allDay": True,
                "backgroundColor": config["color"],
                "borderColor": config["color"],
                "textColor": config["text_color"],
                "classNames": [f"event-{event_key}"],
                "extendedProps": {
                    "eventType": event_key,
                    "label": label,
                    "shortLabel": actual_title,
                    "displayDate": item["display_date"],
                    "symbol": config["symbol"],
                    "markerColor": config["color"],
                },
            })

    return events


@login_required
def calendar_view(request):
    calendar_events = build_calendar_events()
    current_year = date.today().year

    month_options = [
        {"value": 1, "label": "January"},
        {"value": 2, "label": "February"},
        {"value": 3, "label": "March"},
        {"value": 4, "label": "April"},
        {"value": 5, "label": "May"},
        {"value": 6, "label": "June"},
        {"value": 7, "label": "July"},
        {"value": 8, "label": "August"},
        {"value": 9, "label": "September"},
        {"value": 10, "label": "October"},
        {"value": 11, "label": "November"},
        {"value": 12, "label": "December"},
    ]

    year_options = list(range(current_year - 5, current_year + 7))

    legend_items = [
        {"name": "Amavasya", "color": "#ef4444", "symbol": "●"},
        {"name": "Purnima", "color": "#22c55e", "symbol": "●"},
        {"name": "Trayodashi", "color": "#3b82f6", "symbol": "●"},
        {"name": "Pushya", "color": "#facc15", "symbol": "●"},
    ]

    context = {
        "calendar_events": calendar_events,
        "legend_items": legend_items,
        "month_options": month_options,
        "year_options": year_options,
        "default_month": date.today().month,
        "default_year": current_year,
    }
    return render(request, "calendar.html", context)


#######################################################################

import csv
import io
import logging
import os
import traceback
from typing import Dict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from uuid import uuid4

from .forms import WhatsAppBroadcastForm, WhatsAppCSVUploadForm
from .models import WhatsAppCampaign, WhatsAppContact, WhatsAppMessageLog
from .whatsapp_broadcast import (
    WhatsAppBroadcastError,
    detect_media_type,
    normalize_indian_mobile,
    send_media_message,
    send_text_message,
    upload_media_to_whatsapp,
    validate_whatsapp_config,
)

logger = logging.getLogger(__name__)


def _request_trace_id() -> str:
    return uuid4().hex[:12]


def _safe_name(file_obj) -> str:
    try:
        return getattr(file_obj, "name", "") or ""
    except Exception:
        return ""


def _safe_size(file_obj) -> int:
    try:
        return int(getattr(file_obj, "size", 0) or 0)
    except Exception:
        return 0


def _form_errors_as_dict(form) -> Dict:
    try:
        return {field: [str(err) for err in errs] for field, errs in form.errors.items()}
    except Exception:
        return {"non_field_errors": [str(form.errors)]}


def import_contacts_from_csv(user, file_obj, trace_id: str = "-"):
    logger.info(
        "[WA][%s] CSV import started user_id=%s file_name=%s file_size=%s",
        trace_id,
        getattr(user, "id", None),
        _safe_name(file_obj),
        _safe_size(file_obj),
    )

    try:
        file_obj.seek(0)
    except Exception:
        logger.warning("[WA][%s] Could not seek uploaded file to start", trace_id)

    raw_bytes = file_obj.read()
    logger.info("[WA][%s] CSV bytes read=%s", trace_id, len(raw_bytes))

    decoded = raw_bytes.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(decoded))

    headers = reader.fieldnames or []
    logger.info("[WA][%s] CSV headers detected=%s", trace_id, headers)

    allowed_phone_headers = {"phone", "mobile", "number"}
    if not any(header in allowed_phone_headers for header in headers):
        logger.error("[WA][%s] CSV import failed: missing phone/mobile/number column", trace_id)
        raise WhatsAppBroadcastError(
            "CSV must contain one of these columns: phone, mobile, number."
        )

    created_count = 0
    updated_count = 0
    skipped_count = 0
    processed_count = 0

    for row_number, row in enumerate(reader, start=2):
        processed_count += 1
        raw_phone = row.get("phone") or row.get("mobile") or row.get("number") or ""
        phone = normalize_indian_mobile(raw_phone)

        logger.info(
            "[WA][%s] CSV row=%s raw_phone=%r normalized=%r",
            trace_id,
            row_number,
            raw_phone,
            phone,
        )

        if not phone:
            skipped_count += 1
            logger.warning(
                "[WA][%s] CSV row skipped row=%s reason=invalid_phone raw_phone=%r",
                trace_id,
                row_number,
                raw_phone,
            )
            continue

        name = (row.get("name") or row.get("username") or "").strip()
        email = (row.get("email") or "").strip()

        _, created = WhatsAppContact.objects.update_or_create(
            owner=user,
            phone=phone,
            defaults={
                "name": name,
                "email": email,
                "source_file": _safe_name(file_obj),
                "is_active": True,
            },
        )

        if created:
            created_count += 1
            logger.info(
                "[WA][%s] Contact created row=%s phone=%s name=%r",
                trace_id,
                row_number,
                phone,
                name,
            )
        else:
            updated_count += 1
            logger.info(
                "[WA][%s] Contact updated row=%s phone=%s name=%r",
                trace_id,
                row_number,
                phone,
                name,
            )

    result = {
        "created": created_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "processed": processed_count,
    }
    logger.info("[WA][%s] CSV import completed result=%s", trace_id, result)
    return result


@login_required
def whatsapp_broadcast_view(request):
    trace_id = _request_trace_id()
    logger.info(
        "[WA][%s] whatsapp_broadcast_view entered method=%s user_id=%s path=%s",
        trace_id,
        request.method,
        getattr(request.user, "id", None),
        request.path,
    )

    csv_form = WhatsAppCSVUploadForm()
    form = WhatsAppBroadcastForm()

    config_ok, missing_config = validate_whatsapp_config()
    logger.info(
        "[WA][%s] WhatsApp config validation config_ok=%s missing=%s",
        trace_id,
        config_ok,
        missing_config,
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()
        logger.info("[WA][%s] POST action=%r", trace_id, action)

        if action == "upload_csv":
            csv_form = WhatsAppCSVUploadForm(request.POST, request.FILES)
            form = WhatsAppBroadcastForm()

            logger.info(
                "[WA][%s] upload_csv received files=%s",
                trace_id,
                list(request.FILES.keys()),
            )

            if csv_form.is_valid():
                logger.info("[WA][%s] CSV form valid, starting import", trace_id)
                try:
                    result = import_contacts_from_csv(
                        request.user,
                        csv_form.cleaned_data["csv_file"],
                        trace_id=trace_id,
                    )
                    messages.success(
                        request,
                        (
                            f"CSV imported successfully. "
                            f"Created: {result['created']}, "
                            f"Updated: {result['updated']}, "
                            f"Skipped: {result['skipped']}"
                        ),
                    )
                    logger.info("[WA][%s] upload_csv success redirecting", trace_id)
                    return redirect("whatsapp_broadcast")
                except Exception as exc:
                    logger.exception("[WA][%s] CSV import failed error=%s", trace_id, exc)
                    messages.error(request, f"CSV import failed: {str(exc)}")
            else:
                logger.error(
                    "[WA][%s] CSV form invalid errors=%s",
                    trace_id,
                    _form_errors_as_dict(csv_form),
                )
                messages.error(request, "CSV upload form invalid. Please check file and try again.")

        elif action == "send_campaign":
            csv_form = WhatsAppCSVUploadForm()
            form = WhatsAppBroadcastForm(request.POST, request.FILES)

            logger.info(
                "[WA][%s] send_campaign received files=%s",
                trace_id,
                list(request.FILES.keys()),
            )

            if form.is_valid():
                logger.info("[WA][%s] Broadcast form valid", trace_id)

                contacts = WhatsAppContact.objects.filter(
                    owner=request.user,
                    is_active=True,
                ).order_by("id")

                contacts_count = contacts.count()
                logger.info(
                    "[WA][%s] Active contacts fetched count=%s",
                    trace_id,
                    contacts_count,
                )

                if contacts_count == 0:
                    logger.warning("[WA][%s] No contacts found, aborting campaign", trace_id)
                    messages.error(request, "Please upload CSV contacts first.")
                    return redirect("whatsapp_broadcast")

                if not config_ok:
                    logger.error(
                        "[WA][%s] Config missing, aborting campaign missing=%s",
                        trace_id,
                        missing_config,
                    )
                    messages.error(
                        request,
                        f"Missing WhatsApp config: {', '.join(missing_config)}",
                    )
                    return redirect("whatsapp_broadcast")

                attachment = form.cleaned_data.get("attachment")
                attachment_name = getattr(attachment, "name", "") if attachment else ""
                attachment_size = getattr(attachment, "size", 0) if attachment else 0

                logger.info(
                    "[WA][%s] Preparing campaign attachment_name=%r attachment_size=%s",
                    trace_id,
                    attachment_name,
                    attachment_size,
                )

                with transaction.atomic():
                    campaign = WhatsAppCampaign.objects.create(
                        owner=request.user,
                        campaign_name=f"Broadcast {timezone.now().strftime('%d %b %Y %H:%M:%S')}",
                        message=form.cleaned_data["message"],
                        media_file=attachment,
                        media_type=detect_media_type(attachment.name) if attachment else "",
                        status="processing",
                        started_at=timezone.now(),
                        total_contacts=contacts_count,
                    )

                logger.info(
                    "[WA][%s] Campaign created campaign_id=%s total_contacts=%s media_type=%r",
                    trace_id,
                    campaign.id,
                    campaign.total_contacts,
                    campaign.media_type,
                )

                sent_count = 0
                failed_count = 0
                media_id = None
                media_type = ""

                try:
                    if campaign.media_file:
                        logger.info(
                            "[WA][%s] Media detected path=%s",
                            trace_id,
                            campaign.media_file.path,
                        )
                        media_type = detect_media_type(campaign.media_file.path)
                        logger.info(
                            "[WA][%s] Media type detected media_type=%s",
                            trace_id,
                            media_type,
                        )
                        media_id = upload_media_to_whatsapp(campaign.media_file.path)
                        logger.info(
                            "[WA][%s] Media uploaded successfully media_id=%s",
                            trace_id,
                            media_id,
                        )
                    else:
                        logger.info("[WA][%s] No attachment supplied, text-only campaign", trace_id)
                except Exception as exc:
                    logger.exception("[WA][%s] Media upload failed error=%s", trace_id, exc)
                    campaign.status = "failed"
                    campaign.failed_count = contacts_count
                    campaign.completed_at = timezone.now()
                    campaign.save(
                        update_fields=["status", "failed_count", "completed_at", "updated_at"]
                        if hasattr(campaign, "updated_at")
                        else ["status", "failed_count", "completed_at"]
                    )
                    messages.error(request, f"Media upload failed: {str(exc)}")
                    return redirect("whatsapp_broadcast")

                logger.info("[WA][%s] Starting send loop", trace_id)

                for index, contact in enumerate(contacts.iterator(), start=1):
                    personalized_message = (campaign.message or "").replace(
                        "{{name}}",
                        contact.name or "User",
                    )

                    logger.info(
                        "[WA][%s] Sending start idx=%s/%s contact_id=%s phone=%s name=%r media=%s",
                        trace_id,
                        index,
                        contacts_count,
                        contact.id,
                        contact.phone,
                        contact.name,
                        bool(media_id),
                    )

                    log = WhatsAppMessageLog.objects.create(
                        campaign=campaign,
                        contact=contact,
                        phone=contact.phone,
                        status="pending",
                    )

                    logger.info(
                        "[WA][%s] Message log created log_id=%s campaign_id=%s contact_id=%s",
                        trace_id,
                        log.id,
                        campaign.id,
                        contact.id,
                    )

                    try:
                        if media_id:
                            response = send_media_message(
                                to_number=contact.phone,
                                media_id=media_id,
                                media_type=media_type,
                                caption=personalized_message,
                            )
                        else:
                            response = send_text_message(
                                to_number=contact.phone,
                                message_text=personalized_message,
                            )

                        logger.info(
                            "[WA][%s] API response received phone=%s status_code=%s",
                            trace_id,
                            contact.phone,
                            response.status_code,
                        )

                        if response.status_code in (200, 201):
                            sent_count += 1
                            response_json = {}
                            message_id = ""

                            try:
                                response_json = response.json()
                            except Exception:
                                logger.warning(
                                    "[WA][%s] Response JSON parse failed phone=%s body=%r",
                                    trace_id,
                                    contact.phone,
                                    response.text[:1000],
                                )

                            if response_json.get("messages"):
                                message_id = response_json["messages"][0].get("id", "")

                            log.status = "sent"
                            log.whatsapp_message_id = message_id
                            log.response_code = response.status_code
                            log.response_body = response.text[:5000]
                            log.sent_at = timezone.now()
                            log.save()

                            logger.info(
                                "[WA][%s] Send success phone=%s message_id=%r sent_count=%s failed_count=%s",
                                trace_id,
                                contact.phone,
                                message_id,
                                sent_count,
                                failed_count,
                            )
                        else:
                            failed_count += 1
                            log.status = "failed"
                            log.response_code = response.status_code
                            log.response_body = response.text[:5000]
                            log.error_message = response.text[:5000]
                            log.save()

                            logger.error(
                                "[WA][%s] Send failed phone=%s status_code=%s response=%r sent_count=%s failed_count=%s",
                                trace_id,
                                contact.phone,
                                response.status_code,
                                response.text[:1000],
                                sent_count,
                                failed_count,
                            )

                    except Exception as exc:
                        failed_count += 1
                        log.status = "failed"
                        log.response_code = 500
                        log.error_message = str(exc)[:5000]
                        log.response_body = traceback.format_exc()[:5000]
                        log.save()

                        logger.exception(
                            "[WA][%s] Exception during send phone=%s log_id=%s error=%s",
                            trace_id,
                            contact.phone,
                            log.id,
                            exc,
                        )

                campaign.sent_count = sent_count
                campaign.failed_count = failed_count
                campaign.status = "completed" if failed_count == 0 else "failed"
                campaign.completed_at = timezone.now()
                campaign.save()

                logger.info(
                    "[WA][%s] Campaign completed campaign_id=%s sent=%s failed=%s final_status=%s",
                    trace_id,
                    campaign.id,
                    sent_count,
                    failed_count,
                    campaign.status,
                )

                if sent_count > 0 and failed_count == 0:
                    messages.success(
                        request,
                        f"Campaign completed successfully. Sent: {sent_count}, Failed: {failed_count}",
                    )
                elif sent_count > 0 and failed_count > 0:
                    messages.warning(
                        request,
                        f"Campaign partially completed. Sent: {sent_count}, Failed: {failed_count}",
                    )
                else:
                    messages.error(
                        request,
                        f"Campaign failed. Sent: {sent_count}, Failed: {failed_count}",
                    )

                return redirect("whatsapp_broadcast")

            else:
                logger.error(
                    "[WA][%s] Broadcast form invalid errors=%s",
                    trace_id,
                    _form_errors_as_dict(form),
                )
                messages.error(request, "Broadcast form invalid. Please check the fields and try again.")

        else:
            logger.warning("[WA][%s] Unknown POST action=%r", trace_id, action)
            messages.error(request, "Invalid action.")

    logger.info("[WA][%s] Loading dashboard data", trace_id)

    contacts_qs = WhatsAppContact.objects.filter(
        owner=request.user,
        is_active=True,
    ).order_by("-created_at")

    campaigns = WhatsAppCampaign.objects.filter(
        owner=request.user
    ).order_by("-created_at")[:10]

    latest_campaign = campaigns.first()

    recent_logs = WhatsAppMessageLog.objects.filter(
        campaign__owner=request.user
    ).select_related("campaign", "contact").order_by("-created_at")[:20]

    context = {
        "csv_form": csv_form,
        "form": form,
        "contacts_count": contacts_qs.count(),
        "contacts": contacts_qs[:10],
        "campaigns": campaigns,
        "latest_campaign": latest_campaign,
        "recent_logs": recent_logs,
        "config_ok": config_ok,
        "missing_config": missing_config,
    }

    logger.info(
        "[WA][%s] Rendering dashboard contacts_count=%s campaigns_count=%s logs_count=%s",
        trace_id,
        context["contacts_count"],
        len(campaigns),
        len(recent_logs),
    )
    return render(request, "dashboard/whatsapp_broadcast.html", context)

###########################################################################


from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

from .models import GapUpStatus
from . import gapup as gapup_service


@login_required
def gapupview(request):
    trade_date = timezone.localdate()
    rows = GapUpStatus.objects.filter(trade_date=trade_date).order_by("symbol")

    gap_up_rows = rows.filter(gap_up=True)
    gap_down_rows = rows.filter(gap_down=True)
    failed_rows = rows.filter(gap_type="SCAN FAILED")
    no_gap_rows = rows.filter(gap_type="NO GAP")

    context = {
        "trade_date": trade_date,
        "rows": rows,
        "gap_up_rows": gap_up_rows,
        "gap_down_rows": gap_down_rows,
        "gapupcount": gap_up_rows.count(),
        "gapdowncount": gap_down_rows.count(),
        "failedcount": failed_rows.count(),
        "nogapcount": no_gap_rows.count(),
        "hasdata": rows.exists(),
    }
    return render(request, "dashboard/gapup.html", context)


@login_required
@require_POST
def gapuprefreshview(request):
    trade_date = timezone.localdate()
    limit_raw = (request.POST.get("limit") or "").strip()
    limit_symbols = int(limit_raw) if limit_raw.isdigit() else None

    result = gapup_service.update_all_gapup_data(
        trade_date=trade_date,
        limit_symbols=limit_symbols,
    )

    status_code = 200 if result["error_count"] == 0 else 207

    return JsonResponse({
        "status": result["error_count"] == 0,
        "message": f"Gap scan completed for {trade_date}. Success={result['success_count']} Failed={result['error_count']}",
        "trade_date": str(trade_date),
        "success_count": result["success_count"],
        "error_count": result["error_count"],
        "errors": result["errors"][:10],
    }, status=status_code)


@login_required
@require_GET
def gapupstatusapiview(request):
    trade_date = timezone.localdate()
    rows = GapUpStatus.objects.filter(trade_date=trade_date).order_by("symbol")

    gap_up = [
        {
            "symbol": row.symbol,
            "company_name": row.company_name,
            "gap_type": row.gap_type,
            "notes": row.notes,
        }
        for row in rows.filter(gap_up=True)
    ]

    gap_down = [
        {
            "symbol": row.symbol,
            "company_name": row.company_name,
            "gap_type": row.gap_type,
            "notes": row.notes,
        }
        for row in rows.filter(gap_down=True)
    ]

    all_rows = [
        {
            "symbol": row.symbol,
            "company_name": row.company_name,
            "prev_trade_date": str(row.prev_trade_date) if row.prev_trade_date else "",
            "prev_open": str(row.prev_open or ""),
            "prev_high": str(row.prev_high or ""),
            "prev_low": str(row.prev_low or ""),
            "prev_close": str(row.prev_close or ""),
            "today_open": str(row.today_open or ""),
            "today_high": str(row.today_high or ""),
            "today_low": str(row.today_low or ""),
            "today_close": str(row.today_close or ""),
            "open_diff": str(row.open_diff or ""),
            "high_diff": str(row.high_diff or ""),
            "low_diff": str(row.low_diff or ""),
            "close_diff": str(row.close_diff or ""),
            "gap_up": row.gap_up,
            "gap_down": row.gap_down,
            "gap_type": row.gap_type,
            "notes": row.notes,
            "refreshed_at": timezone.localtime(row.refreshed_at).strftime("%d-%m-%Y %I:%M:%S %p") if row.refreshed_at else "",
        }
        for row in rows
    ]

    return JsonResponse({
        "status": True,
        "trade_date": str(trade_date),
        "gap_up_count": len(gap_up),
        "gap_down_count": len(gap_down),
        "failed_count": rows.filter(gap_type="SCAN FAILED").count(),
        "total_count": len(all_rows),
        "gap_up": gap_up,
        "gap_down": gap_down,
        "rows": all_rows,
    })

@login_required
@require_GET
def moon_marse_view(request):
    year_param = request.GET.get("year", "").strip()

    selected_year = None
    if year_param.isdigit():
        selected_year = int(year_param)

    data = get_moon_mars_events_by_year(selected_year=selected_year)

    context = {
        "selected_year": data["selected_year"],
        "available_years": data["available_years"],
        "moon_mars_events": data["events"],
        "moon_mars_total": data["total_events"],
    }
    return render(request, "moon_marse.html", context)


@login_required
@require_GET
def moon_marse_api_view(request):
    year_param = request.GET.get("year", "").strip()

    selected_year = None
    if year_param.isdigit():
        selected_year = int(year_param)

    data = get_moon_mars_events_by_year(selected_year=selected_year)

    return JsonResponse(
        {
            "selected_year": data["selected_year"],
            "available_years": data["available_years"],
            "total_events": data["total_events"],
            "events": data["events"],
        }
    )

import logging

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

from .amavsya import generate_amavasya_levels, STRATEGY_INTERVAL
from .services.angel_api import AngelBroker

logger = logging.getLogger(__name__)


@login_required
@require_GET
def amavasya_strategy_api_view(request):
    symbol = request.GET.get("symbol", DEFAULT_SYMBOL).strip()
    all_symbols = INDEX_SYMBOLS + STOCK_SYMBOLS

    if symbol not in all_symbols:
        symbol = DEFAULT_SYMBOL

    strategy_interval = STRATEGY_INTERVAL

    try:
        broker = AngelBroker()

        candle_result = broker.fetch_historical_candles(
            symbol=symbol,
            interval=strategy_interval,
        )

        if not candle_result.get("status"):
            return JsonResponse({
                "status": False,
                "message": candle_result.get("message", "Unable to fetch broker candles."),
                "symbol": symbol,
                "interval": strategy_interval,
                "levels": [],
                "meta": {
                    "broker_status": False,
                    "broker_message": candle_result.get("message", ""),
                    "raw_candles_count": 0,
                    "levels_count": 0,
                },
            }, status=200)

        raw_candles = candle_result.get("candles", []) or []

        strategy_result = generate_amavasya_levels(
            raw_candles=raw_candles,
            interval=strategy_interval,
        )

        return JsonResponse({
            "status": bool(strategy_result.get("status")),
            "message": strategy_result.get("message", ""),
            "symbol": symbol,
            "interval": strategy_interval,
            "levels": strategy_result.get("levels", []),
            "meta": {
                **strategy_result.get("meta", {}),
                "broker_status": candle_result.get("status"),
                "broker_message": candle_result.get("message", ""),
                "raw_candles_count": len(raw_candles),
                "levels_count": len(strategy_result.get("levels", [])),
            },
        }, status=200)

    except Exception as exc:
        logger.exception("Amavasya strategy exception")
        return JsonResponse({
            "status": False,
            "message": f"Amavasya strategy exception: {str(exc)}",
            "symbol": symbol,
            "interval": strategy_interval,
            "levels": [],
            "meta": {},
        }, status=200)
