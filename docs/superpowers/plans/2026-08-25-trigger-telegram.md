# Trigger via Telegram — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir acionar o robô SIAFI a partir de um grupo do Telegram, com acompanhamento do andamento por lá, sem ninguém na frente da máquina.

**Architecture:** Um bot em long-polling roda como serviço systemd dentro do WSL da máquina que tem o OneDrive e o acesso ao SIAFI. Ele dispara `rodar.sh`, que passa a ser a sequência única de execução (usada também pelo `robo.ps1`). O robô grava eventos estruturados num `.jsonl` via `relato.py`; o bot lê esse arquivo — nunca o stdout bruto — e monta as mensagens do grupo.

**Tech Stack:** Python 3.12, `requests`, `python-dotenv`, pytest, bash (`flock`), systemd, PowerShell 5.1.

**Spec:** `docs/superpowers/specs/2026-08-25-trigger-telegram-design.md`

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---------|------------------|
| `rodar.sh` (novo) | Sequência única de execução: git pull → venv → `login.py`. Lock e log. |
| `siafi_automacao/relato.py` (novo) | `relato()` (console + `.jsonl`) e `formatar_valor()`. Sem dependência do Telegram. |
| `siafi_automacao/telegram_mensagens.py` (novo) | Funções puras: autorização, montagem e poda das mensagens, redação de senha. Zero rede. |
| `siafi_automacao/bot_telegram.py` (novo) | Loop de polling, chamadas HTTP, subprocess, estado da execução. |
| `siafi-bot.service` (novo) | Unit do systemd. |
| `instalar_bot.sh` (novo) | Gera a unit com os caminhos/usuário corretos e habilita o serviço. |
| `tests/` (novo) | Testes. |
| `siafi_automacao/login.py` (modificar) | Emitir eventos de relato. |
| `siafi_automacao/consolida.py` (modificar) | Emitir evento de relato da planilha. |
| `siafi_automacao/fluxo_aprovar.py`, `fluxo_anular.py` (modificar) | Emitir evento de retorno do SIAFI. |
| `robo.ps1` (modificar) | Chamar `rodar.sh` em vez de repetir a sequência inline. |
| `.env.example`, `setup.sh`, `RUNBOOK.md` (modificar) | Configuração e documentação. |

**Nota sobre imports:** o projeto roda como `python siafi_automacao/login.py`, o que coloca `siafi_automacao/` no `sys.path`. Por isso os módulos se importam de forma plana (`from fluxo_anular import anular`). Mantenha esse padrão: use `from relato import relato`, não `from siafi_automacao.relato import relato`.

**Um desvio consciente em relação ao spec:** o spec diz que o contador final (`4 linhas · 2 efetuadas · 2 puladas · 0 com erro`) seria um evento novo emitido pelo `login.py`. Neste plano ele é **calculado pelo bot** a partir dos eventos de linha, em `montar_final()`. O robô já emite tudo que a conta precisa; emitir também o total seria duas fontes de verdade para o mesmo número, que podem divergir. A mensagem no grupo fica idêntica à combinada.

---

## Task 1: Infraestrutura de testes

O repositório não tem nenhum teste hoje. Esta task só cria o terreno.

**Files:**
- Create: `pytest.ini`
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Criar `pytest.ini`**

O `pythonpath` é o que permite os testes importarem `relato`, `telegram_mensagens` etc. da mesma forma que os scripts fazem em produção.

```ini
[pytest]
testpaths = tests
pythonpath = siafi_automacao
```

- [ ] **Step 2: Criar `requirements-dev.txt`**

```
pytest==8.3.4
```

- [ ] **Step 3: Acrescentar `requests` ao `requirements.txt`**

O arquivo hoje termina sem quebra de linha após `python-dotenv==1.2.2`. Deixe assim:

```
py3270==0.3.5
pandas==3.0.2
openpyxl==3.1.5
python-dotenv==1.2.2
requests==2.32.3
```

- [ ] **Step 4: Criar `tests/__init__.py` vazio**

```bash
touch tests/__init__.py
```

- [ ] **Step 5: Instalar e verificar**

Run:
```bash
source venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt && pytest
```
Expected: `no tests ran` (exit code 5). O importante é o pytest executar sem erro de configuração.

- [ ] **Step 6: Commit**

```bash
git add pytest.ini requirements-dev.txt requirements.txt tests/__init__.py
git commit -m "chore: adiciona pytest e requests ao projeto"
```

---

## Task 2: `formatar_valor()`

Converte o inteiro em centavos da planilha para reais. Isolada e testada porque erro aqui é silencioso e exibe valor errado para quem aprova cota.

**Files:**
- Create: `siafi_automacao/relato.py`
- Create: `tests/test_relato.py`

- [ ] **Step 1: Escrever o teste que falha**

`tests/test_relato.py`:

```python
import pytest

from relato import formatar_valor


@pytest.mark.parametrize('centavos, esperado', [
    (7400000,   'R$ 74.000,00'),
    (50000000,  'R$ 500.000,00'),
    (0,         'R$ 0,00'),
    (5,         'R$ 0,05'),
    (123,       'R$ 1,23'),
    (100,       'R$ 1,00'),
    (-7400000,  '-R$ 74.000,00'),
])
def test_formatar_valor(centavos, esperado):
    assert formatar_valor(centavos) == esperado


def test_formatar_valor_aceita_string():
    """A planilha as vezes entrega o valor como texto."""
    assert formatar_valor('7400000') == 'R$ 74.000,00'
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `source venv/bin/activate && pytest tests/test_relato.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'relato'`

- [ ] **Step 3: Implementação mínima**

`siafi_automacao/relato.py`:

```python
"""Separa a mensagem destinada ao usuario da saida de diagnostico.

O robo continua imprimindo tudo no console (a janela do robo.bat fica igual a
de hoje). Alem disso, os eventos que interessam a quem acompanha pelo Telegram
sao gravados num .jsonl que o bot le. O bot nunca le o stdout bruto: assim um
print() de debug futuro nao vaza para o grupo.
"""


def formatar_valor(centavos):
    """Converte o inteiro em centavos da planilha para reais.

    A planilha guarda o valor no formato do mainframe, sem separador decimal:
    7400000 significa R$ 74.000,00.
    """
    n = int(centavos)
    sinal = '-' if n < 0 else ''
    inteiros, cents = divmod(abs(n), 100)
    milhar = f'{inteiros:,}'.replace(',', '.')
    return f'{sinal}R$ {milhar},{cents:02d}'
```

- [ ] **Step 4: Rodar o teste**

Run: `source venv/bin/activate && pytest tests/test_relato.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add siafi_automacao/relato.py tests/test_relato.py
git commit -m "feat: formatar_valor converte centavos da planilha em reais"
```

---

## Task 3: `relato()` — console + `.jsonl`

**Files:**
- Modify: `siafi_automacao/relato.py`
- Modify: `tests/test_relato.py`

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `tests/test_relato.py`:

```python
import json

from relato import relato


def test_relato_imprime_no_console_e_nao_quebra_sem_arquivo(capsys, monkeypatch):
    """Sem RELATO_ARQUIVO (execucao manual, fora do bot) so imprime."""
    monkeypatch.delenv('RELATO_ARQUIVO', raising=False)
    relato('login', 'Login no SIAFI realizado')
    assert capsys.readouterr().out == 'Login no SIAFI realizado\n'


def test_relato_grava_evento_no_jsonl(tmp_path, monkeypatch):
    arquivo = tmp_path / 'relato.jsonl'
    monkeypatch.setenv('RELATO_ARQUIVO', str(arquivo))

    relato('linha', 'Processando linha 4', linha=4, uo='1261')

    eventos = [json.loads(l) for l in arquivo.read_text(encoding='utf-8').splitlines()]
    assert len(eventos) == 1
    assert eventos[0]['tipo'] == 'linha'
    assert eventos[0]['texto'] == 'Processando linha 4'
    assert eventos[0]['linha'] == 4
    assert eventos[0]['uo'] == '1261'
    assert 'ts' in eventos[0]


