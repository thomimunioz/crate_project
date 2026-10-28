import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({viewport:{width:1100,height:1000}});
const err = []; p.on('pageerror', e => err.push(e.message));
const fallos = [];
const ok = (q, bien, det='') => { console.log(`  ${bien?'ok   ':'FALLA'} ${q}${det?'  ('+det+')':''}`); if(!bien) fallos.push(q); };

await p.goto('http://127.0.0.1:7777/mi-crate.html', {waitUntil:'networkidle'});
await p.waitForTimeout(2200);
await (await p.$('#bhot')).click(); await p.waitForTimeout(4000);

await p.click('#bses'); await p.waitForTimeout(5000);
ok('el modo se abre', await p.$eval('#tinder', e=>e.classList.contains('on')));
// mirar la clase no alcanza: el panel estaba dentro del contenedor que el
// propio modo oculta, asi que "funcionaba" sin verse. Hay que exigir pixeles.
ok('la tarjeta SE VE de verdad', await p.isVisible('.tcaja'));
const caja = await (await p.$('.tcaja')).boundingBox();
ok('la tarjeta ocupa lugar en pantalla', !!caja && caja.width > 200 && caja.height > 200,
   caja ? Math.round(caja.width)+'x'+Math.round(caja.height) : 'sin caja');
ok('oculta la tabla', await p.$eval('body', e=>e.classList.contains('ensesion')));

const f1 = await p.evaluate(() => ({
  pos: document.querySelector('#tpos')?.textContent,
  tema: document.querySelector('.ttem')?.textContent,
  genero: document.querySelector('.tgen .pl')?.textContent,
  razones: document.querySelectorAll('.traz li').length,
  tapa: !!document.querySelector('.ttapa'),
}));
console.log('   ficha:', JSON.stringify(f1));
ok('muestra tema, genero y razones', !!f1.tema && !!f1.genero && f1.razones > 0);

// LO IMPORTANTE: tiene que haber saltado al medio, no estar en 0:00
await p.waitForTimeout(4500);
const t = await p.evaluate(() => ({
  modo: typeof modo !== 'undefined' ? modo : '?',
  seg: modo === 'audio' ? AUD.currentTime : (yt && yt.getCurrentTime ? yt.getCurrentTime() : 0),
  dur: sonando ? sonando.dur : 0,
}));
console.log('   reproduciendo en', Math.round(t.seg), 's de', t.dur, 's');
ok('arranca en el PASAJE, no en la intro', t.seg > Math.min(40, t.dur*0.3),
   Math.round(100*t.seg/Math.max(1,t.dur)) + '% del tema');

// flecha derecha = guardar y seguir
await p.keyboard.press('ArrowRight'); await p.waitForTimeout(2500);
const f2 = await p.evaluate(() => document.querySelector('.ttem')?.textContent);
ok('→ guarda y pasa al siguiente', f2 !== f1.tema, f2?.slice(0,30));
ok('el contador avanza', await p.$eval('#tpos', e=>e.textContent) !== f1.pos);

// puntuar con teclado pasa solo
await p.keyboard.press('4'); await p.waitForTimeout(1800);
ok('puntuar con teclado avanza', await p.$eval('.ttem', e=>e.textContent) !== f2);

// flecha izquierda = descartar
const f3 = await p.$eval('.ttem', e=>e.textContent);
await p.keyboard.press('ArrowLeft'); await p.waitForTimeout(2200);
ok('← descarta y pasa', await p.$eval('.ttem', e=>e.textContent) !== f3);

await p.screenshot({path:'sesion.png', clip:{x:300,y:60,width:500,height:800}});
await p.keyboard.press('Escape'); await p.waitForTimeout(800);
ok('Esc vuelve a la tabla', !(await p.$eval('#tinder', e=>e.classList.contains('on'))));
console.log('\n' + (err.length ? 'JS: ' + err.join(' | ') : 'sin errores de JS'));
console.log(fallos.length ? `${fallos.length} FALLAS` : 'TODO OK');
await b.close();
