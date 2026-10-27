# -*- coding: utf-8 -*-
"""mi-crate.html: la app local para buscar en la base propia.

Lleva embebidos SOLO los temas de Thomas (sus playlists + lo que guardo de las
sugerencias), que son los que consulta a diario. El resto del pool queda en
crate.db para consultas con SQL.
"""
import json, os, sqlite3, html
HERE = os.path.dirname(os.path.abspath(__file__))
DB = r"G:\Thomi - Mi Carpeta\crate_project\crate.db"
OUT = r"G:\Thomi - Mi Carpeta\crate_project\mi-crate.html"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
filas = con.execute("""
SELECT c.*, (SELECT count(*) FROM archivo f WHERE f.id=c.id) AS tiene
FROM crate c
WHERE c.playlists IS NOT NULL OR c.estado='guardado'
ORDER BY COALESCE(c.estrellas,0) DESC, c.artista
""").fetchall()
datos = [dict(r) for r in filas]
for d in datos:
    for k in ("bpm", "estrellas", "anio", "duracion", "views", "menor", "vivo", "tiene"):
        if d.get(k) is not None:
            d[k] = round(d[k]) if k == "bpm" else d[k]

CSS = """*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;margin:0;padding:18px;background:#f4efe6;color:#2a2420;line-height:1.45}
h1{font-size:1.5rem;margin:0 0 2px}
.sub{color:#6b5d4d;font-size:.9rem;margin:0 0 14px}
.ctrl{position:sticky;top:0;background:#f4efe6;padding:10px 0;border-bottom:1px solid #d9cdb5;z-index:10;margin-bottom:10px}
.ctrl input,.ctrl select{font:inherit;font-size:.9rem;padding:5px 9px;border:1px solid #c9b8a0;border-radius:6px;background:#fffdf7;color:#2a2420}
#q{width:280px}
.ctrl label{font-size:.84rem;color:#6b5d4d;margin-left:10px}
.chips{margin-top:8px;display:flex;flex-wrap:wrap;gap:5px}
.chip{font-size:.8rem;border:1px solid #c9b8a0;background:#efe6d2;border-radius:12px;padding:2px 10px;cursor:pointer;user-select:none}
.chip.on{background:#8b2f1f;border-color:#8b2f1f;color:#fff;font-weight:600}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th{text-align:left;font-size:.78rem;color:#6b5d4d;text-transform:uppercase;letter-spacing:.4px;padding:6px 8px;border-bottom:2px solid #c9b8a0;cursor:pointer;white-space:nowrap}
th:hover{color:#8b2f1f}
td{padding:6px 8px;border-bottom:1px solid #e0d6c4;vertical-align:top}
td.num{text-align:right;white-space:nowrap;color:#6b5d4d;font-size:.86rem}
a{color:#8b2f1f;text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
.men{color:#5a6a4a;font-weight:600}
.est{color:#b08d2e;white-space:nowrap}
.pl{font-size:.74rem;background:#d9cdb5;border-radius:3px;padding:0 5px;margin-right:3px;color:#4a4038;white-space:nowrap}
.muerto{opacity:.5}.muerto a{color:#8a7a66;text-decoration:line-through}
.slsk{font:inherit;font-size:.72rem;cursor:pointer;border:1px solid #c9b8a0;background:#efe6d2;color:#5a4a38;border-radius:9px;padding:0 6px;margin-left:6px}
.slsk:hover{background:#e0d2b4}
#n{color:#6b5d4d;font-size:.86rem;margin:8px 0}
.ok{color:#5a6a4a;font-weight:700}"""

