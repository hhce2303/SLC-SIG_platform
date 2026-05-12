from rest_framework import serializers


class HistoryEntrySerializer(serializers.Serializer):
    role    = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField(allow_blank=True)


class ChatMessageSerializer(serializers.Serializer):
    message = serializers.CharField(
        max_length=4000,
        error_messages={"blank": "El mensaje no puede estar vacío."},
    )
    history = HistoryEntrySerializer(many=True, default=list)
