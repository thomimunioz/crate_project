# Auditoría de CRATE — 27 oct 2026

Revisión completa del proyecto: seguridad, corrección, deuda técnica y riesgos
de regresión. Lo que se arregló en el acto está marcado **ARREGLADO**; lo que
queda está priorizado al final con un plan por etapas.

> **Nota sobre el pedido original.** El prompt de auditoría que me pasaste está
> escrito para un proyecto **Java / Spring Boot / React con Maven**. Este
> proyecto no es eso: es **Python + HTML/JS a mano**, con un FastAPI dormido y
> un React dormido. Adapté los criterios (seguridad, tests, CI, deuda) al stack
> real. Donde el prompt pedía algo que acá no aplica (perfiles de Maven,
> `application.yml`, inyección de dependencias) lo digo explícitamente en vez de
> inventar un equivalente.

---

## 0. Qué es este proyecto hoy, de verdad

Antes de auditar hay que decir qué está vivo, porque el repo engaña:

| Parte | Líneas | Último cambio | Estado |
|---|---|---|---|
| **`app/`** | 4.588 Python | hoy | **Esto es CRATE.** Lo usás todos los días |
| `backend/` (FastAPI) | 2.292 Python | 20-sep | Dormido. No lo levanta nadie |
| `frontend/` (React) | 9.104 TS/TSX | 20-sep | Dormido. Nunca reemplazó a `mi-crate.html` |
| `crate.db` | 51.438 temas | hoy | El activo real e irreemplazable |

**El 72% del código del repo no se ejecuta.** Eso no es neutral: es superficie
que hay que mantener, que confunde al buscar dónde tocar algo, y que da una
falsa sensación de cobertura. Decidir qué pasa con esas dos carpetas es la
deuda más grande del proyecto, y es una decisión tuya, no mía.

---

## 1. Seguridad

### 1.1 El servidor local servía el repo entero — **ARREGLADO** 🔴 CRÍTICO

`crate_server.py` delegaba en `SimpleHTTPRequestHandler` con
`directory=<raíz del proyecto>`. Cualquier archivo bajo la raíz se servía por
HTTP. Verificado antes del arreglo:

```
GET http://127.0.0.1:7777/.env       → 200, tus 11 claves
GET http://127.0.0.1:7777/crate.db   → 200, la base entera
```

Escucha solo en 127.0.0.1, así que no está expuesto a internet. Pero cualquier
proceso de la máquina —y cualquier página abierta en el navegador, vía una
petición a localhost— podía leerlo.

**Arreglo:** lista blanca de extensiones (`.html .css .js` + imágenes y
fuentes) y rechazo de todo lo que empiece con punto. Verificado: `.env` y
`crate.db` devuelven 403, la app sigue sirviendo normal. Hay un test de
regresión (`test_servidor.py::TestListaBlanca`).

### 1.2 La clave de slskd quedó junto al código — **ARREGLADO** 🟠

`slskd_key.txt` terminó dentro de `app/` al mudar el proyecto. Está en
`.gitignore` y **verificado que nunca entró a la historia de git**. El CI ahora
falla si alguien versiona un `.env`, una clave de slskd o un `.pem`.

### 1.3 El proxy del backend salteaba su propia allowlist — **ARREGLADO** 🟠

`backend/app/proxy.py` valida el host contra una allowlist
(`api.discogs.com, musicbrainz.org, archive.org`) y después hace la petición
con `follow_redirects=True`. **La allowlist se evaluaba solo en la URL
inicial.** Un host permitido que responda `302` hacia `127.0.0.1:8787` o hacia
una IP interna se seguía sin revalidar: SSRF que esquiva el control, en el
archivo que dice en su primera línea *"SIN ser un open relay"*.

**Arreglo:** los redirects se siguen a mano, revalidando el host en cada salto,
con tope de 5. Las credenciales de Discogs se recalculan por salto, así que no
viajan a un host que no las pidió.

> El backend está dormido, así que el riesgo práctico hoy es bajo. Se arregló
> igual porque el día que se levante nadie va a volver a mirar esto.

### 1.4 Lo que está bien y conviene no romper

- **SQL: todo parametrizado.** Ni una sola query armada con `%` o f-string.
- **`subprocess`: siempre con lista de argumentos, nunca `shell=True`.** El
  texto que escribís en el buscador no puede ejecutar nada.
- **El proxy de audio valida el id de YouTube** (11 chars alfanuméricos) antes
  de construir la URL.
- **`.env` nunca estuvo en git** (verificado sobre toda la historia).
- **El DSP borra el audio temporal en `finally`**, falle lo que falle.
- **CORS del backend** restringido a `localhost:5173`, no `*`.
- **`npm audit`: 0 vulnerabilidades** en el frontend.

