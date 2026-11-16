# CLAUDE.md

Orientações para o Claude Code ao trabalhar neste repositório.

## O que é o projeto

Automação de operações no **SIAFI** (terminal mainframe TN3270) para a Cidade
Administrativa de Minas Gerais (SEPLAG / DCMEFO). O robô faz **aprovação e
anulação de cotas orçamentárias** linha a linha, lendo uma planilha Excel e
gravando o resultado de cada operação.

Controla o emulador `x3270`/`s3270` via biblioteca **py3270**. Roda em **Ubuntu**,
tipicamente sob **WSL2 no Windows**.

O repositório também abriga o **bot do Telegram**, que aciona este robô
(`/cota`) e o de crédito (`/credito`, repositório vizinho
`../siafi-automacao-credito`).

## Como rodar

```bash
cd ~/code/splor-mg/siafi-automacao-cota
bash rodar.sh                       # sequência de produção (lock, git pull, login.py)
venv/bin/python -m pytest           # testes: não tocam no SIAFI nem no OneDrive
```

Pelo Windows, o usuário final dá duplo-clique em `robo.bat`; pelo Telegram,
manda `/cota` no grupo. Documentação operacional para a equipe executora:
`RUNBOOK.md`. Visão geral para quem mantém: `README.md`.

## Arquitetura

### Launcher WSL (Windows → robô)
Cadeia de inicialização para o usuário final, que não precisa saber nada técnico:

`robo.bat` → `robo.ps1` → (`setup.sh` na primeira vez) → `rodar.sh` → `login.py`

- **`robo.bat`** — ponto de entrada (duplo-clique). Define `chcp 65001` e chama o PS.
- **`robo.ps1`** — instala WSL+Ubuntu se faltar (com elevação UAC e reboot),
  roda `setup.sh` na primeira vez (sentinela `.setup_done` + checagem de
  `ONEDRIVE_BASE` no `.env`), e por fim executa o `rodar.sh`.
- **`setup.sh`** — idempotente: instala dependências do sistema (`s3270 x3270
  python3-venv git`), clona o repo, cria a venv, instala `requirements.txt` e
  coleta as variáveis ausentes do `.env` (só pergunta o que falta).
- **`rodar.sh`** — sequência única de execução, usada pelo `robo.ps1` e pelo
  bot: pega o lock `~/.siafi-robo.lock` (**compartilhado com o robô de
  crédito**; código de saída 10 se ocupado), apaga logs antigos, faz
  `git checkout main && git pull`, ativa a venv, reinstala as dependências se
  o `requirements.txt` mudou (carimbo em `venv/.requirements.sha256`) e roda o
  `login.py`, gravando `data/logs/robo-*.log` e `relato-*.jsonl`. O `tee` do
  log ignora os sinais de encerramento de propósito, para registrar o resgate.

### Núcleo Python (`siafi_automacao/`)
- **`login.py`** — orquestrador (entrypoint de produção). Roda `consolida.py`,
  move o conferência para `PASTA_LOCAL`, faz login no SIAFI, processa as linhas
  **pendentes** (com dados mas coluna `Progresso` vazia) chamando
  `aprovar`/`anular`, formata e devolve a planilha. **Não há confirmação
  humana no meio**: acionado, vai até o fim. Em qualquer falha a planilha volta
  para a pasta de conferência com o progresso parcial, e a linha em curso é
  marcada `INTERROMPIDA - VERIFICAR NO SIAFI` (não é reprocessada sozinha) —
  inclusive quando a execução é encerrada de fora (Ctrl+C, SIGHUP da janela
  fechada, SIGTERM do serviço reiniciado).
  O fluxo roda sob `if __name__ == "__main__"`; só as funções são importáveis.
  Para testar o fluxo inteiro use `tests/test_login_fim_a_fim.py`, que roda o
  script como subprocesso com um `py3270` de mentira e pastas temporárias.
