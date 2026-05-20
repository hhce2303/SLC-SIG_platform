import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication

from .serializers import ChatMessageSerializer
from . import services

logger = logging.getLogger(__name__)


class ChatbotMessageView(APIView):
    """
    POST /api/v1/chatbot/message/

    Accepts a user message and optional conversation history.
    Returns Claude's text reply after tool resolution.
    Requires authenticated admin user.
    """
    # SessionAuthentication: Django admin session cookies from the dashboard.
    # JWTAuthentication: API clients (PowerShell, curl, etc.) with Bearer token.
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        ser = ChatMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        try:
            reply = services.handle_message(
                message=ser.validated_data["message"],
                history=ser.validated_data.get("history", []),
                user=request.user,
            )
        except RuntimeError as exc:
            # Missing or placeholder API key
            return Response(
                {"error": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as exc:
            # Anthropic API errors, context overflow, etc.
            logger.exception("Chatbot error: %s", exc)
            return Response(
                {"error": f"Error interno del asistente: {type(exc).__name__}: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"reply": reply})


class ChatbotPingView(APIView):
    """
    GET /api/v1/chatbot/ping/

    Verifies Anthropic API key and network connectivity.
    Returns list of available models without consuming message tokens.
    Requires authenticated admin user.
    """
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        try:
            result = services.ping()
        except RuntimeError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as exc:
            logger.exception("Chatbot ping error: %s", exc)
            return Response(
                {"error": f"Error de conectividad: {type(exc).__name__}: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result)
