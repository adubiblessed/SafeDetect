from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from .forms import DetectionUploadForm
from .models import Detection
from django.contrib.auth.decorators import login_required
from .services import run_yolo_detection
from .face_detection import detect_faces, annotate_faces
import cv2
import numpy as np

# Conditional import of face recognition utilities
try:
    from .face_recognition_utils import get_face_encoding_from_array, is_user_face, extract_face_crop
    FACE_RECOGNITION_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    FACE_RECOGNITION_AVAILABLE = False

@login_required
def upload_detection(request):
    if request.method == 'POST':
        form = DetectionUploadForm(request.POST, request.FILES)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.save()

            
            if instance.image:
                result = run_yolo_detection(instance.image.path)
            else:
                result = run_yolo_detection(instance.video.path)

           
            if result:
                instance.label = result['label']
                instance.confidence = result['confidence']
                instance.alert_triggered = result['alert']
                instance.alert_message = result.get('message', '')
                instance.save()

            if instance.image:
                face_result = detect_faces(instance.image.path)

                if face_result['faces_detected'] > 0:
                    # Check if detected face matches user's profile picture
                    is_user, confidence = check_if_user_face(
                        request.user,
                        instance.image.path,
                        face_result['boxes']
                    )
                    
                    # Annotate the image and get path to annotated version
                    annotated_path = annotate_faces(instance.image.path, face_result['boxes'])

                    # Only trigger alert if it's NOT the user's face
                    if is_user:
                        instance.alert_triggered = False
                        instance.alert_message = f"Recognized: {request.user.username} (Confidence: {confidence:.2%})"
                    else:
                        instance.alert_triggered = True
                        instance.alert_message = f"⚠️ Unknown face detected! {face_result['faces_detected']} face(s) - Confidence: {confidence:.2%}"

            
            instance.save()

            return redirect('detection:detection_success')  
    else:
        form = DetectionUploadForm()
    
    return render(request, 'detection/upload.html', {'form': form})


def check_if_user_face(user, image_path, face_boxes, tolerance=0.6):
    """
    Check if detected faces match the user's profile picture.
    Returns True only if user has a profile picture and face matches.
    """
    # Return False if face recognition is not available
    if not FACE_RECOGNITION_AVAILABLE:
        return False, 0.0
    
    # Check if user has profile picture
    if not user.profile_picture:
        return False, 0.0
    
    try:
        # Load the detection image
        image = cv2.imread(image_path)
        if image is None:
            return False, 0.0
        
        # Try to match with multiple face crops (in case multiple faces detected)
        for i, face_box in enumerate(face_boxes):
            try:
                face_crop = extract_face_crop(image, face_box)
                
                # Compare with user's profile picture
                is_match, conf = is_user_face(
                    user.profile_picture.path,
                    face_crop,
                    tolerance=tolerance
                )
                
                if is_match:
                    return True, conf
                    
            except Exception as e:
                print(f"Error processing face box {i}: {e}")
                continue
        
        # Return lowest confidence if no match
        return False, 0.0
        
    except Exception as e:
        print(f"Error checking if user face: {e}")
        return False, 0.0


@login_required
def detection_success(request):
    latest_detection = Detection.objects.filter(user=request.user).order_by('-timestamp').first()
    return render(request, 'detection/success.html', {'detection': latest_detection})


def service_worker(request):
        script = """const CACHE_NAME = 'safedetect-media-v1';

self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);

    if (request.method !== 'GET') {
        return;
    }

    if (request.destination === 'image' || url.pathname.startsWith('/media/')) {
        event.respondWith((async () => {
            const cache = await caches.open(CACHE_NAME);
            const cachedResponse = await cache.match(request);

            if (cachedResponse) {
                event.waitUntil((async () => {
                    try {
                        const freshResponse = await fetch(request);
                        if (freshResponse && freshResponse.ok) {
                            await cache.put(request, freshResponse.clone());
                        }
                    } catch (error) {
                        return;
                    }
                })());

                return cachedResponse;
            }

            const freshResponse = await fetch(request);
            if (freshResponse && freshResponse.ok) {
                await cache.put(request, freshResponse.clone());
            }
            return freshResponse;
        })());
    }
});
"""
        return HttpResponse(script, content_type='application/javascript')










from django.http import StreamingHttpResponse
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












from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Detection_new
from .serializers import DetectionSerializer



