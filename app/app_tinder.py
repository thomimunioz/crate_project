# -*- coding: utf-8 -*-
"""Modo sesion: un tema por vez, para despachar la cola rapido.

Thomas, 28-oct: "mis amigos me sugirieron un 'tinder' de samples, me parece
algo loco, podemos flashear por ahi?".

Lo que lo hace util para EL y no un chiste: arranca en el MEDIO del tema, no
en el 0:00. Su ley de oro es que necesita huecos sin voz, y eso nunca esta en
la intro — esta en el pasaje. Escuchar los primeros quince segundos de
cincuenta temas no te dice nada sobre ninguno.

Se decide con dos teclas y se sigue solo. Al no decidir se saltea: no hay
forma de "dejarlo para despues" porque eso es lo que llena la cola de temas
que nunca escuchaste.
"""

JS = r"""
/* =======================================================================
   MODO SESION ("tinder"): un tema por vez, decidir rapido
   ======================================================================= */
let tCola = [], tPos = -1, tAbierto = false;

/* El 0:00 de un tema no dice nada: las intros son todas parecidas y el hueco
   sampleable esta en el medio. Si hay duracion, se arranca al 45%. */
function tArrancarEnElMedio(d){
  const dur = d && d.dur;
  if(!dur || dur < 90) return;
  const salto = Math.round(dur * 0.45);
  const ir = () => {
    try{
      if(modo === 'audio'){ if(AUD.readyState >= 1) AUD.currentTime = salto; }
      else if(yt && yt.seekTo) yt.seekTo(salto, true);
    }catch(e){}
  };
  setTimeout(ir, 1200);
  setTimeout(ir, 2600);        // el reproductor puede no estar listo al toque
}

function tPintar(){
  const d = tCola[tPos];
  if(!d){ tCerrar(); return; }
  $('#tpos').textContent = (tPos + 1) + ' / ' + tCola.length;
  const dato = [d.anio, d.bpm ? Math.round(d.bpm) + ' bpm' : '', d.tonalidad,
                d.dur ? Math.floor(d.dur/60)+':'+String(d.dur%60).padStart(2,'0') : '']
               .filter(Boolean).join(' · ');
  const raz = (d.razones || []).slice(0, 3);
  $('#tficha').innerHTML =
      '<img class="ttapa" src="https://i.ytimg.com/vi/'+d.id+'/mqdefault.jpg" alt="">'
    + '<div class="ttem">' + esc(d.nombre || d.titulo) + '</div>'
    + '<div class="tart">' + esc(d.artista || d.canal || '—') + '</div>'
    + (d.genero ? '<div class="tgen"><span class="pl '+clg(d.genero)+'">'
                + esc(d.genero)+'</span></div>' : '')
    + (dato ? '<div class="tdato">' + esc(dato) + '</div>' : '')
    + '<div class="tcanal">' + esc(d.canal || '') + '</div>'
    + (raz.length ? '<ul class="traz">' + raz.map(r=>'<li>'+esc(r)+'</li>').join('') + '</ul>' : '');
  tEstrellas();
  reproducir(d.id);
  tArrancarEnElMedio(d);
}

function tEstrellas(){
  const d = tCola[tPos];
  const e = estrellasDe(d) || 0;
  $('#testrellas').innerHTML = [1,2,3,4,5]
    .map(n => '<span class="s '+(n<=e?'on':'off')+'" data-tn="'+n+'">★</span>').join('');
}

function tSiguiente(){
  if(tPos + 1 >= tCola.length){
    $('#tficha').innerHTML = '<div class="tfin"><b>Listo</b>'
      + '<span>despachaste la cola entera</span></div>';
    $('#tpos').textContent = tCola.length + ' / ' + tCola.length;
    return;
  }
  tPos++;
  tPintar();
}

function tAbrir(){
  if(!servidor){ flash('esto necesita el servidor'); return; }
  const base = (modoBusqueda && BUSQUEDA.length) ? BUSQUEDA : D.filter(pasa);
  tCola = base.filter(d => !(estrellasDe(d) > 0));   // lo ya puntuado no vuelve
  if(!tCola.length){ flash('no hay nada sin puntuar en esta vista'); return; }
  tPos = -1;
  tAbierto = true;
  $('#tinder').classList.add('on');
  document.body.classList.add('ensesion');
  tSiguiente();
}

function tCerrar(){
  tAbierto = false;
  $('#tinder').classList.remove('on');
  document.body.classList.remove('ensesion');
  pintar(); marcarSonando();
}

$('#tx').onclick = tCerrar;
$('#tno').onclick = () => {
  const d = tCola[tPos];
  if(d){ ponerEstrellas(d.id, 0); flash('no va'); }
  tSiguiente();
};
$('#tsi').onclick = () => {
  const d = tCola[tPos];
  if(d && !(estrellasDe(d) > 0)) ponerEstrellas(d.id, 4);
  flash('guardado');
  tSiguiente();
};
$('#tplay').onclick = () => $('#pplay').click();
$('#testrellas').addEventListener('click', e => {
  const s = e.target.closest('[data-tn]');
  const d = tCola[tPos];
  if(!s || !d) return;
  ponerEstrellas(d.id, +s.dataset.tn);
  tEstrellas(); pintarEstrellasPlayer();
  setTimeout(tSiguiente, 320);          // se ve lo que elegiste y sigue
});

document.addEventListener('keydown', e => {
  if(!tAbierto) return;
  if(document.activeElement.tagName === 'INPUT') return;
  if(e.key === 'Escape'){ e.preventDefault(); tCerrar(); return; }
  if(e.key === 'ArrowLeft'){ e.preventDefault(); $('#tno').click(); }
  if(e.key === 'ArrowRight'){ e.preventDefault(); $('#tsi').click(); }
  if(/^[1-5]$/.test(e.key)){
    e.preventDefault();
    const d = tCola[tPos];
    if(d){ ponerEstrellas(d.id, +e.key); tEstrellas(); pintarEstrellasPlayer();
           setTimeout(tSiguiente, 320); }
  }
});
$('#bses').onclick = tAbrir;
"""

