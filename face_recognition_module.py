# ====================================================================
# MODULAR FACE RECOGNITION SYSTEM
# ====================================================================
# Modified face recognition system that can be controlled via API
# Runs as a class that can be started/stopped programmatically
# ====================================================================

import cv2
import numpy as np
import face_recognition
import os
import json
from datetime import datetime
import threading
import time

class FaceRecognitionSystem:
    """
    Face Recognition System that can be controlled programmatically
    """
    
    def __init__(self, images_folder='student-images', attendance_file='attendance.json'):
        """
        Initialize the face recognition system
        
        Args:
            images_folder (str): Path to folder containing student images
            attendance_file (str): Path to JSON file for storing attendance
        """
        self.images_folder = images_folder
        self.attendance_file = attendance_file
        self.student_images = []
        self.student_names = []
        self.known_face_encodings = []
        self.video_capture = None
        self.is_running = False
        self.recognition_thread = None
        
        print(f"Initializing Face Recognition System...")
        print(f"Images folder: {images_folder}")
        print(f"Attendance file: {attendance_file}")
        
    def load_student_data(self):
        """Load student images and extract names"""
        print("Loading student images...")
        
        # Clear existing data
        self.student_images = []
        self.student_names = []
        
        if not os.path.exists(self.images_folder):
            print(f"Error: Images folder '{self.images_folder}' not found!")
            return False
        
        # Get list of all files in the student images directory
        image_files = os.listdir(self.images_folder)
        print(f"Found {len(image_files)} image files: {image_files}")
        
        # Process each image file in the directory
        for filename in image_files:
            # Skip non-image files
            if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                print(f"Skipping non-image file: {filename}")
                continue
                
            file_path = os.path.join(self.images_folder, filename)
            
            # Read the image using OpenCV
            current_image = cv2.imread(file_path)
            
            # Check if image was loaded successfully
            if current_image is not None:
                self.student_images.append(current_image)
                # Extract roll number by removing file extension
                roll_number = os.path.splitext(filename)[0]
                self.student_names.append(roll_number)
                print(f"Loaded image for student: {roll_number}")
            else:
                print(f"Warning: Could not load image {filename}")
        
        print(f"Successfully loaded {len(self.student_names)} student images")
        print(f"Student roll numbers: {self.student_names}")
        
        return len(self.student_names) > 0
    
    def generate_face_encodings(self):
        """Generate face encodings for all student images"""
        print("Generating face encodings for student images...")
        self.known_face_encodings = []
        
        valid_students = []
        valid_names = []
        
        for i, img in enumerate(self.student_images):
            # Convert image from BGR (OpenCV format) to RGB (face_recognition format)
            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            try:
                # Generate face encoding
                face_encodings = face_recognition.face_encodings(rgb_img)
                if len(face_encodings) > 0:
                    face_encoding = face_encodings[0]  # Take the first face found
                    self.known_face_encodings.append(face_encoding)
                    valid_students.append(img)
                    valid_names.append(self.student_names[i])
                    print(f"Generated encoding for student: {self.student_names[i]}")
                else:
                    print(f"Warning: No face detected in image for {self.student_names[i]}")
            except Exception as e:
                print(f"Error processing image for {self.student_names[i]}: {e}")
        
        # Update lists to only include students with valid encodings
        self.student_images = valid_students
        self.student_names = valid_names
        
        print(f'✓ Face encoding complete for {len(self.known_face_encodings)} students')
        return len(self.known_face_encodings) > 0
    
    def mark_student_attendance(self, student_roll_no):
        """
        Mark attendance for a recognized student in JSON format.
        Prevents duplicate entries for the same student on the same day.
        """
        try:
            # Initialize default JSON structure
            attendance_data = {"recognizedStudents": []}
            
            # Load existing attendance data if file exists
            if os.path.exists(self.attendance_file):
                try:
                    with open(self.attendance_file, 'r') as file:
                        content = file.read().strip()
                        if content:  # Only parse if file has content
                            attendance_data = json.loads(content)
                            # Ensure proper structure
                            if "recognizedStudents" not in attendance_data:
                                attendance_data["recognizedStudents"] = []
                        else:
                            attendance_data = {"recognizedStudents": []}
                except (json.JSONDecodeError, FileNotFoundError):
                    print("Warning: Invalid JSON file. Creating new attendance record.")
                    attendance_data = {"recognizedStudents": []}
            
            # Get current date for duplicate checking
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # Check if student already marked present today
            already_present = False
            for record in attendance_data["recognizedStudents"]:
                if record.get("rollNo") == student_roll_no:
                    # Parse existing timestamp to check if it's from today
                    try:
                        record_date = record.get("timestamp", "")[:10]  # Get YYYY-MM-DD part
                        if record_date == current_date:
                            already_present = True
                            break
                    except:
                        continue
            
            if not already_present:
                # Create ISO 8601 timestamp
                current_time = datetime.now()
                iso_timestamp = current_time.strftime('%Y-%m-%dT%H:%M:%SZ')
                
                # Create new attendance record
                new_record = {
                    "rollNo": student_roll_no,
                    "timestamp": iso_timestamp
                }
                
                # Add to attendance data
                attendance_data["recognizedStudents"].append(new_record)
                
                # Save to JSON file
                with open(self.attendance_file, 'w') as file:
                    json.dump(attendance_data, file, indent=2)
                
                print(f"✓ Attendance marked for {student_roll_no} at {iso_timestamp}")
                return True
            else:
                print(f"⚠ {student_roll_no} already marked present today")
                return False
                
        except Exception as e:
            print(f"Error marking attendance: {e}")
            # Create fresh attendance file
            try:
                current_time = datetime.now()
                iso_timestamp = current_time.strftime('%Y-%m-%dT%H:%M:%SZ')
                
                fresh_data = {
                    "recognizedStudents": [
                        {
                            "rollNo": student_roll_no,
                            "timestamp": iso_timestamp
                        }
                    ]
                }
                
                with open(self.attendance_file, 'w') as file:
                    json.dump(fresh_data, file, indent=2)
                print(f"✓ Created new attendance.json and marked {student_roll_no}")
                return True
            except Exception as write_error:
                print(f"Failed to create attendance file: {write_error}")
                return False
    
    def initialize_camera(self):
        """Initialize camera with fallback options"""
        print("Searching for available cameras...")
        
        # Try different camera indices
        for camera_index in range(5):
            print(f"Trying camera index {camera_index}...")
            test_cap = cv2.VideoCapture(camera_index)
            
            if test_cap.isOpened():
                ret, frame = test_cap.read()
                if ret and frame is not None:
                    print(f"✓ Found working camera at index {camera_index}")
                    self.video_capture = cv2.VideoCapture(camera_index)
                    test_cap.release()
                    return True
                test_cap.release()
            else:
                print(f"✗ Camera index {camera_index} not available")
        
        print("Error: No working camera found!")
        return False
    
    def start_recognition(self):
        """Start the face recognition process"""
        if self.is_running:
            print("Recognition system is already running!")
            return False
        
        # Load student data
        if not self.load_student_data():
            print("Error: No student data found!")
            return False
        
        # Generate face encodings
        if not self.generate_face_encodings():
            print("Error: Could not generate face encodings!")
            return False
        
        # Initialize camera
        if not self.initialize_camera():
            print("Error: Could not initialize camera!")
            return False
        
        self.is_running = True
        self._run_recognition_loop()
        return True
    
    def _run_recognition_loop(self):
        """Main recognition loop (runs in current thread)"""
        print("Face recognition system is now running!")
        print("Recognition will continue until stopped via API")
        
        last_recognition_time = {}  # Track last recognition time for each student
        recognition_cooldown = 5  # Seconds between recognitions for same student
        
        while self.is_running:
            if not self.video_capture or not self.video_capture.isOpened():
                print("Error: Camera not available")
                break
            
            # Capture frame from webcam
            success, current_frame = self.video_capture.read()
            
            if not success:
                print("Error: Failed to capture frame from webcam")
                time.sleep(0.1)
                continue
            
            # Resize frame for faster processing (1/4 size)
            small_frame = cv2.resize(current_frame, (0, 0), fx=0.25, fy=0.25)
            
            # Convert from BGR to RGB
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            
            # Find all face locations in the current frame
            face_locations = face_recognition.face_locations(rgb_small_frame)
            
            # Generate encodings for all detected faces
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
            
            current_time = time.time()
            
            # Process each detected face
            for face_encoding, face_location in zip(face_encodings, face_locations):
                
                # Compare current face with all known student faces
                matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding)
                
                # Calculate face distance (lower = better match)
                face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
                
                # Find the best match
                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    
                    # If we found a good match
                    if matches[best_match_index] and face_distances[best_match_index] < 0.6:
                        # Get the student's roll number
                        recognized_student = self.student_names[best_match_index].upper()
                        
                        # Check cooldown period
                        if (recognized_student not in last_recognition_time or 
                            current_time - last_recognition_time[recognized_student] > recognition_cooldown):
                            
                            # Mark attendance
                            if self.mark_student_attendance(recognized_student):
                                last_recognition_time[recognized_student] = current_time
            
            # Small delay to prevent excessive CPU usage
            time.sleep(0.1)
        
        print("Recognition loop stopped")
    
    def stop_recognition(self):
        """Stop the face recognition process"""
        print("Stopping face recognition system...")
        self.is_running = False
        
        if self.video_capture:
            self.video_capture.release()
            self.video_capture = None
        
        cv2.destroyAllWindows()
        print("✓ Face recognition system stopped")
    
    def get_attendance_data(self):
        """Get current attendance data"""
        if not os.path.exists(self.attendance_file):
            return {"recognizedStudents": []}
        
        try:
            with open(self.attendance_file, 'r') as file:
                return json.load(file)
        except Exception as e:
            print(f"Error reading attendance file: {e}")
            return {"recognizedStudents": []}
    
    def clear_attendance(self):
        """Clear all attendance data"""
        try:
            if os.path.exists(self.attendance_file):
                os.remove(self.attendance_file)
            print("✓ Attendance data cleared")
            return True
        except Exception as e:
            print(f"Error clearing attendance: {e}")
            return False
    
    def get_status(self):
        """Get current system status"""
        return {
            "is_running": self.is_running,
            "students_loaded": len(self.student_names),
            "encodings_generated": len(self.known_face_encodings),
            "camera_available": self.video_capture is not None and self.video_capture.isOpened() if self.video_capture else False,
            "student_names": self.student_names,
            "attendance_file_exists": os.path.exists(self.attendance_file)
        }

# ====================================================================
# STANDALONE EXECUTION (for testing)
# ====================================================================

if __name__ == "__main__":
    print("Testing Face Recognition System...")
    
    system = FaceRecognitionSystem()
    
    try:
        print("Starting recognition system...")
        if system.start_recognition():
            print("System started successfully. Press Ctrl+C to stop...")
            
            # Keep running until interrupted
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\nShutting down...")
        system.stop_recognition()
        print("System stopped.")