@api_view(['POST'])
def upload_detection_test(request):
    try:
        print("🟨 Incoming data:", request.data)
        serializer = DetectionSerializer(data=request.data)
        if serializer.is_valid():
            from accounts.models import User

            user_id = request.data.get('user_id')
            if not user_id:
                return Response({'error': 'user_id is required'}, status=400)

            user = User.objects.filter(id=user_id).first()
            if user is None:
                return Response({'error': f'User {user_id} not found'}, status=404)

            serializer.save(user=user)
            print("✅ Detection saved.")
            return Response({'message': 'Detection saved.'}, status=201)
        else:
            print("❌ Validation errors:", serializer.errors)
            return Response(serializer.errors, status=400)
    except Exception as e:
        print("🔥 Exception:", str(e))
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
def verify_face(request):
    """
    API endpoint to verify if detected face belongs to a registered user.
    Called from sep_detection/detection.py for real-time camera monitoring.
    
    Expected POST data:
    - user_id: ID of the user to verify against
    - face_image: Image file of the detected face
    
    Returns:
    {
        'is_user': bool,
        'confidence': float (0-1),
        'should_alert': bool,
        'message': str
    }
    """
    try:
        from accounts.models import User
        import tempfile
        
        # Check if face recognition is available
        if not FACE_RECOGNITION_AVAILABLE:
            return Response({
                'is_user': False,
                'confidence': 0.0,
                'should_alert': True,
                'message': 'face_recognition library not installed. Install with: pip install face_recognition'
            }, status=200)
        
        from .face_recognition_utils import is_user_face
        
        user_id = request.data.get('user_id')
        face_image = request.FILES.get('face_image')
        
        if not user_id or not face_image:
            return Response({
                'error': 'user_id and face_image are required',
                'should_alert': True  # Alert if verification fails
            }, status=400)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({
                'error': f'User {user_id} not found',
                'should_alert': True
            }, status=404)
        
        # Check if user has a profile picture
        if not user.profile_picture:
            return Response({
                'is_user': False,
                'confidence': 0.0,
                'should_alert': True,
                'message': 'User has no profile picture set. Cannot verify identity.'
            }, status=200)
        
        # Save face image temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
            for chunk in face_image.chunks():
                tmp_file.write(chunk)
            tmp_path = tmp_file.name
        
        try:
            # Convert saved image to cv2 format
            face_array = cv2.imread(tmp_path)
            
            if face_array is None:
                return Response({
                    'is_user': False,
                    'confidence': 0.0,
                    'should_alert': True,
                    'message': 'Could not read face image'
                }, status=200)
            
            # Verify face
            is_match, confidence = is_user_face(
                user.profile_picture.path,
                face_array,
                tolerance=0.6
            )
            
            return Response({
                'is_user': is_match,
                'confidence': float(confidence),
                'should_alert': not is_match,  # Alert only if NOT the user
                'message': f"User: {user.username} - Match: {is_match} (Confidence: {confidence:.2%})"
            }, status=200)
            
        finally:
            # Clean up temp file
            import os
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    except Exception as e:
        print(f"Error verifying face: {e}")
        return Response({
            'error': str(e),
            'should_alert': True
        }, status=500)


@login_required
def dashboard_new(request):
    user_detections = Detection_new.objects.filter(user=request.user).order_by('-timestamp')
    detections = user_detections[:24]
    profile_picture = getattr(request.user, 'profile_picture', None)
    return render(
        request,
        'detection/dashboard.html',
        {
            'detections': detections,
            'profile_picture': profile_picture,
            'detection_count': user_detections.count(),
            'current_user_id': request.user.id,
        },
    )


@login_required
def dashboard_data(request):
    user_detections = Detection_new.objects.filter(user=request.user).order_by('-timestamp')[:24]
    payload = []

    for d in user_detections:
        payload.append(
            {
                'id': d.id,
                'snapshot_url': d.snapshot.url if d.snapshot else '',
                'face_url': d.face_image.url if d.face_image else '',
                'timestamp_display': d.timestamp.strftime('%b %d, %Y %H:%M'),
                'snapshot_name': d.snapshot.name if d.snapshot else 'Image',
                'face_name': d.face_image.name if d.face_image else 'Face',
                'has_face': bool(d.face_image),
            }
        )

    return JsonResponse(
        {
            'count': Detection_new.objects.filter(user=request.user).count(),
            'detections': payload,
        }
    )
