# -*- coding: utf-8 -*-
"""Genera mi-crate.html desde crate.db."""
import json, os, sqlite3, sys, html, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from app_css import CSS, FUENTES
from app_js import JS

DB = r"G:\Thomi - Mi Carpeta\crate_project\crate.db"
OUT = r"G:\Thomi - Mi Carpeta\crate_project\mi-crate.html"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
filas = con.execute("""
SELECT * FROM crate
WHERE playlists IS NOT NULL OR estado='guardado'
ORDER BY COALESCE(estrellas,0) DESC, anio, artista
""").fetchall()

datos = []
for i, r in enumerate(filas, 1):
    d = dict(r)
    d["cat"] = "CR\u00b7%04d" % i          # numero de catalogo, como en un archivo
    d["bpm"] = round(d["bpm"]) if d.get("bpm") else None
    for k in ("titulo", "artista", "nombre", "canal", "tonalidad", "playlists", "url"):
        d[k] = d.get(k) or ""
    datos.append({k: d[k] for k in
                  ("id", "cat", "titulo", "artista", "nombre", "canal", "anio", "bpm",
                   "tonalidad", "menor", "playlists", "estado", "estrellas", "tiene", "url")})

tot = con.execute("SELECT count(*) FROM tema").fetchone()[0]
med = con.execute("SELECT count(*) FROM analisis").fetchone()[0]
pls = sorted({p for d in datos for p in (d["playlists"] or "").split("\n") if p})
n_est = sum(1 for d in datos if d.get("estrellas"))
hoy = time.strftime("%d.%m.%Y")
sello = time.strftime("%d-%m %H:%M")

CLASE_G = {"SOUL": "g-soul", "80s": "g-80s", "R&B SOUL": "g-rnb", "DARK": "g-dark",
           "JAZZ FUSION": "g-fusion", "CITY POP": "g-citypop", "PIANO": "g-piano",
           "FOLK": "g-folk"}
chips_pl = "".join('<span class="chip %s" data-f="pl:%s">%s</span>'
                   % (CLASE_G.get(p, ""), html.escape(p), html.escape(p))
                   for p in pls)

