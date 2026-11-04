
import { chromium } from 'playwright';
import fs from 'fs';
const cuenta = process.argv[2], tope = +process.argv[3], salida = process.argv[4];
const b = await chromium.launch();
const p = await b.newPage({ viewport:{width:1280,height:1500},
  userAgent:'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
            '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' });
try {
  await p.goto('https://www.instagram.com/' + cuenta + '/',
               { waitUntil:'networkidle', timeout:60000 });
  await p.waitForTimeout(4000);
  for (let i = 0; i < Math.ceil(tope / 6); i++) {
    await p.mouse.wheel(0, 1600);
    await p.waitForTimeout(2200);
  }
  const r = await p.evaluate(() => {
    const out = [], vistos = new Set();
    document.querySelectorAll('a[href*="/reel/"], a[href*="/p/"]').forEach(a => {
      const img = a.querySelector('img');
      if (img && !vistos.has(a.href)) { vistos.add(a.href);
        out.push({ url:a.href, tapa:img.src, alt:img.alt || '' }); }
    });
    // Instagram muestra "cuentas relacionadas" en el perfil incluso sin
    // login: es la forma de saltar de un digger al siguiente.
    const RESERVADAS = ['explore','reels','accounts','about','privacy','terms',
                        'api','p','legal','directory','popular','developer'];
    const cerca = [...new Set([...document.querySelectorAll('a[href^="/"]')]
      .map(a => a.getAttribute('href'))
      .filter(h => /^\/[A-Za-z0-9._]{2,30}\/$/.test(h))
      .map(h => h.replace(/\//g, ''))
      .filter(u => !RESERVADAS.includes(u)))];
    return { login: !!document.querySelector('input[name="username"]'),
             posts: out, cerca };
  });
  if (r.login) { console.log('MURO_DE_LOGIN'); await b.close(); process.exit(2); }
  fs.mkdirSync(salida + '/tapas', { recursive: true });
  let n = 0;
  for (const x of r.posts.slice(0, tope)) {
    try {
      const resp = await p.request.get(x.tapa, { timeout: 30000 });
      if (resp.ok()) { fs.writeFileSync(
          salida + '/tapas/' + String(++n).padStart(2,'0') + '.jpg', await resp.body()); }
    } catch (e) {}
  }
  fs.writeFileSync(salida + '/posts.json', JSON.stringify(r.posts.slice(0, tope), null, 1));
  console.log(JSON.stringify({ posts: r.posts.length, tapas: n, cerca: r.cerca }));
} catch (e) { console.log('ERROR ' + String(e).slice(0,160)); process.exit(1); }
await b.close();
