@echo off
chcp 65001 > nul
echo ==========================================
echo    Smart Document Reader - Khoi dong
echo    He thong Doc Tai Lieu Thong Minh
echo ==========================================
echo.

cd /d "%~dp0"

echo [1/2] Chay Backend FastAPI...
start "Smart Reader Backend" cmd /k "cd /d %~dp0 && set PYTHONIOENCODING=utf-8 && chcp 65001 > nul && uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

echo Doi backend khoi dong (5 giay)...
timeout /t 5 /nobreak > nul

echo [2/2] Chay Frontend Streamlit...
start "Smart Reader Frontend" cmd /k "cd /d %~dp0 && set PYTHONIOENCODING=utf-8 && chcp 65001 > nul && streamlit run frontend/app.py --server.port 8501"

echo.
echo ==========================================
echo    Smart Document Reader da khoi dong!
echo   - Backend API:  http://localhost:8000
echo   - Swagger UI:   http://localhost:8000/docs
echo   - Frontend:     http://localhost:8501
echo ==========================================
echo.
pause
