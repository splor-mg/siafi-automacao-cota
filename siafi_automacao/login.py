import os
import shutil
from dotenv import load_dotenv
from py3270 import Emulator
from datetime import datetime
import pandas as pd
import openpyxl
import time
from fluxo_anular import anular
from fluxo_aprovar import aprovar

load_dotenv()
sistema = os.getenv('SISTEMA')
usuario = os.getenv('USUARIO')
senha = os.getenv('SENHA')
unidade_executora = os.getenv('UNIDADE_EXECUTORA')

month = datetime.today().strftime("%m")

# Definição dos CAMINHOS
# Caminho original no OneDrive — apenas leitura, nunca será modificado
CAMINHO_ONEDRIVE  = '/mnt/c/Users/x70167581686/OneDrive - CAMG/General/@dcmefo/2026/Robo - Remanejamento e aprovacao de cota/Robo (IPU 2)/copia.xlsx'

# Cópia local de trabalho — onde o robô vai ler e salvar durante a execução... ele é criado a partir do original do OneDrive e só é salvo no final, para evitar conflitos de acesso com o OneDrive
CAMINHO_LOCAL     = 'data/copia.xlsx'

# Destino final no OneDrive — arquivo de conferência gerado ao final
CAMINHO_DESTINO   = '/mnt/c/Users/x70167581686/OneDrive - CAMG/General/@dcmefo/2026/Robo - Remanejamento e aprovacao de cota/Conferencia arquivo robo/Conferencia arquivo robo.xlsx'

#Nome da aba na planilha Excel onde estão os dados a serem processados
SHEET_NAME = 'Remanejamento Cota Orçamentaria'

# -----------------------------------------------------------------------
# ETAPA 1: copia o original do OneDrive para o caminho local de trabalho.
# O OneDrive não será mais tocado até o final do processamento.
# A pasta local é criada automaticamente se não existir.
# -----------------------------------------------------------------------
os.makedirs(os.path.dirname(CAMINHO_LOCAL), exist_ok=True)
shutil.copy2(CAMINHO_ONEDRIVE, CAMINHO_LOCAL)
print(f"Arquivo copiado para trabalho local: {CAMINHO_LOCAL}")

# -----------------------------------------------------------------------
# ETAPA 2: garante que a pasta de destino no OneDrive existe.
# Se a pasta "Conferencia arquivo robo" ainda não foi criada, ela é criada aqui.
# -----------------------------------------------------------------------
os.makedirs(os.path.dirname(CAMINHO_DESTINO), exist_ok=True)

em = Emulator(visible=True) ##caso queira que a tela apareça utilize visible=True
em.connect('bhmvsb.prodemge.gov.br')
em.wait_for_field()

# Preenche os dados de login
em.fill_field(19, 13, sistema, 7)
em.fill_field(20, 13, usuario, 7)
em.fill_field(21, 13, senha, 7)
em.send_enter()

# Loop: navega pelas telas até encontrar a mensagem de sucesso
max_tentativas = 10
tentativas = 0

while tentativas < max_tentativas:
    time.sleep(1)

    try:
        em.send_enter()

        # Tela COM campo editável — verifica se é a tela de sucesso
        if em.string_found(1, 13, 'Logon executado com sucesso'):
            print("Login realizado com sucesso!")
            break

        else:
            # Tela com campo editável, mas ainda não é a de sucesso
            print(f"Tentativa {tentativas + 1} - tela intermediária, avançando...")
            em.send_enter()

    except:
        print(f"Tentativa {tentativas + 1} - tela de aviso detectada, passando...")
        em.send_enter()

    tentativas += 1

if tentativas == max_tentativas:
    print("Não foi possível fazer login após várias tentativas.")
    em.terminate()

em.fill_field(1, 2, sistema, 4)
em.send_enter()

##nova tela buscando login...
max_tentativas = 10
tentativas = 0

while tentativas < max_tentativas:
    time.sleep(1)

    try:
        em.send_enter()

        # Tela COM campo editável — verifica se é a tela de sucesso
        if em.string_found(22, 11, 'Unidade Executora'):
            print("Texto encontrado")
            break

        else:
            # Tela com campo editável, mas ainda não é a de sucesso
            print(f"Tentativa {tentativas + 1} - tela intermediária, avançando...")
            em.send_enter()

    except:
        # Tela SEM campo editável — é a tela de aviso, só dá Enter e segue
        print(f"Tentativa {tentativas + 1} - tela de aviso detectada, passando...")
        em.send_enter()

    tentativas += 1

if tentativas == max_tentativas:
    print("Não foi possível fazer login após várias tentativas.")
    em.terminate()

#Entrar com a Unidade Executora
em.fill_field(22, 30, unidade_executora, 7)
em.send_enter()
em.wait_for_field()
# Fim do login

#Entrar em 03 - Movimentacao Orcamentaria
em.fill_field(21, 19, '03', 2)
em.send_enter()
em.wait_for_field()

#Entrar em 02 - Aprovacao de Cota Orcamentaria
em.fill_field(21, 19, '02', 2)
em.send_enter()
em.wait_for_field()

# Leitura da planilha e processamento dos dados

# -----------------------------------------------------------------------
# ETAPA 3: leitura da cópia LOCAL (não do OneDrive)
# -----------------------------------------------------------------------
df = pd.read_excel(CAMINHO_LOCAL, sheet_name=SHEET_NAME)
df = df.dropna(how='all')  # remove linhas completamente vazias
df = df.sort_values(by=['Anular', 'UO_COD'], ascending=[True, True]) # ordena por anulação e depois por UO
df = df.reset_index(drop=False)

