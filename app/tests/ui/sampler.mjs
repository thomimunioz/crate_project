import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({viewport:{width:1300,height:950}});
const err = []; p.on('pageerror', e => err.push(e.message));
const fallos = [];
const ok = (q,v,d='') => { console.log(`  ${v?'ok   ':'FALLA'} ${q}${d?'  ('+d+')':''}`); if(!v) fallos.push(q); };
await p.goto('http://127.0.0.1:7777/mi-crate.html', {waitUntil:'networkidle'});
await p.waitForTimeout(2300);

// --- archivado automatico al puntuar desde el hotlist ---
await (await p.$('#bhot')).click(); await p.waitForTimeout(4200);
const id = await p.$eval('#cuerpo tr[data-id]', t=>t.dataset.id);
const gen = await p.$eval(`#cuerpo tr[data-id="${id}"] .meta2 .pl:last-child`, e=>e.textContent).catch(()=>null);
await p.click(`#cuerpo tr[data-id="${id}"] .estrellas .s[data-n="4"]`);
await p.waitForTimeout(2000);
const listas = await p.evaluate(i => (local[i]&&local[i].listas)||[], id);
ok('puntuar archiva en una lista sola', listas.length > 0, listas.join(',') || 'ninguna');
console.log('   genero sugerido:', gen, '-> archivado en:', listas.join(',') || '—');

// --- sampler ---
await p.click('#cuerpo tr[data-id] .tem'); await p.waitForTimeout(3500);
await p.click('#bsampler'); await p.waitForTimeout(4000);
ok('el panel se abre y SE VE', await p.isVisible('#sampler'));
const est = await p.evaluate(() => ({modo: typeof modo!=='undefined'?modo:'?',
  pres: AUD.preservesPitch, rate: AUD.playbackRate}));
ok('pasa a audio propio para poder tocar', est.modo === 'audio', est.modo);
ok('arranca en modo PLATO (sin artefactos)', est.pres === false, 'preservesPitch=' + est.pres);

// subir 2 semitonos
await p.click('#sMas'); await p.click('#sMas'); await p.waitForTimeout(700);
const t2 = await p.evaluate(() => ({tono: $('#sTono').textContent,
  rate: +AUD.playbackRate.toFixed(3), pres: AUD.preservesPitch}));
ok('+2 semitonos = 1.122x (resampleo puro)', Math.abs(t2.rate - 1.1225) < 0.01, t2.rate + '×');
ok('sigue sin estirar', t2.pres === false);

// modo estirado
await p.click('#sEstira'); await p.waitForTimeout(600);
const t3 = await p.evaluate(() => ({pres: AUD.preservesPitch, rate:+AUD.playbackRate.toFixed(3)}));
ok('"estirado" activa el time-stretch', t3.pres === true);

// loop
await p.click('#sPlato'); await p.waitForTimeout(300);
await p.evaluate(() => { AUD.currentTime = 30; });
await p.waitForTimeout(600); await p.click('#sA');
await p.evaluate(() => { AUD.currentTime = 34; });
await p.waitForTimeout(600); await p.click('#sB');
const m = await p.$eval('#sMarcas', e=>e.textContent.trim());
ok('marca A y B', /0:3\d\s+→\s+0:3\d/.test(m), m);
await p.evaluate(() => { AUD.currentTime = 35; vigilarLoop(); });
await p.waitForTimeout(500);
const vuelto = await p.evaluate(() => AUD.currentTime);
ok('al pasar B vuelve a A', vuelto < 32, vuelto.toFixed(1) + 's');
console.log(err.length?'JS: '+err.join(' | '):'sin errores de JS');
console.log(fallos.length?`${fallos.length} FALLAS`:'TODO OK');
await b.close();
