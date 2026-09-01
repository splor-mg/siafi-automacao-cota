# Manual do Robô de Cotas SIAFI

Este manual ensina, passo a passo, como usar o robô. **Você não precisa saber nada de computador.** Basta seguir cada passo na ordem, do começo ao fim. Cada passo diz exatamente o que fazer.

---

## O que o robô faz

O robô entra no SIAFI sozinho, lê uma planilha do Excel com as cotas a aprovar ou anular, e faz cada operação uma por uma. No final, ele preenche a planilha dizendo o que deu certo e o que deu errado.

---

# PARTE 1 — Uso no dia a dia

> Use esta parte **depois** que o robô já estiver instalado no computador.
> Se for a **primeira vez** neste computador, vá antes para a **PARTE 2** (página mais abaixo).

## Passo 1 — Conferir se você está na rede da SEPLAG

O robô só funciona dentro da rede da SEPLAG.

- Se você está **no computador do trabalho, na SEPLAG** → tudo certo, continue.
- Se você está **em casa ou fora** → ligue a **VPN** antes de continuar.

## Passo 2 — Colocar a planilha na pasta certa

1. Abra o **OneDrive** no computador (o ícone da nuvem azul, perto do relógio).
2. Entre nas pastas, uma dentro da outra, nesta ordem:
   - `@splor`
   - `@dcmefo`
   - `2026`
   - `Robo - Remanejamento e aprovacao de cota`
   - `Remanejamentos`
3. Copie ou arraste para dentro desta pasta **o arquivo Excel** com as cotas.

> Se a sua planilha for da SEGOV, coloque na pasta `Remanejamentos (SEGOV)` em vez de `Remanejamentos`.

**Importante:** feche o arquivo Excel antes de continuar. Ele não pode estar aberto.

> ⚠️ **Confira a planilha ANTES de colocá-la nesta pasta.** Depois que o robô é
> ligado, ele vai direto para o SIAFI e aprova as cotas: **não há nenhuma
> pergunta de confirmação no meio do caminho.** A conferência é sua, e é agora.

## Passo 3 — Ligar o robô

1. Abra a pasta onde está o robô (a pasta com os arquivos que você recebeu).
2. Procure o arquivo chamado **robo** (com um ícone de engrenagem). O nome completo é `robo.bat`.
3. **Clique duas vezes seguidas** (rápido) em cima dele.

## Passo 4 — Esperar a janela preta

- Uma **janela preta** vai abrir na tela. É normal. **Não feche.**
- Dentro dela vão aparecer várias frases em letras claras. **Não precisa fazer nada**, só esperar.
- O robô está juntando todos os arquivos de remanejamento e montando a planilha de conferência.
- Em seguida ele entra no SIAFI **sozinho**. Ele não pergunta nada e não espera
  você confirmar — por isso a conferência tem que ser feita antes, no Passo 2.

## Passo 5 — Esperar o robô trabalhar

- O robô vai entrar no SIAFI e fazer cada cota, uma por uma.
- Na janela preta vão aparecer os resultados de cada linha.
- **Não mexa no computador enquanto ele trabalha.** Espere até ele terminar.

## Passo 6 — Pronto

- Quando o robô terminar, a planilha já processada é guardada sozinha na pasta:
  - `Robo - Remanejamento e aprovacao de cota` → `Conferencia arquivo robo`
- Agora você pode **fechar a janela preta**.

**Acabou.** Para rodar de novo amanhã, é só repetir a PARTE 1 desde o Passo 1.

---

# PARTE 2 — Primeira vez neste computador

> Faça esta parte **só uma vez**, na primeira vez que usar o robô em um computador novo.
> Depois disso, use sempre a PARTE 1.

A primeira instalação tem até **3 etapas**. Faça uma de cada vez, na ordem.

## Etapa A — Instalar o "motor" do robô (Ubuntu)

> Se ao clicar no robô ele já abrir a janela preta normalmente e pedir suas credenciais, **pule para a Etapa C.**

