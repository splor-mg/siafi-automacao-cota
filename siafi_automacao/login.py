import os
import glob
import shutil
import time
from datetime import datetime

from dotenv import load_dotenv
from py3270 import Emulator
from openpyxl import load_workbook

from fluxo_anular import anular
from fluxo_aprovar import aprovar

# ---------------------------------------------------------------------------
# Configuracoes
# ---------------------------------------------------------------------------
load_dotenv()
sistema           = os.getenv('SISTEMA')
usuario           = os.getenv('USUARIO')
senha             = os.getenv('SENHA')
unidade_executora = os.getenv('UNIDADE_EXECUTORA')

month = datetime.today().strftime("%m")

# Pasta de ORIGEM (OneDrive sincronizado) de onde o arquivo a processar e
# MOVIDO para a pasta local. O caminho do Windows  C:\Users\...  e acessado
# a partir do WSL via /mnt/c/...
PASTA_ORIGEM = (
    '/mnt/c/Users/x70167581686/OneDrive - CAMG/General/@dcmefo/2026/'
    'Robo - Remanejamento e aprovacao de cota/Robo (IPU 2)/Python'
)

# Pasta de DESTINO (OneDrive) para onde o arquivo processado e MOVIDO ao
# final, para conferencia.
PASTA_DESTINO = (
    '/mnt/c/Users/x70167581686/OneDrive - CAMG/General/@dcmefo/2026/'
    'Robo - Remanejamento e aprovacao de cota/Conferencia arquivo robo'
)

# Pasta local (Linux/WSL) onde o robo realmente atua, para nao depender da
# sincronizacao do OneDrive enquanto grava.
PASTA_LOCAL = '/home/guilhermemelof/code/splor-mg/siafi-automacao-cota/data'


# ---------------------------------------------------------------------------
# Funcoes auxiliares
# ---------------------------------------------------------------------------
def _vazio(v):
    """True para celula vazia (None ou string em branco)."""
    return v is None or (isinstance(v, str) and v.strip() == '')


def _txt_int(v):
    """Converte numero (mesmo vindo como float, ex.: 1451.0) em string inteira."""
    return str(int(float(v)))


def mover(origem, destino):
    """Move 'origem' para 'destino', sobrescrevendo se ja existir.

    Pre-remover o destino evita o erro 'Destination path already exists' do
    shutil.move quando a origem e o destino estao em sistemas de arquivos
    diferentes (caso tipico de WSL local <-> /mnt/c do OneDrive), situacao em
    que o shutil.move faz copy2 + remove em vez de um rename simples."""
    if os.path.exists(destino):
        os.remove(destino)
    shutil.move(origem, destino)


def localizar_arquivo(pasta):
    """Retorna o caminho do .xlsx mais recente da pasta, ignorando arquivos
    temporarios de lock do Excel (que comecam com '~$')."""
    candidatos = [
        c for c in glob.glob(os.path.join(pasta, '*.xlsx'))
        if not os.path.basename(c).startswith('~$')
    ]
    if not candidatos:
        raise FileNotFoundError(f"Nenhum arquivo .xlsx encontrado em: {pasta}")
    candidatos.sort(key=os.path.getmtime, reverse=True)  # mais recente primeiro
    if len(candidatos) > 1:
        print("Aviso: ha mais de um .xlsx na pasta. Usando o mais recente:")
        print(f"   -> {os.path.basename(candidatos[0])}")
    return candidatos[0]


def localizar_aba(wb):
    """Localiza a aba que contem os dados (a que tem as colunas 'Progresso' e
    'UO_COD' no cabecalho). Assim o script funciona independente do nome da
    aba ('Planilha1', 'Remanejamento Cota Orcamentaria', etc.)."""
    for ws in wb.worksheets:
        cabec = [ws.cell(row=1, column=c).value for c in range(1, (ws.max_column or 0) + 1)]
        if 'Progresso' in cabec and 'UO_COD' in cabec:
            return ws
    return wb.active


