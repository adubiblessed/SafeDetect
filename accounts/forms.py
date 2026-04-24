from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class RegisterForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'phone_no']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            return email

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('A user with this email already exists.')

        return email

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput(), required=True)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get("username")
        password = cleaned_data.get("password")

        if not username or not password:
            raise forms.ValidationError("Both fields are required.")
        
        return cleaned_data


class UserProfileForm(forms.ModelForm):
    """Form for users to update their profile, including profile picture"""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_no', 'profile_picture']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_no': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'help_text': 'Upload a clear photo of your face for intruder detection authentication'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profile_picture'].help_text = 'Upload a clear photo of your face for intruder detection authentication'


class ProfilePictureForm(forms.ModelForm):
    """Simple form for just uploading profile picture"""
    class Meta:
        model = User
        fields = ['profile_picture']
        widgets = {
            'profile_picture': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            })
        }
    
    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if picture:
            # Check file size (max 5MB)
            if picture.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image file too large (max 5MB)")
            
            # Check file type
            valid_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if hasattr(picture, 'content_type') and picture.content_type not in valid_types:
                raise forms.ValidationError("Invalid image format. Use JPEG, PNG, GIF, or WebP")
        
        return picture