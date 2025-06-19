from django.shortcuts import render
from detection.models import Detection

# Create your views here.
def dashboard(request):
    user = request.user
    if not user.is_authenticated:
        return render(request, 'accounts/login.html')
    return render(request, 'dashboard/home.html', {'user': user})

def detection_history(request):
    detection = Detection.objects.filter(user=request.user).order_by('-timestamp')