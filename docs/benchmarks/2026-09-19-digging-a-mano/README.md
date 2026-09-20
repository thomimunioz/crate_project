# Benchmark: digging a mano, 19–20 sep 2026

El 19-sep-2026 se diggearon **a mano** (Claude + agentes, sin la app) 10 playlists ajenas
("Samples Vol. 00–09", canal DIGGING, 1.958 items) hacia las 5 playlists curadas de Thomas.
Él escuchó todo y guardó lo que le sirvió. Esto es el resultado, congelado, para que cada
cambio de discovery, hints, score o DSP **se mida contra el oído real** y no se estime.

## Números

| Entrega | Sugeridos | Guardados | Hit rate | 🔥 fuego | 👍 bien | 🤔 quizás |
|---|---|---|---|---|---|---|
| 80s (quiet storm) | 94 | 55 | 58% | 19/39 | 29/41 | 7/14 |
| SOUL SAMPLES | 30 | 17 | 57% | 11/16 | 5/13 | 1/1 |
| R&B SOUL SAMPLES | 30 | 10 | 33% | 6/15 | 4/13 | 0/2 |
| JAPANESE CITY POP | 22 | 11 | 50% | 8/11 | 2/10 | 1/1 |
| JAZZ FUSION | 30 | 16 | 53% | 7/17 | 7/11 | 2/2 |
| **Total** | **206** | **109** | **53%** | | | |

Lecturas que importan para el producto:

- **Obscurity pesa más que el encaje canónico.** En la entrega 80s los 👍 (71%) le ganaron a los
  🔥 (49%) porque en 🔥 estaba lo mainstream con millones de views (Whitney, Isleys, Patti Austin):
  encajaba perfecto y no lo guardó. Manhattans (1M) y Herb Alpert (8M) sí, pero son excepción.
- **Él redistribuye.** De las 55 guardadas del 80s, 22 fueron a "80s", 17 a R&B y 16 a SOUL. Un
  "no encaja en esta lista" no es rechazo.
- **La década no es rígida si la escuela es la misma:** guardó quiet storm 1990–92 ("estaban TOP").
  El límite duro es el tempo: casi nunca > ~115 BPM real.
- **El DSP se equivoca de octava hacia arriba:** de 120 temas con BPM crudo > 115, 95 eran el doble.
- **Los canales curadores son señal de fuente**, no de obra: Music for empty rooms, Oleg Tsoy,
  TheRAREGROOVEMAN, Soultwinz, `si` concentran lo guardado. Ver `canales.json`.

## Archivos

- `pool.json` — los 1.958 items crudos (id, título, uploader, channel_id, duración, views
  aproximadas de `--flat-playlist`, volumen e índice). Es el input de cualquier harness de
  parseo/portero.
- `playlists_thomas.json` — sus 5 playlists **antes** (19-sep, antes de sugerir) y **después**
  (20-sep, todo escuchado). La diferencia es la ground truth.
- `labels.json` — 333 filas: cada sugerencia (`entrega`, `id`, `tier`, `saved`, `dest`) más los
  127 candidatos verificados que no llegaron al ranking (`tier: no_rankeado`, negativos débiles:
  no los vio).
- `verificacion.json` — por candidato: BPM medido y corregido, tonalidad, año, instrumentos,
  juicio. Es lo que sabía el ranking al elegir.
- `bpm_octave_dataset.json` — 247 pares `raw` (lo que devolvió `backend/app/dsp.py::_estimate_bpm`
  sobre 45 s desde el segundo 60) vs `final` (corregido por juicio musical), con la confianza.
  **Ojo:** el `final` lo corrigieron agentes, no Thomas; cuando la UI permita corregir la octava
  a mano, ese dato reemplaza a este.
- `descripciones.json` — descripción, uploader y año ℗ de 175 videos (los que se verificaron),
  para medir los hints de canales Topic.
- `canales.json` — por canal del pool: cuántos aportó, cuántos se sugirieron, cuántos guardó.

## Cómo se hizo (el método que funcionó)

1. `yt-dlp --flat-playlist` de las 10 playlists (sin API key, sin quota). Se sacó lo que ya
   tenía y los duplicados.
2. **Se leyó todo.** La joya no se anuncia en el título; grep por palabras no sirve.
3. Por playlist, 3 lentes (artista/escena, sonido/instrumentación, joya oculta) + un crítico de
   completitud.
4. Verificación: 45 s de audio por candidato → Librosa (BPM/key) + año del ℗ de la descripción
   (ojo con reediciones) + juicio.
5. Ranking con vara alta, máximo 30 por lista, "why" de una línea, tiers.
6. Entrega en HTML con links y marcas; él escuchó y guardó. Lo guardado se relevó re-listando
   las playlists.

Costo: ~4M tokens de agentes y ~60 min para 1.835 candidatos × 4 listas. Eso es lo que la app
tiene que hacer sola: discover (playlist) → normalize (hints) → enrich (℗/Discogs) → score
(con affinity) → mostrar con "Why this?".
