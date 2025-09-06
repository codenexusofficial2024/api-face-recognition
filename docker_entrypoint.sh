#!/bin/bash
# ====================================================================
# DOCKER ENTRYPOINT SCRIPT
# Face Recognition Attendance System
# ====================================================================
# This script handles container initialization and startup
# ====================================================================

set -e  # Exit on any error

# ====================================================================
# CONFIGURATION
# ====================================================================

# Default values (can be overridden by environment variables)
export HOST=${HOST:-"0.0.0.0"}
export PORT=${PORT:-8000}
export IMAGES_FOLDER=${IMAGES_FOLDER:-"student-images"}
export ATTENDANCE_FILE=${ATTENDANCE_FILE:-"attendance.json"}
export LOG_LEVEL=${LOG_LEVEL:-"info"}
export WORKERS=${WORKERS:-1}

# ====================================================================
# LOGGING SETUP
# ====================================================================

# Colors for logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    if [ "$LOG_LEVEL" = "debug" ]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# ====================================================================
# SYSTEM CHECKS
# ====================================================================

log_info "Starting Face Recognition Attendance System..."
log_info "Container initialization beginning..."

# Check Python installation
if ! command -v python3 &> /dev/null; then
    log_error "Python3 not found!"
    exit 1
fi

log_info "Python version: $(python3 --version)"

# Check required Python packages
log_info "Checking required packages..."

required_packages=(
    "fastapi"
    "uvicorn"
    "cv2"
    "face_recognition"
    "numpy"
)

missing_packages=()

for package in "${required_packages[@]}"; do
    if ! python3 -c "import $package" &> /dev/null; then
        missing_packages+=("$package")
    fi
done

if [ ${#missing_packages[@]} -ne 0 ]; then
    log_error "Missing required packages: ${missing_packages[*]}"
    log_error "Please check your Docker image build process"
    exit 1
fi

log_info "All required packages are available"

# ====================================================================
# DIRECTORY SETUP
# ====================================================================

log_info "Setting up directories..."

# Create required directories
mkdir -p "$IMAGES_FOLDER"
mkdir -p "static"
mkdir -p "logs"
mkdir -p "uploads"

# Set permissions (if running as non-root, this might fail, but that's okay)
chmod -R 755 "$IMAGES_FOLDER" 2>/dev/null || true
chmod -R 755 "static" 2>/dev/null || true
chmod -R 755 "logs" 2>/dev/null || true

log_info "Directories created successfully"

# ====================================================================
# CAMERA DETECTION
# ====================================================================

log_info "Checking camera availability..."

# Check for video devices (Linux)
if [ -d "/dev" ]; then
    video_devices=$(ls /dev/video* 2>/dev/null | wc -l || echo "0")
    if [ "$video_devices" -gt 0 ]; then
        log_info "Found $video_devices video device(s)"
        ls -la /dev/video* 2>/dev/null || true
    else
        log_warn "No video devices found in /dev/"
        log_warn "Camera access may not work properly"
        log_warn "Make sure to run container with --device /dev/video0 flag"
    fi
else
    log_warn "/dev directory not accessible"
fi

# Check camera permissions
if [ -c "/dev/video0" ]; then
    if [ -r "/dev/video0" ] && [ -w "/dev/video0" ]; then
        log_info "Camera permissions look good"
    else
        log_warn "Camera permissions may be insufficient"
        log_warn "You may need to add user to video group or run with appropriate privileges"
    fi
fi

# ====================================================================
# FILE CHECKS
# ====================================================================

log_info "Checking application files..."

required_files=(
    "app.py"
    "face_recognition_module.py"
)

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        log_error "Required file not found: $file"
        exit 1
    fi
done

# Check if static directory has content
if [ ! -f "static/app.js" ]; then
    log_warn "Frontend JavaScript not found (static/app.js)"
    log_warn "Web interface may not work properly"
fi

log_info "Application files check completed"

# ====================================================================
# ENVIRONMENT INFO
# ====================================================================

log_info "Container Environment Information:"
log_info "- Host: $HOST"
log_info "- Port: $PORT"
log_info "- Images Folder: $IMAGES_FOLDER"
log_info "- Attendance File: $ATTENDANCE_FILE"
log_info "- Log Level: $LOG_LEVEL"
log_info "- Workers: $WORKERS"
log_info "- Working Directory: $(pwd)"
log_info "- User: $(whoami)"
log_info "- Python Path: $PYTHONPATH"

# ====================================================================
# HEALTH CHECK SETUP
# ====================================================================

# Create a simple health check endpoint test
create_health_check() {
    log_debug "Setting up health check..."
    
    # This will be used by Docker's HEALTHCHECK
    cat > /tmp/health_check.py << 'EOF'
import requests
import sys
import os

try:
    port = os.environ.get('PORT', 8000)
    response = requests.get(f'http://localhost:{port}/session-status', timeout=5)
    if response.status_code == 200:
        print("Health check passed")
        sys.exit(0)
    else:
        print(f"Health check failed with status: {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"Health check failed with error: {e}")
    sys.exit(1)
EOF
    
    chmod +x /tmp/health_check.py
}

create_health_check

# ====================================================================
# SIGNAL HANDLING
# ====================================================================

# Handle shutdown signals gracefully
cleanup() {
    log_info "Received shutdown signal, cleaning up..."
    
    # Kill any background processes
    jobs -p | xargs -r kill -TERM
    
    # Clean up temporary files
    rm -f /tmp/health_check.py 2>/dev/null || true
    
    log_info "Cleanup completed"
    exit 0
}

# Trap signals
trap cleanup SIGTERM SIGINT SIGQUIT

# ====================================================================
# STARTUP
# ====================================================================

log_info "Starting Face Recognition Attendance System Server..."
log_info "Access the application at: http://localhost:$PORT"
log_info "API documentation at: http://localhost:$PORT/docs"
log_info "Press Ctrl+C to stop"

# Start the application
if [ "$1" = "uvicorn" ]; then
    # Run with uvicorn
    exec python3 -m uvicorn app:app \
        --host "$HOST" \
        --port "$PORT" \
        --log-level "$LOG_LEVEL" \
        --workers "$WORKERS" \
        --access-log \
        --use-colors
elif [ "$1" = "debug" ]; then
    # Debug mode - run with auto-reload
    log_info "Starting in DEBUG mode with auto-reload"
    exec python3 -m uvicorn app:app \
        --host "$HOST" \
        --port "$PORT" \
        --reload \
        --log-level "debug" \
        --access-log \
        --use-colors
elif [ "$1" = "test" ]; then
    # Test mode - just run tests and exit
    log_info "Running in TEST mode"
    python3 -c "
import sys
sys.path.append('.')
from face_recognition_module import FaceRecognitionSystem
print('Testing face recognition module...')
system = FaceRecognitionSystem()
status = system.get_status()
print(f'System status: {status}')
print('Test completed successfully!')
"
    exit 0
elif [ "$1" = "shell" ]; then
    # Shell mode - drop into bash for debugging
    log_info "Starting interactive shell for debugging"
    exec /bin/bash
else
    # Default: run the command as-is
    exec "$@"
fi