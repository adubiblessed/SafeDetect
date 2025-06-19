import cv2
import numpy as np
import os

# Get absolute path to yunet.onnx
model_path = os.path.join(os.path.dirname(__file__), "yunet.onnx")

# Load YuNet model
face_detector = cv2.FaceDetectorYN.create(
    model=model_path,
    config="",
    input_size=(320, 320),
    score_threshold=0.7,
    nms_threshold=0.3,
    top_k=5000
)

def detect_faces(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return {'faces_detected': 0, 'boxes': []}

    h, w = img.shape[:2]
    face_detector.setInputSize((w, h))
    _, faces = face_detector.detect(img)

    result = {'faces_detected': 0, 'boxes': []}

    if faces is not None:
        for face in faces:
            x, y, w, h = map(int, face[:4])
            result['boxes'].append({'x': x, 'y': y, 'w': w, 'h': h})
        result['faces_detected'] = len(faces)

    return result

def annotate_faces(image_path, boxes):
    img = cv2.imread(image_path)
    if img is None:
        return None

    for box in boxes:
        x, y, w, h = box['x'], box['y'], box['w'], box['h']
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

    # Save annotated image
    filename = os.path.basename(image_path)
    annotated_dir = os.path.join(os.path.dirname(__file__), "annotated")
    os.makedirs(annotated_dir, exist_ok=True)
    output_path = os.path.join(annotated_dir, filename)

    cv2.imwrite(output_path, img)
    return output_path
