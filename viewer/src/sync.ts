// Pure karaoke-sync logic: given the audio's current time, which token/sentence
// is active? Kept free of the DOM so it's unit-tested directly.

import type { ListenTimings, SegmentTiming, TokenTiming } from "./types";

/** Map a token's char-offset key (token_start) to its timing. */
export function tokenTimingByStart(timings: ListenTimings | null | undefined): Map<number, TokenTiming> {
  const map = new Map<number, TokenTiming>();
  for (const t of timings?.tokens ?? []) map.set(t.token_start, t);
  return map;
}

/**
 * The `token_start` of the token active at time `t` (seconds), or null.
 * A token is active when `t ∈ [t_start, t_end)`. When several overlap (e.g. a
 * precise word timing inside a coarser segment-fallback window), the one with
 * the latest start wins — so real word timings beat the fallback.
 */
export function activeTokenStart(tokens: TokenTiming[], t: number): number | null {
  let best: TokenTiming | null = null;
  for (const tok of tokens) {
    if (t >= tok.t_start && t < tok.t_end && (best === null || tok.t_start > best.t_start)) {
      best = tok;
    }
  }
  return best ? best.token_start : null;
}

/** The `sentence_index` of the segment active at time `t`, or null. */
export function activeSentenceIndex(segments: SegmentTiming[], t: number): number | null {
  let best: SegmentTiming | null = null;
  for (const s of segments) {
    if (t >= s.t_start && t < s.t_end && (best === null || s.t_start > best.t_start)) {
      best = s;
    }
  }
  return best ? best.sentence_index : null;
}