def test_relato_acumula_eventos_na_ordem(tmp_path, monkeypatch):
    arquivo = tmp_path / 'relato.jsonl'
    monkeypatch.setenv('RELATO_ARQUIVO', str(arquivo))

    relato('login', 'Login no SIAFI realizado')
    relato('pendentes', '2 linha(s) pendente(s)', linhas=[4, 5])

    eventos = [json.loads(l) for l in arquivo.read_text(encoding='utf-8').splitlines()]
    assert [e['tipo'] for e in eventos] == ['login', 'pendentes']
    assert eventos[1]['linhas'] == [4, 5]


def test_relato_cria_a_pasta_se_nao_existir(tmp_path, monkeypatch):
    arquivo = tmp_path / 'logs' / 'relato.jsonl'
    monkeypatch.setenv('RELATO_ARQUIVO', str(arquivo))

    relato('login', 'Login no SIAFI realizado')

    assert arquivo.exists()
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `source venv/bin/activate && pytest tests/test_relato.py -v`
Expected: FAIL com `ImportError: cannot import name 'relato'`

- [ ] **Step 3: Implementar**

Acrescente a `siafi_automacao/relato.py` (imports no topo do arquivo):

```python
import json
import os
from datetime import datetime
```

E a função:

```python
def relato(tipo, texto, **campos):
    """Imprime no console e, se houver execucao instrumentada, grava o evento.

    O caminho do arquivo vem da variavel de ambiente RELATO_ARQUIVO, definida
    pelo rodar.sh. Usar variavel de ambiente (em vez de parametro) faz o
    consolida.py, que roda como subprocesso do login.py, herdar o mesmo arquivo
    sem precisar receber nada.
    """
    print(texto)

    caminho = os.getenv('RELATO_ARQUIVO')
    if not caminho:
        return

    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)

    evento = {
        'tipo': tipo,
        'ts': datetime.now().isoformat(timespec='seconds'),
        'texto': texto,
    }
    evento.update(campos)

    with open(caminho, 'a', encoding='utf-8') as f:
        f.write(json.dumps(evento, ensure_ascii=False) + '\n')
```

- [ ] **Step 4: Rodar os testes**

Run: `source venv/bin/activate && pytest tests/test_relato.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add siafi_automacao/relato.py tests/test_relato.py
git commit -m "feat: relato() grava eventos estruturados para o bot ler"
```

---

## Task 4: Instrumentar `consolida.py`

Um único evento: quantas planilhas foram lidas e quantas linhas no total.

**Files:**
- Modify: `siafi_automacao/consolida.py:608`

- [ ] **Step 1: Acrescentar o import**

No bloco de imports do topo de `siafi_automacao/consolida.py`, acrescente:

```python
from relato import relato
```

- [ ] **Step 2: Emitir o evento junto ao `Salvo:`**

A linha 608 hoje é:

```python
    print(f'Salvo: {destino_final} ({len(final)} linhas no total)')
```

Substitua por:

```python
    print(f'Salvo: {destino_final} ({len(final)} linhas no total)')
    relato('planilha',
           f'{len(arquivos_origem)} planilha(s) lida(s), validação OK '
           f'({len(final)} linhas)')
```

O `print` do caminho absoluto continua — é diagnóstico e vai só para o log. O `relato` é a versão enxuta que vai ao grupo.

- [ ] **Step 3: Verificar que o módulo ainda importa**

Run: `source venv/bin/activate && python -c "import sys; sys.path.insert(0, 'siafi_automacao'); import consolida; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add siafi_automacao/consolida.py
git commit -m "feat: consolida.py emite evento de relato da planilha lida"
```

---

## Task 5: Instrumentar `login.py` e os fluxos

**Files:**
- Modify: `siafi_automacao/login.py` (linhas 460, 527, 535, 541-549, 564, 580, 594-596; e o laço em 521-562)
- Modify: `siafi_automacao/fluxo_aprovar.py:74`
- Modify: `siafi_automacao/fluxo_anular.py:79`

- [ ] **Step 1: Import em `login.py`**

Junto dos imports planos existentes (`from fluxo_anular import anular`, linha 15-16), acrescente:

```python
from relato import relato
```

- [ ] **Step 2: Evento de login (linha 460)**

Hoje:

```python
                    print("Login realizado com sucesso!")
```

Vira:

```python
                    relato('login', "Login no SIAFI realizado")
```

- [ ] **Step 3: Evento de pendentes (linha 429)**

Hoje:

```python
    print(f"{len(pendentes)} linha(s) pendente(s) para processar: {pendentes}")
```

Vira:

```python
    relato('pendentes',
           f"{len(pendentes)} linha(s) pendente(s): "
           f"{', '.join(str(p) for p in pendentes)}",
           linhas=pendentes)
```

- [ ] **Step 4: Eventos de linha pulada (linhas 527 e 535)**

Hoje:

```python
                print(f"Linha {r}: IAG 1, pulando.")
```

Vira:

```python
                relato('linha_pulada', f"Linha {r}: IAG 1, pulando.",
                       linha=r, motivo='IAG 1')
```

E:

```python
                print(f"Linha {r}: sem GLOBAL/AMARRADO definido, pulando.")
```

Vira:

```python
                relato('linha_pulada',
                       f"Linha {r}: sem GLOBAL/AMARRADO definido, pulando.",
                       linha=r, motivo='sem GLOBAL/AMARRADO')
```

- [ ] **Step 5: Evento da linha processada (linhas 540-549)**

O bloco hoje é:

```python
            if data_row['valor_anulacao'] != 0:
                print("realizando procedimento de anulação")
            elif data_row['valor_aprovacao'] != 0:
                print("realizando procedimento de aprovação")

            print(
                f"Processando linha {r} | UO: {data_row['uo']}, Grupo: {data_row['grupo']}, "
                f"Acao: {data_row['acao']}, Fonte: {data_row['fonte']}, "
                f"Procedencia: {data_row['procedencia']}, Valor: {data_row['valor']}"
            )
```

Substitua o bloco inteiro por:

```python
            if data_row['valor_anulacao'] != 0:
                operacao = 'anulação'
            elif data_row['valor_aprovacao'] != 0:
                operacao = 'aprovação'
            else:
                operacao = 'sem valor'

            relato('linha',
                   f"realizando procedimento de {operacao}\n"
                   f"Processando linha {r} | UO: {data_row['uo']}, "
                   f"Grupo: {data_row['grupo']}, Acao: {data_row['acao']}, "
                   f"Fonte: {data_row['fonte']}, "
                   f"Procedencia: {data_row['procedencia']}, "
                   f"Valor: {data_row['valor']}",
                   linha=r, operacao=operacao, uo=data_row['uo'],
                   acao=data_row['acao'], fonte=data_row['fonte'],
                   valor=data_row['valor'])
```

O texto do console continua praticamente idêntico ao de hoje; os campos estruturados é que alimentam a mensagem do Telegram.

- [ ] **Step 6: Evento de retorno do SIAFI**

`fluxo_aprovar.py:74` e `fluxo_anular.py:79` têm a mesma linha:

```python
    print(f"SIAFI retornou: {retorno}")
```

Em **ambos**, substitua por:

```python
    relato('retorno', f"SIAFI retornou: {retorno}", retorno=str(retorno))
```

E acrescente `from relato import relato` no topo dos dois arquivos.

