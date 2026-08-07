# Roadmap

## F1 — El núcleo (el 80% del valor)

**Objetivo:** que buscar `japanese city pop 1982` traiga joyas con < ~1000 views y buen cruce
Discogs, y que el usuario sienta que encontró algo que no hubiera encontrado normal.

Flujo mínimo:

```
Input (query + filtros + fuentes)
   → Discovery         YouTube + Internet Archive
   → Normalization     Artist / Recording / Release / Track  (fuzzy match)
   → Enrichment        Discogs + MusicBrainz + metadata de YouTube (provenance)
   → Scoring           filterMatch + rarity + obscurity + discovery value
   → Results           CRATE SCORE · Why this? · Sources · ▶ Preview · ♡ Save · 🧠 Analyze
   → Personal crate    Seen / Saved / Analyzed / Rejected   (IndexedDB)
```

**Ya hecho:**
- Entorno levantando: frontend, backend, ffmpeg, `.env` único en la raíz.
- Enrichment throttleado por fuente (`sources/throttle.ts`) y cacheado una semana en
  IndexedDB (`db/cache.ts`). Antes se comía 429/503 y perdía créditos y rareza.
- Vista del crate con filtro local, y sacar del crate revirtiendo la affinity.
- **Import de playlists propias de YouTube** como semilla: resuelve el arranque en frío
  de la affinity con curaduría deliberada en vez de clicks inferidos. Cuesta ~1 unidad
  de quota cada 50 temas.

**Sí o sí en F1:**
- Entity model + provenance + confidence.
- Seen / Saved / Analyzed / Rejected + **"no me muestres lo que ya vi"**.
- CRATE Score + **Why this?** (explicable).
- Botón "Analizar audio" (opt-in) con BPM/key + confidence.
- Fuzzy matching YouTube ↔ Discogs — de esto depende también la affinity: si el cruce
  falla, la entidad cae al fallback sin género ni sello y `learn()` casi no aprende nada.
- Fan-out de queries de descubrimiento (hoy `buildQuery` solo concatena strings).
- Render progresivo: mostrar resultados a medida que se enriquecen.
- Estética base (vinilo japonés 70s).

**Fuentes F1:** YouTube · Discogs · MusicBrainz · Internet Archive.

**NO en F1:** Spotify, Bandcamp, SoundCloud, Soulseek, web search, fingerprinting, ML sofisticado,
lenguaje natural, sync multiusuario. (Diseñar sin cerrarles la puerta, pero no construirlos.)

## F2 — Ampliar la red

- Spotify (solo referencia), búsqueda web general (Brave/SerpAPI), Bandcamp (scraping), Freesound opcional.
- Mejores modelos de mood/instrumentos por audio (Essentia).
- Affinity más fina; primeras sugerencias "creo que esto te puede interesar".
- Búsqueda en lenguaje natural (traducción query → filtros).

## F3 — Lo pesado

- Soulseek (P2P, backend dedicado), SoundCloud.
- Fingerprinting (AcoustID) para identificar rips y linkearlos al release real.
- Eventual multiusuario (auth, quotas por usuario, sync del crate).

## Principio de fases

Cada fase entrega algo **usable** antes de sumar complejidad. No agregar 25 features:
cerrar bien el núcleo, obsesionarse con la **calidad de resultados**, y recién ahí ampliar.
