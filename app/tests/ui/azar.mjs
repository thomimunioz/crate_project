import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const err = []; p.on('pageerror', e => err.push(e.message));
const fallos = [];
const ok = (q, bien, det='') => { console.log(`  ${bien?'ok   ':'FALLA'} ${q}${det?'  ('+det+')':''}`); if(!bien) fallos.push(q); };

await p.goto('http://127.0.0.1:7777/mi-crate.html', {waitUntil:'networkidle'});
await p.waitForTimeout(2500);

ok('el boton existe en el reproductor', await p.$('#pmez') !== null);
ok('arranca apagado', !(await p.$eval('#pmez', e => e.classList.contains('on'))));

// prender y ver el orden que propone
await p.evaluate(() => { reproducir(document.querySelector('#cuerpo tr[data-id]').dataset.id); });
await p.waitForTimeout(2500);
await p.click('#pmez'); await p.waitForTimeout(400);
ok('se prende', await p.$eval('#pmez', e => e.classList.contains('on')));

const orden = await p.evaluate(() => {
  const vistos = [sonando.id];
  for (let i = 0; i < 12; i++) {           // avanzar sin esperar al audio
    if (mezclando) {
      iBaraja = (iBaraja + 1) % baraja.length;
      vistos.push(baraja[iBaraja]);
    }
  }
  return { vistos, cola: cola.length, baraja: baraja.length };
});
const repes = orden.vistos.length - new Set(orden.vistos).size;
ok('no repite en los primeros 13', repes === 0, repes + ' repetidos');
ok('baraja toda la cola', orden.baraja === orden.cola, `${orden.baraja} de ${orden.cola}`);
const secuencial = orden.vistos.every((v, i, a) => i === 0 || true);
ok('el orden NO es el de la tabla',
   JSON.stringify(orden.vistos.slice(1,5)) !== JSON.stringify(
     await p.evaluate(() => cola.slice(1,5))));

// apagar y ver que vuelve al orden normal
await p.click('#pmez'); await p.waitForTimeout(300);
ok('se apaga', !(await p.$eval('#pmez', e => e.classList.contains('on'))));

// atajo de teclado
await p.keyboard.press('s'); await p.waitForTimeout(300);
ok('la tecla S lo alterna', await p.$eval('#pmez', e => e.classList.contains('on')));

// se acuerda despues de recargar
await p.reload({waitUntil:'networkidle'}); await p.waitForTimeout(2500);
ok('se acuerda del estado al recargar', await p.$eval('#pmez', e => e.classList.contains('on')));

console.log('\n' + (err.length ? 'JS: ' + err.join(' | ') : 'sin errores de JS'));
console.log(fallos.length ? `${fallos.length} FALLAS` : 'TODO OK');
await b.close();
