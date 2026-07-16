# CLAUDE.md

Orientações para o Claude Code ao trabalhar neste repositório.

## O que é o projeto

Automação de operações no **SIAFI** (terminal mainframe TN3270) para a Cidade
Administrativa de Minas Gerais (SEPLAG / DCMEFO). O robô faz **aprovação e
anulação de cotas orçamentárias** linha a linha, lendo uma planilha Excel e
gravando o resultado de cada operação.

Controla o emulador `x3270`/`s3270` via biblioteca **py3270**. Roda em **Ubuntu**,
tipicamente sob **WSL2 no Windows**.

## Como rodar

```bash
cd ~/code/splor-mg/siafi-automacao-cota
source venv/bin/activate
python siafi_automacao/login.py
```

Pelo Windows, o usuário final dá duplo-clique em `robo.bat` (ver fluxo do
launcher abaixo). Documentação operacional para a equipe executora: `RUNBOOK.md`.

## Arquitetura

### Launcher WSL (Windows → robô)
Cadeia de inicialização para o usuário final, que não precisa saber nada técnico:

`robo.bat` → `robo.ps1` → `setup.sh` → `login.py`

- **`robo.bat`** — ponto de entrada (duplo-clique). Define `chcp 65001` e chama o PS.
- **`robo.ps1`** — instala WSL+Ubuntu se faltar (com elevação UAC e reboot),
  roda `setup.sh` na primeira vez (sentinela `.setup_done` + checagem de
  `ONEDRIVE_BASE` no `.env`), e por fim executa o `login.py`.
- **`setup.sh`** — idempotente: instala dependências do sistema (`s3270 x3270
  python3-venv git`), clona o repo, cria a venv, instala `requirements.txt` e
  coleta as variáveis ausentes do `.env` (só pergunta o que falta).

### Núcleo Python (`siafi_automacao/`)
- **`login.py`** — orquestrador (entrypoint de produção). Roda `consolida.py`,
  abre o arquivo de conferência no Excel para o usuário revisar, pede confirmação
  (`s`/`n`), faz login no SIAFI, processa as linhas **pendentes** (com dados mas
  coluna `Progresso` vazia) chamando `aprovar`/`anular`, formata e move a planilha.
- **`consolida.py`** — junta os `.xlsx` das pastas `Remanejamentos` /
  `Remanejamentos (SEGOV)` em um único `Conferencia arquivo robo DD.MM.xlsx`.
  Suporta múltiplas execuções no mesmo dia (coluna `Execução` incrementada).
- **`fluxo_aprovar.py` / `fluxo_anular.py`** — navegação por coordenadas de tela
  do SIAFI (`em.fill_field(linha, col, ...)`), tratando GLOBAL vs AMARRADO e
  capturando a mensagem de retorno do mainframe.
- **`cota_orcamentaria.py`** — script standalone **legado** (caminho hardcoded,
  lê aba `CombinedSheet`). Não é o fluxo de produção; `login.py` o substituiu.

### Configuração — `.env`
Tudo é dirigido por variáveis (via `python-dotenv`). Ver `.env.example`. Nunca
hardcodar caminhos/credenciais no código. Variáveis:
`SISTEMA`, `USUARIO`, `SENHA`, `UNIDADE_EXECUTORA`, `ONEDRIVE_BASE`,
`PASTA_LOCAL`, `SIAFI_HOST` (default `bhmvsb.prodemge.gov.br`), `SIAFI_VISIVEL`.

`ONEDRIVE_BASE` é a pasta-raiz no OneDrive (acessada do WSL via `/mnt/c/...`) que
contém as subpastas `Remanejamentos`, `Robo (IPU 2)/Python`, `Conferencia arquivo
robo`, `Realizados`, etc. **Deve ser o caminho da PASTA, nunca de um arquivo.**

### Fluxo de dados (produção)
Equipe salva Excel em `Remanejamentos/` → `consolida.py` consolida → arquivo de
conferência em `Robo (IPU 2)/Python/` → usuário revisa no Excel → `login.py`
processa no SIAFI → planilha formatada vai para `Conferencia arquivo robo/` e os
originais para `Realizados/`.

## Gotchas importantes (já custaram tempo)

- **`robo.ps1` NÃO pode conter caracteres acentuados** nas mensagens `Write-Host`.
  O PowerShell 5.1 lê o `.ps1` como Windows-1252 antes de aplicar
  `[Console]::OutputEncoding`, corrompendo acentos (`Robô` → `RobÃ´`). Use ASCII
  puro ("Robo", "configuracao", "codigo"). As mensagens de erro no `RUNBOOK.md`
  refletem essa saída sem acento.
- **Copiar arquivos do WSL para `/mnt/c/`** (ex.: pasta do executor no OneDrive):
  use `wsl.exe -d Ubuntu -e bash -c "cp ..."`. Acesso a `/mnt/c` falha por outras
  vias neste ambiente (sessão bash direta, UNC do PowerShell, cmd.exe UNC).
- **Não rodar `git push`/`fetch` que pedem credencial em background** — eles
  travam esperando usuário/senha (HTTPS, sem credential helper) e seguram a
  branch como "ahead". O push interativo do próprio usuário no terminal funciona.
- O repo já teve `.git/FETCH_HEAD` com dono `root` (de operação antiga com sudo),
  o que bloqueia `git fetch` com "Permission denied". Remover o arquivo resolve.
- **Idioma: português.** Código, comentários, mensagens e documentação são em
  pt-BR. Mantenha o padrão.
- Comandos para o WSL a partir deste ambiente: prefixe com
  `wsl -d Ubuntu -- bash -c "..."` (ou `wsl.exe -d Ubuntu -e bash -c '...'`).

## py3270 / SIAFI
- `Emulator(visible=siafi_visivel)`; conecta em `siafi_host`.
- Telas são manipuladas por coordenadas fixas (`fill_field`, `string_get`,
  `string_found`, `send_enter`, `send_pf`). Mudanças de layout do SIAFI quebram
  essas coordenadas.
- `visible=True` exige WSLg (Windows 11). Em Win10 pode não abrir janela; usar
  `SIAFI_VISIVEL=false` (modo `s3270`).

## Git / estado atual
- Branch de trabalho: `feat/wsl-launcher` (PR #4 contra `main`). Remoto público
  para leitura em `github.com/splor-mg/siafi-automacao-cota`.
- Termine mensagens de commit com:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