Os módulos não conhecem o número da linha — e não precisam. Como o processamento é sequencial, o bot associa cada `retorno` à última `linha` aberta.

- [ ] **Step 7: Marcar sucesso/erro do retorno em `login.py` (linha 561)**

Hoje:

```python
            ws.cell(row=r, column=col['Progresso']).value = traduzir_progresso(retorno)
            wb.save(caminho_local)
```

Vira:

```python
            progresso = traduzir_progresso(retorno)
            relato('resultado', f"Linha {r}: {progresso}",
                   linha=r, ok=(progresso == 'Ok'), progresso=progresso)
            ws.cell(row=r, column=col['Progresso']).value = progresso
            wb.save(caminho_local)
```

`traduzir_progresso` (linha 230) devolve `'Ok'` para sucesso e um texto amigável para os erros conhecidos do SIAFI — por isso a comparação com `'Ok'` é o critério de sucesso.

- [ ] **Step 8: Evento de fim e de planilha final (linhas 564 e 580)**

Hoje:

```python
        print('Fluxo finalizado')
```

Vira:

```python
        relato('fim', 'Fluxo finalizado')
```

E na linha 580:

```python
        print(f"Planilha atualizada e movida para a pasta de conferencia: {caminho_destino}")
```

Vira:

```python
        print(f"Planilha atualizada e movida para a pasta de conferencia: {caminho_destino}")
        relato('planilha_final', os.path.basename(caminho_destino))
```

Só o nome do arquivo vai para o grupo; o caminho completo do OneDrive fica no log.

- [ ] **Step 9: Evento de erro (linhas 592-596)**

O bloco hoje é:

```python
        print("")
        if isinstance(e, SystemExit):
            print("Execucao interrompida antes de concluir todas as linhas.")
        else:
            print(f"Execucao interrompida por erro: {type(e).__name__}: {e}")
```

Vira:

```python
        print("")
        if isinstance(e, SystemExit):
            relato('erro', "Execução interrompida antes de concluir todas as linhas.")
        else:
            relato('erro', f"Execução interrompida por erro: {type(e).__name__}: {e}")
```

- [ ] **Step 10: Verificar que os módulos ainda importam**

Run:
```bash
source venv/bin/activate && python -c "import sys; sys.path.insert(0, 'siafi_automacao'); import fluxo_aprovar, fluxo_anular; print('ok')"
```
Expected: `ok`

(`login.py` executa o fluxo no import de `__main__` só quando rodado direto, então não dá para importá-lo aqui; a verificação dele é a Task 6.)

- [ ] **Step 11: Commit**

```bash
git add siafi_automacao/login.py siafi_automacao/fluxo_aprovar.py siafi_automacao/fluxo_anular.py
git commit -m "feat: login.py e fluxos emitem eventos de relato"
```

---

## Task 6: `rodar.sh` — sequência única de execução

**Files:**
- Create: `rodar.sh`
- Create: `tests/test_rodar_sh.py`

- [ ] **Step 1: Escrever o teste de integração que falha**

O teste monta um repositório falso (git de verdade, sem remoto; `venv/bin/activate` vazio; um `login.py` que dorme) e roda o `rodar.sh` real duas vezes em paralelo. Nada de código só-para-teste no `rodar.sh`.

`tests/test_rodar_sh.py`:

```python
import os
import shutil
import subprocess
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def montar_repo_falso(destino):
    """Cria a estrutura minima que o rodar.sh espera, com um login.py de mentira."""
    os.makedirs(destino / 'siafi_automacao', exist_ok=True)
    os.makedirs(destino / 'venv' / 'bin', exist_ok=True)
    os.makedirs(destino / 'data', exist_ok=True)

    shutil.copy(os.path.join(RAIZ, 'rodar.sh'), destino / 'rodar.sh')
    os.chmod(destino / 'rodar.sh', 0o755)

    # venv/bin/activate vazio: 'source' num arquivo vazio funciona.
    (destino / 'venv' / 'bin' / 'activate').write_text('')
    # 5 segundos: tempo folgado para a segunda invocacao tentar o lock enquanto
    # a primeira ainda esta rodando, sem deixar o teste lento.
    (destino / 'siafi_automacao' / 'login.py').write_text(
        'import time\nprint("robo falso rodando")\ntime.sleep(5)\n')

    subprocess.run(['git', 'init', '-q', '-b', 'main'], cwd=destino, check=True)
    subprocess.run(['git', 'config', 'user.email', 'teste@teste'], cwd=destino, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Teste'], cwd=destino, check=True)
    subprocess.run(['git', 'add', '-A'], cwd=destino, check=True)
    subprocess.run(['git', 'commit', '-q', '-m', 'inicial'], cwd=destino, check=True)


def test_segunda_execucao_simultanea_sai_com_codigo_10(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    montar_repo_falso(repo)

    primeira = subprocess.Popen(['bash', str(repo / 'rodar.sh')],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(1.5)  # tempo de a primeira pegar o lock e entrar no sleep

    segunda = subprocess.run(['bash', str(repo / 'rodar.sh')],
                             capture_output=True, text=True)
    assert segunda.returncode == 10

    assert primeira.wait(timeout=30) == 0


def test_execucao_isolada_termina_com_sucesso_e_gera_log(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    montar_repo_falso(repo)

    r = subprocess.run(['bash', str(repo / 'rodar.sh')], capture_output=True, text=True)
    assert r.returncode == 0

    logs = list((repo / 'data' / 'logs').glob('robo-*.log'))
    assert len(logs) == 1
    conteudo = logs[0].read_text(encoding='utf-8')
    assert 'robo falso rodando' in conteudo
    # Sem remoto configurado, o git pull falha e o aviso tem que aparecer.
    assert 'Nao foi possivel atualizar' in conteudo


def test_propaga_codigo_de_erro_do_login(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    montar_repo_falso(repo)
    (repo / 'siafi_automacao' / 'login.py').write_text('raise SystemExit(3)\n')

    r = subprocess.run(['bash', str(repo / 'rodar.sh')], capture_output=True, text=True)
    assert r.returncode == 3
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `source venv/bin/activate && pytest tests/test_rodar_sh.py -v`
Expected: FAIL — `rodar.sh` não existe (`FileNotFoundError` no `shutil.copy`)

- [ ] **Step 3: Implementar `rodar.sh`**

```bash
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
```

- [ ] **Step 4: Tornar executável e rodar os testes**

Run:
```bash
chmod +x rodar.sh && source venv/bin/activate && pytest tests/test_rodar_sh.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add rodar.sh tests/test_rodar_sh.py
git commit -m "feat: rodar.sh centraliza a sequencia de execucao com lock e log"
```

---

## Task 7: `robo.ps1` passa a chamar `rodar.sh`

Elimina a duplicação da sequência entre o launcher do Windows e o bot.

**Files:**
- Modify: `robo.ps1:147-163`

- [ ] **Step 1: Substituir a Fase 3**

O bloco atual (linhas 147 a 163) é:

```powershell
# Fase 3: Tudo pronto — atualizar o repositorio e executar o robo
Write-Host "Atualizando o robo (git pull na main)..." -ForegroundColor Cyan
wsl -d Ubuntu -- bash -c "cd ~/code/splor-mg/siafi-automacao-cota && git checkout main && git pull origin main"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[aviso] Nao foi possivel atualizar via git pull. Rodando a versao local atual." -ForegroundColor Yellow
}
Write-Host ""

Write-Host "Iniciando o robo SIAFI..." -ForegroundColor Cyan
wsl -d Ubuntu -- bash -c "cd ~/code/splor-mg/siafi-automacao-cota && source venv/bin/activate && PYTHONIOENCODING=utf-8 python siafi_automacao/login.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "O robo encerrou com erro (codigo $LASTEXITCODE)." -ForegroundColor Red
}

