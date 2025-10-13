import cv2

# Path to your video
video_path = "uploads/rickroll.mp4"

cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Could not open video.")
else:
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Frame rate: {fps} frames per second")

cap.release()