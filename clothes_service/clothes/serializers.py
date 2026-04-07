from rest_framework import serializers
from .models import Clothes

class ClothesSerializer(serializers.ModelSerializer):
    type = serializers.CharField(default='clothes', read_only=True)
    class Meta:
        model = Clothes
        fields = '__all__'
