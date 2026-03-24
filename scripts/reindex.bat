@echo off
setlocal
cd /d "%~dp0\.."

if not defined LLM_MODEL set LLM_MODEL=mistral
if not defined EMBEDDING_MODEL set EMBEDDING_MODEL=nomic-embed-text

set PYTHON_EXE=python
if exist ".venv\Scripts\python.exe" set PYTHON_EXE=.venv\Scripts\python.exe

%PYTHON_EXE% scripts\ingest.py
