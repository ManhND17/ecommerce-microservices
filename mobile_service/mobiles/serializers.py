from rest_framework import serializers
from .models import Mobile

class MobileSerializer(serializers.ModelSerializer):
    type = serializers.CharField(default='mobile', read_only=True)
    class Meta:
        model = Mobile
        fields = '__all__'
