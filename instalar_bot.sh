#!/usr/bin/env bash
# Instala o bot do Telegram como servico do systemd dentro do WSL.
# Rode uma vez, na maquina que executa o robo:
#     bash instalar_bot.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USUARIO="$(id -un)"
UNIT=/etc/systemd/system/siafi-bot.service

if ! grep -q '^systemd=true' /etc/wsl.conf 2>/dev/null; then
    echo "ERRO: systemd nao esta habilitado neste WSL."
    echo "Acrescente ao /etc/wsl.conf:"
    echo "  [boot]"
    echo "  systemd=true"
    echo "Depois rode 'wsl --shutdown' no Windows e abra o Ubuntu de novo."
    exit 1
fi

if ! grep -q '^TELEGRAM_BOT_TOKEN=.\+' "$REPO/.env" 2>/dev/null; then
    echo "ERRO: TELEGRAM_BOT_TOKEN nao esta preenchido no .env."
    exit 1
fi

if ! grep -q '^TELEGRAM_CHAT_ID=.\+' "$REPO/.env" 2>/dev/null; then
    echo "ERRO: TELEGRAM_CHAT_ID nao esta preenchido no .env."
    exit 1
fi

echo "Instalando o servico em $UNIT ..."
sudo tee "$UNIT" > /dev/null <<EOF
[Unit]
Description=Bot do Telegram que aciona o robo SIAFI
After=network-online.target

[Service]
Type=simple
User=$USUARIO
WorkingDirectory=$REPO
ExecStart=$REPO/venv/bin/python $REPO/siafi_automacao/bot_telegram.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONIOENCODING=utf-8

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now siafi-bot.service

echo ""
echo "Pronto. Comandos uteis:"
echo "  systemctl status siafi-bot        - ver se esta no ar"
echo "  journalctl -u siafi-bot -f        - acompanhar os logs"
echo "  sudo systemctl restart siafi-bot  - reiniciar apos mudar o codigo"