1. Abra a pasta do robô.
2. Clique duas vezes no arquivo **robo** (`robo.bat`).
3. Vai aparecer uma janela do Windows perguntando se você permite. Clique em **Sim**.
4. Na janela preta vai aparecer a frase: `Instalando WSL e Ubuntu...`
5. **Espere.** Pode demorar alguns minutos. Não feche nada.
6. No final, vai aparecer uma frase pedindo para **reiniciar o computador**.
7. Salve tudo o que estiver aberto e **reinicie o computador** (Menu Iniciar → botão de ligar → Reiniciar).

## Etapa B — Criar o usuário do Ubuntu (depois de reiniciar)

1. Depois de reiniciar, uma janela vai abrir sozinha. Ela tem fundo escuro e letras claras.
2. Ela vai pedir para criar um **nome de usuário**. Digite uma palavra simples, por exemplo `siafi`, e aperte **Enter**.

   > As letras que você digita aqui **não aparecem** na tela. É normal e proposital. Continue digitando mesmo sem ver.
3. Em seguida ela pede uma **senha**. Digite uma senha simples e **anote em um papel** para não esquecer. Aperte **Enter**.
4. Ela vai pedir para **repetir a senha**. Digite a mesma senha de novo e aperte **Enter**.
5. Quando terminar, **feche essa janela** (clique no X).

## Etapa C — Configurar o robô com suas credenciais do SIAFI

1. Abra a pasta do robô.
2. Clique duas vezes no arquivo **robo** (`robo.bat`).
3. A janela preta abre e começa a se configurar sozinha. **Espere** (pode demorar alguns minutos).
4. Em um momento, o robô vai **pedir suas credenciais do SIAFI**, uma de cada vez. Digite cada uma e aperte **Enter**:

   | Quando aparecer | Digite |
   |-----------------|--------|
   | `SISTEMA` | O nome do sistema. Normalmente: `SIAFI` |
   | `USUARIO` | O seu login do SIAFI |
   | `SENHA` | A sua senha do SIAFI *(as letras não aparecem ao digitar — é normal)* |
   | `UNIDADE_EXECUTORA` | O código da sua unidade. Exemplo: `1451` |

5. Depois que você informar tudo, o robô **já começa a funcionar sozinho**.

> A partir daí, é só usar a **PARTE 1** sempre que precisar.

---

# PARTE 3 — Acionar o robô pelo Telegram (opcional)

> Isto é uma forma alternativa de ligar o robô, sem precisar estar na frente
> do computador. Ele executa exatamente a mesma sequência do duplo-clique no
> `robo.bat`.

## Comandos no grupo

| Comando | O que faz |
|---------|-----------|
| `/cota` | Executa o robô de **cota orçamentária** |
| `/credito` | Executa o robô de **crédito** |
| `/status` | Diz se há execução em andamento, e de qual robô |
| `/log` | Envia o log completo da última execução |
| `/ajuda` | Lista os comandos |

> O comando `/rodar` **não existe mais**. Com dois robôs no mesmo grupo ele
> ficou ambíguo, e foi substituído por `/cota` e `/credito`.

Depois do comando o bot manda três mensagens no grupo: o aviso de início, o
resumo da planilha e do login, e no fim o resultado.

## Os dois robôs nunca rodam ao mesmo tempo

Cota e crédito entram no SIAFI com o **mesmo usuário**. Duas sessões
simultâneas fazem o mainframe recusar a segunda, então o robô impede: se você
pedir `/credito` enquanto o de cota está rodando, o bot responde que já há
execução em andamento e não dispara nada. Vale para os dois `.bat` também.

## Atenção especial ao `/credito`

> ⚠️ **O robô de crédito não pergunta mais nada.** Antes ele abria o
> `copia.xlsm` no Excel e esperava você digitar `s`. Isso acabou — vale tanto
> para o Telegram quanto para o duplo-clique no `robo_credito.bat`.
>
> **Confira as planilhas ANTES de colocá-las na pasta de origem.** Depois de
> acionado, o robô vai até o fim sozinho.

Aquele passo nunca foi de fato uma conferência: ele existia porque a aba `ROBO`
é montada por fórmulas que só o Excel calcula, e alguém precisava abrir o
arquivo para elas rodarem. Hoje o robô faz o Excel recalcular sozinho e confere
se a aba veio preenchida — se vier vazia, ele para antes de tocar no SIAFI.