CSS = r"""
/* =============== MODO SESION =============== */
#tinder{position:fixed;inset:0;z-index:75;display:none;align-items:center;
  justify-content:center;padding:22px 16px 118px;background:var(--fondo)}
#tinder.on{display:flex}
.tcaja{width:100%;max-width:440px;text-align:center}
.tcab{display:flex;align-items:center;justify-content:space-between;
  font-family:var(--mono);font-size:.7rem;color:var(--suave);margin-bottom:14px}
.tcab button{background:transparent;border:0;color:var(--suave);cursor:pointer;
  font-size:1rem;line-height:1}
.tcab button:hover{color:var(--estrella)}
.tficha{background:var(--sobre);border-radius:4px;padding:20px;
  box-shadow:0 14px 38px var(--sombra)}
.ttapa{width:148px;height:111px;object-fit:cover;border-radius:3px;
  margin-bottom:14px;background:var(--fondo)}
.ttem{font-family:var(--display);font-size:1.5rem;line-height:1.2;
  color:var(--fuerte);margin-bottom:4px}
.tart{font-family:var(--mono);font-size:.84rem;color:var(--medio)}
.tgen{margin-top:9px}
.tdato{font-family:var(--mono);font-size:.72rem;color:var(--acento);margin-top:9px}
.tcanal{font-family:var(--mono);font-size:.62rem;color:var(--suave);margin-top:5px}
.traz{list-style:none;margin:13px 0 0;padding:0;text-align:left}
.traz li{font-family:var(--mono);font-size:.64rem;color:var(--medio);
  padding-left:11px;position:relative;margin-bottom:3px}
.traz li::before{content:'·';position:absolute;left:2px;color:var(--acento)}
.tfin{padding:34px 0}
.tfin b{display:block;font-family:var(--display);font-size:2rem;color:var(--acento2)}
.tfin span{font-family:var(--mono);font-size:.74rem;color:var(--medio)}
.tacciones{display:flex;align-items:center;justify-content:center;gap:16px;
  margin-top:20px}
.tbtn{width:58px;height:58px;border-radius:50%;border:2px solid var(--suave);
  background:var(--sobre);color:var(--suave);font-size:1.3rem;cursor:pointer;
  transition:transform .1s,border-color .12s,color .12s}
.tbtn:hover{transform:scale(1.07)}
.tbtn.no:hover{border-color:var(--estrella);color:var(--estrella)}
.tbtn.si:hover{border-color:var(--acento2);color:var(--acento2)}
.tbtn.pl{width:46px;height:46px;font-size:.9rem}
.testrellas{margin-top:16px;font-size:1.5rem;letter-spacing:.14em;cursor:pointer}
.testrellas .s{color:var(--estrella)}
.testrellas .s.off{color:transparent;-webkit-text-stroke:1.5px var(--suave)}
.testrellas .s:hover{transform:scale(1.1)}
.tpie{font-family:var(--mono);font-size:.6rem;color:var(--suave);margin-top:16px}
/* OJO: #tinder vive DENTRO de .wrap, asi que ocultar .wrap entero lo
   ocultaba tambien a el. El modo "funcionaba" —el DOM tenia todo— pero no se
   veia nada. Se esconden los hermanos, no el contenedor. */
body.ensesion .wrap > *:not(#tinder){display:none}
"""
