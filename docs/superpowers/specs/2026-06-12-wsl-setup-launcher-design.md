# Design: Launcher WSL + Execução do Robô SIAFI

**Data:** 2026-06-12
**Escopo:** Automação de setup do WSL Ubuntu e execução do `login.py` via duplo-clique no Windows

---

## Contexto

O projeto `siafi-automacao-cota` automatiza operações de aprovação e anulação de cotas orçamentárias no SIAFI via emulador TN3270 (`py3270` + `s3270`). O script principal é `siafi_automacao/login.py` e deve rodar dentro do Ubuntu no WSL, pois depende de ferramentas Linux (`s3270`, `x3270`) e acessa o OneDrive via `/mnt/c/`.

O usuário precisa executar o robô com o mínimo de interação possível a partir do Windows — idealmente um duplo-clique num arquivo executável.

---

## Decisão de design

**Abordagem escolhida:** `.bat` launcher + `.ps1` (lógica Windows) + `.sh` (lógica Ubuntu).

Alternativas descartadas:
- `.bat` puro: linguagem arcaica, tratamento de erro ruim, difícil de manter
- Instalador `.exe` (Inno Setup/NSIS): complexidade de build não justificada para o contexto

---

## Arquitetura

```
siafi-automacao-cota/
├── robo.bat          ← ponto de entrada (usuário clica aqui)
├── robo.ps1          ← lógica Windows (PowerShell)
├── setup.sh          ← lógica Ubuntu (Bash), rodado uma única vez
└── siafi_automacao/
    └── login.py      ← script principal do robô (já existe)
```

### `robo.bat`
Único arquivo que o usuário vê e clica. Sua única responsabilidade é invocar o PowerShell com a política de execução correta, passando o caminho do `robo.ps1`. Solicita elevação de privilégios (UAC) quando necessário (fase de instalação do WSL).

### `robo.ps1`
Detecta a fase atual e avança o estado. Nunca pede interação além do UAC e do que o próprio WSL/Ubuntu exige.

### `setup.sh`
Executado dentro do Ubuntu via `wsl -d Ubuntu -- bash /mnt/c/.../setup.sh`. Configura o ambiente Linux completo na primeira execução.

---

## Máquina de estados

```
┌──────────────────────────────────────────────────────────────┐
│                     robo.bat clicado                         │
└──────────────────────────┬───────────────────────────────────┘
                           │
                WSL instalado?  ──── NÃO ──→  wsl --install -d Ubuntu
                           │                  Informa usuário: reinicie o
                           │                  Windows e clique novamente.
                          SIM                 Para aqui.
                           │
                .setup_done    ──── NÃO ──→  wsl -d Ubuntu -- bash setup.sh
                existe?                      (instala deps, clona repo, cria
                           │                  venv, coleta credenciais, salva
                          SIM                 .env, marca .setup_done)
                           │                  Em seguida executa o robô.
                           │
                    Executa o robô
         wsl -d Ubuntu -- bash -c
         "source venv/bin/activate &&
          python siafi_automacao/login.py"
```

**Arquivo sentinela:** `~/code/splor-mg/siafi-automacao-cota/.setup_done`
Verificado pelo PowerShell via `wsl -d Ubuntu -- test -f <caminho>`.

---

## Fluxo de primeira vez

A instalação do WSL exige reinicialização — isso é uma limitação do Windows, não contornável.

| Momento | O que acontece |
|---------|---------------|
| **Clique 1** | `robo.ps1` detecta WSL ausente → solicita admin via UAC → executa `wsl --install -d Ubuntu` → informa usuário para reiniciar |
| **Reboot** | Windows abre automaticamente o terminal Ubuntu pedindo usuário e senha Linux |
| **Clique 2** | `robo.ps1` detecta Ubuntu instalado, `.setup_done` ausente → executa `setup.sh` no terminal WSL → ao final executa o robô |
| **Cliques seguintes** | `.setup_done` presente → executa o robô diretamente |

---

## `setup.sh` — detalhes

Executado uma única vez (marcado por `.setup_done`). Passos em ordem:

```bash
# 1. Dependências do sistema
sudo apt update
sudo apt install -y s3270 x3270 python3 python3-venv python3-pip git

# 2. Clone do repositório no filesystem Linux (não /mnt/c/ — performance)
mkdir -p ~/code/splor-mg
git clone https://github.com/splor-mg/siafi-automacao-cota.git \
    ~/code/splor-mg/siafi-automacao-cota

# 3. Ambiente virtual Python
cd ~/code/splor-mg/siafi-automacao-cota
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Criação do .env com credenciais SIAFI (interativo)
#    Campos: SISTEMA, USUARIO, SENHA (oculta), UNIDADE_EXECUTORA
#    Arquivo gravado em .env (já coberto pelo .gitignore)

# 5. Sentinela
touch .setup_done
```

**Repositório privado:** se o clone falhar por autenticação, o script solicitará um GitHub Personal Access Token antes de tentar novamente.

**Credenciais SIAFI:** coletadas interativamente via `read` / `read -s` (senha sem eco). Gravadas em `.env` no formato `CHAVE=VALOR`. O arquivo `.env` nunca é comitado (`.gitignore` já cobre).

---

## Segurança e limitações

- A senha SIAFI fica em texto plano no `.env` dentro do WSL — aceitável dado o contexto de uso (máquina pessoal, acesso local)
- O `robo.bat` solicita elevação UAC apenas na fase de instalação do WSL; nas execuções seguintes roda sem admin
- O `setup.sh` é referenciado pelo PowerShell via `/mnt/c/` — o diretório do projeto no Windows deve estar acessível

---

## Arquivos a criar

| Arquivo | Novo? |
|---------|-------|
| `robo.bat` | Novo |
| `robo.ps1` | Novo |
| `setup.sh` | Novo |

Nenhum arquivo existente é modificado.
