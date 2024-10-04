from flask import Flask, render_template, Response, jsonify, send_file
import cv2
import os
from datetime import datetime
from pymongo import MongoClient

app = Flask(__name__)

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client['webcam_app']  # Database name
videos_collection = db['videos']  # Collection name for video metadata

# Initialize variables for camera and video recording
camera = None
is_recording = False
video_writer = None
output_file = "recorded_video.avi"

def generate_frames():
    global camera, video_writer, is_recording
    while camera is not None:
        success, frame = camera.read()
        if not success:
            break
        else:
            if is_recording and video_writer is not None:
                video_writer.write(frame)

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    global camera
    if camera is not None:
        return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return jsonify({"error": "Camera is off"}), 503

@app.route('/camera_on', methods=['POST'])
def camera_on():
    global camera
    if camera is None:
        camera = cv2.VideoCapture(0)
    return jsonify({"status": "Camera started"})

@app.route('/camera_off', methods=['POST'])
def camera_off():
    global camera, is_recording, video_writer
    if camera is not None:
        camera.release()
        camera = None

    if is_recording:
        is_recording = False
        if video_writer is not None:
            video_writer.release()
            video_writer = None

    return jsonify({"status": "Camera stopped"})

@app.route('/start_recording', methods=['POST'])
def start_recording():
    global video_writer, is_recording, camera, output_file

    if camera is not None and not is_recording:
        frame_width = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Create a VideoWriter object to save the video to disk
        video_writer = cv2.VideoWriter(output_file, 
                                       cv2.VideoWriter_fourcc('M','J','P','G'), 
                                       20, (frame_width, frame_height))
        is_recording = True
    
    return jsonify({"status": "Recording started"})

@app.route('/stop_recording', methods=['POST'])
def stop_recording():
    global is_recording, video_writer, output_file

    if is_recording:
        is_recording = False
        if video_writer is not None:
            video_writer.release()
            video_writer = None

        # Store video metadata to MongoDB after recording is finished
        video_data = {
            "file_name": output_file,
            "recorded_at": datetime.now().isoformat(),
            "status": "completed"
        }
        videos_collection.insert_one(video_data)
    
    return jsonify({"status": "Recording stopped"})

@app.route('/download_video', methods=['GET'])
def download_video():
    if os.path.exists(output_file):
        return send_file(output_file, as_attachment=True)
    else:
        return jsonify({"error": "No video recorded yet"}), 404

@app.route('/list_videos', methods=['GET'])
def list_videos():
    # Fetch all videos from MongoDB
    videos = list(videos_collection.find({}, {"_id": 0}))  # Exclude the MongoDB ID field
    return jsonify(videos)

if __name__ == "__main__":
    app.run(debug=True)