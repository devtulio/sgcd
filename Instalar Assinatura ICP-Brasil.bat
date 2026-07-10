@echo off
setlocal

rem Habilita o modulo opcional de assinatura com certificado ICP-Brasil A1
rem (pyhanko). So necessario se essa modalidade de assinatura for usada nesta
rem maquina — o resto do SGCD funciona sem isso.
rem
rem Se o servidor usa o Python embarcavel (extraido por "Iniciar SGCD.bat" em
rem maquinas sem Python instalado), o pip nao vem pronto nesse pacote — nem o
rem modulo "ensurepip" (removido de propósito do embarcavel). Este script usa
rem o "get-pip.py" ja incluido no projeto para nao depender de baixar esse
rem arquivo à parte, mas ESTE SCRIPT INTEIRO PRECISA DE ACESSO A INTERNET: o
rem proprio get-pip.py busca a versao mais recente do pip no PyPI, e o pyhanko
rem (com suas dependencias) tambem vem do PyPI.

set "EMBED_PY=C:\Python312-embed\python.exe"
set "PYEXE=python"

python --version >nul 2>&1
if not errorlevel 1 goto :checapip

if exist "%EMBED_PY%" (
    set "PYEXE=%EMBED_PY%"
    goto :checapip
)

echo.
echo  ERRO: Nenhum Python encontrado ^(nem no PATH, nem embarcavel em C:\Python312-embed^).
echo  Rode "Iniciar SGCD.bat" primeiro nesta maquina.
echo.
pause
exit /b 1

:checapip
"%PYEXE%" -m pip --version >nul 2>&1
if not errorlevel 1 goto :instalarequirements

echo.
echo  Instalando pip ^(usando get-pip.py incluido no projeto^)...
echo.
"%PYEXE%" "%~dp0get-pip.py" --no-warn-script-location
if errorlevel 1 (
    echo.
    echo  ERRO: Falha ao instalar o pip.
    echo.
    pause
    exit /b 1
)

:instalarequirements
echo.
echo  Instalando pyhanko ^(requer acesso a internet — vem do PyPI^)...
echo.
"%PYEXE%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo  ERRO: Falha ao instalar pyhanko. Verifique o acesso a internet.
    echo.
    pause
    exit /b 1
)

echo.
echo  Pronto. Reinicie o SGCD para a assinatura ICP-Brasil ficar disponivel.
echo.
pause
