"""O login.py inteiro, de ponta a ponta, sem SIAFI e sem OneDrive.

O fluxo de produção roda sob `if __name__ == "__main__"`, então nenhum outro
teste o exercita. Aqui ele roda de verdade, como subprocesso, numa cópia do
código em pasta temporária: o py3270 é trocado por um emulador de mentira (a
pasta do script vem antes do site-packages no sys.path) e o ONEDRIVE_BASE
aponta para pastas vazias. O SIAFI_HOST é inválido de propósito: se o emulador
de mentira deixasse de ser usado, o de verdade não teria aonde conectar.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

RAIZ = Path(__file__).resolve().parent.parent

INTERROMPIDA = 'INTERROMPIDA - VERIFICAR NO SIAFI'

EMULADOR_FALSO = '''
"""Emulador de mentira: responde como o SIAFI no caminho feliz."""
import os
import time

_dormir_de_verdade = time.sleep
time.sleep = lambda segundos: None      # as esperas do robo nao interessam aqui


class CommandError(Exception):
    pass


class _Status:
    keyboard = b'E'
    cursor_row = b'15'
    cursor_col = b'15'


class Emulator:
    status = _Status()

    def __init__(self, visible=False):
        print('EMULADOR DE MENTIRA EM USO')
        self.travar = os.getenv('FALSO_TRAVAR') == '1'
        self.parar_em = os.getenv('FALSO_PARAR_EM')

    def connect(self, host):
        pass

    def wait_for_field(self):
        pass

    def string_found(self, y, x, texto):
        return texto in ('Logon executado com sucesso', 'Unidade Executora')

    def string_get(self, y, x, n):
        if y == 1:
            return os.getenv('FALSO_RETORNO', '0011-REGISTRO EFETUADO.').ljust(n)
        return ''.ljust(n)

    def fill_field(self, y, x, texto, n):
        # (16, 16) e (16, 17): o campo da acao, ja no meio da operacao.
        if (y, x) not in ((16, 16), (16, 17)):
            return
        if self.travar:
            raise CommandError('Keyboard locked')
        if self.parar_em:
            with open(self.parar_em, 'w') as f:
                f.write('parado')
            _dormir_de_verdade(120)

    def send_enter(self):
        pass

    def send_pf(self, n):
        pass

    def exec_command(self, cmd):
        pass

    def terminate(self):
        pass
'''

COLUNAS_ORIGEM = ['UO_COD', 'Grupo', 'IAG', 'Fonte', 'IPU', 'Ação', 'GLOBAL',
                  'AMARRADO', 'Anular', 'Aprovar', 'UO Financiadora']
COLUNAS_CONFERENCIA = ['Execução', 'Pedido'] + COLUNAS_ORIGEM + ['Progresso']

ANULAR_GLOBAL = [1501, 3, 0, 10, 1, 4485, 'x', None, 250.0, None, None]
APROVAR_AMARRADO = [1501, 3, 0, 60, 2, 4485, None, '0308', None, 45971.84, 1251]


def _planilha(caminho, cabecalho, linhas):
    livro = Workbook()
    aba = livro.active
    aba.append(cabecalho)
    for linha in linhas:
        aba.append(linha)
    livro.save(caminho)


class Robo:
    """Cópia do robô em pasta temporária, com o OneDrive de mentira."""

    def __init__(self, tmp_path):
        self.raiz = tmp_path / 'robo'
        shutil.copytree(RAIZ / 'siafi_automacao', self.raiz / 'siafi_automacao',
                        ignore=shutil.ignore_patterns('__pycache__'))
        (self.raiz / 'siafi_automacao' / 'py3270.py').write_text(
            EMULADOR_FALSO, encoding='utf-8')

        self.onedrive = tmp_path / 'onedrive'
        self.remanejamentos = self.onedrive / 'Remanejamentos'
        self.entrada = self.onedrive / 'Robo (IPU 2)' / 'Python'
        self.conferencia = self.onedrive / 'Conferencia arquivo robo'
        self.realizados = self.onedrive / 'Realizados'
        for pasta in (self.remanejamentos, self.onedrive / 'Remanejamentos (SEGOV)',
                      self.entrada, self.conferencia, self.realizados):
            pasta.mkdir(parents=True)
        self.local = tmp_path / 'local'
        self.relato = tmp_path / 'relato.jsonl'
        self.parado = tmp_path / 'parado'

    def ambiente(self, **extra):
        # Ambiente montado do zero: nada do .env de produção entra aqui.
        ambiente = {
            'PATH': os.environ['PATH'],
            'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1',
            'ONEDRIVE_BASE': str(self.onedrive), 'PASTA_LOCAL': str(self.local),
            'SISTEMA': 'sist', 'USUARIO': 'usuario', 'SENHA': 'segredo',
            'UNIDADE_EXECUTORA': '1234567',
            'SIAFI_HOST': 'host.invalido.exemplo', 'SIAFI_VISIVEL': 'false',
            'CONEXAO_TENTATIVAS': '1', 'CONEXAO_ESPERA_SEGUNDOS': '0',
            'MOVER_TENTATIVAS': '1', 'MOVER_ESPERA_SEGUNDOS': '0',
            'RELATO_ARQUIVO': str(self.relato),
        }
        ambiente.update(extra)
        return ambiente

    def planilha_de_origem(self, nome, linhas):
        _planilha(self.remanejamentos / nome, COLUNAS_ORIGEM, linhas)

    def rodar(self, **extra):
        return subprocess.run([sys.executable, 'siafi_automacao/login.py'],
                              cwd=self.raiz, env=self.ambiente(**extra),
                              capture_output=True, text=True, timeout=120)

    def iniciar_e_parar_no_meio_da_linha(self):
        """Sobe o robô e espera ele chegar ao meio da primeira operação."""
        proc = subprocess.Popen(
            [sys.executable, 'siafi_automacao/login.py'], cwd=self.raiz,
            env=self.ambiente(FALSO_PARAR_EM=str(self.parado)),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        limite = time.time() + 60
        while not self.parado.exists():
            assert proc.poll() is None, proc.stdout.read().decode()
            assert time.time() < limite, 'o robô não chegou à primeira linha'
            time.sleep(0.05)
        return proc

    def progresso(self):
        """Coluna Progresso do conferência devolvido à pasta de conferência."""
        arquivos = list(self.conferencia.glob('*.xlsx'))
        assert len(arquivos) == 1, arquivos
        aba = load_workbook(arquivos[0]).worksheets[0]
        cabecalho = [c.value for c in aba[1]]
        coluna = cabecalho.index('Progresso') + 1
        return [aba.cell(row=r, column=coluna).value
                for r in range(2, aba.max_row + 1)]

    def eventos(self, tipo):
        linhas = self.relato.read_text(encoding='utf-8').splitlines()
        return [e for e in map(json.loads, linhas) if e['tipo'] == tipo]

    def sobrou_na_pasta_local(self):
        return list(self.local.glob('*')) if self.local.exists() else []


@pytest.fixture
def robo(tmp_path):
    return Robo(tmp_path)


def test_execucao_completa_grava_ok_e_devolve_a_planilha(robo):
    robo.planilha_de_origem('1501-2026-0099 SEPLAG.xlsx',
                            [ANULAR_GLOBAL, APROVAR_AMARRADO])

    r = robo.rodar()

    assert r.returncode == 0, r.stdout + r.stderr
    assert 'EMULADOR DE MENTIRA EM USO' in r.stdout
    assert robo.progresso() == ['Ok', 'Ok']
    assert robo.sobrou_na_pasta_local() == []
    assert (robo.realizados / 'Remanejamentos realizados'
            / '1501-2026-0099 SEPLAG.xlsx').exists()
    assert len(robo.eventos('planilha_final')) == 1


def test_teclado_travado_marca_a_linha_e_imprime_a_tela(robo):
    robo.planilha_de_origem('1501-2026-0099 SEPLAG.xlsx',
                            [ANULAR_GLOBAL, APROVAR_AMARRADO])

    r = robo.rodar(FALSO_TRAVAR='1', FALSO_RETORNO='0139- RECUSADO NA PRIMEIRA TELA')

    assert r.returncode == 1
    assert robo.progresso() == [INTERROMPIDA, None]
    assert robo.sobrou_na_pasta_local() == []
    assert 'TELA DO SIAFI' in r.stdout
    assert any('Na tela do SIAFI estava: 0139- RECUSADO NA PRIMEIRA TELA' in e['texto']
               for e in robo.eventos('erro'))


@pytest.mark.parametrize('sinal', [signal.SIGTERM, signal.SIGHUP])
def test_encerramento_de_fora_no_meio_da_linha_devolve_a_planilha(robo, sinal):
    """SIGTERM é o serviço do bot sendo reiniciado (ou a máquina desligando);
    SIGHUP é a janela preta do robo.bat sendo fechada. Sem tratar o sinal o
    Python morre na hora: a planilha fica órfã na pasta local, de onde nenhuma
    execução seguinte a recupera, e a linha em curso fica sem marca nenhuma."""
    robo.planilha_de_origem('1501-2026-0099 SEPLAG.xlsx',
                            [ANULAR_GLOBAL, APROVAR_AMARRADO])
    proc = robo.iniciar_e_parar_no_meio_da_linha()

    proc.send_signal(sinal)
    proc.wait(timeout=60)

    assert proc.returncode == 128 + sinal
    assert robo.progresso() == [INTERROMPIDA, None]
    assert robo.sobrou_na_pasta_local() == []
    assert any('encerrada de fora' in e['texto'] for e in robo.eventos('erro'))


def test_saida_morta_nao_impede_o_resgate_da_planilha(robo):
    """No reinício do serviço o tee que grava o log morre junto com o robô.
    Um print que falha no meio do tratamento não pode custar a planilha."""
    robo.planilha_de_origem('1501-2026-0099 SEPLAG.xlsx',
                            [ANULAR_GLOBAL, APROVAR_AMARRADO])
    proc = robo.iniciar_e_parar_no_meio_da_linha()

    proc.stdout.close()                 # ninguém mais lê a saída do robô
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=60)

    assert robo.progresso() == [INTERROMPIDA, None]
    assert robo.sobrou_na_pasta_local() == []


def test_falha_ao_organizar_realizados_nao_vira_falha_da_execucao(robo):
    """A planilha já foi processada e devolvida; arrumar a pasta Realizados é
    faxina. Se ela falhar, o grupo recebia 'FALHOU (código 1)' numa execução
    em que todas as linhas tinham dado certo."""
    robo.planilha_de_origem('1501-2026-0099 SEPLAG.xlsx', [ANULAR_GLOBAL])
    # Um ARQUIVO com o nome da pasta de destino: o makedirs dela falha.
    (robo.realizados / 'Remanejamentos realizados').write_text('no caminho')

    r = robo.rodar()

    assert r.returncode == 0, r.stdout + r.stderr
    assert robo.progresso() == ['Ok']
    assert len(robo.eventos('planilha_final')) == 1
    assert robo.eventos('erro') == []
    assert any('Realizados' in e['texto'] for e in robo.eventos('aviso'))


def test_linha_com_dado_invalido_e_marcada_e_as_demais_seguem(robo):
    """Conferência editado à mão com um campo ilegível. A conversão estourava
    antes de a linha ser marcada: a execução caía, a linha continuava pendente
    e toda execução seguinte parava nela, sem nunca chegar às de baixo."""
    _planilha(robo.conferencia / 'Conferencia arquivo robo 01.01.xlsx',
              COLUNAS_CONFERENCIA, [
                  [1, 'a mão', 1501, 3, 0, 'abc', 1, 4485, 'x', None, 250.0, None, None, None],
                  [1, 'a mão'] + ANULAR_GLOBAL + [None],
              ])

    r = robo.rodar()

    assert r.returncode == 0, r.stdout + r.stderr
    assert robo.progresso() == ['Linha com dado inválido na planilha', 'Ok']
    puladas = robo.eventos('linha_pulada')
    assert [e['linha'] for e in puladas] == [2]
    assert 'abc' in puladas[0]['texto']


def test_consolidacao_que_parou_na_arrumacao_e_retomada_e_vai_ao_siafi(robo):
    """A execução anterior salvou o consolidado e arquivou a planilha, mas
    abortou antes de terminar a arrumação (OneDrive travado). Nesta, não há
    nada novo em Remanejamentos: o consolida.py termina a arrumação e o
    login.py processa as linhas que já estavam prontas — em vez de elas
    ficarem para sempre num arquivo esquecido na pasta de entrada."""
    _planilha(robo.entrada / 'Conferencia arquivo robo 02.01.xlsx',
              COLUNAS_CONFERENCIA, [[1, 'B'] + ANULAR_GLOBAL + [None]])
    _planilha(robo.realizados / 'B.xlsx', COLUNAS_ORIGEM, [ANULAR_GLOBAL])
    # O conferência de um dia anterior ainda está na pasta: era ele que o
    # OneDrive segurava.
    _planilha(robo.conferencia / 'Conferencia arquivo robo 01.01.xlsx',
              COLUNAS_CONFERENCIA, [[1, 'A'] + ANULAR_GLOBAL + ['Ok']])

    r = robo.rodar()

    assert r.returncode == 0, r.stdout + r.stderr
    assert [p.name for p in robo.conferencia.glob('*.xlsx')] == [
        'Conferencia arquivo robo 02.01.xlsx']
    assert robo.progresso() == ['Ok']
    assert (robo.realizados / 'Conferencia Robo Realizados'
            / 'Conferencia arquivo robo 01.01.xlsx').exists()
    assert any('retomada' in e['texto'].lower() for e in robo.eventos('planilha'))


def test_servico_reiniciado_no_meio_da_linha_pelo_rodar_sh(robo, tmp_path):
    """O cenário de produção por inteiro: o rodar.sh de verdade chamando o
    login.py de verdade, e o SIGTERM chegando a todos os processos de uma vez,
    como o systemd faz ao reiniciar o serviço do bot durante uma execução."""
    shutil.copy(RAIZ / 'rodar.sh', robo.raiz / 'rodar.sh')
    ativar = robo.raiz / 'venv' / 'bin' / 'activate'
    ativar.parent.mkdir(parents=True)
    ativar.write_text(f'export PATH="{Path(sys.executable).parent}:$PATH"\n')
    log = tmp_path / 'robo.log'
    robo.planilha_de_origem('1501-2026-0099 SEPLAG.xlsx',
                            [ANULAR_GLOBAL, APROVAR_AMARRADO])

    proc = subprocess.Popen(
        ['bash', str(robo.raiz / 'rodar.sh')],
        env=robo.ambiente(FALSO_PARAR_EM=str(robo.parado), ROBO_LOG=str(log),
                          SIAFI_LOCK=str(tmp_path / 'robo.lock')),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    limite = time.time() + 60
    while not robo.parado.exists():
        assert proc.poll() is None and time.time() < limite, log.read_text()
        time.sleep(0.05)

    os.killpg(proc.pid, signal.SIGTERM)
    proc.wait(timeout=30)

    # O bash morre na hora; o login.py ainda leva um instante devolvendo a planilha.
    limite = time.time() + 30
    while 'devolvida para' not in log.read_text(encoding='utf-8'):
        assert time.time() < limite, log.read_text(encoding='utf-8')
        time.sleep(0.05)
    assert robo.progresso() == [INTERROMPIDA, None]
    assert robo.sobrou_na_pasta_local() == []
    assert 'encerrada de fora' in log.read_text(encoding='utf-8')
