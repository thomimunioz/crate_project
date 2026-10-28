# -*- coding: utf-8 -*-
"""Dibuja el icono de CRATE: un disco saliendo de un cajon.

Los colores salen de la paleta "for you" (Tatsuro Yamashita / Hiroshi Nagai),
que es la que Thomas eligio para la app: azul profundo, crema, rojo y el azul
de acento. El icono y la app tienen que verse de la misma familia.

Lo dificil de un icono no es que quede lindo a 256: es que a 16 pixeles —el
tamaño real en la barra de tareas— siga siendo reconocible. Por eso la forma
es simple y de alto contraste: un circulo crema sobre azul, con el punto rojo
del centro. Todo lo que es detalle (surcos, listones del cajon) se dibuja solo
en los tamaños grandes, donde hay lugar.

    python icono.py            genera crate.ico + las pruebas en PNG
"""
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(HERE)

AZUL = (16, 50, 79)         # --fuerte
CREMA = (247, 246, 233)     # --fondo
ROJO = (214, 52, 58)        # --estrella
ACENTO = (15, 102, 173)     # --acento
MEDIO = (47, 81, 105)       # --medio

TAMANOS = [256, 128, 64, 48, 32, 24, 16]


def redondeado(d, caja, radio, color):
    d.rounded_rectangle(caja, radius=radio, fill=color)


def dibujar(lado):
    """Un icono de `lado` pixeles, dibujado 4x y achicado.

    El arte cambia segun el tamaño, que es para lo que existe el formato .ico:
      * grande  disco dentro del cajon, con surcos y separadores
      * 32      disco y una banda fina de cajon, sin detalle
      * chico   SOLO el disco, grande. A 16 pixeles el cajon se come la mitad
                del cuadro y lo unico que se distingue es un borron; el disco
                solo, en cambio, sigue leyendose.

    Descartado en el camino: disco crema con surcos sobre azul (parecia un
    blanco de tiro, y un vinilo real es oscuro con la etiqueta de color) y un
    brillo hecho con pieslice (quedaba una porcion de pizza).
    """
    E = 4
    S = lado * E
    grande = lado >= 48
    medio = lado >= 32
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # fondo crema: en una barra de tareas oscura un icono claro se recorta
    # solo, y es el mismo fondo de la app
    redondeado(d, (0, 0, S - 1, S - 1), int(S * 0.22), CREMA)

    if medio:
        cx, cy, r = S * 0.50, S * 0.44, S * 0.30
        top = S * 0.72
    else:
        cx, cy, r = S * 0.50, S * 0.50, S * 0.39
        top = None

    # --- el cajon detras del disco ---
    if top:
        redondeado(d, (0, top, S - 1, S - 1), int(S * 0.22), ACENTO)
        d.rectangle((0, top, S - 1, top + S * 0.14), fill=ACENTO)

    # --- el disco ---
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=AZUL)

    if grande:
        for k in (0.90, 0.80, 0.70):
            rr = r * k
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr),
                      outline=MEDIO, width=max(1, int(S * 0.007)))
        # brillo: un arco fino arriba a la izquierda, como la luz sobre el
        # vinilo. Un arco, no una cuña rellena.
        d.arc((cx - r * .93, cy - r * .93, cx + r * .93, cy + r * .93),
              200, 245, fill=(86, 122, 150), width=max(2, int(S * 0.028)))

    # etiqueta roja y agujero: lo que hace leer "disco" al instante
    re = r * (0.40 if medio else 0.46)
    d.ellipse((cx - re, cy - re, cx + re, cy + re), fill=ROJO)
    rp = r * 0.09
    d.ellipse((cx - rp, cy - rp, cx + rp, cy + rp), fill=CREMA)

    # el frente del cajon pasa POR ENCIMA de la base del disco: eso es lo que
    # dice "esta metido adentro" y no "apoyado arriba"
    if top:
        frente = S * 0.845
        redondeado(d, (0, frente, S - 1, S - 1), int(S * 0.22), ACENTO)
        d.rectangle((0, frente, S - 1, frente + S * 0.08), fill=ACENTO)
        if grande:
            for fx in (0.33, 0.67):
                x = S * fx
                d.line((x, frente + S * 0.028, x, S * 0.955),
                       fill=CREMA, width=max(1, int(S * 0.022)))

    return img.resize((lado, lado), Image.LANCZOS)


