# SafeDetect Face Authentication Setup Guide

## Overview

This guide explains how to set up and use the new face authentication feature in SafeDetect. This feature prevents intruder alerts when the detected face matches the user's profile picture.

## Installation

### 1. Install Required Dependencies

```bash
pip install face_recognition
```

If you encounter issues with `face_recognition` on Windows, you may need to install additional dependencies:

```bash
pip install face_recognition numpy dlib
```

### 2. Run Database Migrations

```bash
python manage.py migrate accounts
```

This creates the `profile_picture` field in the User model.

## User Setup

### Step 1: Upload Profile Picture

1. Log in to your SafeDetect account
2. Click on your profile (top menu)
3. Click **"Upload Profile Picture"** button
4. Select a clear photo of your face
5. Click **"Upload & Save"**

**Best Practices for Photo:**
- Clear, frontal face photo
- Good lighting (no backlighting)
- No sunglasses or major accessories
- Distance: 1-2 meters from camera
- Neutral or natural expression

### Step 2: Configure Webcam Monitoring (Optional)

For real-time monitoring with face authentication:

```bash
# Set your user ID as environment variable
set SAFEDETECT_USER_ID=<your_user_id>

# Then run the detection script
cd sep_detection
python detection.py
```

## How It Works

### Web Interface (Manual Upload)

1. User uploads image/video via detection upload page
2. System detects faces using YuNet
3. Face authentication compares with user's profile picture
4. If match: logs as "Recognized" (no alert)
5. If no match: triggers "Unknown face" alert

### Webcam Monitoring (Real-time)

1. Continuous webcam monitoring for face detection
2. Periodically captures face snapshots
3. Sends to Django API for verification
4. Calls `/detection/api/verify-face/` endpoint
5. Compares with user's profile picture
6. Only sends Telegram alert if unknown face

## API Endpoint

### Verify Face

**Endpoint:** `POST /detection/api/verify-face/`

**Request:**
```json
{
    "user_id": 1,
    "face_image": <file>
}
```

**Response (Authenticated):**
```json
{
    "is_user": true,
    "confidence": 0.95,
    "should_alert": false,
    "message": "User: john_doe - Match: True (Confidence: 95%)"
}
```

**Response (Unknown Face):**
```json
{
    "is_user": false,
    "confidence": 0.15,
    "should_alert": true,
    "message": "User: john_doe - Match: False (Confidence: 15%)"
}
```

## Configuration

### Tolerance Levels

The face matching uses a tolerance mechanism:
- **Default tolerance:** 0.6 (lower = stricter)
- **More strict:** 0.4 (fewer false positives, may miss matches)
- **Less strict:** 0.8 (more matches, may have false positives)

To adjust, modify in `detection/views.py` and `sep_detection/detection.py`:
```python
is_match, confidence = is_user_face(
    user.profile_picture.path,
    detected_face_array,
    tolerance=0.6  # Change this value
)
```

## Troubleshooting

### Face Not Recognized

1. **Different appearance:** Try uploading a new photo matching current appearance
2. **Poor lighting:** Ensure photo has good front lighting
3. **Changed profile:** If you've changed glasses/facial hair significantly, update photo
4. **Photo quality:** Ensure faces are clearly visible

### "face_recognition not installed"

```bash
pip install face_recognition --upgrade
# Or if on Windows with issues:
pip install face_recognition dlib numpy
```

### Telegram Alerts Not Sending (Authentication Disabled)

If `SAFEDETECT_USER_ID` is not set:
- User authentication is disabled
- All faces trigger alerts
- Set the environment variable to enable authentication

```bash
# Windows
set SAFEDETECT_USER_ID=1

# Linux/Mac
export SAFEDETECT_USER_ID=1
```

## Security Notes

⚠️ **Important:**
- Profile pictures are stored in the media folder
- Ensure your media folder is backed up
- Don't share camera system access without consent
- Face recognition has limitations:
  - Significant appearance changes may not be recognized
  - Multiple people with similar faces may cause confusion
  - Performance depends on photo quality

## File Locations

```
SafeDetect/
├── detection/
│   ├── face_recognition_utils.py      # Face comparison functions
│   ├── views.py                       # API endpoints (verify_face)
│   ├── urls.py                        # API routes
│   └── face_detection.py              # Face detection utilities
├── accounts/
│   ├── models.py                      # User model with profile_picture
│   ├── forms.py                       # Profile forms
│   ├── views.py                       # Profile views
│   ├── urls.py                        # Profile routes
│   └── Templates/accounts/
│       ├── profile.html               # Profile view page
│       ├── edit_profile.html          # Profile edit page
│       └── upload_profile_picture.html # Picture upload page
├── sep_detection/
│   └── detection.py                   # Webcam monitoring with auth
└── README_FACE_AUTH.md               # This file
```

## Testing

### Test Face Verification API

```bash
curl -X POST http://localhost:8000/detection/api/verify-face/ \
  -F "user_id=1" \
  -F "face_image=@path/to/photo.jpg"
```

### Manual testing through web interface

1. Go to Detection > Upload Detection
2. Upload an image with your face
3. Check the alert message (should say "Recognized" if match)
4. Upload image with different person's face
5. Check alert should say "Unknown face detected"

## Next Steps

- [ ] Users upload profile pictures
- [ ] Test face authentication with test images
- [ ] Configure webcam monitoring with USER_ID
- [ ] Test Telegram alerts for unknown faces
- [ ] Monitor and adjust tolerance if needed

