# -*- coding: utf-8 -*-
"""Lee cuentas de Instagram que marcan VETAS, sin tocar la cuenta de Thomas.

Thomas, 4-nov: "hay que buscar canales - cuentas de ig como este y sacar
samples de acà, podemos barrer esta cuenta?" (@offtherecordsamples).

Lo valioso de esas cuentas no es lo que venden: son los TITULOS. Cada reel
dice año + pais + genero — "1973 Soviet Jazz Funk", "1976 Bulgarian Prog
Rock", "1979 Czech Folk Rock Drum". Eso es una lista de vetas, y encima
confirma la del bloque del este que Thomas ya tenia marcada (la escuela de
Camoflauge Monk y Alchemist).

Como se saca, y por que asi:
  * curl NO sirve: Instagram manda la pagina vacia y la llena por JavaScript.
  * yt-dlp sobre el perfil TAMPOCO: pide login.
  * un navegador normal SI, y sin iniciar sesion. Cero riesgo para la cuenta
    de Thomas — no se loguea, no sigue a nadie, no postea, solo mira lo que
    cualquiera ve entrando desde la calle.

El texto esta QUEMADO en el video, no en el caption, asi que no hay forma de
leerlo con codigo sin un OCR. Por eso el script arma una hoja de contacto con
las portadas y la lee una persona (o Claude) de un vistazo. Es medio manual a
proposito: son doce titulos cada varios dias, no vale la pena un OCR.

Uso:
    python insta.py offtherecordsamples      baja portadas y arma la hoja
    python insta.py <cuenta> --n=24          mas posteos
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(HERE, "tests", "ui")           # ahi vive playwright
SALIDA = os.path.join(HERE, "datos", "instagram")

GUION = r"""
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
"""


def hoja_de_contacto(carpeta):
    """Las doce portadas en una sola imagen, para leerlas de un vistazo."""
    try:
        from PIL import Image
    except ImportError:
        print("  (falta Pillow: pip install pillow)")
        return None
    import glob
    fs = sorted(glob.glob(os.path.join(carpeta, "tapas", "*.jpg")))
    if not fs:
        return None
    ims = [Image.open(f) for f in fs]
    L, cols = 300, 4
    filas = (len(ims) + cols - 1) // cols
    hoja = Image.new("RGB", (L * cols, L * filas), (20, 20, 20))
    for i, im in enumerate(ims):
        hoja.paste(im.resize((L, L)), (L * (i % cols), L * (i // cols)))
    p = os.path.join(carpeta, "hoja.png")
    hoja.save(p)
    return p


def una(cuenta, tope=12):
    """Lee una cuenta. Devuelve (datos, carpeta) o (None, motivo)."""
    cuenta = cuenta.strip("@/ ").split("/")[-1]
    carpeta = os.path.join(SALIDA, cuenta)
    os.makedirs(carpeta, exist_ok=True)
    guion = os.path.join(UI, "_insta.mjs")
    with open(guion, "w", encoding="utf-8") as f:
        f.write(GUION)
    try:
        r = subprocess.run(["node", guion, cuenta, str(tope), carpeta],
                           cwd=UI, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return None, "tardo demasiado"
    out = (r.stdout or "").strip()
    if "MURO_DE_LOGIN" in out:
        return None, "pide login (privada?)"
    if not out or out.startswith("ERROR"):
        return None, (out or (r.stderr or ""))[:70]
    try:
        return json.loads(out.splitlines()[-1]), carpeta
    except Exception:
        return None, "respuesta rara"


def rastrillar(semillas, tope_cuentas=20, por_cuenta=12):
    """Arranca de unas cuentas y sigue las relacionadas, como una mancha.

    Va DESPACIO a proposito (pausa entre cuentas): Instagram corta el acceso
    si lo golpeas, y acá no hay sesion de nadie que arriesgar pero igual no
    tiene sentido que nos bloqueen la IP a mitad del rastrillo.
    """
    import time as _t
    cola = [c.strip("@/ ").split("/")[-1] for c in semillas]
    vistas, hallazgos = set(), []
    while cola and len(vistas) < tope_cuentas:
        c = cola.pop(0)
        if c.lower() in vistas:
            continue
        vistas.add(c.lower())
        print("  [%2d/%d] @%-26s " % (len(vistas), tope_cuentas, c[:26]), end="", flush=True)
        d, carpeta = una(c, por_cuenta)
        if not d:
            print("-> %s" % carpeta)
            _t.sleep(2)
            continue
        hoja = hoja_de_contacto(carpeta)
        cerca = [x for x in d.get("cerca", []) if x.lower() not in vistas
                 and x.lower() != c.lower()]
        hallazgos.append({"cuenta": c, "posteos": d["posts"], "tapas": d["tapas"],
                          "hoja": hoja, "cerca": cerca})
        print("-> %2d portadas, %d cuentas nuevas" % (d["tapas"], len(cerca)))
        for x in cerca:
            if x.lower() not in vistas and x not in cola:
                cola.append(x)
        _t.sleep(3)                      # no golpear
    return hallazgos, vistas


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print('decime la cuenta:  python insta.py offtherecordsamples')
        print('o rastrillá:       python insta.py --rastrillar cuenta1 cuenta2')
        return 1

    if "--rastrillar" in sys.argv:
        tope = int(next((a.split("=")[1] for a in sys.argv
                         if a.startswith("--cuentas=")), "20"))
        print("rastrillando desde %d semillas (tope %d cuentas)..." % (len(args), tope))
        print()
        hall, vistas = rastrillar(args, tope)
        reg = os.path.join(SALIDA, "rastrillo.json")
        os.makedirs(SALIDA, exist_ok=True)
        with open(reg, "w", encoding="utf-8") as f:
            json.dump(hall, f, ensure_ascii=False, indent=1)
        print()
        print("cuentas leidas: %d" % len(hall))
        print()
        print("HOJAS PARA MIRAR (ahi estan los discos y las vetas):")
        for h in hall:
            if h["hoja"]:
                print("   @%-26s %s" % (h["cuenta"][:26], h["hoja"]))
        print()
        print("registro: %s" % reg)
        return 0
    cuenta = args[0].strip("@/ ").split("/")[-1]
    tope = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--n=")), "12"))

    carpeta = os.path.join(SALIDA, cuenta)
    os.makedirs(carpeta, exist_ok=True)
    # el guion va JUNTO a node_modules: node resuelve los imports desde la
    # carpeta del archivo, no desde el cwd, asi que dejarlo en otro lado da
    # ERR_MODULE_NOT_FOUND aunque se corra con cwd=UI
    guion = os.path.join(UI, "_insta.mjs")
    with open(guion, "w", encoding="utf-8") as f:
        f.write(GUION)

    if not os.path.exists(os.path.join(UI, "node_modules")):
        print("falta playwright. Corre una vez:  crate ui")
        return 1

    print("leyendo @%s sin iniciar sesion..." % cuenta)
    r = subprocess.run(["node", guion, cuenta, str(tope), carpeta],
                       cwd=UI, capture_output=True, text=True, timeout=300)
    salida = (r.stdout or "").strip()
    if "MURO_DE_LOGIN" in salida:
        print("  Instagram pidio login para esta cuenta (puede ser privada).")
        return 2
    if salida.startswith("ERROR") or not salida:
        print("  no pude leerla: %s" % (salida or (r.stderr or "")[:160]))
        return 1
    try:
        d = json.loads(salida.splitlines()[-1])
    except Exception:
        print("  respuesta rara: %s" % salida[:160])
        return 1

    print("  posteos vistos : %d" % d["posts"])
    print("  portadas       : %d" % d["tapas"])
    cerca = [c for c in d.get("cerca", []) if c.lower() != cuenta.lower()]
    if cerca:
        print()
        print("  CUENTAS PARECIDAS (de donde seguir cavando):")
        for c in cerca:
            print("     @%-28s  ->  crate ig %s" % (c, c))
    hoja = hoja_de_contacto(carpeta)
    print()
    if hoja:
        print("MIRA ESTA IMAGEN, ahi estan los titulos de las vetas:")
        print("   %s" % hoja)
        print()
    print("los links de cada reel quedaron en:")
    print("   %s" % os.path.join(carpeta, "posts.json"))
    print()
    print("Cuando leas las vetas, agregalas a ESCENAS en criterios.py y cava con:")
    print('   crate cavar <veta>')
    return 0


if __name__ == "__main__":
    sys.exit(main())
