@echo off

rem Se ja foi relancado minimizado, vai direto para o servidor
if "%1"=="--min" goto :run

rem Verifica Python antes de minimizar
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

rem Relanca esta janela minimizada e sai da janela atual
start /min "SGCD — Servidor local" "%~f0" --min
exit /b

:run
title SGCD — Servidor local
python "%~dp0server.py"
