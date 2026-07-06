"""
Consolidação do "Conferencia arquivo robo".

Fluxo:

0. VALIDA todos os arquivos das pastas de remanejamento ANTES de qualquer
   consolidação/movimentação. Se qualquer linha violar as regras de negócio,
   imprime TODOS os erros (arquivo, linha, coluna, valor) e aborta com código
   de saída != 0 — o que faz o subprocess.run(..., check=True) do orquestrador
   interromper todo o fluxo antes de tocar no SIAFI.

1. Procura o arquivo "Conferencia arquivo robo <dd.mm>" na pasta CONFERENCIA.

2. Lê a data do nome do arquivo:
   - Se a data == hoje  -> apende um novo bloco com Execução = (máx atual + 1).
   - Se a data != hoje  -> move o conferência antigo para REALIZADOS_CONFERENCIA
                           e começa um conferência novo (Execução = 1).

3. Consolida todos os .xlsx/.xls das pastas REMANEJAMENTOS, ordena o bloco novo
   por UO_COD (crescente) e depois Anular (crescente).

4. Salva o consolidado em ROBO_IPU2_PYTHON com o nome "Conferencia arquivo robo <hoje>".
   Ao final, a pasta CONFERENCIA fica VAZIA:
   - mesma data  -> o arquivo lido é consolidado e movido para ROBO_IPU2_PYTHON;
   - data diferente -> o antigo vai para REALIZADOS_CONFERENCIA e o novo para ROBO_IPU2_PYTHON.

5. Só DEPOIS de salvar com sucesso, move os arquivos de origem para REALIZADOS.

OBS.: como o arquivo SAI da pasta CONFERENCIA, para uma 2ª rodada no MESMO dia
apensar corretamente (Execução +1), o arquivo precisa ser devolvido à pasta
CONFERENCIA por outro processo antes da próxima execução.
"""

import os
import re
import shutil
import unicodedata
from datetime import date

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ===================== CONFIGURAÇÃO =====================
BASE = os.getenv('ONEDRIVE_BASE')

CONFERENCIA            = os.path.join(BASE, 'Conferencia arquivo robo')
REALIZADOS             = os.path.join(BASE, 'Realizados')
REALIZADOS_CONFERENCIA = os.path.join(BASE, 'Realizados', 'Conferencia Robo Realizados')
ROBO_IPU2_PYTHON       = os.path.join(BASE, 'Robo (IPU 2)', 'Python')

PASTAS_REMANEJAMENTOS = [
    os.path.join(BASE, 'Remanejamentos'),
    os.path.join(BASE, 'Remanejamentos (SEGOV)'),
]

SEPARADOR_DATA = '.'
PREFIXO_NOME   = 'Conferencia arquivo robo'
ABA_SAIDA      = 'Planilha1'

COLUNAS_CONFERENCIA = [
    'Execução', 'UO_COD', 'Grupo', 'IAG', 'Fonte', 'IPU', 'Ação',
    'GLOBAL', 'AMARRADO', 'Anular', 'Aprovar', 'UO Financiadora', 'Progresso',
]
COLUNAS_DADOS   = [c for c in COLUNAS_CONFERENCIA if c != 'Execução']
COLUNAS_VALOR   = ['Anular', 'Aprovar']
COLUNAS_CODIGO  = [
    'Execução', 'UO_COD', 'Grupo', 'IAG', 'Fonte', 'IPU', 'Ação',
    'AMARRADO', 'UO Financiadora',
]

# ------------------- REGRAS DE VALIDAÇÃO -------------------
# Colunas obrigatórias em cada planilha de remanejamento. Se faltar alguma,
# o arquivo inteiro é reprovado (não dá para validar/consolidar sem elas).
COLUNAS_OBRIGATORIAS = [
    'UO_COD', 'Grupo', 'IAG', 'IPU', 'Ação',
    'GLOBAL', 'AMARRADO', 'Anular', 'Aprovar', 'UO Financiadora',
]

# Uma linha é considerada "linha de dados" (e portanto validada) se QUALQUER
# uma destas colunas estiver preenchida. Linhas totalmente em branco são
# ignoradas (espaçadores, etc.).
COLUNAS_GATILHO = [
    'UO_COD', 'Grupo', 'IAG', 'Fonte', 'IPU', 'Ação',
    'GLOBAL', 'AMARRADO', 'Anular', 'Aprovar', 'UO Financiadora',
]

