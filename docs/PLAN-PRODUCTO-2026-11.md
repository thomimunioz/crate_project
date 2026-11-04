# De herramienta personal a producto — plan técnico y de diseño

**4 noviembre 2026.** Thomas: *"Tenemos que empezar a pensar en esto como una
aplicación para gente. Mismo la UI, está bastante genérica y bastante IA."*

Este documento es el diagnóstico medido, no una lista de buenas intenciones.
Cada número de acá salió de correr algo, no de estimarlo.

---

## 1. Dónde estamos, con números

### Lo que funciona y es raro que funcione

| | |
|---|---|
| Temas en el índice | 52.000+ |
| Hit rate medido | 60% (176 guardados / 117 rechazados) |
| Tests de Python | 65 |
| Barridos de interfaz | 10, con navegador real |
| Vetas | 19 escenas, 560 combinaciones generables |

**El activo diferencial no es el código: son los datos medidos.** El hit rate
por canal (Krem Soulz 70%, DJ Vinyl Goblin 15%), el rango de tempo, los
umbrales de views. Eso no lo tiene ningún competidor y no se copia: se mide
escuchando.

### La deuda, medida

```
app_js.py          1.203 líneas
app_loop.py          552
app_css.py           559
crate_server.py      698
app_tinder.py        228
```

**~2.000 líneas de JavaScript viven dentro de strings de Python.**

Eso significa, concretamente:
- sin autocompletado ni "ir a la definición"
- sin linter de JS: un `const` duplicado se descubre en el navegador
- sin tipos
- un cambio de CSS obliga a regenerar un HTML de 412 KB
- los editores lo ven como texto plano

No es un problema estético. Los bugs de esta semana —`SPOTS` antes de
inicializar, el `forzar` que quedó dentro del reloj, el HTML del sampler
congelado en el build— **los habría cazado un linter de JS en el acto.**

### Lo que ya se arregló hoy

Instalé `ruff` por primera vez. **766 avisos.** De esos, 760 eran
preferencias de estilo y **6 eran problemas reales**. Uno era un bug que
estaba corriendo:

> `ESCENAS` tenía la clave `"latam"` **dos veces**. La segunda pisaba a la
> primera en silencio, así que cuatro queries de latam nunca se cavaron.
> Ahora son nueve.

Configuré ruff con criterio (`pyproject.toml`): **solo reglas que cazan
errores**, no peleas de estilo. Encender 766 avisos es la forma más rápida de
que nadie vuelva a mirar el linter. Quedó en **13 → 0**, incluidos dos
`shell=True` que eran un riesgo real.

---

## 2. Orden del código

### 2.1 Sacar el JavaScript de los strings de Python — *lo más importante*

**Hoy:** `app_js.py` contiene JS como texto.
**Propuesta:** archivos `.js` de verdad, concatenados o empaquetados.

| Paso | Costo | Qué destraba |
|---|---|---|
| Mover el JS a `app/web/*.js` y que `app_build.py` los lea | 2-3 h | linter, autocompletado, tipos |
| Agregar **ESLint** + `eslint-plugin-unicorn` | 1 h | caza la familia de bugs de esta semana |
| **Vite** para empaquetar | 3-4 h | módulos reales, recarga en caliente |

**Recomendación:** hacer los dos primeros ya; Vite recién cuando haya más de
un desarrollador o la app crezca. Hoy sería ceremonia.

### 2.2 El servidor

`crate_server.py` tiene 698 líneas con todo mezclado: rutas, SQL, llamadas a
yt-dlp, proxy de audio, slskd. Funciona, pero cada endpoint nuevo lo engorda.

**Si esto va a tener usuarios**, el camino es FastAPI (que ya está en el
repo, dormido) con esta estructura — la que recomiendan los guías de 2026
para apps chicas, sin sobre-arquitecturar:

```
app/
  main.py          create_app(), monta los routers
  rutas/           un archivo por área (crate, hotlist, audio, slsk)
  servicios/       la lógica: puntuar, cavar, identificar
  datos/           acceso a SQLite (hoy SQL suelto por todos lados)
  esquemas/        Pydantic: valida entrada y salida
```

**Por qué Pydantic importa acá y no es ceremonia:** hoy `/api/sweet` acepta
cualquier JSON y valida a mano. Con Pydantic, un `desde` negativo o un `id`
de 300 caracteres se rechaza antes de tocar la base.

