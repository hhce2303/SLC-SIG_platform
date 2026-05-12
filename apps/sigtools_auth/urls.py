from django.urls import path

from apps.sigtools_auth.views import WebLoginView, WebLogoutAllView, WebLogoutView, WebMeView

app_name = "sigtools_auth"

urlpatterns = [
    path("login/", WebLoginView.as_view(), name="web-login"),
    path("logout/", WebLogoutView.as_view(), name="web-logout"),
    path("logout-all/", WebLogoutAllView.as_view(), name="web-logout-all"),
    path("me/", WebMeView.as_view(), name="web-me"),
]
