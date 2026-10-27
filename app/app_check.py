# -*- coding: utf-8 -*-
"""Verifica el contraste de TODOS los pares color/fondo que la app usa de verdad.

Existe por un error concreto: verifique "texto contra fondo", dio bien, y la app
igual quedo ilegible — porque los bordes de los chips, los placeholders y las
etiquetas de las cifras usan OTROS pares que no mire. Azul sobre azul.

Falla con codigo != 0 si algo baja de 4.5 (el minimo para leer comodo).
"""
import re, sys, io, os

HERE = os.path.dirname(os.path.abspath(__file__))
MIN = 4.5
MIN_GRANDE = 3.0        # texto grande (>=24px o bold >=19px) admite 3.0


def lum(h):
    h = h.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= .03928 else ((c + .055) / 1.055) ** 2.4
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def mezclar(color, fondo, alfa):
    """El color REAL de un texto con opacity: se compone contra su fondo.

    Hace falta porque varias etiquetas de la app no se pintan con un token de
    la paleta sino con un token AL 65% (td.dato .u, por ejemplo). Medir el
    token puro da un numero mejor que el que se ve de verdad, y es justo el
    tipo de texto que quedo ilegible la primera vez."""
    c, f = color.lstrip("#"), fondo.lstrip("#")
    out = []
    for i in (0, 2, 4):
        a, b = int(c[i:i + 2], 16), int(f[i:i + 2], 16)
        out.append(round(a * alfa + b * (1 - alfa)))
    return "#%02x%02x%02x" % tuple(out)


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + .05) / (min(la, lb) + .05)


# (que color, sobre que fondo, donde se usa, si es texto grande[, opacidad])
PARES = [
    ("fuerte", "fondo",  "texto principal de la tabla",        False),
    ("medio",  "fondo",  "tema (serif), encabezados, footer",  False),
    ("suave",  "fondo",  "canal, metadata, placeholder",       False),
    ("acento", "fondo",  "numero de catalogo, estrellas",      False),
    ("acento", "fondo",  "cifras y conteo (grande)",           True),
    ("fuerte", "sobre",  "texto dentro de inputs y al hover",  False),
    ("medio",  "sobre",  "tema al pasar el mouse",             False),
    ("suave",  "sobre",  "placeholder dentro del input",       False),
    ("stxt",   "acento", "titulo y botones sobre el bloque",   False),
    ("stxt",   "acento2","playlists y sello EN DISCO",         False),
    ("barratxt","barra",  "etiquetas de las cifras",            False),
    ("barranum","barra",  "numeros de las cifras",              True),
    ("fondo",  "acento", "chip activo",                        False),
    ("suave",  "fondo",  "unidad de las cifras (views/bpm)",   False),
    ("suave",  "sobre",  "unidad de las cifras al hover",      False),
]


def main():
    css = io.open(os.path.join(HERE, "app_css.py"), encoding="utf-8").read()
    temas = re.findall(r'body\[data-t="(\w+)"\]\{([^}]+)\}', css)
    if not temas:
        print("no encontre ninguna paleta"); return 1
    fallos = []
    for nombre, bloque in temas:
        v = dict(re.findall(r"--(\w+):\s*(#[0-9a-fA-F]{6})", bloque))
        print("\n%s" % nombre.upper())
        print("  %-36s %6s  %s" % ("par", "ratio", "estado"))
        print("  " + "-" * 56)
        for par in PARES:
            a, b, donde, grande = par[:4]
            alfa = par[4] if len(par) > 4 else 1.0
            if a not in v or b not in v:
                continue
            color = v[a] if alfa >= 1 else mezclar(v[a], v[b], alfa)
            r = ratio(color, v[b])
            lim = MIN_GRANDE if grande else MIN
            ok = r >= lim
            if not ok:
                fallos.append((nombre, donde, round(r, 1), lim))
            print("  %-36s %6.1f  %s" % (donde[:36], r, "ok" if ok else "FALLA (min %.1f)" % lim))
    print()
    if fallos:
        print("%d FALLOS:" % len(fallos))
        for t, d, r, lim in fallos:
            print("   [%s] %s -> %.1f, necesita %.1f" % (t, d, r, lim))
        return 1
    print("las %d paletas pasan todos los pares" % len(temas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
