@echo off

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERRO: Python nao encontrado.
    echo  Instale em https://www.python.org/downloads/
    echo  e marque "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)

start "SGCD - Servidor local" python "%~dp0server.py"