JS = """
const D = DATOS;
let orden='estrellas', desc=true, filtros=new Set();
const $=s=>document.querySelector(s);
const norm=s=>(s||'').normalize('NFKD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();

function limpiar(t){
  return (t||'').replace(/\\([^)]*\\)|\\[[^\\]]*\\]/g,' ')
    .replace(/\\b(official|audio|video|hq|hd|4k|vinyl|rip|full|version|remaster\\w*|lyrics?|unreleased|rare|obscure)\\b/gi,' ')
    .replace(/[\\u266a\\u2022|#]/g,' ').replace(/\\b(19|20)\\d{2}\\b/g,' ')
    .replace(/\\s+/g,' ')
    .replace(/[\\s,·-]*\\b(obscure|rare|northern|modern|sweet|deep|funk|soul|boogie|disco|jazz|and|&|45|single|lp|ep)\\b[\\s,·-]*$/gi,'')
    .replace(/\\s*[-\\u2013\\u2014:]\\s*$/,'').replace(/\\s+/g,' ').trim();
}

function pasa(d){
  const q=norm($('#q').value);
  if(q){
    const blob=norm([d.artista,d.nombre,d.titulo,d.canal,d.tonalidad,d.playlists].join(' '));
    if(!q.split(/\\s+/).every(w=>blob.includes(w))) return false;
  }
  const bmin=+$('#bmin').value||0, bmax=+$('#bmax').value||999;
  if(d.bpm!=null && (d.bpm<bmin||d.bpm>bmax)) return false;
  if((bmin>0||bmax<999) && d.bpm==null) return false;
  const a1=+$('#a1').value||0, a2=+$('#a2').value||9999;
  if(d.anio!=null && (d.anio<a1||d.anio>a2)) return false;
  if((a1>0||a2<9999) && d.anio==null) return false;
  for(const f of filtros){
    if(f==='menor'   && d.menor!==1) return false;
    if(f==='estrella'&& !d.estrellas) return false;
    if(f==='sinbajar'&& d.tiene>0) return false;
    if(f==='bajado'  && !d.tiene) return false;
    if(f==='caido'   && d.vivo!==0) return false;
    if(f.startsWith('pl:') && !(d.playlists||'').includes(f.slice(3))) return false;
  }
  return true;
}

function pintar(){
  const r=D.filter(pasa);
  r.sort((a,b)=>{
    let x=a[orden],y=b[orden];
    if(x==null)x=desc?-Infinity:Infinity; if(y==null)y=desc?-Infinity:Infinity;
    if(typeof x==='string'){x=norm(x);y=norm(y);}
    return (x<y?-1:x>y?1:0)*(desc?-1:1);
  });
  $('#n').innerHTML='<b>'+r.length+'</b> temas'+(r.length!==D.length?' de '+D.length:'')
    +' · '+r.filter(d=>d.tiene).length+' ya en el disco';
  $('#cuerpo').innerHTML=r.map(d=>{
    const pl=(d.playlists||'').split(' + ').filter(Boolean).map(p=>'<span class="pl">'+p+'</span>').join('');
    const est=d.estrellas?'<span class="est">'+'★'.repeat(d.estrellas)+'</span>':'';
    const ton=d.tonalidad?('<span class="'+(d.menor?'men':'')+'">'+d.tonalidad+'</span>'):'-';
    return '<tr class="'+(d.vivo===0?'muerto':'')+'">'
      +'<td>'+(d.tiene?'<span class="ok">✓</span> ':'')
      +'<a href="'+d.url+'" target="_blank">'+esc(d.artista||d.titulo)+'</a>'
      +'<button class="slsk" data-q="'+esc(limpiar(d.titulo))+'">⇩</button>'
      +'<div style="color:#4a4038">'+esc(d.nombre||'')+'</div>'
      +'<div style="font-size:.78rem;color:#6b5d4d">'+esc(d.canal||'')+' '+pl+'</div></td>'
      +'<td class="num">'+(d.anio||'-')+'</td>'
      +'<td class="num">'+(d.bpm||'-')+'</td>'
      +'<td class="num">'+ton+'</td>'
      +'<td class="num">'+est+'</td></tr>';
  }).join('');
}
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

document.addEventListener('click',e=>{
  const b=e.target.closest('.slsk');
  if(b){ navigator.clipboard?.writeText(b.dataset.q).then(()=>{
      b.textContent='✓'; setTimeout(()=>b.textContent='⇩',1200);
    },()=>prompt('Copiá para Soulseek:',b.dataset.q)); return; }
  const c=e.target.closest('.chip');
  if(c){ const f=c.dataset.f; filtros.has(f)?filtros.delete(f):filtros.add(f);
         c.classList.toggle('on'); pintar(); }
});
document.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{
  const k=th.dataset.k; desc = (orden===k)? !desc : true; orden=k; pintar();
});
['q','bmin','bmax','a1','a2'].forEach(id=>$('#'+id).addEventListener('input',pintar));
pintar();
"""

pls = sorted({p for d in datos for p in (d.get("playlists") or "").split(" + ") if p})
chips = "".join('<span class="chip" data-f="pl:%s">%s</span>' % (p, html.escape(p)) for p in pls)
con_arch = sum(1 for d in datos if d.get("tiene"))

doc = """<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mi crate</title><style>%s</style></head><body>
<h1>Mi crate</h1>
<p class="sub">%d temas propios · %d en el disco · base completa en <code>crate.db</code> (51.366 temas)</p>
<div class="ctrl">
  <input id="q" placeholder="buscar artista, tema, canal, tonalidad…">
  <label>BPM <input id="bmin" type="number" style="width:62px" placeholder="min">
  – <input id="bmax" type="number" style="width:62px" placeholder="max"></label>
  <label>año <input id="a1" type="number" style="width:70px" placeholder="desde">
  – <input id="a2" type="number" style="width:70px" placeholder="hasta"></label>
  <div class="chips">
    <span class="chip" data-f="menor">tonalidad menor</span>
    <span class="chip" data-f="estrella">con estrellas</span>
    <span class="chip" data-f="sinbajar">falta bajar</span>
    <span class="chip" data-f="bajado">ya en el disco</span>
    <span class="chip" data-f="caido">video caído</span>
    %s
  </div>
</div>
<div id="n"></div>
<table><thead><tr>
  <th data-k="artista">tema</th><th data-k="anio" class="num">año</th>
  <th data-k="bpm" class="num">bpm</th><th data-k="tonalidad" class="num">tono</th>
  <th data-k="estrellas" class="num">★</th>
</tr></thead><tbody id="cuerpo"></tbody></table>
<script>const DATOS=%s;</script><script>%s</script></body></html>""" % (
    CSS, len(datos), con_arch, chips,
    json.dumps(datos, ensure_ascii=False), JS)

open(OUT, "w", encoding="utf-8").write(doc)
print("%d temas -> %s (%.1f MB)" % (len(datos), OUT, os.path.getsize(OUT) / 1e6))
