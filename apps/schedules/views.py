"""Schedules API views — thin orchestration layer."""

from __future__ import annotations

from datetime import date

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.schedules import selectors, services
from apps.schedules.serializers import (
    AvailableSlotReadSerializer,
    AvailableSlotWriteSerializer,
    CancellationRequestHandleSerializer,
    CancellationRequestReadSerializer,
    CancellationRequestWriteSerializer,
    NotificationMarkReadSerializer,
    NotificationReadSerializer,
    NotificationWriteSerializer,
    ScheduleBulkSerializer,
    ScheduleReadSerializer,
    ScheduleWriteSerializer,
    ShiftTypeSerializer,
    SlotClaimReadSerializer,
    SlotClaimWriteSerializer,
    SquadSerializer,
)


# ── Core data ──────────────────────────────────────────────────────────────

class SquadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qs = selectors.get_all_squads()
        data = SquadSerializer(qs, many=True).data
        return Response({"data": data})


class SquadToggleEligibilityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, squad_id: int) -> Response:
        squad = services.toggle_squad_eligibility(squad_id)
        return Response(SquadSerializer(squad).data)


class ShiftTypeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qs = selectors.get_all_shift_types()
        data = ShiftTypeSerializer(qs, many=True).data
        return Response({"data": data})


# ── Schedules ──────────────────────────────────────────────────────────────

class ScheduleListView(APIView):
    """GET schedules by date range (?start=YYYY-MM-DD&end=YYYY-MM-DD)."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if not start or not end:
            return Response(
                {"detail": "start and end query params required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = selectors.get_schedules_by_range(
            date.fromisoformat(start),
            date.fromisoformat(end),
        )
        data = ScheduleReadSerializer(qs, many=True).data
        return Response({"data": data})


class ScheduleUpsertView(APIView):
    """Upsert a single schedule."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        ser = ScheduleWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        schedule = services.upsert_schedule(**ser.validated_data)
        return Response(
            ScheduleReadSerializer(schedule).data,
            status=status.HTTP_200_OK,
        )


class ScheduleBulkUpsertView(APIView):
    """Upsert schedules in bulk."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        ser = ScheduleBulkSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.upsert_schedules_bulk(ser.validated_data["schedules"])
        return Response({"detail": "ok"})


class ScheduleDeleteRangeView(APIView):
    """DELETE schedules by date range (?start=YYYY-MM-DD&end=YYYY-MM-DD)."""

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request) -> Response:
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if not start or not end:
            return Response(
                {"detail": "start and end query params required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        count = services.delete_schedules_by_range(
            date.fromisoformat(start),
            date.fromisoformat(end),
        )
        return Response({"deleted": count})


# ── Slots ──────────────────────────────────────────────────────────────────

class AvailableSlotListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        start = request.query_params.get("start")
        end = request.query_params.get("end")
        if not start or not end:
            return Response(
                {"detail": "start and end query params required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = selectors.get_slots_by_range(
            date.fromisoformat(start),
            date.fromisoformat(end),
        )
        data = AvailableSlotReadSerializer(qs, many=True).data
        return Response({"data": data})

    def post(self, request: Request) -> Response:
        ser = AvailableSlotWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        slot = services.create_available_slot(**ser.validated_data)
        return Response(
            AvailableSlotReadSerializer(slot).data,
            status=status.HTTP_201_CREATED,
        )


class AvailableSlotDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, slot_id: int) -> Response:
        services.delete_available_slot(slot_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Slot Claims ────────────────────────────────────────────────────────────

class SlotClaimListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qs = selectors.get_all_slot_claims()
        data = SlotClaimReadSerializer(qs, many=True).data
        return Response({"data": data})


class SlotClaimCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        ser = SlotClaimWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        claim = services.claim_slot(**ser.validated_data)
        return Response(
            SlotClaimReadSerializer(claim).data,
            status=status.HTTP_201_CREATED,
        )


class SlotClaimDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        ser = SlotClaimWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.unclaim_slot(**ser.validated_data)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Cancellation Requests ─────────────────────────────────────────────────

class CancellationRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        qs = selectors.get_pending_cancellation_requests()
        data = CancellationRequestReadSerializer(qs, many=True).data
        return Response({"data": data})

    def post(self, request: Request) -> Response:
        ser = CancellationRequestWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            cr = services.create_cancellation_request(**ser.validated_data)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            CancellationRequestReadSerializer(cr).data,
            status=status.HTTP_201_CREATED,
        )


class CancellationRequestHandleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, request_id: int) -> Response:
        ser = CancellationRequestHandleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cr = services.handle_cancellation_request(
            request_id,
            approve=ser.validated_data["approve"],
        )
        return Response(CancellationRequestReadSerializer(cr).data)


# ── Notifications ──────────────────────────────────────────────────────────

class NotificationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user_id = request.query_params.get("user_id")
        is_admin = request.query_params.get("is_admin", "false").lower() == "true"
        qs = selectors.get_notifications(
            user_id=int(user_id) if user_id else None,
            is_admin=is_admin,
        )
        data = NotificationReadSerializer(qs, many=True).data
        return Response({"data": data})

    def post(self, request: Request) -> Response:
        ser = NotificationWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        notif = services.create_notification(**ser.validated_data)
        return Response(
            NotificationReadSerializer(notif).data,
            status=status.HTTP_201_CREATED,
        )


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        ser = NotificationMarkReadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        count = services.mark_notifications_as_read(ser.validated_data["ids"])
        return Response({"updated": count})
