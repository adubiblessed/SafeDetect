"""Lightweight face matching utilities using OpenCV and NumPy only.

This replaces heavy face_recognition/dlib dependencies for low-resource PCs.
"""

import cv2
import numpy as np


FACE_VECTOR_SIZE = (96, 96)
DEFAULT_SIMILARITY_THRESHOLD = 0.82


def _to_face_vector(face_image):
    """Convert a face image to a normalized grayscale feature vector."""
    if face_image is None or getattr(face_image, "size", 0) == 0:
        return None

    try:
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
    except Exception:
        return None

    # Normalize geometry and illumination for stable comparison.
    resized = cv2.resize(gray, FACE_VECTOR_SIZE, interpolation=cv2.INTER_AREA)
    equalized = cv2.equalizeHist(resized)
    vec = equalized.astype(np.float32).flatten()

    norm = np.linalg.norm(vec)
    if norm == 0:
        return None
    return vec / norm


def get_face_encoding(image_path):
    """Create a face vector from an image file path."""
    image = cv2.imread(image_path)
    if image is None:
        return None
    return _to_face_vector(image)


def get_face_encoding_from_array(image_array):
    """Create a face vector from an in-memory OpenCV image array."""
    return _to_face_vector(image_array)


def _cosine_similarity(vec1, vec2):
    if vec1 is None or vec2 is None:
        return 0.0
    return float(np.dot(vec1, vec2))


def compare_faces(known_encoding, unknown_encodings, tolerance=0.6):
    """Backwards-compatible API returning match booleans.

    This project previously used a distance-based tolerance. For the lightweight
    matcher, we use cosine similarity and map tolerance into a safe threshold.
    """
    if known_encoding is None or not isinstance(unknown_encodings, list):
        return []

    # Keep compatibility: lower tolerance means stricter match.
    threshold = max(0.72, min(DEFAULT_SIMILARITY_THRESHOLD, 1.0 - (tolerance * 0.3)))
    results = []
    for unknown in unknown_encodings:
        sim = _cosine_similarity(known_encoding, unknown)
        results.append(sim >= threshold)
    return results


def get_face_distance(known_encoding, unknown_encoding):
    """Backwards-compatible distance metric in [0, 1], lower is better."""
    sim = _cosine_similarity(known_encoding, unknown_encoding)
    return float(1.0 - max(0.0, min(1.0, sim)))


def is_user_face(user_profile_picture_path, detected_face_array, tolerance=0.6):
    """Check whether detected face matches the user's profile picture.

    Returns:
        (is_match: bool, confidence: float)
    """
    try:
        user_vec = get_face_encoding(user_profile_picture_path)
        if user_vec is None:
            return False, 0.0

        detected_vec = get_face_encoding_from_array(detected_face_array)
        if detected_vec is None:
            return False, 0.0

        similarity = _cosine_similarity(user_vec, detected_vec)
        threshold = max(0.72, min(DEFAULT_SIMILARITY_THRESHOLD, 1.0 - (tolerance * 0.3)))
        is_match = similarity >= threshold

        # Clamp confidence to [0, 1].
        confidence = float(max(0.0, min(1.0, similarity)))
        return is_match, confidence
    except Exception as e:
        print(f"Error comparing faces: {e}")
        return False, 0.0


def extract_face_crop(image_array, face_box):
    """Extract and return a cropped face from the image."""
    x, y, w, h = face_box

    ih, iw = image_array.shape[:2]
    x = max(0, x)
    y = max(0, y)
    w = max(1, w)
    h = max(1, h)
    x2 = min(iw, x + w)
    y2 = min(ih, y + h)

    if x >= x2 or y >= y2:
        return None
    return image_array[y:y2, x:x2]


def save_face_encoding(user, encoding):
    """Placeholder for future persistence of face vectors."""
    return None
