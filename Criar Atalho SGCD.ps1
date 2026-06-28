# Cria atalho "Iniciar SGCD.lnk" na Area de Trabalho com icone personalizado
$batPath  = Join-Path $PSScriptRoot "Iniciar SGCD.bat"
$icoPath  = Join-Path $PSScriptRoot "sgcd.ico"
$desktop  = [Environment]::GetFolderPath("Desktop")
$lnkPath  = Join-Path $desktop "Iniciar SGCD.lnk"

$wsh  = New-Object -ComObject WScript.Shell
$link = $wsh.CreateShortcut($lnkPath)
$link.TargetPath       = $batPath
$link.IconLocation     = "$icoPath,0"
$link.WorkingDirectory = $PSScriptRoot
$link.WindowStyle      = 7
$link.Description      = "SGCD - Sistema de Gestao de Contratacao Direta"
$link.Save()

Write-Host "Atalho criado em: $lnkPath" -ForegroundColor Green
