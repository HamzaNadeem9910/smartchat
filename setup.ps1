# SmartChat Quick Start Setup Script for PowerShell

Write-Host "========================================"
Write-Host "  SmartChat - Quick Start Setup"
Write-Host "========================================" -ForegroundColor Blue
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please download Python from https://www.python.org/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if Node.js is installed
try {
    $nodeVersion = node --version 2>&1
    Write-Host "✓ Node.js found: $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ ERROR: Node.js is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please download Node.js from https://nodejs.org/" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if MySQL is accessible
try {
    $mysqlCheck = mysql --version 2>&1
    Write-Host "✓ MySQL found: $mysqlCheck" -ForegroundColor Green
} catch {
    Write-Host "⚠ MySQL not found in PATH. Make sure MySQL server is installed and running." -ForegroundColor Yellow
}

Write-Host ""

# Setup Backend
Write-Host "========================================"
Write-Host "Setting up Backend..."
Write-Host "========================================" -ForegroundColor Blue

Set-Location backend

Write-Host "Installing Python dependencies..."
python -m pip install -r requirements.txt

Write-Host ""
Write-Host "Creating .env file..."
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host ".env file created! Please edit it with your MySQL credentials." -ForegroundColor Green
} else {
    Write-Host ".env file already exists." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Backend setup complete!" -ForegroundColor Green
Write-Host ""

# Setup Frontend
Write-Host "========================================"
Write-Host "Setting up Frontend..."
Write-Host "========================================" -ForegroundColor Blue

Set-Location ..\frontEnd

Write-Host "Installing Node.js dependencies..."
npm install

Write-Host ""
Write-Host "Frontend setup complete!" -ForegroundColor Green
Write-Host ""

# Summary
Write-Host "========================================"
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Blue
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Edit backend/.env with your MySQL credentials"
Write-Host "2. Run database initialization:"
Write-Host "   python backend/init_db.py"
Write-Host "3. Start backend:"
Write-Host "   cd backend"
Write-Host "   uvicorn main:app --reload"
Write-Host "4. Start frontend (in another terminal):"
Write-Host "   cd frontEnd"
Write-Host "   npm run dev"
Write-Host ""
Write-Host "Frontend will be available at: http://localhost:5173"
Write-Host "Backend will be available at: http://localhost:8000"
Write-Host "API Docs at: http://localhost:8000/docs"
Write-Host ""
Read-Host "Press Enter to exit"
