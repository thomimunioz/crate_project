# -*- coding: utf-8 -*-
"""Servidor local de CRATE.

Hace dos cosas que desde file:// no se pueden:
  1. el reproductor de YouTube embebido funciona (desde file:// el navegador
     trata la pagina como origen nulo y el iframe falla)
  2. lo que marcas se guarda DIRECTO en crate.db, sin exportar ni importar

Uso:  python crate_server.py          -> http://127.0.0.1:7777
Cortar con Ctrl+C. No expone nada afuera: escucha solo en 127.0.0.1.
"""
import json, os, posixpath, re, sqlite3, subprocess, sys, time, threading, urllib.request, webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import criterios

YT = "G:/Thomi - Mi Carpeta/crate_project/backend/.venv/Scripts/yt-dlp.exe"
SEP = chr(92) + "t"

HERE = os.path.dirname(os.path.abspath(__file__))
RAIZ = r"G:\Thomi - Mi Carpeta\crate_project"
DB = os.path.join(RAIZ, "crate.db")
PUERTO = 7777
SLSKD = "http://127.0.0.1:5030"
SLSKD_KEY = ""
try:
    SLSKD_KEY = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  "slskd_key.txt")).read().strip()
except Exception:
    pass
CACHE_AUDIO = {}        # id -> (url, cuando) ; las URLs de YouTube caducan


# El servidor sirve la carpeta del proyecto para que mi-crate.html cargue, pero
# ahi vive tambien el .env con las claves y crate.db entera. Cualquier pagina
# abierta en el navegador puede pedirle archivos a 127.0.0.1. Asi que lo que se
# sirve es una lista blanca: el HTML y poco mas. Encontrado auditando el 27-oct.
SERVIBLE = (".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".svg", ".webp",
            ".woff", ".woff2", ".ico")


def servible(ruta):
    nombre = posixpath.basename(ruta)
    if nombre.startswith("."):          # .env, .git, .gitignore
        return False
    return ruta.lower().endswith(SERVIBLE)


def db():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    return con


COLS_CRATE = ("id", "titulo", "artista", "nombre", "canal", "anio", "bpm",
              "tonalidad", "menor", "playlists", "estado", "estrellas",
              "tiene", "url")


