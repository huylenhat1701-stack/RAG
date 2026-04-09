@echo off
echo ==========================================
echo    RAG Q^&A System - Khoi dong he thong
echo ==========================================
echo.

cd /d "%~dp0"

echo [1/2] Chay Backend FastAPI...
start "RAG Backend" cmd /k "cd /d %~dp0 && uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

echo Doi backend khoi dong (5 giay)...
timeout /t 5 /nobreak > nul

echo [2/2] Chay Frontend Streamlit...
start "RAG Frontend" cmd /k "cd /d %~dp0 && streamlit run frontend/app.py --server.port 8501"

echo.
echo ==========================================
echo He thong da khoi dong!
echo   - Backend API:  http://localhost:8000
echo   - Swagger UI:   http://localhost:8000/docs
echo   - Frontend:     http://localhost:8501
echo ==========================================
echo.
pause
