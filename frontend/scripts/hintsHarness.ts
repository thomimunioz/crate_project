/**
 * Harness de hints / portero contra el benchmark del 19-sep-2026.
 *
 * Corre las funciones REALES del dominio (`extractHints`, `splitArtistTitle`,
 * `cleanTitle`, `esBasura`, `puntajeDeDig`, `canalDe`) sobre los 1.958 items
 * de `docs/benchmarks/2026-09-19-digging-a-mano/pool.json` y reporta cobertura.
 * La idea es que cada cambio al parser o al portero se MIDA acá antes de
 * afirmarlo en un commit, no que se estime.
 *
 *   cd frontend && npx tsx scripts/hintsHarness.ts            # tabla
 *   cd frontend && npx tsx scripts/hintsHarness.ts --dump     # + listas por stdout
 *
 * Ojo con el fixture: `descripciones.json` tiene 175 descripciones (no 1.958)
 * y vienen con los saltos de línea COLAPSADOS a espacios. Las cifras de Topic
 * son sobre ese subconjunto y sobre esa forma degradada; el parser tiene que
 * andar con las dos formas (con líneas en la app real, plano acá). Los chequeos
 * unitarios del final cubren la forma multilínea real.
 */
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

import type { SourceItem } from '../src/core/entities'
import { extractHints, NO_HINTS } from '../src/core/ytHints'
import { splitArtistTitle, cleanTitle, extractYear } from '../src/core/fuzzy'
import { esBasura, puntajeDeDig, claveDeObra } from '../src/core/queries'
import { canalDe, CANALES, TEMAS_DE_RUIDO_PERSONAL } from '../src/core/canales'

// ---------- fixtures ----------

interface PoolRow {
  video_id: string
  title: string
  uploader: string | null
  channel_id: string | null
  duration_sec: number | null
  views_approx: number | null
  playlist_vol: number
  playlist_index: number
  unavailable: boolean
}

interface DescRow {
  year?: string | null
  phonogram?: boolean
  uploader?: string
  title?: string
  desc?: string
}

interface LabelRow {
  entrega: string
  id: string
  tier: string
  saved: boolean
  dest: string[]
}

const aqui = dirname(fileURLToPath(import.meta.url))
const BENCH = resolve(aqui, '../../docs/benchmarks/2026-09-19-digging-a-mano')
const leer = <T>(f: string): T => JSON.parse(readFileSync(resolve(BENCH, f), 'utf8')) as T

const pool = leer<PoolRow[]>('pool.json')
const descripciones = leer<Record<string, DescRow>>('descripciones.json')
const labels = leer<LabelRow[]>('labels.json')

const dump = process.argv.includes('--dump')

// ---------- armado de SourceItems (misma forma que `sources/youtube.ts::toItem`) ----------

function toItem(r: PoolRow): SourceItem {
  const d = descripciones[r.video_id]
  return {
    id: `youtube:${r.video_id}`,
    kind: 'youtube',
    nativeId: r.video_id,
    url: `https://www.youtube.com/watch?v=${r.video_id}`,
    title: r.title ?? '',
    uploader: r.uploader ?? undefined,
    channelId: r.channel_id ?? undefined,
    durationSec: r.duration_sec ?? undefined,
    views: r.views_approx ?? undefined,
    viewsApprox: true,
    playlistIndex: r.playlist_index,
    description: d?.desc,
  }
}

const items = pool.map(toItem)
const guardadosFilas = labels.filter((l) => l.saved)
const guardados = new Set(guardadosFilas.map((l) => l.id))

// ---------- métricas ----------

const pct = (n: number, d: number): string => (d ? `${((100 * n) / d).toFixed(1)}%` : '-')
const fila = (k: string, n: number, d: number): string =>
  `${k.padEnd(52)} ${String(n).padStart(5)} / ${String(d).padEnd(5)} ${pct(n, d)}`

interface Medida {
  item: SourceItem
  esTopic: boolean
  conDesc: boolean
  hints: ReturnType<typeof extractHints>
  split: ReturnType<typeof splitArtistTitle>
  artista?: string
  anio?: number
  basura: boolean
}

