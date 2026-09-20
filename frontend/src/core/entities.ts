/**
 * Modelo de entidades de CRATE. CRATE es dueño de la entidad canónica.
 * Source Item → Candidate → Music Entity → Enriched Track.
 * Ver docs/ENTITY_MODEL.md
 */
import type { Provenanced } from './provenance'
import type { Mood, Feel, Texture } from './taxonomy'
import type { CrateScore } from './score'
import type { YtHints } from './ytHints'

export type SourceKind = 'youtube' | 'archive' | 'soundcloud' | 'bandcamp' | 'web'

/** Lo crudo que devuelve una fuente. Puede ser un tema, un álbum, un mix, un rip... */
export interface SourceItem {
  /** id estable: `${kind}:${nativeId}` */
  id: string
  kind: SourceKind
  nativeId: string
  url: string
  title: string
  uploader?: string
  channelId?: string
  durationSec?: number
  views?: number
  /**
   * Las views del listado plano de yt-dlp vienen redondeadas ("945000", "1700").
   * Con esto la UI dice "~1,7k views" y el score no las trata como exactas.
   * Solo es false cuando el número salió de `videos.list`.
   */
  viewsApprox?: boolean
  /** posición dentro de la playlist/canal que se está minando (cursor de veta) */
  playlistIndex?: number
  publishedAt?: string
  thumbnail?: string
  /** Vienen en el mismo `snippet` que ya pedimos: no cuestan quota extra. */
  description?: string
  tags?: string[]
  raw?: unknown
}

/** Un SourceItem parseado, todavía tentativo (pre-cruce con catálogo). */
export interface Candidate {
  source: SourceItem
  cleanedTitle: string
  artist?: string
  title?: string
  year?: number
  bpm?: number
  key?: string
  /** confianza del parseo/limpieza (0..1) */
  parseConfidence: number
  /** lo que se pudo PROBAR desde la descripción/tags/canal, sin adivinar */
  hints: YtHints
}

export interface Credit {
  name: string
  role: string
  instrument?: string
}

export interface RaritySignals {
  discogsWant?: number
  discogsHave?: number
  youtubeViews?: number
  uploadAgeDays?: number
  reissues?: number
}

/** La entidad canónica normalizada — la verdad de CRATE. */
export interface MusicEntity {
  crateId: string
  artist: string
  title: string
  year?: number
  label?: string
  country?: string
  genres: string[]
  styles: string[]
  credits: Credit[]
  discogsId?: number
  releaseMbid?: string
  recordingMbid?: string
  /** ¿el fuzzy match superó el umbral? Si no, no afirmamos catálogo como confirmado. */
  confirmed: boolean
  /**
   * Cómo se llegó a esta entidad. No todas las confirmaciones valen lo mismo:
   * un link a Discogs en la descripción es un id, un match por texto es una
   * apuesta. Se muestra en el "Why this?".
   */
  identifiedBy?: 'catalog_link' | 'topic_channel' | 'acoustid' | 'musicbrainz' | 'discogs'
  /**
   * Fuerza del match contra el release de Discogs del que salieron géneros,
   * estilos, sello y país (0..1; 1 con link directo). Es distinta de
   * `confirmed`: un Topic confirma la OBRA por el bloque ℗, pero el disco de
   * Discogs pudo elegirse con 0.62 de similitud. La affinity solo aprende esas
   * interpretaciones de catálogo cuando este número es alto. Lo setea el pipeline.
   */
  catalogMatch?: number
}

export type CrateStatus = 'seen' | 'saved' | 'analyzed' | 'rejected'

/** Entidad + metadata provenienciada + score + estado. Lo que ve el usuario. */
export interface EnrichedTrack {
  crateId: string
  entity: MusicEntity
  sources: SourceItem[]
  bpm?: Provenanced<number>
  /**
   * Lo que leyó el DSP tal cual (`analyzed`), cuando `bpm` es otra octava
   * plegada al rango del usuario (`inferred`) o corregida a mano. Viaja con la
   * ficha para que el "Why this?" pueda decir "76 BPM · analizado 152": sin
   * esto el usuario no puede juzgar si el pliegue fue correcto.
   */
  bpmRaw?: Provenanced<number>
  key?: Provenanced<string>
  mood?: Provenanced<Mood>
  instruments?: Provenanced<string[]>
  rarity: RaritySignals
  /**
   * Tu taxonomía, no la del catálogo. Sale del nombre de la playlist de origen.
   * Deliberadamente aparte de entity.genres: "dark" no es un género de Discogs,
   * es cómo VOS pensás ese disco a la hora de buscar un sample. Un track puede
   * tener varios: estar en dos playlists no es una contradicción.
   */
  tags?: string[]
  score?: CrateScore
  /**
   * Transitorio: la ficha se está cruzando contra catálogo todavía. Sirve para
   * mostrar lo que YouTube ya nos dio sin esperar los ~2s de red por tema.
   * No se persiste: solo los resultados finales entran al índice.
   */
  pending?: boolean
  status: CrateStatus
  firstSeenAt: string
  updatedAt: string
}

/** Filtros estructurados. Diseñados para poder venir de lenguaje natural a futuro. */
export interface SearchQuery {
  text: string
  bpm?: [number, number]
  key?: string
  mode?: 'major' | 'minor'
  year?: [number, number]
  genres?: string[]
  styles?: string[]
  instruments?: string[]
  feels?: Feel[]
  textures?: Texture[]
  energy?: [number, number]
  sources?: SourceKind[]
}
