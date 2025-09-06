# Face Recognition Attendance System

## 1. Project Overview

This project implements a comprehensive, API-driven system for marking attendance using real-time face recognition. The architecture is designed for modularity and remote operation, separating the concerns of student registration from the attendance marking process.

The system is comprised of two primary microservices:
* **Registration Service (`api_server.py`)**: A dedicated API server for managing the student roster. Its sole responsibility is to receive and persist student data.
* **Recognition Service (`run.py`)**: A controller API that manages the lifecycle of the face recognition task. It can be started and stopped on command, using the data provided by the Registration Service.

---

## 2. System Architecture and Workflow

The system operates based on a two-server model, ensuring that the data registration process is decoupled from the resource-intensive recognition task.

### **Workflow**

1.  **Initial Setup**: Both the Registration Service (`api_server.py`) and the Recognition Service (`run.py`) are started on the host machine, running on different ports.
2.  **Student Registration**: An external client (e.g., a master backend or administrative dashboard) sends a `POST` request to the Registration Service's `/add-student` endpoint. The request contains the roll number and a publicly accessible URL of the student's image.
3.  **Data Persistence**: The Registration Service validates the incoming data and appends it to the `students_data.json` file, which acts as the central student database.
4.  **Start Session**: To begin an attendance session, the client sends a `POST` request to the Recognition Service's `/start-recognition` endpoint.
5.  **Background Processing**: The Recognition Service initiates a background thread. This thread:
    * Reads the `students_data.json` file.
    * Downloads all student images from their respective URLs.
    * Generates face encodings for each registered student.
    * Activates the webcam and begins comparing faces in the live feed against the known encodings.
    * Records successful matches in the `attendance.json` file, ensuring each student is marked only once per day.
6.  **End Session**: To conclude the session, the client sends a `POST` request to the Recognition Service's `/stop-recognition` endpoint.
7.  **Data Retrieval**: The Recognition Service signals the background thread to terminate, safely releasing the camera and other resources. It then reads the `attendance.json` file and returns its content as the final response to the client.

---

## 3. Installation and Setup

### **Prerequisites**
* Python 3.8+
* A package manager (`pip` or `conda`). It is highly recommended to install the `dlib` library via `conda` to prevent compilation issues.
    ```bash
    conda install -c conda-forge dlib
    ```

### **Setup Instructions**

1.  **Clone the Repository**:
    ```bash
    git clone <your-repository-url>
    cd <your-project-folder>
    ```

2.  **Create and Activate a Virtual Environment**:
    ```bash
    # For Windows
    python -m venv venv
    venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**:
    Install all required packages from the provided `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```

---

## 4. Execution Instructions

The two services must be run in separate terminal windows to operate concurrently.

### **Step 1: Run the Registration Service**

This server handles adding new students to the system.

* Open a terminal in the project directory.
* Execute the following command:
    ```bash
    uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
    ```
* This service is now running and listening for requests on port **8000**.

### **Step 2: Run the Recognition Service**

This server controls the start and stop functionality of the attendance session.

* Open a **new** terminal in the project directory.
* Execute the following command:
    ```bash
    uvicorn run:app --host 0.0.0.0 --port 8001 --reload
    ```
* This service is now running and listening for requests on port **8001**.

### **Step 3: Execute a Full Attendance Session (Example)**

With both servers running, you can simulate a complete workflow using an API client like `curl`.

1.  **Register a Student**:
    ```bash
    curl -X POST http://127.0.0.1:8000/add-student -H "Content-Type: application/json" -d '{
      "classStudents": [
        {
          "rollNo": "13030824141",
          "url": "https://.../path/to/student/image.jpg"
        }
      ]
    }'
    ```

2.  **Start the Recognition Process**:
    ```bash
    curl -X POST http://127.0.0.1:8001/start-recognition
    ```
    *This will activate the camera on the server machine.*

3.  **Stop the Recognition Process and Get Results**:
    ```bash
    curl -X POST http://127.0.0.1:8001/stop-recognition
    ```
    *This will return the final attendance JSON data.*

---

## 5. API Endpoint Documentation

### **Service 1: Registration (`api_server.py`)**

#### `POST /add-student`
* **Description**: Registers one or more new students in the system.
* **Request Body**:
    ```json
    {
      "classStudents": [
        {
          "rollNo": "string",
          "url": "string (URL)"
        }
      ]
    }
    ```
* **Success Response (200 OK)**:
    ```json
    {
      "status": "success",
      "message": "Data received. Added: 1 new student(s). Skipped: 0 duplicate(s)."
    }
    ```

### **Service 2: Recognition Controller (`run.py`)**

#### `POST /start-recognition`
* **Description**: Initiates the face recognition process on a background thread.
* **Success Response (200 OK)**:
    ```json
    {
      "status": "success",
      "message": "Face recognition process started."
    }
    ```

#### `POST /stop-recognition`
* **Description**: Terminates the background recognition process, releases resources, and returns the final attendance report.
* **Success Response (200 OK)**:
    ```json
    {
      "recognizedStudents": [
        {
          "rollNo": "13030824141",
          "timestamp": "2025-09-06T13:30:10Z"
        }
      ]
    }
    ```

---

## 6. Remote Deployment with Ngrok

To expose both services to the internet for remote access, you can use **ngrok**.

### **Step 1: Install ngrok**
Download ngrok from [https://ngrok.com/download](https://ngrok.com/download) and set it up with your auth token:
```bash
ngrok config add-authtoken <YOUR_AUTH_TOKEN>
```

### **Step 2: Expose Each Service**

Run the following in separate terminals:

- Registration Service (port 8000):
```bash
ngrok http 8000
```

- Recognition Service (port 8001):
```bash
ngrok http 8001
```

### **Step 3: Expose Multiple Ports at Once**

Alternatively, you can use a single config file to expose both ports together.

Create a file ```ngrok.yml```:
```yaml
version: "2"
authtoken: <YOUR_AUTH_TOKEN>
tunnels:
  registration:
    proto: http
    addr: 8000
  recognition:
    proto: http
    addr: 8001
```

Run ngrok with this config:
```yaml
ngrok start --all --config ngrok.yml
```