DIGITOS_UO       = 4        # UO_COD: exatamente 4 dígitos
DIGITOS_ACAO     = 4        # Ação: exatamente 4 dígitos
DIGITOS_UO_FIN   = 4        # UO Financiadora (quando exigida): exatamente 4 dígitos
GRUPO_MIN, GRUPO_MAX = 1, 6
IPU_MIN, IPU_MAX     = 0, 9
IAG_VALIDOS          = {0, 1}

# AMARRADO: aceita de 1 até 4 dígitos, pois o fluxo faz .zfill(4) e a aba DADOS
# contém elemento-item válidos de 3 dígitos (ex.: 308 -> 0308). Se a regra de
# negócio for "sempre 4 dígitos", troque AMARRADO_MIN_DIGITOS para 4.
AMARRADO_MIN_DIGITOS = 1
AMARRADO_MAX_DIGITOS = 4
# ==========================================================


def _sem_acento(texto: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFKD', str(texto))
        if not unicodedata.combining(c)
    ).lower()


def resolver_pasta(caminho: str) -> str:
    """Se a pasta exata não existir, procura uma irmã com mesmo nome
    ignorando acentos e maiúsculas. Senão, devolve o literal."""
    if os.path.isdir(caminho):
        return caminho
    pai = os.path.dirname(caminho)
    alvo = _sem_acento(os.path.basename(caminho))
    if os.path.isdir(pai):
        for nome in os.listdir(pai):
            p = os.path.join(pai, nome)
            if os.path.isdir(p) and _sem_acento(nome) == alvo:
                return p
    return caminho


def encontrar_conferencia(pasta: str):
    """Retorna (caminho, dia, mes) do arquivo de conferência na pasta, ou None."""
    if not os.path.isdir(pasta):
        return None

    candidatos = []
    prefixo = _sem_acento(PREFIXO_NOME)
    for nome in os.listdir(pasta):
        if nome.startswith('~$'):
            continue
        if not nome.lower().endswith(('.xlsx', '.xls')):
            continue
        if not _sem_acento(nome).startswith(prefixo):
            continue
        m = re.search(r'(\d{2})[.\-_ ](\d{2})', nome)
        if m:
            caminho = os.path.join(pasta, nome)
            candidatos.append((os.path.getmtime(caminho), caminho, int(m.group(1)), int(m.group(2))))

    if not candidatos:
        return None

    candidatos.sort(reverse=True)
    _, caminho, dia, mes = candidatos[0]
    return caminho, dia, mes


# ===========================================================================
# VALIDAÇÃO DAS PLANILHAS DE REMANEJAMENTO
# ===========================================================================
def _vazio_cel(v) -> bool:
    """True para célula vazia: None, NaN (pandas) ou string em branco."""
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return isinstance(v, str) and v.strip() == ''


def _inteiro(v):
    """Tenta converter para int 'limpo'. Retorna (ok, valor).
    Aceita 1401, 1401.0, '1401', ' 1401 '. Rejeita 1401.5, 'abc', vazio."""
    if _vazio_cel(v):
        return False, None
    try:
        f = float(str(v).strip())
    except (TypeError, ValueError):
        return False, None
    if f != int(f):
        return False, None
    return True, int(f)


def _numero(v):
    """Tenta converter para float (valor monetário). Retorna (ok, valor)."""
    if _vazio_cel(v):
        return False, None
    try:
        return True, float(v)
    except (TypeError, ValueError):
        try:
            return True, float(str(v).strip())
        except (TypeError, ValueError):
            return False, None


def _num_digitos(n: int) -> int:
    return len(str(abs(int(n))))