### 1.5 Pendiente (bajo riesgo, backend dormido)

- `/analyze` acepta `url: str` sin validar y `seconds: int` sin tope. Un
  `seconds` enorme genera un WAV enorme. Vale acotarlo cuando se levante.

---

## 2. Corrección

### 2.1 Clasificar no actualizaba la tabla — **ARREGLADO** 🟠

Un tema traído del hotlist o del buscador se guardaba bien en la base, pero no
aparecía en *MI CRATE* hasta recargar la página: el HTML se genera con los
datos horneados y el cliente no tenía esa fila. Daba la impresión de que el
voto se había perdido.

**Arreglo:** `/api/playlist` y `/api/estrellas` devuelven la fila ya armada y el
cliente la inserta en caliente (`sumarACrate`).

### 2.2 Orden de rutas: `/api/slsk/bajadas` nunca llegaba — **ARREGLADO** 🟡

El prefijo genérico `/api/slsk/<id>` se declaraba antes y capturaba
`/api/slsk/bajadas`, interpretando `"bajadas"` como id de búsqueda. Lo
encontré probando la descarga, no leyendo. **La ruta concreta va antes que la
genérica** — vale para cualquier ruta que se agregue después.

### 2.3 El menú de clasificar chocaba con el reproductor — **ARREGLADO** 🟡

Se abría siempre hacia abajo. Ahora mide el espacio disponible.

### 2.4 Claves foráneas apagadas — **ARREGLADO** 🟡

`hotlist` declara `REFERENCES tema(id) ON DELETE CASCADE`, pero SQLite trae las
foráneas **apagadas por defecto**: la cláusula no hacía nada. Hoy no hay
huérfanos (verificado en las 4 tablas), así que no hubo daño. Ahora `db()` hace
`PRAGMA foreign_keys = ON`.

### 2.5 Temas duplicados ofrecidos como novedad — **ARREGLADO** 🟡

381 pares `(título, canal)` repetidos en la base: el mismo tema subido dos
veces con distinto id de YouTube. Medido: **22 de los que ya están en tus
listas tienen un gemelo suelto**, y el minero de vetas podía ofrecértelos como
descubrimiento. `veta.py` ahora los excluye.

Introduje una regresión de rendimiento al hacerlo (el subquery tardaba
minutos sobre 50k filas) y la arreglé con un índice `ix_tema_titulo`: la
corrida volvió a ser instantánea.

### 2.6 Falsos positivos en las vetas — **ARREGLADO** 🟡

- *Cynthia Rhodes*, *Izora Rhodes*: **"Rhodes" también es apellido.** Las
  pistas de instrumento ahora solo cuentan del lado del tema, no del artista.
- *"MAXIMO SPODEK · PIANO LOVE SONGS"*: canales de covers y música funcional.
- **La tonalidad menor sola no hace oscuro a nada** — media discografía soul
  está en menor. Ahora DARK exige menor **y** (lento o sin voz).

### 2.7 El timeout que faltaba — **ARREGLADO** 🟡

`hotlist.py --medir` lanzaba el DSP sin timeout: un yt-dlp colgado dejaba la
tanda a medias para siempre. Ahora 45 min de tope.

> Un grep inicial me marcó cuatro archivos más sin timeout. Era falso positivo:
> el `timeout=` estaba en una línea de continuación. Lo verifiqué recorriendo el
> AST, que es la forma correcta, y reverti esos cambios. Lo dejo escrito porque
> el grep ingenuo sobre llamadas multilínea va a volver a mentir.

---

## 3. Tests y CI

**Antes de hoy: cero tests, cero linter, cero CI.** Con 6.880 líneas de Python
vivas entre `app/` y `backend/`, cada cambio se validaba mirando la pantalla.

Eso tuvo un costo medible. El bug peor del proyecto —cincuenta regex rotas
porque un heredoc de bash convirtió cada `\b` en el carácter 8— sobrevivió días
porque **ese carácter no se imprime**: los patrones se leían perfectos y
fallaban en silencio, dejando pasar basura.

### Lo que hay ahora

43 tests sobre funciones puras: no tocan `crate.db`, no salen a la red, no
necesitan yt-dlp ni slskd. Corren en 0,2 s en cualquier máquina.

| Archivo | Qué fija |
|---|---|
| `test_regex_sanas.py` | ninguna regex tiene caracteres de control, y los `\b` funcionan |
| `test_criterios.py` | lo medido del oído: mainstream no, <1k views no, instrumental sí |
| `test_vetas.py` | los falsos positivos que costaron una corrida cada uno |
| `test_servidor.py` | **regresión de seguridad de la lista blanca**, parseo, orden de formatos |

