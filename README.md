# siafi-automacao-cota

Robô que **aprova e anula cotas orçamentárias** no **SIAFI** (terminal TN3270),
linha a linha, a partir de planilhas Excel. Roda em Ubuntu/WSL2, controla o
emulador `x3270`/`s3270` pela biblioteca `py3270` e pode ser acionado pelo
duplo-clique no `robo.bat` ou pelo comando `/cota` do bot do Telegram.

Este repositório também abriga o **bot do Telegram**, que aciona este robô e o
de crédito ([siafi-automacao-credito](https://github.com/splor-mg/siafi-automacao-credito)).

O manual para quem opera o robô no dia a dia, sem nada técnico, é o
[RUNBOOK.md](RUNBOOK.md).

## O que ele faz

1. **Consolida** (`consolida.py`) — valida todos os `.xlsx` das pastas
   `Remanejamentos` e `Remanejamentos (SEGOV)` do OneDrive e, se nenhum
   reprovar, junta as linhas no `Conferencia arquivo robo DD.MM.xlsx`, em
   `Robo (IPU 2)/Python`. Os originais vão para `Realizados`. Rodadas do mesmo
   dia são apensadas ao mesmo arquivo (coluna `Execução`), e a coluna `Pedido`
   guarda de qual arquivo cada linha veio.
2. **Login** no SIAFI (`login.py`, que também orquestra todo o fluxo) — o
   conferência é movido para a pasta local (`PASTA_LOCAL`), para o robô não
   depender da sincronização do OneDrive enquanto grava.
3. **Processa** cada linha pendente — com dados e com a coluna `Progresso`
   vazia — pelos fluxos `fluxo_aprovar.py` e `fluxo_anular.py` (GLOBAL ou
   AMARRADO). O resultado de cada linha é gravado e salvo na hora.
4. **Devolve** a planilha formatada para `Conferencia arquivo robo/` e arruma
   os originais em `Realizados/Remanejamentos realizados`.

Não há confirmação no meio do caminho: acionado, o robô vai até o fim.

### Quando algo falha no meio

- A planilha **sempre volta** para `Conferencia arquivo robo/` com o progresso
  parcial. Na execução seguinte, mesmo sem planilha nova, o `consolida.py`
  encontra as linhas pendentes e o robô retoma de onde parou.
- A linha que estava em curso recebe `INTERROMPIDA - VERIFICAR NO SIAFI` e
  **não é reprocessada**: a operação pode ter entrado no SIAFI sem o retorno
  ter sido lido. Alguém confere e, se for o caso, apaga o `Progresso` dela.
- Isso vale também para a execução **encerrada de fora**: Ctrl+C, janela do
  `robo.bat` fechada (SIGHUP) ou serviço do bot reiniciado (SIGTERM).
- Se a **consolidação** abortar depois de salvar o consolidado — planilha de
  origem aberta no Excel, OneDrive segurando um arquivo —, a execução seguinte
  termina a arrumação e processa o arquivo que já estava pronto, em vez de
  consolidar de novo e perder as planilhas que já tinham sido arquivadas
  (`retomar_consolidacao_interrompida`, em `consolida.py`).
- Linha pendente com campo ilegível recebe `Linha com dado inválido na
  planilha` e as demais seguem.
- Só `0011-REGISTRO EFETUADO` vira `Ok`. Mensagem que o robô não conhece vira
  `Erro`, nunca `Ok`.
- A tela inteira do SIAFI vai para o log (`tela.py`): as 24 linhas numeradas,
  a régua de colunas, o estado do teclado e a posição do cursor — as mesmas
  coordenadas do `fill_field()`. Para ver todas:

  ```bash
  grep -A 28 "TELA DO SIAFI" data/logs/robo-*.log
  ```

## Estrutura

```
siafi_automacao/
├── login.py               # orquestrador (ponto de entrada)
├── consolida.py           # validação e consolidação das planilhas de origem
├── fluxo_aprovar.py       # telas da aprovação de cota
├── fluxo_anular.py        # telas da anulação de cota
├── emulador.py            # espera o teclado do mainframe destravar
├── tela.py                # print da tela do SIAFI no log, para diagnóstico
├── config.py              # leitura das variáveis que precisam de tratamento
├── relato.py              # eventos (.jsonl) lidos pelo bot do Telegram
├── bot_telegram.py        # bot: long-polling, comandos, disparo dos robôs
└── telegram_mensagens.py  # montagem das mensagens e regras de autorização
data/logs/                 # robo-*.log e relato-*.jsonl de cada execução
rodar.sh                   # sequência única de execução (bat e bot usam a mesma)
robo.bat                   # duplo-clique no Windows -> robo.ps1 -> rodar.sh
setup.sh                   # prepara uma máquina nova (WSL/Ubuntu)
instalar_bot.sh            # instala o bot como serviço do systemd
```

## Configuração

Em máquina nova, o duplo-clique no `robo.bat` cuida de tudo: instala o
WSL/Ubuntu se faltar e roda o `setup.sh`, que instala as dependências, clona o
repositório, cria a venv e pergunta as variáveis do `.env`.

Manualmente: copie `.env.example` para `.env`, preencha, e

```bash
sudo apt install s3270 x3270 python3-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`ONEDRIVE_BASE` é o caminho da **pasta** (vista de dentro do WSL, em
`/mnt/c/...`) que contém `Remanejamentos`, `Robo (IPU 2)`, `Conferencia arquivo
robo` e `Realizados`. As demais variáveis estão explicadas no `.env.example`.

## Execução

```bash
bash rodar.sh
```

O `rodar.sh` pega o lock compartilhado com o robô de crédito (os dois usam o
mesmo usuário do SIAFI e nunca rodam juntos), faz `git pull` na `main`,
reinstala as dependências se o `requirements.txt` mudou e executa o
`login.py`. Códigos de saída:

| Código | Significado |
|---|---|
| 0 | Foi até o fim (pode haver linha com erro — veja a coluna `Progresso`) |
| 1 | Falha (validação reprovada, SIAFI inacessível, execução interrompida) |
| 3 | Senha do SIAFI expirada; nada foi enviado |
| 10 | Já existe uma execução (cota ou crédito) em andamento |
| 129 / 143 | Encerrada de fora: janela fechada (SIGHUP) ou serviço reiniciado (SIGTERM) |

## Telegram

O `bot_telegram.py` roda como serviço do systemd dentro do WSL
(`bash instalar_bot.sh`; o passo a passo está na PARTE 3 do RUNBOOK). No grupo
autorizado ele aceita `/cota`, `/credito`, `/status`, `/log` e `/ajuda`, executa
o `rodar.sh` do repositório correspondente e monta as mensagens a partir do
`.jsonl` gravado pelo `relato()`.

- Os tipos de evento do `relato()` e seus campos são um contrato entre o robô
  e o bot — e entre os dois repositórios. Ele é conferido em
  `tests/test_contrato_relato.py`, que lê também o código do robô de crédito.
- O bot carrega o código uma vez só. Depois de mudar `bot_telegram.py`,
  `telegram_mensagens.py` ou `relato.py`:

  ```bash
  sudo systemctl restart siafi-bot
  ```

  Não reinicie durante uma execução: o systemd encerra o robô junto com o
  bot. A planilha é devolvida e a linha em curso fica marcada como
  interrompida, mas o grupo não recebe o resultado.

## Portal Orçamentário

O Portal (repositório `pedidos-cota`) entrega pedidos aprovados salvando um
`.xlsx` em `Remanejamentos/` e lê o resultado na planilha de conferência. Ele
não importa nada daqui; o contrato é o formato dos arquivos:

- **Entrada** — as onze colunas da planilha padrão, lidas pelo nome na primeira
  aba: `UO_COD`, `Grupo`, `IAG`, `Fonte`, `IPU`, `Ação`, `GLOBAL`, `AMARRADO`,
  `Anular`, `Aprovar`, `UO Financiadora`.
- **Conferência** — os nomes das colunas na linha 1 (`COLUNAS_CONFERENCIA`, em
  `consolida.py`). Incluir coluna é seguro; renomear ou repetir, não.
- **Coluna `Pedido`** — o nome do arquivo de origem, que no arquivo do Portal
  começa pelo número do pedido.
- **Textos do `Progresso`** — `Ok`, `Erro`, `INTERROMPIDA - VERIFICAR NO SIAFI`
  e `Elemento/item não marcado para a UO beneficiada` têm tratamento próprio
  no Portal.
- **Pastas e nomes de arquivo** — o Portal reconhece o arquivo que entregou
  pelo nome, em `Remanejamentos` e onde o robô o arquiva (`Realizados`), e lê o
  resultado na pasta de conferência e no arquivo morto dela. Mudar o destino
  dos arquivos, ou renomeá-los ao arquivar, afeta o Portal.

Os quatro primeiros pontos estão amarrados em `tests/test_contrato_portal.py`
e `tests/test_coluna_pedido.py`; as pastas, não. Se um desses testes falhar, a
mudança precisa ser combinada com o Portal antes de ir para a `main`.

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

Os testes não tocam no SIAFI nem no OneDrive. O `tests/test_login_fim_a_fim.py`
roda o `login.py` inteiro, como subprocesso, com um emulador de mentira no
lugar do `py3270` e pastas temporárias no lugar do OneDrive. Com o repositório do robô de
crédito ao lado (`../siafi-automacao-credito`), a suíte confere também o
contrato do `relato()` dele.
