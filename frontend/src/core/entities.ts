/**
 * Modelo de entidades de CRATE. CRATE es dueño de la entidad canónica.
 * Source Item → Candidate → Music Entity → Enriched Track.
 * Ver docs/ENTITY_MODEL.md
 */
import type { Provenanced } from './provenance'
import type { Mood, Feel, Texture } from './taxonomy'
import type { CrateScore } from './score'

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
  publishedAt?: string
  thumbnail?: string
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
}

export type CrateStatus = 'seen' | 'saved' | 'analyzed' | 'rejected'

/** Entidad + metadata provenienciada + score + estado. Lo que ve el usuario. */
export interface EnrichedTrack {
  crateId: string
  entity: MusicEntity
  sources: SourceItem[]
  bpm?: Provenanced<number>
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
