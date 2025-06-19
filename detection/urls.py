from django.urls import path
from .views import upload_detection, detection_success, upload_detection_test, dashboard_new

app_name = 'detection'

urlpatterns = [
    path('', upload_detection, name='upload_detection'),
    path('success/', detection_success, name='detection_success'),
    #path('video_feed/', video_feed, name='video_feed'),
    #path('stream/', stream_page, name='stream_page'),
    #path('detection_status/', detection_status, name='detection_status'),


    path('api/detections/', upload_detection_test, name='upload_detection_new'),
    path('dashboard_new/', dashboard_new, name='dashboard')
]