#!/usr/bin/env bash
# Sequencia unica de execucao do robo SIAFI.
#
# Usado tanto pelo robo.ps1 (duplo-clique do usuario final no Windows) quanto
# pelo bot do Telegram, para que os dois caminhos executem exatamente a mesma
# coisa.
#
# Codigos de saida:
#   0   sucesso
#   10  ja existe uma execucao em andamento (lock tomado)
#   *   propagado do login.py
# Sem '-e' de proposito: a falha do 'git pull' precisa apenas avisar e seguir
# com a versao local, nao abortar a execucao.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CARIMBO="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$REPO/data/logs"

LOG="${ROBO_LOG:-$REPO/data/logs/robo-$CARIMBO.log}"
export RELATO_ARQUIVO="${RELATO_ARQUIVO:-$REPO/data/logs/relato-$CARIMBO.jsonl}"

# O lock impede que o bot e o robo.bat rodem ao mesmo tempo. flock -n falha
# imediatamente em vez de esperar: quem pediu recebe a resposta na hora.
exec 9>"$REPO/data/.robo.lock"
if ! flock -n 9; then
    echo "Ja existe uma execucao em andamento." >&2
    exit 10
fi

# Registra onde estao os arquivos desta execucao, para o comando /log do bot.
printf '%s\n%s\n' "$LOG" "$RELATO_ARQUIVO" > "$REPO/data/.ultima_execucao"

# Apaga logs antigos. Roda aqui, e nao num timer do systemd, para valer tanto
# para o bot quanto para o duplo-clique no robo.bat sem depender de mais
# nenhuma peca. Os arquivos desta execucao sao de hoje, entao nunca entram no
# alcance do -mtime.
find "$REPO/data/logs" -maxdepth 1 -type f \
    \( -name 'robo-*.log' -o -name 'relato-*.jsonl' \) \
    -mtime +"${LOG_RETENCAO_DIAS:-30}" -delete 2>/dev/null

# O corpo inteiro roda dentro de um grupo canalizado para o tee. O codigo de
# saida vem de ${PIPESTATUS[0]} (o grupo), nao do tee, e o pipe garante que o
# log foi totalmente escrito antes de o script terminar.
{
    echo "=== Robo SIAFI - $CARIMBO ==="
    cd "$REPO" || exit 1

    echo "Atualizando o robo (git pull na main)..."
    if ! { git checkout main && git pull origin main; }; then
        echo "[aviso] Nao foi possivel atualizar via git pull. Rodando a versao local atual."
    fi

    echo "Iniciando o robo SIAFI..."
    # shellcheck disable=SC1091
    if ! source venv/bin/activate; then
        echo "[erro] Nao foi possivel ativar o ambiente virtual (venv ausente ou corrompida)."
        echo "       Rode o setup.sh novamente para recriar a venv."
        exit 1
    fi

    PYTHONIOENCODING=utf-8 python siafi_automacao/login.py
} 2>&1 | tee "$LOG"

exit "${PIPESTATUS[0]}"
