import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({viewport:{width:1300,height:900}});
const err = []; p.on('pageerror', e => err.push(e.message));
const fallos = [];
const ok = (q, bien, det='') => { console.log(`  ${bien?'ok   ':'FALLA'} ${q}${det?'  ('+det+')':''}`); if(!bien) fallos.push(q); };
await p.goto('http://127.0.0.1:7777/mi-crate.html', {waitUntil:'networkidle'});
await p.waitForTimeout(2200);
await (await p.$('#bhot')).click(); await p.waitForTimeout(4200);

const antes = await p.$$eval('#cuerpo tr[data-id]', r=>r.length);
const id = await p.$eval('#cuerpo tr[data-id]', t=>t.dataset.id);
const F = `#cuerpo tr[data-id="${id}"]`;
await p.hover(F); await p.waitForTimeout(250);

// primer click: pregunta, y NO tiene que reproducir
await p.click(`${F} [data-desc]`); await p.waitForTimeout(700);
const son1 = await p.evaluate(() => typeof sonando !== 'undefined' && sonando ? sonando.id : null);
ok('el 1er click NO reproduce', son1 === null, son1 ? 'sono ' + son1 : '');
ok('el 1er click pregunta',
   (await p.$eval(`${F} [data-desc]`, e=>e.textContent)).includes('descartar'));

// segundo click: descarta
await p.click(`${F} [data-desc]`); await p.waitForTimeout(1200);
ok('el 2do click saca la fila', await p.$(F) === null);
ok('la cola bajo en 1', await p.$$eval('#cuerpo tr[data-id]', r=>r.length) === antes - 1);
const son2 = await p.evaluate(() => typeof sonando !== 'undefined' && sonando ? sonando.id : null);
ok('nunca reprodujo el descartado', son2 !== id);

// y que el click en la fila SIGA reproduciendo
await p.click('#cuerpo tr[data-id] .tem'); await p.waitForTimeout(2500);
ok('clickear la fila sigue reproduciendo',
   await p.evaluate(() => typeof sonando !== 'undefined' && !!sonando));
console.log(err.length ? 'JS: '+err.join(' | ') : 'sin errores de JS');
console.log(fallos.length ? `${fallos.length} FALLAS` : 'TODO OK');
await b.close();
