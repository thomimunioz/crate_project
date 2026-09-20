# CRATE Score — el corazón del producto

El score intenta responder **una** pregunta, no "qué tan popular es":

> **"¿Qué tan probable es que esto sea una joya que todavía NO encontraste?"**

Implementación: [`frontend/src/core/score.ts`](../frontend/src/core/score.ts).
Vara de medición: [`frontend/scripts/scoreBench.ts`](../frontend/scripts/scoreBench.ts)
sobre [`docs/benchmarks/2026-09-19-digging-a-mano/`](benchmarks/2026-09-19-digging-a-mano/README.md).

## No colapses estos tres conceptos

| Concepto | Pregunta | Señales |
|---|---|---|
| **Rarity** | ¿Qué tan rara es la *obra* (catálogo/prensado)? | Discogs `want/have`, reissues, ediciones |
| **Obscurity** | ¿Qué tan difícil es *encontrarla*? | views YouTube (castiga mainstream), nombres sobreexpuestos de la escena, antigüedad del upload |
| **Discovery value** | ¿Qué tan *interesante* es descubrirla? | riqueza de metadata + match con tu oído + época de la escena |

"Pocas views" **no** es rareza, y —medido— tampoco es señal de joya: en un pool curado
por otro digger, lo que tiene menos de 1.000 views es OST, karaoke y mal titulado (2% de
guardado), y lo que Thomas guarda tiene mediana **25k views**. Por eso `obscurity` ya no
premia las pocas views: **castiga lo mainstream** (meseta hasta 100k, acantilado después de
300k, cero en 10M) y solo afirma "escondido de verdad" sobre una obra identificada. Un canal
curador tampoco es obscuridad: dice de la FUENTE y va en `sourceQuality`.

## Componentes del score

```
CRATE SCORE (0–100)
├── filterMatch          ¿pega con género/bpm/key/instrumento/época pedidos? (BPM tolera la octava)
├── rarity               want/have de Discogs (normalizado, con piso de datos)
├── obscurity            castiga mainstream (views) y nombres obvios de la escena
├── metadataRichness     ¿tenemos credits, año, sello, estilo? (más data = más trabajable)
├── sourceQuality        ¿buen rip? duración de tema (3–7 min), curador (canal del que ya guardaste)
├── historicalRelevance  época de la ESCENA del plan; sin plan, tu década; sin crate, sweet spots
└── personalAffinity     match con lo que venís guardando (ver affinity.ts); ruido personal resta
```

Cada componente devuelve `0..1`. El total es una **suma ponderada** (`DEFAULT_WEIGHTS`)
multiplicada por la **certeza** (0.55..1 según cuánto se identificó la obra: no se afirma
con la misma fuerza lo que no se sabe qué es).

```ts
computeCrateScore(track, query, affinity, weights?, ctx?)
// ctx.escenas: SceneId[]  → época e "obvios" de la escena (lo cablea el plan de digging)
// ctx.origen: 'veta' | 'busqueda' → en una veta (pool ya curado) la obscuridad pesa la mitad
```

### Pesos (calibrados el 20-sep-2026)

| componente | peso | por qué |
|---|---|---|
| filterMatch | 0.20 | lo que pediste manda, pero sin filtros da 0.6 neutro |
| rarity | 0.18 | en búsqueda real el 68% trae want/have; en el benchmark no hay catálogo, no se pudo medir |
| obscurity | 0.10 (0.05 en veta) | separa poco adentro de un pool curado; sí separa en búsqueda cruda |
| metadataRichness | 0.06 | |
| sourceQuality | 0.22 | lo que más discrimina sin catálogo: curador + duración (ojo: parte de `CANALES` se sembró desde este benchmark; el número honesto es el de la variante "sin sembrados", abajo) |
| historicalRelevance | 0.06 | la época de la escena; en el benchmark el año está sesgado (solo verificados) |
| personalAffinity | 0.18 | artista, género, sello, país, tempo |

## Affinity: qué aprende y de qué

Regla: **por dato, según su provenance** (no por track).

| dato | se aprende cuando |
|---|---|
| canal (`channels`) | siempre: es un hecho de la fuente |
| tags (colección) | siempre |
| BPM (`bpmBuckets`) | solo si salió del audio (`analyzed`/`inferred` de `audio_analysis`) o lo corrigió el usuario (`user/manual`). Si la ficha ya está en el crate y el BPM cambia (re-análisis, ÷2/×2), `learnBpmOnly` descuenta el bucket viejo y suma el nuevo: así el prior de tempo también puede *crecer*, no solo achicarse |
| década (`eras`) | solo con pista dura: ℗ del Topic, link a Discogs, huella |
| artista | confirmado o con pista dura |
| sello | de un disco fuerte (abajo), o del ℗ del Topic cuando no hay disco de Discogs |
| géneros, estilos, país, feels/texturas | **solo de un disco de Discogs que matcheó fuerte**: link directo, o `entity.catalogMatch` ≥ 0.85. `confirmed` solo no alcanza: un Topic confirma la OBRA por el ℗, pero el disco de donde salen los géneros pudo elegirse con 0.62 de similitud ("Rainy Day" → Reggae/Ska). Sin `catalogMatch` (pipeline viejo) vale lo confirmado salvo el Topic |