const medidas: Medida[] = items.map((item) => {
  const esTopic = / - Topic$/.test(item.uploader ?? '')
  const hints = extractHints({
    channelTitle: item.uploader,
    description: item.description,
    tags: item.tags,
    title: item.title,
  })
  const split = splitArtistTitle(item.title)
  // misma prioridad que debería usar `pipeline::normalize`: probado > parseado
  // del título > el canal como artista (parsed, confidence baja)
  const artista = hints.artist ?? split.artist ?? hints.artistFromChannel?.value
  const anio = hints.year ?? hints.titleHints?.year ?? extractYear(item.title)
  return {
    item,
    esTopic,
    conDesc: Boolean(item.description),
    hints,
    split,
    artista,
    anio,
    basura: esBasura(item),
  }
})

const total = medidas.length
const topic = medidas.filter((m) => m.esTopic)
const noTopic = medidas.filter((m) => !m.esTopic)
const topicConDesc = topic.filter((m) => m.conDesc)

// los chequeos duros (exit code 1 si alguno falla) se declaran acá porque el
// portero y los canales también tienen contratos que cumplir, no solo los unitarios
let fallas = 0
const check = (nombre: string, ok: boolean, detalle?: unknown): void => {
  if (!ok) fallas++
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${nombre}${ok ? '' : ` → ${JSON.stringify(detalle)}`}`)
}

console.log(
  `\n== hintsHarness — benchmark 2026-09-19 (${total} items, ${Object.keys(descripciones).length} con descripción) ==\n`,
)

console.log('-- cobertura general --')
console.log(fila('con artista (hints, split o canal)', medidas.filter((m) => m.artista).length, total))
console.log(fila('con artista — solo no-Topic', noTopic.filter((m) => m.artista).length, noTopic.length))
console.log(
  fila(
    '  · solo por hints o split (sin el canal)',
    noTopic.filter((m) => m.hints.artist ?? m.split.artist).length,
    noTopic.length,
  ),
)
console.log(
  fila(
    '  · de esos, artista = uploader (canal artista)',
    noTopic.filter((m) => !(m.hints.artist ?? m.split.artist) && m.hints.artistFromChannel).length,
    noTopic.length,
  ),
)
console.log(fila('con año (℗ / título / convención)', medidas.filter((m) => m.anio).length, total))
console.log(fila('con año — solo no-Topic', noTopic.filter((m) => m.anio).length, noTopic.length))
console.log(fila('con convención de título parseada', medidas.filter((m) => m.hints.titleHints).length, total))
console.log(fila('  · con país del título', medidas.filter((m) => m.hints.titleHints?.country).length, total))
console.log(
  fila('  · con géneros del título', medidas.filter((m) => (m.hints.titleHints?.genres?.length ?? 0) > 0).length, total),
)
console.log(fila('  · con álbum + posición del título', medidas.filter((m) => m.hints.titleHints?.album).length, total))

console.log('\n-- Topic (solo los que tienen descripción en el fixture, forma plana) --')
const topicOk = (f: (m: Medida) => boolean): number =>
  topicConDesc.filter((m) => m.hints.source === 'topic_channel' && f(m)).length
console.log(fila('parseTopic devuelve título', topicOk((m) => Boolean(m.hints.title)), topicConDesc.length))
console.log(fila('parseTopic devuelve artista', topicOk((m) => Boolean(m.hints.artist)), topicConDesc.length))
console.log(fila('parseTopic devuelve álbum', topicOk((m) => Boolean(m.hints.album)), topicConDesc.length))
console.log(fila('parseTopic devuelve año', topicOk((m) => Boolean(m.hints.year)), topicConDesc.length))
console.log(fila('  · marcados reissue', topicConDesc.filter((m) => m.hints.reissue).length, topicConDesc.length))
console.log(
  fila(
    '  · con Released on: distinto del ℗',
    topicConDesc.filter(
      (m) => m.hints.releasedOn && m.hints.phonogramYear && m.hints.releasedOn !== m.hints.phonogramYear,
    ).length,
    topicConDesc.length,
  ),
)
console.log(
  fila(
    '  · título del hint == título del video',
    topicConDesc.filter((m) => m.hints.title && m.hints.title.toLowerCase() === m.item.title.toLowerCase()).length,
    topicConDesc.length,
  ),
)
console.log(
  fila('  · con créditos por rol', topicConDesc.filter((m) => (m.hints.credits?.length ?? 0) > 0).length, topicConDesc.length),
)

// año del hint vs año esperado del fixture (el ℗ que anotaron a mano)
const conAnioEsperado = topicConDesc.filter((m) => {
  const y = descripciones[m.item.nativeId]?.year
  return y && /^\d{4}$/.test(String(y))
})
const anioCoincide = conAnioEsperado.filter((m) => {
  const y = Number(descripciones[m.item.nativeId]?.year)
  return (m.hints.phonogramYear ?? m.hints.releasedOn) === y
})
console.log(fila('℗/Released on leído == año anotado en el fixture', anioCoincide.length, conAnioEsperado.length))
const anioObra = conAnioEsperado.filter((m) => m.hints.year === Number(descripciones[m.item.nativeId]?.year))
console.log(fila('  · year (de la obra) == año anotado (difiere si reissue)', anioObra.length, conAnioEsperado.length))

console.log('\n-- portero --')
const basura = medidas.filter((m) => m.basura)
console.log(fila('esBasura', basura.length, total))
const guardadosBasura = medidas.filter((m) => m.basura && guardados.has(m.item.nativeId))
console.log(
  fila(
    `guardados que caen como basura (${guardadosFilas.length} filas / ${guardados.size} ids)`,
    guardadosBasura.length,
    guardados.size,
  ),
)
const rankeados = new Set(labels.filter((l) => l.tier !== 'no_rankeado').map((l) => l.id))
console.log(
  fila(
    'sugeridos (rankeados) que caen como basura',
    medidas.filter((m) => m.basura && rankeados.has(m.item.nativeId)).length,
    rankeados.size,
  ),
)
// contrato C4: la joya no se anuncia en el título; el portero no puede tirar lo que Thomas guardó
check(
  'ningún guardado cae como basura',
  guardadosBasura.length === 0,
  guardadosBasura.map((m) => m.item.title),
)

// puntajeDeDig por origen: en veta la obscuridad no cuenta
const conViews = medidas.filter((m) => !m.basura && m.item.views != null)
const mediana = (xs: number[]): number => {
  const s = [...xs].sort((a, b) => a - b)
  return s.length ? s[Math.floor(s.length / 2)] : 0
}
for (const origen of ['busqueda', 'veta'] as const) {
  const puntajes = conViews.map((m) => ({ m, p: puntajeDeDig(m.item, {}, origen).valor }))
  const guard = puntajes.filter((x) => guardados.has(x.m.item.nativeId)).map((x) => x.p)
  const resto = puntajes.filter((x) => !guardados.has(x.m.item.nativeId)).map((x) => x.p)
  // AUC por conteo de pares: P(puntaje guardado > puntaje no guardado)
  let ganados = 0
  let pares = 0
  for (const g of guard) {
    for (const r of resto) {
      pares++
      if (g > r) ganados++
      else if (g === r) ganados += 0.5
    }
  }
  console.log(
    `puntajeDeDig[${origen.padEnd(8)}] mediana guardados ${mediana(guard).toFixed(3)} · resto ${mediana(resto).toFixed(3)} · AUC ${(pares ? ganados / pares : 0).toFixed(3)}`,
  )
}

console.log('\n-- canales --')
const curadores = CANALES.filter((c) => c.rol === 'curador')
console.log(`CANALES: ${CANALES.length} (${curadores.length} curadores, ${CANALES.length - curadores.length} ruido)`)
const deCurador = medidas.filter((m) => canalDe(m.item.channelId, m.item.uploader)?.rol === 'curador')
console.log(fila('items del pool subidos por un curador', deCurador.length, total))
console.log(
  fila('  · guardados que vienen de un curador', deCurador.filter((m) => guardados.has(m.item.nativeId)).length, guardados.size),
)
console.log(
  fila(
    'items del pool de un canal de ruido',
    medidas.filter((m) => canalDe(m.item.channelId, m.item.uploader)?.rol === 'ruido').length,
    total,
  ),
)
// ruido PERSONAL por título: baja la affinity a 0.1, así que no puede pegarle
// a nada que Thomas haya guardado o que se le haya sugerido (persona que amo,
// Zelda Barron y The Future Funk Band eran falsos positivos del regex viejo)
const tituloRuido = medidas.filter((m) => TEMAS_DE_RUIDO_PERSONAL.test(m.item.title))
console.log(fila('items con título de ruido personal (TEMAS_DE_RUIDO_PERSONAL)', tituloRuido.length, total))
const ruidoQueSirvio = tituloRuido.filter((m) => guardados.has(m.item.nativeId) || rankeados.has(m.item.nativeId))
check(
  'ningún guardado ni sugerido cae en TEMAS_DE_RUIDO_PERSONAL',
  ruidoQueSirvio.length === 0,
  ruidoQueSirvio.map((m) => m.item.title),
)
for (const titulo of [
  'Los Ángeles Negros - Esa persona que amo',
  'Zelda Barron - Sunshine',
  'The Future Funk Band - Get Down (1979)',
  'Personal Touch - Slow Jam',
]) {
  check(`  · no es ruido: "${titulo}"`, !TEMAS_DE_RUIDO_PERSONAL.test(titulo))
}
for (const titulo of [
  'Beneath the Mask (Persona 5) Funk Cover',
  'Pull the Trigger (Persona Q2) Band Cover',
  'Legend of Zelda Lofi',
  'Naruto Shippuden OST - Sadness',
  'Future Funk Mix',
]) {
  check(`  · sí es ruido: "${titulo}"`, TEMAS_DE_RUIDO_PERSONAL.test(titulo))
}

console.log('\n-- dedupe (claveDeObra sobre cleanTitle) --')
const claves = new Map<string, number>()
for (const m of medidas) {
  const k = claveDeObra(m.item.title)
  claves.set(k, (claves.get(k) ?? 0) + 1)
}
console.log(`claves únicas: ${claves.size} / ${total} · items colapsados: ${total - claves.size}`)
const vacias = medidas.filter((m) => !cleanTitle(m.item.title))
console.log(`cleanTitle vacío: ${vacias.length}`)

// ---------- chequeos duros (forma multilínea real de Topic, casos del brief) ----------

console.log('\n-- chequeos unitarios --')

const topicReal = extractHints({
  channelTitle: 'Sharon Ridley - Topic',
  description:
    'Provided to YouTube by The Orchard Enterprises\n\nWhere Does That Leave Me · Sharon Ridley\n\nStay a While with Me\n\n℗ 1971 Sussex Records\n\nReleased on: 1971-01-01\n\nAuto-generated by YouTube.',
})
check(
  'topic multilínea: título/artista/álbum/año',
  topicReal.title === 'Where Does That Leave Me' &&
    topicReal.artist === 'Sharon Ridley' &&
    topicReal.album === 'Stay a While with Me' &&
    topicReal.year === 1971 &&
    topicReal.label === 'Sussex Records',
  topicReal,
)

const topicReissue = extractHints({
  channelTitle: 'The Majestic Arrows - Topic',
  description:
    'Provided to YouTube by The Orchard Enterprises\n\nHeartbeat · The Majestic Arrows\n\nThe Majestic Arrows\n\n℗ 2013 Dust Index\n\nReleased on: 1973-01-01\n\nAuto-generated by YouTube.',
})
check(
  'topic reissue: usa Released on y marca reissue',
  topicReissue.year === 1973 && topicReissue.reissue === true && topicReissue.phonogramYear === 2013,
  topicReissue,
)

const topicGreatest = extractHints({
  channelTitle: 'The Chi-Lites - Topic',
  description:
    'Provided to YouTube by Universal Music Group\n\nHave You Seen Her · The Chi-Lites\n\n20 Greatest Hits\n\n℗ 2001 Brunswick\n\nReleased on: 2001-01-01\n\nAuto-generated by YouTube.',
})
check(
  'topic recopilatorio: reissue sin año de obra',
  topicGreatest.reissue === true && topicGreatest.year === undefined && topicGreatest.phonogramYear === 2001,
  topicGreatest,
)

const topicFlat = extractHints({
  channelTitle: 'Sharon Ridley - Topic',
  title: 'Where Does That Leave Me',
  description:
    'Provided to YouTube by The Orchard Enterprises Where Does That Leave Me · Sharon Ridley Stay a While with Me ℗ 1971 © Sussex Records™ a division of 43 North Broadway, LLC. Released on: 1971-01-01 Auto-generated by YouTube.',
})
check(
  'topic plano (fixture): título/artista/álbum/año',
  topicFlat.title === 'Where Does That Leave Me' &&
    topicFlat.artist === 'Sharon Ridley' &&
    topicFlat.album === 'Stay a While with Me' &&
    topicFlat.year === 1971,
  topicFlat,
)

const topicPlayers = extractHints({
  channelTitle: 'Hiromasa Suzuki - Topic',
  description:
    'Provided to YouTube by King Record Co., Ltd.\n\nMurmur · The Players · Hiromasa Suzuki\n\nRock Joint Biwa - Kumikyoku Danjo\n\n℗ 1971 KING RECORD CO., LTD.\n\nReleased on: 1971-01-01',
})
check(
  'topic varios artistas: el del canal es el artista',
  topicPlayers.artist === 'Hiromasa Suzuki' && topicPlayers.aliases.includes('The Players'),
  topicPlayers,
)

const roles = extractHints({
  channelTitle: 'Everette Harp - Topic',
  description:
    "Provided to YouTube by Universal\n\nLet's Wait Awhile · Everette Harp\n\nWhat's Going On\n\n℗ 1997 Blue Note\n\nReleased on: 1997-01-01\n\nProducer: George Duke\nSaxophone: Everette Harp\nElectric Piano: George Duke\nBass: Larry Kimpel\n\nAuto-generated by YouTube.",
})
check(
  'topic roles: créditos con instrumento',
  (roles.credits?.length ?? 0) === 4 &&
    roles.credits?.some((c) => c.instrument === 'Rhodes' && c.name === 'George Duke') === true,
  roles.credits,
)

const campos = extractHints({ description: 'Album : Untouched\n  Year : 1978\nLabel: Hot Wax' })
check(
  'FIELD tolera "Album : X" e indentado',
  campos.album === 'Untouched' && campos.year === 1978 && campos.label === 'Hot Wax',
  campos,
)

const fromAlbum = extractHints({ description: 'From the Album "Echoes And Images", 1981' })
check('From the Album "X", AAAA', fromAlbum.album === 'Echoes And Images' && fromAlbum.year === 1981, fromAlbum)

const lpLine = extractHints({ description: 'LP : Think Of The Children Hot Wax Records 1972 USA' })
check(
  'LP : disco sello año país',
  lpLine.year === 1972 && lpLine.album?.startsWith('Think Of The Children') === true,
  lpLine,
)

const mfer = extractHints({
  title: 'Marlon Hunter - Summer Essence [US] Soul, Jazz, Funk (1980)',
  channelTitle: 'Music for empty rooms',
})
check(
  'Music for empty rooms: [País] Género (Año)',
  mfer.titleHints?.country === 'US' && mfer.titleHints?.year === 1980 && (mfer.titleHints?.genres ?? []).length === 3,
  mfer.titleHints,
)
check('  · y el hint NO escribe artista/año de catálogo', mfer.artist === undefined && mfer.year === undefined, mfer)

const ants = extractHints({ title: 'Miki Matsubara - Miracle Touch - 1986 - Japan', channelTitle: 'ants kask' })
check('ants kask: - AAAA - País', ants.titleHints?.year === 1986 && ants.titleHints?.country === 'Japan', ants.titleHints)

const crackle = extractHints({
  title: 'Sugar Billy - Super Duper Love [Soul] (1974 - US)',
  channelTitle: 'Crackle Journey',
})
check(
  'Crackle Journey: [Género] (Año - País)',
  crackle.titleHints?.year === 1974 && crackle.titleHints?.country === 'US' && crackle.titleHints?.genres?.[0] === 'Soul',
  crackle.titleHints,
)

const library = extractHints({
  title: 'Piero Umiliani - Lezione Di Ballo (Library, 1980)',
  channelTitle: 'Antonio Pérez',
})
check(
  '(Library, AAAA)',
  library.titleHints?.year === 1980 && library.titleHints?.genres?.includes('Library') === true,
  library.titleHints,
)

const mvc = extractHints({
  title: 'Dazz Band - On The One (1983) - A3 - Just Believe In Love',
  channelTitle: 'My Vinyl Collection',
})
check(
  'My Vinyl Collection: Álbum (AAAA) - A3 - Título',
  mvc.titleHints?.album === 'On The One' &&
    mvc.titleHints?.position === 'A3' &&
    mvc.titleHints?.title === 'Just Believe In Love' &&
    mvc.titleHints?.year === 1983,
  mvc.titleHints,
)

const sampleSoul = extractHints({ title: 'The Moments – Sho Nuff Boogie (1975)', channelTitle: 'Sample Soul 70' })
check('Sample Soul 70: Artista – Título (AAAA)', sampleSoul.titleHints?.year === 1975, sampleSoul.titleHints)

const sepAsim = splitArtistTitle('The Dramatics- In the rain')
check(
  'separador asimétrico "Artista- Título"',
  sepAsim.artist === 'The Dramatics' && sepAsim.title === 'In the rain',
  sepAsim,
)
const sepDoble = splitArtistTitle('Akira Ishikawa & Count Buffaloes -- Sunrise')
check(
  'separador doble guion',
  sepDoble.artist === 'Akira Ishikawa & Count Buffaloes' && sepDoble.title === 'Sunrise',
  sepDoble,
)
const sepEsp = splitArtistTitle('CARRIE LUCAS   LOVIN IS ON MY MIND')
check(
  'separador de 2+ espacios',
  sepEsp.artist === 'CARRIE LUCAS' && sepEsp.title === 'LOVIN IS ON MY MIND',
  sepEsp,
)
const jeanClaude = splitArtistTitle('Jean-Claude Vannier Tema')
check('Jean-Claude no se parte', jeanClaude.artist === undefined, jeanClaude)
const acdc = splitArtistTitle('AC/DC Back In Black')
check('AC/DC no se parte', acdc.artist === undefined, acdc)

const canalArtista = extractHints({ title: 'Mysterious Vibes', channelTitle: 'The Blackbyrds' })
check(
  'canal = artista (nombre pelado, sin vocabulario digger) → parsed, no probado',
  canalArtista.artistFromChannel?.value === 'The Blackbyrds' &&
    canalArtista.artist === undefined &&
    canalArtista.source === 'none' &&
    canalArtista.artistFromChannel.confidence <= 0.5,
  canalArtista,
)
const canalOficial = extractHints({ title: 'Another Star', channelTitle: 'しばたはつみ 公式YouTubeチャンネル' })
check(
  'canal oficial japonés → artista sin el sufijo',
  canalOficial.artistFromChannel?.value === 'しばたはつみ' && canalOficial.artistFromChannel.reason === 'official',
  canalOficial,
)
const canalBilingue = extractHints({ title: 'To The Limit', channelTitle: '久保田利伸 / Toshinobu Kubota Official YouTube Channel' })
check(
  'canal oficial bilingüe → nombre + alias',
  canalBilingue.artistFromChannel?.value === '久保田利伸' && canalBilingue.artistFromChannel.alias === 'Toshinobu Kubota',
  canalBilingue.artistFromChannel,
)
const canalHandle = extractHints({ title: 'Alone', channelTitle: 'wee' })
check('handle en minúsculas NO es artista', canalHandle.artistFromChannel === undefined, canalHandle.artistFromChannel)
const canalDigger = extractHints({ title: 'Lovin Is On My Mind', channelTitle: 'Here Is Soul & Funk' })
check('canal digger NO es artista', canalDigger.artistFromChannel === undefined && canalDigger.source === 'none', canalDigger)
const canalCurador = extractHints({ title: 'Some Song', channelTitle: 'si' })
check('canal curador de CANALES NO es artista', canalCurador.artistFromChannel === undefined, canalCurador)
check(
  'canal con "Artista - Tema" en el título no usa el uploader',
  extractHints({ title: 'Ronnie Laws - Tidal Wave', channelTitle: 'Ronnie Laws' }).source === 'none',
)

const mk = (title: string, durationSec: number, uploader = 'x'): SourceItem => ({
  id: 'youtube:t',
  kind: 'youtube',
  nativeId: 't',
  url: '',
  title,
  durationSec,
  uploader,
})
check('esBasura: karaoke', esBasura(mk('Sade - Smooth Operator (Karaoke Version)', 240)))
check('esBasura: full album de 40 min sin forma Artista - Tema', esBasura(mk('Quiet Storm Full Album 1985', 2400)))
check(
  'esBasura: full album de 40 min CON forma Artista - Tema pasa',
  !esBasura(mk('Anita Baker - Rapture (1986) [Full Album]', 2400)),
)
check('esBasura: > 75 min', esBasura(mk('Anita Baker - Rapture (1986) [Full Album]', 4600)))
check(
  'esBasura: OST japonés legítimo NO es basura',
  !esBasura(mk('You & The Explosion Band - Silhouette (Japan OST - Lupin III - 1978)', 200)),
)
check(
  'esBasura: Persona cover NO es basura universal (va por CANALES)',
  !esBasura(mk('Beneath the Mask (Persona 5) Funk Cover', 200, 'The Consouls')),
)
check('canalDe: ruido por nombre', canalDe(undefined, 'The Consouls')?.rol === 'ruido')
check('canalDe: curador por channelId', canalDe('UCY8_y20lxQhhBe8GZl5A9rw')?.rol === 'curador')
check('canalDe: familia BigPeter por prefijo', canalDe(undefined, 'BigPeter1086 Real Music Channel')?.rol === 'curador')
check('canalDe: desconocido → undefined', canalDe('UCxxxxxxxxxxxxxxxxxxxxxx', 'alguien') === undefined)

const base = mk('A - B (1980)', 200)
check(
  'puntajeDeDig veta ignora views',
  Math.abs(puntajeDeDig(base, {}, 'veta').valor - puntajeDeDig({ ...base, views: 5_000_000 }, {}, 'veta').valor) < 1e-9,
)
check(
  'puntajeDeDig busqueda sí usa views',
  puntajeDeDig({ ...base, views: 300 }, {}, 'busqueda').valor >
    puntajeDeDig({ ...base, views: 5_000_000 }, {}, 'busqueda').valor,
)
check('NO_HINTS sigue siendo la forma vacía', NO_HINTS.source === 'none' && NO_HINTS.confidence === 0)

console.log(`\n${fallas ? `${fallas} chequeo(s) fallaron` : 'todos los chequeos pasaron'}`)

// ---------- dumps ----------

if (dump) {
  const out = (nombre: string, filas: string[]): void => {
    console.log(`\n### ${nombre} (${filas.length})`)
    for (const f of filas) console.log(f)
  }
  out(
    'basura',
    basura.map((m) => `${m.item.nativeId}\t${m.item.durationSec ?? '-'}s\t${m.item.uploader ?? '-'}\t${m.item.title}`),
  )
  out('guardados como basura', guardadosBasura.map((m) => `${m.item.nativeId}\t${m.item.title}`))
  out(
    'no-Topic sin artista',
    noTopic.filter((m) => !m.artista && !m.basura).map((m) => `${m.item.uploader ?? '-'}\t${m.item.title}`),
  )
  out(
    'Topic reissue',
    topicConDesc
      .filter((m) => m.hints.reissue)
      .map(
        (m) =>
          `${m.item.nativeId}\t℗${m.hints.phonogramYear}\trel ${m.hints.releasedOn ?? '-'}\tyear ${m.hints.year ?? '-'}\t${m.hints.album}\t${m.item.title}`,
      ),
  )
  out(
    'canal como artista',
    medidas
      .filter((m) => !(m.hints.artist ?? m.split.artist) && m.hints.artistFromChannel)
      .map((m) => `${m.hints.artistFromChannel?.confidence}	${m.hints.artistFromChannel?.value}${m.hints.artistFromChannel?.alias ? ` (${m.hints.artistFromChannel.alias})` : ''}	<- ${m.item.uploader}	${m.item.title}`),
  )
  out(
    'convenciones',
    medidas
      .filter((m) => m.hints.titleHints)
      .map((m) => `${m.item.uploader ?? '-'}\t${JSON.stringify(m.hints.titleHints)}\t${m.item.title}`),
  )
}

process.exitCode = fallas ? 1 : 0
