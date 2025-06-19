# import cv2
# from ultralytics import YOLO
# from threading import Thread, Lock
# import time

# model = YOLO("yolov8n.pt")  # Make sure the model is downloaded

# class VideoCamera:
#     def __init__(self):
#         self.video = cv2.VideoCapture(0)
#         self.lock = Lock()
#         self.running = True
#         self.current_frame = None
#         self.frame_interval = 5
#         self.counter = 0
#         self.person_detected = False

#         Thread(target=self.update_frame, daemon=True).start()

#     def __del__(self):
#         self.running = False
#         self.video.release()

#     def update_frame(self):
#         while self.running:
#             success, frame = self.video.read()
#             if not success:
#                 continue

#             self.counter += 1
#             self.person_detected = False

#             if self.counter % self.frame_interval == 0:
#                 resized = cv2.resize(frame, (640, 360))
#                 results = model(resized, classes=[0], verbose=False)
#                 boxes = results[0].boxes

#                 if boxes is not None and len(boxes) > 0:
#                     for box in boxes:
#                         x1, y1, x2, y2 = box.xyxy[0].tolist()
#                         conf = box.conf[0].item()
#                         if conf > 0.5:
#                             self.person_detected = True
#                             scale_x = frame.shape[1] / 640
#                             scale_y = frame.shape[0] / 360
#                             x1, y1, x2, y2 = [int(val * scale) for val, scale in zip((x1, y1, x2, y2), (scale_x, scale_y, scale_x, scale_y))]
#                             cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
#                             cv2.putText(frame, f"Person {conf:.2f}", (x1, y1 - 10),
#                                         cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

#             with self.lock:
#                 self.current_frame = frame

#             time.sleep(0.01)

#     def get_frame(self):
#         with self.lock:
#             if self.current_frame is None:
#                 return None
#             _, jpeg = cv2.imencode('.jpg', self.current_frame)
#             return jpeg.tobytes()

# camera = VideoCamera()
