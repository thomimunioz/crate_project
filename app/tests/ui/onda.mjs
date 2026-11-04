/* La forma de onda al arrastrar una marca del loop.

   Thomas, 4-nov: "cuando mantenes apretado un punto del loop te muestre como
   la onda de audio para poder arrastrar y ser mas preciso. Y si soltas eso
   desaparece". Y sobre el costo: "capaz para ahorrar podemos hacerlo una vez
   que loopeas" — por eso se calcula al marcar A, no al abrir el panel. */
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
await p.waitForTimeout(2300);
await p.click('#cuerpo tr[data-id] .tem');
await p.waitForTimeout(3500);
await p.click('#bsampler');
await p.waitForTimeout(4500);

ok('al abrir NO calcula la onda (no se gasta de gusto)',
   await p.evaluate(() => ONDAS.size === 0));

await p.evaluate(() => { AUD.currentTime = 40; });
await p.waitForTimeout(400);
await p.click('#sA');
console.log('   marcado A, decodificando…');
await p.waitForFunction(() => ONDAS.size > 0, null, { timeout: 90000 })
       .catch(() => {});
ok('marcar A dispara el calculo', await p.evaluate(() => ONDAS.size > 0));
const picos = await p.evaluate(() => {
  const k = [...ONDAS.keys()][0];
  const a = ONDAS.get(k);
  return a ? { largo: a.length, max: Math.max(...a).toFixed(3) } : null;
});
ok('la onda tiene datos reales', picos && picos.largo > 1000 && +picos.max > 0.01,
   picos ? picos.largo + ' picos, pico max ' + picos.max : 'sin datos');

await p.evaluate(() => { AUD.currentTime = 46; });
await p.waitForTimeout(400);
await p.click('#sB');
await p.waitForTimeout(500);

// --- arrastrar: tiene que aparecer y dibujar ---
ok('la onda esta oculta antes de arrastrar', !(await p.isVisible('#ondabox')));
const r = await p.$eval('#pista', e => {
  const z = e.getBoundingClientRect();
  return { x: z.x, y: z.y, w: z.width, h: z.height };
});
await p.hover('#marcaB');
await p.mouse.down();
await p.waitForTimeout(400);
ok('al mantener apretado APARECE la onda', await p.isVisible('#ondabox'));

const pintado = await p.evaluate(() => {
  const c = document.getElementById('onda');
  const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data;
  let n = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
  return n;
});
ok('el lienzo tiene algo dibujado', pintado > 2000, pintado + ' pixeles');

await p.mouse.move(r.x + r.w * 0.5, r.y + r.h / 2, { steps: 8 });
await p.waitForTimeout(300);
await p.mouse.up();
await p.waitForTimeout(400);
ok('al soltar DESAPARECE', !(await p.isVisible('#ondabox')));

console.log(err.length ? 'JS: ' + err.join(' | ') : 'sin errores de JS');
console.log(fallos.length ? `${fallos.length} FALLAS` : 'TODO OK');
await b.close();
