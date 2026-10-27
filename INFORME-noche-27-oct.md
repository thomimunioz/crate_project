# Informe de la noche — 27 oct 2026

Buen día. Esto es lo que quedó hecho, lo que quedó pendiente y las dos cosas que
rompí y arreglé.

---

## Arrancá así

```
crate            ← levanta la app y abre el navegador
crate estado     ← qué hay en la base
crate ayuda      ← el resto de los comandos
```

Un solo comando, desde la raíz del proyecto. Antes eran ~20 scripts sueltos.

**Tenés 122 temas esperándote en el hotlist** (eran 49).

---

## HECHO

### 1. Los dos bugs que reportaste

- **El menú de clasificar chocaba con el footer.** Ahora mide el espacio antes
  de abrirse (contando los ~100px del reproductor) y se abre hacia arriba si no
  entra abajo.
- **Clasificabas un tema y no aparecía hasta recargar.** El servidor ahora
  devuelve la fila completa y la app la mete en la tabla en caliente. Sin F5.
  Probado agregar + deshacer, sin residuos.
  - El tema que te había desaparecido estaba guardado: *後藤悟 — Fly By The Night*
    (1983, JAZZ FUSION, 4★). Ya se ve.

### 2. Tu app ya no vive en una carpeta temporal  ← lo más importante

Todo el sistema (servidor, criterios, hotlist, build) estaba en
`C:\Users\thomi\AppData\Local\Temp\…`. Si Windows limpiaba ese temp, perdías
**todo menos `crate.db`**. Está mudado a `crate_project\app\`:

- 20 scripts vivos + 36 generadores viejos en `app/historico/` (nada se tiró)
- los pools y labels en `app/datos/` (19 MB, ignorado por git)
- verificado: build, chequeo de contraste y servidor corren desde ahí

### 3. Vetas flacas: PIANO y DARK

Escribí `app/veta.py`, que **mina los 50.365 temas sin tocar que ya tenías en la
base** en vez de salir a buscar afuera. Sumó 73 candidatos al hotlist
(23 PIANO · 25 DARK · 25 FOLK), cada uno con el motivo visible.

Dos falsos positivos que cacé y filtré:
- *Cynthia Rhodes* y *Ken Rhodes* entraban a PIANO. **Rhodes también es
  apellido.** Ahora las pistas de instrumento solo valen del lado del tema, no
  del lado de quien firma.
- *"MAXIMO SPODEK · PIANO LOVE SONGS"* y similares: canales de covers y música
  funcional. Filtro nuevo.
- DARK pedía solo tonalidad menor: media discografía soul está en menor y no
  tiene nada de oscura. Ahora exige menor **+ lento o sin voz**.

### 4. Auditoría (Etapa A) — dos agujeros reales, los dos cerrados

**El servidor servía todo el repo por HTTP.** `http://127.0.0.1:7777/.env`
entregaba tus 11 API keys a cualquier cosa corriendo en la máquina. Ahora hay
lista blanca: solo html/css/js/imágenes/fuentes. Verificado: `.env` y
`crate.db` devuelven 403, la app sigue funcionando.

**Rompí la búsqueda de Soulseek al mudar** y la arreglé: `slskd_key.txt` quedó
en `datos/` y el servidor la busca al lado suyo. Restaurada y cargando.

### 5. claude-code-router — NO lo instalé, a propósito

Verifiqué tu máquina: **no hay Ollama y no hay ninguna key de proveedor**
(DeepSeek, OpenRouter, Gemini, Groq). Todos los proveedores que soporta son de
pago por token, así que hacerlo funcionar costaba plata — justo lo que me
pediste evitar. Además solo aplica a sesiones nuevas lanzadas con `ccr code`,
no a la sesión en la que estaba trabajando.

Te dejé la config armada y lista en `app/router-opcional/` (ruteo barato por
defecto, caro solo para razonamiento, fallback entre proveedores). Con una key
son 3 pasos. El porqué completo está en el LEEME de esa carpeta.

---

## PENDIENTE

### Para mañana, me lo explicás vos
1. **FOLK y DARK** — lo dejé donde estaba, como pediste.

### Lo que medí y NO funciona (no lo toqué más)
2. **`app/cavar.py` sirve para FOLK, no para PIANO.** Buscar instrumentos en
   YouTube trae youtubers tocando, no discos: de 415 resultados salían *"Hey
   Jude | Wurlitzer | Instrumental Cover"*, *"Rhodes Chord"*, *"Away in a Manger
   on 1975 Rhodes"*. Le puse un filtro que exige evidencia de prensado (año,
   formato, o canal curador conocido) y aun así PIANO quedó en 7 candidatos
   malos. FOLK con las mismas reglas dio 77 decentes, porque esas queries nombran
   formatos (*private press*, *loner*, *LP*) en vez de instrumentos.
   **La conclusión encaja con lo que ya medimos: pesa QUIÉN lo subió.** El camino
   para PIANO es cavar canales de library/private press y filtrar por
   instrumento, no buscar "piano" en YouTube.

### Lo que quedó sin empezar
3. **Escanear tu carpeta de música** — me falta la ruta del disco.
4. **Bajar desde la app vía slskd** — la búsqueda anda, falta el botón de bajar.
5. **Git: 19 archivos sin trackear**, incluido todo `app/`. No commiteé nada
   porque no me diste autorización para tocar git. Recomiendo commitear `app/`
   (y dejar `crate.db` y los HTML fuera, o el repo se infla a 16 MB+).

### Sin tests, sin CI
6. El proyecto **no tiene un solo test** ni linter ni CI. Con ~5.600 líneas de
   Python vivas, el bug de los 50 regex rotos en silencio que tuvimos es
   exactamente lo que un test hubiera cazado. Propongo arrancar por lo barato:
   un test que verifique que ninguna regex de `criterios.py` tiene el carácter
   de retroceso, y otro que corra `descartar()` contra 20 títulos conocidos.

---

## Nota sobre el `backend/` y el `frontend/` del repo

Siguen ahí y no los toqué, pero **están dormidos desde el 20-sep**. Lo que usás
todos los días es `app/` + `crate.db` + `mi-crate.html`. En algún momento hay que
decidir si el React vuelve a la vida o si `app/` es CRATE de verdad. No es una
decisión mía.

---

Apagué la PC como pediste. Hasta mañana.
