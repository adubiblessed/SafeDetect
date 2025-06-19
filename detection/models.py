from django.db import models
from accounts.models import User
from django.core.exceptions import ValidationError
# Create your models here.

class Detection(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='detections/images/', blank=True, null=True)
    video = models.FileField(upload_to='detections/video/', blank=True, null=True)
    label = models.CharField(max_length=50, null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    alert_triggered = models.BooleanField(default=False)
    alert_message = models.TextField(blank=True, null=True)
    media_type = models.CharField(max_length=10, choices=[('image', 'Image'), ('video', 'Video')])
    annotated_image = models.ImageField(upload_to='detections/annotated/', blank=True, null=True)

    
    def __str__(self):
        return f"Detection by {self.user.username} at {self.timestamp} - {self.label} ({self.media_type})"

    def clean(self):
        if not self.image and not self.video:
            raise ValidationError("Either image or video must be provided.")
        if self.image and self.video:
            raise ValidationError("Upload either an image or a video, not both.")




class Detection_new(models.Model):
    uuid = models.CharField(max_length=100)
    snapshot = models.ImageField(upload_to='snapshots/')
    face_image = models.ImageField(upload_to='faces/')
    timestamp = models.DateTimeField(auto_now_add=True)