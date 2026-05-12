from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users import services
from apps.users.serializers import (
    LoginResponseSerializer,
    LoginSerializer,
    LogoutSerializer,
    StationOptionSerializer,
    StatusSerializer,
    UserProfileSerializer,
    UsernameItemSerializer,
)


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses={200: LoginResponseSerializer})
    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = services.login(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
            station_id=serializer.validated_data["station_id"],
        )

        return Response(result, status=status.HTTP_200_OK)


class AvailableStationsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: StationOptionSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """Return stations that are not currently occupied."""
        stations = services.get_available_stations()
        return Response(stations, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=LogoutSerializer, responses={204: None})
    def post(self, request: Request) -> Response:
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        daily_user = request.daily_user  # type: ignore[attr-defined]
        if daily_user is None:
            return Response(
                {"detail": "Usuario no encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        services.logout(
            daily_user=daily_user,
            refresh_token=serializer.validated_data.get("refresh"),
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserProfileSerializer})
    def get(self, request: Request) -> Response:
        daily_user = request.daily_user  # type: ignore[attr-defined]
        if daily_user is None:
            return Response(
                {"detail": "Usuario no encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        profile = services.get_profile(daily_user)
        return Response(profile, status=status.HTTP_200_OK)


class StatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=StatusSerializer, responses={204: None})
    def patch(self, request: Request) -> Response:
        daily_user = request.daily_user  # type: ignore[attr-defined]
        if daily_user is None:
            return Response(
                {"detail": "Usuario no encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = StatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        services.update_status(
            daily_user=daily_user,
            new_status=serializer.validated_data["status"],
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class UsernamesView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: UsernameItemSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """Return all usernames for autocomplete on the login form."""
        from apps.core.models import UserName

        usernames = UserName.objects.values_list("user_name", flat=True).order_by("user_name")
        data = [{"username": name} for name in usernames]
        return Response(data, status=status.HTTP_200_OK)
