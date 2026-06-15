# WSL Launcher — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar três arquivos (`robo.bat`, `robo.ps1`, `setup.sh`) que permitem executar o robô SIAFI com um duplo-clique no Windows, instalando e configurando o WSL Ubuntu automaticamente na primeira vez.

**Architecture:** `robo.bat` é o ponto de entrada (duplo-clique); chama `robo.ps1` que detecta em qual fase está (sem WSL, sem setup, pronto) e avança o estado; na fase de setup, executa `setup.sh` dentro do Ubuntu via `wsl`; nas execuções seguintes, executa diretamente `login.py`.

**Tech Stack:** Windows Batch, PowerShell 5+, Bash, WSL2 (`wsl --install`), Ubuntu apt, Python venv.

---

## Mapa de arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `robo.bat` | Criar | Ponto de entrada; invoca PowerShell com ExecutionPolicy Bypass |
| `robo.ps1` | Criar | Máquina de estados: detecta fase, instala WSL, executa setup ou robô |
| `setup.sh` | Criar | Configura Ubuntu: apt, git clone, venv, pip, .env interativo, sentinela |

Nenhum arquivo existente é modificado.

---

## Task 1: `robo.bat` — ponto de entrada

**Files:**
- Criar: `robo.bat`

- [ ] **Passo 1: Criar `robo.bat`**

O arquivo detecta se está rodando como administrador e, se precisar de elevação, a solicita via PowerShell. Caso contrário, simplesmente chama `robo.ps1`.

```batch
@echo off
setlocal

:: %~dp0 já termina com barra — passa o caminho completo do script diretamente
PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0robo.ps1"

pause
endlocal
```

- [ ] **Passo 2: Verificar sintaxe**

Abra um terminal no diretório do projeto e execute:

```cmd
cmd /c "robo.bat"
```

Resultado esperado: uma janela PowerShell abre (ou mensagem de erro porque `robo.ps1` ainda não existe — isso é esperado neste passo). O `pause` mantém a janela aberta.

- [ ] **Passo 3: Commit**

```bash
git add robo.bat
git commit -m "feat: adiciona robo.bat como ponto de entrada do launcher"
```

---

## Task 2: `robo.ps1` — máquina de estados

**Files:**
- Criar: `robo.ps1`

- [ ] **Passo 1: Criar `robo.ps1` com funções auxiliares**

```powershell
#Requires -Version 5.0

# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

function Test-UbuntuInstalled {
    <#
    Retorna $true se a distro Ubuntu estiver registrada no WSL.
    Usa -match case-insensitive para cobrir "Ubuntu", "Ubuntu-22.04", etc.
    #>
    $distros = wsl --list --quiet 2>$null
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
    $drive = $WindowsPath[0].ToString().ToLower()
    $rest  = $WindowsPath.Substring(2).Replace("\", "/")
    return "/mnt/$drive$rest"
}
```

- [ ] **Passo 2: Adicionar o fluxo principal ao `robo.ps1`**

Acrescente ao final do arquivo criado no passo anterior:

```powershell
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

    wsl -d Ubuntu -- bash "$setupWsl"

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
```

- [ ] **Passo 3: Verificar sintaxe do PowerShell**

```powershell
$errors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    (Resolve-Path "robo.ps1").Path, [ref]$null, [ref]$errors
)
if ($errors.Count -eq 0) { Write-Host "OK: sem erros de sintaxe" } else { $errors }
```

Resultado esperado: `OK: sem erros de sintaxe`

- [ ] **Passo 4: Testar funções em máquina que já tem WSL**

Se a máquina de desenvolvimento já tiver WSL + Ubuntu:

```powershell
. .\robo.ps1   # dot-source para carregar as funções sem executar o main

Test-UbuntuInstalled   # deve retornar True
Test-SetupDone         # retorna True ou False dependendo do estado atual
ConvertTo-WslPath "C:\Users\foo\projeto\setup.sh"
# esperado: /mnt/c/Users/foo/projeto/setup.sh
```

- [ ] **Passo 5: Commit**

