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
import logging
from typing import Optional

import cv2
import numpy as np
import face_recognition
import requests
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
STUDENTS_DATA_FILE = 'students_data.json' # Input file with student URLs
ATTENDANCE_FILE = 'attendance.json'       # Output file for attendance records

# --- FastAPI App Initialization ---
app = FastAPI(
    title="Face Recognition Attendance Controller",
    description="API to start and stop the face recognition attendance process.",
    version="1.0.0"
)

# --- Global State Management ---
# This dictionary will manage the state of the recognition process across API calls.
recognition_state = {
    "is_running": False,
    "recognition_thread": None,
    "stop_event": None,
    "error_message": None,
    "start_time": None,
    "students_loaded": 0
}

# --- Response Models ---
class StartResponse(BaseModel):
    status: str
    message: str
    students_loaded: int
    start_time: str

class StopResponse(BaseModel):
    status: str
    message: str
    session_duration: str
    recognizedStudents: list

# ====================================================================
# REFACTORED CORE LOGIC FROM main.py
# ====================================================================

def load_and_encode_students():
    """
    Loads student data from JSON, downloads images from URLs, and generates face encodings.
    Returns: tuple (known_face_encodings, known_student_roll_nos, error_message)
    """
    logger.info("Loading student data and generating encodings...")
    
    known_face_encodings = []
    known_student_roll_nos = []

    if not os.path.exists(STUDENTS_DATA_FILE):
        error_msg = f"Error: {STUDENTS_DATA_FILE} not found!"
        logger.error(error_msg)
        return [], [], error_msg

    try:
        with open(STUDENTS_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        error_msg = f"Error reading {STUDENTS_DATA_FILE}: {e}"
        logger.error(error_msg)
        return [], [], error_msg

    students = data.get("classStudents", [])
    if not students:
        error_msg = "No students found in the data file"
        logger.error(error_msg)
        return [], [], error_msg

    for i, student in enumerate(students):
        roll_no = student.get("rollNo")
        url = student.get("url")
        
        if not roll_no or not url:
            logger.warning(f"Student {i+1}: Missing rollNo or URL. Skipping.")
            continue

        try:
            logger.info(f"Processing {roll_no} ({i+1}/{len(students)}) - Downloading image...")
            
            # Download image with better error handling
            response = requests.get(url, timeout=15, stream=True)
            response.raise_for_status()

            # Check if response content is actually an image
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                logger.warning(f"Warning: URL for {roll_no} doesn't seem to be an image (content-type: {content_type}). Skipping.")
                continue

            # Convert image data from bytes to an OpenCV image
            image_bytes = np.frombuffer(response.content, np.uint8)
            img = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)

            if img is None:
                logger.warning(f"Warning: Could not decode image for {roll_no}. Invalid image format. Skipping.")
                continue

            # Check if image is too small
            if img.shape[0] < 50 or img.shape[1] < 50:
                logger.warning(f"Warning: Image for {roll_no} is too small ({img.shape[:2]}). Skipping.")
                continue

            # Convert from BGR (OpenCV) to RGB (face_recognition)
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Get face encoding with better error handling
            encodings = face_recognition.face_encodings(rgb_img)
            
            if encodings:
                known_face_encodings.append(encodings[0])
                known_student_roll_nos.append(roll_no)
                logger.info(f"✓ Encoding generated for {roll_no}")
            else:
                logger.warning(f"Warning: No face found in image for {roll_no}. Make sure the image clearly shows a face.")

        except requests.exceptions.Timeout:
            logger.error(f"Timeout downloading image for {roll_no}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading image for {roll_no}: {e}")
        except Exception as e:
            logger.error(f"An error occurred while processing {roll_no}: {e}")

    success_count = len(known_face_encodings)
    logger.info(f"--- Encoding complete. {success_count}/{len(students)} students loaded successfully. ---")
    
    if success_count == 0:
        return [], [], "No valid face encodings could be generated from the provided images"
    
    return known_face_encodings, known_student_roll_nos, None

