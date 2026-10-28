import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({viewport:{width:1100,height:900}});
const err = []; p.on('pageerror', e => err.push(e.message));
await p.goto('http://127.0.0.1:7777/mi-crate.html', {waitUntil:'networkidle'});
await p.waitForTimeout(2200);
await p.click('#bkpi');
await p.waitForTimeout(1800);
const r = await p.evaluate(() => ({
  visible: document.querySelector('#kpi').classList.contains('on'),
  titular: document.querySelector('.kgrande b')?.textContent,
  filas: document.querySelectorAll('.kfila').length,
  secciones: [...document.querySelectorAll('.ktit')].map(e=>e.textContent),
  // las barras de las listas tienen que tomar el color del genero
  colores: [...document.querySelectorAll('.kbar i')].map(e =>
    getComputedStyle(e).backgroundColor).filter((v,i,a)=>a.indexOf(v)===i).length,
  cifras: [...document.querySelectorAll('.kcifras b')].map(e=>e.textContent),
}));
console.log(JSON.stringify(r, null, 1));
const vis = await p.isVisible('.kcaja');
console.log(vis && r.filas > 8 ? 'TODO OK' : 'FALLA: el panel no se ve o viene vacio');
await p.screenshot({path:'kpi.png'});
console.log(err.length ? 'JS: '+err.join(' | ') : 'sin errores de JS');
await b.close();
