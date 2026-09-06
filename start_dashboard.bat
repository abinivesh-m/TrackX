@echo off
echo Starting TrackX Dashboard...
echo Main Dashboard: http://localhost:8501
echo System Health: http://localhost:8502
echo.
echo Press Ctrl+C to stop both dashboards
echo.

start "TrackX Main Dashboard" .venv\Scripts\python.exe -m streamlit run dashboard\dashboard.py --server.port 8501
timeout /t 2 /nobreak >nul
start "TrackX System Health" .venv\Scripts\python.exe -m streamlit run dashboard\system_health.py --server.port 8502
