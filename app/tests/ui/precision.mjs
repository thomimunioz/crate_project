/* Los cuatro retoques del sampler que reporto Thomas el 4-nov:
   contador legible, el pasaje que no tiembla, la onda disponible aunque
   entres por un sweetspot, y el arrastre fino.

   La prueba BORRA los pasajes del tema que usa antes de empezar. Sin eso
   cada corrida deja uno mas, se superponen, y el que queda arriba no es el
   que la prueba cree estar tocando — me costo media hora perseguir eso. */
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

const limpiar = () => p.evaluate(async i => {
  const d = await (await fetch('/api/sweet')).json();
  for (const sp of ((d.spots || {})[i] || [])) {
    await fetch('/api/sweet', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: i, desde: sp.desde, borrar: true }),
    });
  }
  if (typeof SPOTS !== 'undefined') SPOTS[i] = [];
}, id);

await limpiar();
await p.waitForTimeout(600);

await p.click(`#cuerpo tr[data-id="${id}"] .tem`);
await p.waitForTimeout(3500);
await p.click('#bsampler');
await p.waitForTimeout(4500);

// un unico pasaje, para que no haya superposiciones
await p.evaluate(() => { AUD.currentTime = 50; });
await p.waitForTimeout(400);
await p.click('#sA');
await p.waitForFunction(() => ONDAS.size > 0, null, { timeout: 90000 }).catch(() => {});
await p.evaluate(() => { AUD.currentTime = 58; });
await p.waitForTimeout(400);
await p.click('#sB');
await p.click('#sGuardar');
await p.waitForTimeout(1500);
ok('queda un solo pasaje', await p.$$eval('#pista .spot', e => e.length) === 1,
   (await p.$$eval('#pista .spot', e => e.length)) + ' en la barra');

// --- 1. el contador se tiene que ver ---
const ins = await p.$eval(`#cuerpo tr[data-id="${id}"] .spots`, e => {
  const r = e.getBoundingClientRect();
  return { h: r.height, fs: parseFloat(getComputedStyle(e).fontSize) };
});
ok('el contador es legible', ins.fs >= 10 && ins.h >= 14,
   Math.round(ins.h) + 'px de alto, ' + ins.fs + 'px de letra');

// --- 2. el pasaje no cambia de tamaño al pasarle el mouse ---
const caja = () => p.$eval('#pista .spot', e => {
  const r = e.getBoundingClientRect();
  return { h: Math.round(r.height), y: Math.round(r.y) };
});
const sin = await caja();
await p.hover('#pista .spot');
await p.waitForTimeout(400);
const con = await caja();
ok('el pasaje NO tiembla al pasar el mouse', sin.h === con.h && sin.y === con.y,
   `antes ${sin.h}px@${sin.y} · hover ${con.h}px@${con.y}`);

// --- 3. la onda tiene que estar aunque entres por el sweetspot ---
// (que sobreviva a recargar lo cubre sweet.mjs; aca se prueba el camino
//  corto: tocar el pasaje guardado y poder afinarlo enseguida)
await p.evaluate(() => { ONDAS.clear(); });
await p.click('#pista .spot');
await p.waitForTimeout(1200);
await p.waitForFunction(() => ONDAS.size > 0, null, { timeout: 90000 }).catch(() => {});
ok('tocar un sweetspot pide la onda', await p.evaluate(() => ONDAS.size > 0));

await p.hover('#marcaB');
await p.mouse.down();
await p.waitForTimeout(700);
const pintado = await p.evaluate(() => {
  const c = document.getElementById('onda');
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let n = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
  return n;
});
ok('dibuja la onda, no dice "sin onda"', pintado > 20000, pintado + ' pixeles');

// --- 4. el arrastre tiene que ser FINO con la onda a la vista ---
const antes = await p.evaluate(() => loopB);
const bx = await p.$eval('#marcaB', e => e.getBoundingClientRect().x);
const by = await p.$eval('#pista', e => e.getBoundingClientRect().y);
await p.mouse.move(bx + 20, by + 3, { steps: 6 });
await p.waitForTimeout(400);
const desp = await p.evaluate(() => loopB);
await p.mouse.up();
const porPixel = Math.abs(desp - antes) / 20;
ok('20px mueven decimas, no segundos', porPixel > 0 && porPixel < 0.08,
   porPixel.toFixed(3) + ' s por pixel');

await limpiar();
console.log(err.length ? 'JS: ' + err.join(' | ') : 'sin errores de JS');
console.log(fallos.length ? `${fallos.length} FALLAS` : 'TODO OK');
await b.close();
