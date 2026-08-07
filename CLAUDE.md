# CRATE — Contexto para Claude

> Este archivo lo lee Claude Code automáticamente al abrir el proyecto. Es el
> onboarding: leélo entero antes de tocar nada. El detalle de cada tema vive en
> `docs/`. Los agentes especializados viven en `.claude/agents/`.

---

## Qué es CRATE (en una línea)

**Un buscador de crate-digging que construye tu propio índice mientras buscás.**

Rastrea la web abierta —discos reales de otra gente, no sample packs— para tirarte
**joyas ocultas** que probablemente no hubieras encontrado buscando normalmente,
filtrables por key, BPM, mood e instrumentos.

Lema de trabajo: **"The internet is the crate. Dig deeper. Find what nobody else found."**

El usuario (Thomas) es beatmaker de hiphop: boombap clásico → drumless moderno,
estética Griselda / Roc Marciano, mucho soul, jazz fusion, city pop, MPB, quiet
storm, library music, piano, 80s. CRATE está hecho para *ese* oído.

---

## La obsesión del producto (leé esto dos veces)

El mayor riesgo de CRATE **no es técnico, es la calidad de resultados.**

Podés tener la arquitectura más linda del mundo y que el usuario busque
`70s soul 75-90 BPM Rhodes` y reciba 500 temas genéricos que ya escuchó 40 veces.
Ahí muere el producto.

Toda decisión de discovery y scoring se mide contra **una** pregunta:

> **"¿Encontré algo que probablemente no hubiera encontrado buscando normal?"**

Si CRATE logra eso → hay producto. Si solo junta metadata de YouTube + Discogs →
es un buscador lindo y nada más.

---

## Qué NO es (límites duros)

- **No** es un agregador de sample packs. Nada de Splice, Tracklib, Loopcloud, Loopmasters.
- **No** descarga ni "captura" audio para el usuario. El flujo es **descubrir + preview**;
  el usuario salta a la fuente y consigue el audio por su cuenta.
- **No** es multiusuario todavía. Es una herramienta **personal** (usa las API keys del
  usuario). Pero la arquitectura se diseña para poder abrirlo a otros beatmakers a futuro.
- **No** trata a YouTube como su base de datos. YouTube es **fuente de descubrimiento**;
  CRATE es dueño de la **entidad musical normalizada** (ver Entity Model).

---

## Principio rector: dos capas (el backend es el último recurso)

- **Capa 1 — en el browser (instantáneo, metadata-first).** Meta-search + text-mining +
  cruce contra Discogs/MusicBrainz. De acá sale casi todo: año, género, estilo, mood,
  rareza, **instrumentos (vía créditos de Discogs)** y BPM/key **si vienen taggeados** en
  el título/tags.
- **Capa 2 — opt-in, último recurso (DSP en backend).** El botón **"Analizar audio"** manda
  UN solo track a analizar (yt-dlp baja un fragmento → Librosa/Essentia calcula BPM/key/
  mood/instrumentos con confidence). Nada pesado corre sin que el usuario lo dispare.

> Nota real: aunque la filosofía es "todo en el browser", **igual necesitamos un backend
> liviano** (FastAPI) desde el Tier 0 por dos razones: **CORS** (algunas fuentes y todo lo
> que sea scraping se bloquean desde el navegador) y la **extracción de audio de YouTube**
> (no se puede en el cliente). El backend es un proxy fino + worker de DSP, no el cerebro.

---

## Cuatro decisiones de arquitectura que NO se negocian (vienen de la revisión)

1. **Entity model:** `Source Item → Candidate → Music Entity (Recording / Release / Track) → Enriched`.
   CRATE posee la entidad canónica normalizada. Ver `docs/ENTITY_MODEL.md`.
2. **Provenance por dato:** cada dato tiene `{ value, source, method, confidence, updatedAt }`.
   Nunca mezclamos "metadata confirmada" con "metadata inferida/analizada". Se muestra
   siempre de dónde salió (`84 BPM · del título` vs `86 BPM · analizado` vs `soulful · inferido`).
   Ver `docs/ENTITY_MODEL.md` y `frontend/src/core/provenance.ts`.
3. **Estados Seen / Saved / Analyzed / Rejected.** El índice principal = `Saved + Analyzed`.
   `Seen` es historial/cache. **Feature clave de F1: "no me muestres lo que ya vi".**
