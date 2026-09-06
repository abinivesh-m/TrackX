@echo off
REM TrackX Full Real Demo Script (Windows)

echo ============================================
echo  TRACKX REAL 7-CAMERA DEMO
echo ============================================
echo.

REM Step 1: Check Python installation
echo [1/8] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.11+
    pause
    exit /b 1
)

REM Step 2: Install dependencies
echo [2/8] Installing Python dependencies...
pip install ultralytics paddleocr opencv-python pillow numpy

REM Step 3: Generate camera videos
echo [3/8] Checking camera videos...
if not exist "data\cameras\CAM_01\videos\CAM_01_demo.mp4" (
    echo Generating camera videos...
    python scripts\generate_7_camera_videos.py
) else (
    echo Camera videos already exist.
)

REM Step 4: Start Docker services
echo [4/8] Starting Docker services...
if exist docker-compose.yml (
    docker-compose up -d postgres redis
) else (
    echo WARNING: docker-compose.yml not found. Starting without Docker...
)

REM Step 5: Install backend dependencies
echo [5/8] Installing backend dependencies...
cd backend
if exist requirements.txt (
    pip install -r requirements.txt
) else (
    echo WARNING: requirements.txt not found. Skipping backend dependencies.
)
cd ..

REM Step 6: Run the real pipeline
echo [6/8] Running REAL TrackX pipeline...
python scripts\run_real_pipeline.py

REM Step 7: Verify real data
echo [7/8] Verifying REAL data...
python scripts\verify_real_data.py

REM Step 8: Start services
echo [8/8] Starting TrackX services...
echo.
echo Starting FastAPI backend...
cd backend
start "TrackX Backend" cmd /k "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
cd ..

echo Starting React frontend...
cd frontend
if exist package.json (
    if not exist node_modules (
        echo Installing frontend dependencies...
        call npm install
    )
    start "TrackX Frontend" cmd /k "npm run dev"
) else (
    echo WARNING: package.json not found. Skipping frontend.
)
cd ..

echo.
echo ============================================
echo  TRACKX IS RUNNING!
echo ============================================
echo.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Login with: admin@trackx.com / admin123
echo.
echo Search for plate: TN38AB1234
echo ============================================
echo.
echo Press any key to stop all services...
pause >nul

REM Cleanup
echo.
echo Stopping services...
taskkill /FI "WINDOWTITLE eq TrackX Backend*" /T >nul 2>&1
taskkill /FI "WINDOWTITLE eq TrackX Frontend*" /T >nul 2>&1
echo Services stopped.
pause
