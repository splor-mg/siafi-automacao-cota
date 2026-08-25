import os
import shutil
import subprocess
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def montar_repo_falso(destino):
    """Cria a estrutura minima que o rodar.sh espera, com um login.py de mentira."""
    os.makedirs(destino / 'siafi_automacao', exist_ok=True)
    os.makedirs(destino / 'venv' / 'bin', exist_ok=True)
    os.makedirs(destino / 'data', exist_ok=True)

    shutil.copy(os.path.join(RAIZ, 'rodar.sh'), destino / 'rodar.sh')
    os.chmod(destino / 'rodar.sh', 0o755)

    # venv/bin/activate vazio: 'source' num arquivo vazio funciona.
    (destino / 'venv' / 'bin' / 'activate').write_text('')
    # 5 segundos: tempo folgado para a segunda invocacao tentar o lock enquanto
    # a primeira ainda esta rodando, sem deixar o teste lento.
    (destino / 'siafi_automacao' / 'login.py').write_text(
        'import time\nprint("robo falso rodando")\ntime.sleep(5)\n')

    subprocess.run(['git', 'init', '-q', '-b', 'main'], cwd=destino, check=True)
    subprocess.run(['git', 'config', 'user.email', 'teste@teste'], cwd=destino, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Teste'], cwd=destino, check=True)
    subprocess.run(['git', 'add', '-A'], cwd=destino, check=True)
    subprocess.run(['git', 'commit', '-q', '-m', 'inicial'], cwd=destino, check=True)


def esperar_lock(repo, timeout=20):
    """Espera a execucao pegar o lock, em vez de dormir um tempo fixo.

    O rodar.sh grava .ultima_execucao logo depois de adquirir o lock, entao a
    existencia desse arquivo e o sinal exato de que a execucao comecou.
    """
    limite = time.time() + timeout
    marcador = repo / 'data' / '.ultima_execucao'
    while time.time() < limite:
        if marcador.exists():
            return
        time.sleep(0.05)
    raise AssertionError('a execucao nao pegou o lock dentro do timeout')


def test_segunda_execucao_simultanea_sai_com_codigo_10(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    montar_repo_falso(repo)

    primeira = subprocess.Popen(['bash', str(repo / 'rodar.sh')],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    esperar_lock(repo)  # tempo de a primeira pegar o lock e entrar no sleep

    segunda = subprocess.run(['bash', str(repo / 'rodar.sh')],
                             capture_output=True, text=True)
    assert segunda.returncode == 10

    assert primeira.wait(timeout=30) == 0


def test_execucao_isolada_termina_com_sucesso_e_gera_log(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    montar_repo_falso(repo)

    r = subprocess.run(['bash', str(repo / 'rodar.sh')], capture_output=True, text=True)
    assert r.returncode == 0

    logs = list((repo / 'data' / 'logs').glob('robo-*.log'))
    assert len(logs) == 1
    conteudo = logs[0].read_text(encoding='utf-8')
    assert 'robo falso rodando' in conteudo
    # Sem remoto configurado, o git pull falha e o aviso tem que aparecer.
    assert 'Nao foi possivel atualizar' in conteudo


def test_propaga_codigo_de_erro_do_login(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    montar_repo_falso(repo)
    (repo / 'siafi_automacao' / 'login.py').write_text('raise SystemExit(3)\n')

    r = subprocess.run(['bash', str(repo / 'rodar.sh')], capture_output=True, text=True)
    assert r.returncode == 3


def test_lock_e_liberado_quando_a_execucao_anterior_morre(tmp_path):
    """Um .robo.lock orfao nao pode bloquear execucoes futuras para sempre.

    Matar so o processo 'bash rodar.sh' nao mata o 'login.py' que ele
    disparou: o flock e' associado ao file description, herdado pelos
    processos filhos (o subshell do pipe, o tee e o proprio python), entao
    eles continuam segurando o lock depois que o pai morre. Isso e'
    proposital (ver comentario "Nao faca" sobre nao mexer no fd 9 herdado
    pelo python: se o robo estiver no meio de uma operacao real no SIAFI,
    matar so o wrapper e deixar o lock cair na hora seria pior do que deixar
    o processo real terminar sozinho e so entao liberar). Por isso o teste
    espera ate um timeout generoso, em vez de checar uma unica vez logo apos
    o kill: o lock so fica livre quando o login.py orfao (aqui, o dublê que
    dorme 5s) efetivamente termina.
    """
    repo = tmp_path / 'repo'
    repo.mkdir()
    montar_repo_falso(repo)

    primeira = subprocess.Popen(['bash', str(repo / 'rodar.sh')],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    esperar_lock(repo)
    primeira.kill()
    primeira.wait(timeout=10)

    limite = time.time() + 20
    segunda = subprocess.run(['bash', str(repo / 'rodar.sh')],
                             capture_output=True, text=True, timeout=60)
    while segunda.returncode == 10 and time.time() < limite:
        time.sleep(0.2)
        segunda = subprocess.run(['bash', str(repo / 'rodar.sh')],
                                 capture_output=True, text=True, timeout=60)
    assert segunda.returncode == 0


def test_respeita_caminhos_vindos_do_ambiente(tmp_path):
    """E assim que o bot invoca o script: com ROBO_LOG e RELATO_ARQUIVO ja
    definidos, para saber de antemao onde ler o relato da execucao."""
    repo = tmp_path / 'repo'
    repo.mkdir()
    montar_repo_falso(repo)

    log = tmp_path / 'meu.log'
    relato = tmp_path / 'meu.jsonl'
    ambiente = dict(os.environ, ROBO_LOG=str(log), RELATO_ARQUIVO=str(relato))

    r = subprocess.run(['bash', str(repo / 'rodar.sh')], env=ambiente,
                       capture_output=True, text=True, timeout=60)

    assert r.returncode == 0
    assert log.exists()
    assert 'robo falso rodando' in log.read_text(encoding='utf-8')
    assert (repo / 'data' / '.ultima_execucao').read_text().splitlines() == [
        str(log), str(relato)]


def test_registra_os_caminhos_da_execucao(tmp_path):
    """O comando /log do bot depende desse arquivo para achar o log."""
    repo = tmp_path / 'repo'
    repo.mkdir()
    montar_repo_falso(repo)

    subprocess.run(['bash', str(repo / 'rodar.sh')], capture_output=True,
                   text=True, timeout=60)

    linhas = (repo / 'data' / '.ultima_execucao').read_text().splitlines()
    assert len(linhas) == 2
    assert linhas[0].endswith('.log')
    assert linhas[1].endswith('.jsonl')
    assert os.path.exists(linhas[0])


def test_venv_ausente_aborta_com_mensagem_clara(tmp_path):
    """Sem essa checagem o script seguiria e rodaria o login.py com o Python do
    sistema, contra o SIAFI de producao."""
    repo = tmp_path / 'repo'
    repo.mkdir()
    montar_repo_falso(repo)
    (repo / 'venv' / 'bin' / 'activate').unlink()

    r = subprocess.run(['bash', str(repo / 'rodar.sh')], capture_output=True,
                       text=True, timeout=60)

    assert r.returncode == 1
    assert 'ambiente virtual' in r.stdout
