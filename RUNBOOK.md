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

## Passo 3 — Ligar o robô

1. Abra a pasta onde está o robô (a pasta com os arquivos que você recebeu).
2. Procure o arquivo chamado **robo** (com um ícone de engrenagem). O nome completo é `robo.bat`.
3. **Clique duas vezes seguidas** (rápido) em cima dele.

## Passo 4 — Esperar a janela preta

- Uma **janela preta** vai abrir na tela. É normal. **Não feche.**
- Dentro dela vão aparecer várias frases em letras claras. **Não precisa fazer nada**, só esperar.
- O robô está juntando todos os arquivos de remanejamento e montando a planilha de conferência.

## Passo 5 — Conferir a planilha no Excel

1. Sozinho, o **Excel vai abrir** com a planilha de conferência.
2. **Olhe a planilha com calma.** Confira se as cotas estão certas.
3. Quando terminar de conferir, **feche o Excel** (clique no X no canto da janela do Excel).

## Passo 6 — Confirmar para o robô começar

1. Volte para a **janela preta**.
2. Vai aparecer uma pergunta pedindo para confirmar.
3. Aperte a tecla **`s`** no teclado.
4. Aperte a tecla **`Enter`**.

## Passo 7 — Esperar o robô trabalhar

- O robô vai entrar no SIAFI e fazer cada cota, uma por uma.
- Na janela preta vão aparecer os resultados de cada linha.
- **Não mexa no computador enquanto ele trabalha.** Espere até ele terminar.

## Passo 8 — Pronto

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