def _validar_linha(row, arquivo: str, linha_excel: int, erros: list):
    """Aplica todas as regras de negócio a uma linha e acrescenta os problemas
    encontrados à lista 'erros' como tuplas (arquivo, linha, coluna, valor, msg)."""

    def add(coluna, valor, msg):
        erros.append((arquivo, linha_excel, coluna, valor, msg))

    # --- UO_COD: obrigatório, inteiro, exatamente DIGITOS_UO dígitos ---
    uo = row.get('UO_COD')
    ok_uo, uo_int = _inteiro(uo)
    if _vazio_cel(uo):
        add('UO_COD', uo, 'UO_COD vazio (obrigatório)')
    elif not ok_uo:
        add('UO_COD', uo, 'UO_COD deve ser um número inteiro')
    elif _num_digitos(uo_int) != DIGITOS_UO:
        add('UO_COD', uo, f'UO_COD deve ter {DIGITOS_UO} dígitos')

    # --- Grupo: obrigatório, inteiro de GRUPO_MIN a GRUPO_MAX ---
    grupo = row.get('Grupo')
    ok_grupo, grupo_int = _inteiro(grupo)
    if _vazio_cel(grupo):
        add('Grupo', grupo, 'Grupo vazio (obrigatório)')
    elif not ok_grupo:
        add('Grupo', grupo, 'Grupo deve ser um número inteiro')
    elif not (GRUPO_MIN <= grupo_int <= GRUPO_MAX):
        add('Grupo', grupo, f'Grupo deve estar entre {GRUPO_MIN} e {GRUPO_MAX}')

    # --- IAG: obrigatório, 0 ou 1 ---
    iag = row.get('IAG')
    ok_iag, iag_int = _inteiro(iag)
    if _vazio_cel(iag):
        add('IAG', iag, 'IAG vazio (obrigatório)')
    elif not ok_iag or iag_int not in IAG_VALIDOS:
        add('IAG', iag, 'IAG deve ser 0 ou 1')

    # --- IPU: obrigatório, inteiro de IPU_MIN a IPU_MAX ---
    ipu = row.get('IPU')
    ok_ipu, ipu_int = _inteiro(ipu)
    if _vazio_cel(ipu):
        add('IPU', ipu, 'IPU vazio (obrigatório)')
    elif not ok_ipu or not (IPU_MIN <= ipu_int <= IPU_MAX):
        add('IPU', ipu, f'IPU deve ser um número de {IPU_MIN} a {IPU_MAX}')

    # --- Ação: obrigatório, inteiro, exatamente DIGITOS_ACAO dígitos ---
    acao = row.get('Ação')
    ok_acao, acao_int = _inteiro(acao)
    if _vazio_cel(acao):
        add('Ação', acao, 'Ação vazia (obrigatório)')
    elif not ok_acao:
        add('Ação', acao, 'Ação deve ser um número inteiro')
    elif _num_digitos(acao_int) != DIGITOS_ACAO:
        add('Ação', acao, f'Ação deve ter {DIGITOS_ACAO} dígitos')

    # --- GLOBAL x AMARRADO ---
    glob = row.get('GLOBAL')
    amarr = row.get('AMARRADO')
    glob_preench = not _vazio_cel(glob)
    amarr_preench = not _vazio_cel(amarr)

    # GLOBAL: se preenchido, só aceita 'x'/'X'
    if glob_preench and str(glob).strip().lower() != 'x':
        add('GLOBAL', glob, "GLOBAL só pode conter 'x' (ou 'X')")

    # AMARRADO: se preenchido, inteiro de 1 a AMARRADO_MAX_DIGITOS dígitos
    ok_amarr, amarr_int = (False, None)
    if amarr_preench:
        ok_amarr, amarr_int = _inteiro(amarr)
        if not ok_amarr:
            add('AMARRADO', amarr, 'AMARRADO deve ser um número inteiro')
        elif not (AMARRADO_MIN_DIGITOS <= _num_digitos(amarr_int) <= AMARRADO_MAX_DIGITOS):
            add('AMARRADO', amarr,
                f'AMARRADO deve ter até {AMARRADO_MAX_DIGITOS} dígitos')

    # Exclusão mútua: exatamente um dos dois preenchido
    if glob_preench and amarr_preench:
        add('GLOBAL/AMARRADO', f'GLOBAL={glob} | AMARRADO={amarr}',
            'GLOBAL e AMARRADO não podem estar preenchidos ao mesmo tempo')
    elif not glob_preench and not amarr_preench:
        add('GLOBAL/AMARRADO', '',
            'A linha precisa ter GLOBAL ou AMARRADO preenchido')

    # Grupo 1 ou IPU 9 -> AMARRADO obrigatório (GLOBAL não é permitido)
    exige_amarrado = (ok_grupo and grupo_int == 1) or (ok_ipu and ipu_int == 9)
    if exige_amarrado and not amarr_preench:
        motivo = 'Grupo 1' if (ok_grupo and grupo_int == 1) else 'IPU 9'
        add('AMARRADO', amarr,
            f'{motivo} exige AMARRADO preenchido (GLOBAL não é permitido)')

    # --- Anular x Aprovar ---
    anular = row.get('Anular')
    aprovar = row.get('Aprovar')
    anular_preench = not _vazio_cel(anular)
    aprovar_preench = not _vazio_cel(aprovar)

    if anular_preench:
        ok_an, val_an = _numero(anular)
        if not ok_an:
            add('Anular', anular, 'Anular deve ser um valor numérico')
        elif val_an <= 0:
            add('Anular', anular, 'Anular deve ser um valor maior que zero')

    if aprovar_preench:
        ok_ap, val_ap = _numero(aprovar)
        if not ok_ap:
            add('Aprovar', aprovar, 'Aprovar deve ser um valor numérico')
        elif val_ap <= 0:
            add('Aprovar', aprovar, 'Aprovar deve ser um valor maior que zero')

    # Exclusão mútua: exatamente um dos dois preenchido
    if anular_preench and aprovar_preench:
        add('Anular/Aprovar', f'Anular={anular} | Aprovar={aprovar}',
            'Anular e Aprovar não podem estar preenchidos ao mesmo tempo')
    elif not anular_preench and not aprovar_preench:
        add('Anular/Aprovar', '',
            'A linha precisa ter Anular ou Aprovar preenchido')

    # --- UO Financiadora: obrigatória com 4 dígitos quando IPU == 2 ---
    uofin = row.get('UO Financiadora')
    if ok_ipu and ipu_int == 2:
        if _vazio_cel(uofin):
            add('UO Financiadora', uofin,
                'UO Financiadora é obrigatória quando IPU = 2')
        else:
            ok_fin, fin_int = _inteiro(uofin)
            if not ok_fin:
                add('UO Financiadora', uofin,
                    'UO Financiadora deve ser um número inteiro')
            elif _num_digitos(fin_int) != DIGITOS_UO_FIN:
                add('UO Financiadora', uofin,
                    f'UO Financiadora deve ter {DIGITOS_UO_FIN} dígitos')


