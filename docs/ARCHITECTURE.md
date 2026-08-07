# Arquitectura

## Vista general

```
┌─────────────────────────── FRONTEND (browser, React PWA) ───────────────────────────┐
│                                                                                      │
│  UI  ──►  pipeline: discover → normalize → enrich → score  ──►  ResultCard + Why this?│
│           │            │           │          │                                       │
│           │            │           │          └─ core/score.ts + core/affinity.ts     │
│           │            │           └─ core/fuzzy.ts + sources/discogs,musicbrainz      │
│           │            └─ core/entities.ts (Source Item → Candidate → Entity)          │
│           └─ sources/youtube.ts, archive.ts   (Capa 1: metadata-first, instantáneo)    │
│                                                                                      │
│  db/crateIndex.ts  ── IndexedDB (Dexie): seen / saved / analyzed / rejected + affinity │
│                                                                                      │
└───────────────┬──────────────────────────────────────────────┬──────────────────────┘
                │ (solo cuando CORS bloquea o hay scraping)      │ (solo botón "Analizar audio")
                ▼                                                ▼
        ┌───────────────────────── BACKEND (FastAPI, liviano) ─────────────────────────┐
        │  /api/proxy   relay con allowlist (Discogs, MusicBrainz, Archive, Bandcamp)   │
        │  /api/analyze  yt-dlp baja fragmento → Librosa/Essentia → BPM/key/mood/instr  │
        └──────────────────────────────────────────────────────────────────────────────┘
```

## Dónde corre cada cosa

| Cosa | Dónde | Por qué |
|---|---|---|
| Discovery, normalización, enrichment, scoring | **Cliente (TS)** | Metadata-first; instantáneo; sin server |
| Crate-index (seen/saved/analyzed/rejected + affinity) | **Cliente (IndexedDB/Dexie)** | Miles de registros, async, privado, sin DB paga |
| Llamadas que CORS bloquea + scraping | **Backend proxy** | El navegador no las deja hacer |
| Análisis de audio (DSP) | **Backend worker** | No se puede extraer audio de YouTube en el cliente |

> El backend es **fino**: proxy + DSP. El cerebro (entidades, score, affinity) vive en el cliente.

## El pipeline (Capa 1)

`frontend/src/pipeline/index.ts` orquesta:

1. **discover(query, filters, sources)** → junta `SourceItem[]` de YouTube + Archive.
2. **normalize(items)** → `Candidate[]` (parseo de título/tags, limpieza de ruido).
3. **enrich(candidates)** → cruza con Discogs + MusicBrainz (fuzzy match) → `EnrichedTrack[]`
   con provenance; saca credits (instrumentos), año, sello, rarity (want/have).
4. **score(tracks, query, affinity)** → CRATE Score + `reasons` (Why this?).
5. **filtrar `Seen`** → no mostrar lo ya visto (feature clave). Ordenar por score.

## Capa 2 (opt-in): "Analizar audio"

1. UI dispara `POST /api/analyze { url, startSec?, seconds }`.
2. Backend: `yt-dlp` baja `CRATE_ANALYZE_SECONDS` de audio a `tmp/`.
3. Librosa → `tempo` (BPM) + estimación de key (chroma). [Essentia opcional → mood/instrumentos.]
4. Devuelve `{ bpm, key, mood?, instruments?, confidence:{...} }` con provenance `audio_analysis`.
5. Frontend fusiona en el `EnrichedTrack`, marca estado `analyzed`, persiste en Dexie.
6. Backend borra el fragmento temporal.

## PWA

`vite-plugin-pwa` + `public/manifest.webmanifest`. Instalable en desktop y mobile; funciona
"de donde sea". El crate-index es local al dispositivo (por ahora; sync multiusuario = futuro).

## Seguridad / privacidad

- Keys del usuario: las de front van en `.env` (VITE_*) y quedan en su build local; el proxy
  agrega throttling y allowlist para no exponer un proxy abierto.
- El proxy **nunca** es open relay: solo hosts en `CRATE_PROXY_ALLOWLIST`.
- El análisis baja fragmentos temporales y los borra; no redistribuye audio.
