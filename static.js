// ====================================================================
// FACE RECOGNITION ATTENDANCE SYSTEM - FRONTEND
// ====================================================================
// JavaScript functions for the web interface
// ====================================================================

// Global variables
let sessionActive = false;
let statusCheckInterval = null;

// ====================================================================
// UTILITY FUNCTIONS
// ====================================================================

function showMessage(message, type = 'info', duration = 5000) {
    const messagesDiv = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `status ${type}`;
    messageDiv.textContent = message;
    
    messagesDiv.appendChild(messageDiv);
    
    // Auto-remove message after duration
    setTimeout(() => {
        if (messageDiv.parentNode) {
            messageDiv.parentNode.removeChild(messageDiv);
        }
    }, duration);
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleString();
}

// ====================================================================
// STUDENT MANAGEMENT FUNCTIONS
// ====================================================================

async function uploadStudent() {
    const rollNumber = document.getElementById('rollNumber').value.trim();
    const photoFile = document.getElementById('photo').files[0];
    
    if (!rollNumber) {
        showMessage('Please enter a roll number', 'error');
        return;
    }
    
    if (!photoFile) {
        showMessage('Please select a photo file', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('roll_number', rollNumber);
    formData.append('photo', photoFile);
    
    try {
        const response = await fetch('/upload-student', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage(`Student ${rollNumber} uploaded successfully!`, 'success');
            document.getElementById('rollNumber').value = '';
            document.getElementById('photo').value = '';
            loadStudents(); // Refresh the list
        } else {
            showMessage(`Upload failed: ${result.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showMessage(`Upload error: ${error.message}`, 'error');
        console.error('Upload error:', error);
    }
}

async function loadStudents() {
    try {
        const response = await fetch('/students');
        const result = await response.json();
        
        const studentsList = document.getElementById('studentsList');
        
        if (result.success && result.students.length > 0) {
            studentsList.innerHTML = result.students.map(student => `
                <div class="student-item">
                    <div>
                        <strong>Roll: ${student.roll_number}</strong>
                        <br>
                        <small>File: ${student.filename}</small>
                    </div>
                    <div>
                        <img src="${student.file_path}" alt="${student.roll_number}" 
                             style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;">
                    </div>
                </div>
            `).join('');
            
            showMessage(`Loaded ${result.count} students`, 'success', 2000);
        } else {
            studentsList.innerHTML = '<p>No students uploaded yet.</p>';
            showMessage('No students found', 'info', 2000);
        }
    } catch (error) {
        showMessage(`Error loading students: ${error.message}`, 'error');
        console.error('Load students error:', error);
    }
}

async function clearAllStudents() {
    if (!confirm('Are you sure you want to clear all student data? This will also clear attendance records.')) {
        return;
    }
    
    try {
        const response = await fetch('/students', {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage('All student data cleared successfully!', 'success');
            loadStudents(); // Refresh the list
            document.getElementById('attendanceResults').textContent = '';
        } else {
            showMessage(`Clear failed: ${result.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showMessage(`Clear error: ${error.message}`, 'error');
        console.error('Clear error:', error);
    }
}

// ====================================================================
// SESSION MANAGEMENT FUNCTIONS
// ====================================================================

async function startSession() {
    try {
        const response = await fetch('/start-recognition', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            sessionActive = true;
            updateSessionStatus('Session started - Face recognition active', 'success');
            showMessage('Face recognition session started!', 'success');
            
            // Start checking session status periodically
            startStatusCheck();
        } else {
            showMessage(`Failed to start session: ${result.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showMessage(`Start session error: ${error.message}`, 'error');
        console.error('Start session error:', error);
    }
}

async function stopSession() {
    try {
        const response = await fetch('/stop-recognition', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            sessionActive = false;
            updateSessionStatus('Session stopped', 'info');
            showMessage('Face recognition session stopped!', 'success');
            
            // Stop checking session status
            stopStatusCheck();
            
            // Automatically load attendance after stopping
            setTimeout(getAttendance, 1000);
        } else {
            showMessage(`Failed to stop session: ${result.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showMessage(`Stop session error: ${error.message}`, 'error');
        console.error('Stop session error:', error);
    }
}

async function checkSessionStatus() {
    try {
        const response = await fetch('/session-status');
        const result = await response.json();
        
        if (result.success) {
            sessionActive = result.session_active;
            const statusText = sessionActive ? 'Session active - Face recognition running' : 'Session not active';
            const statusType = sessionActive ? 'success' : 'info';
            updateSessionStatus(statusText, statusType);
        }
    } catch (error) {
        console.error('Status check error:', error);
        updateSessionStatus('Status check failed', 'error');
    }
}

function updateSessionStatus(message, type) {
    const statusDiv = document.getElementById('sessionStatus');
    statusDiv.textContent = message;
    statusDiv.className = `status ${type}`;
}

function startStatusCheck() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
    statusCheckInterval = setInterval(checkSessionStatus, 2000); // Check every 2 seconds
}

function stopStatusCheck() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
}

// ====================================================================
// ATTENDANCE FUNCTIONS
// ====================================================================

async function getAttendance() {
    try {
        const response = await fetch('/attendance');
        const result = await response.json();
        
        const attendanceDiv = document.getElementById('attendanceResults');
        
        if (result.success) {
            const attendanceData = result.data;
            const students = attendanceData.recognizedStudents || [];
            
            if (students.length > 0) {
                // Format the attendance data nicely
                const formattedData = {
                    summary: {
                        totalStudents: students.length,
                        generatedAt: new Date().toISOString()
                    },
                    recognizedStudents: students.map(student => ({
                        rollNo: student.rollNo,
                        timestamp: student.timestamp,
                        formattedTime: formatTimestamp(student.timestamp)
                    }))
                };
                
                attendanceDiv.textContent = JSON.stringify(formattedData, null, 2);
                showMessage(`Loaded attendance for ${students.length} students`, 'success');
            } else {
                attendanceDiv.textContent = 'No attendance data available yet.';
                showMessage('No attendance records found', 'info');
            }
        } else {
            attendanceDiv.textContent = `Error: ${result.message || 'Failed to load attendance'}`;
            showMessage(`Attendance error: ${result.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        showMessage(`Attendance error: ${error.message}`, 'error');
        console.error('Attendance error:', error);
        document.getElementById('attendanceResults').textContent = `Error: ${error.message}`;
    }
}

async function downloadAttendance() {
    try {
        const response = await fetch('/attendance/download');
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `attendance_${new Date().toISOString().slice(0,19).replace(/:/g, '-')}.json`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showMessage('Attendance file downloaded!', 'success');
        } else {
            showMessage('No attendance data available for download', 'error');
        }
    } catch (error) {
        showMessage(`Download error: ${error.message}`, 'error');
        console.error('Download error:', error);
    }
}

// ====================================================================
// DRAG AND DROP FILE UPLOAD
// ====================================================================

function setupDragAndDrop() {
    const photoInput = document.getElementById('photo');
    const container = document.querySelector('.container');
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        container.addEventListener(eventName, preventDefaults, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
        container.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        container.addEventListener(eventName, unhighlight, false);
    });
    
    container.addEventListener('drop', handleDrop, false);
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    function highlight(e) {
        container.style.background = '#e3f2fd';
        container.style.border = '2px dashed #2196f3';
    }
    
    function unhighlight(e) {
        container.style.background = '#f4f4f4';
        container.style.border = 'none';
    }
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length > 0) {
            photoInput.files = files;
            showMessage(`File "${files[0].name}" ready for upload`, 'info', 3000);
        }
    }
}

// ====================================================================
// KEYBOARD SHORTCUTS
// ====================================================================

function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Ctrl+Enter to upload student
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            uploadStudent();
        }
        
        // Ctrl+S to start session
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            startSession();
        }
        
        // Ctrl+X to stop session
        if (e.ctrlKey && e.key === 'x') {
            e.preventDefault();
            stopSession();
        }
        
        // Ctrl+A to get attendance (when not in input field)
        if (e.ctrlKey && e.key === 'a' && !e.target.matches('input, textarea')) {
            e.preventDefault();
            getAttendance();
        }
    });
}

// ====================================================================
// INITIALIZATION
// ====================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('Face Recognition Attendance System - Frontend Loaded');
    
    // Load initial data
    loadStudents();
    checkSessionStatus();
    
    // Setup drag and drop
    setupDragAndDrop();
    
    // Setup keyboard shortcuts
    setupKeyboardShortcuts();
    
    // Add download button functionality
    const attendanceContainer = document.querySelector('h2:contains("Attendance Results")');
    if (attendanceContainer) {
        const downloadBtn = document.createElement('button');
        downloadBtn.className = 'button';
        downloadBtn.textContent = 'Download Attendance';
        downloadBtn.onclick = downloadAttendance;
        attendanceContainer.parentNode.appendChild(downloadBtn);
    }
    
    showMessage('System ready! Upload students and start recognition session.', 'success', 3000);
    
    console.log('Available keyboard shortcuts:');
    console.log('- Ctrl+Enter: Upload student');
    console.log('- Ctrl+S: Start session');
    console.log('- Ctrl+X: Stop session');
    console.log('- Ctrl+A: Get attendance');
});