def validar_arquivo(caminho: str, erros: list):
    """Valida uma planilha de remanejamento inteira, acrescentando os problemas
    encontrados à lista 'erros'. Retorna True se o arquivo foi lido; False se
    houve falha ao abrir (o erro correspondente já é acrescentado à lista)."""
    nome = os.path.basename(caminho)
    try:
        df = pd.read_excel(caminho, sheet_name=0)
    except Exception as e:
        erros.append((nome, '-', '-', '', f'Falha ao abrir o arquivo: {e}'))
        return False

    df.columns = [str(c).strip() for c in df.columns]

    # Colunas obrigatórias presentes?
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        erros.append((nome, '-', ', '.join(faltando), '',
                      'Colunas obrigatórias ausentes na planilha'))
        return True  # sem as colunas não dá para validar linha a linha

    df = df.reset_index(drop=True)
    for i, row in df.iterrows():
        # É linha de dados? (qualquer coluna-gatilho preenchida)
        tem_conteudo = any(
            (c in df.columns) and not _vazio_cel(row.get(c))
            for c in COLUNAS_GATILHO
        )
        if not tem_conteudo:
            continue
        linha_excel = i + 2  # +1 do cabeçalho, +1 porque Excel começa em 1
        _validar_linha(row, nome, linha_excel, erros)

    return True


def validar_todos(arquivos: list) -> list:
    """Valida todos os arquivos e devolve a lista consolidada de erros."""
    erros = []
    for caminho in arquivos:
        validar_arquivo(caminho, erros)
    return erros