def mark_student_attendance(student_roll_no):
    """
    Marks attendance in the JSON file, preventing duplicate entries for the same day.
    Returns: bool (True if marked, False if already present)
    """
    try:
        attendance_data = {"recognizedStudents": []}
        
        # Load existing attendance data
        if os.path.exists(ATTENDANCE_FILE):
            with open(ATTENDANCE_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    attendance_data = json.loads(content)

        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Check if student is already marked present today
        already_present = any(
            rec.get("rollNo") == student_roll_no and rec.get("timestamp", "").startswith(current_date)
            for rec in attendance_data.get("recognizedStudents", [])
        )

        if not already_present:
            new_record = {
                "rollNo": student_roll_no,
                "timestamp": datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            }
            attendance_data.setdefault("recognizedStudents", []).append(new_record)
            
            # Save with backup
            temp_file = ATTENDANCE_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(attendance_data, f, indent=2, ensure_ascii=False)
            
            # Atomic replacement
            os.replace(temp_file, ATTENDANCE_FILE)
            logger.info(f"✓ Attendance marked for {student_roll_no}")
            return True
        else:
            logger.info(f"⚠ {student_roll_no} already marked present today.")
            return False

    except Exception as e:
        logger.error(f"Error marking attendance for {student_roll_no}: {e}")
        return False

def recognition_loop(stop_event: threading.Event):
    """
    The main face recognition loop that runs in a background thread.
    """
    logger.info("BG-THREAD: Recognition loop starting.")
    
    try:
        # Step 1: Load encodings
        known_encodings, known_roll_nos, error_msg = load_and_encode_students()
        if error_msg or not known_encodings:
            logger.error(f"BG-THREAD: {error_msg or 'No student data to process'}. Stopping thread.")
            recognition_state["error_message"] = error_msg or "No valid face encodings available"
            recognition_state["is_running"] = False
            return

        recognition_state["students_loaded"] = len(known_encodings)
        logger.info(f"BG-THREAD: Successfully loaded {len(known_encodings)} student encodings.")

        # Step 2: Initialize camera with retries
        cap = None
        for camera_index in [0, 1, 2]:  # Try multiple camera indices
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                logger.info(f"BG-THREAD: Camera {camera_index} opened successfully.")
                break
            cap.release()
        
        if not cap or not cap.isOpened():
            error_msg = "Error: Could not open any camera. Please check camera connection."
            logger.error(f"BG-THREAD: {error_msg}")
            recognition_state["error_message"] = error_msg
            recognition_state["is_running"] = False
            return

        # Configure camera settings for better performance
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        logger.info("BG-THREAD: Camera initialized. Starting recognition...")
        
        # Step 3: Main recognition loop with frame skipping for performance
        frame_skip = 3  # Process every 3rd frame
        frame_count = 0
        
        while not stop_event.is_set():
            success, frame = cap.read()
            if not success:
                logger.warning("BG-THREAD: Failed to capture frame.")
                time.sleep(0.1)
                continue
            
            frame_count += 1
            
            # Skip frames for better performance
            if frame_count % frame_skip != 0:
                continue
            
            try:
                # Resize frame for faster processing
                small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                
                # Find faces
                face_locations = face_recognition.face_locations(rgb_small_frame, model="hog")  # Use HOG for speed
                
                if face_locations:
                    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

                    for face_encoding in face_encodings:
                        # Compare with known faces
                        matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=0.6)
                        face_distances = face_recognition.face_distance(known_encodings, face_encoding)
                        
                        if len(face_distances) > 0:
                            best_match_index = np.argmin(face_distances)

                            if matches[best_match_index] and face_distances[best_match_index] < 0.5:  # Stricter threshold
                                roll_no = known_roll_nos[best_match_index]
                                mark_student_attendance(roll_no)
                
            except Exception as e:
                logger.error(f"BG-THREAD: Error processing frame: {e}")
            
            # Small delay to prevent excessive CPU usage
            time.sleep(0.05)

    except Exception as e:
        logger.error(f"BG-THREAD: Unexpected error in recognition loop: {e}")
        recognition_state["error_message"] = f"Recognition loop error: {str(e)}"
    
    finally:
        # Step 4: Cleanup
        if 'cap' in locals() and cap:
            cap.release()
        cv2.destroyAllWindows()
        recognition_state["is_running"] = False
        logger.info("BG-THREAD: Recognition loop stopped and resources released.")

# ====================================================================
# API ENDPOINTS
# ====================================================================