def traduzir_progresso(retorno):
    """Converte a mensagem crua do SIAFI no texto que vai para a coluna
    'Progresso'. Mensagens conhecidas viram um texto amigavel; qualquer outro
    retorno e tratado como sucesso ('Ok').
    Para incluir novas mensagens, basta acrescentar uma linha no mapa abaixo."""
    if retorno is None:
        return 'Ok'
    retorno = retorno.strip()

    if retorno.startswith("E90 - SALDO ZERADO NA CONTA"):
        return 'Saldo zerado na conta'

    mapa = {
        "0139- VALOR A APROVAR MAIOR QUE SALDO DISPONIVEL NO PROJ/ATIV.":
            'Valor a aprovar maior que o saldo disponível',
        "0139- VALORES A ANULAR MAIOR QUE SALDO DISPONIVEL.":
            'Valor a anular maior que o saldo disponível',
        "0139- PROJ/ATIV OU FONTE/PROC./IAG INEXISTENTE PARA UO":
            'Proj/Ativ ou Fonte/Proc./IAG inexistente para a UO',
        "0101- GRUPO DESPESA INEXISTENTE(S).":
            'Grupo de despesa inexistente',
        "0139- ELEMENTO/ITEM NAO MARCADO PARA UO BENEFICIADA.":
            'Elemento/item não marcado para a UO beneficiada',
        "SALDO DE CREDITO ORCAMENTARIO A APROVAR POR PROJ/ATIV ZERADO.":
            'Saldo de crédito a aprovar zerado',
    }
    return mapa.get(retorno, 'Ok')


def montar_data_row(get, month):
    """Monta o dicionario data_row a partir de uma linha da planilha.
    'get' e uma funcao que recebe o nome da coluna e devolve o valor da celula."""
    dr = {'month': month}
    dr['uo']          = _txt_int(get('UO_COD'))
    dr['grupo']       = _txt_int(get('Grupo'))
    dr['iag']         = _txt_int(get('IAG'))
    dr['fonte']       = _txt_int(get('Fonte'))
    dr['procedencia'] = _txt_int(get('IPU'))
    dr['acao']        = _txt_int(get('Ação'))

    g = get('GLOBAL')
    dr['tipo_global'] = g.strip() if (isinstance(g, str) and g.strip() != '') else '0'

    am = get('AMARRADO')
    if not _vazio(am):
        amarrado = _txt_int(am).zfill(4)   # garante 4 digitos (ex.: 308 -> '0308')
        dr['tipo_amarrado'] = amarrado
        dr['elemento'] = amarrado[:2]      # dois primeiros digitos
        dr['item']     = amarrado[2:]      # dois ultimos digitos
    else:
        dr['tipo_amarrado'] = '0'
        dr['elemento'] = '0'
        dr['item']     = '0'

    uof = get('UO Financiadora')
    dr['uo_financiadora'] = _txt_int(uof) if not _vazio(uof) else '0'

    av = get('Anular')
    pv = get('Aprovar')
    dr['valor_anulacao']  = int(round(float(av) * 100)) if not _vazio(av) else 0
    dr['valor_aprovacao'] = int(round(float(pv) * 100)) if not _vazio(pv) else 0

    # valor a preencher: usa anulacao se houver, senao aprovacao
    dr['valor'] = dr['valor_anulacao'] if dr['valor_anulacao'] != 0 else dr['valor_aprovacao']
    return dr


