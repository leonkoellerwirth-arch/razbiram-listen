import { describe, expect, it } from "vitest";
import { bandClass } from "../src/cefr";

describe("bandClass", () => {
  it("maps every valid band to its badge class", () => {
    for (const b of ["A1", "A2", "B1", "B2", "C1", "C2"]) {
      expect(bandClass(b)).toBe(`band-${b}`);
    }
  });

  it("returns null for missing or unknown bands", () => {
    expect(bandClass(null)).toBeNull();
    expect(bandClass(undefined)).toBeNull();
    expect(bandClass("")).toBeNull();
    expect(bandClass("D1")).toBeNull();
  });
});