DOC = """<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mi crate</title>
%s
<style>%s</style>
</head><body><div class="wrap">

<header>
  <div class="bloque">
    <h1>Cra<span>te</span></h1>
    <div class="tag"><b>catálogo personal</b>digging · %s<span class="sello" title="cuando se generó esta página — si no coincide con lo último que tocamos, estás viendo una copia vieja: Ctrl+Shift+R">build %s</span>
      <div class="temas">
        <button data-t="foryou"   title="Yamashita · For You — Hiroshi Nagai, mediodía">for you</button>
        <button data-t="allofme"  title="Takanaka · All Of Me — el Pacífico desde el aire">all of me</button>
        <button data-t="twave"    title="Takanaka · T-Wave — atardecer y el descapotable rojo">t-wave</button>
        <button data-t="willisau" title="posters suizos de jazz — sin referencia japonesa">willisau</button>
      </div>
    </div>
  </div>
  <div class="cifras">
    <div class="cifra"><b>%d</b><span>temas propios</span></div>
    <div class="cifra"><b>%s</b><span>en la base</span></div>
    <div class="cifra"><b>%d</b><span>analizados</span></div>
    <div class="cifra"><b>%d</b><span>puntuados</span></div>
  </div>
</header>

<div class="panel">
  <div class="fila1">
    <input id="q" placeholder="buscar artista, tema, canal, tonalidad…   ( / )">
  </div>

  <div class="grupo">
    <span class="gl">rango</span>
    <span class="rango">
      <span class="ru">bpm</span>
      <input id="bmin" class="mini" type="text" inputmode="numeric" maxlength="3" placeholder="58">
      <span class="gui">–</span>
      <input id="bmax" class="mini" type="text" inputmode="numeric" maxlength="3" placeholder="115">
    </span>
    <span class="rango">
      <span class="ru">año</span>
      <input id="a1" class="mini ancho" type="text" inputmode="numeric" maxlength="4" placeholder="1970">
      <span class="gui">–</span>
      <input id="a2" class="mini ancho" type="text" inputmode="numeric" maxlength="4" placeholder="1989">
    </span>
    <button class="chip ghost" id="limpiar">limpiar todo</button>
  </div>

  <div class="grupo">
    <span class="gl">estado</span>
    <span class="chip m" data-f="top">4★ y 5★</span>
    <span class="chip m" data-f="estrella">puntuados</span>
    <span class="chip b" data-f="falta">falta bajar</span>
    <span class="chip o" data-f="disco">en el disco</span>
    <span class="chip" data-f="sinbpm">sin analizar</span>
    <span class="chip o" data-f="menor">tonalidad menor</span>
  </div>

  <div class="grupo">
    <span class="gl">listas</span>
    %s
  </div>

  <div class="fila1" id="cavar">
    <span class="lbl">diggear en youtube</span>
    <input id="qy" placeholder="soul · city pop · piano · folk · dark · fusion">
    <button class="chip b on" id="bcavar">buscar</button>
    <button class="chip m" id="bhot" title="lo mejor sin escuchar, renovado cada semana">★ hotlist</button>
    <button class="chip" id="bvolver" style="display:none">volver a mi crate</button>
    <span id="cavinfo"></span>
  </div>
</div>

<div class="conteo"><div><span class="modo" id="modo">mi crate</span> <span id="conteo"></span></div><div id="conteo2" class="der"></div></div>

<table>
  <thead><tr>
    <th style="width:62px">núm</th>
    <th data-k="artista">artista · tema<span class="f"></span></th>
    <th data-k="anio" class="r">año<span class="f"></span></th>
    <th data-k="bpm" class="r">tempo<span class="f"></span></th>
    <th data-k="tonalidad" class="r">tono<span class="f"></span></th>
    <th data-k="estrellas" class="r act">★<span class="f">▾</span></th>
  </tr></thead>
  <tbody id="cuerpo"></tbody>
</table>

<footer>
  <span>click en las ★ para puntuar &nbsp;·&nbsp; doble click en la fila = ya lo tenés
        &nbsp;·&nbsp; ⇩ slsk lo busca en Soulseek</span>
  <span><button class="chip" id="exp">exportar cambios</button>
        <button class="chip apagar" id="apagar" title="cierra el servidor y Soulseek">apagar</button></span>
</footer>

</div>

<div id="slsk">
  <div class="cab"><b id="slsktit">soulseek</b>
    <span id="slskn" style="font-family:var(--mono);font-size:.64rem"></span>
    <button id="slskx" title="cerrar">&#10005;</button></div>
  <div class="lista" id="slsklista"></div>
</div>

<div id="player">
  <div id="ytbox"><div id="yt"></div></div>
  <img id="cover" alt="">
  <div class="pinfo"><div class="pa"></div><div class="pt"></div></div>
  <button class="pbtn" id="pprev" title="anterior (P)">&#9664;&#9664;</button>
  <button class="pbtn gde" id="pplay" title="play / pausa (espacio)">&#9654;</button>
  <button class="pbtn" id="pnext" title="siguiente (N)">&#9654;&#9654;</button>
  <button class="pbtn mez" id="pmez" title="al azar: cavá en tu propio crate (S)">
    <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor"
         stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
         aria-hidden="true"><path d="M16 3h5v5"/><path d="M4 20 21 3"/>
         <path d="M21 16v5h-5"/><path d="M15 15l6 6"/><path d="M4 4l5 5"/></svg>
  </button>
  <div class="barra">
    <span class="ptiempo" id="ptact">0:00</span>
    <div class="pista" id="pista"><div class="av"></div><div class="bolita"></div></div>
    <span class="ptiempo" id="pttot">0:00</span>
  </div>
  <span class="pest"></span>
  <button class="pbtn" id="pcerrar" title="cerrar">&#10005;</button>
</div>
<script src="https://www.youtube.com/iframe_api"></script>
<script>const DATOS=%s;</script>
<script>%s</script>
</body></html>""" % (FUENTES, CSS, hoy, sello, len(datos), "{:,}".format(tot).replace(",","."),
                     med, n_est, chips_pl,
                     json.dumps(datos, ensure_ascii=False, separators=(",", ":")), JS)

open(OUT, "w", encoding="utf-8").write(DOC)
print("%d temas -> %s  (%.0f KB)" % (len(datos), OUT, os.path.getsize(OUT) / 1024))
