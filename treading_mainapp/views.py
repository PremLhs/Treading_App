from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import LoginForm
from .notification import get_notification_context, add_custom_notification_to_session, get_unread_popup_notifications
from .pinbar import scan_pinbar_signals
from .services.angel_api import AngelBroker
from .services.nifty50_loader import get_dashboard_symbols
from .models import GapUpStatus
import treading_mainapp.gapup
from .moon_mars import get_moon_mars_events_by_year

INDEX_SYMBOLS = [
    "NSE:NIFTY",
    "NSE:BANKNIFTY",
]

# Load dashboard symbols at request time to pick up data file changes without restart
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

    stock_symbols = get_dashboard_symbols()
    all_symbols = INDEX_SYMBOLS + stock_symbols

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
        "stock_symbols": stock_symbols,
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

    stock_symbols = get_dashboard_symbols()
    all_symbols = INDEX_SYMBOLS + stock_symbols

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
        "message": f"Dark Day data loaded for {year}.",
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
                "title": title or "-",
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
        "message": f"Light Day data loaded for {year}.",
        "data": data
    })

############################################################################################################

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

            # paksha is optional, all other fields are required
            if not year_raw or not month or not start or not end:
                continue

            try:
                year = int(year_raw)
            except ValueError:
                continue

            data.setdefault(year, []).append({
                "month": month,
                "paksha": paksha,
                "title": title or "-",
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
        "message": f"Intra Day data loaded for {year}.",
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

PINBAR_SCAN_CACHE: dict[str, dict] = {}


def _get_pinbar_cache_key(request):
    session_key = request.session.session_key
    if session_key:
        return f"pinbar_scan_{session_key}"
    return f"pinbar_scan_{request.COOKIES.get('sessionid', 'anonymous')}"


def _get_current_15m_boundary(now=None):
    now = now or timezone.localtime()
    now = now.replace(second=0, microsecond=0)
    boundary_minute = (now.minute // 15) * 15
    return now.replace(minute=boundary_minute)


def _pinbar_scan_cached(request):
    cache_key = _get_pinbar_cache_key(request)
    cache = request.session.get("pinbar_scan_cache") or PINBAR_SCAN_CACHE.get(cache_key)
    if not cache or not cache.get("boundary"):
        return None

    latest_boundary = _get_current_15m_boundary()
    if cache.get("boundary") == latest_boundary.isoformat():
        return cache.get("signals", [])
    return None


def _pinbar_scan_store(request, scan_results):
    cache_key = _get_pinbar_cache_key(request)
    cached_value = {
        "boundary": _get_current_15m_boundary().isoformat(),
        "signals": scan_results,
    }
    PINBAR_SCAN_CACHE[cache_key] = cached_value
    request.session["pinbar_scan_cache"] = cached_value
    request.session.modified = True


def with_global_notifications(request, context=None):
    context = context or {}
    context.update(get_notification_context(request))
    return context


@login_required
def pinbar_view(request):
    scan_results = []
    notification_count = 0

    try:
        cached_signals = _pinbar_scan_cached(request)
        if cached_signals is not None:
            scan_results = cached_signals
        else:
            scan_results = scan_pinbar_signals()
            _pinbar_scan_store(request, scan_results)

        for result in scan_results:
            if result.get("is_pin_bar") and not result.get("error"):
                candle_period = result.get("candle_period") or result.get("candle_time") or "unknown"
                notification_id = f"pinbar-{result.get('symbol')}-{result.get('trade_date')}-{candle_period}"
                notification = {
                    "id": notification_id,
                    "label": "Pin Bar Alert",
                    "message": f"Pin bar created on {result.get('symbol')}.",
                    "submessage": f"Period: {candle_period} | {result.get('pinbar_type', '').capitalize()} | Close: {result.get('close')}",
                    "page_url": "/pinbar/",
                    "color_class": "notification-danger" if result.get("pinbar_type") == "bearish" else "notification-success",
                    "event_date": result.get("trade_date"),
                    "event_time": candle_period,
                    "sort_order": 0,
                }
                add_custom_notification_to_session(request, notification)
                notification_count += 1
    except Exception as exc:
        scan_results = [{
            "symbol": "N/A",
            "trade_date": str(timezone.localdate()),
            "is_pin_bar": False,
            "pinbar_type": None,
            "candle_time": None,
            "open": None,
            "high": None,
            "low": None,
            "close": None,
            "body": None,
            "upper_wick": None,
            "lower_wick": None,
            "range": None,
            "reason": str(exc),
            "error": True,
        }]

    context = {
        "page_title": "Pin Bar Scanner",
        "signals": scan_results,
        "notification_count": notification_count,
        "hide_global_notifications": True,
    }
    return render(request, "pinbar.html", with_global_notifications(request, context))


@login_required
def pinbar_api_view(request):
    try:
        cached_signals = _pinbar_scan_cached(request)
        if cached_signals is not None:
            scan_results = cached_signals
        else:
            scan_results = scan_pinbar_signals()
            _pinbar_scan_store(request, scan_results)

        for result in scan_results:
            if result.get("is_pin_bar") and not result.get("error"):
                candle_period = result.get("candle_period") or result.get("candle_time") or "unknown"
                notification_id = f"pinbar-{result.get('symbol')}-{result.get('trade_date')}-{candle_period}"
                notification = {
                    "id": notification_id,
                    "label": "Pin Bar Alert",
                    "message": f"Pin bar created on {result.get('symbol')}.",
                    "submessage": f"Period: {candle_period} | {result.get('pinbar_type', '').capitalize()} | Close: {result.get('close')}",
                    "page_url": "/pinbar/",
                    "color_class": "notification-danger" if result.get("pinbar_type") == "bearish" else "notification-success",
                    "event_date": result.get("trade_date"),
                    "event_time": candle_period,
                    "sort_order": 0,
                }
                add_custom_notification_to_session(request, notification)

        unread_notifications = get_unread_popup_notifications(request)

        return JsonResponse({
            "success": True,
            "message": "Pin bar scan completed.",
            "signals": scan_results,
            "notifications": unread_notifications,
        })
    except Exception as exc:
        return JsonResponse({
            "success": False,
            "message": str(exc),
            "signals": [],
            "notifications": [],
        }, status=500)


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
def notifications_page_view(request):
    context = {
        "page_title": "Notifications",
    }
    return render(request, "notifications.html", with_global_notifications(request, context))


@login_required
def notifications_list_view(request):
    inbox = request.session.get("notification_inbox", [])
    unread_count = len([item for item in inbox if not item.get("read", False)])

    return JsonResponse({
        "success": True,
        "unread_count": unread_count,
        "notifications": inbox,
    })


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
        "color": "#111827",
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
    "pentagon": {
        "file": "Pentagon.csv",
        "title": "Pentagon",
        "color": "#b01364",
        "text_color": "#ffffff",
        "symbol": "⬟",
    },
    "red_ball": {
        "file": "red_ball.csv",
        "title": "Red Ball",
        "color": "#ef4444",
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
    "moon_marse": {
        "file": "moon_marse.csv",
        "title": "Moon Mars",
        "color": "#6c0b2e",  # updated color per request
        "text_color": "#ffffff",
        "symbol": "●",
    },
        "reversal": {
        "file": None,
        "title": "Reversal",
        "color": "#a855f7",
        "text_color": "#ffffff",
        "symbol": "●",
    },
}


def extract_dates_from_csv(file_path, field_map=None, fallback_title=""):
    items = []

    if not os.path.exists(file_path):
        return items

    field_map = field_map or {
        "year": ["year"],
        "start": ["start"],
        "title": ["title"],
    }

    def get_field_value(row, keys):
        for key in keys:
            value = row.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return text
        return ""

    seen = set()

    with open(file_path, "r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            try:
                year = get_field_value(row, field_map.get("year", ["year"]))
                start_text = get_field_value(row, field_map.get("start", ["start"]))
                row_title = get_field_value(row, field_map.get("title", ["title"])) or fallback_title

                if not start_text:
                    continue

                parsed = None

                candidates = []
                if year:
                    candidates.append(f"{start_text} {year}".upper())
                candidates.append(start_text)

                for candidate in candidates:
                    for date_format in ["%b %d, %I:%M %p %Y", "%Y-%m-%d %H:%M", "%Y-%m-%d"]:
                        try:
                            parsed = datetime.strptime(candidate, date_format)
                            break
                        except ValueError:
                            continue
                    if parsed is not None:
                        break

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
        if event_key == "reversal":
            continue

        file_path = os.path.join(data_dir, config["file"])
        field_map = None
        fallback_title = ""

        if event_key == "pentagon":
            field_map = {
                "year": ["Year"],
                "start": ["Start Date"],
                "title": ["title"],
            }
            fallback_title = config["title"]
        elif event_key == "red_ball":
            field_map = {
                "year": ["Year"],
                "start": ["Date"],
                "title": ["title"],
            }
            fallback_title = config["title"]

        csv_items = extract_dates_from_csv(file_path, field_map=field_map, fallback_title=fallback_title)

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

    reversal_config = EVENT_SOURCES["reversal"]
    current_year = date.today().year
    years_to_load = range(current_year - 5, current_year + 7)

    seen_reversal = set()

    for year in years_to_load:
        reversal_data = generate_reversal_rows(year)

        for row in reversal_data.get("rows", []):
            reversal_date = str(row.get("reversal_date", "")).strip()

            if not reversal_date or reversal_date == "-":
                continue

            try:
                parsed_date = datetime.strptime(reversal_date, "%d-%m-%Y")
            except ValueError:
                continue

            iso_date = parsed_date.date().isoformat()
            degree = str(row.get("degree", "")).strip()
            actual_title = f"Reversal {degree}°" if degree else reversal_config["title"]
            label = f'{parsed_date.strftime("%d %b %Y")} {actual_title}'

            unique_key = f"{iso_date}|{actual_title}"
            if unique_key in seen_reversal:
                continue

            seen_reversal.add(unique_key)

            events.append({
                "title": actual_title,
                "start": iso_date,
                "allDay": True,
                "backgroundColor": reversal_config["color"],
                "borderColor": reversal_config["color"],
                "textColor": reversal_config["text_color"],
                "classNames": ["event-reversal"],
                "extendedProps": {
                    "eventType": "reversal",
                    "label": label,
                    "shortLabel": actual_title,
                    "displayDate": parsed_date.strftime("%d %b %Y"),
                    "symbol": reversal_config["symbol"],
                    "markerColor": reversal_config["color"],
                    "degree": degree,
                },
            })

    events.sort(key=lambda item: (item.get("start", ""), item.get("title", "")))
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
        {"name": "Amavasya", "color": "#111827", "symbol": "●"},
        {"name": "Purnima", "color": "#22c55e", "symbol": "●"},
        {"name": "Pentagon", "color": "#f472b6", "symbol": "⬟"},
        {"name": "Red Ball", "color": "#ef4444", "symbol": "●"},
        {"name": "Trayodashi", "color": "#3b82f6", "symbol": "●"},
        {"name": "Moon Mars", "color": "#6c0b2e", "symbol": "●"},
        {"name": "Pushya", "color": "#facc15", "symbol": "●"},
        {"name": "Reversal", "color": "#a855f7", "symbol": "●"},
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
    runtime = gapup_service.get_gap_scan_runtime_status(trade_date=trade_date)

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
        "scan_runtime": runtime,
    }
    return render(request, "dashboard/gapup.html", context)


@login_required
@require_POST
def gapuprefreshview(request):
    trade_date = timezone.localdate()
    force_refresh = (request.POST.get("force") or "").strip().lower() in {"1", "true", "yes"}

    result = gapup_service.start_gap_scan_in_background(
        trade_date=trade_date,
        limit_symbols=None,
        scan_type="FORCE" if force_refresh else "MANUAL",
        trigger_source="web_refresh",
        force=force_refresh,
    )

    status_code = 202 if result.get("queued") else 200

    return JsonResponse({
        "status": result["status"],
        "queued": result["queued"],
        "message": result["message"],
        "trade_date": result["trade_date"],
        "run_id": result.get("run_id"),
    }, status=status_code)


@login_required
@require_GET
def gapupstatusapiview(request):
    trade_date = timezone.localdate()
    rows = GapUpStatus.objects.filter(trade_date=trade_date).order_by("symbol")
    runtime = gapup_service.get_gap_scan_runtime_status(trade_date=trade_date)

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
        "runtime": runtime,
    })


@login_required
@require_GET
def gapupscanruntimeapiview(request):
    trade_date = timezone.localdate()
    runtime = gapup_service.get_gap_scan_runtime_status(trade_date=trade_date)
    return JsonResponse(runtime)

##############################################################
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

from .amavsya import generate_amavasya_levels, STRATEGY_INTERVAL, SUPPORTED_INTERVALS
from .services.angel_api import AngelBroker

logger = logging.getLogger(__name__)


@login_required
@require_GET
def amavasya_strategy_api_view(request):
    symbol = request.GET.get("symbol", DEFAULT_SYMBOL).strip()
    stock_symbols = get_dashboard_symbols()
    all_symbols = INDEX_SYMBOLS + stock_symbols

    if symbol not in all_symbols:
        symbol = DEFAULT_SYMBOL

    # Allow client to request different intervals (e.g., '15' or 'D')
    strategy_interval = request.GET.get("interval", STRATEGY_INTERVAL).strip()
    # validate interval
    if strategy_interval not in SUPPORTED_INTERVALS:
        strategy_interval = STRATEGY_INTERVAL
    # optional year filter for breakout levels (e.g., 2024). If provided, only return levels
    # where the trigger_date or amavasya_calendar_date belongs to that year.
    year_filter = request.GET.get("year", "").strip()
    if year_filter and not year_filter.isdigit():
        year_filter = ""

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

        levels = strategy_result.get("levels", []) or []
        if year_filter:
            def _in_year(item):
                try:
                    td = item.get("trigger_date", "")
                    ad = item.get("amavasya_calendar_date", "")
                    return (td.startswith(year_filter) or ad.startswith(year_filter))
                except Exception:
                    return False

            levels = [l for l in levels if _in_year(l)]

        return JsonResponse({
            "status": bool(strategy_result.get("status")),
            "message": strategy_result.get("message", ""),
            "symbol": symbol,
            "interval": strategy_interval,
            "levels": levels,
            "meta": {
                **strategy_result.get("meta", {}),
                "broker_status": candle_result.get("status"),
                "broker_message": candle_result.get("message", ""),
                "raw_candles_count": len(raw_candles),
                "levels_count": len(levels),
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




########################################################
from django.http import JsonResponse
from django.shortcuts import render
from .pentagon import get_pentagon_data_by_year, load_pentagon_data

def pentagon_view(request):
    try:
        all_rows, min_year, max_year = load_pentagon_data()

        year_param = request.GET.get("year")
        if year_param:
            try:
                selected_year = int(year_param)
            except ValueError:
                selected_year = min_year
        else:
            selected_year = min_year

        data = get_pentagon_data_by_year(selected_year)

        context = {
            "year": data["year"],
            "rows": data["rows"],
            "total_records": data["total_records"],
            "min_year": data["min_year"],
            "max_year": data["max_year"],
        }
        return render(request, "pentagon.html", context)

    except FileNotFoundError:
        context = {
            "year": "",
            "rows": [],
            "total_records": 0,
            "min_year": "",
            "max_year": "",
            "error_message": "Pentagon CSV file not found.",
        }
        return render(request, "pentagon.html", context)

    except Exception as exc:
        context = {
            "year": "",
            "rows": [],
            "total_records": 0,
            "min_year": "",
            "max_year": "",
            "error_message": str(exc),
        }
        return render(request, "pentagon.html", context)


def pentagon_api_view(request):
    year_param = request.GET.get("year")

    if not year_param:
        return JsonResponse({
            "success": False,
            "message": "Year parameter is required.",
            "data": {}
        }, status=400)

    try:
        year = int(year_param)
    except ValueError:
        return JsonResponse({
            "success": False,
            "message": "Invalid year format.",
            "data": {}
        }, status=400)

    try:
        data = get_pentagon_data_by_year(year)

        if year < data["min_year"] or year > data["max_year"]:
            return JsonResponse({
                "success": False,
                "message": f"Year must be between {data['min_year']} and {data['max_year']}.",
                "data": {
                    "year": year,
                    "rows": [],
                    "total_records": 0,
                    "min_year": data["min_year"],
                    "max_year": data["max_year"],
                }
            }, status=400)

        return JsonResponse({
            "success": True,
            "message": "Pentagon data fetched successfully.",
            "data": data
        })

    except FileNotFoundError:
        return JsonResponse({
            "success": False,
            "message": "Pentagon CSV file not found.",
            "data": {}
        }, status=500)

    except Exception as exc:
        return JsonResponse({
            "success": False,
            "message": str(exc),
            "data": {}
        }, status=500)
    



##########################################################################
from .red_ball import get_red_ball_data_by_year, load_red_ball_data
def red_ball_view(request):
    try:
        all_rows, min_year, max_year = load_red_ball_data()

        year_param = request.GET.get("year")
        if year_param:
            try:
                selected_year = int(year_param)
            except ValueError:
                selected_year = min_year
        else:
            selected_year = min_year

        data = get_red_ball_data_by_year(selected_year)

        context = {
            "year": data["year"],
            "rows": data["rows"],
            "total_records": data["total_records"],
            "min_year": data["min_year"],
            "max_year": data["max_year"],
        }
        return render(request, "red_ball.html", context)

    except FileNotFoundError:
        context = {
            "year": "",
            "rows": [],
            "total_records": 0,
            "min_year": "",
            "max_year": "",
            "error_message": "Red Ball CSV file not found.",
        }
        return render(request, "red_ball.html", context)

    except Exception as exc:
        context = {
            "year": "",
            "rows": [],
            "total_records": 0,
            "min_year": "",
            "max_year": "",
            "error_message": str(exc),
        }
        return render(request, "red_ball.html", context)


def red_ball_api_view(request):
    year_param = request.GET.get("year")

    if not year_param:
        return JsonResponse({
            "success": False,
            "message": "Year parameter is required.",
            "data": {}
        }, status=400)

    try:
        year = int(year_param)
    except ValueError:
        return JsonResponse({
            "success": False,
            "message": "Invalid year format.",
            "data": {}
        }, status=400)

    try:
        data = get_red_ball_data_by_year(year)

        if year < data["min_year"] or year > data["max_year"]:
            return JsonResponse({
                "success": False,
                "message": f"Year must be between {data['min_year']} and {data['max_year']}.",
                "data": {
                    "year": year,
                    "rows": [],
                    "total_records": 0,
                    "min_year": data["min_year"],
                    "max_year": data["max_year"],
                }
            }, status=400)

        return JsonResponse({
            "success": True,
            "message": "Red Ball data fetched successfully.",
            "data": data
        })

    except FileNotFoundError:
        return JsonResponse({
            "success": False,
            "message": "Red Ball CSV file not found.",
            "data": {}
        }, status=500)

    except Exception as exc:
        return JsonResponse({
            "success": False,
            "message": str(exc),
            "data": {}
        }, status=500)