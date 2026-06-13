"""
Consolidação do "Conferencia arquivo robo".

Fluxo:

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
# ========================================================


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
            return

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
