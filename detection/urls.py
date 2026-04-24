from django.urls import path
from .views import upload_detection, detection_success, upload_detection_test, dashboard_new, verify_face, service_worker, dashboard_data

app_name = 'detection'

urlpatterns = [
    path('upload/', upload_detection, name='upload_detection'),
    path('success/', detection_success, name='detection_success'),
    #path('video_feed/', video_feed, name='video_feed'),
    #path('stream/', stream_page, name='stream_page'),
    #path('detection_status/', detection_status, name='detection_status'),


    path('api/detections/', upload_detection_test, name='upload_detection_new'),
    path('api/verify-face/', verify_face, name='verify_face'),
    path('sw.js', service_worker, name='service_worker'),
    path('dashboard/data/', dashboard_data, name='dashboard_data'),
    path('dashboard/', dashboard_new, name='dashboard')
]