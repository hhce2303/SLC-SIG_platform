from django.urls import path

from apps.users.views import AvailableStationsView, LoginView, LogoutView, MeView, StatusView, UsernamesView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    # No token/refresh/ — post ADR-0001 the access token has no refresh
    # counterpart (~10 year lifetime, "refresh" is always null in the
    # login response). See docs/arc42/daily/decisions/0001-....md.
    path("me/", MeView.as_view(), name="auth-me"),
    path("me/status/", StatusView.as_view(), name="auth-me-status"),
    path("stations/available/", AvailableStationsView.as_view(), name="auth-stations-available"),
    path("usernames/", UsernamesView.as_view(), name="auth-usernames"),
]
