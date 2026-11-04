# -*- coding: utf-8 -*-
"""Loop y pitch en el reproductor: la app como mini-sampler.

Thomas, 28-oct: "pense en cambiar de tono y loopear secciones".
Y el 4-nov, la advertencia que define el diseño: "ojo con el algoritmo o
libreria o lo q sea que agarres porque tengo 1 extension de chrome q es una
verga, la uso en yt y el audio se warpea todo".

Esa advertencia es la clave. Hay DOS formas de cambiar la velocidad y suenan
completamente distinto:

  PLATO (preservesPitch = false) — resampleo puro. El tono sube con la
  velocidad, igual que acelerar un vinilo o pitchear en un MPC. CERO
  artefactos: no hay nada que inventar, solo se leen las muestras mas rapido.
  Es el modo por defecto.

  ESTIRADO (preservesPitch = true) — mantiene el tono y estira el tiempo.
  Para eso hay que INVENTAR muestras con un phase vocoder, y ahi aparece el
  warpeo metalico que le molesta. Queda disponible pero avisado, porque a
  veces se necesita encajar un loop sin que cambie el tono.

El loop es aparte y no tiene ningun costo de calidad: son dos marcas de
tiempo y volver atras cuando se llega al final.

Solo funciona por el camino del audio propio (/api/audio), no con el iframe
de YouTube, que no deja tocar nada. Si el tema esta sonando por YouTube, el
panel lo pasa a audio solo.
"""

