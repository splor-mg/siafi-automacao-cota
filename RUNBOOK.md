# Runbook — Robô de Aprovação e Anulação de Cotas SIAFI

Guia operacional para a área executora. Não é necessário conhecimento técnico para seguir este documento.

---

## O que o robô faz

O robô acessa o SIAFI automaticamente, lê uma planilha Excel com as operações pendentes e executa a aprovação ou anulação de cotas orçamentárias linha a linha. Ao final, devolve a planilha preenchida com o resultado de cada operação.

---

## Pré-requisitos

Antes de usar o robô pela primeira vez, confirme que você tem:

- [ ] Windows 10 ou Windows 11
- [ ] Acesso à internet (necessário apenas na configuração inicial)
- [ ] Suas credenciais de acesso ao SIAFI (sistema, usuário, senha e unidade executora)
- [ ] A planilha Excel com as operações a processar, salva na pasta correta do OneDrive

> **Atenção:** O robô acessa o SIAFI pela rede da SEPLAG. Certifique-se de estar conectado à rede institucional ou à VPN antes de executar.

---

## Como usar

### Uso diário (sistema já configurado)

1. Coloque a planilha Excel na pasta do OneDrive:
   ```
   @splor/@dcmefo/2026/Robo - Remanejamento e aprovacao de cota/Robo (IPU 2)/Python
   ```

2. Dê **duplo-clique** em `robo.bat`

3. Uma janela preta abre e o robô inicia automaticamente

4. Quando solicitado, confirme se deseja continuar digitando `s` e pressionando Enter

5. Aguarde. O robô processa cada linha da planilha e exibe o resultado na tela

6. Ao terminar, a planilha é movida automaticamente para a pasta de conferência:
   ```
   @splor/@dcmefo/2026/Robo - Remanejamento e aprovacao de cota/Conferencia arquivo robo
   ```

---

## Primeira execução (configuração inicial)

Na primeira vez que o robô for usado em uma máquina nova, ele instala automaticamente o ambiente necessário. Siga os passos abaixo.

### Passo 1 — Instalar o WSL (somente se necessário)

> Se ao dar duplo-clique em `robo.bat` o robô abrir normalmente, pule para o **Passo 3**.

1. Dê duplo-clique em `robo.bat`
2. Uma janela de permissão do Windows aparece — clique em **Sim**
3. A janela preta mostra a mensagem: `Instalando WSL e Ubuntu...`
4. Aguarde a conclusão (pode levar alguns minutos)
5. Ao final, a mensagem pede para **reiniciar o computador**
6. Salve tudo o que estiver aberto e reinicie o Windows

### Passo 2 — Configurar o Ubuntu (após o reboot)

1. Após reiniciar, uma janela do Ubuntu abre automaticamente
2. O Ubuntu pede para criar um **nome de usuário** (pode ser qualquer nome, ex: `siafi`)
3. Em seguida pede uma **senha** — escolha qualquer senha e memorize
4. Feche essa janela

### Passo 3 — Configuração do robô (somente na primeira vez)

1. Dê duplo-clique em `robo.bat`
2. O robô detecta que é a primeira execução e inicia a configuração automática:
   - Instala as ferramentas necessárias (pode demorar alguns minutos)
   - Faz o download do código do robô
3. Quando solicitado, informe suas **credenciais do SIAFI**:

   | Campo | O que informar |
   |-------|---------------|
   | `SISTEMA` | Nome do sistema (ex: `SIAFI`) |
   | `USUARIO` | Seu login do SIAFI |
   | `SENHA` | Sua senha do SIAFI *(não aparece na tela ao digitar)* |
   | `UNIDADE_EXECUTORA` | Código da sua UE (ex: `1451`) |

4. Após informar as credenciais, o robô já inicia automaticamente

> A partir daí, nas próximas execuções basta dar duplo-clique em `robo.bat`.

---

## Coluna "Progresso" na planilha

Ao final da execução, a coluna **Progresso** de cada linha é preenchida com o resultado:

| Resultado | Significado |
|-----------|-------------|
| `Ok` | Operação realizada com sucesso |
| `Saldo zerado na conta` | Saldo insuficiente para a operação |
| `Valor a anular maior que o saldo disponível` | Valor solicitado excede o saldo |
| `Valor a aprovar maior que o saldo disponível` | Saldo insuficiente para aprovar |
| `Proj/Ativ ou Fonte/Proc./IAG inexistente para a UO` | Classificação não encontrada |
| `Grupo de despesa inexistente` | Grupo de despesa inválido |
| `Elemento/item não marcado para a UO beneficiada` | Elemento/item sem marcação |
| `Linha sem GLOBAL/AMARRADO definido` | Linha da planilha sem tipo definido |

Linhas que já tinham a coluna Progresso preenchida são **ignoradas** — o robô processa apenas as pendentes.

---

## Solução de problemas

### "Não foi possível estabelecer conexão com o servidor"

O robô não conseguiu se conectar ao SIAFI. Verifique:
- Você está na rede institucional ou VPN?
- O SIAFI está acessível pelo seu navegador?

O robô tentará reconectar automaticamente. Se o problema persistir, feche e abra `robo.bat` novamente.

---

### "Não foi possível fazer login após várias tentativas"

As credenciais do SIAFI podem estar incorretas. Verifique se sua senha não mudou desde a última execução.

Para atualizar as credenciais, peça suporte técnico para editar o arquivo `.env` na pasta do robô dentro do Ubuntu.

---

### A janela fecha imediatamente sem mensagem de erro

Pode ser que a planilha não esteja na pasta correta do OneDrive, ou que o nome do arquivo tenha sido alterado. Verifique se o arquivo `.xlsx` está na pasta:
```
@splor/@dcmefo/2026/Robo - Remanejamento e aprovacao de cota/Robo (IPU 2)/Python
```
E que o arquivo não está com o Excel aberto (feche antes de executar o robô).

---

### A janela do x3270 (terminal verde) não abre

O robô precisa do WSLg para exibir a janela gráfica. Isso funciona automaticamente no Windows 11. Se estiver no Windows 10, a janela pode não aparecer — o robô ainda funciona, mas sem exibição visual.

---

### "ERRO: setup.sh falhou"

Ocorreu um problema durante a configuração inicial. Possíveis causas:
- Sem acesso à internet
- O repositório do robô está privado e o token de acesso expirou

Entre em contato com o suporte técnico.

---

## Suporte

Em caso de dúvidas ou problemas não cobertos acima, entre em contato com a equipe técnica da DCMEFO/SEPLAG.
