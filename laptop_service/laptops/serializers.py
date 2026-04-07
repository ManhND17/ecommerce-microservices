from rest_framework import serializers
from .models import Laptop

class LaptopSerializer(serializers.ModelSerializer):
    type = serializers.CharField(default='laptop', read_only=True)
    class Meta:
        model = Laptop
        fields = '__all__'
