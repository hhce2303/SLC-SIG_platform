from django.urls import path
from .views import ChatbotMessageView, ChatbotPingView

urlpatterns = [
    path("message/", ChatbotMessageView.as_view(), name="chatbot-message"),
    path("ping/",    ChatbotPingView.as_view(),    name="chatbot-ping"),
]
