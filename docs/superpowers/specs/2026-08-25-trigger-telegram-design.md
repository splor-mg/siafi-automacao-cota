# Trigger via Telegram para o robô SIAFI

**Data:** 2026-08-25
**Status:** aprovado, pronto para plano de implementação

## Problema

Hoje o robô só é acionado por duplo-clique no `robo.bat`, presencialmente na
máquina Windows onde o WSL está configurado. Queremos acionar a mesma execução
remotamente, a partir de um grupo do Telegram, e acompanhar o andamento por lá.

## Restrições que moldam a solução

- O robô depende da pasta do OneDrive montada em `/mnt/c/...` e do acesso de
  rede ao SIAFI. **Só roda naquela máquina Windows específica** — nuvem está
  descartada (a branch `rodar_no_actions` já esbarrou nisso).
- A máquina fica ligada continuamente, então um processo escutando o Telegram
  24/7 é viável.
- `login.py` já é totalmente não-interativo: não abre o Excel nem pede
  confirmação `s`/`n`. Pode rodar sem ninguém na frente do PC.
- O WSL não inicia sozinho no boot do Windows: ele só acorda quando algo o
  invoca. Precisa de um gatilho no lado Windows.

## Decisões de arquitetura

**Bot em long-polling, rodando como serviço systemd dentro do WSL.**

Long-polling (`getUpdates`) em vez de webhook: dispensa IP público, porta
aberta e túnel. A máquina da SEPLAG não fica exposta à internet.

systemd em vez de Tarefa Agendada segurando o processo: o systemd já está
ativo neste WSL (`/etc/wsl.conf` tem `systemd=true`, PID 1 é systemd), dá
restart automático em caso de queda e logs via `journalctl`. A Tarefa Agendada
do Windows fica só com o papel de acordar a distro no boot.

Serviço externo (n8n, Zapier) com túnel foi descartado: expõe a máquina, cria
dependência de terceiro e resolve um problema que não temos.

## Componentes

### 1. `rodar.sh` (novo)

Encapsula exatamente a Fase 3 do `robo.ps1` (hoje nas linhas 148-156):

```
git checkout main && git pull origin main   # falha => avisa e segue local
source venv/bin/activate
python siafi_automacao/login.py
```

Responsabilidades adicionais:

- `flock -n` sobre um lockfile, para impedir duas execuções simultâneas. Se o
  lock estiver tomado, sai imediatamente com código dedicado (ver Contratos).
- Grava o log completo (stdout + stderr) em
  `data/logs/robo-AAAAMMDD-HHMMSS.log`.

**Passa a ser a única fonte de verdade da sequência de execução.** O
`robo.ps1` é alterado para chamá-lo em vez de repetir os comandos inline.
Assim o duplo-clique no `robo.bat` e o `/rodar` no Telegram percorrem
literalmente o mesmo caminho.

### 2. `siafi_automacao/relato.py` (novo)

Módulo minúsculo que separa "mensagem destinada ao usuário" de "saída de
diagnóstico".

- `relato(texto, tipo=...)` imprime no stdout (para o console do `robo.bat`
  continuar idêntico ao de hoje) **e** grava uma linha estruturada em
  `data/logs/relato-AAAAMMDD-HHMMSS.jsonl`.
- O bot lê o arquivo de relato; nunca o stdout bruto.
- `formatar_valor(v)` — converte o inteiro em centavos da planilha para
  `R$ 74.000,00`. Isolada e com teste unitário, porque erro de formatação de
  valor é silencioso e exibe número errado para quem aprova cota.

**Por que não filtrar o stdout por regex no bot:** filtro quebra em silêncio a
cada mudança de mensagem, e um `print()` de debug futuro vazaria para o grupo.
O contrato explícito no código é a fronteira certa.

Cerca de 20 dos 70 `print()` do repositório são convertidos para `relato()` —
os que compõem o relato do usuário (validação da planilha, login, cada linha
processada, retorno do SIAFI, fluxo finalizado, erros de resgate). Os demais
(tentativas de tela, caminhos absolutos, avisos internos) continuam `print()` e
vão só para o log.

