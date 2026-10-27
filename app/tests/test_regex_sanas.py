# -*- coding: utf-8 -*-
"""El test que hubiera evitado el peor bug del proyecto.

El 27-oct-2026 aparecieron CINCUENTA regex rotas. Se habian escrito a traves
de un heredoc de bash y cada "\\b" (borde de palabra) llego convertido en el
caracter 8, que es el retroceso. Los filtros de hiphop, remix, reggae y 6/8
dejaron de matchear nada.

Lo grave no fue el bug: fue que no se veia. El caracter 8 no se imprime, asi
que los patrones se leian perfectos en pantalla y fallaban en silencio durante
dias, dejando pasar basura a las tandas.

Este test mira TODAS las regex compiladas de los modulos vivos y falla si
alguna tiene un caracter de control. Es barato y cubre una clase entera de
error, no un caso.
"""
import re

import cavar
import criterios
import crate_server
import veta

MODULOS = [criterios, veta, cavar, crate_server]

# lo que nunca puede aparecer dentro de un patron escrito a mano
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def regex_del_modulo(mod):
    """Todas las regex compiladas que cuelgan del modulo, incluso dentro de
    diccionarios (VETAS guarda las suyas asi)."""
    for nombre in dir(mod):
        valor = getattr(mod, nombre)
        if isinstance(valor, re.Pattern):
            yield "%s.%s" % (mod.__name__, nombre), valor
        elif isinstance(valor, dict):
            for clave, sub in valor.items():
                if isinstance(sub, re.Pattern):
                    yield "%s.%s[%r]" % (mod.__name__, nombre, clave), sub
                elif isinstance(sub, dict):
                    for k2, s2 in sub.items():
                        if isinstance(s2, re.Pattern):
                            yield "%s.%s[%r][%r]" % (mod.__name__, nombre,
                                                     clave, k2), s2


def test_hay_regex_que_revisar():
    """Si esto falla, el test de arriba no esta mirando nada util."""
    total = sum(1 for _ in (r for m in MODULOS for r in regex_del_modulo(m)))
    assert total >= 15, "esperaba muchas mas regex que revisar, encontre %d" % total


def test_ninguna_regex_tiene_caracteres_de_control():
    rotas = []
    for mod in MODULOS:
        for nombre, patron in regex_del_modulo(mod):
            m = CONTROL.search(patron.pattern)
            if m:
                rotas.append("%s  tiene chr(%d) en la posicion %d"
                             % (nombre, ord(m.group()), m.start()))
    assert not rotas, (
        "regex corrompidas (seguro se escribieron por heredoc):\n  "
        + "\n  ".join(rotas))


def test_el_borde_de_palabra_realmente_funciona():
    """No alcanza con que no haya basura: el \\b tiene que hacer su trabajo.

    Si un \\b se perdiera, 'dub' matchearia dentro de 'double' y se irian a la
    basura temas que no son dub.
    """
    assert criterios.SIN_VOZ.search("Marvin Gaye - Inner City Blues (Dub)")
    assert not criterios.SIN_VOZ.search("The Doubles - Double Trouble")
