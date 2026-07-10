import type { ListenDocument } from "./types";

/** Parse and shape-check a `.listen.json`. Permissive on optional fields, strict
 *  on the one thing the viewer needs: a `sentences` array. */
export function parseListenDocument(text: string): ListenDocument {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new ListenError("Die Datei ist kein gültiges JSON.");
  }
  if (data === null || typeof data !== "object") {
    throw new ListenError("Das ist keine .listen.json.");
  }
  const doc = data as Record<string, unknown>;
  if (!Array.isArray(doc.sentences)) {
    throw new ListenError("Das sieht nicht wie eine .listen.json aus — es fehlen sentences.");
  }
  return data as ListenDocument;
}

export class ListenError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ListenError";
  }
}
