// A structural TS view of the .listen.json contract (razbiram-listen ListenDocument
// = razbiram-nlp EnrichedDocument + timings). Only the fields the viewer reads.

export interface Gloss {
  lang: string;
  text: string;
}

export interface Token {
  text: string;
  kind: string; // "word" | "punct" | "number" | "other"
  start: number;
  end: number;
  lemma?: string | null;
  upos?: string | null;
  band?: string | null;
}

export interface Sentence {
  text: string;
  start: number;
  end: number;
  tokens: Token[];
  gloss?: Gloss | null;
}

export interface VocabEntry {
  lemma: string;
  upos?: string | null;
  band?: string | null;
  gloss?: Gloss | null;
}

export interface TokenTiming {
  token_start: number;
  t_start: number;
  t_end: number;
  source: "word" | "segment";
  confidence?: number | null;
}

export interface SegmentTiming {
  sentence_index: number;
  t_start: number;
  t_end: number;
}

export interface ListenTimings {
  tokens: TokenTiming[];
  segments: SegmentTiming[];
}

export interface AudioRef {
  filename: string;
  duration_s?: number | null;
}

export interface ListenDocument {
  schemaVersion?: string;
  text: string;
  lang?: string;
  sentences: Sentence[];
  vocab?: VocabEntry[];
  audioRef?: AudioRef | null;
  timings?: ListenTimings | null;
}

// A background processing job, as reported by GET /jobs.
export interface Job {
  id: string;
  filename: string;
  title: string;
  status: "queued" | "running" | "done" | "error" | "cancelled";
  stage?: string | null;
  fraction?: number | null;
  error?: string | null;
  createdAt: string;
  mode: "core" | "enriched";
}

// A saved entry in the local library, as reported by GET /library.
export interface LibraryEntry {
  id: string;
  title: string;
  filename: string;
  durationS?: number | null;
  mode: "core" | "enriched";
  glossLang?: string | null;
  coverage?: number | null;
  createdAt: string;
  hasAudio: boolean;
}
