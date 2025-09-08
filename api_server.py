import json
import os
from typing import List
import logging
from datetime import datetime

# Import FastAPI and Pydantic for building the API and validating data
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, validator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 1. Define the structure of the data we expect ---
# Pydantic models validate the incoming request data.
# If the data doesn't match this structure, FastAPI returns an error automatically.

class Student(BaseModel):
    rollNo: str = Field(..., min_length=1, description="Student roll number")
    url: str = Field(..., min_length=1, description="Student URL/profile link")
    
    @validator('rollNo')
    def validate_roll_no(cls, v):
        if not v.strip():
            raise ValueError('rollNo cannot be empty or whitespace')
        return v.strip()
    
    @validator('url')
    def validate_url(cls, v):
        if not v.strip():
            raise ValueError('url cannot be empty or whitespace')
        return v.strip()

class StudentPayload(BaseModel):
    classStudents: List[Student] = Field(..., min_items=1, description="List of students")

# --- 2. Initialize the FastAPI application ---
app = FastAPI(
    title="Student Data API",
    description="An API to receive and store student data.",
    version="1.0.0"
)

# The name of the file where we will store the student data.
STUDENTS_DATA_FILE = 'students_data.json'

# --- 3. Helper Functions ---
def load_existing_data():
    """Load existing student data from JSON file."""
    if os.path.exists(STUDENTS_DATA_FILE):
        try:
            with open(STUDENTS_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure the data has the expected structure
                if not isinstance(data, dict) or 'classStudents' not in data:
                    logger.warning("Invalid data structure in file, initializing new structure")
                    return {"classStudents": []}
                return data
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading existing data: {e}")
            return {"classStudents": []}
    else:
        return {"classStudents": []}

def save_data_to_file(data):
    """Save data to JSON file with error handling."""
    try:
        # Create backup of existing file if it exists
        if os.path.exists(STUDENTS_DATA_FILE):
            backup_name = f"{STUDENTS_DATA_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(STUDENTS_DATA_FILE, backup_name)
            logger.info(f"Created backup: {backup_name}")
        
        with open(STUDENTS_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Successfully saved data to {STUDENTS_DATA_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save data: {e}")
        return False

# --- 4. API Endpoints ---

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Student Data API is running",
        "version": "1.0.0",
        "endpoints": {
            "add_student": "/add-student (POST)",
            "get_students": "/students (GET)"
        }
    }

@app.get("/students")
async def get_students():
    """Get all stored student data."""
    try:
        data = load_existing_data()
        return {
            "status": "success",
            "total_students": len(data['classStudents']),
            "data": data
        }
    except Exception as e:
        logger.error(f"Error retrieving students: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve student data"
        )

@app.post("/add-student")
async def add_student_endpoint(payload: StudentPayload):
    """
    Receives student data via a POST request and appends it to a JSON file.
    Prevents duplicate entries based on rollNo.
    """
    try:
        # --- Load Existing Data ---
        data = load_existing_data()
        
        # Get a set of roll numbers we already have (case-insensitive comparison)
        existing_roll_nos = {student['rollNo'].lower() for student in data['classStudents']}
       
        added_count = 0
        skipped_count = 0
        added_students = []
        skipped_students = []

        # --- Process the incoming student(s) from the payload ---
        for student_to_add in payload.classStudents:
            if student_to_add.rollNo.lower() not in existing_roll_nos:
                # Add the new student to our data
                student_dict = student_to_add.dict()
                data['classStudents'].append(student_dict)
                existing_roll_nos.add(student_to_add.rollNo.lower())
                added_students.append(student_to_add.rollNo)
                added_count += 1
                logger.info(f"Added new student: {student_to_add.rollNo}")
            else:
                skipped_students.append(student_to_add.rollNo)
                skipped_count += 1
                logger.info(f"Skipped duplicate student: {student_to_add.rollNo}")

        # --- Save the updated data back to the file ---
        if added_count > 0:
            success = save_data_to_file(data)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save data to file"
                )

        # --- Return a detailed success response ---
        response = {
            "status": "success",
            "message": f"Data processed. Added: {added_count} new student(s). Skipped: {skipped_count} duplicate(s).",
            "summary": {
                "total_received": len(payload.classStudents),
                "added_count": added_count,
                "skipped_count": skipped_count,
                "total_students_now": len(data['classStudents'])
            }
        }
        
        # Include details about which students were added/skipped (useful for debugging)
        if added_students:
            response["added_students"] = added_students
        if skipped_students:
            response["skipped_students"] = skipped_students
            
        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in add_student_endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the request"
        )

# --- 5. Error Handlers ---
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Validation error: {str(exc)}"
    )

# To run this API server, you use a server like Uvicorn.
# In your terminal, you would run: uvicorn api_server:app --reload --host 0.0.0.0 --port 8000