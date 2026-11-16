#!/usr/bin/env bash
# Sequencia unica de execucao do robo SIAFI.
#
# Usado tanto pelo robo.ps1 (duplo-clique do usuario final no Windows) quanto
# pelo bot do Telegram, para que os dois caminhos executem exatamente a mesma
# coisa.
#
# Codigos de saida:
#   0    sucesso
#   3    senha do SIAFI expirada — nada foi enviado ao SIAFI
#   10   ja existe uma execucao em andamento (lock tomado)
#   143  execucao encerrada de fora (SIGTERM); 129 se foi a janela fechada
#   *    propagado do login.py
# Sem '-e' de proposito: a falha do 'git pull' precisa apenas avisar e seguir
# com a versao local, nao abortar a execucao.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CARIMBO="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$REPO/data/logs"

LOG="${ROBO_LOG:-$REPO/data/logs/robo-$CARIMBO.log}"
export RELATO_ARQUIVO="${RELATO_ARQUIVO:-$REPO/data/logs/relato-$CARIMBO.jsonl}"

# LOCK COMPARTILHADO com o robo de credito, de proposito e fora dos dois
# repos: ambos entram no SIAFI com o MESMO usuario, e duas sessoes simultaneas
# fazem o mainframe recusar com 'UNABLE TO ESTABLISH SESSION'. flock -n falha
# imediatamente em vez de esperar: quem pediu recebe a resposta na hora.
LOCK="${SIAFI_LOCK:-$HOME/.siafi-robo.lock}"
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "Ja existe uma execucao do robo (cota ou credito) em andamento." >&2
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

    # Dependencias: o 'git pull' acima pode ter trazido um requirements.txt
    # novo, e sem isto a maquina so descobriria no ImportError. So reinstala
    # quando o arquivo mudou desde a ultima instalacao (o carimbo guarda o
    # sha256 dele), para nao depender de rede a cada execucao. Se o pip falhar,
    # apenas avisa: melhor rodar com as dependencias atuais do que nao rodar. O
    # carimbo fica como estava, e a proxima execucao tenta de novo.
    CARIMBO_REQ="venv/.requirements.sha256"
    if [ -f requirements.txt ]; then
        if [ ! -f "$CARIMBO_REQ" ]; then
            # Primeira execucao com esta checagem: registra o estado atual, que
            # o setup.sh instalou.
            sha256sum requirements.txt > "$CARIMBO_REQ"
        elif ! sha256sum --status -c "$CARIMBO_REQ"; then
            echo "O requirements.txt mudou: atualizando as dependencias..."
            if pip install --quiet --retries 1 --timeout 15 -r requirements.txt; then
                sha256sum requirements.txt > "$CARIMBO_REQ"
            else
                echo "[aviso] Nao foi possivel atualizar as dependencias. Rodando com as atuais."
            fi
        fi
    fi

    # PYTHONUNBUFFERED: com a saida num pipe o Python guarda tudo num buffer e
    # so escreve no fim. A janela do robo.bat ficava muda a execucao inteira, e
    # um robo travado nao deixava nada no log.
    PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 python siafi_automacao/login.py
} 2>&1 | (
    # O tee ignora os sinais de encerramento e so termina quando o robo fecha
    # o pipe. O login.py trata Ctrl+C, SIGTERM (servico do bot reiniciado) e
    # SIGHUP (janela fechada) devolvendo a planilha; se o tee morresse junto,
    # esse resgate nao ficaria no log e os prints do robo passariam a falhar.
    trap '' INT TERM HUP
    exec tee "$LOG"
)

exit "${PIPESTATUS[0]}"