4. **CRATE Score formal + "Why this?".** El score es explicable, nunca un numerito mágico.
   Ver `docs/CRATE_SCORE.md`.

---

## CRATE Score (el corazón del producto)

No es "rareza + pocas views". Es un intento de responder *"¿qué tan probable es que esto
sea una joya que todavía no encontraste?"*. Componentes:

```
CRATE SCORE
├── filter match          ¿pega con lo que pediste?
├── rarity               ¿qué tan rara es la OBRA (catálogo/prensado)? → Discogs want/have
├── obscurity            ¿qué tan difícil es ENCONTRARLA? → views, recomendación, titulado
├── metadata richness    ¿tenemos con qué trabajarla? (credits, año, sello)
├── source quality       ¿la fuente es confiable / buen rip?
├── historical relevance ¿sweet spot de época/escena?
└── personal affinity    ¿pega con TU crate (lo que venís guardando)?
```

**Rarity ≠ Obscurity ≠ Discovery value** — son tres cosas distintas, no las colapses.
Una canción con 200 views puede ser una joya rarísima o una mierda mal titulada.
Detalle y fórmula: `docs/CRATE_SCORE.md`. Implementación: `frontend/src/core/score.ts`.

Cada resultado muestra un **"Why this?"** con los motivos concretos:

```
🔥 Hidden Gem — 91
1974 · Brazilian MPB · 82 BPM · F# minor
Rhodes · flute · strings
Why this?
 • sweet spot 1972–1978
 • 92% match con tus discos de soul guardados
 • solo 1.8k views en YouTube
 • 23 wants / 1,240 haves en Discogs
```

---

## Taxonomía de mood (chica y a propósito)

Nada de campos libres tipo "happy/sad/chill". Taxonomía cerrada, útil para un beatmaker:

- **Energy:** 1 ─ 5
- **Feel:** laid-back · groovy · dreamy · dark · melancholic · uplifting · warm · tense
- **Texture:** dusty · clean · lush · raw · lo-fi · psychedelic · organic

Combinás: `dusty + melancholic + laid-back`. Ver `docs/TAXONOMY.md` y `frontend/src/core/taxonomy.ts`.
El modelo de filtros se diseña pensando en **búsqueda en lenguaje natural a futuro**
("soul brasileño de los 70, lento, con Rhodes y medio melancólico" → filtros), aunque eso NO va en F1.

---

## Stack técnico (ya decidido)

**Frontend** — `frontend/` · React 18 + Vite + TypeScript, PWA.
- Estado async / cache de queries: **TanStack Query**. Estado local: **Zustand**.
- **Crate-index local: IndexedDB vía Dexie.js** (miles de registros estructurados, async, sin server). NO LocalStorage.
- Estilos: **Tailwind** + design tokens propios (paleta/tipografías CRATE).
- El **core de dominio corre en el cliente** (entities, scoring, taxonomy, fuzzy, affinity) → metadata-first.

**Backend** — `backend/` · Python + **FastAPI**.
- Proxy fino con allowlist (resuelve CORS y scraping). `app/proxy.py`.
- Worker de DSP: **yt-dlp** (baja fragmento) + **Librosa** (BPM/key) [+ Essentia opcional para mood/instrumentos]. `app/dsp.py`, `app/analyze.py`.
- Devuelve resultados con **confidence** y provenance `audio_analysis`.

**Fuzzy matching:** `frontend/src/core/fuzzy.ts` — normaliza títulos falopa de YouTube
(`T. Yamashita ~ Sparkle (1982) [Vinyl Rip] HQ`) y hace match tolerante contra Discogs
(Levenshtein + limpieza de ruido). Es CRÍTICO para que el cruce no se rompa.

---

## Mapa del repo

