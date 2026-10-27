# -*- coding: utf-8 -*-
"""Corrige los años que son de la REEDICION y no de la grabacion.

El caso que lo disparo (27-oct): "Esperando Nacer" de Seru Giran figuraba como
2019. Es de 1982; 2019 es cuando el distribuidor subio el disco a YouTube.

Por que pasa: el ℗ de la descripcion es el del master que se publica, no el de
la grabacion. anio_fix.py ya corrige el caso facil — cuando el TITULO declara
el año verdadero — pero no puede hacer nada cuando el titulo no lo dice.

Solucion: preguntarle a MusicBrainz, que tiene la fecha de la primera edicion.
Es gratis, sin clave, y solo se consulta para los sospechosos (año >= 2000),
respetando el limite de 1 pedido por segundo que pide su documentacion.
"""
import json, os, sqlite3, sys, time, urllib.parse, urllib.request

DB = r"G:\Thomi - Mi Carpeta\crate_project\crate.db"
UA = "CRATE/1.0 (digging personal; contacto: thomas@contentboard.com.ar)"
VER = "--ver" in sys.argv
LIMITE = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--max=")), "60"))


def mb_primera_edicion(artista, tema):
    """Primer año de publicacion segun MusicBrainz, o None."""
    q = 'recording:"%s" AND artist:"%s"' % (tema.replace('"', ""), artista.replace('"', ""))
    url = ("https://musicbrainz.org/ws/2/recording?query=%s&fmt=json&limit=5"
           % urllib.parse.quote(q))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return None
    anios = []
    for rec in d.get("recordings", [])[:5]:
        if rec.get("score", 0) < 85:
            continue
        for rel in rec.get("releases", []):
            f = rel.get("date") or ""
            if len(f) >= 4 and f[:4].isdigit():
                anios.append(int(f[:4]))
        f = rec.get("first-release-date") or ""
        if len(f) >= 4 and f[:4].isdigit():
            anios.append(int(f[:4]))
    anios = [a for a in anios if 1940 <= a <= 2026]
    return min(anios) if anios else None


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    # sospechosos: año moderno pero con artista y tema identificados
    filas = con.execute("""
        SELECT id, titulo, artista, nombre, anio FROM tema
        WHERE anio >= 2000 AND artista IS NOT NULL AND nombre IS NOT NULL
          AND oculto = 0
          AND (anio_fuente IS NULL OR anio_fuente <> 'musicbrainz')
        ORDER BY (SELECT count(*) FROM en_playlist p WHERE p.id = tema.id) DESC,
                 anio DESC
        LIMIT ?""", (LIMITE,)).fetchall()
    print("sospechosos de llevar año de reedicion: %d" % len(filas))
    print()
    cambios = 0
    for r in filas:
        real = mb_primera_edicion(r["artista"], r["nombre"])
        time.sleep(1.05)                     # MusicBrainz pide 1 por segundo
        if not real or real >= r["anio"] - 2:
            continue
        print("  %-30s %-28s  %d -> %d" % (
            (r["artista"] or "")[:30], (r["nombre"] or "")[:28], r["anio"], real))
        cambios += 1
        if not VER:
            con.execute("UPDATE tema SET anio=?, anio_fuente='musicbrainz' WHERE id=?",
                        (real, r["id"]))
    if VER:
        print("\n(--ver: no guarde nada)")
    else:
        con.commit()
    print("\ncorregidos: %d de %d" % (cambios, len(filas)))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
