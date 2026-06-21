from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm, ForgotPasswordForm
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


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Account created successfully. Please login.")
            return redirect("login")
    else:
        form = RegisterForm()

    return render(request, "auth/register.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = LoginForm(request, request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, "Login successful.")
            return redirect("dashboard")
    else:
        form = LoginForm()

    return render(request, "auth/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Password reset successful. Please login with new password.")
            return redirect("login")
    else:
        form = ForgotPasswordForm()

    return render(request, "auth/forgot_password.html", {"form": form})


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


import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.shortcuts import render, redirect

from .forms import WhatsAppBroadcastForm


def _normalize_indian_mobile(number):
    digits = "".join(ch for ch in str(number) if ch.isdigit())

    if not digits:
        return None

    if digits.startswith("91") and len(digits) == 12:
        return digits

    if len(digits) == 10:
        return f"91{digits}"

    if digits.startswith("0") and len(digits) == 11:
        trimmed = digits[1:]
        if len(trimmed) == 10:
            return f"91{trimmed}"

    return None


def _load_whatsapp_recipients():
    json_path = getattr(settings, "WHATSAPP_CONTACTS_JSON", "")
    if not json_path:
        raise Exception("WHATSAPP_CONTACTS_JSON not configured in settings.py")

    path = Path(json_path)
    if not path.exists():
        raise Exception(f"JSON file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise Exception("JSON root must be a list.")

    recipients = []
    seen = set()

    for item in data:
        if not isinstance(item, dict):
            continue

        username = item.get("username", "Unknown")
        raw_mobile = item.get("mobile", "")
        mobile = _normalize_indian_mobile(raw_mobile)

        if not mobile:
            continue

        if mobile in seen:
            continue

        seen.add(mobile)
        recipients.append({
            "username": username,
            "mobile": mobile,
            "email": item.get("email", ""),
        })

    return recipients


@login_required(login_url="login")
def whatsapp_broadcast_view(request):
    recipients = []
    recipients_count = 0
    json_error = None
    uploaded_file_info = None

    try:
        recipients = _load_whatsapp_recipients()
        recipients_count = len(recipients)
    except Exception as exc:
        json_error = str(exc)

    if request.method == "POST":
        form = WhatsAppBroadcastForm(request.POST, request.FILES)

        if form.is_valid():
            message_text = (form.cleaned_data.get("message") or "").strip()
            attachment = form.cleaned_data.get("attachment")

            saved_file_url = None
            saved_file_name = None
            saved_file_path = None

            if attachment:
                upload_dir = os.path.join(settings.MEDIA_ROOT, "whatsapp_broadcasts")
                os.makedirs(upload_dir, exist_ok=True)

                storage = FileSystemStorage(location=upload_dir)
                saved_name = storage.save(attachment.name, attachment)
                saved_file_name = saved_name
                saved_file_path = storage.path(saved_name)
                saved_file_url = f"{settings.MEDIA_URL}whatsapp_broadcasts/{saved_name}"

                uploaded_file_info = {
                    "name": saved_file_name,
                    "url": saved_file_url,
                    "path": saved_file_path,
                    "size": attachment.size,
                }

            simulated_results = []
            for recipient in recipients:
                simulated_results.append({
                    "username": recipient["username"],
                    "mobile": recipient["mobile"],
                    "success": False,
                    "status_code": "CONFIG_PENDING",
                    "response_text": "API Config Missing - delivery simulation only.",
                })

            report = {
                "total": len(recipients),
                "success_count": 0,
                "failed_count": len(recipients),
                "message_text": message_text,
                "uploaded_file": uploaded_file_info,
                "results": simulated_results,
            }

            request.session["whatsapp_broadcast_last_result"] = report

            print("\n========== WHATSAPP BROADCAST DEBUG ==========")
            print(f"Recipients loaded: {len(recipients)}")
            print(f"Message text: {message_text}")
            if uploaded_file_info:
                print(f"Attachment saved: {uploaded_file_info['path']}")
            else:
                print("Attachment saved: None")
            print("Status: API Config Missing - UI workflow working correctly.")
            print("=============================================\n")

            messages.success(
                request,
                "Broadcast workflow working hai. JSON read, form submit, file upload, report generation sab sahi hai. Bas API config pending hai."
            )
            return redirect("whatsapp_broadcast")

        else:
            messages.error(request, "Form validation failed. Please correct the errors below.")
    else:
        form = WhatsAppBroadcastForm()

    last_result = request.session.get("whatsapp_broadcast_last_result")

    context = {
        "form": form,
        "page_title": "WhatsApp Broadcast Channel",
        "recipients": recipients[:20],
        "recipients_count": recipients_count,
        "json_error": json_error,
        "config_ok": False,
        "missing_keys": ["WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_ACCESS_TOKEN"],
        "last_result": last_result,
    }
    return render(request, "dashboard/whatsapp_broadcast.html", context)


@login_required
def gapup_view(request):
    trade_date = timezone.localdate()
    rows = GapUpStatus.objects.filter(trade_date=trade_date).order_by("symbol")

    if not rows.exists():
        treading_mainapp.gapup.update_all_gapup_data(trade_date=trade_date)
        rows = GapUpStatus.objects.filter(trade_date=trade_date).order_by("symbol")

    gap_up_count = rows.filter(gap_up=True).count()
    gap_down_count = rows.filter(gap_down=True).count()
    no_gap_count = rows.count() - gap_up_count - gap_down_count

    context = {
        "rows": rows,
        "trade_date": trade_date,
        "gap_up_count": gap_up_count,
        "gap_down_count": gap_down_count,
        "no_gap_count": no_gap_count,
    }
    return render(request, "dashboard/gapup.html", context)


@login_required
def gapup_refresh_view(request):
    if request.method == "POST":
        trade_date = timezone.localdate()
        treading_mainapp.gapup.update_all_gapup_data(trade_date=trade_date)
        messages.success(request, "Gap-up data refreshed successfully.")
    return redirect("gapup")

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