**No hacerlo todavía.** Mientras sea para vos, 698 líneas que andan valen más
que una refactorización de dos días. El disparador concreto: **cuando haya un
segundo usuario**.

### 2.3 Herramientas, ya instaladas o recomendadas

| Herramienta | Estado | Para qué |
|---|---|---|
| **ruff** | ✅ instalado y configurado | linter + formateador, reemplaza flake8/black/isort |
| **pytest** | ✅ 65 tests | |
| **playwright** | ✅ 10 barridos | lo único que caza los bugs de interfaz |
| **pre-commit** | ⬜ recomendado | correr ruff y pytest antes de cada commit |
| **mypy** | ⬜ opcional | tipos en Python; vale cuando haya servicios separados |
| **uv** | ⬜ recomendado | reemplazo de pip, 10-100× más rápido |

---

## 3. La UI — *"está bastante genérica y bastante IA"*

La crítica es justa y vale la pena desarmarla, porque "genérica" tiene causas
concretas.

### 3.1 Qué la hace parecer genérica

**a) Todo tiene el mismo peso visual.** Una fila del hotlist muestra: número,
tema, artista, botón slsk, canal, veta, género, razones, views, bpm, largo,
clasificar, estrellas, descartar. **Catorce elementos.** Cuando todo grita,
nada se escucha.

**b) No hay ritmo.** Las separaciones son casi todas de 4-9px. Un diseño con
intención usa una escala: 4, 8, 16, 32, 64. El salto entre niveles es lo que
crea jerarquía sin usar más color.

**c) La densidad es constante.** Una herramienta de digging tiene dos modos
—escanear muchos y concentrarse en uno— y la interfaz los trata igual.

**d) El color hace demasiado trabajo.** Ocho colores de género compiten entre
sí en la misma fila. El color debería marcar **una** cosa.

### 3.2 Principios para seguir, con criterio

Estos son los que aplican a *esta* app, no una lista genérica:

1. **Una sola cosa dominante por fila.** El tema. Todo lo demás es
   secundario y debe verse como secundario.
2. **El color se gana.** Reservarlo para lo que requiere acción o decisión:
   el género, las estrellas, el estado. El resto en grises de la paleta.
3. **Escala de espaciado de verdad** (4/8/16/32). Hoy hay valores sueltos
   entre 3 y 13px sin sistema.
4. **Escala tipográfica con saltos claros.** Si dos textos tienen tamaños
   parecidos, el ojo los lee como iguales. Mejor 3 tamaños bien separados
   que 6 parecidos.
5. **Revelar al pasar el mouse.** Los botones de acción (slsk, clasificar,
   descartar) solo cuando hacen falta. Ya se hace con algunos; falta
   sistematizarlo.
6. **Responsive de verdad.** Hoy la tabla asume escritorio ancho. Un digger
   escucha en el teléfono.

### 3.3 Referencias concretas, no "inspiración"

Buscando referencias reales de apps de música, lo que sirve:

- **Spotify web** usa un fondo oscuro escalonado (`#121212` base, `#181818`
  tarjetas, `#1f1f1f` interactivo) bajo la idea de *"content-first darkness"*:
  la interfaz se corre para que el contenido mande. **Aplicable**: tu paleta
  "for you" es clara, pero el mismo principio vale — el fondo debe
  desaparecer.
- **Apple Music** define una rampa tipográfica con saltos grandes (128/80/72).
  No para copiar los tamaños, sí el criterio: **saltos grandes, no graduales**.

⚠️ Varias de esas referencias son reconstrucciones de la comunidad, no
documentación oficial. Los valores hay que verificarlos con un medidor de
contraste — que es justo lo que ya hace `app_check.py`.

### 3.4 Plan de UI, por orden de impacto

| | Qué | Costo |
|---|---|---|
| 1 | **Escala de espaciado y tipografía** como tokens CSS | 2 h |
| 2 | **Bajar el ruido de la fila**: jerarquía real, acciones al hover | 3 h |
| 3 | **Responsive**: la tabla se vuelve tarjetas en pantalla angosta | 4 h |
| 4 | **Modo denso / modo foco** | 3 h |
| 5 | Extender `app_check.py` a tamaños y espaciados, no solo contraste | 2 h |

**Lo que NO recomiendo:** traer Tailwind o un framework de componentes. La
app son 2.000 líneas de JS sin build. Meter un framework agregaría más peso
del que resuelve. Los tokens CSS propios ya funcionan — hay que usarlos con
sistema.