Lo negativo: un canal con rol `ruido` en `core/canales.ts`, un título de OST de juego/anime
o vaporwave, o un canal del que ya rechazaste 2+ → affinity 0.1 con razón. Es gusto de
ESTE usuario, no basura universal (eso vive en `esBasura`).

**Artista repetido:** suma (1 guardado → 0.33, 3 → 1.0) y el Why this lo dice ("ya guardaste
3 de X: mismo artista, no un hallazgo"). Se probó restarlo y el ranking empeoró: Thomas guardó
el 71% de lo sugerido de artistas que ya tenía contra 47% de artistas nuevos. Se revisa
cuando haya más de un día de historia.

## Tempo: la octava y el prior del oído

El DSP se equivoca hacia arriba: de 120 temas con BPM crudo > 115, 95 eran el doble. El
backend devuelve **evidencia** (candidatos ×0.5/×1/×2 con support, `ambiguous`); el prior
**personal** vive en el cliente: `tasteTempoRange(affinity)` (p5–p95 de `bpmBuckets` con
30+ temas; default 58–115) y `tempo.ts::foldBpm` elige la octava. El valor plegado se guarda
como `inferred` con razón; el crudo viaja también en la ficha (`bpmRaw`) para que el Why
this diga **"76 BPM · analizado 152, plegado a tu rango"** y el usuario pueda juzgar el
pliegue; las alternativas y la ventana quedan en la tabla `analyses`. Medido: crudo acierta
59.5%, plegado **92.3%** (228/247).

## "Why this?" — el score es explicable, también cuando baja

Nunca mostramos un número mágico solo. Cada resultado explica sus motivos, y las razones que
**bajan** el score empiezan con `↓` (`esRazonNegativa`):

```
✦ Strong dig — 75
1982 · 84 BPM · Rhodes · strings
Why this?
 • subido por Soultwinz, curador que ya te dio 3 temas
 • 1982 · época de quiet storm (1977–1987)
 • 100% match con tu crate
 • ya guardaste 3 de Howard Hewett: mismo artista, no un hallazgo
```

```
Deep cut — 46
Why this?
 • ↓ 2,3M views: esto ya lo conocés
 • ↓ Tatsuro Yamashita: nombre sobreexpuesto de la escena, lo encontrás solo
 • ↓ 2015: fuera de la época de city pop japonés
 • ↓ dura 15:00: probable suite, cara entera o mix
 • ↓ sin cruzar contra catálogo: el puntaje va descontado
```

Regla de oro: **si agregás una señal al score, positiva o negativa, agregá su razón al "Why this?".**

## Cómo se valida

Contra el oído real, no contra una intuición: `cd frontend && npx tsx scripts/scoreBench.ts`
mide **AUC** (probabilidad de que un guardado puntúe arriba de un no guardado) y
**precisión@30** sobre el benchmark del 19-sep-2026.

| conjunto | antes (19-sep) | después (20-sep) | honesto: sin `CANALES` sembrados |
|---|---|---|---|
| sugeridos (199, escuchó todo; tasa base 0.53) | AUC 0.456 · p@30 0.50 | AUC 0.585 · p@30 0.50 | AUC **0.564** |
| pool entero (1.954, solo metadata del flat; tasa base 0.054) | AUC 0.424 · p@30 0.03 | AUC 0.661 · p@30 0.23 | AUC **0.640** · p@30 **0.23** |

La última columna es la que vale: 28 entradas de `core/canales.ts` (las que tienen `guardados`
y los canales de ruido) salieron de ESTE benchmark, así que puntuar con ellas es medir la
etiqueta con la etiqueta. `scoreBench` reporta siempre las dos variantes; `sourceQuality` sola
pasa de 0.612 a 0.595 en el pool y de 0.548 a 0.511 en sugeridos. Lo que discrimina de verdad
es la duración y `affinity.channels` de sus playlists de antes.

Techo honesto: adentro de una lista ya curada (sugeridos) la metadata separa poco; lo que
decide ahí es el sonido, que solo el análisis de audio o el oído ven. El número que importa
es el del pool: de 1.954 items, subir lo guardado de "azar" a 0.66 es lo que hace que una veta
de 2.000 temas se pueda cavar por tandas empezando por lo más probable.

Lo que el benchmark no mide (y hay que medir en uso real): rarity y richness (sin catálogo),
y la escena real de cada búsqueda. La métrica del producto es el **hit rate** (mostradas /
guardadas por búsqueda), que la app calcula sola desde `crateIndex.hitRate()` (v3: cada
`seen` guarda `queryText` / `sessionId` / `shownAt`). Cuenta como acierto solo lo guardado
**después** de mostrado en ese contexto (`savedAt` > `shownAt`): una ficha importada de
playlist que reaparece con hideSeen apagado es "mostrada", no "guardada" de esa búsqueda. Los
rechazos conservan el contexto (`reject` fusiona sobre la fila persistida), así que también se
cuentan. El 53% a mano del 19-sep es la vara.
