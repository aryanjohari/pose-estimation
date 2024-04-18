import cv2
import base64
from redis import Redis
from rq import Queue
import subprocess

# Initialize Redis connection and RQ queue
redis_conn = Redis(host='localhost', port=6379)
queue = Queue(connection=redis_conn)

def capture_frames():
    cap = cv2.VideoCapture(0)
    
    while True:
        ret, frame = cap.read()
        
        if ret:
            # Convert frame to base64 string
            _, buffer = cv2.imencode('.jpg', frame)
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            yield frame_base64
    
    cap.release()

if __name__ == '__main__':
    # Start worker process
    subprocess.Popen(['python', 'worker.py'])
    
    # Start sink process
    subprocess.Popen(['python', 'sink_process.py'])
    
    frames = capture_frames()
    for frame in frames:
        queue.enqueue('worker.process_frame', frame)
