# -*- coding: utf-8 -*-
"""Vuelca a crate.db todo lo que Thomas marco desde afuera, y regenera la app.

Cierra el circulo: la app y los HTML de tandas guardan en el navegador, esto lo
pasa a la base, que es la fuente de verdad. Sin esto, lo que marca vive solo en
el localStorage de Chrome y se pierde si lo limpia.

Lee dos cosas:
  * crate-cambios.json      — el boton "exportar cambios" de mi-crate.html
                              (estrellas puestas desde la app, "ya lo tengo")
  * crate-feedback-*.json   — los export de cada tanda
                              (guardado/rechazado, motivo, nota, estrellas)

Uso:  python bd_sync.py          lee de Descargas y actualiza
      python bd_sync.py --ver    muestra que haria, sin tocar nada
"""
import json, os, glob, sqlite3, sys, time, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
DB = r"G:\Thomi - Mi Carpeta\crate_project\crate.db"
DESCARGAS = os.path.join(os.path.expanduser("~"), "Downloads")
VER = "--ver" in sys.argv


def abrir():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS sync_hecho(
        archivo TEXT PRIMARY KEY, mtime REAL, filas INTEGER, fecha TEXT)""")
    return con


def ya_procesado(con, f):
    r = con.execute("SELECT mtime FROM sync_hecho WHERE archivo=?",
                    (os.path.basename(f),)).fetchone()
    return r and abs(r[0] - os.path.getmtime(f)) < 1


def main():
    if not os.path.exists(DB):
        print("no existe %s — corre bd_build.py primero" % DB)
        return 1
    if not VER:
        shutil.copy2(DB, DB + ".bak")        # por las dudas
    con = abrir()
    cur = con.cursor()
    hoy = time.strftime("%Y-%m-%d")
    nuevas = {"marca": 0, "estrella": 0, "archivo": 0}
    saltados = 0

    # ---------- 1. los export de cada tanda ----------
    for f in sorted(glob.glob(os.path.join(DESCARGAS, "crate-feedback-*.json")),
                    key=os.path.getmtime):
        if ya_procesado(con, f):
            saltados += 1
            continue
        d = json.load(open(f, encoding="utf-8"))
        tanda = (d.get("pagina") or os.path.basename(f))[:60]
        fecha = (d.get("fecha") or "")[:10] or hoy
        n = 0
        for t in d.get("temas", []):
            vid = t.get("id")
            if not vid:
                continue
            estado = ("guardado" if t.get("agregado")
                      else "rechazado" if t.get("motivo")
                      else "visto" if t.get("abierto") else None)
            if not estado:
                continue
            cur.execute("SELECT 1 FROM tema WHERE id=?", (vid,))
            if not cur.fetchone():
                cur.execute("INSERT INTO tema(id,titulo,agregado) VALUES(?,?,?)",
                            (vid, t.get("titulo") or vid, hoy))
            cur.execute("""INSERT OR REPLACE INTO marca
                           (id,estado,estrellas,motivo,nota,tanda,fecha)
                           VALUES(?,?,?,?,?,?,?)""",
                        (vid, estado, t.get("estrellas") or None,
                         t.get("motivo") or None, t.get("nota") or None, tanda, fecha))
            n += 1
            nuevas["marca"] += 1
        print("  %-46s %3d marcas" % (os.path.basename(f)[:46], n))
        if not VER:
            cur.execute("INSERT OR REPLACE INTO sync_hecho VALUES(?,?,?,?)",
                        (os.path.basename(f), os.path.getmtime(f), n, hoy))

    # ---------- 2. lo que cambio desde la app ----------
    for f in sorted(glob.glob(os.path.join(DESCARGAS, "crate-cambios*.json")),
                    key=os.path.getmtime):
        if ya_procesado(con, f):
            saltados += 1
            continue
        d = json.load(open(f, encoding="utf-8"))
        cambios = d.get("cambios", {})
        n = 0
        for vid, c in cambios.items():
            if c.get("estrellas") is not None:
                e = c["estrellas"] or None
                cur.execute("""INSERT INTO marca(id,estado,estrellas,tanda,fecha)
                               VALUES(?,'guardado',?,'app',?)
                               ON CONFLICT(id,tanda) DO UPDATE SET estrellas=excluded.estrellas""",
                            (vid, e, hoy))
                nuevas["estrella"] += 1; n += 1
            if c.get("bajado"):
                cur.execute("""INSERT OR IGNORE INTO archivo(id,ruta,fuente,bajado)
                               VALUES(?,?,?,?)""",
                            (vid, "(marcado a mano)", "manual", hoy))
                nuevas["archivo"] += 1; n += 1
            elif c.get("bajado") is False:
                cur.execute("DELETE FROM archivo WHERE id=? AND fuente='manual'", (vid,))
        print("  %-46s %3d cambios" % (os.path.basename(f)[:46], n))
        if not VER:
            cur.execute("INSERT OR REPLACE INTO sync_hecho VALUES(?,?,?,?)",
                        (os.path.basename(f), os.path.getmtime(f), n, hoy))

    if VER:
        con.rollback()
        print("\n(modo --ver: no se guardo nada)")
    else:
        con.commit()
    q = lambda s: cur.execute(s).fetchone()[0]
    print()
    print("archivos ya procesados antes, salteados: %d" % saltados)
    print("marcas nuevas %d | estrellas %d | archivos %d"
          % (nuevas["marca"], nuevas["estrella"], nuevas["archivo"]))
    print()
    print("estado de la base:")
    print("  guardados          %5d" % q("SELECT count(DISTINCT id) FROM marca WHERE estado='guardado'"))
    print("  con estrellas      %5d" % q("SELECT count(DISTINCT id) FROM marca WHERE estrellas>0"))
    print("  en el disco        %5d" % q("SELECT count(DISTINCT id) FROM archivo"))
    print("  falta bajar        %5d" % q("SELECT count(*) FROM por_bajar"))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
