# ====================================================================
# run.py - FACE RECOGNITION ATTENDANCE API
# ====================================================================
# This script runs a FastAPI server to control the face recognition process.
# - POST /start-recognition: Begins the attendance process in the background.
# - POST /stop-recognition: Stops the process and returns the attendance data.
# ====================================================================

import os
import json
import threading
import time
from datetime import datetime
import io

import cv2
import numpy as np
import face_recognition
import requests
from fastapi import FastAPI, HTTPException

# --- Configuration ---
STUDENTS_DATA_FILE = 'students_data.json' # Input file with student URLs
ATTENDANCE_FILE = 'attendance.json'       # Output file for attendance records

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Face Recognition Attendance Controller",
    description="API to start and stop the face recognition attendance process."
)

# --- Global State Management ---
# This dictionary will manage the state of the recognition process across API calls.
recognition_state = {
    "is_running": False,
    "recognition_thread": None,
    "stop_event": None
}

# ====================================================================
# REFACTORED CORE LOGIC FROM main.py
# ====================================================================

def load_and_encode_students():
    """
    Loads student data from JSON, downloads images from URLs, and generates face encodings.
    """
    print("Loading student data and generating encodings...")
    
    known_face_encodings = []
    known_student_roll_nos = []

    if not os.path.exists(STUDENTS_DATA_FILE):
        print(f"Error: {STUDENTS_DATA_FILE} not found!")
        return [], []

    with open(STUDENTS_DATA_FILE, 'r') as f:
        data = json.load(f)

    for student in data.get("classStudents", []):
        roll_no = student.get("rollNo")
        url = student.get("url")
        
        if not roll_no or not url:
            continue

        try:
            print(f"Downloading image for {roll_no} from {url}...")
            response = requests.get(url, timeout=10)
            response.raise_for_status() # Raise an exception for bad status codes

            # Convert image data from bytes to an OpenCV image
            image_bytes = np.frombuffer(response.content, np.uint8)
            img = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)

            if img is None:
                print(f"Warning: Could not decode image for {roll_no}. Skipping.")
                continue

            # Convert from BGR (OpenCV) to RGB (face_recognition)
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Get face encoding
            encodings = face_recognition.face_encodings(rgb_img)
            
            if encodings:
                known_face_encodings.append(encodings[0])
                known_student_roll_nos.append(roll_no)
                print(f"✓ Encoding generated for {roll_no}")
            else:
                print(f"Warning: No face found in image for {roll_no}. Skipping.")

        except requests.exceptions.RequestException as e:
            print(f"Error downloading image for {roll_no}: {e}")
        except Exception as e:
            print(f"An error occurred while processing {roll_no}: {e}")

    print(f"--- Encoding complete. {len(known_face_encodings)} students loaded. ---")
    return known_face_encodings, known_student_roll_nos

def mark_student_attendance(student_roll_no):
    """
    Marks attendance in the JSON file, preventing duplicate entries for the same day.
    """
    try:
        attendance_data = {"recognizedStudents": []}
        if os.path.exists(ATTENDANCE_FILE):
            with open(ATTENDANCE_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    attendance_data = json.loads(content)

        current_date = datetime.now().strftime('%Y-%m-%d')
        already_present = any(
            rec.get("rollNo") == student_roll_no and rec.get("timestamp", "").startswith(current_date)
            for rec in attendance_data.get("recognizedStudents", [])
        )

        if not already_present:
            new_record = {
                "rollNo": student_roll_no,
                "timestamp": datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
            }
            attendance_data.setdefault("recognizedStudents", []).append(new_record)
            
            with open(ATTENDANCE_FILE, 'w') as f:
                json.dump(attendance_data, f, indent=2)
            print(f"✓ Attendance marked for {student_roll_no}")
        else:
            print(f"⚠ {student_roll_no} already marked present today.")

    except Exception as e:
        print(f"Error marking attendance: {e}")

def recognition_loop(stop_event: threading.Event):
    """
    The main face recognition loop that runs in a background thread.
    """
    print("BG-THREAD: Recognition loop starting.")
    
    # Step 1: Load encodings
    known_encodings, known_roll_nos = load_and_encode_students()
    if not known_encodings:
        print("BG-THREAD: No student data to process. Stopping thread.")
        recognition_state["is_running"] = False
        return

    # Step 2: Initialize camera
    cap = cv2.VideoCapture(0) # Use camera index 0 (default)
    if not cap.isOpened():
        print("BG-THREAD: Error: Could not open camera. Stopping thread.")
        recognition_state["is_running"] = False
        return

    print("BG-THREAD: Camera initialized. Starting recognition...")
    
    # Step 3: Main recognition loop
    while not stop_event.is_set():
        success, frame = cap.read()
        if not success:
            print("BG-THREAD: Failed to capture frame.")
            time.sleep(0.5)
            continue
        
        # Process frame
        rgb_small_frame = cv2.cvtColor(cv2.resize(frame, (0, 0), fx=0.25, fy=0.25), cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_small_frame)
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces(known_encodings, face_encoding)
            face_distances = face_recognition.face_distance(known_encodings, face_encoding)
            best_match_index = np.argmin(face_distances)

            if matches[best_match_index] and face_distances[best_match_index] < 0.6:
                roll_no = known_roll_nos[best_match_index]
                mark_student_attendance(roll_no)
        
        # A short delay to prevent high CPU usage
        time.sleep(0.1)

    # Step 4: Cleanup
    cap.release()
    cv2.destroyAllWindows()
    print("BG-THREAD: Recognition loop stopped and resources released.")

# ====================================================================
# API ENDPOINTS
# ====================================================================

@app.post("/start-recognition")
async def start_recognition():
    """
    Starts the face recognition process in a background thread.
    """
    if recognition_state["is_running"]:
        raise HTTPException(status_code=400, detail="Recognition process is already running.")
    
    # Clear old attendance file before starting a new session if needed
    # if os.path.exists(ATTENDANCE_FILE):
    #     os.remove(ATTENDANCE_FILE)

    print("API: Received request to start recognition.")
    recognition_state["stop_event"] = threading.Event()
    recognition_state["recognition_thread"] = threading.Thread(
        target=recognition_loop,
        args=(recognition_state["stop_event"],)
    )
    recognition_state["recognition_thread"].start()
    recognition_state["is_running"] = True
    
    return {"status": "success", "message": "Face recognition process started."}


@app.post("/stop-recognition")
async def stop_recognition():
    """
    Stops the background face recognition process and returns the collected attendance data.
    """
    if not recognition_state["is_running"]:
        raise HTTPException(status_code=400, detail="Recognition process is not running.")

    print("API: Received request to stop recognition.")
    
    # Signal the thread to stop
    recognition_state["stop_event"].set()
    # Wait for the thread to finish its cleanup
    recognition_state["recognition_thread"].join()
    
    recognition_state["is_running"] = False
    
    # Read the final attendance data
    if not os.path.exists(ATTENDANCE_FILE):
        return {"recognizedStudents": []}

    with open(ATTENDANCE_FILE, 'r') as f:
        attendance_data = json.load(f)
        
    return attendance_data


@app.get("/")
def root():
    return {
        "message": "Attendance System Controller is running.",
        "is_recognition_active": recognition_state["is_running"]
    }