exit $LASTEXITCODE
```

Substitua por:

```powershell
# Fase 3: Tudo pronto — executar o robo.
# A sequencia (git pull, venv, login.py) vive no rodar.sh, compartilhada com o
# bot do Telegram, para os dois caminhos rodarem exatamente a mesma coisa.
Write-Host "Iniciando o robo SIAFI..." -ForegroundColor Cyan
wsl -d Ubuntu -- bash -c "bash ~/code/splor-mg/siafi-automacao-cota/rodar.sh"

if ($LASTEXITCODE -eq 10) {
    Write-Host ""
    Write-Host "Ja existe uma execucao do robo em andamento. Aguarde ela terminar." -ForegroundColor Yellow
} elseif ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "O robo encerrou com erro (codigo $LASTEXITCODE)." -ForegroundColor Red
}

exit $LASTEXITCODE
```

**Atenção:** o `robo.ps1` não pode conter caracteres acentuados nas mensagens `Write-Host` — o PowerShell 5.1 lê o arquivo como Windows-1252 e corrompe os acentos. Use ASCII puro, como acima.

- [ ] **Step 2: Verificar que não entrou acento no arquivo**

Run: `grep -nP '[^\x00-\x7F]' robo.ps1 || echo "ASCII puro, ok"`
Expected: `ASCII puro, ok`

- [ ] **Step 3: Commit**

```bash
git add robo.ps1
git commit -m "refactor: robo.ps1 usa rodar.sh em vez de repetir a sequencia"
```

---

## Task 8: Autorização e redação de senha

Funções puras, sem rede — o coração da segurança do bot.

**Files:**
- Create: `siafi_automacao/telegram_mensagens.py`
- Create: `tests/test_telegram_mensagens.py`

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_telegram_mensagens.py`:

```python
import time

from telegram_mensagens import autorizado, muito_antigo, redigir

GRUPO = '-1001234567890'


def update_de(chat_id, texto='/rodar', is_bot=False, quando=None):
    return {
        'update_id': 1,
        'message': {
            'message_id': 10,
            'date': int(quando if quando is not None else time.time()),
            'chat': {'id': chat_id},
            'from': {'id': 42, 'first_name': 'Guilherme', 'is_bot': is_bot},
            'text': texto,
        },
    }


def test_aceita_mensagem_do_grupo_autorizado():
    assert autorizado(update_de(int(GRUPO)), GRUPO) is True


def test_recusa_mensagem_de_outro_chat():
    assert autorizado(update_de(999), GRUPO) is False


def test_recusa_mensagem_de_bot():
    assert autorizado(update_de(int(GRUPO), is_bot=True), GRUPO) is False


def test_recusa_edicao_de_mensagem():
    """Edicao chega em 'edited_message'. Reprocessar edicao dispararia o robo
    de novo a partir de uma mensagem antiga."""
    up = update_de(int(GRUPO))
    up['edited_message'] = up.pop('message')
    assert autorizado(up, GRUPO) is False


def test_recusa_update_sem_mensagem():
    assert autorizado({'update_id': 1, 'callback_query': {}}, GRUPO) is False


def test_update_recente_nao_e_antigo():
    agora = time.time()
    assert muito_antigo(update_de(int(GRUPO), quando=agora), agora=agora) is False


def test_update_de_dez_minutos_atras_e_antigo():
    agora = time.time()
    up = update_de(int(GRUPO), quando=agora - 600)
    assert muito_antigo(up, agora=agora) is True


def test_redige_a_senha_do_texto():
    texto = 'falha ao logar com senha SEGREDO123 no SIAFI'
    assert redigir(texto, ['SEGREDO123']) == 'falha ao logar com senha *** no SIAFI'


def test_redigir_ignora_segredos_vazios():
    assert redigir('texto qualquer', ['', None]) == 'texto qualquer'
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `source venv/bin/activate && pytest tests/test_telegram_mensagens.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'telegram_mensagens'`

- [ ] **Step 3: Implementar**

`siafi_automacao/telegram_mensagens.py`:

```python
"""Montagem das mensagens do Telegram e regras de autorizacao.

Funcoes puras, sem rede e sem estado: o bot_telegram.py cuida do I/O. Assim
tudo que decide "quem pode acionar" e "o que sai no grupo" e testavel sem
tocar na API do Telegram nem no SIAFI.
"""

IDADE_MAXIMA_UPDATE = 300  # segundos


def autorizado(update, chat_autorizado):
    """So aceita mensagem nova, de humano, vinda do grupo autorizado.

    Edicoes de mensagem chegam sob a chave 'edited_message' e por isso ja caem
    fora: reprocessar uma edicao dispararia o robo a partir de um comando
    antigo.
    """
    msg = update.get('message')
    if not msg:
        return False
    if msg.get('from', {}).get('is_bot'):
        return False
    return str(msg.get('chat', {}).get('id')) == str(chat_autorizado)


def muito_antigo(update, agora, idade_maxima=IDADE_MAXIMA_UPDATE):
    """Comando velho demais para ser obedecido.

    Protege o caso de o bot ficar fora do ar e voltar com backlog: ninguem quer
    que o robo dispare sozinho por causa de um /rodar de uma hora atras.
    """
    msg = update.get('message') or {}
    return (agora - msg.get('date', 0)) > idade_maxima


def redigir(texto, segredos):
    """Troca ocorrencias dos segredos por *** antes de qualquer coisa sair."""
    for segredo in segredos:
        if segredo:
            texto = texto.replace(segredo, '***')
    return texto
```

- [ ] **Step 4: Rodar os testes**

Run: `source venv/bin/activate && pytest tests/test_telegram_mensagens.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add siafi_automacao/telegram_mensagens.py tests/test_telegram_mensagens.py
git commit -m "feat: autorizacao por grupo, descarte de comando antigo e redacao de senha"
```

---

## Task 9: Montagem das mensagens

**Files:**
- Modify: `siafi_automacao/telegram_mensagens.py`
- Modify: `tests/test_telegram_mensagens.py`

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao fim de `tests/test_telegram_mensagens.py`:

```python
from telegram_mensagens import (agrupar_linhas, formatar_duracao,
                                montar_final, montar_progresso)


def eventos_de_exemplo():
    return [
        {'tipo': 'planilha', 'texto': '1 planilha(s) lida(s), validação OK (4 linhas)'},
        {'tipo': 'login', 'texto': 'Login no SIAFI realizado'},
        {'tipo': 'pendentes', 'texto': '4 linha(s) pendente(s): 2, 3, 4, 5',
         'linhas': [2, 3, 4, 5]},
        {'tipo': 'linha_pulada', 'texto': '...', 'linha': 2, 'motivo': 'IAG 1'},
        {'tipo': 'linha_pulada', 'texto': '...', 'linha': 3, 'motivo': 'IAG 1'},
        {'tipo': 'linha', 'texto': '...', 'linha': 4, 'operacao': 'aprovação',
         'uo': '1261', 'acao': '4511', 'fonte': '10', 'valor': 7400000},
        {'tipo': 'retorno', 'texto': '...', 'retorno': '0011-REGISTRO EFETUADO.'},
        {'tipo': 'resultado', 'texto': '...', 'linha': 4, 'ok': True, 'progresso': 'Ok'},
        {'tipo': 'linha', 'texto': '...', 'linha': 5, 'operacao': 'aprovação',
         'uo': '1261', 'acao': '2128', 'fonte': '10', 'valor': 50000000},
        {'tipo': 'retorno', 'texto': '...', 'retorno': '0011-REGISTRO EFETUADO.'},
        {'tipo': 'resultado', 'texto': '...', 'linha': 5, 'ok': True, 'progresso': 'Ok'},
        {'tipo': 'fim', 'texto': 'Fluxo finalizado'},
        {'tipo': 'planilha_final', 'texto': 'Conferencia arquivo robo 25.08.xlsx'},
    ]