@app.get("/")
def root():
    return {
        "message": "Face Recognition Attendance Controller is running.",
        "version": "1.0.0",
        "is_recognition_active": recognition_state["is_running"],
        "students_loaded": recognition_state.get("students_loaded", 0),
        "start_time": recognition_state.get("start_time"),
        "endpoints": {
            "start": "/start-recognition (POST)",
            "stop": "/stop-recognition (POST)",
            "status": "/status (GET)"
        }
    }

@app.get("/status")
def get_status():
    """Get current status of the recognition system."""
    return {
        "is_running": recognition_state["is_running"],
        "students_loaded": recognition_state.get("students_loaded", 0),
        "start_time": recognition_state.get("start_time"),
        "error_message": recognition_state.get("error_message")
    }

@app.post("/start-recognition")
async def start_recognition():
    """
    Starts the face recognition process in a background thread.
    """
    if recognition_state["is_running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Recognition process is already running. Stop it first before starting a new session."
        )
    
    logger.info("API: Received request to start recognition.")
    
    # Reset state
    recognition_state["error_message"] = None
    recognition_state["students_loaded"] = 0
    recognition_state["start_time"] = datetime.now().isoformat()
    
    # Optional: Clear old attendance file before starting a new session
    # Uncomment the lines below if you want to start fresh each time
    # if os.path.exists(ATTENDANCE_FILE):
    #     backup_name = f"{ATTENDANCE_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    #     os.rename(ATTENDANCE_FILE, backup_name)
    #     logger.info(f"Previous attendance backed up as: {backup_name}")

    try:
        recognition_state["stop_event"] = threading.Event()
        recognition_state["recognition_thread"] = threading.Thread(
            target=recognition_loop,
            args=(recognition_state["stop_event"],),
            daemon=True  # Thread will be killed when main process ends
        )
        recognition_state["recognition_thread"].start()
        recognition_state["is_running"] = True
        
        # Wait a moment to check if initialization was successful
        time.sleep(2)
        
        if recognition_state.get("error_message"):
            recognition_state["is_running"] = False
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=recognition_state["error_message"]
            )
        
        return StartResponse(
            status="success",
            message="Face recognition process started successfully.",
            students_loaded=recognition_state.get("students_loaded", 0),
            start_time=recognition_state["start_time"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Error starting recognition: {e}")
        recognition_state["is_running"] = False
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start recognition process: {str(e)}"
        )

@app.post("/stop-recognition")
async def stop_recognition():
    """
    Stops the background face recognition process and returns the collected attendance data.
    """
    if not recognition_state["is_running"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Recognition process is not running. Nothing to stop."
        )

    logger.info("API: Received request to stop recognition.")
    
    try:
        start_time = recognition_state.get("start_time")
        
        # Signal the thread to stop
        if recognition_state["stop_event"]:
            recognition_state["stop_event"].set()
        
        # Wait for the thread to finish its cleanup (with timeout)
        if recognition_state["recognition_thread"]:
            recognition_state["recognition_thread"].join(timeout=10)
            
            if recognition_state["recognition_thread"].is_alive():
                logger.warning("Recognition thread did not stop gracefully within timeout")
        
        recognition_state["is_running"] = False
        
        # Calculate session duration
        session_duration = "Unknown"
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
                duration = datetime.now() - start_dt
                session_duration = f"{duration.total_seconds():.1f} seconds"
            except:
                pass
        
        # Read the final attendance data
        attendance_data = {"recognizedStudents": []}
        if os.path.exists(ATTENDANCE_FILE):
            try:
                with open(ATTENDANCE_FILE, 'r', encoding='utf-8') as f:
                    attendance_data = json.load(f)
            except Exception as e:
                logger.error(f"Error reading attendance file: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error reading attendance data: {str(e)}"
                )
        
        logger.info(f"API: Recognition stopped. Session duration: {session_duration}")
        logger.info(f"API: Returning attendance data with {len(attendance_data.get('recognizedStudents', []))} records")
        
        return StopResponse(
            status="success",
            message=f"Face recognition process stopped successfully. Session duration: {session_duration}",
            session_duration=session_duration,
            recognizedStudents=attendance_data.get("recognizedStudents", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"API: Error stopping recognition: {e}")
        recognition_state["is_running"] = False  # Force stop
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error stopping recognition process: {str(e)}"
        )

# ====================================================================
# ERROR HANDLERS
# ====================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred"
    )

# To run this server:
# uvicorn run:app --reload --host 0.0.0.0 --port 8001