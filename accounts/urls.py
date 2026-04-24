from django.urls import path
from .views import register, login, logout, profile_view, edit_profile, upload_profile_picture

app_name = 'accounts'

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),
    path('profile/', profile_view, name='profile'),
    path('edit-profile/', edit_profile, name='edit_profile'),
    path('upload-profile-picture/', upload_profile_picture, name='upload_profile_picture'),
]