def test_formatar_duracao():
    assert formatar_duracao(45) == '45s'
    assert formatar_duracao(192) == '3min12s'
    assert formatar_duracao(3720) == '1h02min'


def test_progresso_sai_vazio_antes_de_saber_as_pendentes():
    assert montar_progresso(eventos_de_exemplo()[:2]) is None


def test_progresso_junta_planilha_login_e_pendentes():
    msg = montar_progresso(eventos_de_exemplo())
    assert msg == ('1 planilha(s) lida(s), validação OK (4 linhas)\n'
                   'Login no SIAFI realizado\n'
                   '4 linha(s) pendente(s): 2, 3, 4, 5')


def test_agrupar_associa_retorno_a_ultima_linha_aberta():
    itens = agrupar_linhas(eventos_de_exemplo())
    assert [i['linha'] for i in itens] == [2, 3, 4, 5]
    assert itens[0]['pulada'] is True
    assert itens[2]['retorno'] == '0011-REGISTRO EFETUADO.'
    assert itens[2]['ok'] is True
    assert itens[3]['retorno'] == '0011-REGISTRO EFETUADO.'


def test_final_traz_cabecalho_linhas_e_resumo():
    msg = montar_final(eventos_de_exemplo(), codigo=0, duracao_seg=192)
    assert 'Robô SIAFI · concluído em 3min12s' in msg
    assert 'Linha 2 · pulada (IAG 1)' in msg
    assert ('Linha 4 · aprovação · UO 1261 · Ação 4511 · Fonte 10 · '
            'R$ 74.000,00') in msg
    assert 'R$ 500.000,00' in msg
    assert '0011-REGISTRO EFETUADO.' in msg
    assert '4 linhas · 2 efetuada(s) · 2 pulada(s) · 0 com erro' in msg
    assert 'Planilha: Conferencia arquivo robo 25.08.xlsx' in msg


def test_final_marca_falha_e_mostra_o_erro():
    eventos = eventos_de_exemplo()[:8] + [
        {'tipo': 'erro', 'texto': 'Execução interrompida por erro: TimeoutError: x'},
    ]
    msg = montar_final(eventos, codigo=1, duracao_seg=60)
    assert 'FALHOU (código 1)' in msg
    assert 'Execução interrompida por erro' in msg


def test_final_conta_linha_com_erro():
    eventos = eventos_de_exemplo()[:8]
    eventos[7] = {'tipo': 'resultado', 'texto': '...', 'linha': 4, 'ok': False,
                  'progresso': 'Saldo zerado na conta'}
    msg = montar_final(eventos, codigo=0, duracao_seg=10)
    assert '3 linhas · 0 efetuada(s) · 2 pulada(s) · 1 com erro' in msg


def test_final_escapa_html_do_retorno_do_siafi():
    eventos = eventos_de_exemplo()[:7]
    eventos[6] = {'tipo': 'retorno', 'texto': '...', 'retorno': 'ERRO <A & B>'}
    msg = montar_final(eventos, codigo=0, duracao_seg=10)
    assert '&lt;A &amp; B&gt;' in msg
    assert '<A & B>' not in msg


def test_final_poda_linhas_efetuadas_quando_estoura_o_limite():
    """Acima de 4096 caracteres o Telegram recusa a mensagem. As linhas com
    erro sao as que exigem acao, entao sao elas que sobrevivem a poda."""
    eventos = eventos_de_exemplo()[:3]
    for linha in range(10, 210):
        eventos += [
            {'tipo': 'linha', 'texto': '...', 'linha': linha,
             'operacao': 'aprovação', 'uo': '1261', 'acao': '4511',
             'fonte': '10', 'valor': 7400000},
            {'tipo': 'retorno', 'texto': '...', 'retorno': '0011-REGISTRO EFETUADO.'},
            {'tipo': 'resultado', 'texto': '...', 'linha': linha, 'ok': True,
             'progresso': 'Ok'},
        ]
    eventos += [
        {'tipo': 'linha', 'texto': '...', 'linha': 999, 'operacao': 'aprovação',
         'uo': '1261', 'acao': '4511', 'fonte': '10', 'valor': 7400000},
        {'tipo': 'retorno', 'texto': '...', 'retorno': 'E90 - SALDO ZERADO NA CONTA'},
        {'tipo': 'resultado', 'texto': '...', 'linha': 999, 'ok': False,
         'progresso': 'Saldo zerado na conta'},
    ]

    msg = montar_final(eventos, codigo=0, duracao_seg=600)

    assert len(msg) <= 4096
    assert 'Linha 999' in msg          # a que deu erro sobrevive
    assert 'linha(s) efetuada(s) (veja /log)' in msg
    assert '200 efetuada(s)' in msg    # o resumo continua contando tudo
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `source venv/bin/activate && pytest tests/test_telegram_mensagens.py -v`
Expected: FAIL com `ImportError: cannot import name 'agrupar_linhas'`

- [ ] **Step 3: Implementar**

Acrescente ao topo de `siafi_automacao/telegram_mensagens.py`:

```python
from html import escape

from relato import formatar_valor

LIMITE_TELEGRAM = 4096
```

E ao fim do arquivo:

```python
def formatar_duracao(segundos):
    segundos = int(segundos)
    if segundos < 60:
        return f'{segundos}s'
    minutos, s = divmod(segundos, 60)
    if minutos < 60:
        return f'{minutos}min{s:02d}s'
    horas, m = divmod(minutos, 60)
    return f'{horas}h{m:02d}min'


def montar_progresso(eventos):
    """Mensagem do marco intermediario.

    Devolve None enquanto o robo ainda nao souber quantas linhas vai processar
    — o bot fica tentando ate essa hora chegar.
    """
    pendentes = next((e for e in eventos if e['tipo'] == 'pendentes'), None)
    if not pendentes:
        return None

    partes = [e['texto'] for e in eventos if e['tipo'] in ('planilha', 'login')]
    partes.append(pendentes['texto'])
    return '\n'.join(partes)


def agrupar_linhas(eventos):
    """Junta cada linha com o retorno do SIAFI e o resultado que vieram depois.

    fluxo_aprovar/fluxo_anular nao conhecem o numero da linha, e nao precisam:
    o processamento e sequencial, entao o retorno pertence sempre a ultima
    linha aberta.
    """
    itens = []
    for ev in eventos:
        tipo = ev['tipo']
        if tipo == 'linha_pulada':
            itens.append({'linha': ev['linha'], 'pulada': True,
                          'motivo': ev['motivo'], 'ok': True, 'retorno': None})
        elif tipo == 'linha':
            itens.append({'linha': ev['linha'], 'pulada': False,
                          'operacao': ev['operacao'], 'uo': ev['uo'],
                          'acao': ev['acao'], 'fonte': ev['fonte'],
                          'valor': ev['valor'], 'retorno': None, 'ok': False})
        elif tipo == 'retorno' and itens and not itens[-1]['pulada']:
            itens[-1]['retorno'] = ev['retorno']
        elif tipo == 'resultado':
            for item in itens:
                if item['linha'] == ev['linha'] and not item['pulada']:
                    item['ok'] = ev['ok']
                    item['progresso'] = ev['progresso']
    return itens


def _texto_item(item):
    if item['pulada']:
        return f"Linha {item['linha']} · pulada ({item['motivo']})"

    cabecalho = (f"Linha {item['linha']} · {item['operacao']} · "
                 f"UO {item['uo']} · Ação {item['acao']} · "
                 f"Fonte {item['fonte']} · {formatar_valor(item['valor'])}")
    retorno = item['retorno'] or 'sem retorno (execução interrompida)'
    return f"{cabecalho}\n   {retorno}"


def _montar(cabecalho, corpo, rodape):
    return f"{cabecalho}\n\n<pre>{escape(corpo)}</pre>\n\n{rodape}"


def montar_final(eventos, codigo, duracao_seg, limite=LIMITE_TELEGRAM):
    itens = agrupar_linhas(eventos)
    duracao = formatar_duracao(duracao_seg)

    if codigo == 0:
        cabecalho = f'Robô SIAFI · concluído em {duracao}'
    else:
        cabecalho = f'Robô SIAFI · FALHOU (código {codigo}) após {duracao}'

    efetuadas = sum(1 for i in itens if not i['pulada'] and i['ok'])
    puladas = sum(1 for i in itens if i['pulada'])
    com_erro = sum(1 for i in itens if not i['pulada'] and not i['ok'])

    rodape = (f'{len(itens)} linhas · {efetuadas} efetuada(s) · '
              f'{puladas} pulada(s) · {com_erro} com erro')

    planilha = next((e['texto'] for e in eventos
                     if e['tipo'] == 'planilha_final'), None)
    if planilha:
        rodape += f'\nPlanilha: {planilha}'

    erro = next((e['texto'] for e in eventos if e['tipo'] == 'erro'), None)
    if erro:
        rodape += f'\n{erro}'

    corpo = '\n'.join(_texto_item(i) for i in itens)
    mensagem = _montar(cabecalho, corpo, rodape)
    if len(mensagem) <= limite:
        return mensagem

    # Nao coube: as linhas com erro sao as que exigem acao de alguem, entao sao
    # elas que ficam. O resto vira uma contagem, e o log completo tem tudo.
    mantidos = [i for i in itens if i['pulada'] or not i['ok']]
    omitidas = len(itens) - len(mantidos)
    corpo = '\n'.join(_texto_item(i) for i in mantidos)
    corpo += f'\n…+{omitidas} linha(s) efetuada(s) (veja /log)'

    # Guarda final: se nem assim couber (execucao com centenas de erros), corta.
    return _montar(cabecalho, corpo, rodape)[:limite]
```

