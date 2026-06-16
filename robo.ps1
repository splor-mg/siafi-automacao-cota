#Requires -Version 5.0

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8

# ---------------------------------------------------------------------------
# Funcoes auxiliares
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
    Retorna $true se o sentinela .setup_done existe E o .env tem ONEDRIVE_BASE.
    Se o .env estiver incompleto, o setup.sh re-executa apenas para coletar
    as vars ausentes — as etapas pesadas (apt, clone, venv) sao puladas.
    #>
    wsl -d Ubuntu -- bash -c "
        test -f ~/code/splor-mg/siafi-automacao-cota/.setup_done &&
        grep -q '^ONEDRIVE_BASE=' ~/code/splor-mg/siafi-automacao-cota/.env 2>/dev/null
    " 2>$null
    return $LASTEXITCODE -eq 0
}

function Request-Elevation {
    <#
    Se nao for admin, relanca este script como administrador via UAC e encerra.
    #>
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

    if (-not $isAdmin) {
        Write-Host "Solicitando permissao de administrador para instalar o WSL..."
        Start-Process PowerShell -Verb RunAs -ArgumentList `
            "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
        exit 0
    }
}

function Test-WslEngineActive {
    <#
    Retorna $true se a engine WSL2 ja esta ativa no sistema.
    Usado para saber se um reboot e necessario apos wsl --install -d Ubuntu.
    #>
    wsl --status 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function ConvertTo-WslPath {
    <#
    Converte um caminho Windows para caminho WSL.
    Trata dois casos:
      - Caminho normal: C:\Users\foo\bar  ->  /mnt/c/Users/foo/bar
      - UNC do WSL:     \\wsl.localhost\Ubuntu\home\foo  ->  /home/foo
        (ocorre quando o script e executado a partir do filesystem WSL)
    #>
    param([string]$WindowsPath)

    if ($WindowsPath -match '^\\\\wsl\.localhost\\[^\\]+\\(.*)$') {
        return '/' + $Matches[1].Replace('\', '/')
    }

    if ($WindowsPath -match '^\\\\') {
        throw "ConvertTo-WslPath: caminho UNC nao suportado: $WindowsPath"
    }

    $drive = $WindowsPath[0].ToString().ToLower()
    $rest  = $WindowsPath.Substring(2).Replace('\', '/')
    return "/mnt/$drive$rest"
}

# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "=== Robo SIAFI ===" -ForegroundColor Cyan
Write-Host ""

# Fase 1: Ubuntu nao registrado no WSL
if (-not (Test-UbuntuInstalled)) {
    $wslJaAtivo = Test-WslEngineActive

    if ($wslJaAtivo) {
        Write-Host "WSL ja instalado, mas Ubuntu nao encontrado. Registrando Ubuntu..." -ForegroundColor Yellow
    } else {
        Write-Host "WSL nao encontrado. Instalando WSL e Ubuntu..." -ForegroundColor Yellow
    }

    Request-Elevation

    Write-Host "Executando: wsl --install -d Ubuntu" -ForegroundColor Yellow
    wsl --install -d Ubuntu

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERRO: wsl --install falhou (codigo $LASTEXITCODE)." -ForegroundColor Red
        Write-Host "Verifique se a virtualizacao esta habilitada na BIOS e tente novamente." -ForegroundColor Red
        exit 1
    }

    if (-not $wslJaAtivo) {
        Write-Host ""
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host "  WSL e Ubuntu instalados com sucesso!"                       -ForegroundColor Green
        Write-Host "  REINICIE o Windows e clique em robo.bat novamente."         -ForegroundColor Green
        Write-Host "============================================================" -ForegroundColor Green
        exit 0
    }

    Write-Host ""
    Write-Host "Ubuntu registrado. Prosseguindo com a configuracao..." -ForegroundColor Green
    Write-Host ""
}

# Fase 2: Ubuntu instalado mas projeto nao configurado
if (-not (Test-SetupDone)) {
    Write-Host "Primeira execucao: configurando o ambiente Ubuntu..." -ForegroundColor Yellow
    Write-Host "(Isso pode levar alguns minutos)" -ForegroundColor Gray
    Write-Host ""

    $setupWin = Join-Path $PSScriptRoot "setup.sh"
    $setupWsl = ConvertTo-WslPath $setupWin

    wsl -d Ubuntu -- bash -c "bash '$setupWsl'"

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERRO: setup.sh falhou (codigo $LASTEXITCODE). Verifique as mensagens acima." -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "Configuracao concluida! Iniciando o robo..." -ForegroundColor Green
    Write-Host ""
}

# Fase 3: Tudo pronto — atualizar o repositorio e executar o robo
Write-Host "Atualizando o robo (git pull na main)..." -ForegroundColor Cyan
wsl -d Ubuntu -- bash -c "cd ~/code/splor-mg/siafi-automacao-cota && git checkout main && git pull origin main"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[aviso] Nao foi possivel atualizar via git pull. Rodando a versao local atual." -ForegroundColor Yellow
}
Write-Host ""

Write-Host "Iniciando o robo SIAFI..." -ForegroundColor Cyan
wsl -d Ubuntu -- bash -c "cd ~/code/splor-mg/siafi-automacao-cota && source venv/bin/activate && PYTHONIOENCODING=utf-8 python siafi_automacao/login.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "O robo encerrou com erro (codigo $LASTEXITCODE)." -ForegroundColor Red
}

exit $LASTEXITCODE
