#!/usr/bin/env bash
# shellcheck shell=bash
set -euo pipefail

REPO_DIR="$HOME/code/splor-mg/siafi-automacao-cota"
REPO_URL="https://github.com/splor-mg/siafi-automacao-cota.git"

echo ""
echo "=== Configurando ambiente Ubuntu para o robô SIAFI ==="
echo ""

# -------------------------------------------------------------------
# 1. Dependências do sistema
# -------------------------------------------------------------------
echo "[1/6] Instalando dependências do sistema..."
sudo apt-get update -q
sudo apt-get install -y --no-install-recommends \
    s3270 x3270 \
    python3 python3-venv python3-pip \
    git

# -------------------------------------------------------------------
# 2. Clone do repositório (filesystem Linux — melhor performance que /mnt/c/)
# -------------------------------------------------------------------
echo ""
echo "[2/6] Clonando repositório..."
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
        git -c "url.https://${GH_TOKEN}@github.com/.insteadOf=https://github.com/" \
            clone "$REPO_URL" "$REPO_DIR"
        echo "Clone concluído."
    fi
else
    echo "Repositório já existe em $REPO_DIR, pulando clone."
fi

# -------------------------------------------------------------------
# 3. Ambiente virtual Python + dependências
# -------------------------------------------------------------------
echo ""
echo "[3/6] Configurando ambiente virtual Python..."
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
echo "[4/6] Verificando suporte a interface gráfica (WSLg)..."
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
# 5. Variáveis de ambiente (.env)
# -------------------------------------------------------------------
echo ""
echo "[5/6] Configurando variáveis de ambiente..."

# Detectar usuário Windows para sugerir o caminho padrão do OneDrive
_win_user=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r\n' || true)
_year=$(date +%Y)
if [ -n "$_win_user" ]; then
    _onedrive_sugestao="/mnt/c/Users/${_win_user}/OneDrive - CAMG/@splor/@dcmefo/${_year}/Robo - Remanejamento e aprovacao de cota"
else
    _onedrive_sugestao=""
fi

# Garantir que .env existe com permissões restritas
if [ ! -f ".env" ]; then
    touch .env
    chmod 600 .env
fi

# Coletar apenas as variáveis ausentes
_novas_vars=false

if ! grep -q "^SISTEMA=" .env 2>/dev/null; then
    _novas_vars=true
    echo ""
    echo "Informe as credenciais de acesso ao SIAFI:"
    echo ""
    read -rp  "  SISTEMA (ex: SIAF): "          SISTEMA
    read -rp  "  USUARIO: "                      USUARIO
    read -rsp "  SENHA (não aparece na tela): "  SENHA
    echo ""
    read -rp  "  UNIDADE_EXECUTORA (ex: 1451): " UNIDADE_EXECUTORA
    printf 'SISTEMA=%s\nUSUARIO=%s\nSENHA=%s\nUNIDADE_EXECUTORA=%s\n' \
        "$SISTEMA" "$USUARIO" "$SENHA" "$UNIDADE_EXECUTORA" >> .env
    echo "Credenciais SIAFI salvas."
fi

if ! grep -q "^ONEDRIVE_BASE=" .env 2>/dev/null; then
    _novas_vars=true
    echo ""
    echo "Caminho WSL até a pasta-raiz do projeto de cotas no OneDrive"
    echo "(diretório que contém as subpastas 'Robo (IPU 2)', 'Realizados', etc.):"
    if [ -n "$_onedrive_sugestao" ]; then
        echo "  Sugestão detectada: $_onedrive_sugestao"
        read -rp "  ONEDRIVE_BASE [Enter para aceitar]: " ONEDRIVE_BASE
        ONEDRIVE_BASE="${ONEDRIVE_BASE:-$_onedrive_sugestao}"
    else
        echo "  Exemplo: /mnt/c/Users/SEU_USUARIO/OneDrive - CAMG/@splor/@dcmefo/${_year}/Robo - Remanejamento e aprovacao de cota"
        read -rp "  ONEDRIVE_BASE: " ONEDRIVE_BASE
    fi
    printf 'ONEDRIVE_BASE=%s\n' "$ONEDRIVE_BASE" >> .env
    echo "ONEDRIVE_BASE salvo."
fi

if ! grep -q "^PASTA_LOCAL=" .env 2>/dev/null; then
    _novas_vars=true
    _local_padrao="$HOME/siafi-trabalho"
    echo ""
    echo "Pasta local (Linux) para cópia temporária dos arquivos durante a execução:"
    read -rp "  PASTA_LOCAL [Enter para usar $_local_padrao]: " PASTA_LOCAL
    PASTA_LOCAL="${PASTA_LOCAL:-$_local_padrao}"
    printf 'PASTA_LOCAL=%s\n' "$PASTA_LOCAL" >> .env
    echo "PASTA_LOCAL salvo."
fi

if [ "$_novas_vars" = false ]; then
    echo ".env completo — mantendo variáveis existentes."
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