O contador final (`4 linhas · 2 efetuadas · 2 puladas · 0 com erro`) **não
existe hoje** no `login.py` — é um evento de relato novo, emitido ao fim do
laço de processamento e também impresso no console.

### 3. `siafi_automacao/bot_telegram.py` (novo)

Loop de long-polling usando `requests` — única dependência nova. Nada de
framework assíncrono: o estilo do repositório é procedural e direto.

Comandos:

| Comando  | Efeito |
|----------|--------|
| `/rodar` | Dispara a execução |
| `/status`| Diz se há execução em andamento (e há quantos minutos) e quando foi a última |
| `/log`   | Envia o arquivo de log completo da última execução |
| `/ajuda` | Lista os comandos |

O `rodar.sh` é disparado numa thread, para o polling continuar respondendo
`/status` durante os minutos de execução.

### 4. `siafi-bot.service` (novo)

Unit do systemd em `/etc/systemd/system/`, com `Restart=always`,
`RestartSec=10` e `WantedBy=multi-user.target`. Sobe junto com o WSL.

### 5. Tarefa Agendada do Windows

No boot, executa `wsl.exe -d Ubuntu -e true` para acordar a distro — e com ela
o systemd e o bot.

## Configuração

Duas variáveis novas no `.env` (já coberto pelo `.gitignore`):

- `TELEGRAM_BOT_TOKEN` — token do bot, obtido no @BotFather
- `TELEGRAM_CHAT_ID` — id do grupo autorizado

Ambas entram no `.env.example` e na coleta interativa do `setup.sh`, que só
pergunta o que está faltando.

## Fluxo de uma execução

1. Alguém digita `/rodar` no grupo.
2. O bot confere o `chat_id`. Se não for o grupo autorizado, **ignora em
   silêncio** — não responde nada, nem "não autorizado", para não confirmar a
   existência do bot a quem o encontrou por acaso.
3. Confere o lock. Se ocupado: *"Já tem execução em andamento desde 14:32,
   iniciada por Fulano"*.
4. Responde a mensagem de início e registra no log quem acionou.
5. Dispara o `rodar.sh` em thread.
6. Publica as mensagens de progresso e a final (ver Formato do retorno).

## Formato do retorno

Três mensagens, nos marcos naturais — a execução leva minutos e mandar tudo só
no fim deixa o grupo no escuro.

**Início:**

```
Robô SIAFI · iniciado
por Guilherme · 25/08 às 14:32
```

**Após consolidação e login:**

```
1 planilha lida, validação OK (4 linhas)
Login no SIAFI realizado
4 linha(s) pendente(s): 2, 3, 4, 5
```

**Final:**

```
Robô SIAFI · concluído em 3min12s

Linha 2 · pulada (IAG 1)
Linha 3 · pulada (IAG 1)
Linha 4 · aprovação · UO 1261 · Ação 4511 · Fonte 10 · R$ 74.000,00
   0011-REGISTRO EFETUADO
Linha 5 · aprovação · UO 1261 · Ação 2128 · Fonte 10 · R$ 500.000,00
   0011-REGISTRO EFETUADO

4 linhas · 2 efetuadas · 2 puladas · 0 com erro
Planilha: Conferencia arquivo robo 25.08.xlsx
```

Decisões de formato:

- O bloco das linhas vai em `<pre>` (HTML do Telegram), monoespaçado, para as
  colunas alinharem no celular.
- `Processando linha 4 | ...` e `realizando procedimento de aprovação` viram
  uma linha só: no celular linha longa quebra mal, e "realizando procedimento"
  repetido a cada linha não informa nada que o resto não diga.
- Valores em centavos, formatados como reais (`7400000` → `R$ 74.000,00`).
- Ficam de fora do Telegram (vão só para o log): `Texto encontrado`,
  `Tentativa N - tela intermediária`, caminhos absolutos, warnings do openpyxl
  (que já saem em stderr).
- O ruído de `CMD.EXE ... Não há suporte para caminhos UNC` não existe neste
  caminho — é artefato do `robo.bat` sendo executado de um caminho
  `\\wsl.localhost\...`. Correção do `robo.bat` fica fora do escopo.

