# CRATE 🎛️

**Un buscador de crate-digging que construye tu propio índice mientras buscás.**

CRATE rastrea la web abierta (discos reales de otra gente, no sample packs) para tirarte
**joyas ocultas** que probablemente no hubieras encontrado buscando normal — filtrables por
key, BPM, mood e instrumentos, con un score explicable de "joya".

> The internet is the crate. Dig deeper. Find what nobody else found.

Para beatmakers de hiphop: boombap, drumless, soul, jazz fusion, city pop, MPB, quiet storm, library.

---

## Estado

**Scaffold de F1.** El dominio (entities, provenance, taxonomy, score, fuzzy, affinity, DB) tiene
lógica real de arranque; fuentes, pipeline, UI y DSP son skeletons tipados con `// TODO(F1)`.

## Arranque rápido

```bash
# Frontend (React + Vite + TS, PWA)
cd frontend && npm install && npm run dev

# Backend (FastAPI: proxy CORS + DSP)
cd backend && python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8787
```

Copiá `.env.example` → `.env` y cargá tus keys (YouTube Data API v3, Discogs token).

## Cómo está organizado

- `CLAUDE.md` — **empezá acá.** Contexto completo para trabajar el proyecto (lo lee Claude Code solo).
- `docs/` — spec, entity model, score, taxonomía, fuentes, arquitectura, roadmap.
- `.claude/agents/` — 5 subagentes especializados (scout, source-integrator, dsp-analyst, score-tuner, digger-ux).
- `frontend/` — la PWA. `backend/` — el proxy + worker de análisis de audio.

## Filosofía en 4 puntos

1. **Metadata-first:** casi todo se resuelve en el browser; el análisis de audio es opt-in.
2. **CRATE es dueño de la entidad** normalizada (Source Item → Recording → Release → Track). YouTube solo descubre.
3. **Cada dato tiene provenance + confidence.** No se mezcla confirmado con inferido.
4. **El score de "joya" es explicable** ("Why this?"), y separa rareza / obscuridad / valor de descubrimiento.

## Licencia / uso

Herramienta personal. Respeta los ToS de cada fuente; el análisis de audio opt-in baja
fragmentos temporales solo para features (BPM/key) y no redistribuye audio.