def fila_crate(con, vid):
    """La fila como la espera la tabla del HTML, para que un tema recien
    puntuado o clasificado aparezca sin recargar la pagina."""
    r = con.execute("SELECT * FROM crate WHERE id=?", (vid,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["bpm"] = round(d["bpm"]) if d.get("bpm") else None
    for k in ("titulo", "artista", "nombre", "canal", "tonalidad", "playlists", "url"):
        d[k] = d.get(k) or ""
    return {k: d.get(k) for k in COLS_CRATE}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=RAIZ, **k)

    def log_message(self, *a):
        pass                                  # sin ruido en la consola

    def _json(self, obj, codigo=200):
        cuerpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta == "/":
            self.send_response(302)
            self.send_header("Location", "/mi-crate.html")
            self.end_headers()
            return
        if ruta == "/api/slsk/bajadas":
            if not SLSKD_KEY:
                return self._json({"ok": False, "error": "falta la API key"}, 503)
            try:
                d = slsk_api("GET", "/api/v0/transfers/downloads")
            except Exception as e:
                return self._json({"ok": False, "error": str(e)[:140]}, 502)
            return self._json({"ok": True, "bajadas": bajadas_planas(d)})
        if ruta.startswith("/api/slsk/"):
            sid = ruta.rsplit("/", 1)[-1]
            try:
                d = slsk_api("GET", "/api/v0/searches/%s?includeResponses=true" % sid)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)[:140]}, 502)
            estado = d.get("state", "")
            listo = estado.startswith("Completed")
            return self._json({"ok": True, "listo": listo, "estado": estado,
                               "contados": d.get("fileCount") or 0,
                               "archivos": ordenar_archivos(d) if listo else []})
        if ruta.startswith("/api/audio/"):
            return self.servir_audio(ruta.rsplit("/", 1)[-1])
        if ruta == "/api/hotlist":
            con = db()
            try:
                filas = [dict(r) for r in con.execute("SELECT * FROM hot LIMIT 120")]
            except sqlite3.OperationalError:
                filas = []          # todavia no se genero ninguna tanda
            con.close()
            for f in filas:
                try:
                    f["razones"] = json.loads(f.get("razones") or "[]")
                except Exception:
                    f["razones"] = []
            return self._json({"ok": True, "temas": filas})
        if ruta == "/api/estado":
            con = db()
            q = lambda s: con.execute(s).fetchone()[0]
            self._json({"ok": True,
                        "temas": q("SELECT count(*) FROM crate"),
                        "guardados": q("SELECT count(DISTINCT id) FROM marca WHERE estado='guardado'"),
                        "estrellas": q("SELECT count(DISTINCT id) FROM marca WHERE estrellas>0"),
                        "por_bajar": q("SELECT count(*) FROM por_bajar")})
            con.close()
            return
        if not servible(ruta):
            return self._json({"ok": False,
                               "error": "fuera de la lista blanca"}, 403)
        return super().do_GET()

    def servir_audio(self, vid):
        """Saca la URL del audio con yt-dlp y la retransmite. Sirve para los
        videos que bloquean el embebido, asi no hay que salir de la app."""
        if not (len(vid) == 11 and vid.replace("-", "").replace("_", "").isalnum()):
            return self._json({"ok": False, "error": "id invalido"}, 400)
        url = CACHE_AUDIO.get(vid)
        if not url or time.time() - url[1] > 3600:      # las URLs caducan
            try:
                r = subprocess.run(
                    [YT, "-f", "bestaudio/best", "--js-runtimes", "node",
                     "--no-warnings", "-q", "-g",
                     "https://www.youtube.com/watch?v=" + vid],
                    capture_output=True, text=True, timeout=70)
            except subprocess.TimeoutExpired:
                return self._json({"ok": False, "error": "tardo demasiado"}, 504)
            linea = (r.stdout or "").strip().splitlines()
            if not linea:
                err = (r.stderr or "").strip().splitlines()
                return self._json({"ok": False,
                                   "error": (err[-1] if err else "sin audio")[:160]}, 502)
            url = (linea[0], time.time())
            CACHE_AUDIO[vid] = url
        pedido = urllib.request.Request(url[0], headers={
            "User-Agent": "Mozilla/5.0", "Accept": "*/*",
            "Range": self.headers.get("Range", "bytes=0-")})
        try:
            with urllib.request.urlopen(pedido, timeout=30) as up:
                self.send_response(up.status)
                for h in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
                    v = up.headers.get(h)
                    if v:
                        self.send_header(h, v)
                self.end_headers()
                while True:
                    bloque = up.read(65536)
                    if not bloque:
                        break
                    self.wfile.write(bloque)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass                     # cortaste el tema: es normal, no es un error
        except Exception as e:
            try:
                self._json({"ok": False, "error": str(e)[:120]}, 502)
            except Exception:
                pass

    def do_POST(self):
        ruta = urlparse(self.path).path
        largo = int(self.headers.get("Content-Length") or 0)
        try:
            datos = json.loads(self.rfile.read(largo) or b"{}")
        except Exception:
            return self._json({"ok": False, "error": "json invalido"}, 400)
        hoy = time.strftime("%Y-%m-%d")

        if ruta == "/api/estrellas":
            vid, n = datos.get("id"), datos.get("estrellas")
            if not vid:
                return self._json({"ok": False}, 400)
            con = db()
            # si viene de una busqueda, el tema todavia no esta en la base: hay
            # que crearlo ANTES de marcarlo, si no la marca queda huerfana y el
            # tema desaparece (pasó el 27-oct con Cal State Long Beach).
            existe = con.execute("SELECT 1 FROM tema WHERE id=?", (vid,)).fetchone()
            nuevo = False
            if not existe:
                t = datos.get("titulo") or vid
                art, nom = partir(t)
                con.execute("""INSERT INTO tema(id,titulo,artista,nombre,canal,
                                                duracion,views,agregado)
                               VALUES(?,?,?,?,?,?,?,?)""",
                            (vid, t, art, nom, datos.get("canal"),
                             datos.get("dur"), datos.get("views"), hoy))
                con.execute("INSERT OR IGNORE INTO origen(id,fuente) VALUES(?,'busqueda')", (vid,))
                nuevo = True
            con.execute("""INSERT INTO marca(id,estado,estrellas,tanda,fecha)
                           VALUES(?,'guardado',?,'app',?)
                           ON CONFLICT(id,tanda) DO UPDATE SET estrellas=excluded.estrellas""",
                        (vid, n or None, hoy))
            con.commit()
            fila = fila_crate(con, vid)
            con.close()
            return self._json({"ok": True, "id": vid, "estrellas": n,
                               "nuevo": nuevo, "tema": fila})

        if ruta == "/api/buscar":
            q = (datos.get("q") or "").strip()
            if not q:
                return self._json({"ok": False, "error": "falta la busqueda"}, 400)
            try:
                res, info = buscar(q)
            except Exception as e:
                return self._json({"ok": False, "error": str(e)[:200]}, 500)
            return self._json({"ok": True, "q": q, "resultados": res, "info": info})

        if ruta == "/api/slsk":
            q = (datos.get("q") or "").strip()
            if not q:
                return self._json({"ok": False, "error": "falta que buscar"}, 400)
            if not SLSKD_KEY:
                return self._json({"ok": False, "error": "falta la API key de slskd"}, 503)
            try:
                ini = slsk_api("POST", "/api/v0/searches", {"searchText": q})
            except Exception as e:
                return self._json({"ok": False,
                                   "error": "slskd no responde: " + str(e)[:120]}, 502)
            return self._json({"ok": True, "id": ini.get("id"), "q": q})

        if ruta == "/api/slsk/bajar":
            usuario = (datos.get("usuario") or "").strip()
            archivo = datos.get("ruta") or ""
            if not usuario or not archivo:
                return self._json({"ok": False, "error": "falta usuario o archivo"}, 400)
            if not SLSKD_KEY:
                return self._json({"ok": False, "error": "falta la API key de slskd"}, 503)
            cuerpo = [{"filename": archivo, "size": int(datos.get("bytes") or 0)}]
            try:
                slsk_api("POST", "/api/v0/transfers/downloads/%s"
                         % urllib.parse.quote(usuario, safe=""), cuerpo)
            except Exception as e:
                return self._json({"ok": False,
                                   "error": "slskd rechazo la descarga: " + str(e)[:120]}, 502)
            # queda anotado contra el tema: asi `por_bajar` deja de pedirlo y se
            # sabe de donde salio el archivo cuando aparezca en el disco
            vid = datos.get("id")
            if vid:
                con = db()
                if con.execute("SELECT 1 FROM tema WHERE id=?", (vid,)).fetchone():
                    con.execute("""INSERT OR REPLACE INTO archivo(id,ruta,formato,
                                                 bitrate,bytes,fuente,bajado)
                                   VALUES(?,?,?,?,?,'slskd',?)""",
                                (vid, archivo, (datos.get("ext") or "").lower(),
                                 datos.get("bitrate"), datos.get("bytes"), hoy))
                    con.commit()
                con.close()
            return self._json({"ok": True, "usuario": usuario})

        if ruta == "/api/playlist":
            vid = datos.get("id")
            lista = (datos.get("playlist") or "").strip()
            quitar = bool(datos.get("quitar"))
            if not vid or not lista:
                return self._json({"ok": False}, 400)
            con = db()
            if not con.execute("SELECT 1 FROM tema WHERE id=?", (vid,)).fetchone():
                t = datos.get("titulo") or vid
                art, nom = partir(t)
                con.execute("""INSERT INTO tema(id,titulo,artista,nombre,canal,
                                                duracion,views,agregado)
                               VALUES(?,?,?,?,?,?,?,?)""",
                            (vid, t, art, nom, datos.get("canal"),
                             datos.get("dur"), datos.get("views"), hoy))
            if quitar:
                con.execute("DELETE FROM en_playlist WHERE id=? AND playlist=?", (vid, lista))
            else:
                con.execute("INSERT OR IGNORE INTO en_playlist(id,playlist) VALUES(?,?)",
                            (vid, lista))
            listas = [r[0] for r in con.execute(
                "SELECT playlist FROM en_playlist WHERE id=? ORDER BY playlist", (vid,))]
            con.commit()
            fila = fila_crate(con, vid)
            con.close()
            return self._json({"ok": True, "id": vid, "listas": listas,
                               "tema": fila})

        if ruta == "/api/archivo":
            vid, tiene = datos.get("id"), bool(datos.get("tiene"))
            con = db()
            if tiene:
                con.execute("""INSERT OR IGNORE INTO archivo(id,ruta,fuente,bajado)
                               VALUES(?,'(marcado a mano)','manual',?)""", (vid, hoy))
            else:
                con.execute("DELETE FROM archivo WHERE id=? AND fuente='manual'", (vid,))
            con.commit(); con.close()
            return self._json({"ok": True, "id": vid, "tiene": tiene})

        return self._json({"ok": False, "error": "ruta desconocida"}, 404)