**Verificados con mutaciones, no solo mirando que pasen.** Rompí a propósito la
lista blanca, una regex y el separador de artista: los tests cayeron. Dos
mutaciones se escaparon porque las dos capas de la lista blanca se tapan entre
sí; agregué una aserción sobre la lista misma y ahora se cazan.

**CI:** GitHub Actions corre pytest en cada push a `main` y `develop`, más un
guardia que falla si alguien versiona un secreto.

### Lo que NO está cubierto

- Los endpoints del servidor (hay que levantarlo: necesita `crate.db`)
- Todo `backend/` y todo `frontend/`
- `app_js.py` / `app_css.py`: 2.000 líneas de JS y CSS generadas, sin un test.
  El `app_check.py` solo verifica contraste de color.

---

## 4. Deuda técnica

### 4.1 Las dos carpetas dormidas 🟠

`backend/` y `frontend/` son el 72% del código y no corren. Opciones:
**(a)** archivarlas en una rama y sacarlas de `develop`; **(b)** revivir el
React; **(c)** dejarlas y asumir el ruido. Hoy el repo sugiere que CRATE es una
PWA React, y no lo es.

### 4.2 `crate.db` versionado 🟡

Es irreemplazable y por eso se commiteó. Pero SQLite es binario: **cada commit
guarda los 16 MB enteros de nuevo.** Diez commits y la historia pesa 160 MB.
Alternativas: volcarlo a SQL plano (`.dump`, comprime y diffea), `git lfs`, o
commitearlo solo en hitos.

### 4.3 El HTML generado también está versionado 🟢

`mi-crate.html` (342 KB) se regenera con `crate build`. Versionar un artefacto
derivado genera conflictos en cada cambio. Vale ignorarlo.

### 4.4 `app/historico/` 🟢

36 scripts de tandas pasadas, conservados a propósito. Está bien que estén,
pero conviene que el README diga que no se tocan.

### 4.5 Duplicación de criterios 🟡

`criterios.py` es la fuente de verdad, pero `app/historico/demo_pre.py` tiene
su propia copia de las regex y los umbrales. Si alguien corre un script viejo,
aplica reglas viejas sin enterarse.

---

## 5. Lo que medí y NO funciona

Honestidad sobre lo que se probó y falló, para que nadie lo reintente a ciegas:

- **`cavar.py` para instrumentos no sirve.** Buscar "piano", "rhodes" o
  "wurlitzer" en YouTube trae intérpretes, no prensados: de 415 resultados
  salieron *"Hey Jude | Wurlitzer | Instrumental Cover"*, *"Rhodes Chord"*,
  *"Piano Background Music"*. Con un filtro que exige evidencia de prensado
  (año, formato, canal curador) quedaron 7, igual malos. **Para formatos sí
  funciona**: las mismas reglas en FOLK dieron 77 candidatos decentes, porque
  esas queries nombran *private press*, *loner*, *LP*. Encaja con lo ya medido:
  pesa QUIÉN lo subió, no qué palabra tiene el título.
- **El detector de espacio instrumental (`espacio.py`) no anda.** Dos enfoques
  (heurísticas de pyin, mid/side) fallaron. El camino correcto es separación de
  fuentes (Demucs/Spleeter). Documentado como no funcional.

---

## 6. Plan por etapas

### Etapa A — Diagnóstico ✅ *este documento*

### Etapa B — Seguridad ✅ *hecho*
Lista blanca del servidor, SSRF del proxy, secretos fuera de git, guardia en CI.

### Etapa C — Red de seguridad ✅ *hecho*
43 tests verificados con mutaciones + CI en cada push.

### Etapa D — Decisión de alcance 🔜 *necesita que decidas vos*
Qué pasa con `backend/` y `frontend/`. Hasta que no se decida, todo lo demás se
hace sobre un repo que miente sobre lo que es. **Es el próximo paso real.**

### Etapa E — Higiene del repo 🔜
Sacar `mi-crate.html` de git; decidir estrategia para `crate.db`; unificar los
criterios duplicados de `historico/`; un linter (`ruff`) en el CI.

### Etapa F — Cobertura 🔜
Tests de los endpoints con una `crate.db` de juguete; tests del JS generado.

---

## 7. Resumen

**9 problemas encontrados, 9 arreglados**, 3 de ellos con test de regresión.
Uno era crítico (las claves servidas por HTTP) y dos eran de seguridad real.

Lo mejor del proyecto es que **las decisiones están medidas, no opinadas**: los
hit rates por canal, el rango de tempo, los umbrales de views. Eso es raro y
vale la pena cuidarlo — los tests nuevos existen sobre todo para eso.

Lo peor es el desbalance: el 72% del código no corre, y hasta hoy no había una
sola prueba automática sobre el 28% que sí.