JS = r"""
/* =======================================================================
   SAMPLER: loop de un pasaje + pitch
   ======================================================================= */
let loopA = null, loopB = null, loopOn = false;
let tono = 0;                      // en semitonos
let modoPlato = true;              // true = como un vinilo (sin artefactos)

const semitonoARazon = n => Math.pow(2, n / 12);

function aplicarTono(){
  const r = semitonoARazon(tono);
  try{
    AUD.preservesPitch = !modoPlato;
    AUD.mozPreservesPitch = !modoPlato;
    AUD.webkitPreservesPitch = !modoPlato;
    AUD.playbackRate = Math.min(4, Math.max(0.25, r));
  }catch(e){}
  const t = $('#sTono');
  if(t) t.textContent = (tono > 0 ? '+' : '') + tono;
  const v = $('#sVel');
  if(v) v.textContent = modoPlato ? (r.toFixed(2) + '×') : '1.00×';
}

/* Las marcas A y B en la barra del reproductor: verlas y poder moverlas.
   Thomas, 4-nov: "estaria bueno poder mover marquitas en el timeline (...)
   sino hay que pegarle si o si con los botones A y B y no podes reajustar". */
function pintarMarcas(dur){
  const d = dur || (modo === 'audio' ? AUD.duration : 0) || 0;
  const mA = document.getElementById('marcaA');
  const mB = document.getElementById('marcaB');
  const z  = document.getElementById('zonaloop');
  if(!mA || !mB || !z) return;
  const pon = (el, seg) => {
    if(seg == null || !d){ el.style.display = 'none'; return; }
    el.style.display = 'block';
    el.style.left = Math.max(0, Math.min(100, seg / d * 100)) + '%';
  };
  pon(mA, loopA); pon(mB, loopB);
  if(typeof pintarSpots === 'function') pintarSpots(true);
  if(loopA != null && loopB != null && d){
    z.style.display = 'block';
    z.style.left  = (loopA / d * 100) + '%';
    z.style.width = ((loopB - loopA) / d * 100) + '%';
    z.classList.toggle('activo', loopOn);
  } else { z.style.display = 'none'; }
}

/* Arrastrar una marca. Se mueve con el mouse y se suelta donde quede: asi se
   ajusta el pasaje al oido en vez de tener que acertarle con el boton. */
function arrastrable(el, cual){
  if(!el) return;
  el.addEventListener('mousedown', ev => {
    ev.preventDefault(); ev.stopPropagation();
    const pista = document.getElementById('pista');
    mostrarOnda(true);
    dibujarOnda(cual === 'A' ? (loopA || 0) : (loopB || 0));
    const mover = e2 => {
      const r = pista.getBoundingClientRect();
      const f = Math.max(0, Math.min(1, (e2.clientX - r.left) / r.width));
      const d = (modo === 'audio' ? AUD.duration : 0) || 0;
      if(!d) return;
      const seg = f * d;
      if(cual === 'A'){ loopA = (loopB != null && seg >= loopB) ? loopB - 0.2 : seg; }
      else           { loopB = (loopA != null && seg <= loopA) ? loopA + 0.2 : seg; }
      pintarMarcas(d); pintarSampler();
      dibujarOnda(seg);
    };
    const soltar = () => {
      mostrarOnda(false);
      document.removeEventListener('mousemove', mover);
      document.removeEventListener('mouseup', soltar);
      if(loopA != null && loopB != null && loopOn){
        try{ AUD.currentTime = loopA; }catch(e){}
      }
    };
    document.addEventListener('mousemove', mover);
    document.addEventListener('mouseup', soltar);
  });
}
arrastrable(document.getElementById('marcaA'), 'A');
arrastrable(document.getElementById('marcaB'), 'B');


/* =======================================================================
   FORMA DE ONDA al arrastrar una marca
   Thomas, 4-nov: "cuando mantenes apretado un punto del loop (a-b) te
   muestre como la onda de audio para poder arrastrar y ser mas preciso. Y
   si soltas eso desaparece".

   El costo real es decodificar el tema entero una vez. Por eso NO se hace al
   abrir el panel: se dispara cuando marcas A, que es cuando de verdad vas a
   loopear —idea suya— y asi para cuando agarres la manija ya esta lista. Si
   nunca loopeas, no se gasta nada.

   Se puede porque el audio lo sirve nuestro propio servidor: mismo origen,
   sin CORS. Con el iframe de YouTube seria imposible.
   ======================================================================= */
const ONDAS = new Map();           // id -> Float32Array de picos
let ondaPidiendo = null;

async function pedirOnda(id){
  if(!id || ONDAS.has(id) || ondaPidiendo === id) return ONDAS.get(id);
  ondaPidiendo = id;
  try{
    const resp = await fetch('/api/audio/' + id);
    if(!resp.ok) throw new Error('no llego el audio');
    const buf = await resp.arrayBuffer();
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const audio = await ctx.decodeAudioData(buf);
    const canal = audio.getChannelData(0);
    // Resolucion FIJA por segundo, no un total fijo. Con 2000 picos para
    // todo el tema, una ventana de 8s quedaba con 44 picos estirados en 760
    // pixeles: un bloque escalonado inservible para afinar un loop. Con 120
    // por segundo son ~960 en la ventana, uno por pixel, y pesa nada:
    // seis minutos son 43k floats, 170 KB.
    const POR_SEG = 120;
    const N = Math.max(1, Math.round(audio.duration * POR_SEG));
    const paso = canal.length / N;
    const picos = new Float32Array(N);
    for(let i = 0; i < N; i++){
      let m = 0;
      const a = Math.floor(i * paso), b = Math.min(canal.length, Math.floor((i+1) * paso));
      for(let j = a; j < b; j += 2){ const v = Math.abs(canal[j]); if(v > m) m = v; }
      picos[i] = m;
    }
    ONDAS.set(id, picos);
    try{ await ctx.close(); }catch(e){}
    return picos;
  }catch(e){
    return null;
  }finally{
    ondaPidiendo = null;
  }
}

/* Dibuja un tramo de la onda centrado en `seg`, con la marca en el medio.
   Muestra ~8 segundos: suficiente para ver donde entra y sale un pasaje. */
function dibujarOnda(seg){
  const c = document.getElementById('onda');
  if(!c || !sonando) return;
  const picos = ONDAS.get(sonando.id);
  const dur = (modo === 'audio' ? AUD.duration : 0) || 0;
  const ctx = c.getContext('2d');
  const W = c.width, H = c.height;
  ctx.clearRect(0, 0, W, H);
  if(!picos || !dur){
    ctx.fillStyle = 'rgba(247,246,233,.45)';
    ctx.font = '11px monospace';
    ctx.fillText(ondaPidiendo ? 'leyendo el audio…' : 'sin onda', 12, H/2);
    return;
  }
  const VENTANA = 8;                       // segundos a la vista
  const desde = Math.max(0, seg - VENTANA/2), hasta = Math.min(dur, seg + VENTANA/2);
  const i0 = Math.floor(desde / dur * picos.length);
  const i1 = Math.ceil(hasta / dur * picos.length);
  const n = Math.max(1, i1 - i0);

  // la zona del loop, si cae en la ventana
  if(loopA != null && loopB != null){
    const xa = (loopA - desde) / (hasta - desde) * W;
    const xb = (loopB - desde) / (hasta - desde) * W;
    ctx.fillStyle = 'rgba(79,176,239,.20)';
    ctx.fillRect(Math.max(0, xa), 0, Math.min(W, xb) - Math.max(0, xa), H);
  }
  ctx.fillStyle = 'rgba(238,243,247,.8)';
  for(let x = 0; x < W; x++){
    const p = picos[i0 + Math.floor(x / W * n)] || 0;
    const h = Math.max(1, p * H * 0.92);
    ctx.fillRect(x, (H - h) / 2, 1, h);
  }
  // la marca que estas moviendo, en el centro
  ctx.fillStyle = '#4fb0ef';
  ctx.fillRect(W/2 - 1, 0, 2, H);
  ctx.fillStyle = 'rgba(247,246,233,.55)';
  ctx.font = '10px monospace';
  ctx.fillText(seg.toFixed(2) + 's', W/2 + 6, 12);
}

function mostrarOnda(v){
  const d = document.getElementById('ondabox');
  if(d) d.classList.toggle('on', !!v);
}


/* =======================================================================
   SWEETSPOTS: los pasajes que vale la pena, guardados por tema
   Thomas, 4-nov: "encontras un loop y lo podes marcar como sweetspot y que
   un tema pueda tener varios sweetspots".

   Es el dato mas valioso que puede juntar la app. Su ley de oro es que un
   tema sirve si tiene huecos sin voz, y hasta ahora el sistema no tenia NI
   IDEA de donde estaban: podia decir "este dura 6 minutos, debe haber
   lugar", nada mas. Cada pasaje que marca es un ejemplo real de lo que
   busca.

   El problema visual que el mismo planteo —"que las tarjetas no queden tan
   cargadas"— se resuelve asi: en la tarjeta va SOLO un contador chiquito
   (◉ 2). Los pasajes se ven de verdad en la barra del reproductor cuando
   ese tema suena, que es el unico momento en que sirven.
   ======================================================================= */
let SPOTS = {};                 // id -> [{desde, hasta, nota}]

async function cargarSpots(){
  if(!servidor) return;
  try{
    const d = await (await fetch('/api/sweet')).json();
    if(d && d.ok) SPOTS = d.spots || {};
  }catch(e){}
  pintarSpots();
  if(typeof pintar === 'function') pintar();
}

function spotsDe(id){ return SPOTS[id] || []; }

async function guardarSpot(){
  if(!sonando) return;
  if(loopA == null || loopB == null){ flash('marcá A y B primero'); return; }
  const r = await aServidor('/api/sweet',
    {id: sonando.id, desde: loopA, hasta: loopB});
  if(!r){ flash('no pude guardarlo'); return; }
  try{
    const j = await r.json();
    if(j && j.ok){
      SPOTS[sonando.id] = j.spots;
      flash('sweetspot guardado · ' + (loopB - loopA).toFixed(1) + 's');
      pintarSpots();
      if(typeof pintar === 'function') pintar();
      if(typeof marcarSonando === 'function') marcarSonando();
    }
  }catch(e){}
}

/* Los pasajes guardados, dibujados sobre la barra del reproductor. Click en
   uno = loopear ese pasaje. */
let _spotsFirma = '';
function pintarSpots(forzar){
  const pista = document.getElementById('pista');
  if(!pista) return;
  // El reloj corre 8 veces por segundo. Redibujar los pasajes en cada tick
  // los desprendia del DOM constantemente: parpadeaban y no se podia hacer
  // click en uno. Solo se rehacen si de verdad cambiaron.
  const dur0 = (modo === 'audio' ? AUD.duration : 0) || 0;
  const firma = (sonando ? sonando.id : '') + '|' + Math.round(dur0) + '|'
              + JSON.stringify(spotsDe(sonando ? sonando.id : ''));
  if(!forzar && firma === _spotsFirma) return;
  _spotsFirma = firma;
  [...pista.querySelectorAll('.spot')].forEach(x => x.remove());
  if(!sonando) return;
  const dur = (modo === 'audio' ? AUD.duration : (yt && yt.getDuration ? yt.getDuration() : 0)) || 0;
  if(!dur) return;
  spotsDe(sonando.id).forEach((sp, i) => {
    const el = document.createElement('div');
    el.className = 'spot';
    el.style.left  = (sp.desde / dur * 100) + '%';
    el.style.width = Math.max(0.6, (sp.hasta - sp.desde) / dur * 100) + '%';
    el.title = 'sweetspot ' + (i+1) + ': ' + sp.desde.toFixed(1) + 's → '
             + sp.hasta.toFixed(1) + 's · click para loopearlo';
    el.onclick = ev => {
      ev.stopPropagation();
      loopA = sp.desde; loopB = sp.hasta; loopOn = true;
      try{ AUD.currentTime = loopA; }catch(e){}
      document.getElementById('sampler').classList.add('on');
      pintarSampler(); pintarMarcas();
      flash('loopeando el sweetspot ' + (i+1));
    };
    pista.appendChild(el);
  });
}

function pintarSampler(){
  const d = $('#sMarcas');
  if(!d) return;
  const f = s => s == null ? '—' : (Math.floor(s/60) + ':' + String(Math.floor(s%60)).padStart(2,'0'));
  d.textContent = f(loopA) + '  →  ' + f(loopB);
  $('#sLoop').classList.toggle('on', loopOn);
  $('#sPlato').classList.toggle('on', modoPlato);
  $('#sEstira').classList.toggle('on', !modoPlato);
}

/* El loop se vigila en el mismo reloj del reproductor: cuando pasa de B,
   vuelve a A. Sin nodos raros ni procesamiento: no puede sonar mal. */
function vigilarLoop(){
  if(!loopOn || loopA == null || loopB == null) return;
  if(modo !== 'audio') return;
  if(AUD.currentTime >= loopB || AUD.currentTime < loopA - 0.3){
    try{ AUD.currentTime = loopA; }catch(e){}
  }
}

/* Cambiar de tema con el sampler abierto dejaba las marcas del anterior:
   el loop saltaba a un segundo que en el tema nuevo no significa nada y
   quedaba glitchy. Thomas, 4-nov: "si toco otro tema ya tiene que estar
   listo el sampler para loopear ese tema". Se limpia y queda esperando. */
function resetSampler(){
  loopA = loopB = null;
  loopOn = false;
  tono = 0;
  aplicarTono();
  pintarSampler();
  pintarMarcas();
}

function abrirSampler(){
  if(!sonando){ flash('poné un tema primero'); return; }
  if(!servidor){ flash('esto necesita el servidor'); return; }
  if(modo !== 'audio'){
    // el iframe de YouTube no deja tocar velocidad ni posicion con precision
    flash('pasando a audio propio para poder loopear…');
    noEmb[sonando.id] = Date.now();
    try{ localStorage.setItem(NOEMB, JSON.stringify(noEmb)); }catch(e){}
    porAudio(sonando.id);
  }
  $('#sampler').classList.add('on');
  pintarSampler(); aplicarTono();
}

function cerrarSampler(){
  $('#sampler').classList.remove('on');
  loopOn = false;
  tono = 0; modoPlato = true;
  aplicarTono();
}

$('#sx').onclick = cerrarSampler;
$('#bsampler').onclick = abrirSampler;

$('#sA').onclick = () => {
  loopA = AUD.currentTime;
  if(loopB != null && loopB <= loopA) loopB = null;
  pintarSampler(); pintarMarcas();
  // recien aca se calcula la onda: es cuando de verdad vas a loopear
  if(sonando) pedirOnda(sonando.id);
};
$('#sB').onclick = () => {
  const t = AUD.currentTime;
  if(loopA == null){ flash('marcá primero el principio (A)'); return; }
  if(t <= loopA){ flash('el final tiene que ir después del principio'); return; }
  loopB = t;
  loopOn = true;              // marcar el final YA deja el pasaje girando
  pintarSampler(); pintarMarcas();
  flash('loopeando ' + (loopB - loopA).toFixed(1) + 's');
};
$('#sLoop').onclick = () => {
  if(loopA == null || loopB == null){ flash('marcá A y B primero'); return; }
  loopOn = !loopOn;
  if(loopOn) try{ AUD.currentTime = loopA; }catch(e){}
  pintarSampler(); pintarMarcas();
};
$('#sBorrar').onclick = () => { loopA = loopB = null; loopOn = false;
  pintarSampler(); pintarMarcas(); };
$('#sGuardar').onclick = guardarSpot;
cargarSpots();

$('#sMenos').onclick = () => { tono = Math.max(-12, tono - 1); aplicarTono(); };
$('#sMas').onclick   = () => { tono = Math.min(12,  tono + 1); aplicarTono(); };
$('#sCero').onclick  = () => { tono = 0; aplicarTono(); };
$('#sPlato').onclick = () => {
  modoPlato = true; aplicarTono(); pintarSampler();
  flash('vinyl: el tono sube con la velocidad, sin artefactos');
};
$('#sEstira').onclick = () => {
  modoPlato = false; aplicarTono(); pintarSampler();
  flash('stretch: mantiene el tono pero puede sonar metálico');
};

document.addEventListener('keydown', e => {
  if(!$('#sampler').classList.contains('on')) return;
  if(document.activeElement.tagName === 'INPUT') return;
  if(e.key === 'a' || e.key === 'A'){ e.preventDefault(); $('#sA').click(); }
  if(e.key === 'b' || e.key === 'B'){ e.preventDefault(); $('#sB').click(); }
  if(e.key === 'l' || e.key === 'L'){ e.preventDefault(); $('#sLoop').click(); }
  if(e.key === 'g' || e.key === 'G'){ e.preventDefault(); guardarSpot(); }
  if(e.key === '+' || e.key === '='){ e.preventDefault(); $('#sMas').click(); }
  if(e.key === '-' || e.key === '_'){ e.preventDefault(); $('#sMenos').click(); }
});
"""

