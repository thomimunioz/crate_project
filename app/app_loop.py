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
    const mover = e2 => {
      const r = pista.getBoundingClientRect();
      const f = Math.max(0, Math.min(1, (e2.clientX - r.left) / r.width));
      const d = (modo === 'audio' ? AUD.duration : 0) || 0;
      if(!d) return;
      const seg = f * d;
      if(cual === 'A'){ loopA = (loopB != null && seg >= loopB) ? loopB - 0.2 : seg; }
      else           { loopB = (loopA != null && seg <= loopA) ? loopA + 0.2 : seg; }
      pintarMarcas(d); pintarSampler();
    };
    const soltar = () => {
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

$('#sMenos').onclick = () => { tono = Math.max(-12, tono - 1); aplicarTono(); };
$('#sMas').onclick   = () => { tono = Math.min(12,  tono + 1); aplicarTono(); };
$('#sCero').onclick  = () => { tono = 0; aplicarTono(); };
$('#sPlato').onclick = () => {
  modoPlato = true; aplicarTono(); pintarSampler();
  flash('como un plato: sin artefactos');
};
$('#sEstira').onclick = () => {
  modoPlato = false; aplicarTono(); pintarSampler();
  flash('estirado: mantiene el tono pero puede sonar metálico');
};

document.addEventListener('keydown', e => {
  if(!$('#sampler').classList.contains('on')) return;
  if(document.activeElement.tagName === 'INPUT') return;
  if(e.key === 'a' || e.key === 'A'){ e.preventDefault(); $('#sA').click(); }
  if(e.key === 'b' || e.key === 'B'){ e.preventDefault(); $('#sB').click(); }
  if(e.key === 'l' || e.key === 'L'){ e.preventDefault(); $('#sLoop').click(); }
  if(e.key === '+' || e.key === '='){ e.preventDefault(); $('#sMas').click(); }
  if(e.key === '-' || e.key === '_'){ e.preventDefault(); $('#sMenos').click(); }
});
"""

CSS = r"""
/* marcas A y B sobre la barra del reproductor */
#pista{position:relative;overflow:visible}
#pista .zonaloop{position:absolute;top:0;bottom:0;display:none;
  background:rgba(79,176,239,.22);pointer-events:none;border-radius:2px}
#pista .zonaloop.activo{background:rgba(79,176,239,.38)}
#pista .marca{position:absolute;top:-7px;display:none;width:15px;height:20px;
  margin-left:-7px;border-radius:2px;background:var(--barranum);
  color:var(--barra);font-family:var(--mono);font-size:.56rem;font-weight:700;
  line-height:20px;text-align:center;cursor:ew-resize;z-index:3;
  box-shadow:0 1px 4px rgba(0,0,0,.35)}
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
    <div class="stit">tono</div>
    <div class="stono">
      <button id="sMenos" title="bajar un semitono (-)">&minus;</button>
      <b id="sTono">0</b>
      <button id="sMas" title="subir un semitono (+)">+</button>
      <button id="sCero" title="volver a cero" style="width:auto;padding:0 9px;border-radius:2px;font-size:.6rem">0</button>
    </div>
    <div id="sVel">1.00&times;</div>
    <div class="sfila" style="margin-top:10px">
      <button class="b on" id="sPlato" title="tono y velocidad juntos, sin artefactos">como un plato</button>
      <button class="b" id="sEstira" title="mantiene el tono, puede sonar metálico">estirado</button>
    </div>
    <div class="snota">
      <b>como un plato</b> es resampleo puro: el tono sube con la velocidad,
      igual que acelerar un vinilo. No tiene artefactos.<br>
      <b>estirado</b> mantiene el tono inventando muestras — es lo que warpea
      el audio en las extensiones de Chrome.
    </div>
  </div>
</div>
"""