# ===========================================================================
# Execucao
# ===========================================================================
if __name__ == "__main__":

    # -----------------------------------------------------------------------
    # 1) Move o arquivo da pasta de origem para a pasta local e abre a copia
    # -----------------------------------------------------------------------
    os.makedirs(PASTA_LOCAL, exist_ok=True)
    os.makedirs(PASTA_DESTINO, exist_ok=True)

    arquivo_origem  = localizar_arquivo(PASTA_ORIGEM)
    nome_arquivo    = os.path.basename(arquivo_origem)
    caminho_local   = os.path.join(PASTA_LOCAL, nome_arquivo)
    caminho_destino = os.path.join(PASTA_DESTINO, nome_arquivo)

    # A partir daqui o arquivo NAO existe mais na pasta de origem.
    mover(arquivo_origem, caminho_local)
    print(f"Arquivo movido da pasta de origem para a pasta local: {caminho_local}")

    wb = load_workbook(caminho_local)
    ws = localizar_aba(wb)
    col = {ws.cell(row=1, column=c).value: c
           for c in range(1, ws.max_column + 1)
           if ws.cell(row=1, column=c).value}

    # -----------------------------------------------------------------------
    # 2) Identifica as linhas pendentes (tem dados, mas a coluna Progresso
    #    ainda esta vazia). E o caso da execucao mais recente.
    # -----------------------------------------------------------------------
    pendentes = [
        r for r in range(2, ws.max_row + 1)
        if not _vazio(ws.cell(row=r, column=col['UO_COD']).value)
        and _vazio(ws.cell(row=r, column=col['Progresso']).value)
    ]

    if not pendentes:
        print("Nenhuma linha pendente para processar.")
        mover(caminho_local, caminho_destino)
        print(f"Arquivo movido para a pasta de conferencia: {caminho_destino}")
        raise SystemExit(0)

    print(f"{len(pendentes)} linha(s) pendente(s) para processar: {pendentes}")

    # -----------------------------------------------------------------------
    # 3) Login no SIAFI
    # -----------------------------------------------------------------------
    em = Emulator(visible=True)  # use visible=False para rodar sem janela
    em.connect('bhmvsb.prodemge.gov.br')
    em.wait_for_field()

    em.fill_field(19, 13, sistema, 7)
    em.fill_field(20, 13, usuario, 7)
    em.fill_field(21, 13, senha, 7)
    em.send_enter()

    max_tentativas = 10
    tentativas = 0
    while tentativas < max_tentativas:
        time.sleep(1)
        try:
            em.send_enter()
            if em.string_found(1, 13, 'Logon executado com sucesso'):
                print("Login realizado com sucesso!")
                break
            else:
                print(f"Tentativa {tentativas + 1} - tela intermediária, avançando...")
                em.send_enter()
        except:
            print(f"Tentativa {tentativas + 1} - tela de aviso detectada, passando...")
            em.send_enter()
        tentativas += 1

    if tentativas == max_tentativas:
        print("Não foi possível fazer login após várias tentativas.")
        em.terminate()
        raise SystemExit(1)

    em.fill_field(1, 2, sistema, 4)
    em.send_enter()

    # nova tela buscando login...
    max_tentativas = 10
    tentativas = 0
    while tentativas < max_tentativas:
        time.sleep(1)
        try:
            em.send_enter()
            if em.string_found(22, 11, 'Unidade Executora'):
                print("Texto encontrado")
                break
            else:
                print(f"Tentativa {tentativas + 1} - tela intermediária, avançando...")
                em.send_enter()
        except:
            print(f"Tentativa {tentativas + 1} - tela de aviso detectada, passando...")
            em.send_enter()
        tentativas += 1

    if tentativas == max_tentativas:
        print("Não foi possível fazer login após várias tentativas.")
        em.terminate()
        raise SystemExit(1)

    # Entrar com a Unidade Executora
    em.fill_field(22, 30, unidade_executora, 7)
    em.send_enter()
    em.wait_for_field()
    # Fim do login

    # Entrar em 03 - Movimentacao Orcamentaria
    em.fill_field(21, 19, '03', 2)
    em.send_enter()
    em.wait_for_field()

    # Entrar em 02 - Aprovacao de Cota Orcamentaria
    em.fill_field(21, 19, '02', 2)
    em.send_enter()
    em.wait_for_field()

    # -----------------------------------------------------------------------
    # 4) Processa cada linha pendente e grava o resultado na coluna Progresso
    # -----------------------------------------------------------------------
    for r in pendentes:
        get = lambda nome: ws.cell(row=r, column=col[nome]).value
        data_row = montar_data_row(get, month)

        # Linha sem GLOBAL e sem AMARRADO nao e processavel no SIAFI:
        # registra o motivo e segue para a proxima.
        if data_row['tipo_global'] != 'x' and data_row['tipo_amarrado'] == '0':
            print(f"Linha {r}: sem GLOBAL/AMARRADO definido, pulando.")
            ws.cell(row=r, column=col['Progresso']).value = 'Linha sem GLOBAL/AMARRADO definido'
            wb.save(caminho_local)
            continue

        if data_row['valor_anulacao'] != 0:
            print("realizando procedimento de anulação")
        elif data_row['valor_aprovacao'] != 0:
            print("realizando procedimento de aprovação")

        print(
            f"Processando linha {r} | UO: {data_row['uo']}, Grupo: {data_row['grupo']}, "
            f"Acao: {data_row['acao']}, Fonte: {data_row['fonte']}, "
            f"Procedencia: {data_row['procedencia']}, Valor: {data_row['valor']}"
        )

        retorno = None
        if data_row['valor_anulacao'] != 0:
            retorno = anular(em, data_row)
        elif data_row['valor_aprovacao'] != 0:
            retorno = aprovar(em, data_row)
        else:
            retorno = 'Linha sem valor de anulação/aprovação'

        # Grava o resultado e salva imediatamente (resiliencia: se o SIAFI
        # travar no meio, o progresso ja concluido fica registrado).
        ws.cell(row=r, column=col['Progresso']).value = traduzir_progresso(retorno)
        wb.save(caminho_local)

    print('Fluxo finalizado')
    em.terminate()

    # -----------------------------------------------------------------------
    # 5) Move o arquivo atualizado para a pasta de conferencia do OneDrive.
    # -----------------------------------------------------------------------
    wb.save(caminho_local)
    mover(caminho_local, caminho_destino)
    print(f"Planilha atualizada e movida para a pasta de conferencia: {caminho_destino}")