```bash
git add robo.ps1
git commit -m "feat: adiciona robo.ps1 com maquina de estados WSL/setup/execucao"
```

---

## Task 3: `setup.sh` — configuração do Ubuntu

**Files:**
- Criar: `setup.sh`

- [ ] **Passo 1: Criar `setup.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$HOME/code/splor-mg/siafi-automacao-cota"
REPO_URL="https://github.com/splor-mg/siafi-automacao-cota.git"

echo ""
echo "=== Configurando ambiente Ubuntu para o robô SIAFI ==="
echo ""

# -------------------------------------------------------------------
# 1. Dependências do sistema
# -------------------------------------------------------------------
echo "[1/5] Instalando dependências do sistema..."
sudo apt-get update -q
sudo apt-get install -y --no-install-recommends \
    s3270 x3270 \
    python3 python3-venv python3-pip \
    git

# -------------------------------------------------------------------
# 2. Clone do repositório (filesystem Linux — melhor performance que /mnt/c/)
# -------------------------------------------------------------------
echo ""
echo "[2/5] Clonando repositório..."
if [ ! -d "$REPO_DIR/.git" ]; then
    mkdir -p "$HOME/code/splor-mg"

    if git clone "$REPO_URL" "$REPO_DIR" 2>/dev/null; then
        echo "Clone concluído."
    else
        echo ""
        echo "Repositório privado ou sem acesso. Informe seu GitHub Personal Access Token:"
        echo "(O token não aparecerá na tela)"
        read -rs GH_TOKEN
        echo ""
        TOKEN_URL="https://${GH_TOKEN}@github.com/splor-mg/siafi-automacao-cota.git"
        git clone "$TOKEN_URL" "$REPO_DIR"
        echo "Clone concluído."
    fi
else
    echo "Repositório já existe em $REPO_DIR, pulando clone."
fi

# -------------------------------------------------------------------
# 3. Ambiente virtual Python + dependências
# -------------------------------------------------------------------
echo ""
echo "[3/5] Configurando ambiente virtual Python..."
cd "$REPO_DIR"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --quiet -r requirements.txt
echo "Dependências Python instaladas."

# -------------------------------------------------------------------
# 4. Aviso WSLg (necessário para visible=True no x3270)
# -------------------------------------------------------------------
echo ""
echo "[4/5] Verificando suporte a interface gráfica (WSLg)..."
if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
    echo ""
    echo "AVISO: WSLg não detectado nesta sessão."
    echo "O login.py usa Emulator(visible=True), que abre a janela gráfica do x3270."
    echo "Se o robô falhar ao abrir a janela, altere visible=True para visible=False"
    echo "em siafi_automacao/login.py para rodar sem interface gráfica."
    echo ""
else
    echo "WSLg disponível (DISPLAY=$DISPLAY)."
fi

# -------------------------------------------------------------------
# 5. Credenciais SIAFI (.env)
# -------------------------------------------------------------------
echo ""
echo "[5/6] Configurando credenciais SIAFI..."

if [ ! -f ".env" ]; then
    echo ""
    echo "Informe as credenciais de acesso ao SIAFI:"
    echo ""
    read -rp  "  SISTEMA (ex: SIAF): "          SISTEMA
    read -rp  "  USUARIO: "                      USUARIO
    read -rsp "  SENHA (não aparece na tela): "  SENHA
    echo ""
    read -rp  "  UNIDADE_EXECUTORA (ex: 1451): " UNIDADE_EXECUTORA

    cat > .env <<EOF
SISTEMA=${SISTEMA}
USUARIO=${USUARIO}
SENHA=${SENHA}
UNIDADE_EXECUTORA=${UNIDADE_EXECUTORA}
EOF
    echo ""
    echo "Arquivo .env criado com sucesso."
else
    echo ".env já existe — mantendo credenciais existentes."
fi

# -------------------------------------------------------------------
# 6. Sentinela
# -------------------------------------------------------------------
echo ""
echo "[6/6] Marcando setup como concluído..."
touch "$REPO_DIR/.setup_done"

echo ""
echo "============================================================"
echo "  Configuração concluída! O robô será iniciado em seguida."
echo "============================================================"
echo ""
```

