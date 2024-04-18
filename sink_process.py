import json
import numpy as np
from tensorflow.keras.models import load_model
from redis import Redis
from rq import Queue

# Initialize Redis connection and RQ queue
redis_conn = Redis(host='localhost', port=6379)
queue = Queue(connection=redis_conn)

# Load the trained RNN model
model = load_model('best_model.h5')

def process_feature_vector_sequence(feature_vector_sequence_json):
    # Decode feature vector sequence from JSON
    feature_vector_sequence = json.loads(feature_vector_sequence_json)['feature_vector_sequence']
    
    # Convert feature vector sequence to numpy array
    X = np.array(feature_vector_sequence)
    
    # Reshape feature vector sequence for model input
    X = np.reshape(X, (1, 30, X.shape[1]))
    
    # Predict punch using the model
    predictions = model.predict(X)
    
    # Get the predicted punch and its probability
    if predictions[0][0] > predictions[0][1]:
        punch = 'jab'
        probability = predictions[0][0]
    else:
        punch = 'cross'
        probability = predictions[0][1]
    
    # Send the result to app.py
    result = {
        'punch': punch,
        'probability': probability
    }
    
    # Convert result to JSON and enqueue for app.py
    result_json = json.dumps(result)
    queue.enqueue('app.process_result', result_json)

if __name__ == '__main__':
    while True:
        feature_vector_sequence_json = queue.dequeue()  # Dequeue feature vector sequence from Redis queue
        if feature_vector_sequence_json:
            process_feature_vector_sequence(feature_vector_sequence_json)