def dibujar_cerrar(lado):
    """Variante apagada, para el acceso directo que cierra la app.

    Mismo objeto para que se lean como pareja, pero sin vida: el disco en
    gris, la etiqueta sin rojo y el cajon apagado. Asi se distinguen de un
    vistazo en la barra sin tener que leer el nombre.
    """
    E = 4
    S = lado * E
    grande = lado >= 48
    medio = lado >= 32
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    GRIS = (150, 152, 148)
    GRIS_F = (96, 99, 96)
    FONDO = (231, 230, 219)

    redondeado(d, (0, 0, S - 1, S - 1), int(S * 0.22), FONDO)

    if medio:
        cx, cy, r = S * 0.50, S * 0.44, S * 0.30
        top = S * 0.72
    else:
        cx, cy, r = S * 0.50, S * 0.50, S * 0.39
        top = None

    if top:
        redondeado(d, (0, top, S - 1, S - 1), int(S * 0.22), GRIS)
        d.rectangle((0, top, S - 1, top + S * 0.14), fill=GRIS)

    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GRIS_F)
    if grande:
        for k in (0.90, 0.80, 0.70):
            rr = r * k
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr),
                      outline=GRIS, width=max(1, int(S * 0.007)))

    re = r * (0.40 if medio else 0.46)
    d.ellipse((cx - re, cy - re, cx + re, cy + re), fill=GRIS)
    rp = r * 0.09
    d.ellipse((cx - rp, cy - rp, cx + rp, cy + rp), fill=FONDO)

    if top:
        frente = S * 0.845
        redondeado(d, (0, frente, S - 1, S - 1), int(S * 0.22), GRIS)
        d.rectangle((0, frente, S - 1, frente + S * 0.08), fill=GRIS)
        if grande:
            for fx in (0.33, 0.67):
                x = S * fx
                d.line((x, frente + S * 0.028, x, S * 0.955),
                       fill=FONDO, width=max(1, int(S * 0.022)))
    return img.resize((lado, lado), Image.LANCZOS)


def main():
    capas = []
    for t in TAMANOS:
        capas.append(dibujar(t))

    ico = os.path.join(RAIZ, "crate.ico")
    capas[0].save(ico, format="ICO",
                  sizes=[(t, t) for t in TAMANOS])
    print("icono -> %s" % ico)

    apagadas = [dibujar_cerrar(t) for t in TAMANOS]
    ico2 = os.path.join(RAIZ, "crate-cerrar.ico")
    apagadas[0].save(ico2, format="ICO", sizes=[(t, t) for t in TAMANOS])
    print("icono -> %s" % ico2)

    par = Image.new("RGB", (620, 300), (32, 32, 32))
    par.paste(capas[0], (40, 22), capas[0])
    par.paste(apagadas[0], (324, 22), apagadas[0])
    par.save(os.path.join(HERE, "icono-par.png"))

    # tira de prueba: como se ve en cada tamaño, sobre claro y sobre oscuro,
    # que es lo unico que dice si de verdad funciona
    for fondo, nombre in ((CREMA, "claro"), (AZUL, "oscuro"), ((32, 32, 32), "negro")):
        ancho = sum(t + 16 for t in TAMANOS) + 16
        tira = Image.new("RGB", (ancho, 300), fondo)
        x = 16
        for t, c in zip(TAMANOS, capas):
            tira.paste(c, (x, 150 - t // 2), c)
            x += t + 16
        p = os.path.join(HERE, "icono-%s.png" % nombre)
        tira.save(p)
        print("prueba -> %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