CSS = r"""
/* la onda aparece solo mientras arrastras una marca */
#ondabox{position:fixed;left:50%;bottom:112px;transform:translateX(-50%);
  z-index:80;display:none;background:var(--barra);border-radius:4px;
  padding:9px 9px 5px;box-shadow:0 14px 44px rgba(0,0,0,.45)}
#ondabox.on{display:block}
#onda{display:block;border-radius:2px;background:rgba(0,0,0,.22)}
.ondapie{font-family:var(--mono);font-size:.56rem;color:var(--barratxt);
  opacity:.7;text-align:center;margin-top:5px;letter-spacing:.06em}

/* marcas A y B sobre la barra del reproductor */
#pista{position:relative;overflow:visible}
#pista .spot{position:absolute;top:auto;bottom:-15px;height:6px;
  background:var(--acento2);border-radius:2px;cursor:pointer;z-index:2;
  opacity:.85;transition:opacity .12s,height .12s}
#pista .spot:hover{opacity:1;height:9px;bottom:-17px}
#sampler button.b.sweet{border-color:var(--acento2);color:var(--acento2)}
#sampler button.b.sweet:hover{background:var(--acento2);color:var(--stxt)}
#pista .zonaloop{position:absolute;top:0;bottom:0;display:none;
  background:rgba(79,176,239,.22);pointer-events:none;border-radius:2px}
#pista .zonaloop.activo{background:rgba(79,176,239,.38)}
/* Manijas grandes: con 15px eran casi imposibles de agarrar. La pastilla
   visible mide 22x26 y ademas tiene una zona invisible de 44px alrededor
   (::before), que es el minimo comodo para el mouse. */
#pista .marca{position:absolute;top:-20px;display:none;width:22px;height:26px;
  margin-left:-11px;border-radius:3px;background:var(--barranum);
  color:var(--barra);font-family:var(--mono);font-size:.66rem;font-weight:700;
  line-height:26px;text-align:center;cursor:ew-resize;z-index:3;
  box-shadow:0 1px 5px rgba(0,0,0,.4);transition:transform .1s}
/* La zona de agarre se extiende hacia ARRIBA y a los costados, nunca hacia
   abajo: ahi viven los pasajes guardados y la manija les comia el click. */
#pista .marca::before{content:'';position:absolute;left:-11px;right:-11px;
  top:-11px;bottom:0}
#pista .marca:active{transform:scale(1.18)}
#pista .marca:hover{background:var(--stxt)}
#pista .marca.b{background:var(--acento2);color:var(--stxt)}
#pista .marca.b:hover{background:var(--stxt);color:var(--acento2)}

/* =============== SAMPLER: loop y pitch =============== */
#sampler{position:fixed;right:16px;bottom:104px;width:330px;z-index:58;
  display:none;flex-direction:column;background:var(--sobre);border-radius:4px;
  box-shadow:0 14px 40px var(--sombra);overflow:hidden}
#sampler.on{display:flex}
#sampler .cab{display:flex;align-items:center;justify-content:space-between;
  padding:9px 13px;background:var(--barra);color:var(--barratxt)}
#sampler .cab b{font-family:var(--display);font-size:1rem;letter-spacing:.08em}
#sampler .cab button{background:transparent;border:0;color:var(--barratxt);
  cursor:pointer;font-size:.95rem;line-height:1}
#sampler .cuerpo{padding:13px}
.sfila{display:flex;align-items:center;gap:7px;margin-bottom:10px}
.stit{font-family:var(--mono);font-size:.58rem;letter-spacing:.12em;
  text-transform:uppercase;color:var(--suave);margin-bottom:6px}
#sampler button.b{flex:1;font-family:var(--mono);font-size:.68rem;
  padding:7px 0;border:1px solid var(--suave);background:transparent;
  color:var(--fuerte);border-radius:2px;cursor:pointer;letter-spacing:.04em}
#sampler button.b:hover{border-color:var(--acento);color:var(--acento)}
#sampler button.b.on{background:var(--acento);border-color:var(--acento);
  color:var(--stxt)}
#sMarcas{font-family:var(--mono);font-size:.84rem;font-weight:700;
  color:var(--fuerte);text-align:center;padding:6px 0;background:var(--fondo);
  border-radius:2px;margin-bottom:9px;font-variant-numeric:tabular-nums}
.stono{display:flex;align-items:center;justify-content:center;gap:12px;
  padding:4px 0 2px}
.stono b{font-family:var(--display);font-size:1.7rem;color:var(--acento);
  min-width:46px;text-align:center;font-variant-numeric:tabular-nums}
.stono button{width:30px;height:30px;border-radius:50%;border:1px solid var(--suave);
  background:transparent;color:var(--fuerte);cursor:pointer;font-size:1rem;line-height:1}
.stono button:hover{border-color:var(--acento);color:var(--acento)}
#sVel{font-family:var(--mono);font-size:.62rem;color:var(--suave);
  text-align:center;margin-top:-2px}
.snota{font-family:var(--mono);font-size:.56rem;color:var(--suave);
  line-height:1.5;margin-top:9px;padding-top:9px;border-top:1px solid var(--fondo)}
"""

