from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class User(AbstractUser):
    phone_no = models.CharField(max_length=15, blank=True, null=True)
    email_address = models.EmailField(max_length=254, unique=True, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True, help_text="Upload your photo for intruder detection authentication")