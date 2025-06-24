from ultralytics import YOLO


model = YOLO("safe_detect 1.1.pt")

# Only these classes should trigger an alert
alert_classes = ["knife", "fire", "gun", "mask"]

def run_yolo_detection(file_path):
    results = model(file_path)[0]  
    labels = results.names         
    boxes = results.boxes          

    for box in boxes:
        label_id = int(box.cls[0].item())       
        label = labels[label_id]                
        confidence = float(box.conf[0].item())  

        if label in alert_classes and confidence > 0.5:
            return {
                'label': label,
                'confidence': confidence,
                'alert': True,
                'message': f"{label.upper()} detected!"
            }

    # No threat classes detected
    return {
        'label': None,
        'confidence': 0.0,
        'alert': False,
        'message': "No threat detected"
    }
