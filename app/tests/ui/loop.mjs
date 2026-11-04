import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({viewport:{width:1300,height:950}});
const err = []; p.on('pageerror', e => err.push(e.message));
const fallos = [];
const ok = (q,v,d='') => { console.log(`  ${v?'ok   ':'FALLA'} ${q}${d?'  ('+d+')':''}`); if(!v) fallos.push(q); };
await p.goto('http://127.0.0.1:7777/mi-crate.html', {waitUntil:'networkidle'});
await p.waitForTimeout(2300);
await p.click('#cuerpo tr[data-id] .tem'); await p.waitForTimeout(3500);
await p.click('#bsampler'); await p.waitForTimeout(4500);

// marcar un pasaje corto y DEJARLO SOLO — nada de llamar funciones a mano
await p.evaluate(() => { AUD.currentTime = 40; });
await p.waitForTimeout(500); await p.click('#sA');
await p.evaluate(() => { AUD.currentTime = 43; });
await p.waitForTimeout(500); await p.click('#sB');
ok('marcar B deja el loop activo', await p.$eval('#sLoop', e=>e.classList.contains('on')));
ok('las marcas se VEN en la barra',
   await p.isVisible('#marcaA') && await p.isVisible('#marcaB'));
ok('la zona del loop se ve', await p.isVisible('#zonaloop'));

// esperar de verdad a que pase el final y ver si volvio solo
console.log('   dejandolo sonar 7 s sin tocar nada...');
const muestras = [];
for (let i = 0; i < 14; i++) {
  await p.waitForTimeout(500);
  muestras.push(await p.evaluate(() => +AUD.currentTime.toFixed(1)));
}
const max = Math.max(...muestras), volvio = muestras.some((v,i)=> i>0 && v < muestras[i-1] - 1);
ok('NUNCA se pasa del final (B=43s)', max <= 43.6, 'llego a ' + max + 's');
ok('vuelve solo al principio', volvio, muestras.slice(0,10).join(' '));

// arrastrar la marca B mas lejos
const r = await p.$eval('#pista', e => { const b=e.getBoundingClientRect(); return {x:b.x,y:b.y,w:b.width}; });
const d = await p.evaluate(() => AUD.duration);
const bAntes = await p.evaluate(() => loopB);
await p.hover('#marcaB');
await p.mouse.down();
await p.mouse.move(r.x + r.w * (55 / d), r.y + 5, {steps: 10});
await p.mouse.up(); await p.waitForTimeout(600);
const bDespues = await p.evaluate(() => loopB);
ok('arrastrar la marca B la mueve', Math.abs(bDespues - bAntes) > 5,
   bAntes.toFixed(1) + 's -> ' + bDespues.toFixed(1) + 's');
console.log(err.length?'JS: '+err.join(' | '):'sin errores de JS');
console.log(fallos.length?`${fallos.length} FALLAS`:'TODO OK');
await b.close();
