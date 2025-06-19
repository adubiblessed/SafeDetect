from django import forms
from .models import Detection

class DetectionUploadForm(forms.ModelForm):
    class Meta:
        model = Detection
        fields = ['image', 'video']
    
    def clean(self):
        cleaned_data = super().clean()
        image = cleaned_data.get('image')
        video = cleaned_data.get('video')

        if not image and not video:
            raise forms.ValidationError("You must upload either an image or a video.")
        if image and video:
            raise forms.ValidationError("Upload only one: image or video, not both.")
        
        return cleaned_data
