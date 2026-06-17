from django.urls import path
from . import views

urlpatterns = [
    path("", views.home_redirect, name="home"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("forgot-password/", views.forgot_password_view, name="forgot_password"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("api/broker-health/", views.broker_health_view, name="broker_health"),
    path("api/candles/", views.candles_api_view, name="candles_api"),

    path("reversal-dates/", views.reversal_dates_view, name="reversal_dates"),
    path("api/reversal-dates/", views.reversal_dates_api_view, name="reversal_dates_api"),

    path("amavasya/", views.amavasya_view, name="amavasya"),
    path("api/amavasya/", views.amavasya_api_view, name="amavasya_api"),

    path("purnima/", views.purnima_view, name="purnima"),
    path("api/purnima/", views.purnima_api_view, name="purnima_api"),

    path("trayodashi/", views.trayodashi_view, name="trayodashi"),
    path("api/trayodashi/", views.trayodashi_api_view, name="trayodashi_api"),

    path("pushya/", views.pushya_view, name="pushya"),
    path("api/pushya/", views.pushya_api_view, name="pushya_api"),

    path("calendar/", views.calendar_view, name="calendar"),

    path("api/notifications/", views.notifications_list_view, name="notifications_list"),
    path("api/notifications/mark-popup-shown/", views.mark_notifications_popup_shown_view, name="mark_notifications_popup_shown"),
    path("api/notifications/mark-read/", views.mark_notification_read_view, name="mark_notification_read"),
]