@echo off
setlocal
cd /d "%~dp0\.."

echo [INFO] A remover artefactos locais nao necessarios...

if exist "frontend\node_modules" rmdir /s /q "frontend\node_modules"
if exist "frontend\dist" rmdir /s /q "frontend\dist"
if exist "frontend\.vite" rmdir /s /q "frontend\.vite"
if exist ".pytest_cache" rmdir /s /q ".pytest_cache"
if exist "__pycache__" rmdir /s /q "__pycache__"
if exist "src\__pycache__" rmdir /s /q "src\__pycache__"
if exist "tests\__pycache__" rmdir /s /q "tests\__pycache__"
if exist "data\app_state\sessions.json" del /q "data\app_state\sessions.json"
if exist "tests\golden_report_publicos.json" del /q "tests\golden_report_publicos.json"

echo [OK] Limpeza local concluida.
