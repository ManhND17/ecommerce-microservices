from rest_framework import serializers
from .models import SearchLog, InteractionLog

class SearchLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchLog
        fields = '__all__'

class InteractionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = InteractionLog
        fields = '__all__'
