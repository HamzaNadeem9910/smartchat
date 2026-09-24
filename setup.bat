@echo off
REM Quick Start Script for SmartChat

echo ========================================
echo   SmartChat - Quick Start Setup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please download Python from https://www.python.org/
    pause
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please download Node.js from https://nodejs.org/
    pause
    exit /b 1
)

echo Python version:
python --version
echo.
echo Node.js version:
node --version
echo.

REM Setup Backend
echo ========================================
echo Setting up Backend...
echo ========================================
cd backend

echo Installing Python dependencies...
pip install -r requirements.txt

echo.
echo Creating .env file...
if not exist .env (
    copy .env.example .env
    echo .env file created! Please edit it with your MySQL credentials.
) else (
    echo .env file already exists.
)

echo.
echo Backend setup complete!
echo.

REM Setup Frontend
echo ========================================
echo Setting up Frontend...
echo ========================================
cd ..\frontEnd

echo Installing Node.js dependencies...
call npm install

echo.
echo Frontend setup complete!
echo.

echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit backend/.env with your MySQL credentials
echo 2. Run database initialization: python backend/init_db.py
echo 3. Start backend: cd backend && uvicorn main:app --reload
echo 4. Start frontend: cd frontEnd && npm run dev
echo.
pause
