#Requires -Version 5.0

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8

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
    Retorna $true se o sentinela .setup_done existe E o .env tem ONEDRIVE_BASE.
    Se o .env estiver incompleto (ex: atualização do login.py adicionou novas
    variáveis), o setup.sh re-executa apenas para coletar as vars ausentes —
    as etapas pesadas (apt, clone, venv) são idempotentes e são puladas.
    #>
    wsl -d Ubuntu -- bash -c "
        test -f ~/code/splor-mg/siafi-automacao-cota/.setup_done &&
        grep -q '^ONEDRIVE_BASE=' ~/code/splor-mg/siafi-automacao-cota/.env 2>/dev/null
    " 2>$null
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

function Test-WslEngineActive {
    <#
    Retorna $true se a engine WSL2 já está ativa no sistema (independente de
    haver distros registradas). Usado para saber se um reboot é necessário após
    wsl --install -d Ubuntu: se a engine já estava ativa, não é.
    #>
    wsl --status 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function ConvertTo-WslPath {
    <#
    Converte um caminho Windows para caminho WSL.
    Trata dois casos:
      - Caminho normal: C:\Users\foo\bar  →  /mnt/c/Users/foo/bar
      - UNC do WSL:     \\wsl.localhost\Ubuntu\home\foo  →  /home/foo
        (ocorre quando o script é executado a partir do filesystem WSL)
    #>
    param([string]$WindowsPath)

    if ($WindowsPath -match '^\\\\wsl\.localhost\\[^\\]+\\(.*)$') {
        # \\wsl.localhost\<distro>\<path> → /<path>
        return '/' + $Matches[1].Replace('\', '/')
    }

    if ($WindowsPath -match '^\\\\') {
        throw "ConvertTo-WslPath: caminho UNC não suportado: $WindowsPath"
    }

    $drive = $WindowsPath[0].ToString().ToLower()
    $rest  = $WindowsPath.Substring(2).Replace('\', '/')
    return "/mnt/$drive$rest"
}

# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "=== Robô SIAFI ===" -ForegroundColor Cyan
Write-Host ""

# Fase 1: Ubuntu não registrado no WSL
if (-not (Test-UbuntuInstalled)) {
    $wslJaAtivo = Test-WslEngineActive

    if ($wslJaAtivo) {
        Write-Host "WSL já instalado, mas Ubuntu não encontrado. Registrando Ubuntu..." -ForegroundColor Yellow
    } else {
        Write-Host "WSL não encontrado. Instalando WSL e Ubuntu..." -ForegroundColor Yellow
    }

    Request-Elevation   # re-lança como admin se necessário (não retorna se não for admin)

    Write-Host "Executando: wsl --install -d Ubuntu" -ForegroundColor Yellow
    wsl --install -d Ubuntu

    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERRO: wsl --install falhou (código $LASTEXITCODE)." -ForegroundColor Red
        Write-Host "Verifique se a virtualização está habilitada na BIOS e tente novamente." -ForegroundColor Red
        exit 1
    }

    if (-not $wslJaAtivo) {
        # Engine WSL foi instalada agora — reboot obrigatório para ativar virtualização
        Write-Host ""
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host "  WSL e Ubuntu instalados com sucesso!"                       -ForegroundColor Green
        Write-Host "  REINICIE o Windows e clique em robo.bat novamente."         -ForegroundColor Green
        Write-Host "============================================================" -ForegroundColor Green
        exit 0
    }

    # WSL já estava ativo — Ubuntu acabou de ser registrado, sem reboot necessário.
    # O Ubuntu abrirá para configuração de usuário/senha na Fase 2.
    Write-Host ""
    Write-Host "Ubuntu registrado. Prosseguindo com a configuração..." -ForegroundColor Green
    Write-Host ""
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
