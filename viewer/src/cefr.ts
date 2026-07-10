// CEFR band → CSS class. The colours live in styles.css (--band-* tokens), which
// are the Studio-authoritative family scale (ECOSYSTEM §4).

export const CEFR_BANDS = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;
export type CefrBand = (typeof CEFR_BANDS)[number];

const KNOWN = new Set<string>(CEFR_BANDS);

/** The badge class for a band, or null if the band is missing/unknown. */
export function bandClass(band: string | null | undefined): string | null {
  return band && KNOWN.has(band) ? `band-${band}` : null;
}