- [ ] **Step 4: Rodar os testes**

Run: `source venv/bin/activate && pytest tests/ -v`
Expected: todos passam (9 + 9 anteriores + os novos)

- [ ] **Step 5: Commit**

```bash
git add siafi_automacao/telegram_mensagens.py tests/test_telegram_mensagens.py
git commit -m "feat: montagem das mensagens de progresso e final do Telegram"
```

---

## Task 10: Offset persistido

Sem isso, o Telegram reentrega o `/rodar` não confirmado quando o bot reinicia — e o robô dispara sozinho, aprovando cota sem ninguém ter pedido. É a parte mais crítica do bot.

**Files:**
- Create: `siafi_automacao/bot_telegram.py`
- Create: `tests/test_bot_telegram.py`

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_bot_telegram.py`:

```python
from bot_telegram import gravar_offset, ler_eventos, ler_offset


def test_offset_ausente_devolve_none(tmp_path):
    assert ler_offset(tmp_path / 'nao-existe') is None


def test_offset_grava_e_le(tmp_path):
    arquivo = tmp_path / '.telegram_offset'
    gravar_offset(105, arquivo)
    assert ler_offset(arquivo) == 105


def test_offset_corrompido_devolve_none(tmp_path):
    """Arquivo truncado por queda de energia nao pode derrubar o bot."""
    arquivo = tmp_path / '.telegram_offset'
    arquivo.write_text('lixo')
    assert ler_offset(arquivo) is None


def test_ler_eventos_ignora_linha_incompleta(tmp_path):
    """O bot le o .jsonl enquanto o robo ainda escreve nele: a ultima linha
    pode estar pela metade."""
    arquivo = tmp_path / 'relato.jsonl'
    arquivo.write_text('{"tipo": "login", "texto": "ok"}\n{"tipo": "lin',
                       encoding='utf-8')
    eventos = ler_eventos(arquivo)
    assert len(eventos) == 1
    assert eventos[0]['tipo'] == 'login'


def test_ler_eventos_de_arquivo_inexistente(tmp_path):
    assert ler_eventos(tmp_path / 'nao-existe') == []