- **`consolida.py`** — valida e junta os `.xlsx` das pastas `Remanejamentos` /
  `Remanejamentos (SEGOV)` em um único `Conferencia arquivo robo DD.MM.xlsx`.
  Suporta múltiplas execuções no mesmo dia (coluna `Execução` incrementada),
  grava o arquivo de origem na coluna `Pedido` e, sem planilha nova, retoma o
  conferência que ficou com linhas pendentes. A arrumação do fim (arquivar as
  origens, tirar o conferência antigo) pode falhar por trava do Windows; a
  execução seguinte continua dali (`retomar_consolidacao_interrompida`).
- **`fluxo_aprovar.py` / `fluxo_anular.py`** — navegação por coordenadas de tela
  do SIAFI (`em.fill_field(linha, col, ...)`), tratando GLOBAL vs AMARRADO e
  capturando a mensagem de retorno do mainframe.
- **`emulador.py`** — `esperar_teclado()`. **`tela.py`** — print da tela do SIAFI
  no log em caso de falha (igual ao do robô de crédito). **`config.py`** —
  leitura de `UOS_BLOQUEADAS`.
- **`relato.py`** — `relato(tipo, texto, **campos)` imprime no console e grava
  o evento no `.jsonl` que o bot lê. O bot nunca lê o stdout.

### Bot do Telegram
- **`bot_telegram.py`** — long-polling; comandos `/cota`, `/credito`, `/status`,
  `/log`, `/ajuda`. Roda como serviço systemd (`siafi-bot`, instalado pelo
  `instalar_bot.sh`) e dispara o `rodar.sh` do repositório correspondente,
  sempre com `SIAFI_VISIVEL=false`.
- **`telegram_mensagens.py`** — funções puras: autorização, montagem das
  mensagens, corte no limite de 4096 caracteres.
- O bot carrega o código uma vez. Mudou `bot_telegram.py`,
  `telegram_mensagens.py` ou `relato.py` → `sudo systemctl restart siafi-bot`.
  **Nunca reinicie durante uma execução**: o systemd encerra o robô junto
  (`KillMode=control-group`). A planilha é devolvida e a linha em curso fica
  `INTERROMPIDA`, mas o grupo não recebe o resultado.

