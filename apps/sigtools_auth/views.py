"""
Views for the Sigtools web cookie auth system.
Orchestration only — all logic is in services.py.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import ServiceException
from apps.sigtools_auth import services
from apps.sigtools_auth.authentication import (
    COOKIE_NAME,
    SigtoolsCookieAuthentication,
)
from apps.sigtools_auth.models import PersonalAccessToken
from apps.sigtools_auth.serializers import (
    SigtoolsUserSerializer,
    WebLoginResponseSerializer,
    WebLoginSerializer,
)


class WebLoginView(APIView):
    """
    POST /api/v1/web-auth/login/
    Body: { username, password }

    Authenticates via LDAP → generates Sanctum-compatible token →
    sets HttpOnly cookie `sig_token` → returns user info + access_level.
    The raw token is NEVER returned in the body.
    """
    authentication_classes = []   # no auth required to login
    permission_classes = [AllowAny]

    @extend_schema(
        request=WebLoginSerializer,
        responses={200: WebLoginResponseSerializer},
        tags=["web-auth"],
    )
    def post(self, request: Request) -> Response:
        serializer = WebLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = services.login(
                username=serializer.validated_data["username"],
                password=serializer.validated_data["password"],
            )
        except ServiceException as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

        body = {
            "user": result["user"],
            "access_level": result["access_level"],
            "access_token": result["client_token"],
        }
        response = Response(body, status=status.HTTP_200_OK)
        services.set_cookie(response, result["client_token"])
        return response


class WebLogoutView(APIView):
    """
    POST /api/v1/web-auth/logout/
    Requires: valid sig_token cookie.

    Revokes the token in the DB and clears the cookie.
    """
    authentication_classes = [SigtoolsCookieAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None}, tags=["web-auth"])
    def post(self, request: Request) -> Response:
        client_token = request.COOKIES.get(COOKIE_NAME, "")
        if client_token:
            services.logout(client_token)

        response = Response(status=status.HTTP_204_NO_CONTENT)
        services.clear_cookie(response)
        return response


class WebMeView(APIView):
    """
    GET /api/v1/web-auth/me/
    Requires: valid sig_token cookie.

    Returns the authenticated SigtoolsUser profile.
    """
    authentication_classes = [SigtoolsCookieAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SigtoolsUserSerializer}, tags=["web-auth"])
    def get(self, request: Request) -> Response:
        # request.user is a SigtoolsWebUser (set by SigtoolsCookieAuthentication)
        sig_user = request.user.sigtools_user
        data = {
            "id": sig_user.pk,
            "name": sig_user.name,
            "email": sig_user.email,
            "username": sig_user.username,
        }
        return Response(data, status=status.HTTP_200_OK)


class WebLogoutAllView(APIView):
    """
    POST /api/v1/web-auth/logout-all/
    Requires: valid sig_token cookie or Bearer token.

    Revokes ALL active tokens for the current user (all devices/sessions).
    Useful after a password change or suspected account compromise.
    """
    authentication_classes = [SigtoolsCookieAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: None}, tags=["web-auth"])
    def post(self, request: Request) -> Response:
        sig_user = request.user.sigtools_user

        deleted_count, _ = PersonalAccessToken.objects.using("sigtools").filter(
            tokenable_type="App\\Models\\User",
            tokenable_id=sig_user.pk,
        ).delete()

        response = Response(
            {"message": f"Logged out from {deleted_count} session(s)."},
            status=status.HTTP_200_OK,
        )
        services.clear_cookie(response)
        return response
