@echo off
setlocal
cd /d "%~dp0\.."

if not exist "frontend\package.json" (
  echo [ERRO] A pasta frontend nao existe nesta base.
  exit /b 1
)

cd frontend
if not exist "node_modules" (
  echo [INFO] node_modules nao encontrado. A instalar dependencias frontend...
  call npm install
  if errorlevel 1 exit /b 1
)

call npm run dev
