from django.shortcuts import render, redirect
from .forms import DetectionUploadForm
from .models import Detection
from django.contrib.auth.decorators import login_required
from .services import run_yolo_detection
from .face_detection import detect_faces, annotate_faces 

@login_required
def upload_detection(request):
    if request.method == 'POST':
        form = DetectionUploadForm(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.save()

            # 🔁 Trigger YOLOv8 detection on the uploaded file
            if instance.image:
                result = run_yolo_detection(instance.image.path)
            else:
                result = run_yolo_detection(instance.video.path)

            # Save detection results
            if result:
                instance.label = result['label']
                instance.confidence = result['confidence']
                instance.alert_triggered = result['alert']
                instance.alert_message = result.get('message', '')
                instance.save()

            if instance.image:
                face_result = detect_faces(instance.image.path)

                if face_result['faces_detected'] > 0:
                # Annotate the image and get path to annotated version
                    annotated_path = annotate_faces(instance.image.path, face_result['boxes'])

                    # Update the Detection instance
                    instance.alert_triggered = True
                    instance.alert_message = f"{face_result['faces_detected']} face(s) detected in image."

                    # instance.annotated_image_path = annotated_path

            # Optional: Save annotated path if you want
            instance.save()

            return redirect('detection:detection_success')  
    else:
        form = DetectionUploadForm()
    
    return render(request, 'detection/upload.html', {'form': form})


@login_required
def detection_success(request):
    latest_detection = Detection.objects.filter(user=request.user).order_by('-timestamp').first()
    return render(request, 'detection/success.html', {'detection': latest_detection})










from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render
# from .camera import camera

# def stream_page(request):
#     return render(request, "detection/video_stream.html")

# def video_feed(request):
#     def gen(camera):
#         while True:
#             frame = camera.get_frame()
#             if frame:
#                 yield (b'--frame\r\n'
#                        b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
#     return StreamingHttpResponse(gen(camera), content_type="multipart/x-mixed-replace; boundary=frame")

# def detection_status(request):
#     return JsonResponse({'detected': camera.person_detected})











# views.py
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Detection_new
from .serializers import DetectionSerializer

from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import exception_handler


@api_view(['POST'])
def upload_detection_test(request):
    try:
        print("🟨 Incoming data:", request.data)
        serializer = DetectionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            print("✅ Detection saved.")
            return Response({'message': 'Detection saved.'}, status=201)
        else:
            print("❌ Validation errors:", serializer.errors)
            return Response(serializer.errors, status=400)
    except Exception as e:
        print("🔥 Exception:", str(e))
        return Response({'error': str(e)}, status=500)


def dashboard_new(request):
    detections = Detection_new.objects.order_by('-timestamp')[:20]  # latest 20
    return render(request, 'detection/dashboard.html', {'detections': detections})
