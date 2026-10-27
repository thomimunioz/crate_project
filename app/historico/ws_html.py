# -*- coding: utf-8 -*-
"""Genera el HTML de la 2da tanda (la de WhoSampled). Archivo NUEVO:
no toca ninguna de las 5 listas que Thomas está usando."""
import json, os, re, html, unicodedata
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = r"G:\Thomi - Mi Carpeta\crate_project\sugerencias-v3-whosampled.html"
APOS = "\u2019"

sel = json.load(open(os.path.join(HERE, "ws_sel.json"), encoding="utf-8"))
try:
    bpm = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))
except Exception:
    bpm = {}
SNIP = open(os.path.join(HERE, "marks_snippet.html"), encoding="utf-8").read()

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    for ch in ("'", APOS, "`"):
        s = s.replace(ch, "")
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()

RUIDO_TIT = re.compile(
    r"\b(mono|stereo|vinyl|remaster\w*|hq|hd|4k|full|cd|lp|ep|version|upload|"
    r"a jazzman dean|hits archive|single|extended|records?|recording|label|"
    r"us|uk|usa|jp|listen up|official|audio|video|promo|reissue|rare|soul|funk|"
    r"jazz|disco|45|7|12)\b", re.I)

def clave(t):
    """Clave de dedup por CONJUNTO de raices: une 'A - B' con 'B - A', y
    'Makin' con 'Making' (se cortan las terminaciones -g/-s/-e)."""
    t = re.sub(r"\(.*?\)|\[.*?\]|\b(19|20)\d{2}\b|\u2117", " ", t)
    t = RUIDO_TIT.sub(" ", t)
    w = []
    for x in norm(t).split():
        if len(x) <= 2:
            continue
        x = re.sub(r"(ing|in|es|s|e)$", "", x)   # makin/making/makes -> mak
        if len(x) > 2:
            w.append(x)
    return " ".join(sorted(set(w)))

# falsos positivos de ytsearch: el título contiene el nombre de la semilla por casualidad
FALSOS = re.compile(r"icicle works|johnny mathis|fun boy three", re.I)
# verificado en WhoSampled durante esta sesión
FUERA = re.compile(r"monk higgins", re.I)

# estado de la obra según lo que verifiqué en WhoSampled
VERIF = {
 "virgen":  ("\U0001F7E2", "sin registro en WhoSampled"),
 "radar":   ("\U0001F7E1", "el disco ya fue tocado, pero este corte no"),
}
EN_RADAR = re.compile(r"zingara|faith,? ?hope", re.I)

def estado(x):
    if x["punta"] == "hermano" and EN_RADAR.search(x["title"]):
        return "radar"
    return "virgen"