```
crate_project/
├── CLAUDE.md              ← este archivo
├── README.md             ← quickstart
├── docs/                 ← toda la spec y el diseño (leer para el detalle)
│   ├── SPEC.md           ← spec de producto (v0.2, con todo integrado)
│   ├── ENTITY_MODEL.md   ← Source Item → Recording → Release → Track + provenance
│   ├── CRATE_SCORE.md    ← el score explicable + Why this?
│   ├── TAXONOMY.md       ← mood/feel/texture/energy + instrumentos + géneros
│   ├── SOURCES.md        ← mapa de fuentes, quotas, CORS, gotchas, fase
│   ├── ARCHITECTURE.md   ← data flow, dónde corre cada cosa, IndexedDB, DSP
│   └── ROADMAP.md        ← F1 / F2 / F3
├── .claude/agents/       ← 5 subagentes especializados (ver abajo)
├── frontend/             ← React + Vite + TS (PWA)
│   └── src/
│       ├── core/         ← dominio (entities, provenance, taxonomy, score, fuzzy, affinity)
│       ├── sources/      ← clients por fuente (youtube, discogs, musicbrainz, archive)
│       ├── pipeline/     ← discover → normalize → enrich → score
│       ├── db/           ← Dexie crate-index (seen/saved/analyzed/rejected)
│       ├── state/        ← stores Zustand
│       ├── api/          ← cliente del backend (analyze, proxy)
│       └── ui/           ← componentes (ResultCard, AnalyzePanel, FilterBar, ...)
└── backend/              ← FastAPI (proxy + DSP)
    └── app/              ← main, config, models, proxy, analyze, dsp
```

---

## Cómo correrlo

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

**Backend**
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8787
```

Copiá `.env.example` → `.env` y completá las keys (YouTube Data API, Discogs token).
En dev, Vite proxea `/api` → `http://localhost:8787` (ver `vite.config.ts`).

> Estado actual: **F1 corriendo, sin validar con datos reales.** El core de dominio, el
> pipeline completo (discover → normalize → enrich → score), los clients de fuentes, el
> crate-index y la UI están escritos y compilan. El enrichment está throttleado por fuente
> y cacheado en IndexedDB. Falta lo que necesita las API keys puestas: correr los casos de
> prueba y calibrar. Buscá `// TODO(F1)` en el código para lo que queda.
>
> Lo próximo, en orden: (1) fan-out de queries de descubrimiento — hoy `buildQuery` en
> `sources/youtube.ts` solo concatena strings y es donde vive o muere el producto;
> (2) render progresivo de resultados, porque el enrichment serializado hace que una
> búsqueda en frío tarde ~40s con un spinner y nada más; (3) calibrar los pesos del score
> contra los casos de prueba.

---

## Los 5 agentes (`.claude/agents/`)

- **crate-scout** — inteligencia de digging: arma queries astutas por escena/época/sello
  para sacar joyas ocultas, y define los casos de prueba. Sabe de la estética (boombap,
  soul, city pop, MPB, quiet storm, library).
- **source-integrator** — implementa/mantiene los clients de fuentes, CORS/proxy, manejo de
  quota y el fuzzy matching / normalización de entidades.
- **dsp-analyst** — dueño del path de "Analizar audio": yt-dlp + Librosa/Essentia,
  detección de BPM/key/mood/instrumentos con confidence.
- **score-tuner** — dueño del CRATE Score, la separación rarity/obscurity/discovery,
  la affinity personal, el "Why this?" y la validación contra los casos de prueba.
- **digger-ux** — dueño de la PWA React, la estética (vinilo japonés 70s), el ResultCard
  con score + Why this?, el AnalyzePanel con confidence, y los flujos seen/saved/analyzed/rejected.

---

## Convenciones para trabajar acá

- **Metadata-first:** antes de mandar algo al backend, exprimí todo lo que se pueda sacar de
  texto y catálogos. El DSP es opt-in y último recurso.
- **Provenance siempre:** ningún dato entra al índice sin `source + method + confidence`.
  No inventes valores "seguros".
- **CRATE es dueño de la entidad:** las fuentes se normalizan hacia la entidad canónica; no
  ates la lógica a la forma de una fuente puntual.
- **Nada de guardar basura:** `Seen` es cache; solo `Saved`/`Analyzed` forman el crate real.
- **El score es explicable:** si agregás una señal al score, agregá su razón al "Why this?".
- Escribí TypeScript tipado (nada de `any` gratis) y comentarios en el idioma del código vecino.

## Casos de prueba (validación de F1)

Si con estas queries CRATE trae joyas con **menos de ~1000 views** y buen cruce Discogs, el motor anda:
- `80s quiet storm`
- `japanese city pop 1982`
- `70s brazilian MPB rhodes melancholic`
- `soul jazz rhodes 75-90 bpm minor`
- `library music cinematic strings 1974`

Detalle de nombre y branding: quedó **CRATE**. Mundo visual: crates, etiquetas, fichas,
stickers, sellos, timestamps, polvo, vinilos japoneses 70s (texturas vintage, tonos cálidos
desvanecidos, grano cinematográfico). Ver `docs/SPEC.md`.