def imprimir_relatorio_erros(erros: list):
    """Imprime os erros agrupados por arquivo, ordenados por linha."""
    print('\n' + '=' * 78)
    print(f'VALIDAÇÃO REPROVADA — {len(erros)} problema(s) encontrado(s).')
    print('Corrija as planilhas abaixo e rode novamente. Nada foi consolidado.')
    print('=' * 78)

    por_arquivo = {}
    for arq, linha, coluna, valor, msg in erros:
        por_arquivo.setdefault(arq, []).append((linha, coluna, valor, msg))

    for arq in sorted(por_arquivo):
        print(f'\n>> {arq}')
        def _chave(item):
            linha = item[0]
            return (0, linha) if isinstance(linha, int) else (1, 0)
        for linha, coluna, valor, msg in sorted(por_arquivo[arq], key=_chave):
            local = f'linha {linha}' if isinstance(linha, int) else 'arquivo'
            valor_txt = '' if _vazio_cel(valor) else f" | valor: '{valor}'"
            print(f'   [{local}] coluna: {coluna}{valor_txt}\n       -> {msg}')
    print('\n' + '=' * 78)


# ===========================================================================
def ler_arquivo_origem(caminho: str) -> pd.DataFrame:
    """Lê a 1ª aba, descarta linhas-lixo e alinha as colunas ao layout do conferência."""
    df = pd.read_excel(caminho, sheet_name=0)
    df.columns = [str(c).strip() for c in df.columns]

    if 'UO_COD' not in df.columns:
        raise ValueError(f"Coluna 'UO_COD' não encontrada em {os.path.basename(caminho)}")

    df['UO_COD'] = pd.to_numeric(df['UO_COD'], errors='coerce')
    df = df[df['UO_COD'].notna()].copy()
    df = df.reindex(columns=COLUNAS_DADOS)

    for col in COLUNAS_VALOR:
        df[col] = pd.to_numeric(df[col], errors='coerce').round(2)

    return df


def coletar_arquivos_origem(pastas):
    arquivos = []
    for pasta in pastas:
        if not os.path.isdir(pasta):
            print(f'[aviso] Pasta de origem não encontrada, ignorando: {pasta}')
            continue
        for nome in os.listdir(pasta):
            if nome.startswith('~$'):
                continue
            if nome.lower().endswith(('.xlsx', '.xls')):
                arquivos.append(os.path.join(pasta, nome))
    return arquivos


def mover_com_seguranca(origem: str, pasta_destino: str):
    os.makedirs(pasta_destino, exist_ok=True)
    destino = os.path.join(pasta_destino, os.path.basename(origem))
    if os.path.exists(destino):
        base, ext = os.path.splitext(os.path.basename(origem))
        i = 1
        while os.path.exists(destino):
            destino = os.path.join(pasta_destino, f'{base} ({i}){ext}')
            i += 1
    shutil.move(origem, destino)


