# CRATE Score — el corazón del producto

El score intenta responder **una** pregunta, no "qué tan popular es":

> **"¿Qué tan probable es que esto sea una joya que todavía NO encontraste?"**

Implementación: [`frontend/src/core/score.ts`](../frontend/src/core/score.ts).

## No colapses estos tres conceptos

| Concepto | Pregunta | Señales |
|---|---|---|
| **Rarity** | ¿Qué tan rara es la *obra* (catálogo/prensado)? | Discogs `want/have`, reissues, ediciones |
| **Obscurity** | ¿Qué tan difícil es *encontrarla*? | views YouTube, antigüedad del upload, si está mal titulada, recomendación |
| **Discovery value** | ¿Qué tan *interesante* es descubrirla? | riqueza de metadata + match con tu oído + relevancia histórica |

"Pocas views" **no** es rareza. Un tema con 200 views puede ser una joya rarísima o una
mierda que nadie buscó. Un tema con 40k views puede ser una joya súper sampleable. Por eso
`obscurity` pondera **por qué** tiene pocas views (upload nuevo vs. realmente escondido).

## Componentes del score

```
CRATE SCORE (0–100)
├── filterMatch          ¿pega con género/bpm/key/instrumento/época pedidos?
├── rarity               want/have de Discogs (normalizado, con piso de datos)
├── obscurity            bajo alcance real (views ajustadas por edad del upload)
├── metadataRichness     ¿tenemos credits, año, sello, estilo? (más data = más trabajable)
├── sourceQuality        ¿buen rip? ¿fuente confiable? ¿duración razonable (no un mix de 1h)?
├── historicalRelevance  sweet spots de época/escena para la estética del usuario
└── personalAffinity     match con lo que el usuario viene guardando (ver affinity.ts)
```

Cada componente devuelve `0..1`. El total es una **suma ponderada** con pesos ajustables
(ver `DEFAULT_WEIGHTS` en `score.ts`). Los pesos se tunean con los casos de prueba —
ese trabajo es del agente **score-tuner**.

## Heurística de arranque (simple, mientras tuneamos)

Como semilla de `rarity × obscurity`, la fórmula de Gemini funciona sorprendentemente bien:

```
gemScore ≈ (discogsWant / max(discogsHave, 1)) / log10(max(youtubeViews, 10))
```

Ej: 1000 wants, 10 haves (rarísimo) y 300 views → el score explota y sube arriba de todo.
Pero es solo una señal dentro del modelo completo, **no** el score final.

## "Why this?" — el score es explicable

Nunca mostramos un número mágico solo. Cada resultado explica sus motivos (los `reasons`
que arma `computeCrateScore`):

```
🔥 Hidden Gem — 91
1974 · Brazilian MPB · 82 BPM · F# minor · Rhodes · flute · strings
Why this?
 • sweet spot 1972–1978
 • 92% match con tus discos de soul guardados
 • solo 1.8k views en YouTube
 • 23 wants / 1,240 haves en Discogs (rareza alta)
 • Rhodes + strings (instrumentos que buscás seguido)
```

Regla de oro: **si agregás una señal al score, agregá su razón al "Why this?".**

## Cómo se valida

Contra los casos de prueba de `CLAUDE.md`. El motor "anda" si para `japanese city pop 1982`
o `80s quiet storm` trae joyas con < ~1000 views y buen cruce Discogs, y el usuario siente
que **encontró algo que no hubiera encontrado buscando normal**.
