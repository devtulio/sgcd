@echo off
setlocal

set "EMBED_DIR=C:\Python312-embed"
set "EMBED_PY=%EMBED_DIR%\python.exe"
set "EMBED_ZIP=%~dp0python-3.12.9-embed-amd64.zip"
set "PYEXE=python"

python --version >nul 2>&1
if not errorlevel 1 goto :run

if exist "%EMBED_PY%" (
    set "PYEXE=%EMBED_PY%"
    goto :run
)

if not exist "%EMBED_ZIP%" goto :erro_sem_python

echo.
echo  Python nao encontrado no sistema.
echo  Extraindo Python embarcado incluido no SGCD ^(primeira execucao apenas^)...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Test-Path '%EMBED_DIR%') { Remove-Item '%EMBED_DIR%' -Recurse -Force }; Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%EMBED_ZIP%', '%EMBED_DIR%')"

if not exist "%EMBED_PY%" (
    echo.
    echo  ERRO: Falha ao extrair o Python embarcado em %EMBED_DIR%.
    echo  Verifique se ha permissao de escrita em C:\ ou instale o Python manualmente.
    echo.
    pause
    exit /b 1
)

set "PYEXE=%EMBED_PY%"
echo  Python embarcado pronto em %EMBED_DIR%
echo.
goto :run

:erro_sem_python
echo.
echo  ERRO: Python nao encontrado.
echo  Instale em https://www.python.org/downloads/
echo  e marque "Add Python to PATH" durante a instalacao.
echo.
pause
exit /b 1

:run
start "SGCD - Servidor local" "%PYEXE%" "%~dp0server.py"
