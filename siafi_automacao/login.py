import os
import sys
import glob
import shutil
import subprocess
import time
from datetime import date, datetime

from dotenv import load_dotenv
from py3270 import Emulator
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

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

_onedrive_base = os.getenv('ONEDRIVE_BASE')
siafi_host     = os.getenv('SIAFI_HOST', 'bhmvsb.prodemge.gov.br')
siafi_visivel  = os.getenv('SIAFI_VISIVEL', 'true').lower() == 'true'

month = datetime.today().strftime("%m")

# Pasta de ORIGEM (OneDrive sincronizado) de onde o arquivo a processar e
# MOVIDO para a pasta local. O caminho do Windows  C:/Users/...  e acessado
# a partir do WSL via /mnt/c/...
PASTA_ORIGEM                    = os.path.join(_onedrive_base, 'Robo (IPU 2)', 'Python')
PASTA_DESTINO                   = os.path.join(_onedrive_base, 'Conferencia arquivo robo')
PASTA_REALIZADOS                = os.path.join(_onedrive_base, 'Realizados')
PASTA_REMANEJAMENTOS_REALIZADOS = os.path.join(_onedrive_base, 'Realizados', 'Remanejamentos realizados')

# Pasta local (Linux/WSL) onde o robo realmente atua, para nao depender da
# sincronizacao do OneDrive enquanto grava.
PASTA_LOCAL = os.getenv('PASTA_LOCAL')


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
    shutil.move(origem, destino, copy_function=shutil.copyfile)


def organizar_realizados(pasta_origem, pasta_destino):
    """Move os .xlsx soltos em 'pasta_origem' para 'pasta_destino'.
    Se ja existir um arquivo com o mesmo nome, adiciona sufixo (1), (2), etc."""
    os.makedirs(pasta_destino, exist_ok=True)
    arquivos = [
        f for f in os.listdir(pasta_origem)
        if f.endswith('.xlsx') and os.path.isfile(os.path.join(pasta_origem, f))
    ]
    for nome in arquivos:
        origem = os.path.join(pasta_origem, nome)
        destino = os.path.join(pasta_destino, nome)
        if os.path.exists(destino):
            base, ext = os.path.splitext(nome)
            contador = 1
            while os.path.exists(destino):
                destino = os.path.join(pasta_destino, f"{base} ({contador}){ext}")
                contador += 1
        shutil.move(origem, destino, copy_function=shutil.copyfile)
        print(f"Organizando: {nome} -> {os.path.basename(destino)}")


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
        "0139- PROGRAMA DE TRABALHO NAO ENCONTRADO PARA GM/FP.":
            'Programa de trabalho não encontrado para GM/FP',
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


