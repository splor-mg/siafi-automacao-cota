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

# Process substitution (e nao pipe para o tee) para preservar o codigo de saida
# do python: num pipe, $? seria o do tee.
exec > >(tee "$LOG") 2>&1

echo "=== Robo SIAFI - $CARIMBO ==="
cd "$REPO" || exit 1

echo "Atualizando o robo (git pull na main)..."
if ! { git checkout main && git pull origin main; }; then
    echo "[aviso] Nao foi possivel atualizar via git pull. Rodando a versao local atual."
fi

echo "Iniciando o robo SIAFI..."
# shellcheck disable=SC1091
source venv/bin/activate
PYTHONIOENCODING=utf-8 python siafi_automacao/login.py
codigo=$?

# Da tempo ao tee de esvaziar o buffer antes do processo morrer.
sleep 0.2
exit "$codigo"
