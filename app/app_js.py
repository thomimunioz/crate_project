# -*- coding: utf-8 -*-
"""Logica de la app. Todo lo que Thomas cambia se guarda en localStorage y
despues `bd_sync.py` lo vuelca a crate.db, que es la fuente de verdad.
Asi la app funciona sin servidor y nada se pierde."""

JS = r"""
const D = DATOS;
const LS = 'crate-local';           // lo que el usuario cambia desde la app
let local = {};
try { local = JSON.parse(localStorage.getItem(LS) || '{}') || {}; } catch(e){}
const guardarLocal = () => { try{ localStorage.setItem(LS, JSON.stringify(local)); }catch(e){} };
let BUSQUEDA = [];
/* cuando corre bajo crate_server.py se guarda DIRECTO en crate.db */
const servidor = location.protocol.startsWith('http');
function aServidor(ruta, cuerpo){
  if(!servidor) return Promise.resolve(null);
  return fetch(ruta,{method:'POST',headers:{'Content-Type':'application/json'},
                     body:JSON.stringify(cuerpo)}).catch(()=>null);
}
/* Un tema que saliste a buscar (hotlist o YouTube) no esta en DATOS: entra a la
   tabla recien cuando el servidor lo guarda. Lo sumamos en caliente, sin F5. */
function sumarACrate(fila){
  if(!fila || !fila.id) return false;
  const i = D.findIndex(x => x.id === fila.id);
  if(i >= 0){ D[i] = Object.assign({}, D[i], fila); return false; }
  fila.cat = 'CR·' + String(D.length + 1).padStart(4, '0');
  D.push(fila);
  return true;
}

function ponerEstrellas(id, n){
  local[id] = Object.assign({}, local[id], {estrellas:n});
  guardarLocal();
  // si sale de una busqueda, el tema todavia no esta en la base: va con todos
  // sus datos para que entre completo y no quede una marca huerfana
  const b = (BUSQUEDA||[]).find(x=>x.id===id);
  const cuerpo = b
    ? {id, estrellas:n, titulo:b.titulo, canal:b.canal, dur:b.dur, views:b.views}
    : {id, estrellas:n};
  aServidor('/api/estrellas', cuerpo).then(async r=>{
    if(!r) return;
    try{
      const j = await r.json();
      if(j && j.tema){ sumarACrate(j.tema); pintar(); marcarSonando(); }
      if(j && j.nuevo) flash('guardado en tu crate · ' + (n?n+'★':'sin puntaje'));
      else if(n) flash('puntuado ' + n + '★');
    }catch(e){}
  });
}

/* avisito breve, para que sepas que quedó guardado */
function flash(txt){
  let el = document.getElementById('flash');
  if(!el){
    el = document.createElement('div');
    el.id = 'flash';
    document.body.appendChild(el);
  }
  el.textContent = txt;
  el.classList.add('on');
  clearTimeout(el._t);
  el._t = setTimeout(()=>el.classList.remove('on'), 2200);
}

const $  = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const norm = s => (s||'').normalize('NFKD').replace(/[̀-ͯ]/g,'').toLowerCase();
const esc  = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

let orden = 'estrellas', desc = true;
const filtros = new Set();

/* --- el nombre limpio, para buscarlo en Soulseek --- */
function limpiar(t){
  return (t||'')
    .replace(/\([^)]*\)|\[[^\]]*\]/g,' ')
    .replace(/\b(official|audio|video|hq|hd|4k|vinyl|rip|full|version|remaster\w*|lyrics?|visualizer|unreleased|rare|obscure)\b/gi,' ')
    .replace(/[♪•|#]/g,' ')
    .replace(/\b(19|20)\d{2}\b/g,' ')
    .replace(/\s+/g,' ')
    .replace(/[\s,·-]*\b(obscure|rare|northern|modern|sweet|deep|funk|soul|boogie|disco|jazz|and|&|45|single|lp|ep)\b[\s,·-]*$/gi,'')
    .replace(/\s*[-–—:]\s*$/,'')
    .replace(/\s+/g,' ').trim();
}
const estado = d => local[d.id] || {};
const tiene  = d => estado(d).bajado !== undefined ? estado(d).bajado : d.tiene > 0;
const estrellasDe = d => estado(d).estrellas !== undefined ? estado(d).estrellas : d.estrellas;

/* las listas donde puede ir un tema. Las cinco de siempre mas las que pidio
   el 27-oct: piano, folk y dark. */
const LISTAS = ['80s','SOUL','R&B SOUL','CITY POP','JAZZ FUSION',
                'PIANO','FOLK','DARK'];
/* cada lista tiene su color; la clase lo aplica */
const CLASE_G = {'SOUL':'g-soul','80s':'g-80s','R&B SOUL':'g-rnb','DARK':'g-dark',
                 'JAZZ FUSION':'g-fusion','CITY POP':'g-citypop','PIANO':'g-piano',
                 'FOLK':'g-folk'};
const clg = L => CLASE_G[L] || '';

function listasDe(d){
  const l = local[d.id] && local[d.id].listas;
  if(l) return l;
  return (d.playlists||'').split(chr10).filter(Boolean);
}
const chr10 = String.fromCharCode(10);

function clasif(d){
  const mias = listasDe(d);
  const et = mias.length ? mias.join(' · ') : '+ lista';
  return '<span class="clasif" data-cl="'+d.id+'">'
    + '<button class="btn-cl" title="a qué lista va">'+esc(et)+'</button>'
    + '<div class="menu-cl">'
    +   LISTAS.map(L=>'<button data-l="'+esc(L)+'" class="'+clg(L)+' '
        + (mias.includes(L)?'ya':'') + '">'+esc(L)+'</button>').join('')
    + '</div></span>';
}

function rating(id, e){
  return '<span class="rating">'
    + '<span class="estrellas" data-est="'+id+'" title="puntuar del 1 al 5">'
    + [1,2,3,4,5].map(n=>'<span class="s '+(n<=(e||0)?'on':'off')+'" data-n="'+n+'">★</span>').join('')
    + '</span>'
    + (e ? '<button class="quitar" data-quitar="'+id+'" title="quitar puntaje">✕</button>' : '')
    + '</span>';
}

function pasa(d){
  const q = norm($('#q').value);
  if(q){
    const blob = norm([d.artista,d.nombre,d.titulo,d.canal,d.tonalidad,d.playlists,d.anio].join(' '));
    if(!q.split(/\s+/).every(w => blob.includes(w))) return false;
  }
  const bmin=+$('#bmin').value||0, bmax=+$('#bmax').value||9999;
  if(bmin||bmax<9999){ if(d.bpm==null || d.bpm<bmin || d.bpm>bmax) return false; }
  const a1=+$('#a1').value||0, a2=+$('#a2').value||9999;
  if(a1||a2<9999){ if(d.anio==null || d.anio<a1 || d.anio>a2) return false; }
  for(const f of filtros){
    if(f==='menor'    && d.menor!==1) return false;
    if(f==='estrella' && !estrellasDe(d)) return false;
    if(f==='top'      && (estrellasDe(d)||0) < 4) return false;
    if(f==='falta'    && tiene(d)) return false;
    if(f==='disco'    && !tiene(d)) return false;
    if(f==='sinbpm'   && d.bpm!=null) return false;
    if(f.startsWith('pl:') && !(d.playlists||'').split('\n').includes(f.slice(3))) return false;
  }
  return true;
}

function pintar(){
  if(modoBusqueda){ pintarBusqueda(BUSQUEDA); return; }
  const r = D.filter(pasa);
  r.sort((a,b)=>{
    let x = orden==='estrellas' ? (estrellasDe(a)||0) : a[orden];
    let y = orden==='estrellas' ? (estrellasDe(b)||0) : b[orden];
    if(x==null) x = desc ? -Infinity : Infinity;
    if(y==null) y = desc ? -Infinity : Infinity;
    if(typeof x==='string'){ x=norm(x); y=norm(y); }
    return (x<y?-1:x>y?1:0)*(desc?-1:1);
  });

  const enDisco = r.filter(tiene).length;
  const m0=$('#modo');
  if(m0) m0.innerHTML = 'mi crate <span class="det">lo que ya es tuyo</span>';
  $('#conteo').innerHTML =
      '<b>'+r.length+'</b> ' + (r.length===1?'tema':'temas')
    + (r.length!==D.length ? ' <span class="der">de '+D.length+'</span>' : '');
  $('#conteo2').textContent = enDisco + ' en el disco · ' + (r.length-enDisco) + ' por bajar';

  $('#cuerpo').innerHTML = r.length ? r.map((d,i)=>{
    const e  = estrellasDe(d);
    const mias = listasDe(d);
    const pl = mias.map(p=>'<span class="pl '+clg(p)+'">'+esc(p)+'</span>').join('');
    const gcls = mias.length ? clg(mias[0]) : '';   // la fila toma el color del 1er genero
    const ton = d.tonalidad ? '<span class="'+(d.menor?'men':'')+'">'+esc(d.tonalidad)+'</span>' : '·';
    return '<tr data-id="'+d.id+'" class="'+gcls+'">'
      + '<td class="cat">'+d.cat+'</td>'
      + '<td>'
        + (tiene(d) ? '<span class="bajado" title="ya está en el disco">EN DISCO</span>' : '')
        + '<span class="tem">'+esc(d.nombre || d.titulo)+'</span>'
        + '<a class="art" href="'+d.url+'" target="_blank" rel="noopener">'
        +   esc(d.artista || '—')+'</a>'
        + '<button class="slsk" data-q="'+esc(limpiar(d.titulo))+'" data-id="'+esc(d.id)+'" title="buscar en Soulseek">⇩ slsk</button>'
        + '<div class="meta">'+(d.canal?'<span>'+esc(d.canal)+'</span>':'')+pl+'</div>'
      + '</td>'
      + '<td class="dato">'+(d.anio ? '<span class="v">'+d.anio+'</span>' : '·')+'</td>'
      + '<td class="dato">'+(d.bpm ? '<span class="v">'+d.bpm+'</span><span class="u">bpm</span>' : '·')+'</td>'
      + '<td class="dato">'+(d.tonalidad
            ? '<span class="v'+(d.menor?' men':'')+'">'+esc(d.tonalidad.replace(' minor','m').replace(' major',''))+'</span>'
            : '·')+'</td>'
      + '<td class="est">'+clasif(d)+' '+rating(d.id, e)+'</td></tr>';
  }).join('') : '<tr><td colspan="6" class="vacio">nada con esos filtros</td></tr>';
}

/* --- acciones --- */
document.addEventListener('click', e => {
  // toda la fila reproduce. Antes el area de click era el enlace del artista,
  // que cuando no hay artista es un guion de 10 pixeles.
  const fila = e.target.closest('tr[data-id]');
  if(fila && servidor && !e.ctrlKey && !e.metaKey && !e.shiftKey
     && !e.target.closest('.estrellas, [data-quitar], .slsk, .clasif, a')){
    if(reproducir(fila.dataset.id)){ e.preventDefault(); return; }
  }
  const a = e.target.closest('a.art');
  if(a && servidor && !e.ctrlKey && !e.metaKey && !e.shiftKey){
    const tr = a.closest('tr[data-id]');
    if(tr){
      // Se frena SIEMPRE, ande o no. Si reproducir() falla (tipico: el
      // reproductor de YouTube todavia no termino de cargar) antes el click
      // se escapaba al href y se abria una pestaña sin que lo pidieras.
      // Para ir a YouTube a proposito: ctrl+click o boton del medio.
      e.preventDefault();
      reproducir(tr.dataset.id);
      return;
    }
  }
  const b = e.target.closest('.slsk');
  if(b){
    e.preventDefault(); e.stopPropagation();
    buscarEnSoulseek(b.dataset.q, b, b.dataset.id);
    return;
  }
  const s = e.target.closest('.estrellas .s');
  if(s){                                     // puntuar: click en la estrella misma
    const cont = s.closest('.estrellas');
    const id = cont.dataset.est;
    const d  = D.find(x=>x.id===id);
    const n  = +s.dataset.n;
    ponerEstrellas(id, n);          // la estrella solo PONE; quitar es aparte
    pintar(); if(sonando && sonando.id===id) pintarEstrellasPlayer();
    marcarSonando();
    return;
  }
  const bc = e.target.closest('.btn-cl');
  if(bc){
    e.preventDefault(); e.stopPropagation();
    const cont = bc.closest('.clasif');
    const abierto = cont.classList.contains('abierto');
    $$('.clasif.abierto').forEach(x=>x.classList.remove('abierto','arriba'));
    if(!abierto){
      // ¿entra para abajo? El reproductor ocupa los ultimos ~96px
      const r = bc.getBoundingClientRect();
      const menu = cont.querySelector('.menu-cl');
      const alto = (menu && menu.scrollHeight) || 290;
      const piso = window.innerHeight - (document.body.classList.contains('conplayer') ? 100 : 12);
      const cabe = (r.bottom + 6 + alto) <= piso;
      cont.classList.toggle('arriba', !cabe && r.top > alto + 20);
      cont.classList.add('abierto');
    }
    return;
  }
  const op = e.target.closest('.menu-cl button');
  if(op){
    e.preventDefault(); e.stopPropagation();
    const cont = op.closest('.clasif');
    const id = cont.dataset.cl;
    const L = op.dataset.l;
    const d = D.find(x=>x.id===id) || (BUSQUEDA||[]).find(x=>x.id===id);
    const mias = listasDe(d);
    const quitar = mias.includes(L);
    const nuevas = quitar ? mias.filter(x=>x!==L) : mias.concat([L]);
    local[id] = Object.assign({}, local[id], {listas:nuevas});
    guardarLocal();
    const b = (BUSQUEDA||[]).find(x=>x.id===id);
    aServidor('/api/playlist', Object.assign({id, playlist:L, quitar},
      b ? {titulo:b.titulo, canal:b.canal, dur:b.dur, views:b.views} : {}))
      .then(async r => {
        if(!r) return;
        try{
          const j = await r.json();
          if(j && j.tema){
            // el servidor manda la fila ya armada: el tema queda buscable y
            // filtrable al instante, sin recargar
            const es_nuevo = sumarACrate(j.tema);
            delete local[id];            // ya esta en la base, sin pendiente
            guardarLocal();
            pintar(); marcarSonando();
            if(es_nuevo) flash('va a ' + L + ' · ya es tuyo');
          }
        }catch(e){}
      });
    flash(quitar ? ('sacado de ' + L) : ('va a ' + L));
    cont.classList.remove('abierto');
    pintar();
    return;
  }
  const qb = e.target.closest('[data-quitar]');
  if(qb){
    e.preventDefault(); e.stopPropagation();
    if(qb.classList.contains('preg')){          // segundo click: confirmado
      ponerEstrellas(qb.dataset.quitar, 0);
      pintar(); if(sonando) pintarEstrellasPlayer(); marcarSonando();
    } else {                                     // primer click: pregunta
      $$('.quitar.preg').forEach(x=>{ x.classList.remove('preg'); x.textContent='✕'; });
      qb.classList.add('preg'); qb.textContent='¿quitar?';
      clearTimeout(qb._t);
      qb._t = setTimeout(()=>{ qb.classList.remove('preg'); qb.textContent='✕'; }, 3200);
    }
    return;
  }
  const c = e.target.closest('.chip');
  if(c){
    const f = c.dataset.f;
    filtros.has(f) ? filtros.delete(f) : filtros.add(f);
    c.classList.toggle('on'); pintar();
  }
});

/* --- hover del rating: se ve que va a pasar antes de hacer click --- */
document.addEventListener('mouseover', e => {
  const s = e.target.closest('.estrellas .s');
  if(!s) return;
  const cont = s.closest('.estrellas');
  const d = D.find(x => x.id === cont.dataset.est);
  const act = estrellasDe(d) || 0;
  const n = +s.dataset.n;
  cont.querySelectorAll('.s').forEach(x => {
    const k = +x.dataset.n;
    x.classList.toggle('pre', k <= n && k > act);
  });
});
document.addEventListener('mouseout', e => {
  const cont = e.target.closest('.estrellas');
  if(!cont || cont.contains(e.relatedTarget)) return;
  cont.querySelectorAll('.s').forEach(x => x.classList.remove('pre'));
});

/* marcar que ya está en el disco: doble click en la fila */
document.addEventListener('click', e => {
  if(!e.target.closest('.clasif')) $$('.clasif.abierto').forEach(x=>x.classList.remove('abierto'));
}, true);

document.addEventListener('dblclick', e => {
  const tr = e.target.closest('tr[data-id]');
  if(!tr) return;
  const id = tr.dataset.id, d = D.find(x=>x.id===id);
  const v = !tiene(d);
  local[id] = Object.assign({}, local[id], {bajado: v});
  guardarLocal(); aServidor('/api/archivo', {id, tiene:v}); pintar(); marcarSonando();
});

$$('thead th[data-k]').forEach(th => th.onclick = () => {
  const k = th.dataset.k;
  desc = (orden === k) ? !desc : true;
  orden = k;
  $$('thead th').forEach(x=>x.classList.remove('act'));
  th.classList.add('act');
  th.querySelector('.f').textContent = desc ? '▾' : '▴';
  pintar();
});
['bmin','bmax','a1','a2'].forEach(id => {
  const el = $('#'+id);
  el.addEventListener('input', () => {
    const limpio = el.value.replace(/[^0-9]/g, '');   // ni signos ni letras
    if(limpio !== el.value) el.value = limpio;
    pintar();
  });
});
$('#q').addEventListener('input', pintar);
$('#limpiar').onclick = () => {
  ['q','bmin','bmax','a1','a2'].forEach(id => $('#'+id).value = '');
  filtros.clear();
  $$('.chip.on').forEach(c => { if(c.dataset.f) c.classList.remove('on'); });
  pintar();
};

/* atajos: / busca, Esc limpia */
document.addEventListener('keydown', e => {
  if(e.key === '/' && document.activeElement !== $('#q')){ e.preventDefault(); $('#q').focus(); }
  if(e.key === 'Escape'){ $('#q').value=''; $('#q').blur(); pintar(); }
  if(document.activeElement.tagName === 'INPUT') return;
  if(e.code === 'Space' && sonando){ e.preventDefault(); $('#pplay').click(); }
  if(e.key === 'n' || e.key === 'N'){ siguiente(1); }
  if(e.key === 'p' || e.key === 'P'){ siguiente(-1); }
  if(/^[1-5]$/.test(e.key) && sonando){
    ponerEstrellas(sonando.id, +e.key);
    pintarEstrellasPlayer(); pintar(); marcarSonando();
  }
});

/* exportar lo que cambié, para volcarlo a la base */
$('#exp').onclick = () => {
  const payload = {fecha:new Date().toISOString(), cambios:local};
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(payload,null,1)],{type:'application/json'}));
  a.download = 'crate-cambios.json'; a.click();
};

/* --- selector de paleta --- */
const TEMA='crate-tema';
function ponerTema(t){
  document.body.dataset.t=t;
  $$('.temas button').forEach(b=>b.classList.toggle('on',b.dataset.t===t));
  try{ localStorage.setItem(TEMA,t); }catch(e){}
}
$$('.temas button').forEach(b=>b.onclick=()=>ponerTema(b.dataset.t));
let t0='foryou'; try{ t0=localStorage.getItem(TEMA)||'foryou'; }catch(e){}
ponerTema(t0);


/* =======================================================================
   REPRODUCTOR
   El iframe de YouTube solo anda servido por http; desde file:// el navegador
   trata la pagina como origen nulo. Por eso existe crate_server.py.
   ======================================================================= */
let YT_OK=false, yt=null, cola=[], iCola=-1, sonando=null, reloj=null;
let modo='yt';                     // 'yt' = iframe · 'audio' = stream directo
const AUD = new Audio();
AUD.preload = 'none';
AUD.addEventListener('ended', ()=>siguiente(1));
AUD.addEventListener('error', ()=>{
  if(modo==='audio' && sonando) avisar('no pude traer el audio de ese tema');
});
/* el icono del boton tiene que reflejar lo que pasa, venga del iframe o del
   audio. Antes solo lo actualizaba el iframe y en modo audio quedaba pegado. */
const iconoPlay = reproduciendo => {
  const b = document.getElementById('pplay');
  if(b) b.innerHTML = reproduciendo ? '&#10074;&#10074;' : '&#9654;';
};
AUD.addEventListener('play',    ()=>iconoPlay(true));
AUD.addEventListener('playing', ()=>iconoPlay(true));
AUD.addEventListener('pause',   ()=>iconoPlay(false));
AUD.addEventListener('ended',   ()=>iconoPlay(false));
const servido = location.protocol.startsWith('http');

window.onYouTubeIframeAPIReady = function(){
  yt = new YT.Player('yt', {
    height:'1', width:'1', playerVars:{playsinline:1, rel:0, modestbranding:1,
      controls:0, disablekb:1, fs:0, iv_load_policy:3},
    events:{
      onReady: ()=>{ YT_OK=true; },
      onStateChange: e=>{
        if(e.data===YT.PlayerState.ENDED) siguiente();
        $('#pplay').innerHTML = (e.data===YT.PlayerState.PLAYING)?'&#10074;&#10074;':'&#9654;';
      },
      onError: ()=>{ noEmbebible(sonando && sonando.id); }
    }
  });
};

/* algunos videos tienen el embebido bloqueado por quien los subio. No se
   pierden: se marcan y se abren en YouTube, pero siguen en la lista y se
   pueden puntuar igual. */
const NOEMB = 'crate-noemb';
let noEmb = {};
try{ noEmb = JSON.parse(localStorage.getItem(NOEMB)||'{}')||{}; }catch(e){}

function noEmbebible(id){
  if(!id) return;
  noEmb[id] = 1;
  try{ localStorage.setItem(NOEMB, JSON.stringify(noEmb)); }catch(e){}
  if(servidor){ porAudio(id); return; }      // respaldo: sin salir de la app
  const d = D.find(x=>x.id===id) || (BUSQUEDA||[]).find(x=>x.id===id);
  const nom = d ? (d.artista || d.titulo) : 'este tema';
  $('#player .pa').textContent = nom;
  $('#player .pt').innerHTML =
      'no se puede escuchar acá — <a href="https://www.youtube.com/watch?v='+id+'" '
    + 'target="_blank" style="color:var(--acento);text-decoration:underline">abrir en YouTube</a>'
    + ' · <span id="saltar" style="cursor:pointer;text-decoration:underline">siguiente</span>';
  const sa = document.getElementById('saltar');
  if(sa) sa.onclick = ()=>siguiente(1);
  $('#pista .av').style.width = '0%';
  marcarSonando();
}

/* respaldo: el servidor saca la URL del audio con yt-dlp y la retransmite.
   Asi se escuchan tambien los videos que bloquean el embebido. */
function porAudio(id){
  modo = 'audio';
  if(yt && yt.stopVideo) try{ yt.stopVideo(); }catch(e){}
  $('#player .pt').textContent = 'trayendo el audio…';

  const d = sonando;
  const detalle = d ? [d.nombre, d.anio, d.bpm?d.bpm+' bpm':'', d.tonalidad]
                        .filter(Boolean).join(' · ') : '';
  const fallo = () => {
    $('#player .pt').innerHTML = 'no pude reproducirlo — '
      + '<a href="https://www.youtube.com/watch?v='+id+'" target="_blank" '
      + 'style="color:var(--acento);text-decoration:underline">abrir en YouTube</a>';
  };

  // llamar a play() apenas se setea el src falla: el elemento todavia no tiene
  // datos. Hay que esperar a que pueda reproducir.
  AUD.oncanplay = null; AUD.onerror = null;
  AUD.src = '/api/audio/' + id;
  AUD.load();
  let arranco = false;
  AUD.oncanplay = () => {
    if(arranco) return;
    arranco = true;
    AUD.play().then(()=>{
      $('#player .pt').textContent = detalle;
    }).catch(fallo);
  };
  AUD.onerror = fallo;
  setTimeout(()=>{ if(!arranco && AUD.readyState < 3) fallo(); }, 25000);
}

function avisar(txt){
  const el=$('#player .pt'); if(!el) return;
  const antes=el.textContent; el.textContent=txt;
  setTimeout(()=>{ if(el.textContent===txt) el.textContent=antes; },2600);
}
const fmt = s => isFinite(s) ? Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0') : '0:00';

function reproducir(id){
  if(!servido){ avisar('abrí la app con crate_server.py para escuchar acá'); return false; }
  if(!YT_OK || !yt){ avisar('cargando reproductor…'); return false; }
  const d = D.find(x=>x.id===id) || (BUSQUEDA||[]).find(x=>x.id===id);
  if(!d) return false;
  sonando = d;
  // limpieza completa: sin esto, a los 5 o 6 temas el reproductor se traba
  clearInterval(reloj);
  try{ AUD.pause(); }catch(e){}
  AUD.oncanplay = null; AUD.onerror = null;
  if(AUD.src){ AUD.removeAttribute('src'); AUD.load(); }
  if(yt && yt.stopVideo) try{ yt.stopVideo(); }catch(e){}
  modo = noEmb[id] ? 'audio' : 'yt';
  cola = [...document.querySelectorAll('#cuerpo tr[data-id]')].map(tr=>tr.dataset.id);
  iCola = cola.indexOf(id);
  iconoPlay(true);                      // arranca reproduciendo
  if(modo==='audio') porAudio(id); else yt.loadVideoById(id);
  $('#player').classList.add('on');
  document.body.classList.add('conplayer');
  $('#cover').src = 'https://i.ytimg.com/vi/'+id+'/mqdefault.jpg';
  $('#cover').onerror = ()=>{ $('#cover').style.visibility='hidden'; };
  $('#cover').style.visibility='visible';
  $('#player .pa').textContent = d.artista || d.titulo;
  $('#player .pt').textContent = [d.nombre, d.anio, d.bpm?d.bpm+' bpm':'', d.tonalidad]
      .filter(Boolean).join(' · ');
  pintarEstrellasPlayer();
  marcarSonando();
  clearInterval(reloj);
  reloj = setInterval(()=>{
    let t=0, dd=0;
    if(modo==='audio'){ t=AUD.currentTime||0; dd=AUD.duration||0; }
    else { if(!yt || !yt.getDuration) return; t=yt.getCurrentTime()||0; dd=yt.getDuration()||0; }
    $('#ptact').textContent = fmt(t);
    $('#pttot').textContent = fmt(dd);
    const pc = dd ? (t/dd*100) : 0;
    $('#pista .av').style.width = pc+'%';
    $('#pista .bolita').style.left = pc+'%';
  }, 250);
  return true;
}
function marcarSonando(){
  $$('#cuerpo tr').forEach(tr=>{
    const es = !!(sonando && tr.dataset.id===sonando.id);
    tr.classList.toggle('sonando', es);
    tr.classList.toggle('noemb', !!noEmb[tr.dataset.id]);
    const c = tr.querySelector('td.cat');
    if(!c) return;
    if(es && !c.querySelector('.eq'))
      c.insertAdjacentHTML('afterbegin','<span class="eq"><i></i><i></i><i></i></span>');
    if(!es){ const eq=c.querySelector('.eq'); if(eq) eq.remove(); }
  });
}
function pintarEstrellasPlayer(){
  if(!sonando) return;
  const e = estrellasDe(sonando)||0;
  $('#player .pest').innerHTML = [1,2,3,4,5]
    .map(n=>'<span class="s '+(n<=e?'on':'off')+'" data-pn="'+n+'">★</span>').join('');
}
function siguiente(d=1){
  if(!cola.length) return;
  iCola = (iCola + d + cola.length) % cola.length;
  reproducir(cola[iCola]);
}
$('#pista').addEventListener('click', e=>{
  const r = e.currentTarget.getBoundingClientRect();
  const f = (e.clientX - r.left)/r.width;
  if(modo==='audio'){ if(AUD.duration) AUD.currentTime = f*AUD.duration; }
  else if(yt && yt.getDuration) yt.seekTo(f*yt.getDuration(), true);
});
$('#pnext').onclick = ()=>siguiente(1);
$('#pprev').onclick = ()=>siguiente(-1);
$('#pplay').onclick = ()=>{
  if(modo==='audio'){
    if(AUD.paused) AUD.play(); else AUD.pause();   // el icono lo maneja el evento
    return;
  }
  if(!yt) return;
  const e=yt.getPlayerState(); (e===YT.PlayerState.PLAYING)?yt.pauseVideo():yt.playVideo(); };
$('#pcerrar').onclick = ()=>{ if(yt) try{yt.stopVideo();}catch(e){} AUD.pause(); AUD.src='';
  clearInterval(reloj);
  $('#player').classList.remove('on'); document.body.classList.remove('conplayer');
  sonando=null; marcarSonando(); };
$('#player .pest').addEventListener('click', e=>{
  const s=e.target.closest('[data-pn]'); if(!s||!sonando) return;
  ponerEstrellas(sonando.id, +s.dataset.pn); pintarEstrellasPlayer(); pintar(); marcarSonando();
});


/* =======================================================================
   DIGGEAR EN YOUTUBE DESDE LA APP
   Thomas escribe "soul" y el servidor le agrega todo lo que fuimos midiendo:
   expande la busqueda, descarta con los criterios y ordena por lo que rinde.
   ======================================================================= */
let modoBusqueda = false;

/* En el hotlist el artista a veces no viene separado del titulo (lo que trae
   el buscador es el titulo crudo de YouTube). En ese caso firma con el canal,
   que es lo que de verdad importa: quien lo subio. */
function firmaDe(d){
  if(d.artista && d.artista !== d.titulo) return d.artista;
  return d.canal || '—';
}

function pintarBusqueda(res){
  $('#cuerpo').innerHTML = res.length ? res.map((d,i)=>{
    const e = estrellasDe(d)||0;
    const raz = (d.razones||[]).slice(0,2).join(' · ');
    return '<tr data-id="'+d.id+'" class="nuevo">'
      + '<td class="cat">+'+String(i+1).padStart(3,'0')+'</td>'
      + '<td>'
        // Misma estructura que la tabla principal: el TEMA es un span grande y
        // clickeable (toda la fila reproduce), y el link a YouTube es solo la
        // firma de abajo. Antes el titulo entero era el <a>, asi que si el
        // reproductor todavia estaba cargando el click se escapaba al link y
        // se abria una pestaña. Ahora no hay forma de que eso pase.
        + '<span class="tem">'+esc(d.nombre || d.titulo)+'</span>'
        + '<a class="art" href="https://www.youtube.com/watch?v='+d.id+'"'
        +   ' target="_blank" rel="noopener" title="abrir en YouTube">'
        +   esc(firmaDe(d))+'</a>'
        + '<button class="slsk" data-q="'+esc(limpiar(d.titulo))+'" data-id="'+esc(d.id)+'">⇩ slsk</button>'
        + '<div class="meta">'+esc(d.canal||'')+'</div>'
        + (raz?'<div class="razon">'+esc(raz)+'</div>':'')
      + '</td>'
      // Las TRES celdas llevan etiqueta, si o si. .v es display:block, asi que
      // la unidad siempre cae abajo: una celda con etiqueta mide dos renglones
      // y una sin etiqueta mide uno. Con vertical-align:middle la de un
      // renglon queda centrada respecto de las otras y se ve torcida. Ademas
      // la etiqueta va en <span class="u"> y no en texto pelado despues de un
      // <br>, para que tome el estilo de la tabla principal.
      + '<td class="dato">'+(d.views!=null
            ? '<span class="v">'+(d.views>=1000?Math.round(d.views/1000)+'k':d.views)
              +'</span><span class="u">views</span>'
            : '·')+'</td>'
      + '<td class="dato">'+(d.bpm
            ? '<span class="v">'+Math.round(d.bpm)+'</span><span class="u">bpm</span>'
            : '·')+'</td>'
      + '<td class="dato">'+(d.dur
            ? '<span class="v">'+Math.floor(d.dur/60)+':'+String(d.dur%60).padStart(2,'0')
              +'</span><span class="u">largo</span>'
            : '·')+'</td>'
      + '<td class="est">'+clasif(d)+' '+rating(d.id, e)+'</td></tr>';
  }).join('') : '<tr><td colspan="6" class="vacio">no quedo nada después de filtrar</td></tr>';
  marcarSonando();
}

$('#bcavar').onclick = async () => {
  const q = $('#qy').value.trim();
  if(!q) return;
  if(!servidor){ $('#cavinfo').innerHTML = 'esto necesita <b>crate_server.py</b>'; return; }
  $('#bcavar').textContent = 'cavando…';
  $('#cavinfo').textContent = 'yt-dlp está buscando, puede tardar un rato';
  try{
    const r = await fetch('/api/buscar',{method:'POST',headers:{'Content-Type':'application/json'},
                                         body:JSON.stringify({q})});
    const j = await r.json();
    if(!j.ok){ $('#cavinfo').textContent = 'error: '+(j.error||'?'); return; }
    BUSQUEDA = j.resultados.map(x=>Object.assign({},x,{titulo:x.titulo,artista:x.titulo}));
    modoBusqueda = true;
    document.body.classList.add('buscando');
    pintarBusqueda(BUSQUEDA);
    const d = j.info.descartes || {};
    const top = Object.entries(d).sort((a,b)=>b[1]-a[1]).slice(0,3)
                  .map(([k,v])=>v+' '+k).join(' · ');
    const m1=$('#modo');
    if(m1) m1.innerHTML = 'cavando youtube <span class="det">puntuá y entra a tu crate</span>';
    $('#conteo').innerHTML = '<b>'+BUSQUEDA.length+'</b> encontrados';
    $('#conteo2').textContent = 'de '+j.info.crudo+' crudos';
    $('#cavinfo').innerHTML = 'buscó <b>'+j.info.buscado.length+'</b> variantes · descartó: '+esc(top);
    $('#bvolver').style.display = '';
  }catch(err){ $('#cavinfo').textContent = 'no pude: '+err; }
  finally{ $('#bcavar').textContent = 'buscar'; }
};
$('#qy').addEventListener('keydown', e=>{ if(e.key==='Enter') $('#bcavar').click(); });
$('#bvolver').onclick = () => {
  modoBusqueda = false; BUSQUEDA = [];
  document.body.classList.remove('buscando');
  $('#bvolver').style.display='none'; $('#cavinfo').textContent='';
  pintar();
};


/* =======================================================================
   SOULSEEK de verdad: el boton lanza la busqueda via slskd y muestra quien
   tiene el archivo, en que formato y a que bitrate. Copiar al portapapeles
   no servia para nada.
   ======================================================================= */
let SLSK_TEMA = null;          // id del tema cuya ficha esta abierta
async function buscarEnSoulseek(q, boton, id){
  SLSK_TEMA = id || null;
  if(!servidor){ flash('esto necesita crate_server.py'); return; }
  const caja = $('#slsk');
  $('#slsktit').textContent = q;
  $('#slskn').textContent = '';
  $('#slsklista').innerHTML = '<div class="vacio2">lanzando la búsqueda…</div>';
  caja.classList.add('on');
  if(boton) boton.textContent = '…';

  const fin = (html)=>{ $('#slsklista').innerHTML = html; if(boton) boton.textContent='⇩ slsk'; };
  try{
    const r = await fetch('/api/slsk', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify({q})});
    const j = await r.json();
    if(!j.ok || !j.id){ fin('<div class="vacio2">'+esc(j.error||'no pude lanzarla')+'</div>'); return; }

    // slskd NO entrega los resultados hasta terminar (~40s): hay que consultar.
    const t0 = Date.now();
    const consultar = async () => {
      const rr = await fetch('/api/slsk/' + j.id);
      const d = await rr.json();
      if(!d.ok){ fin('<div class="vacio2">'+esc(d.error||'error')+'</div>'); return; }
      const seg = Math.round((Date.now()-t0)/1000);
      if(!d.listo){
        $('#slsklista').innerHTML =
          '<div class="vacio2">buscando en la red… <b>'+(d.contados||0)+'</b> archivos vistos'
          + '<br><span style="opacity:.6">' + seg + 's — soulseek tarda ~40s</span></div>';
        setTimeout(consultar, 2500);
        return;
      }
      const a = d.archivos || [];
      $('#slskn').textContent = a.length + ' archivos · ' + seg + 's';
      fin(a.length ? a.map((f,i)=>{
          SLSK_ARCH[i] = f;
          return '<div class="fila" title="'+esc(f.ruta||'')+'">'
        + '<span class="fmt'+(f.ext==='mp3'?' mp3':'')+'">'+esc(f.ext.toUpperCase())
        +   (f.bitrate?(' '+f.bitrate):'')+'</span>'
        + '<span class="nom">'+esc(f.nombre)+'</span>'
        + '<span class="usr">'+esc(f.usuario||'')+(f.libre?' ●':'')+'</span>'
        + '<span class="usr">'+f.mb+' MB</span>'
        + '<button class="bajar" data-i="'+i+'" title="bajar de '
        +   esc(f.usuario||'')+'">bajar</button></div>';
        }).join('')
        : '<div class="vacio2">nadie lo tiene compartido ahora</div>');
    };
    setTimeout(consultar, 2500);
  }catch(err){ fin('<div class="vacio2">slskd no responde</div>'); }
}
$('#slskx').onclick = ()=> $('#slsk').classList.remove('on');

/* En Soulseek pedir no es recibir: el par puede estar caido o tener la cola
   llena. Sin esto el boton decia "listo" y el archivo no llegaba nunca.
   (Paso en la primera prueba: "Completed, Errored" a los 6 segundos.) */
async function seguirBajada(nombre, boton){
  for(let i = 0; i < 40; i++){
    await new Promise(r => setTimeout(r, 3000));
    let d;
    try{ d = await (await fetch('/api/slsk/bajadas')).json(); }catch(e){ continue; }
    const x = (d.bajadas || []).find(z => z.nombre === nombre);
    if(!x) continue;
    const e = (x.estado || '').toLowerCase();
    if(e.includes('errored') || e.includes('rejected') || e.includes('cancelled')){
      boton.classList.remove('listo'); boton.classList.add('fallo');
      boton.textContent = 'falló'; boton.disabled = false;
      boton.title = 'el par no la entregó — probá otro de la lista';
      flash('no la entregó ' + (x.usuario || '') + ' · probá otro');
      return;
    }
    if(e.includes('completed')){
      boton.textContent = 'bajado ✓'; boton.classList.add('listo');
      flash('bajado: ' + nombre.slice(0, 40));
      return;
    }
    if(x.pct > 0) boton.textContent = Math.round(x.pct) + '%';
  }
}

/* Bajar de verdad: se lo pedimos a slskd y queda anotado contra el tema, asi
   `por_bajar` deja de reclamarlo. El archivo cae en la carpeta de slskd. */
const SLSK_ARCH = {};
$('#slsklista').addEventListener('click', async e => {
  const b = e.target.closest('.bajar');
  if(!b) return;
  const f = SLSK_ARCH[b.dataset.i];
  if(!f) return;
  b.disabled = true; b.textContent = 'pidiendo…';
  try{
    const r = await fetch('/api/slsk/bajar', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({usuario:f.usuario, ruta:f.ruta, bytes:f.bytes,
                            ext:f.ext, bitrate:f.bitrate, id:SLSK_TEMA})});
    const j = await r.json();
    if(j.ok){
      b.textContent = 'en cola'; b.classList.add('listo');
      flash('pedida a ' + f.usuario);
      seguirBajada(f.nombre, b);
      if(SLSK_TEMA){                        // ya lo tenes: que se vea al toque
        local[SLSK_TEMA] = Object.assign({}, local[SLSK_TEMA], {tiene:1});
        guardarLocal();
        const d = D.find(x=>x.id===SLSK_TEMA);
        if(d){ d.tiene = 1; pintar(); }
      }
    } else {
      b.disabled = false; b.textContent = 'bajar';
      flash(j.error || 'slskd no la acepto');
    }
  }catch(err){ b.disabled=false; b.textContent='bajar'; flash('slskd no responde'); }
});


/* =======================================================================
   HOTLIST: lo mejor del pozo de 50.000 que todavia no escuchaste.
   Se renueva por tandas y se limpia solo: lo que puntuas o abris, sale.
   ======================================================================= */
$('#bhot').onclick = async () => {
  if(!servidor){ flash('esto necesita crate_server.py'); return; }
  $('#bhot').textContent = '…';
  try{
    const r = await fetch('/api/hotlist');
    const j = await r.json();
    const t = (j.temas||[]).map(x=>({
      id:x.id, titulo:x.titulo, artista:x.artista, nombre:x.nombre,
      canal:x.canal, anio:x.anio, dur:x.duracion, views:x.views,
      bpm:x.bpm, tonalidad:x.tonalidad, menor:x.menor,
      razones:x.razones, pts:x.pts
    }));
    if(!t.length){ flash('el hotlist está vacío — generá una tanda'); return; }
    BUSQUEDA = t;
    modoBusqueda = true;
    document.body.classList.add('buscando');
    pintarBusqueda(t);
    const m=$('#modo');
    if(m) m.innerHTML = 'hotlist <span class="det">lo mejor sin escuchar · puntuá y sale</span>';
    $('#conteo').innerHTML = '<b>'+t.length+'</b> elegidos';
    $('#conteo2').textContent = 'del pozo de candidatos';
    $('#cavinfo').innerHTML = 'se renueva por tandas · lo que puntués <b>sale solo</b>';
    $('#bvolver').style.display = '';
  }catch(e){ flash('no pude traer el hotlist'); }
  finally{ $('#bhot').textContent = '★ hotlist'; }
};

pintar();
"""