A análise de saldo automática continua valendo: se ela reprovar, o robô para e
**nenhuma solicitação é enviada ao SIAFI**. Nesse caso a mensagem do grupo diz
*"interrompido"*, e não *"FALHOU"*.

> Quando o robô é acionado pelo Telegram, **nenhuma janela do SIAFI aparece na
> tela** — ele trabalha por baixo dos panos. Isso é proposital: assim funciona
> mesmo com o computador bloqueado. Pelo `robo.bat`, a janela continua
> aparecendo normalmente.

## Funciona com o computador bloqueado?

Sim. Bloquear a tela (`Win+L`) não desconecta você: o robô continua acessível
pelo Telegram e executa normalmente.

O que **não** pode acontecer é o computador desligar ou reiniciar. Depois de um
reinício, alguém precisa **fazer login no Windows** para o robô voltar ao ar
(veja o passo 6 da instalação). Bloquear é diferente de reiniciar — bloquear
não atrapalha.

## Duas execuções nunca acontecem ao mesmo tempo

Se alguém der `/rodar` enquanto o robô já está em andamento — pelo Telegram ou
por duplo-clique no `robo.bat` — o bot responde que já existe execução e
**não** dispara uma segunda. Vale o contrário também: se o `robo.bat` for
acionado enquanto o bot está executando, a janela preta avisa e não roda.
Deixar duas execuções mexerem na mesma cota ao mesmo tempo bagunçaria o
resultado, então o robô sempre recusa a segunda.

## Se uma execução travar

O bot **não mata** uma execução travada sozinha. Interromper o robô no meio da
aprovação de cotas deixaria linhas em estado indefinido no SIAFI — pior do que
esperar. Use `/status` para ver há quanto tempo a execução está rodando. Se
for mesmo preciso interromper, isso é decisão de quem entende do assunto,
feita manualmente no servidor, não pelo grupo do Telegram.

## Onde ficam os logs

Cada execução grava um arquivo em `data/logs/`, dentro da pasta do robô no
Ubuntu. O `/log` envia o da execução mais recente — é essa informação que a
equipe deve passar para quem estiver dando suporte.

Os logs se apagam sozinhos depois de **30 dias**. A limpeza acontece no começo
de cada execução, então não há nada a fazer manualmente. Para mudar o prazo,
ajuste `LOG_RETENCAO_DIAS` no `.env` (não precisa reiniciar o serviço — quem lê
essa variável é o `rodar.sh`, a cada execução).

## Quem pode acionar

Mensagens de fora do grupo são sempre ignoradas. Dentro do grupo, há duas
configurações possíveis:

**Sem lista de pessoas** (`TELEGRAM_USUARIOS_AUTORIZADOS` vazio no `.env`):
qualquer pessoa do grupo aciona. **Entrar no grupo é o mesmo que ganhar
permissão de aprovar e anular cota no SIAFI de produção** — não adicione
ninguém sem combinar antes.

**Com lista de pessoas:** só quem está na lista pode dar `/rodar`. Os demais
membros continuam usando `/status`, `/log` e `/ajuda` normalmente — eles
acompanham o resultado, mas não disparam. Quem não está na lista e tenta
`/rodar` recebe uma resposta explicando, e nada acontece.

Para montar a lista, descubra o id de cada pessoa: peça para ela mandar uma
mensagem no grupo e abra `https://api.telegram.org/bot<TOKEN>/getUpdates` —
o número está em `"from":{"id": ...}`. Depois preencha no `.env`, separando por
vírgula, e reinicie o serviço:

```bash
# no .env
TELEGRAM_USUARIOS_AUTORIZADOS=1296210429,987654321

sudo systemctl restart siafi-bot
```

## Instalação (uma vez, na máquina do robô)

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

## Depois de atualizar o código do robô

O robô se atualiza sozinho: o `rodar.sh` dá `git pull` antes de cada execução.
O **bot** não — ele carrega o código dele uma vez só, quando o serviço sobe.

