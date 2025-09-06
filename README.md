# Face Recognition Attendance System

A comprehensive web-based attendance system using face recognition technology, built with FastAPI, OpenCV, and modern web technologies.

## 🚀 Features

- **Real-time Face Recognition**: Detect and recognize student faces using camera
- **Web-based Interface**: Upload student data and manage attendance through a modern web UI
- **RESTful API**: Full FastAPI backend with automatic documentation
- **Docker Support**: Easy deployment with Docker and Docker Compose
- **Persistent Storage**: JSON-based attendance records with duplicate prevention
- **Multiple Upload Options**: Single or batch student data upload
- **Session Management**: Start/stop recognition sessions programmatically
- **Real-time Status**: Live session status and attendance updates

## 📁 Project Structure

```
face-recognition-attendance/
├── app.py                          # FastAPI server
├── face_recognition_module.py      # Modular face recognition system
├── requirements.txt                # Python dependencies
├── requirements_docker.txt         # Docker-specific dependencies
├── Dockerfile                      # Docker container configuration
├── docker-compose.yml              # Multi-service deployment
├── docker-entrypoint.sh           # Container startup script
├── static/
│   └── app.js                     # Frontend JavaScript
├── student-images/                 # Student photos (created automatically)
├── attendance.json                 # Attendance records (created automatically)
└── README.md                      # This file
```

## 🛠 Installation & Setup

### Option 1: Docker Deployment (Recommended)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd face-recognition-attendance
   ```

2. **Build and run with Docker Compose**:
   ```bash
   # Start all services
   docker-compose up -d
   
   # Or start only the main application
   docker-compose up face-recognition-app
   ```

3. **Access the application**:
   - Web Interface: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### Option 2: Local Installation

1. **System Dependencies** (Ubuntu/Debian):
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3-dev cmake build-essential
   sudo apt-get install -y libopencv-dev python3-opencv
   sudo apt-get install -y libjpeg-dev libpng-dev libtiff-dev
   sudo apt-get install -y libavcodec-dev libavformat-dev libswscale-dev
   sudo apt-get install -y libv4l-dev libxvidcore-dev libx264-dev
   sudo apt-get install -y libgtk-3-dev libatlas-base-dev gfortran
   ```

2. **Python Environment**:
   ```bash
   # Create virtual environment
   python -m venv face_recognition_env
   source face_recognition_env/bin/activate  # Linux/Mac
   # OR: face_recognition_env\Scripts\activate  # Windows
   
   # Install dependencies
   pip install --upgrade pip setuptools wheel
   pip install -r requirements.txt
   ```

3. **Alternative with Conda (Recommended for dlib)**:
   ```bash
   conda create -n face_recognition_env python=3.9
   conda activate face_recognition_env
   conda install -c conda-forge dlib
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   python app.py
   # OR
   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```

## 📝 Usage Guide

### 1. Upload Student Data

**Web Interface**:
1. Open http://localhost:8000 in your browser
2. Enter student roll number
3. Select student photo
4. Click "Add Student"

**API Endpoint**:
```bash
curl -X POST "http://localhost:8000/upload-student" \
     -F "roll_number=12345" \
     -F "photo=@student_photo.jpg"
```

### 2. Start Recognition Session

**Web Interface**:
- Click "Start Recognition" button
- Grant camera permissions if prompted

**API Endpoint**:
```bash
curl -X POST "http://localhost:8000/start-recognition"
```

### 3. Monitor Attendance

**Web Interface**:
- Click "Get Attendance" to view current results
- Attendance updates automatically during sessions

**API Endpoint**:
```bash
curl "http://localhost:8000/attendance"
```

### 4. Download Results

**Web Interface**:
- Click "Download Attendance" button

**API Endpoint**:
```bash
curl "http://localhost:8000/attendance/download" -o attendance.json
```

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web interface |
| POST | `/upload-student` | Upload single student |
| POST | `/upload-multiple-students` | Upload multiple students |
| GET | `/students` | Get all students |
| DELETE | `/students` | Clear all students |
| POST | `/start-recognition` | Start face recognition |
| POST | `/stop-recognition` | Stop face recognition |
| GET | `/session-status` | Get session status |
| GET | `/attendance` | Get attendance data |
| GET | `/attendance/download` | Download attendance file |

## 🐳 Docker Configuration

### Basic Usage