```

- [ ] **Step 2: Rodar para confirmar que falha**

Run: `source venv/bin/activate && pytest tests/test_bot_telegram.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'bot_telegram'`

- [ ] **Step 3: Implementar o esqueleto do bot com essas funções**

`siafi_automacao/bot_telegram.py`:

```python
"""Bot do Telegram que aciona o robo SIAFI.

Long-polling contra a API do Telegram: dispensa IP publico, porta aberta e
tunel. Roda como servico systemd dentro do WSL da maquina que tem o OneDrive
montado e o acesso de rede ao SIAFI.
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_OFFSET = os.path.join(REPO, 'data', '.telegram_offset')


def ler_offset(caminho=None):
    """Ultimo update_id ja confirmado, ou None se nao houver.

    Devolve None tambem em arquivo corrompido: perder o offset e chato (o
    Telegram reentrega o backlog, que o filtro de idade descarta), mas derrubar
    o bot no arranque seria pior.
    """
    caminho = caminho or ARQUIVO_OFFSET
    try:
        with open(caminho, encoding='utf-8') as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def gravar_offset(offset, caminho=None):
    caminho = caminho or ARQUIVO_OFFSET
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write(str(offset))


def ler_eventos(caminho):
    """Le o .jsonl do relato da execucao.

    Descarta linha incompleta: o bot le o arquivo enquanto o robo ainda escreve
    nele, entao a ultima linha pode estar pela metade.
    """
    eventos = []
    try:
        with open(caminho, encoding='utf-8') as f:
            for linha in f:
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    eventos.append(json.loads(linha))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return eventos
```

- [ ] **Step 4: Rodar os testes**

Run: `source venv/bin/activate && pytest tests/test_bot_telegram.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add siafi_automacao/bot_telegram.py tests/test_bot_telegram.py
git commit -m "feat: offset persistido e leitura do relato no bot"
```

---

## Task 11: Loop de polling, comandos e execução

**Files:**
- Modify: `siafi_automacao/bot_telegram.py`

- [ ] **Step 1: Acrescentar imports e configuração**

Logo abaixo dos imports existentes em `bot_telegram.py`:

```python
import subprocess
import threading
import time
from datetime import datetime

import requests
from dotenv import load_dotenv

from telegram_mensagens import (autorizado, formatar_duracao, montar_final,
                                montar_progresso, muito_antigo, redigir)

load_dotenv(os.path.join(REPO, '.env'))

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_AUTORIZADO = os.getenv('TELEGRAM_CHAT_ID')
API = f'https://api.telegram.org/bot{TOKEN}'
SEGREDOS = [os.getenv('SENHA'), os.getenv('USUARIO')]

ARQUIVO_ULTIMA = os.path.join(REPO, 'data', '.ultima_execucao')
RODAR = os.path.join(REPO, 'rodar.sh')

AJUDA = (
    'Robô SIAFI\n\n'
    '/rodar — executa o robô (consolida as planilhas e processa no SIAFI)\n'
    '/status — diz se há execução em andamento\n'
    '/log — envia o log completo da última execução\n'
    '/ajuda — esta mensagem'
)

EXECUCAO = {'rodando': False, 'inicio': None, 'quem': None}
TRAVA = threading.Lock()
```

- [ ] **Step 2: Funções de envio**

```python
def enviar(texto):
    """Manda uma mensagem para o grupo. Nunca levanta excecao: falha de rede
    aqui nao pode derrubar o bot nem interromper o robo."""
    try:
        requests.post(f'{API}/sendMessage', timeout=30, data={
            'chat_id': CHAT_AUTORIZADO,
            'text': redigir(texto, SEGREDOS),
            'parse_mode': 'HTML',
        })
    except Exception as e:
        print(f'[aviso] falha ao enviar mensagem: {e}')


def enviar_documento(caminho, nome):
    """Envia um arquivo, com os segredos redigidos antes de sair."""
    try:
        with open(caminho, encoding='utf-8', errors='replace') as f:
            conteudo = redigir(f.read(), SEGREDOS)
        requests.post(f'{API}/sendDocument', timeout=60,
                      data={'chat_id': CHAT_AUTORIZADO},
                      files={'document': (nome, conteudo.encode('utf-8'))})
    except Exception as e:
        print(f'[aviso] falha ao enviar documento: {e}')
        enviar(f'Não consegui enviar o log: {e}')
```

- [ ] **Step 3: Caminhos da última execução**

```python
def caminhos_ultima_execucao():
    """(log, relato) da execucao mais recente, ou (None, None).

    O rodar.sh grava esses caminhos assim que pega o lock.
    """
    try:
        with open(ARQUIVO_ULTIMA, encoding='utf-8') as f:
            linhas = [l.strip() for l in f if l.strip()]
        return linhas[0], linhas[1]
    except (OSError, IndexError):
        return None, None
```

- [ ] **Step 4: A execução em si**

```python
def executar(quem):
    """Roda o rodar.sh e publica os marcos no grupo.

    Roda numa thread para o loop de polling continuar respondendo /status
    durante os minutos que o robo leva.
    """
    inicio = time.time()
    carimbo = datetime.now().strftime('%Y%m%d-%H%M%S')

    # O bot define os caminhos em vez de descobri-los depois: assim nao ha
    # risco de ler o relato da execucao ANTERIOR enquanto esta ainda comeca.
    log = os.path.join(REPO, 'data', 'logs', f'robo-{carimbo}.log')
    arquivo_relato = os.path.join(REPO, 'data', 'logs', f'relato-{carimbo}.jsonl')

    ambiente = dict(os.environ, ROBO_LOG=log, RELATO_ARQUIVO=arquivo_relato)

    enviar(f'Robô SIAFI · iniciado\npor {quem} · '
           f'{datetime.now().strftime("%d/%m às %H:%M")}')

    proc = subprocess.Popen(['bash', RODAR], env=ambiente,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)

    progresso_enviado = False
    while proc.poll() is None:
        time.sleep(2)
        if not progresso_enviado:
            msg = montar_progresso(ler_eventos(arquivo_relato))
            if msg:
                enviar(msg)
                progresso_enviado = True

    codigo = proc.returncode
    if codigo == 10:
        enviar('Já existe uma execução em andamento (iniciada pelo robo.bat).')
    else:
        enviar(montar_final(ler_eventos(arquivo_relato), codigo,
                            time.time() - inicio))

    with TRAVA:
        EXECUCAO.update(rodando=False, inicio=None, quem=None)
```

- [ ] **Step 5: Tratamento dos comandos**

```python
def comando_rodar(quem):
    with TRAVA:
        if EXECUCAO['rodando']:
            desde = datetime.fromtimestamp(EXECUCAO['inicio']).strftime('%H:%M')
            enviar(f'Já tem execução em andamento desde {desde}, '
                   f'iniciada por {EXECUCAO["quem"]}.')
            return
        EXECUCAO.update(rodando=True, inicio=time.time(), quem=quem)

    threading.Thread(target=executar, args=(quem,), daemon=True).start()


def comando_status():
    with TRAVA:
        rodando, inicio, quem = (EXECUCAO['rodando'], EXECUCAO['inicio'],
                                 EXECUCAO['quem'])

    if rodando:
        enviar(f'Execução em andamento há {formatar_duracao(time.time() - inicio)}, '
               f'iniciada por {quem}.')
        return

    log, _ = caminhos_ultima_execucao()
    if not log or not os.path.exists(log):
        enviar('Nenhuma execução registrada ainda. Use /rodar.')
        return

    quando = datetime.fromtimestamp(os.path.getmtime(log))
    enviar(f'Nenhuma execução em andamento. '
           f'A última terminou em {quando.strftime("%d/%m às %H:%M")}.')


def comando_log():
    log, _ = caminhos_ultima_execucao()
    if not log or not os.path.exists(log):
        enviar('Não há log de execução ainda.')
        return
    enviar_documento(log, os.path.basename(log))


def tratar(update):
    msg = update['message']
    quem = msg.get('from', {}).get('first_name', 'alguém')
    texto = (msg.get('text') or '').split('@')[0].strip().lower()

    if texto == '/rodar':
        print(f'[{datetime.now():%Y-%m-%d %H:%M:%S}] /rodar acionado por {quem}')
        comando_rodar(quem)
    elif texto == '/status':
        comando_status()
    elif texto == '/log':
        comando_log()
    elif texto in ('/ajuda', '/start', '/help'):
        enviar(AJUDA)
```

O `.split('@')[0]` trata o formato `/rodar@nome_do_bot`, que é como o Telegram entrega comandos em grupo quando há mais de um bot.

- [ ] **Step 6: O loop principal**

```python
def main():
    if not TOKEN or not CHAT_AUTORIZADO:
        raise SystemExit('Defina TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID no .env')

    print(f'Bot iniciado. Grupo autorizado: {CHAT_AUTORIZADO}')
    offset = ler_offset()
    espera = 1

    while True:
        try:
            r = requests.get(f'{API}/getUpdates', timeout=40,
                             params={'offset': offset, 'timeout': 30})
            r.raise_for_status()
            updates = r.json().get('result', [])
            espera = 1
        except Exception as e:
            print(f'[aviso] falha ao consultar o Telegram: {e}')
            time.sleep(espera)
            espera = min(espera * 2, 60)
            continue

        for update in updates:
            # Confirma ANTES de tratar. Se o bot cair no meio do tratamento, o
            # comando nao volta na proxima consulta: um /rodar reentregue
            # dispararia o robo sozinho.
            offset = update['update_id'] + 1
            gravar_offset(offset)

            if not autorizado(update, CHAT_AUTORIZADO):
                continue
            if muito_antigo(update, agora=time.time()):
                print('[info] comando antigo descartado')
                continue

            try:
                tratar(update)
            except Exception as e:
                print(f'[erro] falha ao tratar update: {e}')


if __name__ == '__main__':
    main()
```

- [ ] **Step 7: Verificar que a suíte continua passando e o módulo importa**

Run:
```bash
source venv/bin/activate && pytest tests/ -v && python -c "import sys; sys.path.insert(0, 'siafi_automacao'); import bot_telegram; print('ok')"
```
Expected: todos os testes passam e imprime `ok`

- [ ] **Step 8: Commit**

```bash
git add siafi_automacao/bot_telegram.py
git commit -m "feat: loop de polling, comandos e disparo do robo pelo Telegram"
```

---

## Task 12: Configuração — `.env.example` e `setup.sh`

**Files:**
- Modify: `.env.example`
- Modify: `setup.sh`

- [ ] **Step 1: Acrescentar as variáveis ao `.env.example`**

Ao fim do arquivo:

```bash
# --- Bot do Telegram (opcional) ---------------------------------------------
# Token do bot, obtido no @BotFather (/newbot).
TELEGRAM_BOT_TOKEN=

# ID do grupo autorizado a acionar o robo. Para descobrir: adicione o bot ao
# grupo, mande qualquer mensagem e acesse
#   https://api.telegram.org/bot<TOKEN>/getUpdates
# O id do grupo e negativo, algo como -1001234567890.
TELEGRAM_CHAT_ID=
```

- [ ] **Step 2: Acrescentar a coleta das duas variáveis**

O `setup.sh` não tem função auxiliar: cada variável é coletada com um `if ! grep -q` seguido de `read -rp` e `printf >> .env` (veja o bloco de `ONEDRIVE_BASE`, linhas 116-130, e o de `PASTA_LOCAL`, a partir da linha 138). Siga o mesmo formato.

Acrescente **depois** do bloco de `PASTA_LOCAL`:

```bash
# --- Bot do Telegram (opcional) ---------------------------------------------
# Quem nao usa o Telegram deixa em branco e segue com o robo.bat normalmente.
if ! grep -q "^TELEGRAM_BOT_TOKEN=" .env 2>/dev/null; then
    echo ""
    echo "Bot do Telegram (opcional - Enter para pular)."
    read -rp "  TELEGRAM_BOT_TOKEN: " TELEGRAM_BOT_TOKEN
    printf 'TELEGRAM_BOT_TOKEN=%s\n' "$TELEGRAM_BOT_TOKEN" >> .env
fi

if ! grep -q "^TELEGRAM_CHAT_ID=" .env 2>/dev/null; then
    read -rp "  TELEGRAM_CHAT_ID (id do grupo, negativo): " TELEGRAM_CHAT_ID
    printf 'TELEGRAM_CHAT_ID=%s\n' "$TELEGRAM_CHAT_ID" >> .env
fi
```

Confira antes se o `.env` é mesmo criado/atualizado a partir do diretório corrente nesse ponto do script (os blocos existentes usam `.env` relativo).

- [ ] **Step 4: Verificar a sintaxe do shell**

Run: `bash -n setup.sh && echo "sintaxe ok"`
Expected: `sintaxe ok`

- [ ] **Step 5: Commit**

```bash
git add .env.example setup.sh
git commit -m "feat: coleta as variaveis do Telegram no setup"
```

---

## Task 13: Serviço systemd

**Files:**
- Create: `instalar_bot.sh`

- [ ] **Step 1: Escrever o instalador**

A unit é gerada em vez de versionada porque depende do usuário e do caminho do repositório, que variam por máquina.

`instalar_bot.sh`:

```bash
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
```

- [ ] **Step 2: Verificar sintaxe e tornar executável**

Run: `bash -n instalar_bot.sh && chmod +x instalar_bot.sh && echo "sintaxe ok"`
Expected: `sintaxe ok`

- [ ] **Step 3: Commit**

```bash
git add instalar_bot.sh
git commit -m "feat: instalador do bot como servico systemd"
```

---

## Task 14: Documentação no RUNBOOK

**Files:**
- Modify: `RUNBOOK.md`

- [ ] **Step 1: Ler a estrutura atual**

Run: `grep -n '^#' RUNBOOK.md`

Siga o tom e o nível de detalhe já usados (documento operacional, para a equipe executora).

- [ ] **Step 2: Acrescentar a seção**

````markdown
## Acionar o robô pelo Telegram

O robô pode ser acionado do grupo do Telegram, sem ninguém na frente do
computador. Ele executa exatamente a mesma coisa que o duplo-clique no
`robo.bat`.

### Comandos no grupo

| Comando | O que faz |
|---------|-----------|
| `/rodar` | Executa o robô |
| `/status` | Diz se há execução em andamento |
| `/log` | Envia o log completo da última execução |
| `/ajuda` | Lista os comandos |

Depois do `/rodar` o bot manda três mensagens: o aviso de início, o resumo da
planilha e do login, e no fim o resultado linha a linha.

### Quem pode acionar

Qualquer pessoa do grupo. **Entrar no grupo é o mesmo que ganhar permissão de
aprovar e anular cota no SIAFI de produção** — não adicione ninguém sem
combinar antes. Mensagens de fora do grupo são ignoradas.

### Instalação (uma vez, na máquina do robô)

1. Crie o bot no `@BotFather` do Telegram (`/newbot`) e guarde o token.
2. Adicione o bot ao grupo da equipe.
3. Mande qualquer mensagem no grupo e abra
   `https://api.telegram.org/bot<TOKEN>/getUpdates` no navegador. Anote o
   `chat.id` (é negativo, algo como `-1001234567890`).
4. No Ubuntu, preencha as duas variáveis no `.env`:
   ```
   TELEGRAM_BOT_TOKEN=<token do BotFather>
   TELEGRAM_CHAT_ID=<id do grupo>
   ```
5. Instale o serviço:
   ```bash
   cd ~/code/splor-mg/siafi-automacao-cota
   bash instalar_bot.sh
   ```
6. No **Windows**, abra o PowerShell **como administrador** e crie a tarefa
   que acorda o WSL quando a máquina liga (sem ela o bot só sobe quando alguém
   abre um terminal do Ubuntu):
   ```powershell
   schtasks /create /tn "Robo SIAFI - acordar WSL" /tr "wsl.exe -d Ubuntu -e true" /sc onlogon /f
   ```

Depois de reiniciar o Windows é preciso **fazer login na conta do usuário**
para o WSL subir — a tarefa é `onlogon`. Se a máquina ficar na tela de login,
o bot não responde.

### Se o bot não responder

```bash
systemctl status siafi-bot     # o serviço está no ar?
journalctl -u siafi-bot -n 50  # o que ele registrou
sudo systemctl restart siafi-bot
```

Se o `systemctl` disser que o serviço não existe, o WSL provavelmente não subiu
com systemd: rode `wsl --shutdown` no Windows e abra o Ubuntu de novo.
````

- [ ] **Step 3: Commit**

```bash
git add RUNBOOK.md
git commit -m "docs: como acionar e instalar o robo pelo Telegram"
```

---

## Task 15: Verificação ponta a ponta

Não é código — é a checagem de que o conjunto funciona na máquina real.

- [ ] **Step 1: Suíte completa**

Run: `source venv/bin/activate && pytest tests/ -v`
Expected: todos passam

- [ ] **Step 2: Subir o bot em primeiro plano e conferir o arranque**

Run: `source venv/bin/activate && python siafi_automacao/bot_telegram.py`
Expected: `Bot iniciado. Grupo autorizado: -100...`

- [ ] **Step 3: No grupo, mandar `/ajuda`**

Expected: o bot responde com a lista de comandos.

- [ ] **Step 4: Mandar `/status` sem execução**

Expected: *"Nenhuma execução registrada ainda. Use /rodar."* (ou a data da última execução).

- [ ] **Step 5: Mandar um comando de um chat privado com o bot**

Expected: **nenhuma resposta**. Confirma que a autorização por grupo funciona.

- [ ] **Step 6: Testar o descarte de comando antigo — o teste mais importante**

1. Pare o bot (Ctrl+C).
2. Mande `/rodar` no grupo.
3. Espere **mais de 5 minutos**.
4. Suba o bot de novo.

Expected: o robô **não** dispara; o console mostra `[info] comando antigo descartado`.

- [ ] **Step 7: Execução real ponta a ponta**

Com planilhas de verdade na pasta de remanejamentos, mandar `/rodar`.
Expected: as três mensagens chegam ao grupo, o resultado bate com a planilha de
conferência gerada, e os valores aparecem formatados em reais.

- [ ] **Step 8: Confirmar que o `robo.bat` continua funcionando**

Duplo-clique no `robo.bat` pelo Windows.
Expected: o robô roda como antes, com a saída no console praticamente idêntica
à de hoje.

- [ ] **Step 9: Instalar como serviço e reiniciar**

Run: `bash instalar_bot.sh && systemctl status siafi-bot`
Expected: `active (running)`

Depois reinicie o Windows, faça login e mande `/status` no grupo.
Expected: o bot responde.