def vs(v):
    if v is None: return "?"
    return "%.1fM" % (v / 1e6) if v >= 1e6 else ("%dk" % (v // 1000) if v >= 1000 else str(v))

def ds(d):
    return "?" if not d else "%d:%02d" % (d // 60, d % 60)

def tempo(b):
    if not b: return "? BPM"
    if b > 115 and 55 <= b / 2 <= 115:
        return "%d BPM <span class=alt>(leyó %d)</span>" % (round(b / 2), round(b))
    return "%d BPM" % round(b)

def plegar(b):
    return b / 2 if b > 115 and 55 <= b / 2 <= 115 else b

def reordenar(x):
    """El score original se calculo SOLO con texto, antes de medir. Ahora que
    estan el BPM y la tonalidad reales, se usan: Thomas guarda lento y menor."""
    m = bpm.get(x["id"], {})
    s = x["score"]
    b = m.get("bpm")
    if b:
        b = plegar(b)
        if 62 <= b <= 95: s += 1.4          # el corazon de lo que guarda
        elif 95 < b <= 108: s += 0.5
        elif b < 62: s += 0.6               # muy lento tambien le sirve
        else: s -= 1.0                      # >108 ya le queda rapido
    k = m.get("key") or ""
    if "minor" in k: s += 0.9
    kc = m.get("key_conf")
    if kc is not None and kc < 0.4: s -= 0.2
    x["score2"] = round(s, 2)
    return x

sel = [reordenar(x) for x in sel]

def huella(x):
    """Dos rips del mismo tema dan el mismo BPM, la misma tonalidad y la misma
    duración. Es la forma más dura de detectar un duplicado."""
    m = bpm.get(x["id"], {})
    b, k, d = m.get("bpm"), m.get("key"), m.get("dur") or x.get("dur")
    return (round(b), k, d) if (b and k and d) else None

def jaccard(a, b):
    A, B = set(a.split()), set(b.split())
    return len(A & B) / len(A | B) if A | B else 0.0

# --- dedup final y limpieza ---
limpio, claves, huellas = [], [], set()
for x in sorted(sel, key=lambda y: -y["score2"]):
    t = x["title"]
    if FALSOS.search(t) or FUERA.search(t):
        continue
    k = clave(t)
    if len(k) < 8:
        continue
    hp = huella(x)
    if hp and hp in huellas:            # mismo BPM + tonalidad + duración
        continue
    # mismo tema con la cola del sello o del canal pegada
    if any(jaccard(k, k2) >= 0.62 for k2 in claves):
        continue
    if hp:
        huellas.add(hp)
    claves.append(k)
    x["estado"] = estado(x)
    limpio.append(x)

herm = [x for x in limpio if x["punta"] == "hermano"]
veta = [x for x in limpio if x["punta"] == "veta"]

CSS = """body{font-family:system-ui,sans-serif;max-width:1060px;margin:24px auto;padding:0 16px;background:#f4efe6;color:#2a2420}
h1{font-size:1.4rem}h2{font-size:1.04rem;margin-top:2.2rem;border-bottom:2px solid #c9b8a0;padding-bottom:4px}
table{width:100%;border-collapse:collapse}td{padding:6px 8px;border-bottom:1px solid #e0d6c4;vertical-align:top;font-size:.92rem}
td.n{color:#8a7a66;width:2.4em;text-align:right}td.m{width:10.5em;color:#6b5d4d;font-size:.84rem;white-space:nowrap}
a{color:#8b2f1f;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
.ch{color:#6b5d4d;font-size:.82rem}.why{color:#4a4038;font-size:.86rem;margin-top:2px}
.alt{color:#9a8c7c;font-size:.78rem}.men{color:#5a6a4a;font-weight:600}
.nota{background:#efe6d2;border:1px solid #c9b8a0;padding:10px 14px;border-radius:6px;margin:12px 0;font-size:.9rem}
.ws{font-size:.76rem;margin-left:6px;color:#6b5d4d;font-weight:400}
.via{color:#7a5c3a;font-size:.8rem;font-style:italic}"""

out = ['<!doctype html><html lang="es"><head><meta charset="utf-8">'
       '<title>2da tanda · vía WhoSampled</title><style>%s</style></head><body>' % CSS,
 '<h1>2da tanda: lo que encontré cruzando WhoSampled</h1>',
 '<div class="nota"><b>Cómo salió esto.</b> Tenías razón con Ace Spectrum: yo medía '
 '<b>views del video</b> (obscuridad del upload) y lo que importa es <b>cuántos ya lo '
 'samplearon</b> (obscuridad de la obra). Así que esta vez arranqué al revés: fui a ver qué '
 'samplean <b>Daringer, Conductor Williams, Nicholas Craven, Knxwledge, Camoflauge Monk, '
 'Beat Butcha, Alchemist y Real Bad Man</b>, y de ahí saqué las escuelas que cavan.<br><br>'
 '<b>Dos puntas:</b><br>'
 '\u2022 <b>Hermanos</b> \u2014 discos que ellos YA usaron, pero <i>los otros cortes</i>. '
 'Si Craven sampleó un tema de Zingara 1981, quedan los otros nueve. Saqué el corte que ya usaron.<br>'
 '\u2022 <b>Veta nueva</b> \u2014 descubrí que viven en <b>library europea y bloque del este</b> '
 '(Gianni Marchetti, de Roubaix, Lesiman, Sośnicka, Zodiac), que yo no estaba cavando. '
 'Caví esos canales enteros: <b>21.368 temas nuevos</b> listados sin gastar quota.<br><br>'
 '<b>Tu regla de los 10, aplicada.</b> Verifiqué artista por artista en WhoSampled y saqué todo '
 'lo que pasa de 10 samples reales: Piero Umiliani (189), <b>Monk Higgins (410 \u2014 lo sampleó '
 'Kendrick en "Not Like Us")</b>, Janko Nilovic (82), Bruno Nicolai (64), Alessandroni, Ortolani, '
 'Gianni Ferrio (lo usó Pete Rock). El \U0001F7E2 es <b>cero registro en WhoSampled</b>; '
 'el \U0001F7E1 es <b>el disco ya fue tocado pero este corte no</b>.<br><br>'
 'Usá el desplegable <b>\u2717 por qué no</b> y al final <b>\U0001F4BE exportar feedback</b>.<br><br>'
 '<b>Este archivo es nuevo: no toqué ninguna de tus 5 listas.</b></div>']

def tabla(items, titulo, sub):
    out.append("<h2>%s</h2>" % html.escape(titulo))
    out.append('<p class="ch">%s</p><table>' % sub)
    for i, x in enumerate(items, 1):
        vid = x["id"]; b = bpm.get(vid, {})
        ico, txt = VERIF[x["estado"]]
        q = re.sub(r"\[.*?\]|\(.*?\)", " ", x["title"])[:60].strip()
        ws = "https://www.whosampled.com/search/?q=" + html.escape(q.replace(" ", "+"))
        key = b.get("key") or ""
        kcls = ' class="men"' if "minor" in key else ""
        l2 = tempo(b.get("bpm")) + ((' \u00b7 <span%s>%s</span>' % (kcls, key)) if key else "")
        info = "%s<br>%s<br>%s views \u00b7 %s" % (
            re.search(r"\b(19[4-9]\d|20[0-2]\d)\b", x["title"]).group(1)
            if re.search(r"\b(19[4-9]\d|20[0-2]\d)\b", x["title"]) else "?",
            l2, vs(x.get("views")), ds(x.get("dur")))
        out.append(
            '<tr><td class="n">%d</td><td>%s <a href="https://www.youtube.com/watch?v=%s" '
            'target="_blank">%s</a><a class="ws" href="%s" target="_blank">[WhoSampled \u2197]</a>'
            '<div class="ch">%s</div><div class="via">%s</div><div class="why">%s</div></td>'
            '<td class="m">%s</td></tr>' % (
                i, ico, vid, html.escape(x["title"][:92]), ws,
                html.escape(x.get("uploader") or ""), html.escape(x["via"]),
                txt, info))
    out.append("</table>")

por_prod = {}
for x in herm:
    por_prod.setdefault(x.get("quien", "?"), []).append(x)
for quien in sorted(por_prod, key=lambda k: -len(por_prod[k])):
    tabla(por_prod[quien], "Vía %s (%d)" % (quien, len(por_prod[quien])),
          "Discos que %s ya tocó, pero los otros cortes. "
          "El que usó no está en la lista." % html.escape(quien))
tabla(veta, "Veta nueva \u2014 library europea y bloque del este (%d)" % len(veta),
      "La escuela que cavan Daringer, Camoflauge Monk y Alchemist, y que yo no estaba tocando. "
      "Canales cavados enteros, filtrado contra todo lo que ya viste.")

med = sum(1 for x in limpio if bpm.get(x["id"], {}).get("bpm"))
out.append('<p class="ch">BPM y tonalidad medidos con el DSP de CRATE sobre 45 s de audio '
           '(%d de %d). Cuando el DSP lee la octava de arriba se muestra la mitad y entre '
           'paréntesis lo que leyó. Las tonalidades <span class="men">menores</span> van '
           'resaltadas.</p>' % (med, len(limpio)))
out.append(SNIP + "</body></html>")
open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("hermanos %d | veta %d | total %d | con BPM %d" % (len(herm), len(veta), len(limpio), med))
print("->", OUT)
