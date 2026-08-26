"""Utilidades de baixo nivel do emulador 3270."""

from py3270 import CommandError


def esperar_teclado(em, segundos=10):
    """Espera o mainframe destravar o teclado antes de digitar.

    O py3270 sobe o emulador com unlockDelay desligado. O comentario no proprio
    codigo dele explica por que isso e perigoso: existem hosts que liberam o
    teclado antes de terem processado o comando, e a espera de 350ms existe
    para contornar exatamente isso — mas o py3270 a desativa "por performance".

    O SIAFI e um desses hosts. Em 26/08/2026 uma execucao morreu no meio da
    linha 18 com 'Keyboard locked': o wait_for_field() tinha passado, e o
    mainframe voltou a travar antes do fill_field seguinte.

    Se o teclado nao destravar no prazo, segue mesmo assim: o fill_field
    seguinte falha com a mensagem clara do py3270, e a linha e marcada para
    conferencia humana em vez de ficar em estado ambiguo.
    """
    try:
        em.exec_command(f'Wait({segundos}, Unlock)'.encode('ascii'))
    except CommandError:
        pass