---

## 4. Orquestar mejor a Claude Code

Thomas: *"repositorios que ayudan a orquestar mejor al LLM, que no de tantas
vueltas, que no haga tanto slop"*.

### 4.1 Lo que YA funciona en este proyecto

Vale decirlo porque es lo que más impacto tuvo:

- **`CLAUDE.md`** con el contexto real. Que diga "esto se toca en `app/`, no
  en `frontend/`" evitó horas.
- **Los barridos de interfaz.** Son el antídoto directo al slop: no puedo
  decir "listo" sin que 10 pruebas en navegador pasen.
- **Comentarios que explican el *por qué*.** Cuando el código dice "esto no
  puede ser un heredoc porque los `\b` llegan como chr(8)", no se repite el
  error.

### 4.2 Herramientas del ecosistema (2026)

| | Qué es | Veredicto |
|---|---|---|
| **GitHub Spec Kit** | CLI de especificaciones, ~93k estrellas, 30+ agentes | El estándar. Para equipos; acá sería ceremonia |
| **GSD** | Capa para Claude Code contra el *context rot* | Lo más alineado con el problema real |
| **Traycer** | Extensión de VS Code que agrega planificación y verificación | La verificación es el mecanismo anti-slop más directo |
| **claude_code_agent_farm** | Sesiones paralelas | Para barridos grandes, no para esto |

⚠️ **Advertencia honesta:** casi todas esas comparativas las publican los
propios vendedores. No encontré ninguna que *mida* reducción de slop. La
evidencia es cualitativa.

### 4.3 Mi recomendación, en orden

1. **`pre-commit` con ruff + pytest.** Imposible commitear algo roto. 30 min.
2. **Mantener `CLAUDE.md` al día.** Ya pagó más que cualquier herramienta.
3. **ESLint cuando el JS salga de los strings.** Caza la familia de bugs de
   esta semana automáticamente.
4. **GSD, si las sesiones largas siguen degradándose.** Probar, no adoptar.

**Lo que no recomiendo ahora:** adoptar un framework de especificaciones. El
cuello de botella no es la planificación: es que el JS no tiene linter.

---

## 5. Si esto va a tener usuarios

Lo que hoy es una herramienta personal y tendría que cambiar:

| | Hoy | Para usuarios |
|---|---|---|
| Base | SQLite local | Postgres |
| Gusto | `criterios.py` escrito a mano con el oído de Thomas | aprendido por usuario |
| Descubrimiento | yt-dlp en vivo | índice crawleado offline |
| Soulseek | **no sobrevive a ser público** | otra fuente de audio |
| Arranque | — | **onboarding tipo Tinder** (idea de Thomas, 4-nov) |

**El cold start es el único problema difícil.** Un usuario nuevo no tiene
canales medidos. La idea de Thomas —hacerle escuchar 10 temas y que puntúe—
es exactamente la solución correcta, y ya existe la maquinaria: el modo
sesión *es* eso.

---

## 6. Orden sugerido

**Ahora (horas):**
1. `pre-commit` con ruff y pytest
2. Sacar el JS a archivos `.js` + ESLint

**Pronto (días):**
3. Tokens de espaciado y tipografía; bajar el ruido de la fila
4. Responsive

**Cuando haya un segundo usuario:**
5. FastAPI con capas, Pydantic, Postgres
6. Onboarding y gusto por usuario

---

**Sources:**
[9 Best AI Tools for Spec-Driven Development in 2026](https://www.marktechpost.com/2026/05/08/9-best-ai-tools-for-spec-driven-development-in-2026-kiro-bmad-gsd-and-more-compare/) ·
[Best Claude Code multi-agent orchestrators in 2026](https://defract.dev/blog/best-claude-code-orchestrators-2026) ·
[awesome-claude-code](https://github.com/jqueryscript/awesome-claude-code) ·
[Production-Ready FastAPI Project Structure 2026](https://dev.to/datanestdigital/production-ready-fastapi-project-structure-2026-guide-b1g) ·
[FastAPI Architecture: Clean, Scalable](https://dev.to/naved_shaikh/fastapi-architecture-clean-scalable-self-documenting-22n8) ·
[Design System Inspired by Spotify](https://cdn.jsdelivr.net/npm/oh-my-opencode@4.18.2/dist/skills/frontend/references/design/spotify.md) ·
[Apple Music design reference](https://www.shadcn.io/design/apple-music/raw)
