# -*- coding: utf-8 -*-
"""Diseño de la app.

Historial de errores, para no repetirlos:
  1. papel beige y sepia -> "colores de una oficina de nueva york re formal"
  2. bermellon y mostaza -> "LAS IAS NO CONOCEN OTRAS PALETAS QUE NO ESTEN EN EL
     ESPECTRO DEL MARRON - NARANJA?"
  3. verde institucional -> "donde quedaron los azules del city pop? me baiteaste"
  4. azul noche -> azul sobre azul, ILEGIBLE. El error de fondo: los bordes y
     etiquetas quedaron atados a una variable "oscura" que en un tema oscuro es
     MAS oscura que el fondo. Invisibles por construccion. Y verifique solo el
     texto principal contra el fondo, no los bordes, los placeholders ni nada
     con opacidad — que era justo lo que se veia mal.

REFERENCIA, esta vez buscada y no inventada:
  * Reid Miles (Blue Note, 400+ tapas): "nunca usaba muchos tonos, explotaba el
    contraste entre blanco y negro, con excepciones como naranja y azul".
    Tipografia bold, espacio negativo teatral, Bauhaus y escuela suiza.
  * Niklaus Troxler (posters del festival de jazz de Willisau): alto contraste,
    colores complementarios, serigrafia.
  Los dos trabajan con BLANCO Y NEGRO MAS UN COLOR. Eso no se puede volver
  ilegible.

SISTEMA DE VARIABLES, rehecho para que el error 4 no pueda repetirse:
  --fondo    el fondo
  --sobre    superficie elevada (inputs, fila al pasar el mouse)
  --fuerte   MAXIMO contraste contra el fondo: texto principal y bordes
  --medio    texto secundario   (>= 4.5 contra fondo Y contra sobre)
  --suave    texto terciario    (>= 4.5 contra fondo Y contra sobre)
  --acento   EL color
  --acento2  el segundo, para lo que ya esta hecho
  --stxt     el texto que va ENCIMA del acento
Ningun borde ni texto usa un color sin verificar contra su fondo real.
app_check.py recorre todos los pares y falla si alguno baja de 4.5.
"""

FUENTES = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
           '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
           '<link href="https://fonts.googleapis.com/css2?'
           'family=Bebas+Neue&'
           'family=DM+Serif+Display:ital@0;1&'
           'family=Archivo:wght@500;600;700;800;900&'
           'family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">')