# Garante que a coluna 'Progresso' existe no DataFrame.
# Se a planilha já tiver a coluna de uma execução anterior, ela é mantida.
# Se não tiver, é criada vazia para receber os retornos desta execução.
df['Progresso'] = df['Progresso'].astype(str) if 'Progresso' in df.columns else ''
df['Progresso'] = df['Progresso'].astype(object)

# O loop agora usa "for idx, row" em vez de "for _, row".
# O idx é o índice real da linha no DataFrame e é necessário para que o
# df.at[idx, 'Progresso'] grave o retorno na linha correta em memória.
for idx, row in df.iterrows():
    data_row = {}
    data_row['month']   = month
    data_row['uo']      = str(int(row['UO_COD']))
    data_row['grupo']   = str(int(row['Grupo']))
    data_row['iag']     = str(int(row['IAG']))
    data_row['fonte']   = str(int(row['Fonte']))
    data_row['procedencia'] = str(int(row['IPU']))
    data_row['acao'] = str(int(row['Ação']))
    data_row['tipo_global'] = row['GLOBAL'] if pd.notna(row['GLOBAL']) else '0'
    data_row['tipo_amarrado'] = str(int(row['AMARRADO'])) if pd.notna(row['AMARRADO']) else '0'
    data_row['uo_financiadora'] = str(int(row['UO Financiadora'])) if pd.notna(row['UO Financiadora']) else '0'
    if pd.notna(row['AMARRADO']):
        amarrado = str(int(row['AMARRADO']))
        data_row['elemento'] = amarrado[:2]   # dois primeiros digitos
        data_row['item'] = amarrado[2:]       # dois ultimos digitos
    else:
        data_row['elemento'] = '0'
        data_row['item'] = '0'
    data_row['valor_anulacao'] = int(round(float(row['Anular']), 2) * 100) if pd.notna(row['Anular']) else 0
    data_row['valor_aprovacao'] = int(round(float(row['Aprovar']), 2) * 100) if pd.notna(row['Aprovar']) else 0

    ##Definição do valor a ser preenchido, dependendo se é anulação ou aprovação
    if pd.notna(row['Anular']):
        data_row['valor'] = int(round(float(row['Anular']), 2) * 100)
    else:
        data_row['valor'] = int(round(float(row['Aprovar']), 2) * 100)

    # 'retorno' é inicializado vazio antes de cada linha para evitar que,
    # em caso de erro inesperado, o retorno de uma linha anterior seja
    # gravado incorretamente na linha atual.
    retorno = ''

    if data_row['valor_anulacao'] != 0:
        print(f"realizando procedimento de anulação")
    elif data_row['valor_aprovacao'] != 0:
        print(f"realizando procedimento de aprovação")

    if data_row['tipo_global'] == 'x':
        print(f"Processando UO: {data_row['uo']}, Grupo: {data_row['grupo']}, Acao: {data_row['acao']}, Fonte: {data_row['fonte']}, Procedencia: {data_row['procedencia']}, Valor: {data_row['valor']}")
    elif data_row['tipo_amarrado'] != '0':
        print(f"Processando UO: {data_row['uo']}, Grupo: {data_row['grupo']}, Acao: {data_row['acao']}, Fonte: {data_row['fonte']}, Procedencia: {data_row['procedencia']}, Valor: {data_row['valor']}")

    # -------------------- exemplo para orquestrar o fluxo --------------------
    # aqui você pode inspecionar o data_row e decidir se é anulação ou aprovação, global ou amarrado, e então chamar as funções correspondentes

    if data_row['valor_anulacao'] != 0:
        retorno = anular(em, data_row)
    elif data_row['valor_aprovacao'] != 0:
        retorno = aprovar(em, data_row)

    # Grava o retorno do SIAFI na coluna 'Progresso' do DataFrame em memória,
    # na linha correspondente (idx). Nenhum arquivo é aberto ou salvo aqui —
    # tudo fica em RAM até o fim do loop, evitando conflitos com o OneDrive.
    df.at[idx, 'Progresso'] = retorno
    print(f"Progresso gravado em memória — linha {idx}: {retorno}")

print('Fluxo finalizado — salvando planilha...')

# -----------------------------------------------------------------------
# ETAPA 4: salva o DataFrame processado na cópia local.
# O arquivo local recebe todos os dados incluindo a coluna Progresso.
# - mode='a'                  → abre a planilha existente sem apagar outras abas
# - if_sheet_exists='overlay' → sobrescreve apenas a aba alvo
# - index=False               → não grava o índice do DataFrame como coluna
# -----------------------------------------------------------------------
with pd.ExcelWriter(CAMINHO_LOCAL, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
    df.to_excel(writer, sheet_name=SHEET_NAME, index=False)

print(f"Planilha salva localmente: {CAMINHO_LOCAL}")

# -----------------------------------------------------------------------
# ETAPA 5: copia o arquivo local processado para o destino no OneDrive,
# já com o novo nome "Conferencia arquivo robo.xlsx".
# O original em "Robo (IPU 2)/copia.xlsx" permanece intacto.
# -----------------------------------------------------------------------
shutil.copy2(CAMINHO_LOCAL, CAMINHO_DESTINO)
print(f"Arquivo de conferência salvo no OneDrive: {CAMINHO_DESTINO}")

em.terminate()
