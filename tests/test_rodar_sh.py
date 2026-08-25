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


def test_segunda_execucao_simultanea_sai_com_codigo_10(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    montar_repo_falso(repo)

    primeira = subprocess.Popen(['bash', str(repo / 'rodar.sh')],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    time.sleep(1.5)  # tempo de a primeira pegar o lock e entrar no sleep

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
