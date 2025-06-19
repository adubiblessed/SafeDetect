from django.urls import path
from .views import dashboard

app_name = 'users'

urlpatterns = [
    path('', dashboard, name='dashboard'),
]