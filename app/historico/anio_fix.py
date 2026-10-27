# -*- coding: utf-8 -*-
"""Arregla el anio en meta_cache.json. Dos bugs encontrados el 24-oct:

1. El ℗ se tomaba con \\d{4} suelto, asi que "℗ 709044 Records DK" (el sello de
   DistroKid) daba el anio 7090. Hay que exigir que no siga otro digito y que
   caiga en un rango plausible.
2. El ℗ de una REEDICION se tomaba como anio de la obra: "Carrie Lucas -
   Questions - 1978 Soul" quedaba como 2005 porque el upload es un redistribuido.
   Si el titulo declara un anio y el ℗ es muy posterior, manda el titulo.

No toca la red: recomputa sobre la descripcion que ya esta cacheada.
"""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "meta_cache.json")
cache = json.load(open(CACHE, encoding="utf-8"))

# \d{4} que NO este pegado a mas digitos, y dentro de un rango real
PHONO = re.compile(r"[℗©]\s*(?<!\d)(\d{4})(?!\d)")
ANIO_T = re.compile(r"(?<!\d)(19[4-9]\d|20[0-2]\d)(?!\d)")
HOY = 2026

def plausible(y):
    return y is not None and 1940 <= y <= HOY

cambios, rotos, reed = 0, 0, 0
for vid, m in cache.items():
    if not isinstance(m, dict) or "desc" not in m:
        continue
    desc, tit = m.get("desc") or "", m.get("title") or ""
    viejo = m.get("year")
    viejo = int(viejo) if str(viejo or "").isdigit() else None

    yt = None                                  # anio declarado en el TITULO
    mt = ANIO_T.search(tit)
    if mt:
        yt = int(mt.group(1))

    yp = None                                  # anio del ℗
    mp = PHONO.search(desc)
    if mp and plausible(int(mp.group(1))):
        yp = int(mp.group(1))

    yd = None                                  # anio suelto en la descripcion
    md = ANIO_T.search(desc)
    if md:
        yd = int(md.group(1))

    # el titulo gana cuando el ℗ es claramente de una reedicion
    if yt and yp and yp - yt >= 8:
        nuevo, fuente = yt, "titulo (℗ %d es reedicion)" % yp
        reed += 1
    elif yp:
        nuevo, fuente = yp, "phonogram"
    elif yt:
        nuevo, fuente = yt, "titulo"
    elif yd and plausible(yd):
        nuevo, fuente = yd, "descripcion"
    else:
        nuevo, fuente = None, None

    if viejo is not None and not plausible(viejo):
        rotos += 1
    if nuevo != viejo:
        cambios += 1
    m["year"] = str(nuevo) if nuevo else None
    m["year_src"] = fuente
    m["phonogram"] = bool(mp and plausible(int(mp.group(1))))

json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
con = sum(1 for m in cache.values()
          if isinstance(m, dict) and str(m.get("year") or "").isdigit())
print("entradas en cache: %d" % len(cache))
print("anios corregidos:  %d" % cambios)
print("eran imposibles:   %d  (tipo 7090, del sello de DistroKid)" % rotos)
print("reediciones detectadas: %d  (gana el anio del titulo)" % reed)
print("con anio valido:   %d" % con)
