/* El sampler tiene que quedar LISTO al cambiar de tema.

   Thomas, 4-nov: "la ventanita esa emergente se tiene que cerrar si toco
   otro tema. O en todo caso, si toco otro tema ya tiene que estar listo el
   sampler para loopear ese tema. Porque sino queda medio glitchy."

   Antes quedaban las marcas del tema anterior y el loop saltaba a un
   segundo que en el tema nuevo no significa nada. */
import { chromium } from 'playwright';

const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1300, height: 950 } });
const err = [];
p.on('pageerror', e => err.push(e.message));
const fallos = [];
const ok = (q, v, d = '') => {
  console.log(`  ${v ? 'ok   ' : 'FALLA'} ${q}${d ? '  (' + d + ')' : ''}`);
  if (!v) fallos.push(q);
};

await p.goto('http://127.0.0.1:7777/mi-crate.html', { waitUntil: 'networkidle' });
await p.waitForTimeout(2300);

const filas = await p.$$('#cuerpo tr[data-id]');
await filas[0].$eval('.tem', e => e.click());
await p.waitForTimeout(3500);
await p.click('#bsampler');
await p.waitForTimeout(4500);

await p.evaluate(() => { AUD.currentTime = 30; });
await p.waitForTimeout(400);
await p.click('#sA');
await p.evaluate(() => { AUD.currentTime = 36; });
await p.waitForTimeout(400);
await p.click('#sB');
await p.click('#sMas');
await p.click('#sMas');
await p.waitForTimeout(600);

const antes = await p.evaluate(() => ({ A: loopA, B: loopB, on: loopOn, tono }));
ok('queda un loop y un pitch puestos',
   antes.A != null && antes.B != null && antes.on && antes.tono === 2,
   JSON.stringify(antes));

// --- cambiar de tema ---
await filas[2].$eval('.tem', e => e.click());
await p.waitForTimeout(4000);
const desp = await p.evaluate(() => ({
  A: loopA, B: loopB, on: loopOn, tono,
  rate: +AUD.playbackRate.toFixed(2),
  abierto: document.querySelector('#sampler').classList.contains('on'),
}));
ok('al cambiar de tema se limpian las marcas', desp.A === null && desp.B === null);
ok('el loop queda apagado', desp.on === false);
ok('el pitch vuelve a cero', desp.tono === 0 && desp.rate === 1,
   'tono ' + desp.tono + ' rate ' + desp.rate);
ok('el panel sigue abierto y listo', desp.abierto === true);

// --- y se puede loopear el tema nuevo enseguida ---
await p.evaluate(() => { AUD.currentTime = 20; });
await p.waitForTimeout(400);
await p.click('#sA');
await p.evaluate(() => { AUD.currentTime = 23; });
await p.waitForTimeout(400);
await p.click('#sB');
await p.waitForTimeout(3000);
const t = await p.evaluate(() => AUD.currentTime);
ok('loopea el tema nuevo enseguida', t >= 19 && t <= 24, t.toFixed(1) + 's');

// --- las manijas tienen que poder agarrarse ---
const m = await p.$eval('#marcaA', e => {
  const r = e.getBoundingClientRect();
  return { w: r.width, h: r.height };
});
ok('las manijas son agarrables', m.w >= 20 && m.h >= 24,
   Math.round(m.w) + 'x' + Math.round(m.h) + 'px');

const a = await p.$eval('#sPlato', e => e.textContent);
const c = await p.$eval('#sEstira', e => e.textContent);
ok('se llaman vinyl y stretch', a === 'vinyl' && c === 'stretch', a + ' / ' + c);

console.log(err.length ? 'JS: ' + err.join(' | ') : 'sin errores de JS');
console.log(fallos.length ? `${fallos.length} FALLAS` : 'TODO OK');
await b.close();
