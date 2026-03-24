@echo off
setlocal
cd /d "%~dp0\.."

set PYTHON_EXE=python
if exist ".venv\Scripts\python.exe" set PYTHON_EXE=.venv\Scripts\python.exe

%PYTHON_EXE% -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
  echo [ERRO] FastAPI/Uvicorn nao estao instalados neste ambiente.
  echo [INFO] Corre primeiro: pip install -r requirements-api.txt
  exit /b 1
)

%PYTHON_EXE% -m uvicorn api:app --reload