**Limite de tamanho.** O Telegram corta em 4096 caracteres. Se a execução tiver
muitas linhas, a mensagem final traz o resumo e **todas as linhas com erro**,
omitindo as bem-sucedidas com um aviso *"…+38 linhas efetuadas (veja /log)"*.

**Em caso de erro** a mensagem final traz o bloco parcial, a linha onde parou e
a confirmação de que a planilha foi resgatada para a pasta de conferência
(`resgatar_planilha`, `login.py:148`). O trecho de log anexado passa por um
filtro que redige qualquer ocorrência da senha do SIAFI antes de sair.

## Tratamento de erros

| Falha | Comportamento |
|-------|---------------|
| Bot cai | systemd reinicia (`Restart=always`, `RestartSec=10`) |
| Máquina reinicia | Tarefa Agendada acorda o WSL no boot |
| `git pull` falha | Mesmo de hoje (`robo.ps1:150-152`): avisa e roda a versão local |
| Telegram/rede fora | Loop com backoff exponencial; o processo não morre |
| Execução já em andamento | `flock -n` retorna na hora; o bot avisa quem pediu |
| `login.py` trava no SIAFI | **Não há kill automático.** O `/status` informa há quantos minutos está rodando |

**Por que não matar por timeout:** interromper no meio da aprovação de cotas
deixaria linhas em estado indefinido no SIAFI. Isso é decisão humana.

## Segurança

- Autorização por `chat_id` do grupo. Mensagens de qualquer outro chat são
  descartadas sem resposta. Comandos vindos de bots e edições de mensagem são
  ignorados.
- Token só no `.env`, nunca no git.
- **Offset persistido** em `data/.telegram_offset`. Sem isso, o Telegram
  reentrega mensagens não confirmadas quando o bot reinicia — e o robô
  dispararia sozinho, aprovando cota sem ninguém ter pedido. Além do offset, no
  arranque o bot descarta qualquer update com mais de 5 minutos de idade.
- O tail de log enviado ao grupo passa pelo filtro de redação de senha.

### Risco aceito

Com `/rodar` num grupo, **pertencer ao grupo passa a ser o único controle** para
disparar aprovação e anulação de cota orçamentária no SIAFI de produção, sem
revisão prévia da planilha. Quem for adicionado ao grupo ganha esse poder
imediatamente, e a conta do SIAFI usada é sempre a do `.env`.

Mitigações: manter o grupo fechado, combinar antes de adicionar alguém, e o log
de execução registra quem acionou. Risco registrado e aceito pelo dono do
projeto.

## Testes

**Unitários (sem rede, sem SIAFI):**

- `formatar_valor()` — centavos, zero, valores grandes, negativos
- Autorização — chat autorizado, chat estranho, mensagem de bot, edição
- Montagem da mensagem final — caso normal, caso com erro, caso acima de 4096
  caracteres (verifica que linhas com erro sobrevivem à poda)
- Redação de senha no trecho de log

**Integração:**

- `flock` — dois `rodar.sh` simultâneos com um comando falso no lugar do
  `login.py`; o segundo sai com o código de "ocupado"
- Descarte de update antigo no arranque

**Manual:**

- `/rodar`, `/status`, `/log` e `/ajuda` no grupo real, ponta a ponta
- Reiniciar o serviço no meio de uma execução e confirmar que o robô **não**
  redispara

## Contratos entre componentes

- `rodar.sh` → códigos de saída: `0` sucesso, `10` já em execução (lock),
  demais códigos propagados do `login.py`.
- `relato.py` → arquivo `.jsonl`, uma entrada por evento, com `tipo`,
  `timestamp` e campos próprios do tipo. O bot depende só desse formato, não do
  texto das mensagens.
- `bot_telegram.py` → não conhece o interior do `login.py`; fala apenas com
  `rodar.sh` (processo) e com o arquivo de relato.

## Fora de escopo

- Corrigir o ruído de UNC do `robo.bat`
- Agendamento automático (cron) da execução
- Qualquer alteração na lógica de navegação no SIAFI
