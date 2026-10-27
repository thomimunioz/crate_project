# -*- coding: utf-8 -*-
"""Generador UNIFICADO: un solo crate.html con todas las tandas adentro y
pestañas para cambiar de una a otra.

Thomas, 26-oct: "hace una limpieza de html's tengo mil por todos lados (...) o
unifica y q sea un solo html la proxima y pueda ir switcheando desde ahi".

De acá en adelante toda tanda nueva entra como una pestaña de este archivo.
Las marcas viven en localStorage bajo 'crate-marks', que es global, así que
regenerar el archivo NO borra nada de lo marcado.

Uso:
    from crate_html import Tanda, generar
    generar([Tanda(slug, titulo, bajada, items), ...], salida)
donde cada item es un dict con: id, title, uploader, why, dur, views y
opcionalmente tier.
"""
import json, os, re, html

HERE = os.path.dirname(os.path.abspath(__file__))
SNIP = open(os.path.join(HERE, "marks_snippet.html"), encoding="utf-8").read()
META = json.load(open(os.path.join(HERE, "meta_cache.json"), encoding="utf-8"))
BPM = json.load(open(os.path.join(HERE, "bpm_cache.json"), encoding="utf-8"))

TIER = {"fuego": "\U0001F525", "bien": "\U0001F44D", "quizas": "\U0001F914"}


class Tanda(object):
    def __init__(self, slug, titulo, bajada, items):
        self.slug, self.titulo, self.bajada, self.items = slug, titulo, bajada, items


def _vs(v):
    if v is None:
        return "?"
    return "%.1fM" % (v / 1e6) if v >= 1e6 else ("%dk" % (v // 1000) if v >= 1000 else str(v))


def _tempo(vid):
    b = BPM.get(vid, {}).get("bpm")
    if not b:
        return "? BPM"
    if b > 115 and 55 <= b / 2 <= 115:
        return "%d BPM <span class=alt>(leyó %d)</span>" % (round(b / 2), round(b))
    return "%d BPM" % round(b)


CSS = """*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;max-width:1060px;margin:0 auto;padding:22px 16px 60px;background:#f4efe6;color:#2a2420;line-height:1.5}
h1{font-size:1.6rem;margin:0 0 14px;letter-spacing:-.4px}
nav{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 18px;position:sticky;top:0;background:#f4efe6;padding:8px 0;z-index:20;border-bottom:1px solid #d9cdb5}
nav button{font:inherit;font-size:.88rem;cursor:pointer;border:1px solid #c9b8a0;background:#efe6d2;color:#4a4038;padding:5px 12px;border-radius:14px}
nav button:hover{background:#e4d8bf}
nav button.on{background:#8b2f1f;border-color:#8b2f1f;color:#fff;font-weight:600}
nav button .c{opacity:.65;font-size:.82em;margin-left:4px}
.tanda{display:none}.tanda.on{display:block}
.bajada{color:#4a4038;font-size:.9rem;background:#fffdf7;border:1px solid #d9cdb5;border-radius:8px;padding:11px 16px;margin:0 0 16px}
table{width:100%;border-collapse:collapse}
td{padding:7px 8px;border-bottom:1px solid #e0d6c4;vertical-align:top;font-size:.93rem}
td.n{color:#8a7a66;width:2.4em;text-align:right}
td.m{width:10.5em;color:#6b5d4d;font-size:.83rem;white-space:nowrap;text-align:right}
a{color:#8b2f1f;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
.ch{color:#6b5d4d;font-size:.81rem}.why{color:#4a4038;font-size:.86rem;margin-top:2px}
.alt{color:#9a8c7c;font-size:.76rem}.men{color:#5a6a4a;font-weight:600}
@media(max-width:640px){td.m{width:auto;font-size:.76rem}body{padding:14px 10px}}"""

JS_TABS = """
<script>
(function(){
  var KEY='crate-tanda';
  var bs=[].slice.call(document.querySelectorAll('nav button'));
  function ir(slug){
    document.querySelectorAll('.tanda').forEach(function(d){
      d.classList.toggle('on', d.dataset.slug===slug);
    });
    bs.forEach(function(b){ b.classList.toggle('on', b.dataset.slug===slug); });
    try{localStorage.setItem(KEY,slug)}catch(e){}
    location.hash=slug;
    window.scrollTo(0,0);
  }
  bs.forEach(function(b){ b.onclick=function(){ ir(b.dataset.slug); }; });
  var ini=(location.hash||'').replace('#','');
  if(!ini){ try{ini=localStorage.getItem(KEY)||''}catch(e){} }
  if(!ini || !document.querySelector('.tanda[data-slug="'+ini+'"]')){
    ini=bs.length?bs[0].dataset.slug:'';
  }
  if(ini) ir(ini);
  // contador de pendientes por pestaña, leido de las marcas guardadas
  try{
    var m=JSON.parse(localStorage.getItem('crate-marks')||'{}')||{};
    document.querySelectorAll('.tanda').forEach(function(d){
      var ids=[].slice.call(d.querySelectorAll('a[href*="watch?v="]')).map(function(a){
        var r=a.href.match(/v=([A-Za-z0-9_-]{11})/); return r?r[1]:null;}).filter(Boolean);
      var pend=ids.filter(function(i){var s=m[i]||{}; return !s.added && !s.rej && !s.seen;}).length;
      var b=document.querySelector('nav button[data-slug="'+d.dataset.slug+'"] .c');
      if(b) b.textContent=pend?('· '+pend):'· ✓';
    });
  }catch(e){}
})();
</script>"""


def generar(tandas, salida):
    nav = "".join(
        '<button data-slug="%s">%s<span class="c"></span></button>'
        % (t.slug, html.escape(t.titulo)) for t in tandas)
    out = ['<!doctype html><html lang="es"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1">'
           '<title>CRATE</title><style>%s</style></head><body>' % CSS,
           "<h1>CRATE</h1>", "<nav>%s</nav>" % nav]
    for t in tandas:
        out.append('<div class="tanda" data-slug="%s">' % t.slug)
        out.append('<div class="bajada">%s</div><table>' % t.bajada)
        for i, e in enumerate(t.items, 1):
            vid = e["id"]
            m = META.get(vid, {})
            b = BPM.get(vid, {})
            key = b.get("key") or ""
            kc = ' class="men"' if "minor" in key else ""
            d = e.get("dur") or 0
            v = m.get("views") if m.get("views") is not None else e.get("views")
            info = "%s<br>%s%s<br>%s · %d:%02d" % (
                m.get("year") or "?", _tempo(vid),
                (" · <span%s>%s</span>" % (kc, key)) if key else "",
                _vs(v), d // 60, d % 60)
            out.append('<tr><td class="n">%d</td><td>%s <a href="https://www.youtube.com/watch?v=%s" '
                       'target="_blank">%s</a><div class="ch">%s</div><div class="why">%s</div></td>'
                       '<td class="m">%s</td></tr>'
                       % (i, TIER.get(e.get("tier"), ""), vid,
                          html.escape(e["title"][:92]),
                          html.escape(e.get("uploader") or ""),
                          html.escape(e.get("why", "")), info))
        out.append("</table></div>")
    out.append(SNIP)
    out.append(JS_TABS)
    out.append("</body></html>")
    open(salida, "w", encoding="utf-8").write("\n".join(out))
    return sum(len(t.items) for t in tandas)
