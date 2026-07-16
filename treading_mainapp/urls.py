from django.urls import path
from django.views.generic.base import RedirectView
from . import views


urlpatterns = [
    path("", views.home_redirect, name="home"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("api/broker-health/", views.broker_health_view, name="broker_health"),
    path("api/candles/", views.candles_api_view, name="candles_api"),

    path("reversal-dates/", RedirectView.as_view(url="/degree-date/", permanent=True, query_string=True)),
    path("degree-date/", views.reversal_dates_view, name="reversal_dates"),
    path("api/reversal-dates/", RedirectView.as_view(url="/api/degree-date/", permanent=True, query_string=True)),
    path("api/degree-date/", views.reversal_dates_api_view, name="reversal_dates_api"),

    path("amavasya/", RedirectView.as_view(url="/dark-day/", permanent=True, query_string=True)),
    path("dark-day/", views.amavasya_view, name="amavasya"),
    path("api/amavasya/", views.amavasya_api_view, name="amavasya_api"),

    path("purnima/", RedirectView.as_view(url="/light-day/", permanent=True, query_string=True)),
    path("light-day/", views.purnima_view, name="purnima"),
    path("api/purnima/", views.purnima_api_view, name="purnima_api"),

    path("trayodashi/", RedirectView.as_view(url="/intra-day/", permanent=True, query_string=True)),
    path("intra-day/", views.trayodashi_view, name="trayodashi"),
    path("api/trayodashi/", views.trayodashi_api_view, name="trayodashi_api"),

    path("pushya/", RedirectView.as_view(url="/flower/", permanent=True, query_string=True)),
    path("flower/", views.pushya_view, name="pushya"),
    path("api/pushya/", views.pushya_api_view, name="pushya_api"),

    path("moon-marse/", RedirectView.as_view(url="/top-bottom/", permanent=True, query_string=True)),
    path("top-bottom/", views.moon_marse_view, name="moon_marse"),
    path("api/moon-marse/", views.moon_marse_api_view, name="moon_marse_api"),

    path("calendar/", views.calendar_view, name="calendar"),

    path("gapup/", RedirectView.as_view(url="/dd-stock/", permanent=True, query_string=True)),
    path("dd-stock/", views.gapupview, name="gapup"),
    path("gapup/refresh/", views.gapuprefreshview, name="gapuprefresh"),
    path("api/gapup/status/", views.gapupstatusapiview, name="gapupstatusapi"),
    path("api/gapup/runtime/", views.gapupscanruntimeapiview, name="gapupscanruntimeapi"),

    path("notifications/", views.notifications_page_view, name="notifications_page"),
    path("api/notifications/", views.notifications_list_view, name="notifications_list"),
    path("api/notifications/mark-popup-shown/", views.mark_notifications_popup_shown_view, name="mark_notifications_popup_shown"),
    path("api/notifications/mark-read/", views.mark_notification_read_view, name="mark_notification_read"),

    path("pinbar/", views.pinbar_view, name="pinbar"),
    path("api/pinbar/", views.pinbar_api_view, name="pinbar_api"),

    path("api/amavasya-strategy/", views.amavasya_strategy_api_view, name="amavasya_strategy_api"),
    
    path("pentagon/", views.pentagon_view, name="pentagon"),
    path("api/pentagon/", views.pentagon_api_view, name="pentagon_api"),

    path("red-ball/", views.red_ball_view, name="red_ball"),
    path("api/red-ball/", views.red_ball_api_view, name="red_ball_api"),
]
