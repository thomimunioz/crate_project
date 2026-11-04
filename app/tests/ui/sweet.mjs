/* Sweetspots: los pasajes que valen la pena, guardados por tema.

   Thomas, 4-nov: "encontras un loop y lo podes marcar como sweetspot y que
   un tema pueda tener varios sweetspots". Y sobre lo visual: "no se a nivel
   visual como mostrar eso para que las tarjetas no queden tan cargadas".

   La respuesta: en la tarjeta va solo un contador; los pasajes se ven en la
   barra del reproductor cuando ese tema suena. Esta prueba verifica las dos
   cosas, y que sobrevivan a recargar. */
import { chromium } from 'playwright';

const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1300, height: 980 } });
const err = [];
p.on('pageerror', e => err.push(e.message));
const fallos = [];
const ok = (q, v, d = '') => {
  console.log(`  ${v ? 'ok   ' : 'FALLA'} ${q}${d ? '  (' + d + ')' : ''}`);
  if (!v) fallos.push(q);
};

await p.goto('http://127.0.0.1:7777/mi-crate.html', { waitUntil: 'networkidle' });
await p.waitForTimeout(2500);
const id = await p.$eval('#cuerpo tr[data-id]', t => t.dataset.id);
await p.click(`#cuerpo tr[data-id="${id}"] .tem`);
await p.waitForTimeout(3500);
await p.click('#bsampler');
await p.waitForTimeout(4500);

const antes = await p.evaluate(i => spotsDe(i).length, id);

// --- marcar y guardar un pasaje ---
await p.evaluate(() => { AUD.currentTime = 30; });
await p.waitForTimeout(400);
await p.click('#sA');
await p.evaluate(() => { AUD.currentTime = 38; });
await p.waitForTimeout(400);
await p.click('#sB');
await p.waitForTimeout(400);
await p.click('#sGuardar');
await p.waitForTimeout(1600);

const uno = await p.evaluate(i => spotsDe(i), id);
ok('guarda el pasaje', uno.length === antes + 1, uno.length + ' pasajes');
ok('guarda el rango correcto',
   uno.length > 0 && Math.abs(uno[uno.length-1].hasta - uno[uno.length-1].desde - 8) < 1,
   uno.length ? (uno[uno.length-1].hasta - uno[uno.length-1].desde).toFixed(1) + 's' : '');

// --- un segundo pasaje en el mismo tema ---
await p.evaluate(() => { AUD.currentTime = 60; });
await p.waitForTimeout(400);
await p.click('#sA');
await p.evaluate(() => { AUD.currentTime = 65; });
await p.waitForTimeout(400);
await p.click('#sB');
await p.click('#sGuardar');
await p.waitForTimeout(1600);
ok('un tema puede tener VARIOS pasajes',
   (await p.evaluate(i => spotsDe(i).length, id)) === antes + 2);

// --- se ven en la barra, no en la tarjeta ---
ok('se dibujan en la barra del reproductor',
   (await p.$$eval('#pista .spot', e => e.length)) >= 2);
const ins = await p.$eval(`#cuerpo tr[data-id="${id}"] .cat`, e => e.textContent);
ok('la tarjeta solo muestra un contador', /◉\d/.test(ins), ins.trim());

// --- click en un pasaje lo loopea ---
await p.click('#pista .spot');
await p.waitForTimeout(900);
const l = await p.evaluate(() => ({A: loopA, B: loopB, on: loopOn}));
ok('click en un pasaje lo loopea', l.on && l.A != null && l.B != null,
   l.A ? l.A.toFixed(1) + '→' + l.B.toFixed(1) : '');

// --- sobreviven a recargar: estan en la base, no en el navegador ---
await p.reload({ waitUntil: 'networkidle' });
await p.waitForTimeout(3000);
ok('sobreviven a recargar (estan en crate.db)',
   (await p.evaluate(i => spotsDe(i).length, id)) === antes + 2);

console.log(err.length ? 'JS: ' + err.join(' | ') : 'sin errores de JS');
console.log(fallos.length ? `${fallos.length} FALLAS` : 'TODO OK');
await b.close();
