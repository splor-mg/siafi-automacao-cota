import os
import shutil
import sys
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

def require_env(name, value, max_length):
    if value is None or not value.strip():
        raise RuntimeError(f"Required environment variable '{name}' is not set.")
    value = value.strip()
    if len(value) > max_length:
        raise RuntimeError(
            f"Environment variable '{name}' must be at most {max_length} characters; got {len(value)}."
        )
    return value

sistema = require_env('SISTEMA', sistema, 4)
usuario = require_env('USUARIO', usuario, 7)
senha = require_env('SENHA', senha, 7)
unidade_executora = require_env('UNIDADE_EXECUTORA', unidade_executora, 7)

month = datetime.today().strftime("%m")


CAMINHO_LOCAL = os.path.join(os.getenv('PASTA_LOCAL'), 'remanejamento.xlsx')

#Nome da aba na planilha Excel onde estão os dados a serem processados
SHEET_NAME = 'CombinedSheet'

while True:
    em = Emulator(visible=False, args=['-script']) ## use modo headless com script para o s3270
    em.connect('bhmvsb.prodemge.gov.br')
    em.wait_for_field()

    if not em.string_found(1, 2, 'UNABLE TO ESTABLISH SESSION'):
        break

    print("Não foi possível estabelecer conexão com o servidor. Tentando novamente...")
    em.terminate()
    time.sleep(1)

# Preenche os dados de login
em.fill_field(19, 13, sistema, 8)
em.fill_field(20, 13, usuario, 8)
em.fill_field(21, 13, senha, 8)
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
    sys.exit(1)

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
    sys.exit(1)

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


# Leitura da planilha

df = pd.read_excel(CAMINHO_LOCAL, sheet_name=SHEET_NAME)
df = df.dropna(how='all')  # remove linhas completamente vazias
df = df.sort_values(by=['Anular', 'UO_COD'], ascending=[True, True]) # ordena por anulação e depois por UO


# O loop itera sobre cada linha do DataFrame, processa os dados.
for idx, row in df.iterrows():
    data_row = {}
    data_row['month']   = month
    data_row['uo']      = str(int(row['UO_COD']))
    data_row['grupo']   = str(int(row['Grupo']))
    data_row['iag']     = str(int(row['IAG']))
    data_row['fonte']   = str(int(row['Fonte']))
    data_row['procedencia'] = str(int(row['IPU']))
    data_row['acao'] = str(int(row['Ação']))
    data_row['tipo_global'] = str(row['GLOBAL']).strip().lower() if pd.notna(row['GLOBAL']) else '0'
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

print('Fluxo finalizado')

em.terminate()
