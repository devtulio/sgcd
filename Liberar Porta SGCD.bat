@echo off
echo.
echo  SGCD — Liberar porta 3000 no Firewall do Windows
echo  -------------------------------------------------
echo  Este arquivo precisa ser executado como Administrador.
echo.

net session >nul 2>&1
if errorlevel 1 (
    echo  ERRO: Execute este arquivo clicando com o botao direito
    echo        e escolhendo "Executar como administrador".
    echo.
    pause
    exit /b 1
)

netsh advfirewall firewall show rule name="SGCD Servidor" >nul 2>&1
if not errorlevel 1 (
    echo  A regra "SGCD Servidor" ja existe no firewall.
) else (
    netsh advfirewall firewall add rule name="SGCD Servidor" dir=in action=allow protocol=TCP localport=3000
    echo  Regra criada com sucesso! Porta 3000 liberada para conexoes de entrada.
)

echo.
echo  Pressione qualquer tecla para fechar...
pause >nul