def formatar_planilha(ws):
    """Aplica formatacao visual gerencial na aba: cabecalho colorido, valores
    numericos formatados, zebra nas linhas, coluna Progresso com cor condicional
    e larguras ajustadas ao conteudo."""
    AZUL_ESCURO  = PatternFill('solid', fgColor='1F4E79')
    AZUL_CLARO   = PatternFill('solid', fgColor='D6E4F0')
    BRANCO       = PatternFill('solid', fgColor='FFFFFF')
    VERDE        = PatternFill('solid', fgColor='C6EFCE')
    AMARELO      = PatternFill('solid', fgColor='FFEB9C')
    VERMELHO     = PatternFill('solid', fgColor='FFC7CE')
    FONTE_BRANCA = Font(bold=True, color='FFFFFF', name='Calibri', size=11)
    FONTE_NORMAL = Font(name='Calibri', size=10)
    BORDA = Border(
        left=Side(style='thin', color='BFBFBF'),
        right=Side(style='thin', color='BFBFBF'),
        top=Side(style='thin', color='BFBFBF'),
        bottom=Side(style='thin', color='BFBFBF'),
    )
    COLS_VALOR = {'Anular', 'Aprovar'}

    max_col = ws.max_column
    max_row = ws.max_row

    # Mapeia nome da coluna -> indice
    cabec = {ws.cell(row=1, column=c).value: c for c in range(1, max_col + 1)}

    # Remove linhas de grade
    ws.sheet_view.showGridLines = False

    # Cabecalho
    for c in range(1, max_col + 1):
        cell = ws.cell(row=1, column=c)
        cell.fill   = AZUL_ESCURO
        cell.font   = FONTE_BRANCA
        cell.border = BORDA
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=False)
    ws.row_dimensions[1].height = 20

    # Linhas de dados
    for r in range(2, max_row + 1):
        zebra = AZUL_CLARO if r % 2 == 0 else BRANCO
        for c in range(1, max_col + 1):
            cell      = ws.cell(row=r, column=c)
            cell.fill = zebra
            cell.font = FONTE_NORMAL
            cell.border = BORDA

            col_nome = ws.cell(row=1, column=c).value

            # Formata colunas de valor monetario (alinha direita)
            if col_nome in COLS_VALOR and cell.value not in (None, ''):
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal='right', vertical='center')
            else:
                cell.alignment = Alignment(horizontal='center', vertical='center')

        # Cor condicional na coluna Progresso
        if 'Progresso' in cabec:
            prog_cell = ws.cell(row=r, column=cabec['Progresso'])
            valor = (prog_cell.value or '').strip()
            if valor == 'Ok':
                prog_cell.fill = VERDE
            elif valor != '':
                prog_cell.fill = VERMELHO if 'zerado' in valor.lower() or 'maior' in valor.lower() or 'inexistente' in valor.lower() else AMARELO

    # Congela a primeira linha
    ws.freeze_panes = 'A2'

    # Ajusta largura: usa o maior entre o titulo do cabecalho e o conteudo
    for c in range(1, max_col + 1):
        col_letter = get_column_letter(c)
        max_len = 0
        for r in range(1, max_row + 1):
            val = ws.cell(row=r, column=c).value
            if val is not None:
                max_len = max(max_len, len(str(val)))
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 10), 50)


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
    dr['tipo_global'] = g.strip().lower() if (isinstance(g, str) and g.strip() != '') else '0'

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
    # 0) Executa consolida.py, aguarda o arquivo ficar disponível e pede
    #    confirmação antes de iniciar o fluxo no SIAFI.
    # -----------------------------------------------------------------------
    script_consolida = os.path.join(os.path.dirname(__file__), 'consolida.py')
    print("Executando consolida.py...")
    subprocess.run([sys.executable, script_consolida], check=True)

    hoje = date.today()
    nome_conferencia = (
        f'Conferencia arquivo robo {hoje.day:02d}.{hoje.month:02d}.xlsx'
    )
    caminho_conferencia = os.path.join(PASTA_ORIGEM, nome_conferencia)

    print("Aguardando o arquivo de conferência ficar disponível...", end='', flush=True)
    disponivel = False
    for _ in range(30):
        if os.path.exists(caminho_conferencia):
            try:
                open(caminho_conferencia, 'rb').close()
                disponivel = True
                break
            except OSError:
                pass
        print('.', end='', flush=True)
        time.sleep(2)
    print()

    if disponivel:
        caminho_windows = caminho_conferencia.replace('/mnt/c/', 'C:\\').replace('/', '\\')
        subprocess.Popen(
            ['cmd.exe', '/c', 'start', '', caminho_windows],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print(f"Arquivo aberto: {caminho_windows}")
    else:
        print("[aviso] Arquivo de conferência não encontrado após 60s.")

    resposta = ''
    while resposta not in ('s', 'n'):
        resposta = input("Deseja continuar com o fluxo no SIAFI? (s/n): ").strip().lower()

    if resposta == 'n':
        print("Fluxo cancelado pelo usuário.")
        raise SystemExit(0)

    if disponivel:
        nome_conferencia_win = os.path.basename(caminho_conferencia)
        ps_cmd = (
            '$xl = $null; '
            'try { $xl = [Runtime.InteropServices.Marshal]::GetActiveObject("Excel.Application") } catch {}; '
            f'if ($xl) {{ $xl.Workbooks | Where-Object {{ $_.Name -eq "{nome_conferencia_win}" }} '
            '| ForEach-Object { $_.Close($false) }; '
            'if ($xl.Workbooks.Count -eq 0) { $xl.Quit() } }'
        )
        subprocess.run(
            ['powershell.exe', '-Command', ps_cmd],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print(f"Arquivo de conferência fechado.")

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
    while True:
        em = Emulator(visible=siafi_visivel)
        em.connect(siafi_host)
        em.wait_for_field()

        if not em.string_found(1, 2, 'UNABLE TO ESTABLISH SESSION'):
            break

        print("Não foi possível estabelecer conexão com o servidor. Tentando novamente...")
        em.terminate()
        time.sleep(1)

    em.fill_field(19, 13, sistema, 8)
    em.fill_field(20, 13, usuario, 8)
    em.fill_field(21, 13, senha, 8)
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
    # 5) Formata e move o arquivo atualizado para a pasta de conferencia.
    # -----------------------------------------------------------------------
    formatar_planilha(ws)
    wb.save(caminho_local)
    mover(caminho_local, caminho_destino)
    print(f"Planilha atualizada e movida para a pasta de conferencia: {caminho_destino}")

    # -----------------------------------------------------------------------
    # 6) Organiza os .xlsx soltos em Realizados -> Remanejamentos realizados.
    # -----------------------------------------------------------------------
    organizar_realizados(PASTA_REALIZADOS, PASTA_REMANEJAMENTOS_REALIZADOS)
    print("Pasta Realizados organizada.")