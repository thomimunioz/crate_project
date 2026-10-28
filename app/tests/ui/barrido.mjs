/* Barrido de la interfaz: ejercita TODA la superficie de interaccion en las
   dos vistas (MI CRATE y HOTLIST) y verifica que el estado quede consistente.

   Existe porque los bugs venian de a uno y los encontraba Thomas: el hover de
   las estrellas, el doble click, EN DISCO, el orden del reproductor, las
   estrellas que se borraban al clasificar. Todos eran la misma familia —la
   vista del hotlist se construyo aparte de la del crate y quedo con otro
   estado— pero aparecian salteados, y reportarlos de a uno es un dolor.

   Corre con:   crate ui        (necesita la app levantada)
   Requiere:    npm i playwright  en app/tests/ui
*/
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
const err = []; p.on('pageerror', e => err.push(e.message));
const fallos = [];
const ok = (q, bien, det='') => { console.log(`  ${bien?'ok   ':'FALLA'} ${q}${det?'  ('+det+')':''}`); if(!bien) fallos.push(q); };
await p.goto('http://127.0.0.1:7777/mi-crate.html', {waitUntil:'networkidle'});
await p.waitForTimeout(2500);

async function vista(nombre) {
  console.log('\n=== ' + nombre + ' ===');
  const id = await p.$eval('#cuerpo tr[data-id]', t => t.dataset.id);
  const F = `#cuerpo tr[data-id="${id}"]`;
  const est = () => p.$$eval(`${F} .estrellas .s:not(.off)`, s=>s.length);

  await p.click(`${F} .estrellas .s[data-n="3"]`); await p.waitForTimeout(700);
  ok('puntuar se ve en la tarjeta', await est() === 3);

  await p.hover(`${F} .estrellas .s[data-n="5"]`); await p.waitForTimeout(350);
  ok('hover muestra preview', await p.$$eval(`${F} .estrellas .s.pre`, s=>s.length) > 0);
  await p.mouse.move(5,5); await p.waitForTimeout(250);

  await p.click(`${F} .tem`); await p.waitForTimeout(2800);
  ok('player: arriba el TEMA',
     (await p.$eval('#player .pa', e=>e.textContent.trim())) === await p.$eval(`${F} .tem`, e=>e.textContent.trim()));
  ok('player: estrellas coinciden',
     await p.$$eval('#player .pest .s.on', s=>s.length) === 3);

  await p.click('#player .pest [data-pn="5"]'); await p.waitForTimeout(700);
  ok('puntuar desde el player actualiza la tarjeta', await est() === 5);

  // CLASIFICAR: lo que reporto Thomas
  await p.hover(F); await p.waitForTimeout(250);
  await p.click(`${F} .btn-cl`); await p.waitForTimeout(400);
  await p.click(`${F} .menu-cl button[data-l="SOUL"]`); await p.waitForTimeout(1500);
  const sigue = await p.$(F) !== null;
  if (sigue) {
    ok('clasificar NO borra las estrellas', await est() === 5, (await est()) + ' estrellas');
    ok('clasificar muestra la lista en la tarjeta',
       (await p.$eval(F, e=>e.textContent)).includes('SOUL'));
  } else { ok('clasificar: la fila salio de la vista', true); }

  // deshacer
  if (sigue) { await p.hover(F); await p.waitForTimeout(250);
               await p.click(`${F} .btn-cl`); await p.waitForTimeout(400);
               await p.click(`${F} .menu-cl button[data-l="SOUL"]`); await p.waitForTimeout(1200); }

  if (await p.$(F)) {
    await p.dblclick(F); await p.waitForTimeout(700);
    ok('doble click marca EN DISCO', await p.$(`${F} .bajado`) !== null);
    await p.dblclick(F); await p.waitForTimeout(600);
    await p.click(`${F} [data-quitar]`); await p.waitForTimeout(300);
    await p.click(`${F} [data-quitar]`); await p.waitForTimeout(700);
    ok('quitar puntaje limpia la tarjeta', await est() === 0);
  }
}
await vista('MI CRATE');
await (await p.$('#bhot')).click(); await p.waitForTimeout(4500);
await vista('HOTLIST');
console.log('\n' + (err.length ? 'JS: ' + err.join(' | ') : 'sin errores de JS'));
console.log(fallos.length ? `\n${fallos.length} FALLAS` : '\nTODO OK');
await b.close();
