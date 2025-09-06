import json
import os
from typing import List

# Import FastAPI and Pydantic for building the API and validating data
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- 1. Define the structure of the data we expect ---
# Pydantic models validate the incoming request data.
# If the data doesn't match this structure, FastAPI returns an error automatically.

class Student(BaseModel):
    rollNo: str
    url: str

class StudentPayload(BaseModel):
    classStudents: List[Student]

# --- 2. Initialize the FastAPI application ---
app = FastAPI(
    title="Student Data API",
    description="An API to receive and store student data."
)

# The name of the file where we will store the student data.
STUDENTS_DATA_FILE = 'students_data.json'

# --- 3. Create the API Endpoint ---
# @app.post("/add-student") creates a URL endpoint that only accepts POST requests.
# This is the URL your friend's backend will "push" the JSON to.

@app.post("/add-student")
async def add_student_endpoint(payload: StudentPayload):
    """
    Receives student data via a POST request and appends it to a JSON file.
    """
    # --- Load Existing Data ---
    if os.path.exists(STUDENTS_DATA_FILE):
        try:
            with open(STUDENTS_DATA_FILE, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            data = {"classStudents": []}
    else:
        data = {"classStudents": []}

    # Get a list of roll numbers we already have
    existing_roll_nos = {student['rollNo'] for student in data['classStudents']}
    
    added_count = 0
    skipped_count = 0

    # --- Process the incoming student(s) from the payload ---
    for student_to_add in payload.classStudents:
        if student_to_add.rollNo not in existing_roll_nos:
            # Add the new student to our data and the set of existing roll numbers
            data['classStudents'].append(student_to_add.dict())
            existing_roll_nos.add(student_to_add.rollNo)
            added_count += 1
        else:
            skipped_count += 1

    # --- Save the updated data back to the file ---
    try:
        with open(STUDENTS_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        # If saving fails, return a server error
        raise HTTPException(status_code=500, detail=f"Failed to write to file: {e}")

    # --- Return a success response ---
    return {
        "status": "success",
        "message": f"Data received. Added: {added_count} new student(s). Skipped: {skipped_count} duplicate(s)."
    }

# To run this API server, you use a server like Uvicorn.
# In your terminal, you would run: uvicorn api_server:app --reload