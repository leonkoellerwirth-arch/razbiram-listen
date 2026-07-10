import { describe, expect, it } from "vitest";
import { ListenError, parseListenDocument } from "../src/loadListen";

describe("parseListenDocument", () => {
  it("accepts a minimal .listen.json", () => {
    const doc = parseListenDocument(
      JSON.stringify({ schemaVersion: "1.0.0", text: "Здравей.", sentences: [] }),
    );
    expect(doc.schemaVersion).toBe("1.0.0");
    expect(doc.sentences).toEqual([]);
  });

  it("rejects invalid JSON", () => {
    expect(() => parseListenDocument("{ not json")).toThrow(ListenError);
  });

  it("rejects a document without a sentences array", () => {
    expect(() => parseListenDocument(JSON.stringify({ text: "x" }))).toThrow(/sentences/);
  });

  it("rejects a non-object", () => {
    expect(() => parseListenDocument("42")).toThrow(ListenError);
  });
});