- [ ] **Passo 2: Verificar sintaxe com shellcheck**

Se shellcheck não estiver instalado:
```bash
sudo apt-get install -y shellcheck
```

Executar:
```bash
shellcheck setup.sh
```

Resultado esperado: nenhuma saída (zero erros/avisos). Corrija qualquer aviso antes de continuar.

- [ ] **Passo 3: Testar o script em Ubuntu com `--dry-run` manual**

Execute passo a passo para validar o fluxo sem WSL:

```bash
# Simula leitura do .env sem criar arquivos
bash -n setup.sh
```

Resultado esperado: nenhum erro de sintaxe Bash.

- [ ] **Passo 4: Adicionar `.setup_done` ao `.gitignore`**

Abra `.gitignore` e adicione ao final:

```
# Sentinela do launcher WSL
.setup_done
```

- [ ] **Passo 5: Commit**

```bash
git add setup.sh .gitignore
git commit -m "feat: adiciona setup.sh para configuracao do Ubuntu e atualiza .gitignore"
```

---

## Task 4: Verificação de integração manual

Esta task documenta o roteiro de teste completo. Execute em uma máquina sem WSL instalado (ou use `wsl --unregister Ubuntu` para resetar em ambiente de teste).

> **Atenção:** `wsl --unregister Ubuntu` apaga todos os dados da distro. Só execute em ambiente de teste.

- [ ] **Passo 1: Verificar que os três arquivos existem no repositório**

```bash
ls -la robo.bat robo.ps1 setup.sh
```

Resultado esperado: todos os três listados, com timestamps recentes.

- [ ] **Passo 2: Testar Fase 1 (sem WSL)**

Em máquina sem WSL, ou após `wsl --unregister Ubuntu` em PowerShell admin:

```
Duplo-clique em robo.bat
```

Resultado esperado:
- UAC solicita permissão de administrador
- Terminal mostra `Executando: wsl --install -d Ubuntu`
- Ao final: mensagem pedindo reboot
- Script encerra sem erro

- [ ] **Passo 3: Reboot e primeira inicialização do Ubuntu**

Após reiniciar o Windows, o terminal do Ubuntu abre automaticamente pedindo usuário e senha Linux. Defina usuário (ex: `brunohorosa`) e senha.

- [ ] **Passo 4: Testar Fase 2 (sem `.setup_done`)**

```
Duplo-clique em robo.bat
```

Resultado esperado:
- Detecta Ubuntu instalado, `.setup_done` ausente
- Executa `setup.sh` no terminal WSL
- Instala apt packages, clona repositório, cria venv, instala requirements
- Pede credenciais SIAFI interativamente
- Cria `.env`
- Cria `.setup_done`
- Inicia `login.py`

- [ ] **Passo 5: Testar Fase 3 (setup já feito)**

```
Duplo-clique em robo.bat
```

Resultado esperado:
- Nenhuma mensagem de instalação
- `login.py` inicia diretamente em menos de 3 segundos

- [ ] **Passo 6: Commit final**

```bash
git add .
git commit -m "docs: adiciona roteiro de teste de integracao no plano do launcher"
```

---

## Checklist de cobertura do spec

| Requisito do spec | Task |
|-------------------|------|
| `robo.bat` como ponto de entrada | Task 1 |
| Detecção de WSL ausente + `wsl --install` | Task 2 |
| Solicitação de elevação UAC | Task 2 |
| Detecção de `.setup_done` | Task 2 |
| Execução do `login.py` via `wsl` | Task 2 |
| `apt install` de dependências do sistema | Task 3 |
| `git clone` com fallback para repositório privado | Task 3 |
| `python3 -m venv` + `pip install` | Task 3 |
| Coleta interativa de credenciais SIAFI → `.env` | Task 3 |
| Criação do sentinela `.setup_done` | Task 3 |
| `.setup_done` no `.gitignore` | Task 3 |
| Aviso WSLg se `visible=True` sem display | Task 3 |
| Verificação de integração completa | Task 4 |