def main():
    hoje = date.today()
    nome_saida = f'{PREFIXO_NOME} {hoje.day:02d}{SEPARADOR_DATA}{hoje.month:02d}.xlsx'

    pasta_conferencia = resolver_pasta(CONFERENCIA)
    pastas_origem     = [resolver_pasta(p) for p in PASTAS_REMANEJAMENTOS]
    print(f'Pasta conferência: {pasta_conferencia}')

    # 1) Coleta os arquivos a consolidar ANTES de mexer em qualquer coisa
    arquivos_origem = coletar_arquivos_origem(pastas_origem)
    if not arquivos_origem:
        print('Nenhum arquivo nas pastas de remanejamento. Nada a consolidar.')
        return

    # 1.5) VALIDA todas as planilhas antes de consolidar/mover qualquer coisa.
    #      Se houver qualquer erro, imprime tudo e ABORTA com código != 0 para
    #      interromper o orquestrador (subprocess.run(..., check=True)).
    print(f'Validando {len(arquivos_origem)} arquivo(s) de remanejamento...')
    erros = validar_todos(arquivos_origem)
    if erros:
        imprimir_relatorio_erros(erros)
        raise SystemExit(1)
    print('Validação OK: todas as planilhas passaram nas regras.')

    # 2) Lê os arquivos de origem
    blocos = []
    for caminho in arquivos_origem:
        try:
            df = ler_arquivo_origem(caminho)
            if not df.empty:
                blocos.append(df)
                print(f'Lido: {os.path.basename(caminho)} ({len(df)} linhas)')
            else:
                print(f'[aviso] Sem linhas válidas: {os.path.basename(caminho)}')
        except Exception as e:
            print(f'[ERRO] Falha ao ler {os.path.basename(caminho)}: {e}')
            print('Abortando para não consolidar dados parciais.')
            raise SystemExit(1)

    if not blocos:
        print('Nenhuma linha válida encontrada nos arquivos de origem.')
        return

    bloco_novo = pd.concat(blocos, ignore_index=True)

    # 3) Ordena o bloco novo: UO_COD crescente, Anular crescente (vazios por último)
    bloco_novo = bloco_novo.sort_values(
        by=['UO_COD', 'Anular'], ascending=[True, True], na_position='last'
    ).reset_index(drop=True)

    # 4) Decide entre apêndice (mesma data) ou conferência novo (data diferente)
    info = encontrar_conferencia(pasta_conferencia)
    conferencia_antigo = None
    base_existente     = None
    sequencial         = 1

    if info is not None:
        conferencia_antigo, dia_arq, mes_arq = info
        mesma_data = (dia_arq == hoje.day and mes_arq == hoje.month)
        if mesma_data:
            base_existente = pd.read_excel(conferencia_antigo)
            base_existente.columns = [str(c).strip() for c in base_existente.columns]
            seq_max    = pd.to_numeric(base_existente['Execução'], errors='coerce').max()
            sequencial = int(seq_max) + 1 if pd.notna(seq_max) else 1
            print(f'Mesma data: apêndice com Execução = {sequencial}')
        else:
            print(f'Data diferente ({dia_arq:02d}/{mes_arq:02d}): novo conferência (Execução = 1)')
    else:
        print('Nenhum conferência anterior encontrado: novo conferência (Execução = 1)')

    bloco_novo.insert(0, 'Execução', sequencial)

    # 5) Monta o conferência final
    if base_existente is not None:
        base_existente = base_existente.reindex(columns=COLUNAS_CONFERENCIA)
        final = pd.concat([base_existente, bloco_novo], ignore_index=True)
    else:
        final = bloco_novo.reindex(columns=COLUNAS_CONFERENCIA)

    # 6) Normaliza colunas de código para inteiro (vazio continua vazio)
    for col in COLUNAS_CODIGO:
        if col in final.columns:
            final[col] = pd.to_numeric(final[col], errors='coerce').astype('Int64')

    # 7) Salva o consolidado em ROBO_IPU2_PYTHON
    pasta_destino = resolver_pasta(ROBO_IPU2_PYTHON)
    os.makedirs(pasta_destino, exist_ok=True)
    destino_final = os.path.join(pasta_destino, nome_saida)
    caminho_tmp   = os.path.join(pasta_destino, '_tmp_conferencia.xlsx')

    with pd.ExcelWriter(caminho_tmp, engine='openpyxl') as writer:
        final.to_excel(writer, sheet_name=ABA_SAIDA, index=False)

    os.replace(caminho_tmp, destino_final)
    print(f'Salvo: {destino_final} ({len(final)} linhas no total)')

    # 8) SÓ AGORA esvazia a pasta CONFERENCIA e move as origens
    if conferencia_antigo is not None:
        if base_existente is not None:
            if os.path.abspath(conferencia_antigo) != os.path.abspath(destino_final):
                try:
                    os.remove(conferencia_antigo)
                    print('Conferência de hoje consolidado e removido da pasta de origem.')
                except OSError as e:
                    print(f'[aviso] Consolidado salvo, mas não consegui remover o original: {e}')
        else:
            mover_com_seguranca(conferencia_antigo, REALIZADOS_CONFERENCIA)
            print(f'Conferência antigo arquivado em: {REALIZADOS_CONFERENCIA}')

    for caminho in arquivos_origem:
        mover_com_seguranca(caminho, REALIZADOS)
    print(f'{len(arquivos_origem)} arquivo(s) de origem movidos para: {REALIZADOS}')


if __name__ == '__main__':
    main()