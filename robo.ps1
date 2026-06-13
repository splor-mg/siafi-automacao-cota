#Requires -Version 5.0

# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

function Test-UbuntuInstalled {
    <#
    Retorna $true se a distro Ubuntu estiver registrada no WSL.
    Usa -match case-insensitive para cobrir "Ubuntu", "Ubuntu-22.04", etc.
    wsl --list --quiet emite UTF-16 LE; remove bytes nulos antes de comparar.
    #>
    $distros = (wsl --list --quiet 2>$null) -replace '\x00', ''
    if ($LASTEXITCODE -ne 0) { return $false }
    return ($distros -join "`n") -match "ubuntu"
}

function Test-SetupDone {
    <#
    Retorna $true se o arquivo sentinela .setup_done existir dentro do Ubuntu.
    O ~ é expandido pelo próprio bash dentro do WSL, usando o usuário padrão.
    #>
    wsl -d Ubuntu -- bash -c "test -f ~/code/splor-mg/siafi-automacao-cota/.setup_done" 2>$null
    return $LASTEXITCODE -eq 0
}

function Request-Elevation {
    <#
    Se não for admin, relança este script como administrador via UAC e encerra.
    #>
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

    if (-not $isAdmin) {
        Write-Host "Solicitando permissão de administrador para instalar o WSL..."
        Start-Process PowerShell -Verb RunAs -ArgumentList `
            "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
        exit 0
    }
}

function ConvertTo-WslPath {
    <#
    Converte um caminho Windows (ex: C:\Users\foo\bar) para caminho WSL (/mnt/c/Users/foo/bar).
    #>
    param([string]$WindowsPath)
    if ($WindowsPath -match '^\\\\') {
        throw "ConvertTo-WslPath: caminhos UNC não são suportados: $WindowsPath"
    }
    $drive = $WindowsPath[0].ToString().ToLower()
    $rest  = $WindowsPath.Substring(2).Replace("\", "/")
    return "/mnt/$drive$rest"
}

# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "=== Robô SIAFI ===" -ForegroundColor Cyan
Write-Host ""

# Fase 1: WSL + Ubuntu não instalados
if (-not (Test-UbuntuInstalled)) {
    Write-Host "Ubuntu/WSL não encontrado. Iniciando instalação..." -ForegroundColor Yellow
    Request-Elevation   # re-lança como admin se necessário (não retorna)

    Write-Host "Executando: wsl --install -d Ubuntu" -ForegroundColor Yellow
    wsl --install -d Ubuntu

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERRO: wsl --install falhou (código $LASTEXITCODE)." -ForegroundColor Red
        Write-Host "Verifique se a virtualização está habilitada na BIOS e tente novamente." -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host "  WSL e Ubuntu instalados com sucesso!"                       -ForegroundColor Green
    Write-Host "  REINICIE o Windows e clique em robo.bat novamente."         -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    exit 0
}

# Fase 2: Ubuntu instalado mas projeto não configurado
if (-not (Test-SetupDone)) {
    Write-Host "Primeira execução: configurando o ambiente Ubuntu..." -ForegroundColor Yellow
    Write-Host "(Isso pode levar alguns minutos)" -ForegroundColor Gray
    Write-Host ""

    $setupWin = Join-Path $PSScriptRoot "setup.sh"
    $setupWsl = ConvertTo-WslPath $setupWin

    wsl -d Ubuntu -- bash -c "bash '$setupWsl'"

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERRO: setup.sh falhou (código $LASTEXITCODE). Verifique as mensagens acima." -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "Configuração concluída! Iniciando o robô..." -ForegroundColor Green
    Write-Host ""
}

# Fase 3: Tudo pronto — executar o robô
Write-Host "Iniciando o robô SIAFI..." -ForegroundColor Cyan
wsl -d Ubuntu -- bash -c "cd ~/code/splor-mg/siafi-automacao-cota && source venv/bin/activate && python siafi_automacao/login.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "O robô encerrou com erro (código $LASTEXITCODE)." -ForegroundColor Red
}

exit $LASTEXITCODE
