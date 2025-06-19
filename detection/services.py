from ultralytics import YOLO

model = YOLO("yolov8n.pt")

def run_yolo_detection(file_path):
    results = model(file_path)[0]  # Get first image result
    labels = results.names
    boxes = results.boxes

    for box in boxes:
        label_id = int(box.cls[0])
        label = labels[label_id]
        confidence = float(box.conf[0])

        # Only process 'person' class
        if label == 'person' and confidence > 0.7:
            return {
                'label': label,
                'confidence': confidence,
                'alert': True,
                'message': "Intruder detected"
            }

    # No person detected
    return {
        'label': None,
        'confidence': 0.0,
        'alert': False,
        'message': "No intruder detected"
    }
