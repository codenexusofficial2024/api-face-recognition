# ====================================================================
# FASTAPI FACE RECOGNITION ATTENDANCE SYSTEM
# ====================================================================
# FastAPI server that handles student data uploads and face recognition sessions
# ====================================================================

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import json
import shutil
from typing import List, Optional
import asyncio
from datetime import datetime
import threading
import time

# Import our modified face recognition module
from face_recognition_module import FaceRecognitionSystem

# ====================================================================
# CONFIGURATION
# ====================================================================

UPLOAD_FOLDER = "student-images"
ATTENDANCE_FILE = "attendance.json"
STATIC_FOLDER = "static"

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

# ====================================================================
# FASTAPI APP SETUP
# ====================================================================

app = FastAPI(
    title="Face Recognition Attendance System",
    description="API for managing student face recognition attendance",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_FOLDER), name="static")

# Global variables for session management
recognition_system = None
recognition_thread = None
session_active = False

# ====================================================================
# UTILITY FUNCTIONS
# ====================================================================

def clear_student_images():
    """Clear all existing student images"""
    if os.path.exists(UPLOAD_FOLDER):
        for filename in os.listdir(UPLOAD_FOLDER):
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")

def save_uploaded_file(upload_file: UploadFile, destination: str):
    """Save uploaded file to destination"""
    try:
        with open(destination, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
        return True
    except Exception as e:
        print(f"Error saving file {destination}: {e}")
        return False

def run_recognition_session():
    """Run face recognition in background thread"""
    global recognition_system, session_active
    try:
        if recognition_system:
            recognition_system.start_recognition()
    except Exception as e:
        print(f"Error in recognition session: {e}")
    finally:
        session_active = False

# ====================================================================
# API ENDPOINTS
# ====================================================================

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Face Recognition Attendance System</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            .container { background: #f4f4f4; padding: 20px; border-radius: 8px; margin: 20px 0; }
            .button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 5px; }
            .button:hover { background: #0056b3; }
            .button.danger { background: #dc3545; }
            .button.success { background: #28a745; }
            .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
            .status.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .status.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .status.info { background: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
            .file-input { margin: 10px 0; }
            .student-item { background: white; padding: 10px; margin: 5px 0; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; }
        </style>
    </head>
    <body>
        <h1>Face Recognition Attendance System</h1>
        
        <div class="container">
            <h2>Upload Student Data</h2>
            <div>
                <label for="rollNumber">Roll Number:</label>
                <input type="text" id="rollNumber" placeholder="Enter roll number">
            </div>
            <div class="file-input">
                <label for="photo">Student Photo:</label>
                <input type="file" id="photo" accept="image/*">
            </div>
            <button class="button" onclick="uploadStudent()">Add Student</button>
            <button class="button danger" onclick="clearAllStudents()">Clear All Students</button>
        </div>

        <div class="container">
            <h2>Current Students</h2>
            <div id="studentsList"></div>
            <button class="button" onclick="loadStudents()">Refresh List</button>
        </div>

        <div class="container">
            <h2>Face Recognition Session</h2>
            <div id="sessionStatus" class="status info">Session not started</div>
            <button class="button success" onclick="startSession()">Start Recognition</button>
            <button class="button danger" onclick="stopSession()">Stop Recognition</button>
            <button class="button" onclick="getAttendance()">Get Attendance</button>
        </div>

        <div class="container">
            <h2>Attendance Results</h2>
            <pre id="attendanceResults"></pre>
        </div>

        <div id="messages"></div>

        <script src="/static/app.js"></script>
    </body>
    </html>
    """
    return html_content

@app.post("/upload-student")
async def upload_student(
    roll_number: str = Form(...),
    photo: UploadFile = File(...)
):
    """Upload a single student's photo and roll number"""
    try:
        # Validate file type
        if not photo.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Create filename with roll number
        file_extension = os.path.splitext(photo.filename)[1]
        filename = f"{roll_number}{file_extension}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        # Save the file
        if save_uploaded_file(photo, file_path):
            return JSONResponse({
                "success": True,
                "message": f"Student {roll_number} uploaded successfully",
                "filename": filename
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to save file")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/upload-multiple-students")
async def upload_multiple_students(
    roll_numbers: str = Form(...),
    photos: List[UploadFile] = File(...)
):
    """Upload multiple students at once"""
    try:
        roll_list = [roll.strip() for roll in roll_numbers.split(",")]
        
        if len(roll_list) != len(photos):
            raise HTTPException(
                status_code=400, 
                detail="Number of roll numbers must match number of photos"
            )
        
        results = []
        for roll_number, photo in zip(roll_list, photos):
            if not photo.content_type.startswith("image/"):
                results.append({"roll_number": roll_number, "success": False, "error": "Invalid file type"})
                continue
                
            file_extension = os.path.splitext(photo.filename)[1]
            filename = f"{roll_number}{file_extension}"
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            
            if save_uploaded_file(photo, file_path):
                results.append({"roll_number": roll_number, "success": True, "filename": filename})
            else:
                results.append({"roll_number": roll_number, "success": False, "error": "Failed to save"})
        
        return JSONResponse({
            "success": True,
            "message": f"Processed {len(photos)} files",
            "results": results
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch upload failed: {str(e)}")

@app.get("/students")
async def get_students():
    """Get list of all uploaded students"""
    try:
        students = []
        if os.path.exists(UPLOAD_FOLDER):
            for filename in os.listdir(UPLOAD_FOLDER):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    roll_number = os.path.splitext(filename)[0]
                    students.append({
                        "roll_number": roll_number,
                        "filename": filename,
                        "file_path": f"/student-images/{filename}"
                    })
        
        return JSONResponse({
            "success": True,
            "students": students,
            "count": len(students)
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get students: {str(e)}")

@app.delete("/students")
async def clear_students():
    """Clear all student data"""
    try:
        clear_student_images()
        
        # Also clear attendance file
        if os.path.exists(ATTENDANCE_FILE):
            os.remove(ATTENDANCE_FILE)
        
        return JSONResponse({
            "success": True,
            "message": "All student data cleared"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear students: {str(e)}")

@app.post("/start-recognition")
async def start_recognition_session(background_tasks: BackgroundTasks):
    """Start face recognition session"""
    global recognition_system, recognition_thread, session_active
    
    try:
        if session_active:
            return JSONResponse({
                "success": False,
                "message": "Recognition session already active"
            })
        
        # Check if we have student images
        if not os.path.exists(UPLOAD_FOLDER) or len(os.listdir(UPLOAD_FOLDER)) == 0:
            raise HTTPException(status_code=400, detail="No student images found. Please upload student data first.")
        
        # Initialize recognition system
        recognition_system = FaceRecognitionSystem(UPLOAD_FOLDER, ATTENDANCE_FILE)
        
        # Start recognition in background thread
        session_active = True
        recognition_thread = threading.Thread(target=run_recognition_session, daemon=True)
        recognition_thread.start()
        
        return JSONResponse({
            "success": True,
            "message": "Face recognition session started",
            "session_id": datetime.now().isoformat()
        })
        
    except Exception as e:
        session_active = False
        raise HTTPException(status_code=500, detail=f"Failed to start recognition: {str(e)}")

@app.post("/stop-recognition")
async def stop_recognition_session():
    """Stop face recognition session"""
    global recognition_system, session_active
    
    try:
        if not session_active:
            return JSONResponse({
                "success": False,
                "message": "No active recognition session"
            })
        
        session_active = False
        if recognition_system:
            recognition_system.stop_recognition()
        
        return JSONResponse({
            "success": True,
            "message": "Face recognition session stopped"
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop recognition: {str(e)}")

@app.get("/session-status")
async def get_session_status():
    """Get current session status"""
    return JSONResponse({
        "success": True,
        "session_active": session_active,
        "timestamp": datetime.now().isoformat()
    })

@app.get("/attendance")
async def get_attendance():
    """Get attendance results"""
    try:
        if not os.path.exists(ATTENDANCE_FILE):
            return JSONResponse({
                "success": True,
                "data": {"recognizedStudents": []},
                "message": "No attendance data available"
            })
        
        with open(ATTENDANCE_FILE, 'r') as file:
            attendance_data = json.load(file)
        
        return JSONResponse({
            "success": True,
            "data": attendance_data,
            "count": len(attendance_data.get("recognizedStudents", []))
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get attendance: {str(e)}")

@app.get("/attendance/download")
async def download_attendance():
    """Download attendance file"""
    try:
        if not os.path.exists(ATTENDANCE_FILE):
            raise HTTPException(status_code=404, detail="Attendance file not found")
        
        return FileResponse(
            ATTENDANCE_FILE,
            media_type="application/json",
            filename=f"attendance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download attendance: {str(e)}")

@app.get("/student-images/{filename}")
async def get_student_image(filename: str):
    """Get student image file"""
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(file_path)

# ====================================================================
# SERVER STARTUP
# ====================================================================

if __name__ == "__main__":
    print("Starting Face Recognition Attendance API Server...")
    print("Access the web interface at: http://localhost:8000")
    print("API docs available at: http://localhost:8000/docs")
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )