from flask import Flask, redirect, request, jsonify, session, render_template, url_for
from requests import Response
from werkzeug.security import generate_password_hash, check_password_hash
from redis import Redis
from rq import Queue
import pymongo
import datetime
import json
import base64
import os
import subprocess
import cv2

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Initialize Redis connection and RQ queue
redis_conn = Redis(host='localhost', port=6379)
queue = Queue(connection=redis_conn)

# Initialize MongoDB connection
client = pymongo.MongoClient("mongodb+srv://johariaryan16:niggasinparis@cluster0.x2acwj3.mongodb.net/")
db = client["auth_database"]
users_collection = db["users"]
sessions_collection = client["session_database"]

camera = cv2.VideoCapture(0)  # Capture video from the default camera

def generate_frames():
    while True:
        success, frame = camera.read()  # Read a frame from the camera
        
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')  # Add frame to video stream


@app.before_request
def before_request():
    if request.path == '/':
        # This code will run before each request to the home page
        pass

@app.after_request
def after_request(response):
    if request.path == '/':
        # This code will run after each request to the home page
        camera.release()  # Release the camera when the request is completed
    return response


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method == 'POST':
        # Retrieve form data
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            return jsonify({"message": "Username and password are required"}), 400
        
        #hashed_password = generate_password_hash(password, method='sha256')
        
        user = {
            "username": username,
            "password": password
        }
        
        users_collection.insert_one(user)
    
    if request.method == 'GET':
        return render_template('register.html')
    

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        # Retrieve form data
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            return jsonify({"message": "Username and password are required"}), 400
        
        user = users_collection.find_one({"username": username})
        
        # if not user or not check_password_hash(user['password'], password):
        if not user or not user['password'] == password:
             return jsonify({"message": "Invalid credentials"}), 401
        session['username'] = username
        return redirect(url_for('start_session'))
    
    if request.method == 'GET':
        return render_template('login.html')
    

@app.route('/start_session', methods=['POST', 'GET'])
def start_session():
    if request.method == 'POST':
        if 'username' not in session:
            return jsonify({"message": "User not logged in"}), 401
        
        # Start the load process
        subprocess.Popen(['python', 'load_process.py'])

        
        return redirect(url_for('session'))
    
    if request.method == 'GET':
        return render_template('start_session.html')
    
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/stop_capture', methods=['GET'])
def stop_capture():
    try:
        camera.release()  # Release the camera
        return {'success': True}, 200
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500


@app.route('/process_result', methods=['POST'])
def process_result():
    # Display the result to the user
    result_json = request.json
    result = json.loads(result_json)
    punch = result['punch']
    probability = result['probability']
    user_id = result['user_id']
    
    # Store the result in MongoDB
    session = {
        'timestamp': datetime.datetime.now(),
        'punch': punch,
        'probability': probability
    }
    sessions_collection.db[user_id].insert_one(session)
    
    return jsonify({'punch': punch, 'probability': probability})

if __name__ == '__main__':
    app.run(debug=True)
