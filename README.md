# CRATE 🎛️

**Un buscador de crate-digging que construye tu propio índice mientras buscás.**

CRATE rastrea la web abierta (discos reales de otra gente, no sample packs) para tirarte
**joyas ocultas** que probablemente no hubieras encontrado buscando normal — filtrables por
key, BPM, mood e instrumentos, con un score explicable de "joya".

> The internet is the crate. Dig deeper. Find what nobody else found.

Para beatmakers de hiphop: boombap, drumless, soul, jazz fusion, city pop, MPB, quiet storm, library.

---

## Estado (20-sep-2026)

**F1 funcionando y medido contra el oído real.** El pipeline entero corre (discover →
normalize → enrich → score) con render progresivo, vetas de canales y playlists ajenas (pegás
la URL y se cava entera por tandas), import de playlists propias, huella acústica opt-in y
análisis de audio (BPM/key) que anda de nuevo, con ÷2/×2 para corregir la octava. Hay un
benchmark congelado en `docs/benchmarks/2026-09-19-digging-a-mano/` (1.958 temas, 206
sugerencias, 109 guardadas) y harnesses que miden parseo, ranking y BPM contra él.

Números: 72% de las obras identificadas contra catálogo (pistas duras del snippet +
MusicBrainz + Discogs); ranking sobre el pool AUC 0.66
(antes 0.42); octava del BPM correcta 75% sin prior, 82% con el rango del usuario (58–115);
hit rate del digging a mano 53% (la vara que la app tiene que igualar sola).

Lo que falta de verdad: los datos de Thomas desde la app (importar sus playlists como Saved
con tag y guardar/rechazar/corregir ahí, para que el hit rate se mida solo), un snapshot de
`videos.list` de los 1.958 ids del benchmark, y el lote "analizar estos N guardados". Ver
`docs/ROADMAP.md`.

## Arranque rápido

```bash
# Frontend (React + Vite + TS, PWA)
cd frontend && npm install && npm run dev

# Backend (FastAPI: proxy CORS + discovery yt-dlp + DSP)
cd backend && python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8787
```

Copiá `.env.example` → `.env` y cargá tus keys (YouTube Data API v3, Discogs token).

**Requisitos del sistema para "Analizar audio"** (buscar y listar no los necesita):
- `yt-dlp >= 2026.08.19` + `yt-dlp-ejs` (los instala `requirements.txt`; si YouTube vuelve a
  dar 403, `pip install -U yt-dlp yt-dlp-ejs`).
- Un runtime JS: **node 22+** o **deno 2.3+**. Sin runtime, yt-dlp no resuelve el desafío de
  YouTube ("Requested format is not available").
- **ffmpeg** en el PATH (recorta la ventana a WAV). Opcional: **fpcalc** + key de AcoustID
  para `/identify`.

`curl localhost:8787/health` te dice qué encontró y qué falta, con el comando para arreglarlo.
Detalle en `backend/README.md`.

## Cómo está organizado

- `CLAUDE.md` — **empezá acá.** Contexto completo para trabajar el proyecto (lo lee Claude Code solo).
- `docs/` — spec, entity model, score, taxonomía, fuentes, arquitectura, roadmap, y
  `benchmarks/` con los datos reales contra los que se mide todo.
- `.claude/agents/` — 5 subagentes especializados (scout, source-integrator, dsp-analyst, score-tuner, digger-ux).
- `frontend/` — la PWA (+ `scripts/` con los harnesses). `backend/` — proxy + discovery con
  yt-dlp + worker de análisis de audio (+ `tools/` de calibración).

## Filosofía en 5 puntos

1. **Metadata-first:** casi todo se resuelve en el browser; el análisis de audio es opt-in.
2. **CRATE es dueño de la entidad** normalizada (Source Item → Recording → Release → Track). YouTube solo descubre.
3. **Cada dato tiene provenance + confidence.** No se mezcla confirmado con inferido.
4. **El score de "joya" es explicable** ("Why this?"), y separa rareza / obscuridad / valor de descubrimiento.
5. **El backend no es el cerebro:** devuelve evidencia; el gusto (affinity, prior de tempo) vive
   en el cliente y se mide contra lo que el usuario guarda de verdad.

## Licencia / uso

Herramienta personal. Respeta los ToS de cada fuente; el análisis de audio opt-in hace una
descarga temporal del track solo para calcular features (BPM/key/huella), la recorta, la borra
y nunca la sirve ni redistribuye audio.
