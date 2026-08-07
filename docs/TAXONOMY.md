# Taxonomía — mood, instrumentos, géneros

Diseñada chica y a propósito. El objetivo NO es describir toda la música del mundo, es dar
al beatmaker filtros útiles y consistentes. Implementación: [`frontend/src/core/taxonomy.ts`](../frontend/src/core/taxonomy.ts).

## Mood (nada de campos libres)

`happy / sad / chill / dark` suelto es inútil y subjetivo. Usamos 3 ejes cerrados:

```
Energy    1 ───────────── 5        (calmo → intenso)

Feel      laid-back · groovy · dreamy · dark · melancholic · uplifting · warm · tense

Texture   dusty · clean · lush · raw · lo-fi · psychedelic · organic
```

Combinás ejes: `dusty + melancholic + laid-back`, `lush + warm + groovy`, etc.
Eso es mucho más útil (y filtrable) que "sad vibes".

**De dónde sale el mood:**
- `inferred` — de género + estilo + tags/descripción (confidence media). Es lo default en Capa 1.
- `analyzed` — de modelos de audio (Essentia mood models) cuando corrés "Analizar audio".
- `user` — si el usuario corrige/etiqueta a mano (confidence 1).

Siempre con provenance. Nunca se afirma un mood como si fuera un hecho del catálogo.

## Instrumentos (la joya escondida: créditos de Discogs)

El diferencial más fuerte de la Capa 1: **Discogs lista créditos por músico** en muchos
releases. O sea podemos saber que un disco tiene Rhodes / sax / cuerdas / Fender bass
**sin tocar el audio**, directo del catálogo.

Instrumentos que más le importan a un beatmaker (lista base, ampliable):

```
Rhodes · Wurlitzer · piano acústico · organ · clavinet · synth
guitar (clean/wah) · bass (upright/electric) · drums · percussion
strings · flute · saxophone · trumpet · trombone · harp · vibraphone
vocals (male/female) · choir · harpsichord
```

**De dónde salen:**
- `catalog` — de los credits de Discogs (alta confianza, es lo ideal).
- `analyzed` — de un clasificador de instrumentos sobre el audio (opt-in), con confidence.
- `parsed` — mención en el título/tags ("Rhodes", "piano loop") (confianza media).

## Géneros / estilos

Nos apoyamos en la **taxonomía de Discogs** (Genre + Style), que es rica y estándar:
`Soul`, `Jazz-Funk`, `Soul-Jazz`, `Boogie`, `MPB`, `City Pop`, `Library`, `Bossa Nova`,
`Free Funk`, `Fusion`, etc. No inventamos una taxonomía de géneros propia; mapeamos a Discogs.

## Pensado para lenguaje natural (a futuro, NO en F1)

El modelo de filtros se diseña para que mañana se pueda traducir:

```
"soul brasileño de los 70, lento, con Rhodes y medio melancólico"
        ↓
{ genre: ['Soul','MPB'], year: [1970,1979], bpm: [65,90],
  instruments: ['Rhodes'], feel: ['melancholic'], energy: [1,2] }
```

Por eso todo filtro es estructurado y serializable desde ahora.
