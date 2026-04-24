from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import RegisterForm, LoginForm, UserProfileForm, ProfilePictureForm
from .models import User

# Create your views here.
def register(request):
    form = RegisterForm()
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful. You can log in now.')
            return redirect('accounts:login')
        else:
            messages.error(request, 'Registration failed. Please fix the errors below and try again.')
            return render(request, 'accounts/register.html', {'form': form})
    return render(request, 'accounts/register.html', {'form': form})


def login(request):
    form = LoginForm()
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                auth_login(request, user)
                return redirect('detection:dashboard') 
            else:
                form.add_error(None, 'Login failed: invalid username or password.')
                messages.error(request, 'Login failed: invalid username or password.')
        else:
            messages.error(request, 'Login failed. Please enter both username and password.')
    return render(request, 'accounts/login.html', {'form': form})

def logout(request):
    if request.method == 'POST':
        from django.contrib.auth import logout as auth_logout
        auth_logout(request)
        return redirect('accounts:login')
    return render(request, 'accounts/logout.html')


@login_required
def profile_view(request):
    """Display user profile"""
    return render(request, 'accounts/profile.html', {'user': request.user})


@login_required
def edit_profile(request):
    """Edit user profile including profile picture"""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=request.user)
    
    return render(request, 'accounts/edit_profile.html', {'form': form})


@login_required
def upload_profile_picture(request):
    """Simple page to upload profile picture for face authentication"""
    if request.method == 'POST':
        form = ProfilePictureForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Profile picture uploaded successfully! You\'re now authenticated for intruder detection.')
            return redirect('accounts:profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ProfilePictureForm(instance=request.user)
    
    return render(request, 'accounts/upload_profile_picture.html', {'form': form})

