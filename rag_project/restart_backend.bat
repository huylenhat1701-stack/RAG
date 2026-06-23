@echo off
chcp 65001 > nul
echo ==========================================
echo    Restart Backend (Fix Token Error)
echo ==========================================
echo.

echo Đang ngừng backend cũ...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq Smart Reader Backend" 2>nul

timeout /t 2 /nobreak > nul

echo Bắt đầu backend mới...
echo.

cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

echo.
echo Backend đã dừng.
pause