def slsk_api(metodo, ruta, cuerpo=None):
    req = urllib.request.Request(
        SLSKD + ruta, method=metodo,
        data=json.dumps(cuerpo).encode() if cuerpo is not None else None,
        headers={"X-API-Key": SLSKD_KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        txt = r.read().decode("utf-8", "replace")
    return json.loads(txt) if txt.strip() else {}


def bajadas_planas(d):
    """slskd devuelve usuario -> directorios -> archivos. Se aplana a una lista
    con lo unico que importa mirando una descarga: que es, como va y si fallo."""
    out = []
    for u in (d or []):
        for dirr in (u.get("directories") or []):
            for f in (dirr.get("files") or []):
                tam = f.get("size") or 0
                out.append({
                    "usuario": u.get("username"),
                    "nombre": (f.get("filename") or "").replace("/", chr(92))
                              .split(chr(92))[-1],
                    "estado": f.get("state") or "",
                    "pct": round(100.0 * (f.get("bytesTransferred") or 0) / tam, 1)
                           if tam else 0.0,
                    "mb": round(tam / 1048576.0, 1)})
    return out


def ordenar_archivos(d):
    """Saca los archivos de la respuesta y los ordena por calidad: FLAC primero,
    despues por bitrate, y los que tienen slot libre antes."""
    out = []
    for r in (d.get("responses") or []):
        usr = r.get("username")
        libre = r.get("hasFreeUploadSlot")
        for f in (r.get("files") or []):
            nom = (f.get("filename") or "").replace("/", chr(92)).split(chr(92))[-1]
            ext = nom.rsplit(".", 1)[-1].lower() if "." in nom else ""
            if ext not in ("flac", "mp3", "wav", "aiff", "m4a", "ogg", "wv", "ape"):
                continue
            out.append({"nombre": nom, "usuario": usr, "libre": libre, "ext": ext,
                        "bitrate": f.get("bitRate"),
                        "mb": round((f.get("size") or 0) / 1048576.0, 1),
                        "bytes": f.get("size") or 0,
                        "seg": f.get("length"), "ruta": f.get("filename")})
    prio = {"flac": 0, "wav": 0, "aiff": 0, "ape": 1, "wv": 1, "m4a": 2, "ogg": 2, "mp3": 3}
    out.sort(key=lambda x: (prio.get(x["ext"], 9), -(x["bitrate"] or 0),
                            0 if x["libre"] else 1))
    return out[:40]


def partir(t):
    """Separa 'Artista - Tema' sacando el ruido tipico de YouTube."""
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", t or "")
    s = re.sub(r"\b(official|audio|video|hq|hd|4k|vinyl|rip|lyrics?|full|"
               r"version|remaster\w*|rare|obscure|unreleased|soul sample)\b", " ", s, flags=re.I)
    s = re.sub(r"\b(19|20)\d{2}\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -–—:.,")
    m = re.split(r"\s+[-–—]\s+|\s*:\s+", s, 1)
    if len(m) == 2 and 1 < len(m[0]) < 60 and len(m[1]) > 1:
        return m[0].strip(), m[1].strip()
    return None, s or None


def ytsearch(q, n=22):
    """Una busqueda en YouTube con yt-dlp. Cero quota de API."""
    cmd = [YT, "--flat-playlist", "--no-warnings", "-q", "--ignore-errors",
           "--print", "%%(id)s%s%%(title)s%s%%(duration)s%s%%(view_count)s%s%%(uploader)s"
           % (SEP, SEP, SEP, SEP), "ytsearch%d:%s" % (n, q)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=90)
    except subprocess.TimeoutExpired:
        return []
    out = []
    for ln in r.stdout.splitlines():
        c = ln.split(SEP)
        if len(c) < 5 or len(c[0]) != 11:
            continue
        out.append({"id": c[0], "titulo": c[1], "canal": c[4],
                    "dur": int(c[2]) if c[2].isdigit() else None,
                    "views": int(c[3]) if c[3].isdigit() else None})
    return out


def buscar(q):
    """Lo que Thomas escribe + toda la salsita: se expande la busqueda, se
    descarta con los criterios medidos y se ordena por lo que historicamente
    rinde."""
    queries = criterios.expandir(q)
    genero = None
    low = criterios.quitar_tildes(q)
    for g in ("fusion", "citypop", "soul", "rnb", "80s", "library"):
        if g in low:
            genero = g
            break

    crudo = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        for lote in ex.map(ytsearch, queries[:5]):
            for x in lote:
                crudo.setdefault(x["id"], x)

    # lo que ya esta en la base: visto, guardado o rechazado
    con = db()
    ya = {r[0] for r in con.execute("SELECT id FROM tema")}
    marcados = {r[0]: r[1] for r in con.execute(
        "SELECT id, estado FROM marca GROUP BY id")}
    anal = {r[0]: (r[1], r[2]) for r in con.execute(
        "SELECT id, bpm_real, menor FROM analisis")}
    con.close()

    pasan, descartes = [], {}
    for vid, x in crudo.items():
        if vid in marcados:
            descartes["ya lo viste"] = descartes.get("ya lo viste", 0) + 1
            continue
        motivo = criterios.descartar(x["titulo"], x["dur"], x["views"],
                                     x["canal"], genero)
        if motivo:
            descartes[motivo] = descartes.get(motivo, 0) + 1
            continue
        bpm, menor = anal.get(vid, (None, None))
        pts, razones = criterios.puntuar(x["titulo"], x["dur"], x["views"],
                                         x["canal"], None, bpm, menor)
        x.update({"pts": pts, "razones": razones, "bpm": bpm, "menor": menor,
                  "enbase": vid in ya})
        pasan.append(x)

    pasan.sort(key=lambda y: -y["pts"])
    info = {"buscado": queries[:5], "crudo": len(crudo),
            "pasan": len(pasan), "descartes": descartes, "genero": genero}
    return pasan[:40], info


def main():
    if not os.path.exists(DB):
        print("no encuentro %s" % DB); return 1
    if not os.path.exists(os.path.join(RAIZ, "mi-crate.html")):
        print("falta mi-crate.html — corre app_build.py"); return 1
    # ThreadingHTTPServer y no HTTPServer: con un solo hilo, mientras transmite
    # un audio (que dura minutos) no puede atender ningun otro pedido, y a los
    # 5 o 6 temas la app quedaba trabada.
    srv = ThreadingHTTPServer(("127.0.0.1", PUERTO), Handler)
    srv.daemon_threads = True
    url = "http://127.0.0.1:%d/mi-crate.html" % PUERTO
    print("CRATE sirviendo en %s" % url)
    print("  escucha solo en 127.0.0.1, no sale de esta maquina")
    print("  lo que marques se guarda solo en crate.db")
    print("  Ctrl+C para cortar")
    threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\ncortado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