Por isso, se a mudança for em `bot_telegram.py`, `telegram_mensagens.py` ou
`relato.py`, é preciso reiniciar o serviço:

```bash
sudo systemctl restart siafi-bot
```

Mudanças em `login.py`, `consolida.py`, `fluxo_aprovar.py`, `fluxo_anular.py`
ou `rodar.sh` valem na execução seguinte, sem reiniciar nada.

> A armadilha: um `git pull` (feito pelo próprio robô numa execução) atualiza
> os arquivos do bot no disco, mas o bot continua rodando a versão antiga até
> alguém reiniciar. O disco fica novo e o comportamento fica velho.

## Se o bot não responder

```bash
systemctl status siafi-bot     # o serviço está no ar?
journalctl -u siafi-bot -n 50  # o que ele registrou
sudo systemctl restart siafi-bot
```

Se o `systemctl` disser que o serviço não existe, o WSL provavelmente não subiu
com systemd: rode `wsl --shutdown` no Windows e abra o Ubuntu de novo.

---

# O que significa a coluna "Progresso"

Quando o robô termina, ele escreve o resultado de cada linha na coluna **Progresso** da planilha:

| O que está escrito | O que significa |
|--------------------|-----------------|
| `Ok` | Deu tudo certo |
| `Saldo zerado na conta` | Não tinha saldo para fazer a operação |
| `Valor a anular maior que o saldo disponível` | O valor pedido é maior que o saldo |
| `Valor a aprovar maior que o saldo disponível` | Não tinha saldo suficiente para aprovar |
| `Proj/Ativ ou Fonte/Proc./IAG inexistente para a UO` | Uma classificação não foi encontrada |
| `Grupo de despesa inexistente` | O grupo de despesa está errado |
| `Elemento/item não marcado para a UO beneficiada` | Faltou uma marcação no elemento/item |
| `Linha sem GLOBAL/AMARRADO definido` | A linha da planilha está sem o tipo |
| `INTERROMPIDA - VERIFICAR NO SIAFI` | **Exige ação sua.** Veja abaixo. |

## Se aparecer `INTERROMPIDA - VERIFICAR NO SIAFI`

O robô parou no meio dessa linha e **não sabe se a operação entrou no SIAFI**.

Nesse caso ele *não* deixa a linha em branco de propósito: linha em branco seria
reprocessada na próxima execução, e se a operação já tivesse entrado, ela seria
feita **duas vezes**.

O que fazer:

1. Consulte no SIAFI se aquela cota foi mesmo aprovada ou anulada.
2. **Se entrou:** deixe como está (ou escreva `Ok`). Não rode de novo essa linha.
3. **Se não entrou:** apague o conteúdo da coluna `Progresso` dessa linha. Ela
   volta para a fila e o robô a processa na próxima execução.

> As linhas que já tinham a coluna Progresso preenchida são **puladas**. O robô só faz as que ainda estão em branco.

---

# Quando algo dá errado

## A janela preta fechou sozinha, sem dizer nada

- Provavelmente o arquivo Excel estava aberto. **Feche o Excel** e tente de novo.
- Ou a planilha não está na pasta certa. Confira a pasta no Passo 2 da PARTE 1.

## Apareceu "Nao foi possivel estabelecer conexao com o servidor"

O robô não conseguiu entrar no SIAFI. Confira:
- Você está na rede da SEPLAG ou com a VPN ligada?
- O SIAFI está funcionando no seu navegador?

Feche a janela preta e tente de novo desde o Passo 3.

## Apareceu "Nao foi possivel fazer login apos varias tentativas"

Sua senha do SIAFI pode ter mudado. Peça para o **suporte técnico da DCMEFO** atualizar a senha do robô.

## Apareceu "ERRO: setup.sh falhou"

Deu um problema na primeira instalação. Pode ser falta de internet. Chame o **suporte técnico da DCMEFO**.

## Qualquer outra coisa

Não tente adivinhar. Tire uma **foto da tela** (ou print) e mande para o **suporte técnico da DCMEFO/SEPLAG**.

---

**Dúvidas?** Fale com a equipe técnica da DCMEFO/SEPLAG.
