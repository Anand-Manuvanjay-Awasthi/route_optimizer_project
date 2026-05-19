from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    start = serializers.CharField()
    end = serializers.CharField()

    def validate_start(self, value):
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("Start location name is required.")
        return value.strip()

    def validate_end(self, value):
        if not value or len(value.strip()) < 2:
            raise serializers.ValidationError("End location name is required.")
        return value.strip()