HTML = """
<div id="ondabox"><canvas id="onda" width="760" height="110"></canvas>
  <div class="ondapie">arrastrá para ajustar · soltá para cerrar</div></div>

<div id="sampler">
  <div class="cab"><b>Sampler</b><button id="sx" title="cerrar">&#10005;</button></div>
  <div class="cuerpo">
    <div class="stit">pasaje a loopear</div>
    <div id="sMarcas">—  →  —</div>
    <div class="sfila">
      <button class="b" id="sA" title="marcar el principio (A)">A</button>
      <button class="b" id="sB" title="marcar el final (B)">B</button>
      <button class="b" id="sLoop" title="loop on/off (L)">LOOP</button>
      <button class="b" id="sBorrar" title="borrar las marcas">&#10005;</button>
    </div>
    <div class="sfila">
      <button class="b sweet" id="sGuardar" title="guardar este pasaje en el tema (G)">&#9673; guardar sweetspot</button>
    </div>
    <div class="stit">tono</div>
    <div class="stono">
      <button id="sMenos" title="bajar un semitono (-)">&minus;</button>
      <b id="sTono">0</b>
      <button id="sMas" title="subir un semitono (+)">+</button>
      <button id="sCero" title="volver a cero" style="width:auto;padding:0 9px;border-radius:2px;font-size:.6rem">0</button>
    </div>
    <div id="sVel">1.00&times;</div>
    <div class="sfila" style="margin-top:10px">
      <button class="b on" id="sPlato" title="como un vinilo: tono y velocidad juntos, sin artefactos">vinyl</button>
      <button class="b" id="sEstira" title="estira el tiempo: mantiene el tono, puede sonar metálico">stretch</button>
    </div>
    <div class="snota">
      <b>vinyl</b> es resampleo puro: el tono sube con la velocidad,
      igual que acelerar un vinilo. No tiene artefactos.<br>
      <b>stretch</b> mantiene el tono inventando muestras — es lo que warpea
      el audio en las extensiones de Chrome.
    </div>
  </div>
</div>
"""
