import cv2
import base64
import numpy as np
import json
from redis import Redis
from rq import Queue
import mediapipe as mp

# Initialize Redis connection and RQ queue
redis_conn = Redis(host='localhost', port=6379)
queue = Queue(connection=redis_conn)

# Initialize MediaPipe Pose
mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=False, 
    model_complexity=1, 
    enable_segmentation=False)

def calculate_feature_vector(current_landmarks, prev_landmarks=None):
    feature_vector = []
    
    # Calculate present coordinates of landmarks
    for landmark in current_landmarks:
        feature_vector.extend([landmark['x'], landmark['y'], landmark['z']])
    
    # Calculate change in coordinates wrt previous frame
    if prev_landmarks:
        delta_coordinates = [cur['x'] - prev['x'] for cur, prev in zip(current_landmarks, prev_landmarks)]
        delta_coordinates.extend([cur['y'] - prev['y'] for cur, prev in zip(current_landmarks, prev_landmarks)])
        delta_coordinates.extend([cur['z'] - prev['z'] for cur, prev in zip(current_landmarks, prev_landmarks)])
        
        feature_vector.extend(delta_coordinates)
    else:
        feature_vector.extend([0] * len(current_landmarks) * 3)
    
    return feature_vector

def process_frame(frame_base64):
    # Decode base64 string to image
    decoded_data = base64.b64decode(frame_base64)
    np_data = np.frombuffer(decoded_data, np.uint8)
    frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
    
    # Convert BGR to RGB
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    # Process frame with MediaPipe Pose
    results = pose.process(rgb_frame)
    
    if results.pose_landmarks:
        landmarks = []
        
        for landmark in results.pose_landmarks.landmark:
            landmarks.append({
                'x': landmark.x,
                'y': landmark.y,
                'z': landmark.z
            })
        
        # Load previous landmarks from Redis
        prev_landmarks_json = redis_conn.get('prev_landmarks')
        prev_landmarks = json.loads(prev_landmarks_json.decode('utf-8')) if prev_landmarks_json else None
        
        # Calculate feature vector
        feature_vector = calculate_feature_vector(landmarks, prev_landmarks)
        
        # Store current landmarks as previous landmarks for next frame
        redis_conn.set('prev_landmarks', json.dumps(landmarks))
        
        # Convert feature vector to JSON
        feature_vector_json = json.dumps({'feature_vector': feature_vector})
        
        # Enqueue feature vector for sink process
        queue.enqueue('sink_process.process_feature_vector', feature_vector_json)

if __name__ == '__main__':
    while True:
        frame_base64 = queue.dequeue()  # Dequeue frame from Redis queue
        if frame_base64:
            process_frame(frame_base64)
