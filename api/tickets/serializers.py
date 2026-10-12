from rest_framework import serializers

from .models import Ticket


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ["id", "title", "description", "status", "priority", "created_at"]
        read_only_fields = ["id", "created_at"]


class TicketUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ["status", "priority"]

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide a status or priority to update.")
        return attrs
