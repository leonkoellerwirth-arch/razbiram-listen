import { describe, expect, it } from "vitest";
import { activeSentenceIndex, activeTokenStart, tokenTimingByStart } from "../src/sync";
import type { SegmentTiming, TokenTiming } from "../src/types";

const tokens: TokenTiming[] = [
  { token_start: 0, t_start: 0.0, t_end: 0.4, source: "word" },
  { token_start: 3, t_start: 0.4, t_end: 0.7, source: "word" },
  { token_start: 7, t_start: 0.7, t_end: 1.1, source: "word" },
];

describe("tokenTimingByStart", () => {
  it("keys timings by their token_start", () => {
    const map = tokenTimingByStart({ tokens, segments: [] });
    expect(map.get(3)?.t_start).toBe(0.4);
    expect(map.has(99)).toBe(false);
  });
});

describe("activeTokenStart", () => {
  it("finds the token whose window contains t (half-open)", () => {
    expect(activeTokenStart(tokens, 0.0)).toBe(0);
    expect(activeTokenStart(tokens, 0.5)).toBe(3);
    expect(activeTokenStart(tokens, 1.05)).toBe(7);
  });

  it("returns null outside every window", () => {
    expect(activeTokenStart(tokens, 5)).toBeNull();
    expect(activeTokenStart([], 0)).toBeNull();
  });

  it("prefers the later-starting token when windows overlap (word beats fallback)", () => {
    const overlap: TokenTiming[] = [
      { token_start: 0, t_start: 0.0, t_end: 2.0, source: "segment" },
      { token_start: 3, t_start: 0.9, t_end: 1.4, source: "word" },
    ];
    expect(activeTokenStart(overlap, 1.0)).toBe(3);
    expect(activeTokenStart(overlap, 0.5)).toBe(0);
  });
});

describe("activeSentenceIndex", () => {
  const segments: SegmentTiming[] = [
    { sentence_index: 0, t_start: 0.0, t_end: 1.1 },
    { sentence_index: 1, t_start: 1.1, t_end: 2.0 },
  ];
  it("maps time to the containing sentence", () => {
    expect(activeSentenceIndex(segments, 0.5)).toBe(0);
    expect(activeSentenceIndex(segments, 1.5)).toBe(1);
    expect(activeSentenceIndex(segments, 9)).toBeNull();
  });
});
