from rest_framework import serializers
from .models import Detection_new 

class DetectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Detection_new
        fields = ['uuid', 'snapshot', 'face_image']