### Configuração — `.env`
Tudo é dirigido por variáveis (via `python-dotenv`). Ver `.env.example`. Nunca
hardcodar caminhos/credenciais no código. Variáveis:
`SISTEMA`, `USUARIO`, `SENHA`, `UNIDADE_EXECUTORA`, `ONEDRIVE_BASE`,
`PASTA_LOCAL`, `SIAFI_HOST` (default `bhmvsb.prodemge.gov.br`), `SIAFI_VISIVEL`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_USUARIOS_AUTORIZADOS`,
`REPO_CREDITO`, `LOG_RETENCAO_DIAS`, `UOS_BLOQUEADAS`, `MOTIVO_UO_BLOQUEADA`,
`CONEXAO_TENTATIVAS`, `CONEXAO_ESPERA_SEGUNDOS`, `MOVER_TENTATIVAS`,
`MOVER_ESPERA_SEGUNDOS`.

`ONEDRIVE_BASE` é a pasta-raiz no OneDrive (acessada do WSL via `/mnt/c/...`) que
contém as subpastas `Remanejamentos`, `Robo (IPU 2)/Python`, `Conferencia arquivo
robo`, `Realizados`, etc. **Deve ser o caminho da PASTA, nunca de um arquivo.**

### Fluxo de dados (produção)
Equipe (ou o Portal Orçamentário) salva Excel em `Remanejamentos/` →
`consolida.py` valida e consolida → arquivo de conferência em
`Robo (IPU 2)/Python/` → `login.py` o move para `PASTA_LOCAL` e processa no
SIAFI → planilha formatada vai para `Conferencia arquivo robo/` e os originais
para `Realizados/` (e depois `Realizados/Remanejamentos realizados/`).

## Contratos com outros repositórios

- **Robô de crédito** (`../siafi-automacao-credito`): o bot daqui o aciona e lê
  o `relato` dele; o lock do `rodar.sh` é o mesmo arquivo nos dois. Os tipos e
  campos do `relato()` estão amarrados em `tests/test_contrato_relato.py`, que
  lê o código dos dois repositórios. `relato.py` e `tela.py` são cópias
  idênticas nos dois.
- **Portal Orçamentário** (repositório `pedidos-cota`, privado): escreve a
  planilha em `Remanejamentos/` e lê a conferência de volta. Não importa nada
  daqui; o contrato é o formato: colunas da planilha de entrada, colunas da
  conferência (`COLUNAS_CONFERENCIA`), coluna `Pedido` e os textos da coluna
  `Progresso` (`Ok`, `Erro`, `INTERROMPIDA - VERIFICAR NO SIAFI`,
  `Elemento/item não marcado para a UO beneficiada`). Amarrado em
  `tests/test_contrato_portal.py` e `tests/test_coluna_pedido.py`. Não mude
  esses pontos sem combinar com o Portal.

## Gotchas importantes (já custaram tempo)

- **A produção roda DESTE checkout.** O bot é um processo vivo daqui e o
  `rodar.sh` usa este diretório: edição não commitada em `login.py`,
  `consolida.py` ou nos fluxos já vale na próxima execução. Não deixe edição
  pela metade; rode os testes antes de largar o arquivo. O `rodar.sh` só se
  troca de forma atômica (escreva num arquivo ao lado e `mv`): o bash lê o
  script aos poucos, e editar no lugar atinge uma execução em andamento.
- Teste que chama `consolida.main()` precisa trocar **todas** as constantes de
  pasta (elas vêm do `.env` e apontam para o OneDrive real). Use a fixture
  `pastas` de `tests/test_coluna_pedido.py`.
- **`robo.ps1` NÃO pode conter caracteres acentuados** nas mensagens `Write-Host`.
  O PowerShell 5.1 lê o `.ps1` como Windows-1252 antes de aplicar
  `[Console]::OutputEncoding`, corrompendo acentos (`Robô` → `RobÃ´`). Use ASCII
  puro ("Robo", "configuracao", "codigo").
- **Copiar arquivos do WSL para `/mnt/c/`** (ex.: pasta do executor no OneDrive):
  use `wsl.exe -d Ubuntu -e bash -c "cp ..."`. Acesso a `/mnt/c` falha por outras
  vias neste ambiente (sessão bash direta, UNC do PowerShell, cmd.exe UNC).
- **Git:** nesta máquina o remoto é SSH (`git@github.com:splor-mg/...`) e o
  `git pull` do `rodar.sh` roda sem pedir nada. Em máquina preparada pelo
  `setup.sh` o remoto é HTTPS: lá, `push`/`fetch` que peçam credencial em
  background travam esperando usuário/senha.
- O repo já teve `.git/FETCH_HEAD` com dono `root` (de operação antiga com sudo),
  o que bloqueia `git fetch` com "Permission denied". Remover o arquivo resolve.
- **O repositório é público.** Nada de credencial, nome de pessoa ou dado
  interno em código, teste ou documentação.
- **Idioma: português.** Código, comentários, mensagens e documentação são em
  pt-BR. Mantenha o padrão.
- Comandos para o WSL a partir do Windows: prefixe com
  `wsl -d Ubuntu -- bash -c "..."` (ou `wsl.exe -d Ubuntu -e bash -c '...'`).

## py3270 / SIAFI
- `Emulator(visible=siafi_visivel)`; conecta em `siafi_host`.
- Telas são manipuladas por coordenadas fixas (`fill_field`, `string_get`,
  `string_found`, `send_enter`, `send_pf`). Mudanças de layout do SIAFI quebram
  essas coordenadas. Não há ambiente de teste do SIAFI: mudança em
  `fluxo_aprovar.py`/`fluxo_anular.py` só se prova em produção.
- `visible=True` exige WSLg (Windows 11). Em Win10 pode não abrir janela; usar
  `SIAFI_VISIVEL=false` (modo `s3270`).

## Git / estado atual
- Trabalho direto na `main` (é dela que o `rodar.sh` faz `git pull`). Remoto
  público em `github.com/splor-mg/siafi-automacao-cota`.
- Termine mensagens de commit com:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