```bash
# Build the image
docker build -t face-recognition-attendance .

# Run with camera access (Linux)
docker run -it --rm \
  --device /dev/video0:/dev/video0 \
  -p 8000:8000 \
  -v $(pwd)/student-images:/app/student-images \
  -v $(pwd)/attendance.json:/app/attendance.json \
  face-recognition-attendance

# Run with Docker Compose
docker-compose up -d
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| HOST | 0.0.0.0 | Server host |
| PORT | 8000 | Server port |
| IMAGES_FOLDER | student-images | Student photos folder |
| ATTENDANCE_FILE | attendance.json | Attendance data file |
| LOG_LEVEL | info | Logging level |
| WORKERS | 1 | Number of worker processes |

### Volume Mounts

- `./student-images:/app/student-images` - Persistent student photos
- `./attendance.json:/app/attendance.json` - Persistent attendance data
- `./logs:/app/logs` - Application logs

## 📊 Data Formats

### Student Upload Format

- **Roll Number**: Alphanumeric string (e.g., "12345", "ST001")
- **Photo**: Image file (JPG, PNG, GIF, BMP)
- **File Naming**: Photos saved as `{roll_number}.{extension}`

### Attendance JSON Format

```json
{
  "recognizedStudents": [
    {
      "rollNo": "12345",
      "timestamp": "2025-09-06T10:30:15Z"
    },
    {
      "rollNo": "67890",
      "timestamp": "2025-09-06T10:30:18Z"
    }
  ]
}
```

## ⚙️ Configuration

### Camera Settings

The system automatically detects available cameras. For manual configuration:

```python
# In face_recognition_module.py
def initialize_camera(self):
    # Try specific camera index
    camera_index = 0  # Change this value
    self.video_capture = cv2.VideoCapture(camera_index)
```

### Recognition Settings

```python
# In face_recognition_module.py
# Face recognition threshold (lower = more strict)
if face_distances[best_match_index] < 0.6:  # Adjust this value

# Recognition cooldown (seconds between same student detections)
recognition_cooldown = 5  # Adjust this value
```

## 🔍 Troubleshooting

### Common Issues

1. **Camera Not Found**:
   ```bash
   # Check available cameras (Linux)
   ls /dev/video*
   
   # Test camera access
   v4l2-ctl --list-devices
   ```

2. **dlib Installation Fails**:
   ```bash
   # Use conda instead
   conda install -c conda-forge dlib
   
   # Or install build tools first
   sudo apt-get install build-essential cmake
   ```

3. **Face Recognition Not Working**:
   - Ensure good lighting conditions
   - Check if faces are clearly visible in photos
   - Verify camera permissions
   - Try adjusting recognition threshold

4. **Port Already in Use**:
   ```bash
   # Use different port
   uvicorn app:app --port 8001
   
   # Or kill process using port 8000
   sudo lsof -t -i:8000 | xargs kill -9
   ```

5. **Docker Camera Access**:
   ```bash
   # Linux - add user to video group
   sudo usermod -a -G video $USER
   
   # Restart Docker daemon
   sudo systemctl restart docker
   ```

### Debug Mode

```bash
# Run in debug mode
python app.py
# OR
uvicorn app:app --reload --log-level debug

# Docker debug mode
docker run -it face-recognition-attendance debug
```

## 🧪 Testing

### Manual Testing

```bash
# Test face recognition module
python face_recognition_module.py

# Test API endpoints
curl http://localhost:8000/session-status
```

### Unit Tests (if implemented)

```bash
python -m pytest tests/
```

## 🔒 Security Considerations

- **Camera Access**: Only grant camera permissions to trusted applications
- **File Uploads**: Validate file types and sizes
- **Data Storage**: Secure student photos and attendance data
- **Network**: Use HTTPS in production
- **Container Security**: Run containers with non-root users

## 🚀 Production Deployment

### Using Gunicorn

```bash
pip install gunicorn
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Environment Variables for Production

```bash
export HOST=0.0.0.0
export PORT=8000
export LOG_LEVEL=warning
export WORKERS=4
```

## 📈 Performance Optimization

- **Image Resize**: Reduce camera resolution for faster processing
- **Frame Skip**: Process every nth frame instead of all frames
- **Threading**: Use separate threads for recognition and web server
- **Caching**: Cache face encodings in memory
- **GPU**: Use GPU-accelerated OpenCV if available

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:

1. Check the troubleshooting section
2. Review API documentation at `/docs`
3. Create an issue on GitHub
4. Check system logs: `docker-compose logs -f`

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OpenCV Python Tutorials](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html)
- [Face Recognition Library](https://github.com/ageitgey/face_recognition)
- [Docker Documentation](https://docs.docker.com/)

---

**Made with ❤️ for automated attendance tracking**