CSS = r"""
:root{
  --serif:'DM Serif Display',Georgia,serif;
  --display:'Bebas Neue','Archivo',Impact,sans-serif;
  --sans:'Archivo',system-ui,-apple-system,'Segoe UI',sans-serif;
  --mono:'Space Mono','SF Mono',Consolas,monospace;
}

/* ---------------------------------------------------------------------------
   Las tres paletas salen de tapas que eligio Thomas. Los hex se muestrearon
   de las imagenes, no se inventaron.
   --------------------------------------------------------------------------- */

/* 1 · ALL OF ME — Masayoshi Takanaka, 1979. El Pacifico desde el aire:
   azul profundo dominante (#004890 es el 8.6% de la tapa), nubes blancas,
   el naranja del traje de paracaidismo y el turquesa del arrecife. */
body[data-t="allofme"]{
  --fondo:#06305c; --sobre:#0e467c; --sombra:rgba(255,255,255,.17);
  --fuerte:#eef5fa; --medio:#b4cee2; --suave:#97b8d2;
  --acento:#ff9436; --acento2:#4fd0e0; --stxt:#06305c; --estrella:#ff6b6b;
  --barra:#021f3f; --barratxt:#dfeaf4; --barranum:#ff9436;
}
/* 2 · FOR YOU — Tatsuro Yamashita, 1982, ilustracion de Hiroshi Nagai.
   Mediodia: cielo azul (#126cb4, el 12.9%), concreto crema, verde palmera. */
body[data-t="foryou"]{
  --fondo:#f7f6e9; --sobre:#ffffff; --sombra:rgba(16,50,79,.17);
  --fuerte:#10324f; --medio:#2f5169; --suave:#4a6a80;
  --acento:#0f66ad; --acento2:#2a7d64; --stxt:#f7f6e9; --estrella:#d6343a;
  --barra:#10324f; --barratxt:#eef3f7; --barranum:#4fb0ef;
}
/* 3 · T-WAVE — Takanaka, 1980. Atardecer: negro de las palmeras a contraluz,
   el rojo del descapotable (#c62436, el 14.2% de la tapa) y la arena. */
body[data-t="twave"]{
  --fondo:#17161a; --sobre:#262329; --sombra:rgba(255,255,255,.15);
  --fuerte:#efece8; --medio:#c5bdb4; --suave:#a69d94;
  --acento:#e8414e; --acento2:#e8a561; --stxt:#17161a; --estrella:#ff7a6b;
  --barra:#0d0c0f; --barratxt:#e8e3dd; --barranum:#e8a561;
}
/* 4 · WILLISAU — los posters suizos de jazz de Niklaus Troxler. Queda por si
   queres algo sin referencia japonesa: negro puro y amarillo de serigrafia. */
body[data-t="willisau"]{
  --fondo:#131312; --sobre:#20201d; --sombra:rgba(255,255,255,.16);
  --fuerte:#f5f3ec; --medio:#c2bfb4; --suave:#a09d92;
  --acento:#f5c518; --acento2:#4ec9a5; --stxt:#131312; --estrella:#ff5e5e;
  --barra:#070706; --barratxt:#f5f3ec; --barranum:#f5c518;
}

/* ---------------------------------------------------------------
   Un color por genero. Ocho matices repartidos en la rueda, con la
   luminosidad pareja para que ninguno pese mas que otro, y elegidos para
   complementar el azul y el verde de la paleta sin copiarlos.
   Todos verificados: el texto crema encima da entre 4.5 y 7.9 de contraste.
   --------------------------------------------------------------- */
.g-soul       {--g:#b23a48}   /* carmin */
.g-80s        {--g:#c0407e}   /* magenta nocturno */
.g-rnb        {--g:#7a4a9e}   /* violeta */
.g-dark       {--g:#3d4a7a}   /* indigo */
.g-fusion     {--g:#1c6f96}   /* azul petroleo */
.g-citypop    {--g:#0f7575}   /* turquesa */
.g-piano      {--g:#2f7a52}   /* verde pino */
.g-folk       {--g:#5d6824}   /* oliva */
.pl{background:var(--g,var(--acento2)) !important;color:#f7f6e9 !important}
.menu-cl button::before{content:'';display:inline-block;width:8px;height:8px;
  border-radius:2px;background:var(--g,var(--suave));margin-right:7px;vertical-align:0}
.chip[data-f^="pl:"].on{background:var(--g,var(--acento2));border-color:var(--g,var(--acento2));
  color:#f7f6e9}
.chip[data-f^="pl:"]::before{content:'';display:inline-block;width:7px;height:7px;
  border-radius:2px;background:var(--g,var(--suave));margin-right:6px;vertical-align:1px}

*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0;background:var(--fondo);color:var(--fuerte);
  font-family:var(--sans);font-size:16px;line-height:1.5;
}
/* textura: grano apenas perceptible, no toca la legibilidad */
body::after{
  content:'';position:fixed;inset:0;pointer-events:none;z-index:0;opacity:.05;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.8' numOctaves='4'/%3E%3C/filter%3E%3Crect width='200' height='200' filter='url(%23n)'/%3E%3C/svg%3E");
}
.wrap{position:relative;z-index:3;max-width:1200px;margin:0 auto;padding:0 24px 90px}

/* ---------- cabecera: el bloque de color de una tapa ---------- */
header{margin:0 -24px}
.bloque{
  background:var(--acento);color:var(--stxt);padding:30px 24px 22px;
  display:flex;align-items:flex-end;justify-content:space-between;gap:22px;flex-wrap:wrap;
}
h1{
  font-family:var(--display);font-size:5.6rem;line-height:.76;margin:0;
  letter-spacing:.014em;font-weight:400;text-transform:uppercase;
}
.tag{font-family:var(--mono);font-size:.68rem;letter-spacing:.17em;text-transform:uppercase;
  border-left:2px solid var(--stxt);padding-left:11px;line-height:1.75}
footer .apagar{margin-left:8px;border-color:var(--suave);color:var(--suave)}
footer .apagar:hover{border-color:var(--estrella);color:var(--estrella)}
footer .apagar.preg{border-color:var(--estrella);color:var(--estrella);
  background:transparent;font-weight:700}
/* la pantalla de despedida: la app ya no existe, no tiene sentido dejar la
   tabla ahi como si todavia funcionara */
.chau{min-height:100vh;display:flex;flex-direction:column;align-items:center;
  justify-content:center;gap:10px;text-align:center;background:var(--fondo)}
.chau b{font-family:var(--display);font-size:2rem;letter-spacing:.08em;
  color:var(--fuerte)}
.chau span{font-family:var(--mono);font-size:.78rem;color:var(--medio)}
.chau .chico{font-size:.68rem;color:var(--suave)}
/* la etiqueta de genero en el hotlist: misma pastilla de color que en el
   crate, para que se lea como el mismo idioma */
.meta2{display:flex;align-items:center;gap:6px;margin-top:3px}
.meta2 .sug.ya{color:var(--acento2)}
.meta2 .sug{font-family:var(--mono);font-size:.58rem;letter-spacing:.1em;
  text-transform:uppercase;color:var(--suave)}
.sello{font-family:var(--mono);font-size:.56rem;letter-spacing:.06em;
  margin-left:10px;padding:1px 5px;border:1px solid var(--suave);border-radius:2px;
  color:var(--suave);white-space:nowrap}
.tag b{font-size:1.1rem;display:block;letter-spacing:.05em}
.temas{display:flex;gap:5px;margin-top:10px}
.temas button{border-radius:3px;
  font-family:var(--mono);font-size:.58rem;letter-spacing:.11em;text-transform:uppercase;
  background:transparent;border:1.5px solid var(--stxt);color:var(--stxt);
  padding:3px 8px;cursor:pointer;line-height:1.5;
}
.temas button:hover{background:rgba(255,255,255,.18)}
.temas button.on{background:var(--stxt);color:var(--acento);font-weight:700}
.cifras{display:flex;gap:30px;flex-wrap:wrap;padding:14px 24px 0;
  background:var(--barra);margin:0 -24px;color:var(--barratxt)}
.cifra{padding:0 0 14px}
.cifra b{font-family:var(--display);font-size:2.1rem;line-height:1;color:var(--barranum);
  display:block;letter-spacing:.02em}
.cifra span{font-family:var(--mono);font-size:.6rem;letter-spacing:.16em;
  text-transform:uppercase;color:var(--barratxt)}

/* ---------- panel ---------- */
.panel{position:sticky;top:0;z-index:9;background:var(--fondo);
  border-bottom:1.5px solid var(--fuerte);padding:14px 0 12px;margin-bottom:2px}
.fila1{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.campo{display:flex;align-items:center;gap:6px}
.campo>span{font-family:var(--display);font-size:1.05rem;letter-spacing:.09em;
  text-transform:uppercase;color:var(--acento)}
input{font-family:var(--mono);font-size:.86rem;color:var(--fuerte);
  background:var(--sobre);border:1.5px solid var(--fuerte);border-radius:3px;
  padding:7px 10px;outline:none}
input:focus{border-color:var(--acento);box-shadow:inset 0 0 0 1px var(--acento)}
input::placeholder{color:var(--suave);opacity:1}
#q{flex:1;min-width:260px;font-family:var(--sans);font-size:1rem;font-weight:600;padding:10px 13px}
.mini{width:66px;text-align:center}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:12px}
.chip{border-radius:3px;
  font-family:var(--display);font-size:1.06rem;letter-spacing:.07em;text-transform:uppercase;
  border:1.5px solid var(--fuerte);background:var(--fondo);color:var(--fuerte);
  padding:3px 13px 2px;cursor:pointer;user-select:none;line-height:1.45;
}
.chip:hover{background:var(--sobre)}
.chip.on{background:var(--fuerte);color:var(--fondo)}
.chip.on.b,.chip.on.m{background:var(--acento);border-color:var(--acento);color:var(--stxt)}
.chip.on.o,.chip.on.p{background:var(--acento2);border-color:var(--acento2);color:var(--stxt)}

/* ---------- filtros, ordenados por tipo ---------- */
.grupo{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:9px}
.gl{font-family:var(--display);font-size:.92rem;letter-spacing:.11em;text-transform:uppercase;
  color:var(--suave);min-width:62px}
.rango{display:inline-flex;align-items:center;gap:5px;border:1.5px solid var(--sombra);
  border-radius:3px;padding:2px 8px 2px 6px}
.rango .ru{font-family:var(--display);font-size:.9rem;letter-spacing:.09em;
  text-transform:uppercase;color:var(--acento)}
.rango .gui{color:var(--suave);font-family:var(--mono);font-size:.76rem}
.mini{width:46px;text-align:center;border:0;border-bottom:1.5px solid var(--sombra);
  border-radius:0;padding:3px 2px;background:transparent}
.mini.ancho{width:54px}
.mini:focus{border-bottom-color:var(--acento);background:transparent;box-shadow:none}
/* sin flechitas: los numeros se escriben, no se clickean */
.mini::-webkit-outer-spin-button,.mini::-webkit-inner-spin-button{-webkit-appearance:none;margin:0}
.mini{-moz-appearance:textfield}
.chip.ghost{border-style:dashed;color:var(--suave);border-color:var(--sombra)}
.chip.ghost:hover{border-style:solid;color:var(--acento);border-color:var(--acento)}

#cavar{border-top:1.5px dashed var(--sombra);padding-top:11px;margin-top:11px}
#cavar .lbl{font-family:var(--display);font-size:1.05rem;letter-spacing:.09em;
  text-transform:uppercase;color:var(--acento)}
#qy{flex:1;min-width:230px;font-family:var(--sans);font-size:.95rem;font-weight:600;padding:8px 11px}
#cavinfo{font-family:var(--mono);font-size:.64rem;color:var(--suave);line-height:1.35}
#cavinfo b{color:var(--acento)}
tr.nuevo td.cat{color:var(--acento2)}
.razon{font-family:var(--mono);font-size:.62rem;color:var(--acento2);margin-top:3px}

/* ---------- dónde estoy parado ----------
   Thomas, 27-oct: "es re confuso la busqueda, no entiendo si estoy en mi crate
   o en youtube, si lo que voto se guarda, donde se guarda". Tenia razon: no
   habia ninguna señal. Ahora el cuerpo entero cambia. */
.modo{display:inline-flex;align-items:center;gap:7px;font-family:var(--display);
  font-size:1.15rem;letter-spacing:.08em;text-transform:uppercase}
.modo::before{content:'';width:9px;height:9px;border-radius:50%;background:var(--acento2)}
body.buscando .modo::before{background:var(--acento)}
body.buscando{box-shadow:inset 0 0 0 4px var(--acento)}
body.buscando .panel{background:var(--sobre);border-bottom-color:var(--acento)}
body.buscando #cavar{border-top-color:var(--acento)}
.modo .det{font-family:var(--mono);font-size:.62rem;letter-spacing:.04em;
  text-transform:none;color:var(--suave)}

/* avisito de guardado */
#flash{position:fixed;left:50%;bottom:104px;transform:translate(-50%,14px);
  background:var(--barra);color:var(--barratxt);font-family:var(--mono);
  font-size:.74rem;padding:9px 16px;border-radius:4px;border-left:3px solid var(--acento2);
  opacity:0;pointer-events:none;transition:opacity .16s,transform .16s;z-index:60}
#flash.on{opacity:1;transform:translate(-50%,0)}

/* ---------- clasificar: a que lista va ---------- */
.clasif{position:relative;display:inline-block}
.btn-cl{
  font-family:var(--display);font-size:.84rem;letter-spacing:.09em;text-transform:uppercase;
  border:1.5px dashed var(--suave);border-radius:3px;background:transparent;color:var(--suave);
  padding:1px 7px;cursor:pointer;line-height:1.5;visibility:hidden;
}
tr:hover .btn-cl,.clasif.abierto .btn-cl{visibility:visible}
.btn-cl:hover{border-style:solid;border-color:var(--acento);color:var(--acento)}
.menu-cl{
  position:absolute;right:0;top:calc(100% + 4px);z-index:40;display:none;
  max-height:58vh;overflow:auto;
  background:var(--sobre);border:1.5px solid var(--fuerte);border-radius:4px;
  padding:5px;min-width:152px;box-shadow:0 5px 18px rgba(0,0,0,.2);
}
.clasif.abierto .menu-cl{display:block}
/* si no entra para abajo, se abre para arriba: si no choca con el footer o
   con el reproductor */
.clasif.arriba .menu-cl{top:auto;bottom:calc(100% + 4px)}
.menu-cl button{
  display:block;width:100%;text-align:left;font-family:var(--display);font-size:.95rem;
  letter-spacing:.07em;text-transform:uppercase;background:transparent;border:0;
  color:var(--fuerte);padding:5px 8px;cursor:pointer;border-radius:3px;line-height:1.4;
}
.menu-cl button:hover{background:var(--acento);color:var(--stxt)}
.menu-cl button.ya{color:var(--acento2)}
.menu-cl button.ya::after{content:' ✓'}
.menu-cl .sep{height:1px;background:var(--sombra);margin:4px 2px}

/* ---------- resultados de Soulseek ---------- */
/* =============== NUMEROS: como venis =============== */
.panelbtn{position:absolute;right:0;top:0}
header{position:relative}
#kpi{position:fixed;inset:0;z-index:70;display:none;align-items:flex-start;
  justify-content:center;padding:40px 16px;overflow:auto;
  background:rgba(16,50,79,.42)}
#kpi.on{display:flex}
.kcaja{width:100%;max-width:620px;background:var(--sobre);border-radius:4px;
  box-shadow:0 18px 50px var(--sombra);overflow:hidden}
.kcab{display:flex;align-items:center;justify-content:space-between;
  padding:13px 18px;background:var(--barra);color:var(--barratxt)}
.kcab b{font-family:var(--display);font-size:1.2rem;letter-spacing:.08em}
.kcab button{background:transparent;border:0;color:var(--barratxt);cursor:pointer;
  font-size:1rem;line-height:1}
.kcuerpo{padding:18px}
.kgrande{text-align:center;padding:6px 0 18px;border-bottom:1px solid var(--sombra)}
.kgrande b{display:block;font-family:var(--display);font-size:3.2rem;
  line-height:1;color:var(--acento)}
.kgrande span{display:block;font-family:var(--mono);font-size:.74rem;
  color:var(--medio);margin-top:6px}
.kgrande .kchico{font-size:.64rem;color:var(--suave);margin-top:3px}
.ktit{font-family:var(--mono);font-size:.62rem;letter-spacing:.14em;
  text-transform:uppercase;color:var(--suave);margin:18px 0 8px}
.kfila{display:flex;align-items:center;gap:9px;margin-bottom:5px}
.knom{flex:0 0 32%;font-family:var(--mono);font-size:.68rem;color:var(--fuerte);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kbar{flex:1;height:13px;background:var(--fondo);border-radius:2px;overflow:hidden}
.kbar i{display:block;height:100%;background:var(--medio);border-radius:2px}
.kbar i.bien{background:var(--acento2)}
.kbar i.flojo{background:var(--suave)}
.kbar i.estr{background:var(--estrella)}
.kbar i[class*='g-']{background:var(--g,var(--medio))}
.kval{flex:0 0 46px;text-align:right;font-family:var(--mono);font-size:.7rem;
  font-weight:700;color:var(--fuerte)}
.kcifras{display:grid;grid-template-columns:repeat(4,1fr);gap:9px;margin-top:4px}
.kcifras div{text-align:center;padding:9px 4px;background:var(--fondo);border-radius:3px}
.kcifras b{display:block;font-family:var(--display);font-size:1.3rem;color:var(--fuerte)}
.kcifras span{font-family:var(--mono);font-size:.58rem;color:var(--suave)}

#slsk{position:fixed;right:16px;bottom:104px;width:420px;max-height:62vh;z-index:55;
  background:var(--sobre);border:1.5px solid var(--fuerte);border-radius:5px;
  box-shadow:0 10px 34px rgba(0,0,0,.26);display:none;flex-direction:column}
#slsk.on{display:flex}
#slsk .cab{display:flex;align-items:center;gap:9px;padding:10px 13px;
  border-bottom:1.5px solid var(--sombra);background:var(--acento);color:var(--stxt)}
#slsk .cab b{font-family:var(--display);font-size:1.15rem;letter-spacing:.07em;
  text-transform:uppercase;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#slsk .cab button{background:transparent;border:0;color:var(--stxt);cursor:pointer;
  font-size:1rem;padding:0 4px}
#slsk .lista{overflow:auto;padding:5px}
#slsk .fila{display:flex;align-items:center;gap:9px;padding:7px 9px;border-radius:3px;
  font-size:.82rem;cursor:pointer}
#slsk .fila:hover{background:var(--fondo)}
#slsk .nom{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  color:var(--fuerte)}
#slsk .fmt{font-family:var(--mono);font-size:.66rem;padding:1px 6px;border-radius:2px;
  background:var(--acento2);color:var(--stxt);white-space:nowrap}
#slsk .fmt.mp3{background:var(--suave)}
#slsk .usr{font-family:var(--mono);font-size:.62rem;color:var(--suave);white-space:nowrap}
/* el boton de bajar: discreto hasta que lo apuntas, verde cuando quedo pedido */
/* al azar: apagado se ve como un control mas; prendido toma el color del
   reproductor para que se note de un vistazo cual es el estado */
.pbtn.mez{display:inline-flex;align-items:center;justify-content:center;opacity:.55}
.pbtn.mez:hover{opacity:1}
.pbtn.mez.on{opacity:1;color:var(--barranum)}
.pbtn.mez.on::after{content:'';position:absolute;left:50%;bottom:2px;width:4px;
  height:4px;margin-left:-2px;border-radius:50%;background:var(--barranum)}
.pbtn.mez{position:relative}

#slsk .bajar{margin-left:4px;border:1px solid var(--acento);background:transparent;
  color:var(--acento);font-family:var(--mono);font-size:.62rem;letter-spacing:.06em;
  text-transform:uppercase;padding:3px 8px;border-radius:2px;cursor:pointer;
  transition:background .12s,color .12s}
#slsk .bajar:hover:not(:disabled){background:var(--acento);color:var(--stxt)}
#slsk .bajar:disabled{opacity:.5;cursor:default}
#slsk .bajar.listo{border-color:var(--acento2);color:var(--acento2);opacity:1}
#slsk .bajar.fallo{border-color:var(--estrella);color:var(--estrella);opacity:1}
#slsk .vacio2{padding:26px 12px;text-align:center;color:var(--suave);
  font-family:var(--mono);font-size:.76rem}

/* ---------- conteo ---------- */
.conteo{display:flex;justify-content:space-between;align-items:baseline;gap:18px;
  font-family:var(--mono);font-size:.76rem;color:var(--medio);
  padding:12px 0 8px;border-bottom:1.5px solid var(--fuerte);flex-wrap:wrap}
.conteo b{font-family:var(--display);font-size:1.6rem;color:var(--acento);letter-spacing:.03em}
.conteo .der{color:var(--suave)}

/* ---------- tabla ---------- */
table{width:100%;border-collapse:collapse}
thead th{
  font-family:var(--display);font-size:1.04rem;letter-spacing:.1em;text-transform:uppercase;
  color:var(--medio);text-align:left;padding:11px 9px 8px;white-space:nowrap;
  border-bottom:1.5px solid var(--fuerte);cursor:pointer;user-select:none;
}
thead th:hover{color:var(--acento)}
thead th.r{text-align:right}
thead th .f{opacity:0;margin-left:3px}
thead th.act{color:var(--acento)} thead th.act .f{opacity:1}
tbody tr{border-bottom:1px solid var(--sombra)}
tbody tr:last-child{border-bottom:0}
tbody tr{cursor:pointer;position:relative}
/* la fila se tiñe con el color de su genero, apenas: una linea al costado,
   el numero de catalogo, y un fondo casi imperceptible al pasar el mouse */
tbody tr[class*="g-"]{box-shadow:inset 2px 0 0 var(--g)}
tbody tr[class*="g-"] td.cat{color:var(--g)}
tbody tr:hover{background:var(--sobre);box-shadow:inset 3px 0 0 var(--acento)}
tbody tr[class*="g-"]:hover{
  background:color-mix(in srgb, var(--g) 7%, var(--sobre));
  box-shadow:inset 3px 0 0 var(--g);
}
tbody tr[class*="g-"]:hover .tem{color:var(--g)}
/* lo que NO reproduce al clickear vuelve al cursor normal */
tbody tr .estrellas,tbody tr .slsk,tbody tr .clasif,tbody tr [data-quitar],
tbody tr a{cursor:pointer}
/* el titulo se marca al pasar, para que se vea que la fila es clickeable */
tbody tr:hover .tem{color:var(--acento)}
/* las filas tienen 2-3 lineas: centrado vertical, como recomiendan las guias
   de tablas. Arriba solo si la diferencia de alto fuera mayor. */
td{padding:11px 10px;vertical-align:middle}

/* --- jerarquia: el TEMA es lo que se busca, va primero y mas grande --- */
.tem{
  font-family:var(--sans);font-weight:700;font-size:1.04rem;line-height:1.25;
  color:var(--fuerte);letter-spacing:-.008em;
  display:block;margin:0;
}
.art{
  font-family:var(--sans);font-weight:500;font-size:.86rem;line-height:1.3;
  color:var(--medio);text-decoration:none;display:inline;
}
.art:hover{color:var(--acento);text-decoration:underline;text-underline-offset:2px}
/* el contexto va abajo y en voz baja: no compite */
.meta{font-family:var(--mono);font-size:.64rem;color:var(--suave);margin-top:4px;
  display:flex;flex-wrap:wrap;gap:7px;align-items:center}
.pl{font-family:var(--sans);font-weight:700;font-size:.58rem;letter-spacing:.09em;
  text-transform:uppercase;background:var(--acento2);color:var(--stxt);
  padding:1px 6px;border-radius:2px;line-height:1.5}

td.cat{font-family:var(--mono);font-size:.66rem;color:var(--suave);width:66px;
  white-space:nowrap;font-variant-numeric:tabular-nums;font-weight:700}
/* numeros: a la derecha y de ancho fijo, para que se puedan comparar de un vistazo */
td.dato{font-family:var(--mono);font-size:.8rem;text-align:right;white-space:nowrap;
  color:var(--suave);width:76px;font-variant-numeric:tabular-nums}
td.dato .v{font-family:var(--mono);font-weight:700;font-size:1.02rem;color:var(--fuerte);
  letter-spacing:-.01em;line-height:1.15;display:block;font-variant-numeric:tabular-nums}
/* sin opacity: al 65% quedaba en 2,7 de contraste sobre "for you" (minimo
   4,5). Ya es secundaria por tamaño, mayusculas y espaciado; no hace falta
   ademas apagarla hasta volverla ilegible. */
td.dato .u{font-size:.6rem;letter-spacing:.08em;text-transform:uppercase}
td.dato .v.men{color:var(--acento2)}
.bajado{display:inline-block;font-family:var(--sans);font-weight:700;font-size:.56rem;
  letter-spacing:.1em;color:var(--stxt);background:var(--acento2);padding:1px 5px;
  border-radius:2px;margin-right:6px;vertical-align:1px}

/* ---------- estrellas ----------
   Las estrellas SOLO ponen puntaje. Quitar es un boton aparte, porque tener el
   "borrar" en la quinta estrella hacia que un click de mas borrara el 5. */
td.est{width:150px;text-align:right;white-space:nowrap;padding-top:9px}
.rating{display:inline-flex;align-items:center;gap:7px}
.estrellas{display:inline-flex;gap:3px;cursor:pointer;font-size:1.5rem;line-height:1.05;
  user-select:none}
.estrellas .s{cursor:pointer;color:var(--estrella);transition:transform .08s,color .08s}
.estrellas .s.off{color:transparent;-webkit-text-stroke:1.5px var(--suave);opacity:.5}
.estrellas .s.on{color:var(--estrella);-webkit-text-stroke:0}
/* lo que vas a poner si hacés click: en hueco y un poco mas grande */
.estrellas .s.pre{color:transparent;-webkit-text-stroke:2px var(--estrella);opacity:1;
  transform:scale(1.16)}

/* boton de quitar: solo aparece si hay puntaje, y pide confirmar */
.quitar{border-radius:3px;
  font-family:var(--mono);font-size:.78rem;line-height:1;cursor:pointer;
  background:transparent;border:1.5px solid var(--suave);color:var(--suave);
  padding:2px 5px;visibility:hidden;
}
tr:hover .quitar,.quitar.preg{visibility:visible}
.quitar:hover{border-color:var(--estrella);color:var(--estrella)}
.quitar.preg{
  border-color:var(--estrella);color:var(--estrella);background:var(--sobre);
  font-size:.6rem;letter-spacing:.07em;text-transform:uppercase;padding:3px 7px;
  animation:aparece .14s ease-out;
}
@keyframes aparece{from{opacity:0;transform:translateX(5px)}to{opacity:1;transform:none}}

.slsk{border-radius:3px;font-family:var(--display);font-size:.92rem;letter-spacing:.07em;background:var(--fondo);
  cursor:pointer;border:1.5px solid var(--medio);color:var(--medio);padding:0 8px;
  margin-left:10px;line-height:1.5}
.slsk:hover{border-color:var(--acento);color:var(--acento)}
.vacio{padding:60px 10px;text-align:center;color:var(--medio);
  font-family:var(--display);font-size:1.6rem;letter-spacing:.08em}

footer{margin-top:36px;padding-top:16px;border-top:1.5px solid var(--fuerte);
  font-family:var(--mono);font-size:.68rem;color:var(--medio);
  display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;align-items:center}

/* ---------- reproductor ----------
   El iframe de YouTube no se muestra (queda de 1px, fuera de vista): se usa
   solo como motor de audio. Lo que se ve es la caratula del video y los
   controles propios. */
#player{position:fixed;left:0;right:0;bottom:0;z-index:50;background:var(--barra);
  color:var(--barratxt);border-top:2px solid var(--acento);display:none;
  align-items:center;gap:15px;padding:11px 20px}
#player.on{display:flex}
#ytbox{position:absolute;width:1px;height:1px;overflow:hidden;opacity:0;
  pointer-events:none;left:-9999px}
#cover{width:54px;height:54px;flex:0 0 auto;border-radius:3px;object-fit:cover;
  background:var(--sobre);box-shadow:0 1px 6px rgba(0,0,0,.3)}
.pinfo{flex:0 1 300px;min-width:0}
.pinfo .pa{font-weight:700;font-size:.97rem;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}
.pinfo .pt{font-family:var(--serif);font-size:.88rem;opacity:.75;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
/* barra de progreso propia, clickeable para saltar */
.barra{flex:1;min-width:120px;display:flex;align-items:center;gap:10px}
.pista{flex:1;height:5px;border-radius:3px;background:rgba(255,255,255,.17);
  cursor:pointer;position:relative}
.pista .av{position:absolute;left:0;top:0;bottom:0;border-radius:3px;
  background:var(--acento);width:0}
.pista .bolita{position:absolute;top:50%;width:11px;height:11px;border-radius:50%;
  background:var(--acento);transform:translate(-50%,-50%);left:0;
  opacity:0;transition:opacity .12s}
.pista:hover .bolita{opacity:1}
.ptiempo{font-family:var(--mono);font-size:.66rem;opacity:.7;white-space:nowrap}
.pbtn{font-family:var(--sans);font-size:.95rem;background:rgba(255,255,255,.09);
  border:0;border-radius:4px;color:var(--barratxt);cursor:pointer;
  padding:6px 11px;line-height:1}
.pbtn:hover{background:var(--acento);color:var(--stxt)}
.pbtn.gde{font-size:1.15rem;padding:8px 14px}
.pest{display:inline-flex;gap:3px;font-size:1.25rem;cursor:pointer;color:var(--estrella)}
.pest .s{cursor:pointer}
.pest .s.off{color:transparent;-webkit-text-stroke:1.4px var(--barratxt);opacity:.45}
body.conplayer{padding-bottom:96px}
/* el tema que suena se tiene que ver de lejos */
tr.sonando{background:var(--sobre);box-shadow:inset 5px 0 0 var(--estrella)}
tr.sonando:hover{background:var(--sobre);box-shadow:inset 5px 0 0 var(--estrella)}
tr.sonando .tem{color:var(--estrella)}
tr.sonando .art{color:var(--estrella);font-weight:700}
tr.sonando td.dato .v{color:var(--estrella)}
tr.sonando td.cat{color:var(--estrella);font-weight:700}
tr.sonando td.cat .eq{display:inline-flex;align-items:flex-end;gap:2px;height:12px;
  margin-right:5px;vertical-align:-2px}
tr.sonando td.cat .eq i{width:2.5px;background:var(--estrella);display:block;
  animation:eqb .62s ease-in-out infinite alternate}
tr.sonando td.cat .eq i:nth-child(1){height:5px;animation-delay:0s}
tr.sonando td.cat .eq i:nth-child(2){height:12px;animation-delay:.2s}
tr.sonando td.cat .eq i:nth-child(3){height:7px;animation-delay:.4s}
@keyframes eqb{from{transform:scaleY(.35)}to{transform:scaleY(1)}}
/* el que no se puede escuchar embebido: no se pierde, se marca */
tr.noemb td.cat::after{content:' ↗';color:var(--acento2);font-weight:700}
tr.noemb .art{text-decoration:underline dotted var(--acento2);text-underline-offset:3px}
tr.noemb .art[title]{cursor:pointer}
@media(prefers-reduced-motion:reduce){tr.sonando td.cat .eq i{animation:none}}
@media(max-width:760px){
  #yt{width:84px;height:48px} .pinfo .pt{display:none} .ptiempo{display:none}

  h1{font-size:3.6rem}
  .wrap{padding:0 15px 60px}
  header{margin:0 -15px} .bloque{padding:22px 15px 18px} .cifras{margin:0 -15px;padding:12px 15px 0}
  td.cat{display:none} td.dato{width:auto} td.dato .v{font-size:1.22rem}
  td.est{width:110px} .estrellas{font-size:1.36rem}
  #q{min-width:100%}
}
@media print{body::after{display:none}.panel,.slsk,footer{display:none}}
"""
